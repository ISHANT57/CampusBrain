"""Token-usage types shared by the LLM and embedding provider protocols.

Lives outside both app/infrastructure/llm/ and app/infrastructure/embeddings/
because both need the same shape -- putting it in either would make the
other import across a sibling package for no reason.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
