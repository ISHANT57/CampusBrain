"""Audit trail for admin actions that mutate an org's data or touch it under
a real, identified principal.

Written into the SAME db session as the action it records, and NOT
best-effort like app/infrastructure/cache.py: an audit row that silently
fails to write is worse than the request failing outright, because it then
looks identical to an action nobody performed. If this insert fails, the
whole request fails with it -- call record() before the caller's own
db.commit(), never in a separate try/except.

Covers, as of Phase 8: document upload (documents.py), login (auth.py),
and search (search.py). Deliberately NOT covered, and why:
  - delete / permission changes -- no such endpoint exists yet. Route it
    through record() the same way the moment one does, rather than starting
    a second logging path.
  - chat -- anonymous by design (ADR-008), no principal to attribute a turn
    to; already durably logged via rag_service's rag_answer observability
    event, which is the right layer for a high-volume, unauthenticated path.
  - failed logins -- no principal either (a typo'd email resolves to no user
    row at all); the 5/min rate limit is the actual defense here, not an
    audit trail.

user_id is Optional because /search accepts a service API key with no user
row behind it (app/core/dependencies.py's SearchPrincipal) -- that absence
is recorded as None, never guessed at.
"""

import json

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record(
    db: Session,
    *,
    org_id: int,
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str | int | None = None,
    detail: dict | None = None,
) -> None:
    db.add(AuditLog(
        org_id=org_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        detail=json.dumps(detail) if detail else None,
    ))
