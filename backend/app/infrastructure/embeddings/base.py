from typing import Protocol


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int:
        """Length of the vectors this provider returns. vector_store reads this
        to size the Qdrant collection — it must never be a value guessed or
        hardcoded separately from what embed() actually returns."""
        ...

    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for a single piece of text."""
        ...
