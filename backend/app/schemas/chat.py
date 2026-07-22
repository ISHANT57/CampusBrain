from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.answer import Citation

# How many prior turns to feed back to the model. Keeps the prompt bounded —
# whole conversations would eventually overflow the model's context window.
MAX_HISTORY_TURNS = 12


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    # Students chat anonymously, so the server keeps no transcript — the
    # browser replays the recent turns it already holds in localStorage.
    # That makes this untrusted input landing directly in an LLM prompt:
    # bounded here in both turn count and per-turn size.
    history: list[ChatTurn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS)
    # Bounded because this endpoint is public: top_k drives how many chunks
    # get retrieved and stuffed into the prompt, so an unbounded value is a
    # free way for anyone to run up the LLM bill.
    top_k: int = Field(default=5, ge=1, le=20)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
