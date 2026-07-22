"""Regression tests for the four security bugs found during development.

Integration-style: runs against the real Postgres + Supabase Storage
configured in .env, via
    docker compose exec backend pytest
Each test states the attack it prevents, so a future change that reintroduces
the bug fails here instead of in production.
"""

import uuid

import pytest
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.user import User, UserRole

client = TestClient(app)
ORG_ID = 1


def _unique_email(prefix: str) -> str:
    # Not .local/.test/.example — email-validator rejects reserved special-use
    # domains, so tests need a normal-looking one.
    return f"{prefix}-{uuid.uuid4().hex[:8]}@sitare.ac.in"


def _make_user(role: UserRole) -> tuple[User, str]:
    """Create a user directly (there is no registration endpoint any more) and
    return the user plus a bearer token for it."""
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


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_no_self_registration_endpoint():
    """BUG 1 (privilege escalation) is now structural: there is no public way
    to create an account at all, so there is no role to escalate. Accounts come
    from scripts/create_admin.py only."""
    res = client.post(
        "/api/v1/auth/register",
        json={"org_id": ORG_ID, "email": _unique_email("escalate"), "password": "pass1234"},
    )
    assert res.status_code == 404, res.text


def test_upload_filename_cannot_escape_storage_prefix():
    """BUG 2 (path traversal): the client filename was spliced straight into
    the object-storage key, so `../../` could escape the org prefix."""
    _, token = _make_user(UserRole.ADMIN)
    res = client.post(
        "/api/v1/documents",
        headers=_auth(token),
        files={"file": ("../../etc/passwd.txt", b"harmless test content", "text/plain")},
    )
    assert res.status_code == 201, res.text

    storage_key = res.json()["storage_key"]
    assert ".." not in storage_key
    assert storage_key.startswith(f"{ORG_ID}/")
    assert storage_key.count("/") == 1  # exactly one separator: <org_id>/<uuid><ext>


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no_header"),
        pytest.param({"Authorization": "Bearer not.a.jwt"}, id="malformed_token"),
    ],
)
def test_protected_route_returns_401_not_403(headers):
    """BUG 3: a missing Authorization header returned 403 (forbidden), which
    conflates 'not authenticated' with 'authenticated but not allowed'."""
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 401


def test_chat_is_public():
    """BUG 4 (IDOR on another user's conversation) is gone with the transcript
    itself: anonymous chat stores nothing server-side.

    Sends a deliberately invalid body so this asserts reachability without
    spending a real LLM call — 422 proves the request got as far as body
    validation with no token at all. A 401 here would mean chat went back
    behind auth and every student is locked out."""
    res = client.post("/api/v1/chat", json={"question": ""})
    assert res.status_code == 422, res.text


@pytest.mark.parametrize("role", [UserRole.STUDENT, UserRole.FACULTY])
def test_non_admin_cannot_upload_documents(role):
    """RBAC: uploading is restricted to Admin/Super Admin. Faculty is included
    here because it used to be allowed — this is the regression guard."""
    _, token = _make_user(role)
    res = client.post(
        "/api/v1/documents",
        headers=_auth(token),
        files={"file": ("notes.txt", b"some notes", "text/plain")},
    )
    assert res.status_code == 403


@pytest.mark.parametrize(
    "method,path,kwargs",
    [
        pytest.param("post", "/api/v1/documents", {"files": {"file": ("n.txt", b"x", "text/plain")}}, id="upload"),
        pytest.param("get", "/api/v1/documents/1", {}, id="get_document"),
        pytest.param("post", "/api/v1/search", {"json": {"query": "fees"}}, id="search"),
    ],
)
def test_knowledge_base_routes_reject_anonymous(method, path, kwargs):
    """Students have no account, so every document-management route has to
    turn away a request with no token — the chatbot being public must not
    have made anything else public."""
    res = getattr(client, method)(path, **kwargs)
    assert res.status_code == 401, res.text


def test_unsupported_file_type_is_rejected():
    """File validation sniffs real content, not the claimed extension."""
    _, token = _make_user(UserRole.ADMIN)
    res = client.post(
        "/api/v1/documents",
        headers=_auth(token),
        files={"file": ("looks_safe.txt", b"\x7fELF\x02\x01\x01\x00binary", "text/plain")},
    )
    assert res.status_code == 400
