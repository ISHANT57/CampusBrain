# pyrefly: ignore [missing-import]
from fastapi import Request
from jose import JWTError
# pyrefly: ignore [missing-import]
from slowapi import Limiter
# pyrefly: ignore [missing-import]
from slowapi.util import get_remote_address

from app.core.security import decode_access_token


def rate_limit_key(request: Request) -> str:
    # Per-user when authenticated (so one user's abuse can't lock out others),
    # falling back to client IP for pre-login endpoints like register/login.
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
