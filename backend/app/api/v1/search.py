from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.search import SearchRequest, SearchResponse
from app.services.retrieval_service import semantic_search

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search(payload: SearchRequest, current_user: User = Depends(get_current_user)):
    # org_id comes from the token, never the request — a caller can only ever
    # search their own organization's chunks.
    hits = semantic_search(current_user.org_id, payload.query, payload.top_k)
    return SearchResponse(hits=hits)
