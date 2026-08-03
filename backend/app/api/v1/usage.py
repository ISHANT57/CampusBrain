# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Query
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.services import usage_service

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/summary")
def usage_summary(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """Total tokens, estimated cost, a daily series, and top spenders --
    scoped to the caller's own org. Admin-only: spend and per-user/per-
    document breakdowns are operational detail, not something to expose
    publicly, same reasoning as /metrics.
    """
    return usage_service.summary(db, current_user.org_id, days=days)
