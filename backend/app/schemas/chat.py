from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.message import MessageRole
from app.schemas.answer import Citation


class ChatRequest(BaseModel):
    question: str
    conversation_id: int | None = None  # omit to start a new conversation
    top_k: int = 5


class ChatResponse(BaseModel):
    conversation_id: int
    answer: str
    citations: list[Citation]


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MessageRole
    content: str
    created_at: datetime
