from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.models.user import User
from app.repositories.document_repository import DocumentRepository
from app.schemas.answer import AnswerResponse, AskRequest, Citation
from app.services.rag_service import answer_question

router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("", response_model=AnswerResponse)
@limiter.limit("20/minute")
def ask(
    request: Request,
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = answer_question(current_user.org_id, payload.question, payload.top_k)

    doc_repo = DocumentRepository(db, current_user.org_id)
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
    return AnswerResponse(answer=result["answer"], citations=citations)
