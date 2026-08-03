"""Audit trail for admin actions (Tier-1 "Audit Logs").

Unit-tier: db.add() is captured on a stub session, no real Postgres needed.
The end-to-end path (upload -> an audit_logs row survives commit) is covered
by test_security.py's style of integration test and needs real infra:
    docker compose exec backend pytest
"""

import json

from app.models.audit_log import AuditLog
from app.services import audit_service


class StubDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


def test_record_stores_the_given_fields():
    db = StubDB()
    audit_service.record(
        db, org_id=3, user_id=7, action="document.upload",
        resource_type="document", resource_id=42, detail={"filename": "x.pdf"},
    )
    assert len(db.added) == 1
    row = db.added[0]
    assert isinstance(row, AuditLog)
    assert (row.org_id, row.user_id, row.action, row.resource_type) == (3, 7, "document.upload", "document")
    assert row.resource_id == "42"  # stored as text -- a future resource may not have an int PK
    assert json.loads(row.detail) == {"filename": "x.pdf"}


def test_resource_id_and_detail_are_optional():
    db = StubDB()
    audit_service.record(db, org_id=1, user_id=1, action="user.login", resource_type="user")
    row = db.added[0]
    assert row.resource_id is None
    assert row.detail is None
