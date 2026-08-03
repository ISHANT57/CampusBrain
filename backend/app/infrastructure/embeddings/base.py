from typing import Protocol

from app.infrastructure.usage import TokenUsage


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int:
        """Length of the vectors this provider returns. vector_store reads this
        to size the Qdrant collection — it must never be a value guessed or
        hardcoded separately from what embed() actually returns."""
        ...

    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for a single piece of text.

        No usage returned here on purpose: this is the query-time path,
        cache-checked in retrieval_service.py, called on every chat/search
        request. Widening its signature would mean every caller -- most of
        which only ever want the vector -- has to unpack a tuple. Ingestion
        is the one caller that tracks embedding cost; it uses
        embed_with_usage() below instead.
        """
        ...

    def embed_with_usage(self, text: str) -> tuple[list[float], TokenUsage | None]:
        """Same as embed(), but also returns token usage. Used only by
        document ingestion (app/services/document_processing_service.py),
        which is the one caller with a document to attribute the cost to and
        a call volume low enough that tracking every call is cheap."""
        ...
