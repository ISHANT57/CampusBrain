# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Query
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.services import eval_service

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/stats")
def evaluation_stats(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    """Label-free quality signals over recorded eval traces (Phase 4).

    Reports `scored_metrics_available: false` and says why in `note`:
    recall/precision/groundedness need a golden set that doesn't exist yet
    (P1-7). This endpoint deliberately does not invent them.
    """
    return eval_service.trace_stats(db, current_user.org_id, days=days)
