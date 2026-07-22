# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.schemas.search import SearchRequest, SearchResponse
from app.services.retrieval_service import hybrid_search, keyword_search, semantic_search

router = APIRouter(prefix="/search", tags=["search"])


# Admin-only: this returns raw document chunks, which is a knowledge-base
# inspection tool, not something students need — they get grounded answers
# through /chat. Students have no accounts at all, so anything left
# authenticated is admin-only by construction.
@router.post("", response_model=SearchResponse)
def search(
    payload: SearchRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    db: Session = Depends(get_db),
):
    # org_id comes from the token, never the request — a caller can only ever
    # search their own organization's chunks.
    org_id = current_user.org_id
    if payload.mode == "semantic":
        hits = semantic_search(org_id, payload.query, payload.top_k)
    elif payload.mode == "keyword":
        hits = keyword_search(db, org_id, payload.query, payload.top_k)
    else:
        hits = hybrid_search(db, org_id, payload.query, payload.top_k)
    return SearchResponse(hits=hits)
