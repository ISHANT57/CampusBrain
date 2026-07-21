# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.search import SearchRequest, SearchResponse
from app.services.retrieval_service import hybrid_search, keyword_search, semantic_search

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search(
    payload: SearchRequest,
    current_user: User = Depends(get_current_user),
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
