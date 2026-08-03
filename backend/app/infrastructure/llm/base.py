from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from app.infrastructure.usage import TokenUsage


@dataclass(frozen=True)
class GenerationResult:
    text: str
    # None when the provider's response didn't carry usage data (a
    # malformed/unexpected payload shape) -- callers must treat "no usage"
    # as "nothing to record", never as "zero tokens spent".
    usage: TokenUsage | None


@dataclass(frozen=True)
class StreamChunk:
    # Empty on the final sentinel chunk that carries usage -- Gemini's SSE
    # stream reports usageMetadata once the response is complete, not
    # per-token, so there is no earlier chunk it could ride along on.
    text: str
    usage: TokenUsage | None = None


class LLMProvider(Protocol):
    def generate(self, prompt: str) -> GenerationResult:
        """Return the model's completion for a single prompt, with usage."""
        ...

    def generate_stream(self, prompt: str) -> Iterator[StreamChunk]:
        """Yield the completion in pieces as it's generated. The last chunk
        yielded carries the request's usage; every other chunk's usage is
        None.

        Only implemented on the active provider (GeminiProvider). Not on
        OpenRouterProvider: it's dead code per ADR-003, and streaming for a
        provider nothing selects would be speculative work with no caller.
        """
        ...
