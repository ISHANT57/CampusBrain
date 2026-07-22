import re

from sqlalchemy.orm import Session

from app.infrastructure.llm.provider import get_llm_provider
from app.services.guardrails import sanitize_context
from app.services.prompt_templates import NO_EVIDENCE_RESPONSE, build_rag_prompt
from app.services.retrieval_service import hybrid_search

# Below this top-hit *semantic* similarity, we treat the question as
# out-of-corpus and refuse rather than let the model answer ungrounded (M39).
RELEVANCE_THRESHOLD = 0.35

CITATION_MARKER = re.compile(r"\[(\d+)\]")


def keep_cited_sources(answer: str, hits: list[dict]) -> tuple[str, list[dict]]:
    """Return the answer with citation markers renumbered, and only the sources
    it actually cites.

    Retrieval always returns top_k chunks, but the model typically grounds its
    answer in a subset — and when it declines to answer, in none of them.
    Returning every retrieved chunk made the UI show a "5 sources" list under
    answers that referenced one of them, or under an outright refusal, which
    overstates how grounded the answer is. Sources should be evidence for what
    was said, not a log of what was searched.

    Markers are renumbered to stay contiguous: if the model cites [2] and [4],
    the user sees sources 1 and 2, not 2 and 4 with gaps that read as missing
    items. A marker pointing outside the retrieved set (a hallucinated [9]) is
    dropped entirely rather than left dangling.
    """
    seen: list[int] = []
    for match in CITATION_MARKER.finditer(answer):
        n = int(match.group(1))
        if 1 <= n <= len(hits) and n not in seen:
            seen.append(n)

    if not seen:
        # Strip any markers that survived — all of them are out of range, so
        # leaving them would show the user a reference to nothing.
        return CITATION_MARKER.sub("", answer).strip(), []

    seen.sort()
    renumber = {old: new for new, old in enumerate(seen, start=1)}
    rewritten = CITATION_MARKER.sub(
        lambda m: f"[{renumber[int(m.group(1))]}]" if int(m.group(1)) in renumber else "",
        answer,
    )

    citations = [
        {
            "index": new,
            "document_id": hits[old - 1]["document_id"],
            "page_number": hits[old - 1]["page_number"],
            "chunk_id": hits[old - 1]["chunk_id"],
            "excerpt": hits[old - 1]["text"][:200],
        }
        for old, new in sorted(renumber.items(), key=lambda kv: kv[1])
    ]
    return rewritten, citations


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

    # Only surface the sources the answer actually cites. Passing the
    # retrieval threshold means the corpus looked relevant; it does not mean
    # the model found an answer in every chunk, and it may still have declined
    # to answer at all.
    answer, citations = keep_cited_sources(answer, sanitized_hits)
    return {"answer": answer, "citations": citations}
