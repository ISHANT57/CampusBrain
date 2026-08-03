import json
import time
from collections.abc import Iterator

import httpx

from app.core.config import settings
from app.infrastructure.retry import RETRYABLE_STATUS, backoff, post_with_retry

# Same key and same REST style as embeddings/gemini_provider.py — one httpx
# call doesn't justify the google-genai SDK.
#   POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
#   header: x-goog-api-key
#   body:   {"contents": [{"parts": [{"text": prompt}]}]}
#   response: {"candidates": [{"content": {"parts": [{"text": ...}]}, ...}]}
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Same request shape, "streamGenerateContent" instead of "generateContent",
# plus alt=sse so the wire format is Server-Sent Events: repeated
# "data: {json}\n\n" lines, each one a partial GenerateContentResponse.
_STREAM_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent"


def _sse_text_fragments(line: str) -> Iterator[str]:
    """One raw line from the SSE stream -> zero or more text fragments.

    A blank line (SSE's event separator) or anything not prefixed "data: "
    carries nothing. A "data: " line with no candidates (or a candidate with
    no parts -- a pure finishReason chunk) yields nothing either; that's
    normal at the end of a stream, not an error.
    """
    if not line.startswith("data: "):
        return
    payload = json.loads(line[len("data: "):])
    candidates = payload.get("candidates") or []
    if not candidates:
        return
    for part in candidates[0].get("content", {}).get("parts", []):
        if "text" in part:
            yield part["text"]


class GeminiProvider:
    """LLMProvider backed by Gemini, reusing GEMINI_API_KEY.

    Replaced OpenRouter as the default: its free tier is 50 requests *per day*
    across all free models, which the chatbot exhausted in an afternoon and
    then returned 429 on every question until midnight UTC. No retry schedule
    fixes a daily cap — the only fix is a provider with a usable free quota,
    and this deploy already had a working Gemini key for embeddings.
    """

    def generate(self, prompt: str) -> str:
        response = post_with_retry(
            _ENDPOINT.format(model=settings.gemini_llm_model),
            headers={"x-goog-api-key": settings.gemini_api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=120.0,
        )
        candidate = response.json()["candidates"][0]
        # A safety block or a token-limit stop returns a candidate with no
        # parts at all. Reaching into ["parts"][0] would KeyError into an
        # opaque 500, so name the reason instead.
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(p["text"] for p in parts if "text" in p)
        if not text:
            raise RuntimeError(f"Gemini returned no text (finishReason={candidate.get('finishReason')})")
        return text

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """Yield the answer as it's generated.

        Retries only cover opening the connection (a 5xx/429 on the initial
        response, or a connect/timeout error before any bytes arrive).
        post_with_retry can't be reused as-is: once tokens have started
        reaching the caller there's no single response body left to retry --
        restarting transparently would mean re-sending a partial answer.
        """
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                with httpx.stream(
                    "POST",
                    _STREAM_ENDPOINT.format(model=settings.gemini_llm_model),
                    headers={"x-goog-api-key": settings.gemini_api_key},
                    params={"alt": "sse"},
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=120.0,
                ) as response:
                    if response.status_code in RETRYABLE_STATUS and attempt < max_attempts - 1:
                        time.sleep(backoff(attempt))
                        continue
                    response.raise_for_status()

                    got_any_text = False
                    for line in response.iter_lines():
                        for text in _sse_text_fragments(line):
                            got_any_text = True
                            yield text
                    if not got_any_text:
                        raise RuntimeError("Gemini streamed no text at all (empty response)")
                    return
            except (httpx.TimeoutException, httpx.ConnectError):
                if attempt == max_attempts - 1:
                    raise
                time.sleep(backoff(attempt))
