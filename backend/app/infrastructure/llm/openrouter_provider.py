import time

import httpx

from app.core.config import settings
from app.infrastructure.llm.base import GenerationResult
from app.infrastructure.usage import TokenUsage


class OpenRouterProvider:
    """LLMProvider backed by OpenRouter's hosted models. Swappable for a local
    Ollama provider later — nothing outside this class knows the difference."""

    def generate(self, prompt: str) -> GenerationResult:
        # Free-tier models throttle aggressively; retry 429s with exponential backoff.
        max_attempts = 5
        for attempt in range(max_attempts):
            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=120.0,
            )
            if response.status_code == 429 and attempt < max_attempts - 1:
                sleep_time = 5 * (2 ** attempt)  # 5, 10, 20, 40 seconds
                time.sleep(sleep_time)
                continue
            response.raise_for_status()
            payload = response.json()
            text = payload["choices"][0]["message"]["content"]
            # OpenAI-compatible shape: {"usage": {"prompt_tokens", "completion_tokens", "total_tokens"}}.
            # Kept in sync with LLMProvider's Protocol even though this path
            # is dead (ADR-003) -- re-enabling it (a credited OpenRouter
            # account) must not silently break rag_service's result.text /
            # result.usage access with an AttributeError.
            u = payload.get("usage")
            usage = TokenUsage(
                prompt_tokens=u["prompt_tokens"], completion_tokens=u["completion_tokens"],
                total_tokens=u["total_tokens"],
            ) if u else None
            return GenerationResult(text=text, usage=usage)
