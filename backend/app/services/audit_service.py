"""Audit trail for admin actions that mutate an org's data.

Written into the SAME db session as the mutation it records, and NOT
best-effort like app/infrastructure/cache.py: an audit row that silently
fails to write is worse than the request failing outright, because it then
looks identical to an action nobody performed. If this insert fails, the
whole request fails with it -- call record() before the caller's own
db.commit(), never in a separate try/except.

Currently the only mutation this covers is document upload -- there is no
document-delete endpoint yet (P2-14/roadmap notes this explicitly). Route any
future mutating endpoint (delete, reprocess, role change) through record()
the same way, rather than starting a second logging path.
"""

import json

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record(
    db: Session,
    *,
    org_id: int,
    user_id: int,
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
