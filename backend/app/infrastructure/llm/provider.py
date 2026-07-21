from app.infrastructure.llm.base import LLMProvider
from app.infrastructure.llm.openrouter_provider import OpenRouterProvider


def get_llm_provider() -> LLMProvider:
    # Single place that picks the implementation. Swap to an Ollama provider
    # here (or by config) without touching any calling code.
    return OpenRouterProvider()
