import hashlib
import secrets

# pyrefly: ignore [missing-import]
from fastapi import Request
from jose import JWTError
# pyrefly: ignore [missing-import]
from slowapi import Limiter
# pyrefly: ignore [missing-import]
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.security import decode_access_token


def rate_limit_key(request: Request) -> str:
    # Per-user when authenticated (so one user's abuse can't lock out others),
    # falling back to client IP for pre-login endpoints like register/login.

    # A VALID service caller gets its own bucket, keyed by a hash of the key
    # rather than the key itself — this string lands in slowapi's store and in
    # anything that logs it, and a credential does not belong there.
    #
    # The key MUST be verified here, not merely present. This function is
    # slowapi's key_func: it runs before any endpoint dependency, on every
    # rate-limited route — including /auth/login (5/min) and /chat (120/min),
    # neither of which authenticates at all. Bucketing on the header's presence
    # would let anyone send a fresh random X-API-Key per request to mint a new
    # bucket each time, making both limits unenforceable: unlimited password
    # attempts on /auth/login, and unmetered LLM spend on /chat.
    #
    # An absent or wrong key falls through to the IP bucket below, which is the
    # correct default for an unauthenticated caller.
    api_key = request.headers.get("X-API-Key")
    if api_key and settings.service_api_key and secrets.compare_digest(api_key, settings.service_api_key):
        return f"service:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = decode_access_token(auth[7:])
            return f"user:{payload['sub']}"
        except JWTError:
            pass
    return get_remote_address(request)


# No storage_uri: slowapi defaults to in-memory counters. That's correct here
# — every free-tier host in this deploy (Render free web service) only ever
# runs one instance, so there's no second process for counters to be
# inconsistent with. If this ever runs with >1 worker process or instance,
# rate limits become per-process (each one enforces its own count), which
# under-limits in aggregate — that's the point at which a shared store
# (Upstash Redis's free tier, e.g.) earns its keep again.
limiter = Limiter(key_func=rate_limit_key)
