from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole


class EmailAlreadyExistsError(Exception):
    pass


def register_user(db: Session, *, org_id: int, email: str, password: str, role: UserRole) -> User:
    existing = db.query(User).filter(User.org_id == org_id, User.email == email).first()
    if existing is not None:
        raise EmailAlreadyExistsError(email)

    user = User(org_id=org_id, email=email, hashed_password=hash_password(password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, org_id: int, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.org_id == org_id, User.email == email).first()
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user
