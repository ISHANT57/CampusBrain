from app.infrastructure.embeddings.base import EmbeddingProvider
from app.infrastructure.embeddings.gemini_provider import GeminiEmbeddingProvider


def get_embedding_provider() -> EmbeddingProvider:
    # Single place that picks the implementation — mirrors
    # app/infrastructure/llm/provider.py. Swap to an OpenAI, Voyage AI, Jina AI,
    # or Ollama provider here (or by config) without touching retrieval_service,
    # document_processing_service, or vector_store: none of them know which
    # provider is in use, only that it satisfies EmbeddingProvider.
    return GeminiEmbeddingProvider()
