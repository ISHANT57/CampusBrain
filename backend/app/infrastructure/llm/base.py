from collections.abc import Iterator
from typing import Protocol


class LLMProvider(Protocol):
    def generate(self, prompt: str) -> str:
        """Return the model's completion for a single prompt."""
        ...

    def generate_stream(self, prompt: str) -> Iterator[str]:
        """Yield the completion in pieces as it's generated.

        Only implemented on the active provider (GeminiProvider). Not on
        OpenRouterProvider: it's dead code per ADR-003, and streaming for a
        provider nothing selects would be speculative work with no caller.
        """
        ...
