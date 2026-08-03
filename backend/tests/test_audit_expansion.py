"""Phase 8: audit coverage for login and search -- the two real, existing
endpoints that had an identifiable principal and weren't audited yet.

Integration-style, same convention as test_security.py: runs against the
real Postgres configured in .env, via
    docker compose exec backend pytest tests/test_audit_expansion.py

Deliberately NOT covered here (see ADR-013's sibling reasoning in
audit_service.py and dependencies.py):
  - "Delete" / "permission changes": no such endpoint exists yet. Auditing
    a mutation that can't happen would be a test for fiction.
  - "Chat": anonymous by design (ADR-008) -- no principal to attribute a
    chat turn to, and it's already durably logged via rag_service's
    rag_answer observability event.
  - Failed logins: no principal to attribute a failed attempt to either
    (a typo'd email resolves to no user row at all); brute-force defense
    here is the existing 5/min rate limit, not an audit trail.
"""

import uuid

import pytest
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole

client = TestClient(app)
ORG_ID = 1


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@sitare.ac.in"


def _make_user(role: UserRole) -> tuple[User, str]:
    email = _unique_email(role.value)
    db = SessionLocal()
    user = User(org_id=ORG_ID, email=email, hashed_password=hash_password("pass1234"), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.expunge(user)
    db.close()

    res = client.post(
        "/api/v1/auth/login", json={"org_id": ORG_ID, "email": email, "password": "pass1234"}
    )
    assert res.status_code == 200, res.text
    return user, res.json()["access_token"]


def _latest_audit_row(action: str) -> AuditLog | None:
    db = SessionLocal()
    try:
        return db.query(AuditLog).filter(AuditLog.action == action).order_by(AuditLog.id.desc()).first()
    finally:
        db.close()


def test_successful_login_is_audited():
    user, _token = _make_user(UserRole.ADMIN)
    row = _latest_audit_row("user.login")
    assert row is not None
    assert row.user_id == user.id
    assert row.org_id == ORG_ID
    assert row.resource_type == "user"


def test_failed_login_is_not_audited():
    """No principal to attribute a failed attempt to -- see module docstring."""
    before = _latest_audit_row("user.login")
    res = client.post(
        "/api/v1/auth/login", json={"org_id": ORG_ID, "email": "nobody@sitare.ac.in", "password": "wrong"},
    )
    assert res.status_code == 401
    after = _latest_audit_row("user.login")
    assert (before.id if before else None) == (after.id if after else None)


def test_search_by_an_admin_is_audited_with_the_user_id():
    _user, token = _make_user(UserRole.ADMIN)
    res = client.post(
        "/api/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        # keyword mode: no real embedding call needed, keeps this test fast
        # and free of external API spend for what's really a logging check.
        json={"query": "fees", "mode": "keyword", "top_k": 3},
    )
    assert res.status_code == 200, res.text

    row = _latest_audit_row("search.query")
    assert row is not None
    assert row.user_id == _user.id
    assert row.org_id == ORG_ID
    assert "fees" in row.detail


@pytest.fixture
def service_key_enabled(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "service_api_key", "test-key-for-audit-expansion")
    monkeypatch.setattr(settings, "service_api_key_org_id", ORG_ID)


def test_search_by_a_service_key_is_audited_with_no_user_id(service_key_enabled):
    res = client.post(
        "/api/v1/search",
        headers={"X-API-Key": "test-key-for-audit-expansion"},
        json={"query": "fees", "mode": "keyword", "top_k": 3},
    )
    assert res.status_code == 200, res.text

    row = _latest_audit_row("search.query")
    assert row is not None
    assert row.user_id is None  # no user row for a machine caller -- not guessed at
    assert row.org_id == ORG_ID
