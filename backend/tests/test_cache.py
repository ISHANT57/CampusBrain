"""Query-embedding cache (P1-10 / Tier-1 "Redis Cache").

httpx.post is monkeypatched throughout -- no real Upstash account or network
needed to verify the fail-open contract, which is the property that matters
most: a cache bug must never turn into a chat outage.
"""

import httpx
import pytest

from app.core import metrics
from app.infrastructure import cache


@pytest.fixture(autouse=True)
def _clear_counters():
    metrics._counters.clear()


def test_disabled_when_no_url_configured(monkeypatch):
    """Default deploys have no Upstash account -- this must be a silent
    no-op, not a startup requirement."""
    monkeypatch.setattr(cache.settings, "upstash_redis_rest_url", "")
    assert cache.get_embedding("ns", "hello") is None
    cache.set_embedding("ns", "hello", [0.1, 0.2])  # must not raise


def test_hit_after_set(monkeypatch):
    monkeypatch.setattr(cache.settings, "upstash_redis_rest_url", "https://x.upstash.io")
    store: dict[str, str] = {}

    def fake_post(_url, json, **_kw):
        cmd = json
        if cmd[0] == "SET":
            store[cmd[1]] = cmd[2]
            return httpx.Response(200, json={"result": "OK"}, request=httpx.Request("POST", "https://x"))
        if cmd[0] == "GET":
            return httpx.Response(200, json={"result": store.get(cmd[1])}, request=httpx.Request("POST", "https://x"))
        raise AssertionError(cmd)

    monkeypatch.setattr(cache.httpx, "post", fake_post)

    assert cache.get_embedding("ns", "how many students") is None
    cache.set_embedding("ns", "how many students", [0.1, 0.2, 0.3])
    assert cache.get_embedding("ns", "how many students") == [0.1, 0.2, 0.3]

    snap = metrics.snapshot()["counters"]
    assert snap["cache.embedding.miss"] == 1
    assert snap["cache.embedding.hit"] == 1


def test_any_transport_failure_is_a_miss_not_an_exception(monkeypatch):
    """The whole point of this design: a downed or misconfigured cache must
    degrade chat to 'no cache', never to a 500."""
    monkeypatch.setattr(cache.settings, "upstash_redis_rest_url", "https://x.upstash.io")
    monkeypatch.setattr(cache.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))

    assert cache.get_embedding("ns", "anything") is None
    cache.set_embedding("ns", "anything", [1.0])  # must not raise either


def test_different_namespaces_do_not_collide():
    """A model or dimension change (ADR-009) must not serve a vector cached
    under the old shape."""
    k1 = cache._key("gemini-embedding-001:768", "fees")
    k2 = cache._key("gemini-embedding-001:1536", "fees")
    assert k1 != k2
