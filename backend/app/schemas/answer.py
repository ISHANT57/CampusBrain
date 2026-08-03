from pydantic import BaseModel


# FROZEN for v1 (M43): the frontend builds against this exact shape. Add fields
# additively if needed; do not rename or remove existing ones.
class Citation(BaseModel):
    index: int  # matches the [n] marker in the answer text
    document_id: int
    filename: str
    page_number: int
    excerpt: str


class RetrievedDocument(BaseModel):
    """A document retrieval surfaced, before the model decided whether to use it.

    Emitted mid-stream so the sources panel can fill as soon as retrieval
    finishes rather than holding a skeleton for the whole generation.

    Deliberately NOT the same type as Citation: retrieval returns top_k chunks
    and the answer typically grounds in a subset, so rendering these as
    "sources" would overstate the evidence behind what was actually said. The
    client must label them as searched, not cited.
    """

    document_id: int
    filename: str
    pages: list[int]
    chunks: int  # how many retrieved chunks came from this document


class AnswerGrounding(BaseModel):
    """What the answer rests on, as measured values rather than as a verdict.

    Every field here was already computed per answer (rag_service._log_answer)
    and written to eval_traces and the structured log line -- it was simply
    discarded from the response. Nothing new is measured; something already
    measured stops being thrown away.

    There is deliberately NO `confidence: high|medium|low` field. Bucketing
    these numbers means inventing cutoffs nothing validated, and a label gets
    quoted downstream as though it were measured -- the same reasoning that
    keeps recall/precision out of eval_service (ADR-016). The client renders
    the numbers with their basis visible, which is a claim this system can
    actually support.
    """

    # Reported together on purpose: 0.71 means nothing without knowing 0.35 is
    # the floor below which the system refuses outright.
    best_semantic_score: float
    relevance_threshold: float

    # Considered vs. actually used. The gap is informative on its own -- an
    # answer citing 2 of 14 retrieved chunks is a different claim from one
    # citing 9 of 14.
    retrieved_chunks: int
    cited_chunks: int
    cited_documents: int

    refused: bool


