# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, Request, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserRead
from app.services.user_service import authenticate_user

# Staff-only. Students use the chatbot anonymously and never authenticate, so
# there is deliberately no self-registration endpoint — accounts are created
# out-of-band with backend/scripts/create_admin.py.
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, org_id=payload.org_id, email=payload.email, password=payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user_id=user.id, org_id=user.org_id, role=user.role.value)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user
