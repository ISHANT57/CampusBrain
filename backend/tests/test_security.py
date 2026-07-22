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
from app.models.conversation import Conversation
from app.models.user import User, UserRole

client = TestClient(app)
ORG_ID = 1


def _unique_email(prefix: str) -> str:
    # Not .local/.test/.example — email-validator rejects reserved special-use
    # domains, so tests need a normal-looking one.
    return f"{prefix}-{uuid.uuid4().hex[:8]}@sitare.ac.in"


def _make_user(role: UserRole) -> tuple[User, str]:
    """Create a user directly (public registration can only make Students) and
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


def test_register_ignores_client_supplied_role():
    """BUG 1 (privilege escalation): anyone could self-register as SUPER_ADMIN
    by putting `role` in the request body."""
    res = client.post(
        "/api/v1/auth/register",
        json={
            "org_id": ORG_ID,
            "email": _unique_email("escalate"),
            "password": "pass1234",
            "role": "super_admin",
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["role"] == "student"


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


def test_user_cannot_read_another_users_conversation():
    """BUG 4 (IDOR): org scoping alone let any user in the same organization
    read another user's private chat by guessing its id."""
    owner, owner_token = _make_user(UserRole.STUDENT)
    _, other_token = _make_user(UserRole.STUDENT)

    # Create the conversation directly so the test doesn't need an LLM call.
    db = SessionLocal()
    conversation = Conversation(org_id=ORG_ID, user_id=owner.id, title="private")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    conversation_id = conversation.id
    db.close()

    # The owner can read it...
    assert client.get(f"/api/v1/chat/{conversation_id}/messages", headers=_auth(owner_token)).status_code == 200

    # ...another user in the SAME org cannot read it...
    assert client.get(f"/api/v1/chat/{conversation_id}/messages", headers=_auth(other_token)).status_code == 404

    # ...nor continue it.
    hijack = client.post(
        "/api/v1/chat",
        headers=_auth(other_token),
        json={"conversation_id": conversation_id, "question": "what did they ask?"},
    )
    assert hijack.status_code == 404


def test_student_cannot_upload_documents():
    """RBAC: uploading is restricted to Faculty/Admin/Super Admin."""
    _, student_token = _make_user(UserRole.STUDENT)
    res = client.post(
        "/api/v1/documents",
        headers=_auth(student_token),
        files={"file": ("notes.txt", b"some notes", "text/plain")},
    )
    assert res.status_code == 403


def test_unsupported_file_type_is_rejected():
    """File validation sniffs real content, not the claimed extension."""
    _, token = _make_user(UserRole.ADMIN)
    res = client.post(
        "/api/v1/documents",
        headers=_auth(token),
        files={"file": ("looks_safe.txt", b"\x7fELF\x02\x01\x01\x00binary", "text/plain")},
    )
    assert res.status_code == 400
