import time

import httpx

from app.core.config import settings


class OpenRouterProvider:
    """LLMProvider backed by OpenRouter's hosted models. Swappable for a local
    Ollama provider later — nothing outside this class knows the difference."""

    def generate(self, prompt: str) -> str:
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
            return response.json()["choices"][0]["message"]["content"]
