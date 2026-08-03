from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class EvalTrace(Base):
    """One row per answered question: what was asked, what retrieval returned,
    what the model said, and how long it took.

    INFRASTRUCTURE ONLY -- deliberately no recall/precision/groundedness/
    hallucination columns. Every one of those requires a labelled ground
    truth this project does not have yet (P1-7: no golden set exists), and a
    column named `recall` holding a number nothing computed would be worse
    than no column at all -- it would look like the metric exists.

    What this table IS for: the durable substrate those metrics need. Once a
    golden set exists, scoring is a batch job that reads these rows and
    writes results elsewhere -- it does not need this schema to change, which
    is the point of storing raw retrieval output rather than a verdict.

    Also the practical answer to "seed a golden set from what?" -- real user
    questions live here, which is the only realistic source of one
    (ENGINEERING_ROADMAP P1-4's second-order cost).
    """

    __tablename__ = "eval_traces"

    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    # Joins to the rag_answer log line and the usage_logs row for the same
    # request -- the three together are the full picture of one answer.
    request_id = Column(String, nullable=True, index=True)

    question = Column(Text, nullable=False)
    # Not the same as `question` when history was folded in (rag_service's
    # _retrieve) -- the query that ACTUALLY hit retrieval is what a retrieval
    # metric has to be scored against.
    retrieval_query = Column(Text, nullable=False)

    # Comma-separated chunk ids and their scores, parallel-ordered. Text, not
    # a relation: these are an immutable snapshot of what retrieval returned
    # at answer time, and a chunk deleted by a later re-index must not change
    # or break a historical trace (a FK would cascade or block).
    retrieved_chunk_ids = Column(Text, nullable=False, default="")
    retrieved_scores = Column(Text, nullable=False, default="")

    answer = Column(Text, nullable=False)
    # Which of the retrieved chunks the answer actually cited, post-renumber.
    cited_chunk_ids = Column(Text, nullable=False, default="")

    refused = Column(Boolean, nullable=False, default=False)
    best_semantic_score = Column(Float, nullable=True)
    prompt_version = Column(String, nullable=True)
    llm_model = Column(String, nullable=True)
    embedding_model = Column(String, nullable=True)
    retrieval_ms = Column(Integer, nullable=True)
    llm_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
