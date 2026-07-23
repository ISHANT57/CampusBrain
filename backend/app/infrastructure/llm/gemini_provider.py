import httpx

from app.core.config import settings

# Same key and same REST style as embeddings/gemini_provider.py — one httpx
# call doesn't justify the google-genai SDK.
#   POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
#   header: x-goog-api-key
#   body:   {"contents": [{"parts": [{"text": prompt}]}]}
#   response: {"candidates": [{"content": {"parts": [{"text": ...}]}, ...}]}
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider:
    """LLMProvider backed by Gemini, reusing GEMINI_API_KEY.

    Replaced OpenRouter as the default: its free tier is 50 requests *per day*
    across all free models, which the chatbot exhausted in an afternoon and
    then returned 429 on every question until midnight UTC. No retry schedule
    fixes a daily cap — the only fix is a provider with a usable free quota,
    and this deploy already had a working Gemini key for embeddings.
    """

    def generate(self, prompt: str) -> str:
        response = httpx.post(
            _ENDPOINT.format(model=settings.gemini_llm_model),
            headers={"x-goog-api-key": settings.gemini_api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=120.0,
        )
        response.raise_for_status()

        candidate = response.json()["candidates"][0]
        # A safety block or a token-limit stop returns a candidate with no
        # parts at all. Reaching into ["parts"][0] would KeyError into an
        # opaque 500, so name the reason instead.
        parts = candidate.get("content", {}).get("parts", [])
        text = "".join(p["text"] for p in parts if "text" in p)
        if not text:
            raise RuntimeError(f"Gemini returned no text (finishReason={candidate.get('finishReason')})")
        return text
