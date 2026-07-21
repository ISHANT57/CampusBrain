import httpx

from app.core.config import settings

# BGE-M3 is served by the local Ollama instance (already running for the LLM),
# avoiding a heavy torch/sentence-transformers dependency in the backend image.


def embed_text(text: str) -> list[float]:
    response = httpx.post(
        f"{settings.ollama_url}/api/embeddings",
        json={"model": settings.embedding_model, "prompt": text},
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()["embedding"]
