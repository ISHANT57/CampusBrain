"""Unit tests for resolving a chat request's organization from its URL slug.

No DB — the session is stubbed:
    docker compose exec backend pytest tests/test_chat_org_routing.py

Guards the one thing that decides which college's documents a public visitor
can reach. An unknown slug must 404 rather than fall back to a default org,
which would quietly serve one tenant's corpus under another's URL.
"""

import pytest
from fastapi import HTTPException

from app.api.v1.chat import DEFAULT_ORG_SLUG, _org_id


class StubOrg:
    def __init__(self, org_id: int) -> None:
        self.id = org_id


class StubDB:
    """Enough of a Session to satisfy db.query(...).filter(...).first()."""

    def __init__(self, found: StubOrg | None) -> None:
        self._found = found

    def query(self, *_):
        return self

    def filter(self, *_):
        return self

    def first(self):
        return self._found


def test_known_slug_resolves_to_its_org():
    assert _org_id(StubDB(StubOrg(2)), "goqii") == 2


def test_unknown_slug_is_404_not_a_fallback():
    """Falling back to the default org would serve Sitare's documents to
    anyone who mistyped a tenant name — a wrong answer, confidently sourced."""
    with pytest.raises(HTTPException) as excinfo:
        _org_id(StubDB(None), "does-not-exist")
    assert excinfo.value.status_code == 404
    assert "does-not-exist" in excinfo.value.detail


def test_default_slug_is_looked_up_like_any_other():
    """The bare /chat route resolves through the same table rather than
    hardcoding an id, so renaming or re-seeding org 1 can't silently break it."""
    assert _org_id(StubDB(StubOrg(1)), DEFAULT_ORG_SLUG) == 1
