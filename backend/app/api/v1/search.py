# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Request
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import SearchPrincipal, require_search_access
from app.core.rate_limit import limiter
from app.schemas.search import SearchRequest, SearchResponse
from app.services import audit_service
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
    principal: SearchPrincipal = Depends(require_search_access),
    db: Session = Depends(get_db),
):
    # org_id still comes from the credential, never the request body — a
    # caller can only ever search the organization its credential resolves to.
    org_id = principal.org_id
    if payload.mode == "semantic":
        hits = semantic_search(org_id, payload.query, payload.top_k)
    elif payload.mode == "keyword":
        hits = keyword_search(db, org_id, payload.query, payload.top_k)
    else:
        hits = hybrid_search(db, org_id, payload.query, payload.top_k)

    # Phase 8: who searched the corpus, for what, and how much it returned.
    # user_id is None for a service-key caller -- there's no user row to
    # attribute a machine call to, and that's recorded as-is, not guessed at.
    # Query is truncated, not omitted: the same call this project already
    # made for chat questions (rag_service's rag_answer event) — the highest-
    # value debugging field, worth the bytes.
    audit_service.record(
        db,
        org_id=org_id,
        user_id=principal.user_id,
        action="search.query",
        resource_type="search",
        detail={"mode": payload.mode, "query": payload.query[:200], "hit_count": len(hits)},
    )
    db.commit()

    return SearchResponse(hits=hits)
