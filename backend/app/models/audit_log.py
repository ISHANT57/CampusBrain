from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    # Nullable: /search accepts a service API key (SearchPrincipal.user_id is
    # None for that caller — see app/core/dependencies.py) with no user row to
    # attribute the call to. This was NOT NULL from the original admin-only
    # audit trail and never relaxed when the search endpoint's logging was
    # added, so every service-key search call violated the constraint and
    # 500'd — see migration f3a1b2c4d5e6.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # Dotted verb, e.g. "document.upload" -- room to grow into
    # "document.delete", "user.role_change" without a schema change.
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    # Text, not a FK: an audited resource can be a document today and a user
    # or a collection tomorrow, and this table must never block on which.
    resource_id = Column(String, nullable=True)
    # Small JSON blob (e.g. {"filename": "..."}). Text, not JSONB: this
    # table is written far more than it's queried, and Postgres JSON
    # querying isn't a need this project has yet.
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
