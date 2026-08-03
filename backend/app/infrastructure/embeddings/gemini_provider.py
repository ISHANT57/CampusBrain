from app.core.config import settings
from app.infrastructure.retry import post_with_retry
from app.infrastructure.usage import TokenUsage

# API contract confirmed against Google's current docs (2026):
#   POST https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent
#   header: x-goog-api-key
#   body:   {"model": "models/...", "content": {"parts": [{"text": ...}]},
#            "output_dimensionality": N}
#   response: {"embedding": {"values": [...], "shape": [...]}, "usageMetadata": {...}}
#
# output_dimensionality truncates gemini-embedding-001's native 3072-dim output
# (Matryoshka-trained, so truncated vectors stay meaningful — not naive slicing).
# 768 is one of Google's documented recommended cut points and keeps a
# collection well inside Qdrant Cloud's free 1GB cluster.
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"


class GeminiEmbeddingProvider:
    """EmbeddingProvider backed by Gemini's free-tier embedding API.

    Talks to the raw REST endpoint via httpx rather than the google-genai SDK —
    consistent with OpenRouterProvider's style, and one JSON call doesn't
    justify an extra dependency (ponytail).
    """

    def __init__(self) -> None:
        self._model = settings.embedding_model
        self._dimension = settings.embedding_dim

    @property
    def dimension(self) -> int:
        return self._dimension

    def _request(self, text: str):
        return post_with_retry(
            _ENDPOINT.format(model=self._model),
            headers={"x-goog-api-key": settings.gemini_api_key},
            json={
                "model": f"models/{self._model}",
                "content": {"parts": [{"text": text}]},
                "output_dimensionality": self._dimension,
            },
            timeout=60.0,
        )

    def embed(self, text: str) -> list[float]:
        return self._request(text).json()["embedding"]["values"]

    def embed_with_usage(self, text: str) -> tuple[list[float], TokenUsage | None]:
        payload = self._request(text).json()
        u = payload.get("usageMetadata")
        # embedContent's usageMetadata carries only a total -- there is no
        # separate "completion" side to an embedding call, so it's the whole
        # cost, not a component of it.
        usage = TokenUsage(
            prompt_tokens=u.get("totalTokenCount", 0), completion_tokens=0, total_tokens=u.get("totalTokenCount", 0),
        ) if u else None
        return payload["embedding"]["values"], usage
