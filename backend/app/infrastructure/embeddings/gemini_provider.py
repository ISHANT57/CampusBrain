import httpx

from app.core.config import settings

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

    def embed(self, text: str) -> list[float]:
        response = httpx.post(
            _ENDPOINT.format(model=self._model),
            headers={"x-goog-api-key": settings.gemini_api_key},
            json={
                "model": f"models/{self._model}",
                "content": {"parts": [{"text": text}]},
                "output_dimensionality": self._dimension,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()["embedding"]["values"]
