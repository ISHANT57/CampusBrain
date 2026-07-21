from app.infrastructure.llm.provider import get_llm_provider
from app.services.guardrails import sanitize_context
from app.services.prompt_templates import NO_EVIDENCE_RESPONSE, build_rag_prompt
from app.services.retrieval_service import semantic_search

# Below this top-hit similarity, we treat the question as out-of-corpus and
# refuse rather than let the model answer ungrounded (M39).
RELEVANCE_THRESHOLD = 0.35


def answer_question(org_id: int, question: str, top_k: int = 5) -> dict:
    hits = semantic_search(org_id, question, top_k)

    # No-evidence guardrail: nothing retrieved, or nothing relevant enough.
    if not hits or hits[0]["score"] < RELEVANCE_THRESHOLD:
        return {"answer": NO_EVIDENCE_RESPONSE, "citations": []}

    # Sanitize retrieved text before it ever enters the prompt (M40).
    sanitized_hits = [{**hit, "text": sanitize_context(hit["text"])} for hit in hits]

    prompt = build_rag_prompt(question, sanitized_hits)
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
