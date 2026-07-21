from typing import Protocol


class LLMProvider(Protocol):
    def generate(self, prompt: str) -> str:
        """Return the model's completion for a single prompt."""
        ...
