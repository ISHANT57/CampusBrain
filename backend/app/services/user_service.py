# pyrefly: ignore [missing-import]
from psycopg2.errors import ForeignKeyViolation
# pyrefly: ignore [missing-import]
from sqlalchemy.exc import IntegrityError
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole


class EmailAlreadyExistsError(Exception):
    pass


class UnknownOrganizationError(Exception):
    pass


def register_user(db: Session, *, org_id: int, email: str, password: str, role: UserRole) -> User:
    existing = db.query(User).filter(User.org_id == org_id, User.email == email).first()
    if existing is not None:
        raise EmailAlreadyExistsError(email)

    user = User(org_id=org_id, email=email, hashed_password=hash_password(password), role=role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        # An org_id the user typed that doesn't exist is bad input, not a
        # server fault — without this it escaped as an unhandled 500, which
        # Starlette generates *above* CORSMiddleware, so the response carried
        # no CORS headers and the browser reported it as a CORS failure
        # instead of showing the real error.
        db.rollback()
        if isinstance(exc.orig, ForeignKeyViolation):
            raise UnknownOrganizationError(org_id) from exc
        # uq_user_org_email is the only other constraint on this table — a
        # concurrent registration that slipped in between the check above and
        # this commit.
        raise EmailAlreadyExistsError(email) from exc
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, org_id: int, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.org_id == org_id, User.email == email).first()
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user
