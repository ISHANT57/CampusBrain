from typing import Literal

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    mode: Literal["semantic", "keyword", "hybrid"] = "hybrid"


class SearchHit(BaseModel):
    score: float
    chunk_id: int
    document_id: int
    page_number: int
    text: str


class SearchResponse(BaseModel):
    hits: list[SearchHit]
