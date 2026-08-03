from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base


class UsageLog(Base):
    """Raw ledger of every metered LLM/embedding call. Deliberately dumb --
    token counts and the model that produced them, nothing derived (no cost,
    no aggregation). Cost is computed at read time from a pricing table
    (app/services/usage_service.py) so a price change never needs a backfill
    against history that already happened at the old price.
    """

    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    # Null for anonymous chat (this product has no student accounts, ADR-008)
    # -- populated only for the ingestion path, where the uploading admin is
    # known. "Top users" therefore reads as "top uploaders by embedding
    # spend", not per-student attribution; that's the honest shape of the
    # data, not a shortcut.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # Null for chat generation (not tied to one document); set for
    # ingestion, so "top documents by cost" has something to group on.
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)
    # From observability.py's request_id_var -- joins a cost row back to the
    # exact rag_answer log line for the same request. Null for ingestion,
    # which runs on a worker thread outside any HTTP request context.
    request_id = Column(String, nullable=True, index=True)
    operation = Column(String, nullable=False)  # "chat.generate" | "ingestion.embed"
    model = Column(String, nullable=False)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
