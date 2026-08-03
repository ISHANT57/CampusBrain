import enum

# pyrefly: ignore [missing-import]
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Text
# pyrefly: ignore [missing-import]
from sqlalchemy.sql import func

from app.core.database import Base


class IngestionJobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    # Nullable: tools/ingest.py creates jobs with no uploading user at all.
    # Threaded through to index_document so ingestion-side token usage
    # (usage_service, Phase 3) can attribute cost to whoever uploaded it --
    # without this, "top users" on the cost dashboard would only ever be
    # empty, since chat itself is anonymous (ADR-008).
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    status = Column(
        Enum(IngestionJobStatus, name="ingestion_job_status", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=IngestionJobStatus.PENDING,
        index=True,
    )
    # Incremented at CLAIM time, not at completion -- so a worker that claims
    # a job and then dies mid-processing (Render restart) still counts as one
    # attempt once the stale-job reaper puts it back to pending, rather than
    # letting a crash loop retry forever for free.
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    last_error = Column(Text, nullable=True)
    # Set when a worker claims the job; the reaper uses this to find jobs
    # whose worker died without ever reaching completed/failed.
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    # Backoff is expressed by moving this forward, not by sleeping in the
    # worker -- a delayed retry is just a row the claim query doesn't select
    # yet, so it survives a restart for free, same as everything else here.
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
