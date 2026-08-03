"""Phase 5: API integration tests against real infrastructure.

INTEGRATION TIER -- needs the real Postgres/Qdrant/Supabase from .env:
    docker compose exec backend python -m pytest tests/test_integration_api.py

Covers the Phase 5 list that wasn't already covered elsewhere. What's
already tested and deliberately not duplicated here:
  - upload / RBAC / anonymous rejection -> tests/test_security.py
  - document read endpoints            -> tests/test_document_read_api.py
  - login + search audit rows          -> tests/test_audit_expansion.py
  - ingestion retry/backoff logic      -> tests/test_ingestion_queue.py (unit)

What this file adds: the durable-queue behaviors that only mean anything
against a real database (claim atomicity, stale-lease recovery), and RBAC on
the endpoints added in Phases 3, 4 and 9.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.document import Document, DocumentStatus
from app.models.ingestion_job import IngestionJob, IngestionJobStatus
from app.models.user import User, UserRole
from app.services import ingestion_queue

client = TestClient(app)
ORG_ID = 1


def _make_user(role: UserRole) -> tuple[User, str]:
    email = f"{role.value}-{uuid.uuid4().hex[:8]}@sitare.ac.in"
    db = SessionLocal()
    user = User(org_id=ORG_ID, email=email, hashed_password=hash_password("pass1234"), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.expunge(user)
    db.close()
    res = client.post("/api/v1/auth/login", json={"org_id": ORG_ID, "email": email, "password": "pass1234"})
    assert res.status_code == 200, res.text
    return user, res.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_document(status=DocumentStatus.PENDING) -> Document:
    db = SessionLocal()
    doc = Document(
        org_id=ORG_ID, filename=f"t-{uuid.uuid4().hex[:6]}.txt", mime_type="text/plain",
        size_bytes=10, status=status, storage_key=f"{ORG_ID}/{uuid.uuid4()}.txt",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    db.expunge(doc)
    db.close()
    return doc


# --- durable queue: the behaviors that need a real database ----------------

def test_a_claimed_job_cannot_be_claimed_twice():
    """FOR UPDATE SKIP LOCKED's whole purpose. A unit test can't prove this
    -- it's a property of the SQL, not of Python."""
    doc = _make_document()
    db = SessionLocal()
    try:
        ingestion_queue.enqueue(db, org_id=ORG_ID, document_id=doc.id)
        db.commit()
    finally:
        db.close()

    db1, db2 = SessionLocal(), SessionLocal()
    try:
        first = ingestion_queue.claim_next(db1)
        assert first is not None
        claimed_ids = {first.id}
        # Drain anything else pending from other tests, then confirm the same
        # row never comes back twice.
        while (nxt := ingestion_queue.claim_next(db2)) is not None:
            assert nxt.id not in claimed_ids
            claimed_ids.add(nxt.id)
    finally:
        db1.close()
        db2.close()


def test_claiming_increments_attempts_so_a_crash_loop_is_bounded():
    doc = _make_document()
    db = SessionLocal()
    try:
        job = ingestion_queue.enqueue(db, org_id=ORG_ID, document_id=doc.id)
        db.commit()
        job_id = job.id
    finally:
        db.close()

    db = SessionLocal()
    try:
        while (claimed := ingestion_queue.claim_next(db)) is not None:
            if claimed.id == job_id:
                assert claimed.attempts == 1
                assert claimed.status == IngestionJobStatus.PROCESSING
                return
    finally:
        db.close()
    pytest.fail("the enqueued job was never claimed")


