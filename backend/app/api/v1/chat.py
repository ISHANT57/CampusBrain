# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Request
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.repositories.document_repository import DocumentRepository
from app.schemas.answer import Citation
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag_service import answer_question

router = APIRouter(prefix="/chat", tags=["chat"])

# Students use the chatbot without an account, so there is no token to read an
# org from and this deploy serves exactly one institution. Every public answer
# is retrieved from org 1's documents — the row migration b3e1f0a72c44 seeds.
# If this ever serves multiple institutions, that's the moment to resolve the
# org from the request's hostname instead of pinning it here.
PUBLIC_ORG_ID = 1


@router.post("", response_model=ChatResponse)
# Anonymous callers have no user id, so rate_limit_key falls back to client IP
# — and a whole campus behind one NAT is a single IP. 20/minute (the old
# per-user limit) would have meant 20 questions per minute for the entire
# college, so this is deliberately loose: it exists to cap a runaway script,
# not to ration students.
# ponytail: per-IP ceiling. If abuse gets real, the next rung is a signed
# per-browser session token issued on first load, keyed the same way.
@limiter.limit("120/minute")
def chat(request: Request, payload: ChatRequest, db: Session = Depends(get_db)):
    history = [turn.model_dump() for turn in payload.history]
    result = answer_question(
        db, PUBLIC_ORG_ID, payload.question, top_k=payload.top_k, history=history or None
    )

    doc_repo = DocumentRepository(db, PUBLIC_ORG_ID)
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
