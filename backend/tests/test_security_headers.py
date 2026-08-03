"""Phase 9: security headers on every response, and the Phase 7 tenant/user
log fields.

INTEGRATION TIER -- importing app.main runs storage.py's module-level
_ensure_bucket(), which is a real boto3 call with boto3's default retry
budget; against an unreachable endpoint that stalls for minutes rather than
failing fast. Same reason test_observability.py and test_security.py are
integration-tier. Run via:
    docker compose exec backend python -m pytest tests/test_security_headers.py

/health is the probe target because it's the one endpoint with no
dependencies at all -- these are middleware-level guarantees, so they must
hold on the simplest possible response, not just authenticated ones.
"""

# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient

from app.core.observability import tenant_id_var, user_id_var
from app.main import app

client = TestClient(app)


def test_security_headers_are_present_on_every_response():
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"


def test_security_headers_are_present_on_an_error_response():
    """A 404 goes through the same middleware -- headers must not be
    conditional on a happy path."""
    r = client.get("/no-such-route")
    assert r.status_code == 404
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_anonymous_request_logs_no_tenant_or_user(monkeypatch):
    """Anonymous chat genuinely has no tenant/user (ADR-008), and the
    middleware resets both per request -- so a request following an
    authenticated one must not inherit the previous caller's identity in its
    log line. That leak is the actual bug this reset prevents."""
    import logging

    events = []
    monkeypatch.setattr(
        logging.getLogger("http"), "info", lambda _msg, extra=None: events.append(extra["event"]),
    )

    # Simulate identity left behind on this task by a prior authenticated
    # request, which is exactly what would leak without the reset.
    tenant_id_var.set(999)
    user_id_var.set(888)

    client.get("/health")

    assert len(events) == 1
    assert events[0]["tenant_id"] is None
    assert events[0]["user_id"] is None
