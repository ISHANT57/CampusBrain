import secrets

# pyrefly: ignore [missing-import]
from fastapi import Depends, Header, HTTPException, status
# pyrefly: ignore [missing-import]
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        # HTTPBearer's own auto_error raises 403 for a missing header, which
        # conflates "not authenticated" with "authenticated but forbidden".
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_role(*allowed_roles: UserRole):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return dependency


def require_search_access(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> int:
    """Return the org_id permitted to search. Accepts EITHER credential.

    Two callers with genuinely different needs:

      admin JWT  — a human inspecting the knowledge base through the admin UI.
                   Unchanged; this path behaves exactly as it did before.
      X-API-Key  — a machine (currently the agent runtime) doing read-only
                   retrieval. No password to store, no hourly re-login, and
                   crucially NO upload rights: this dependency is wired only to
                   /search, so the key cannot reach POST /documents.

    Returns an int rather than a User because that is all the endpoint ever
    used (`current_user.org_id`), and a service key has no user to return.

    Order matters: the API key is checked first so a machine caller never
    touches the users table.
    """
    if x_api_key and settings.service_api_key:
        # Constant-time. A plain `==` leaks key material through timing —
        # comparison stops at the first differing byte, so response latency
        # correlates with how many leading characters are correct.
        if secrets.compare_digest(x_api_key, settings.service_api_key):
            return settings.service_api_key_org_id
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    user = get_current_user(credentials, db)
    if user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return user.org_id
