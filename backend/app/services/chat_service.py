from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.message import Message, MessageRole
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.services.rag_service import answer_question

# How many prior turns to feed back as context. Keeps the prompt bounded —
# whole conversations would eventually overflow the model's context window.
HISTORY_TURN_LIMIT = 6


class ConversationNotFoundError(Exception):
    pass


def handle_chat(
    db: Session, *, org_id: int, user_id: int, question: str, conversation_id: int | None, top_k: int = 5
) -> dict:
    conv_repo = ConversationRepository(db, org_id)
    msg_repo = MessageRepository(db, org_id)

    if conversation_id is None:
        conversation = Conversation(org_id=org_id, user_id=user_id, title=question[:80])
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    else:
        # get_for_user, not get: a client-supplied conversation_id must belong
        # to this user, not just this org.
        conversation = conv_repo.get_for_user(conversation_id, user_id)
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)

    history = [
        {"role": m.role.value, "content": m.content}
        for m in msg_repo.list_for_conversation(conversation.id, limit=HISTORY_TURN_LIMIT)
    ]

    db.add(Message(conversation_id=conversation.id, org_id=org_id, role=MessageRole.USER, content=question))
    db.commit()

    result = answer_question(org_id, question, top_k=top_k, history=history or None)

    db.add(
        Message(
            conversation_id=conversation.id,
            org_id=org_id,
            role=MessageRole.ASSISTANT,
            content=result["answer"],
        )
    )
    db.commit()

    return {
        "conversation_id": conversation.id,
        "answer": result["answer"],
        "citations": result["citations"],
    }
