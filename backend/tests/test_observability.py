"""Pillar 2 (Observability): structured logging, request correlation, the
readiness probe, and the metrics endpoint.

Unit-tier tests (formatter, filter, metrics math) need no infrastructure.
The readiness tests monkeypatch the dependency call itself, so they don't
need real Postgres/Qdrant either — only the "storage is down but chat still
works" case needs the real DB/Qdrant this suite already requires elsewhere
(see test_security.py):
    docker compose exec backend pytest tests/test_observability.py
"""

import json
import logging

# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient

from app.core import database, metrics
from app.core.observability import JsonFormatter, RequestIdFilter, request_id_var
from app.infrastructure import storage
from app.main import app

client = TestClient(app)


def test_request_id_appears_in_unrelated_module_logs():
    """The whole point of a Filter: a module that knows nothing about request
    ids still gets them attached to its records.

    Exercises the Filter directly rather than going through
    configure_logging() + caplog: configure_logging() calls
    root.handlers.clear(), which would also strip out pytest's own caplog
    handler (installed on the root logger before this test runs) -- a false
    negative on the test's own plumbing, not on RequestIdFilter itself.
    """
    filt = RequestIdFilter()
    token = request_id_var.set("test-abc")
    try:
        record = logging.LogRecord("some.third.party", logging.WARNING, __file__, 1, "hello", None, None)
        filt.filter(record)
    finally:
        request_id_var.reset(token)
    assert record.request_id == "test-abc"


def test_formatter_emits_valid_json_with_flattened_event():
    rec = logging.LogRecord("rag", logging.INFO, __file__, 1, "answered", None, None)
    rec.event = {"event": "rag_answer", "org_id": 3, "refused": False}
    parsed = json.loads(JsonFormatter().format(rec))
    assert parsed["org_id"] == 3 and parsed["event"] == "rag_answer"


def test_newline_in_client_request_id_cannot_forge_a_log_line():
    """Log injection: a client-supplied id containing \\n must not split one
    JSON line into two."""
    rec = logging.LogRecord("http", logging.INFO, __file__, 1, "request", None, None)
    rec.request_id = "abc\nlevel=ERROR msg=fake"
    line = JsonFormatter().format(rec)
    assert line.count("\n") == 0
    assert json.loads(line)["request_id"] == "abc\nlevel=ERROR msg=fake"


def test_endpoint_returns_and_honours_request_id_header():
    r = client.get("/health", headers={"X-Request-Id": "client-supplied-123"})
    assert r.headers["X-Request-Id"] == "client-supplied-123"

    r2 = client.get("/health")
    assert len(r2.headers["X-Request-Id"]) > 0


def test_percentile_on_empty_returns_zero_not_crash():
    """A metrics endpoint that 500s during an incident is worse than useless."""
    assert metrics._pct([], 0.95) == 0.0


def test_latency_buffer_is_bounded():
    """Unbounded growth would OOM the only worker on a 512 MB box."""
    metrics._latencies.pop("t", None)
    for i in range(5000):
        metrics.observe("t", float(i))
    assert len(metrics._latencies["t"]) == 1000


def test_rates_are_none_not_zerodivision_before_first_answer():
    metrics._counters.clear()
    assert metrics.snapshot()["rates"]["refusal_rate"] is None


def test_metrics_endpoint_requires_credentials():
    assert client.get("/metrics").status_code == 401


def test_liveness_stays_200_when_postgres_is_down(monkeypatch):
    """The single most important test in this concept: liveness must NOT
    check dependencies, or a DB blip becomes a restart storm."""
    monkeypatch.setattr(database, "SessionLocal", lambda: (_ for _ in ()).throw(Exception("down")))
    assert client.get("/health").status_code == 200


def test_readiness_returns_503_when_postgres_is_down(monkeypatch):
    monkeypatch.setattr(database, "SessionLocal", lambda: (_ for _ in ()).throw(Exception("down")))
    r = client.get("/health/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["postgres"].startswith("error")


def test_readiness_does_not_leak_credentials(monkeypatch):
    """Unauthenticated endpoint: an exception message can contain a DSN."""
    def boom():
        raise Exception("could not connect to postgresql://user:hunter2@host/db")
    monkeypatch.setattr(database, "SessionLocal", boom)
    assert "hunter2" not in client.get("/health/ready").text


def test_readiness_stays_200_when_only_storage_is_down(monkeypatch):
    """Graceful degradation: storage is needed to ingest, not to chat. Failing
    readiness here would take chat down for every student because an admin
    can't upload. Requires real Postgres + Qdrant (see module docstring)."""
    monkeypatch.setattr(storage, "health_check", lambda: (False, "unreachable"))
    r = client.get("/health/ready")
    assert r.json()["checks"]["storage"] == "error"
    assert r.status_code == 200
    assert r.json()["status"] == "ready"
