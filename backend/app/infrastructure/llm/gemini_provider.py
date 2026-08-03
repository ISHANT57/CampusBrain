import json
import time
from collections.abc import Iterator

import httpx

from app.core.config import settings
from app.infrastructure.llm.base import GenerationResult, StreamChunk
from app.infrastructure.retry import RETRYABLE_STATUS, backoff, post_with_retry
from app.infrastructure.usage import TokenUsage

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


def _extract_usage(payload: dict) -> TokenUsage | None:
    """payload["usageMetadata"], if present, in this codebase's field names.
    None (not a zero-valued TokenUsage) when absent -- absence means "the
    response didn't say", not "zero tokens were spent", and callers must not
    conflate the two.
    """
    u = payload.get("usageMetadata")
    if not u:
        return None
    return TokenUsage(
        prompt_tokens=u.get("promptTokenCount", 0),
        completion_tokens=u.get("candidatesTokenCount", 0),
        total_tokens=u.get("totalTokenCount", 0),
    )


def _parse_sse_json(line: str) -> dict | None:
    """A blank line (SSE's event separator) or anything not prefixed
    "data: " carries no payload."""
    if not line.startswith("data: "):
        return None
    return json.loads(line[len("data: "):])


def _sse_text_fragments(line: str) -> Iterator[str]:
    """One raw line from the SSE stream -> zero or more text fragments.

    A "data: " line with no candidates (or a candidate with no parts -- a
    pure finishReason/usage-only chunk) yields nothing; that's normal at the
    end of a stream, not an error.
    """
    payload = _parse_sse_json(line)
    if payload is None:
        return
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

    def generate(self, prompt: str) -> GenerationResult:
        response = post_with_retry(
            _ENDPOINT.format(model=settings.gemini_llm_model),
            headers={"x-goog-api-key": settings.gemini_api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=120.0,
        )
        payload = response.json()
        candidate = payload["candidates"][0]
        # A safety block or a token-limit stop returns a candidate with no
        # parts at all. Reaching into ["parts"][0] would KeyError into an
        # opaque 500, so name the reason instead.
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(p["text"] for p in parts if "text" in p)
        if not text:
            raise RuntimeError(f"Gemini returned no text (finishReason={candidate.get('finishReason')})")
        return GenerationResult(text=text, usage=_extract_usage(payload))

    def generate_stream(self, prompt: str) -> Iterator[StreamChunk]:
        """Yield the answer as it's generated. The final chunk (empty text)
        carries usage -- Gemini reports usageMetadata once the response is
        complete, not per-token, so there's no earlier chunk it could travel
        on.

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
                    last_usage = None
                    for line in response.iter_lines():
                        for text in _sse_text_fragments(line):
                            got_any_text = True
                            yield StreamChunk(text=text)
                        payload = _parse_sse_json(line)
                        if payload is not None:
                            usage = _extract_usage(payload)
                            if usage is not None:
                                last_usage = usage
                    if not got_any_text:
                        raise RuntimeError("Gemini streamed no text at all (empty response)")
                    if last_usage is not None:
                        yield StreamChunk(text="", usage=last_usage)
                    return
            except (httpx.TimeoutException, httpx.ConnectError):
                if attempt == max_attempts - 1:
                    raise
                time.sleep(backoff(attempt))
