"""Unit tests for the Jina reranker client.

No network — httpx.post is stubbed:
    docker compose exec backend pytest tests/test_reranker.py

Two things worth guarding. The API returns results ordered BY SCORE, not by
input index, so scores have to be mapped back onto the texts they belong to —
read positionally, every chunk gets someone else's score and retrieval quietly
gets worse rather than visibly breaking. And this runs in the request path of
a public endpoint, so nothing it does may raise.
"""

import httpx
import pytest

from app.core.config import settings
from app.infrastructure import reranker

TEXTS = ["about fees", "about KlearNow students", "about attendance"]


@pytest.fixture(autouse=True)
def _with_key(monkeypatch):
    monkeypatch.setattr(settings, "jina_api_key", "test-key")


def stub_post(payload: dict | None = None, exc: Exception | None = None, status: int = 200):
    def fake_post(url, **kwargs):
        if exc is not None:
            raise exc
        return httpx.Response(
            status, json=payload or {}, request=httpx.Request("POST", "https://x")
        )

    return fake_post


def test_scores_are_realigned_to_input_order(monkeypatch):
    """The API ranks best-first; index 1 scoring highest must not put that
    score on text 0."""
    monkeypatch.setattr(
        reranker.httpx,
        "post",
        stub_post({"results": [
            {"index": 1, "relevance_score": 0.9},
            {"index": 2, "relevance_score": -0.1},
            {"index": 0, "relevance_score": -0.3},
        ]}),
    )
    assert reranker.rerank("who went to KlearNow", TEXTS) == [-0.3, 0.9, -0.1]


def test_no_key_configured_disables_reranking(monkeypatch):
    """An unset key must not attempt a call — deploys without one are meant to
    behave exactly as they did before."""
    monkeypatch.setattr(settings, "jina_api_key", "")
    monkeypatch.setattr(
        reranker.httpx, "post", stub_post(exc=AssertionError("must not be called"))
    )
    assert reranker.rerank("q", TEXTS) is None


def test_empty_candidate_list_is_not_a_call():
    assert reranker.rerank("q", []) is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"exc": httpx.ReadTimeout("too slow")},
        {"exc": httpx.ConnectError("no route")},
        {"status": 401, "payload": {"detail": "bad key"}},
        {"status": 503, "payload": {"detail": "overloaded"}},
        {"payload": {"unexpected": "shape"}},
    ],
)
def test_every_failure_degrades_to_none(monkeypatch, kwargs):
    """Timeout, refused connection, expired key, provider outage, changed
    response shape — all mean 'no scores, carry on', never a 500. An exhausted
    free tier on a different provider took this app down once already."""
    monkeypatch.setattr(reranker.httpx, "post", stub_post(**kwargs))
    assert reranker.rerank("q", TEXTS) is None


def test_out_of_range_index_is_ignored(monkeypatch):
    """A malformed index must not IndexError its way into the request path."""
    monkeypatch.setattr(
        reranker.httpx,
        "post",
        stub_post({"results": [{"index": 99, "relevance_score": 0.5},
                               {"index": 0, "relevance_score": 0.2}]}),
    )
    assert reranker.rerank("q", TEXTS) == [0.2, 0.0, 0.0]
