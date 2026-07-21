# pyrefly: ignore [missing-import]
from sqlalchemy import Column, Computed, DateTime, ForeignKey, Index, Integer, String
# pyrefly: ignore [missing-import]
from sqlalchemy.dialects.postgresql import TSVECTOR
# pyrefly: ignore [missing-import]
from sqlalchemy.sql import func

from app.core.database import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    # Denormalized (not just derivable via a join to documents) so Chunk plugs
    # directly into OrgScopedRepository like every other org-scoped table.
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    text = Column(String, nullable=False)
    # Generated column: Postgres maintains the tsvector itself for existing and
    # future rows, so keyword search needs no application code and no backfill.
    search_vector = Column(TSVECTOR, Computed("to_tsvector('english', text)", persisted=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_chunks_search_vector", "search_vector", postgresql_using="gin"),
    )