def test_a_stale_processing_job_is_recovered_to_pending():
    """The Render-sleeps-mid-job recovery path (P0-1a). Simulated by writing
    a claimed_at older than the lease -- which is exactly the state a killed
    worker leaves behind."""
    doc = _make_document()
    db = SessionLocal()
    try:
        job = ingestion_queue.enqueue(db, org_id=ORG_ID, document_id=doc.id)
        job.status = IngestionJobStatus.PROCESSING
        job.claimed_at = datetime.now(timezone.utc) - timedelta(
            seconds=ingestion_queue.LEASE_TIMEOUT_SECONDS + 60,
        )
        db.commit()
        job_id = job.id

        recovered = ingestion_queue.recover_stale_jobs(db)
        assert recovered >= 1

        db.expire_all()
        assert db.get(IngestionJob, job_id).status == IngestionJobStatus.PENDING
    finally:
        db.close()


def test_a_freshly_claimed_job_is_not_reaped():
    """The other half: the reaper must not steal work from a worker that's
    still alive and mid-ingest."""
    doc = _make_document()
    db = SessionLocal()
    try:
        job = ingestion_queue.enqueue(db, org_id=ORG_ID, document_id=doc.id)
        job.status = IngestionJobStatus.PROCESSING
        job.claimed_at = datetime.now(timezone.utc)  # just now
        db.commit()
        job_id = job.id

        ingestion_queue.recover_stale_jobs(db)

        db.expire_all()
        assert db.get(IngestionJob, job_id).status == IngestionJobStatus.PROCESSING
    finally:
        db.close()


# --- RBAC on the endpoints added in Phases 3, 4 and 9 ---------------------

@pytest.mark.parametrize("path", ["/api/v1/usage/summary", "/api/v1/evaluation/stats", "/api/v1/audit-logs"])
def test_admin_only_endpoints_reject_anonymous(path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", ["/api/v1/usage/summary", "/api/v1/evaluation/stats", "/api/v1/audit-logs"])
def test_admin_only_endpoints_reject_a_student(path):
    _user, token = _make_user(UserRole.STUDENT)
    assert client.get(path, headers=_auth(token)).status_code == 403


@pytest.mark.parametrize("path", ["/api/v1/usage/summary", "/api/v1/evaluation/stats", "/api/v1/audit-logs"])
def test_admin_only_endpoints_allow_an_admin(path):
    _user, token = _make_user(UserRole.ADMIN)
    assert client.get(path, headers=_auth(token)).status_code == 200


def test_evaluation_stats_never_claims_unscored_metrics():
    """Phase 4's honesty guarantee, asserted at the HTTP boundary."""
    _user, token = _make_user(UserRole.ADMIN)
    body = client.get("/api/v1/evaluation/stats", headers=_auth(token)).json()
    for forbidden in ("recall", "precision", "groundedness", "hallucination_rate"):
        assert forbidden not in body


def test_download_returns_a_signed_url_and_is_admin_only():
    doc = _make_document()
    assert client.get(f"/api/v1/documents/{doc.id}/download").status_code == 401

    _user, student_token = _make_user(UserRole.STUDENT)
    assert client.get(f"/api/v1/documents/{doc.id}/download", headers=_auth(student_token)).status_code == 403

    _admin, admin_token = _make_user(UserRole.ADMIN)
    res = client.get(f"/api/v1/documents/{doc.id}/download", headers=_auth(admin_token))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["expires_in"] == 900
    # A signed URL, not a bare object path: the signature params are the
    # whole point -- without them the bucket being Private makes it useless.
    assert "X-Amz-Signature" in body["url"] or "Signature" in body["url"]


def test_cross_tenant_document_access_is_impossible():
    """Tenant isolation at the API boundary: org_id comes from the verified
    credential, never a path or body, so another org's document id must 404
    rather than leak."""
    db = SessionLocal()
    try:
        other = Document(
            org_id=999, filename="other-org.txt", mime_type="text/plain", size_bytes=1,
            status=DocumentStatus.PROCESSED, storage_key="999/x.txt",
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        other_id = other.id
    finally:
        db.close()

    _admin, token = _make_user(UserRole.ADMIN)  # org 1
    assert client.get(f"/api/v1/documents/{other_id}", headers=_auth(token)).status_code == 404
    assert client.get(f"/api/v1/documents/{other_id}/download", headers=_auth(token)).status_code == 404
