import httpx

from app.core.config import settings


class OpenRouterProvider:
    """LLMProvider backed by OpenRouter's hosted models. Swappable for a local
    Ollama provider later — nothing outside this class knows the difference."""

    def generate(self, prompt: str) -> str:
        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120.0,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
