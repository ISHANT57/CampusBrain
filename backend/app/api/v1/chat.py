from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.message_repository import MessageRepository
from app.schemas.answer import Citation
from app.schemas.chat import ChatRequest, ChatResponse, MessageRead
from app.services.chat_service import ConversationNotFoundError, handle_chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
@limiter.limit("20/minute")
def chat(
    request: Request,
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = handle_chat(
            db,
            org_id=current_user.org_id,
            user_id=current_user.id,
            question=payload.question,
            conversation_id=payload.conversation_id,
            top_k=payload.top_k,
        )
    except ConversationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

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
    return ChatResponse(
        conversation_id=result["conversation_id"], answer=result["answer"], citations=citations
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
def get_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = ConversationRepository(db, current_user.org_id).get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return MessageRepository(db, current_user.org_id).list_for_conversation(conversation_id)
