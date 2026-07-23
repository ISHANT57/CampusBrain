"""P1-CHANGE-1: X-API-Key service auth on /search.

The change is additive and must stay that way. Half these tests exist to prove
the EXISTING admin-JWT path is untouched — a backward-compatibility claim
nobody verified is a claim nobody should believe.
"""

import secrets

import pytest
from fastapi import HTTPException

from app.core import dependencies
from app.core.config import settings
from app.core.rate_limit import rate_limit_key
from app.models.user import User, UserRole

VALID_KEY = "test-service-key-" + secrets.token_urlsafe(16)


@pytest.fixture
def service_key_enabled(monkeypatch):
    monkeypatch.setattr(settings, "service_api_key", VALID_KEY)
    monkeypatch.setattr(settings, "service_api_key_org_id", 1)


class FakeRequest:
    def __init__(self, headers: dict):
        self.headers = headers


# --- the new path -----------------------------------------------------------

def test_valid_api_key_resolves_to_the_configured_org(service_key_enabled):
    assert dependencies.require_search_access(x_api_key=VALID_KEY, credentials=None, db=None) == 1


def test_wrong_api_key_is_rejected(service_key_enabled):
    with pytest.raises(HTTPException) as e:
        dependencies.require_search_access(x_api_key="wrong", credentials=None, db=None)
    assert e.value.status_code == 401


def test_api_key_path_never_touches_the_database(service_key_enabled):
    # db=None would raise AttributeError if the key path fell through to the
    # JWT branch. Passing None is the assertion.
    assert dependencies.require_search_access(x_api_key=VALID_KEY, credentials=None, db=None) == 1


def test_feature_is_off_when_unconfigured(monkeypatch):
    # An empty SERVICE_API_KEY must not mean "any key works", and must not
    # mean "the empty string is a valid key". Existing deploys set nothing.
    monkeypatch.setattr(settings, "service_api_key", "")
    with pytest.raises(HTTPException) as e:
        dependencies.require_search_access(x_api_key="anything", credentials=None, db=None)
    assert e.value.status_code == 401           # falls through to JWT, which is absent


# --- backward compatibility: the JWT path is unchanged ----------------------

def _admin() -> User:
    u = User(email="a@b.c", org_id=7, role=UserRole.ADMIN, hashed_password="x")
    u.id = 99
    return u


def test_admin_jwt_still_works_with_no_api_key(service_key_enabled, monkeypatch):
    monkeypatch.setattr(dependencies, "get_current_user", lambda c, d: _admin())
    assert dependencies.require_search_access(x_api_key=None, credentials="tok", db=None) == 7


def test_admin_jwt_still_works_when_the_feature_is_disabled(monkeypatch):
    monkeypatch.setattr(settings, "service_api_key", "")
    monkeypatch.setattr(dependencies, "get_current_user", lambda c, d: _admin())
    assert dependencies.require_search_access(x_api_key=None, credentials="tok", db=None) == 7


def test_non_admin_jwt_is_still_forbidden(service_key_enabled, monkeypatch):
    student = User(email="s@b.c", org_id=7, role=UserRole.STUDENT, hashed_password="x")
    student.id = 1
    monkeypatch.setattr(dependencies, "get_current_user", lambda c, d: student)
    with pytest.raises(HTTPException) as e:
        dependencies.require_search_access(x_api_key=None, credentials="tok", db=None)
    assert e.value.status_code == 403


# --- the guarantees tests/test_security.py asserts at the route level -------
#
# Mirrored here because test_security.py transitively imports PaddleOCR (cv2),
# which is not installed in this lightweight test environment. These are the
# same two invariants, checked one layer down, so the change is not merely
# ASSUMED to preserve them.


def test_anonymous_is_still_rejected(service_key_enabled):
    # test_knowledge_base_routes_reject_anonymous: /search must never be open.
    # No API key and no bearer token must still 401 with the feature enabled.
    with pytest.raises(HTTPException) as e:
        dependencies.require_search_access(x_api_key=None, credentials=None, db=None)
    assert e.value.status_code == 401


def test_missing_credentials_return_401_not_403(service_key_enabled):
    # test_protected_route_returns_401_not_403: "not authenticated" and
    # "authenticated but forbidden" must stay distinguishable.
    with pytest.raises(HTTPException) as e:
        dependencies.require_search_access(x_api_key=None, credentials=None, db=None)
    assert e.value.status_code == 401
    assert e.value.detail == "Not authenticated"


# --- rate limiting ----------------------------------------------------------

def test_valid_service_key_gets_its_own_rate_bucket(service_key_enabled):
    key = rate_limit_key(FakeRequest({"X-API-Key": VALID_KEY}))
    assert key.startswith("service:")
    # The raw credential must not appear in the bucket id — it lands in
    # slowapi's store and in anything that logs it.
    assert VALID_KEY not in key


def test_invalid_api_key_cannot_mint_a_rate_limit_bucket(service_key_enabled, monkeypatch):
    """REGRESSION: rate-limit bypass via a client-controlled bucket key.

    rate_limit_key is slowapi's key_func — it runs BEFORE any endpoint
    dependency, on every rate-limited route, including /auth/login (5/min) and
    /chat (120/min), neither of which authenticates.

    An earlier version bucketed on the header's mere presence, so an attacker
    sending a fresh random X-API-Key per request would get a fresh bucket every
    time: unlimited password attempts on /auth/login and unmetered LLM spend on
    /chat. A wrong key must fall through to the IP bucket.
    """
    monkeypatch.setattr("app.core.rate_limit.get_remote_address", lambda r: "9.9.9.9")

    # Every attacker-chosen key must land in the SAME (IP) bucket.
    for attempt in ("random-1", "random-2", "", "  ", VALID_KEY + "x"):
        assert rate_limit_key(FakeRequest({"X-API-Key": attempt})) == "9.9.9.9"


def test_api_key_bucket_is_disabled_when_the_feature_is_off(monkeypatch):
    # With SERVICE_API_KEY unset, no header value may create a service bucket —
    # otherwise the empty-string comparison would match an empty header.
    monkeypatch.setattr(settings, "service_api_key", "")
    monkeypatch.setattr("app.core.rate_limit.get_remote_address", lambda r: "9.9.9.9")
    assert rate_limit_key(FakeRequest({"X-API-Key": ""})) == "9.9.9.9"
    assert rate_limit_key(FakeRequest({"X-API-Key": "anything"})) == "9.9.9.9"


def test_requests_without_an_api_key_are_keyed_as_before(monkeypatch):
    monkeypatch.setattr("app.core.rate_limit.get_remote_address", lambda r: "1.2.3.4")
    assert rate_limit_key(FakeRequest({})) == "1.2.3.4"


def test_jwt_bucketing_is_unchanged_by_the_api_key_path(service_key_enabled, monkeypatch):
    from app.core.security import create_access_token

    monkeypatch.setattr("app.core.rate_limit.get_remote_address", lambda r: "1.2.3.4")
    token = create_access_token(user_id=42, org_id=1, role="admin")
    assert rate_limit_key(FakeRequest({"Authorization": f"Bearer {token}"})) == "user:42"
