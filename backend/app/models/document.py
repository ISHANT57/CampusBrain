import enum

# pyrefly: ignore [missing-import]
from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, Integer, String
# pyrefly: ignore [missing-import]
from sqlalchemy.sql import func

from app.core.database import Base


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=True, index=True)
    filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    status = Column(
        Enum(DocumentStatus, name="document_status", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
        default=DocumentStatus.PENDING,
    )
    # Populated once upload/storage is wired in (Phase 4) — not used yet.
    storage_key = Column(String, nullable=True)
    # sha256 of the raw bytes. Set only by tools/ingest.py, which uses it to
    # skip files it has already indexed; API uploads leave it NULL (they have
    # no re-run semantics to dedup against). Not exposed in DocumentRead —
    # deliberately internal, so the API response shape is unchanged.
    content_hash = Column(String(64), nullable=True, index=True)
    # Populated once real extraction runs (M23). Language detection deliberately
    # skipped for now — no downstream consumer yet, would add a dependency for
    # a field nothing uses.
    page_count = Column(Integer, nullable=True)
    extraction_method = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
