# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Request
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_search_access
from app.core.rate_limit import limiter
from app.schemas.search import SearchRequest, SearchResponse
from app.services.retrieval_service import hybrid_search, keyword_search, semantic_search

router = APIRouter(prefix="/search", tags=["search"])


# Returns raw document chunks — a knowledge-base inspection tool, not something
# students need (they get grounded answers through /chat). Two callers are
# permitted, both privileged:
#
#   admin JWT   a human inspecting the corpus through the admin UI
#   X-API-Key   a machine doing read-only retrieval (the agent runtime)
#
# The API-key path is off unless SERVICE_API_KEY is set, and it is wired to
# this endpoint ONLY — a service key cannot upload documents or read /auth.
#
# Both callers already need credentials, so this rate limit is defense in
# depth, not the primary control: a leaked admin token or service key could
# otherwise be used as a free embedding-cost amplifier (P2-14) with no other
# limit in front of it.
@router.post("", response_model=SearchResponse)
@limiter.limit("60/minute")
def search(
    request: Request,
    payload: SearchRequest,
    org_id: int = Depends(require_search_access),
    db: Session = Depends(get_db),
):
    # org_id still comes from the credential, never the request body — a
    # caller can only ever search the organization its credential resolves to.
    if payload.mode == "semantic":
        hits = semantic_search(org_id, payload.query, payload.top_k)
    elif payload.mode == "keyword":
        hits = keyword_search(db, org_id, payload.query, payload.top_k)
    else:
        hits = hybrid_search(db, org_id, payload.query, payload.top_k)
    return SearchResponse(hits=hits)
