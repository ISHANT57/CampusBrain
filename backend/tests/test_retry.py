"""Retry classification for outbound Gemini calls (P1-5).

No network, no infra: httpx.post is monkeypatched and time.sleep is a no-op,
so this is fast and runs everywhere, unlike the integration-style tests that
need real Postgres/Qdrant.
"""

import httpx
import pytest

from app.infrastructure import retry as retry_mod

URL = "https://example.invalid/x"


def _response(status: int) -> httpx.Response:
    return httpx.Response(status_code=status, request=httpx.Request("POST", URL))


def _no_sleep(monkeypatch):
    monkeypatch.setattr(retry_mod.time, "sleep", lambda _seconds: None)


def test_first_attempt_success_returns_immediately(monkeypatch):
    _no_sleep(monkeypatch)
    calls = []
    monkeypatch.setattr(retry_mod.httpx, "post", lambda *a, **k: calls.append(1) or _response(200))
    r = retry_mod.post_with_retry(URL)
    assert r.status_code == 200
    assert len(calls) == 1


def test_500_then_200_retries_once_and_succeeds(monkeypatch):
    _no_sleep(monkeypatch)
    responses = iter([_response(500), _response(200)])
    monkeypatch.setattr(retry_mod.httpx, "post", lambda *a, **k: next(responses))
    r = retry_mod.post_with_retry(URL)
    assert r.status_code == 200


def test_client_error_is_never_retried(monkeypatch):
    """A bad request or a bad key doesn't get fixed by trying again --
    retrying it only adds latency to an already-final failure."""
    _no_sleep(monkeypatch)
    calls = []
    monkeypatch.setattr(retry_mod.httpx, "post", lambda *a, **k: calls.append(1) or _response(404))
    with pytest.raises(httpx.HTTPStatusError):
        retry_mod.post_with_retry(URL)
    assert len(calls) == 1


def test_429_exhausts_attempts_and_then_raises(monkeypatch):
    """INC-002: a 429 can mean 'come back tomorrow'. Retries are capped so a
    genuine quota exhaustion fails fast instead of amplifying the outage."""
    _no_sleep(monkeypatch)
    calls = []
    monkeypatch.setattr(retry_mod.httpx, "post", lambda *a, **k: calls.append(1) or _response(429))
    with pytest.raises(httpx.HTTPStatusError):
        retry_mod.post_with_retry(URL, max_attempts=3)
    assert len(calls) == 3


def test_timeout_is_retried_then_succeeds(monkeypatch):
    _no_sleep(monkeypatch)
    attempts = {"n": 0}

    def fake_post(*_a, **_k):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise httpx.TimeoutException("timed out")
        return _response(200)

    monkeypatch.setattr(retry_mod.httpx, "post", fake_post)
    r = retry_mod.post_with_retry(URL)
    assert r.status_code == 200
    assert attempts["n"] == 2


def test_connect_error_exhausts_attempts_and_reraises(monkeypatch):
    _no_sleep(monkeypatch)
    monkeypatch.setattr(retry_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("refused")))
    with pytest.raises(httpx.ConnectError):
        retry_mod.post_with_retry(URL, max_attempts=2)
