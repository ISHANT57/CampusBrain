from sqlalchemy.orm import Session

from app.infrastructure.llm.provider import get_llm_provider
from app.services.guardrails import sanitize_context
from app.services.prompt_templates import NO_EVIDENCE_RESPONSE, build_rag_prompt
from app.services.retrieval_service import hybrid_search

# Below this top-hit *semantic* similarity, we treat the question as
# out-of-corpus and refuse rather than let the model answer ungrounded (M39).
RELEVANCE_THRESHOLD = 0.35


def answer_question(
    db: Session, org_id: int, question: str, top_k: int = 5, history: list[dict] | None = None
) -> dict:
    # A follow-up like "what about semester 5?" has no retrievable content on
    # its own, so fold recent user turns into the retrieval query. Cheaper than
    # a dedicated LLM condensation call, and good enough for short follow-ups.
    # ponytail: naive concatenation, swap for query rewriting if follow-ups
    # start retrieving the wrong chunks.
    retrieval_query = question
    if history:
        prior_user_turns = " ".join(m["content"] for m in history if m["role"] == "user")
        retrieval_query = f"{prior_user_turns} {question}".strip()

    hits = hybrid_search(db, org_id, retrieval_query, top_k)

    # No-evidence guardrail. Checks the best *semantic* score across the fused
    # results (not the RRF score, which is on a different scale): a keyword-only
    # match on a common word is not evidence that the corpus answers this.
    best_semantic = max((h.get("semantic_score", 0.0) for h in hits), default=0.0)
    if not hits or best_semantic < RELEVANCE_THRESHOLD:
        return {"answer": NO_EVIDENCE_RESPONSE, "citations": []}

    # Sanitize retrieved text before it ever enters the prompt (M40).
    sanitized_hits = [{**hit, "text": sanitize_context(hit["text"])} for hit in hits]

    prompt = build_rag_prompt(question, sanitized_hits, history=history)
    answer = get_llm_provider().generate(prompt)

    citations = [
        {
            "index": i,
            "document_id": hit["document_id"],
            "page_number": hit["page_number"],
            "chunk_id": hit["chunk_id"],
            "excerpt": hit["text"][:200],
        }
        for i, hit in enumerate(sanitized_hits, start=1)
    ]
    return {"answer": answer, "citations": citations}
