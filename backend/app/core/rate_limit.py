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
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = decode_access_token(auth[7:])
            return f"user:{payload['sub']}"
        except JWTError:
            pass
    return get_remote_address(request)


limiter = Limiter(
    key_func=rate_limit_key,
    storage_uri=f"redis://{settings.redis_host}:{settings.redis_internal_port}",
)
