from app.infrastructure.llm.base import LLMProvider
from app.infrastructure.llm.gemini_provider import GeminiProvider


def get_llm_provider() -> LLMProvider:
    # Single place that picks the implementation. Swap to an Ollama provider
    # here (or by config) without touching any calling code.
    #
    # Was OpenRouterProvider until its free tier's 50-requests-per-day cap
    # started 429ing every question. openrouter_provider.py is still here and
    # still works — put it back if the account ever gets credits.
    return GeminiProvider()
