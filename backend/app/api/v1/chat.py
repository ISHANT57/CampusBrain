# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, Request, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.organization import Organization
from app.repositories.document_repository import DocumentRepository
from app.schemas.answer import Citation
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag_service import answer_question

router = APIRouter(prefix="/chat", tags=["chat"])

# Which organization the un-suffixed /chat serves. This endpoint used to pin
# org 1 as a constant because the deploy served exactly one institution; the
# slug now resolves through the organizations table instead, so adding a
# tenant is a row and a frontend route, not a code change here.
#
# The bare route is kept because the frontend and the backend deploy
# independently (Vercel and Render): during the gap where a new backend is
# live and the old frontend is still calling POST /chat, this is what keeps
# the original chatbot answering instead of 404ing.
DEFAULT_ORG_SLUG = "sitare"


def _org_id(db: Session, slug: str) -> int:
    """Slug -> org id, 404 on anything unknown.

    The org is chosen by the caller (the URL path the visitor is on), which is
    only acceptable because every corpus reachable here is a public-facing
    knowledge base — this endpoint needs no account precisely because none of
    it is private. It is NOT an authorization boundary: uploads, documents and
    /search all continue to take org_id from a verified JWT, never from a
    path. Anything genuinely confidential must not be a chat corpus.
    """
    org = db.query(Organization).filter(Organization.slug == slug).first()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown organization '{slug}'"
        )
    return org.id


def _answer(db: Session, org_id: int, payload: ChatRequest) -> ChatResponse:
    history = [turn.model_dump() for turn in payload.history]
    result = answer_question(
        db, org_id, payload.question, top_k=payload.top_k, history=history or None
    )

    doc_repo = DocumentRepository(db, org_id)
    citations = []
    for c in result["citations"]:
        document = doc_repo.get(c["document_id"])
        citations.append(
            Citation(
                index=c["index"],
                document_id=c["document_id"],
                filename=document.filename if document else "(unknown)",
                page_number=c["page_number"],
                excerpt=c["excerpt"],
            )
        )
    return ChatResponse(answer=result["answer"], citations=citations)


# Anonymous callers have no user id, so rate_limit_key falls back to client IP
# — and a whole campus behind one NAT is a single IP. 20/minute (the old
# per-user limit) would have meant 20 questions per minute for the entire
# college, so this is deliberately loose: it exists to cap a runaway script,
# not to ration students.
#
# The limit is per IP, NOT per organization: one bucket per visitor covers
# every tenant they can reach, so adding organizations cannot multiply what a
# single abuser is allowed to spend.
# ponytail: per-IP ceiling. If abuse gets real, the next rung is a signed
# per-browser session token issued on first load, keyed the same way.
@router.post("", response_model=ChatResponse)
@limiter.limit("120/minute")
def chat(request: Request, payload: ChatRequest, db: Session = Depends(get_db)):
    return _answer(db, _org_id(db, DEFAULT_ORG_SLUG), payload)


@router.post("/{org_slug}", response_model=ChatResponse)
@limiter.limit("120/minute")
def chat_for_org(
    request: Request, org_slug: str, payload: ChatRequest, db: Session = Depends(get_db)
):
    return _answer(db, _org_id(db, org_slug), payload)
