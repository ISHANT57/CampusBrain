import time

import httpx

from app.core.config import settings


class OpenRouterProvider:
    """LLMProvider backed by OpenRouter's hosted models. Swappable for a local
    Ollama provider later — nothing outside this class knows the difference."""

    def generate(self, prompt: str) -> str:
        # Free-tier models throttle aggressively; retry 429s with linear backoff.
        # ponytail: fixed 3 retries, swap for a queue if throughput ever matters.
        for attempt in range(3):
            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=120.0,
            )
            if response.status_code == 429 and attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
