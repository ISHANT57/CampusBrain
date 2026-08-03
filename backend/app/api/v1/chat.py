import json

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, Request, status
# pyrefly: ignore [missing-import]
from fastapi.responses import StreamingResponse
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.organization import Organization
from app.repositories.document_repository import DocumentRepository
from app.schemas.answer import AnswerGrounding, Citation
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag_service import answer_question, stream_answer

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


def _filename(doc_repo: DocumentRepository, document_id: int) -> str:
    """Bare document_id -> display filename, scoped to the caller's org.

    Kept in the API layer, not rag_service: retrieval and citation logic deal
    in ids, and this is the one place a display string is resolved -- shared by
    the blocking response, the SSE citations, and the SSE retrieved event.
    """
    document = doc_repo.get(document_id)
    return document.filename if document else "(unknown)"


def _hydrate_citation(doc_repo: DocumentRepository, c: dict) -> dict:
    return {
        "index": c["index"],
        "document_id": c["document_id"],
        "filename": _filename(doc_repo, c["document_id"]),
        "page_number": c["page_number"],
        "excerpt": c["excerpt"],
    }


def _hydrate_retrieved(doc_repo: DocumentRepository, d: dict) -> dict:
    return {
        "document_id": d["document_id"],
        "filename": _filename(doc_repo, d["document_id"]),
        "pages": d["pages"],
        "chunks": d["chunks"],
    }


def _answer(db: Session, org_id: int, payload: ChatRequest) -> ChatResponse:
    history = [turn.model_dump() for turn in payload.history]
    result = answer_question(
        db, org_id, payload.question, top_k=payload.top_k, history=history or None
    )
    doc_repo = DocumentRepository(db, org_id)
    citations = [Citation(**_hydrate_citation(doc_repo, c)) for c in result["citations"]]
    return ChatResponse(
        answer=result["answer"],
        citations=citations,
        grounding=AnswerGrounding(**result["grounding"]) if result.get("grounding") else None,
    )


def _stream_events(db: Session, org_id: int, payload: ChatRequest):
    """SSE body for /chat/stream[/{org_slug}]. Same request contract as the
    blocking endpoint, different transport: one "data: {json}\\n\\n" line per
    event -- an optional leading {"type": "retrieved", "documents": [...]} once
    retrieval has run, then {"type": "delta", "text": ...} while the answer is
    generating, then exactly one {"type": "done", "answer": ...,
    "citations": [...], "grounding": {...}} carrying the final renumbered text,
    hydrated citations and the measured basis for the answer. See
    rag_service.stream_answer's docstring for why renumbering can't be done
    incrementally, chunk by chunk.
    """
    history = [turn.model_dump() for turn in payload.history]
    doc_repo = DocumentRepository(db, org_id)
    for event in stream_answer(
        db, org_id, payload.question, top_k=payload.top_k, history=history or None
    ):
        if event["type"] == "done":
            event = {**event, "citations": [_hydrate_citation(doc_repo, c) for c in event["citations"]]}
        elif event["type"] == "retrieved":
            event = {**event, "documents": [_hydrate_retrieved(doc_repo, d) for d in event["documents"]]}
        yield f"data: {json.dumps(event)}\n\n"


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


# Registered BEFORE /{org_slug}: that route is a single-segment catch-all, so
# without this ordering "/chat/stream" would itself match org_slug="stream"
# instead of ever reaching this route -- FastAPI matches in registration
# order, and both patterns fit that URL. (An org literally named "stream"
# would still be shadowed by this route; an accepted, narrow edge case, the
# same shape as DEFAULT_ORG_SLUG's.)
@router.post("/stream")
@limiter.limit("120/minute")
def chat_stream(request: Request, payload: ChatRequest, db: Session = Depends(get_db)):
    org_id = _org_id(db, DEFAULT_ORG_SLUG)  # resolved eagerly, so an unknown org still 404s immediately
    return StreamingResponse(_stream_events(db, org_id, payload), media_type="text/event-stream")


@router.post("/stream/{org_slug}")
@limiter.limit("120/minute")
def chat_stream_for_org(
    request: Request, org_slug: str, payload: ChatRequest, db: Session = Depends(get_db)
):
    org_id = _org_id(db, org_slug)
    return StreamingResponse(_stream_events(db, org_id, payload), media_type="text/event-stream")


@router.post("/{org_slug}", response_model=ChatResponse)
@limiter.limit("120/minute")
def chat_for_org(
    request: Request, org_slug: str, payload: ChatRequest, db: Session = Depends(get_db)
):
    return _answer(db, _org_id(db, org_slug), payload)
