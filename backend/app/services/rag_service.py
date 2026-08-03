import logging
import re
import time
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.core import metrics
from app.core.config import settings
from app.core.observability import request_id_var
from app.infrastructure.llm.provider import get_llm_provider
from app.infrastructure.usage import TokenUsage
from app.services import eval_service, usage_service
from app.services.guardrails import sanitize_context
from app.services.prompt_templates import NO_EVIDENCE_RESPONSE, PROMPT_VERSION, build_rag_prompt
from app.services.retrieval_service import hybrid_search

logger = logging.getLogger("rag")

# Below this top-hit *semantic* similarity, we treat the question as
# out-of-corpus and refuse rather than let the model answer ungrounded (M39).
RELEVANCE_THRESHOLD = 0.35

# Matches a single marker "[3]" and a grouped one "[1, 2, 4]" alike. Models
# group markers whenever a claim rests on several chunks, and matching only
# the single form meant those answers surfaced NO sources at all — the sources
# panel was empty under exactly the best-evidenced answers.
CITATION_MARKER = re.compile(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]")


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
    dropped entirely rather than left dangling. A grouped marker keeps only its
    in-range numbers — "[2, 9]" becomes "[1]", not a dangling reference and not
    a lost one.
    """

    def numbers(match: re.Match) -> list[int]:
        return [int(n) for n in match.group(1).split(",")]

    seen: list[int] = []
    for match in CITATION_MARKER.finditer(answer):
        for n in numbers(match):
            if 1 <= n <= len(hits) and n not in seen:
                seen.append(n)

    if not seen:
        # Strip any markers that survived — all of them are out of range, so
        # leaving them would show the user a reference to nothing.
        return CITATION_MARKER.sub("", answer).strip(), []

    seen.sort()
    renumber = {old: new for new, old in enumerate(seen, start=1)}

    def rewrite(match: re.Match) -> str:
        kept = [renumber[n] for n in numbers(match) if n in renumber]
        return f"[{', '.join(str(n) for n in kept)}]" if kept else ""

    rewritten = CITATION_MARKER.sub(rewrite, answer)

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


def _log_answer(
    org_id: int, question: str, history: list[dict] | None, hits: list[dict],
    best_semantic: float, refused: bool, citations: list[dict],
    retrieval_ms: float, llm_ms: float, ttft_ms: float | None = None,
    usage: TokenUsage | None = None,
    retrieval_query: str | None = None, answer_text: str = "",
) -> None:
    # keyword_hits: chunks that reached the fused result with no semantic
    # contribution at all -- the early-warning signal for the keyword arm
    # dying silently behind a semantic arm that keeps covering for it
    # (INC-001, months undetected before this field existed).
    keyword_hits = sum(1 for h in hits if h.get("semantic_score", 0.0) == 0.0)

    metrics.incr("rag.answers")
    if refused:
        metrics.incr("rag.refused")
    if keyword_hits == 0:
        metrics.incr("rag.zero_keyword")
    metrics.incr("rag.citations", len(citations))
    metrics.observe("retrieval", retrieval_ms)
    metrics.observe("llm", llm_ms)
    if ttft_ms is not None:
        metrics.observe("llm_ttft", ttft_ms)

    logger.info("answered", extra={"event": {
        "event": "rag_answer",
        "org_id": org_id,
        "question": question,
        "question_len": len(question),
        "history_turns": len(history or []),
        "retrieved_chunk_ids": [h["chunk_id"] for h in hits],
        "n_hits": len(hits),
        "best_semantic_score": round(best_semantic, 4),
        "keyword_hits": keyword_hits,
        "refused": refused,
        "citation_count": len(citations),
        "relevance_threshold": RELEVANCE_THRESHOLD,
        "prompt_version": PROMPT_VERSION,
        "llm_model": settings.gemini_llm_model,
        "embedding_model": settings.embedding_model,
        "retrieval_ms": round(retrieval_ms),
        "llm_ms": round(llm_ms),
        "ttft_ms": round(ttft_ms) if ttft_ms is not None else None,
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": usage.completion_tokens if usage else None,
        "total_tokens": usage.total_tokens if usage else None,
    }})

    # Chat is anonymous (ADR-008) -- no user_id to attribute this to.
    # request_id ties this row back to the exact log line above.
    if usage is not None:
        usage_service.record(
            org_id=org_id,
            operation="chat.generate",
            model=settings.gemini_llm_model,
            usage=usage,
            request_id=request_id_var.get(),
            latency_ms=round(llm_ms),
        )

    # Phase 4: the durable substrate a future evaluation harness scores
    # against. Recorded for refusals too -- a refusal IS a result, and
    # refusal rate is one of the few signals measurable without labels.
    eval_service.record_trace(
        org_id=org_id,
        question=question,
        retrieval_query=retrieval_query or question,
        hits=hits,
        answer=answer_text,
        citations=citations,
        refused=refused,
        best_semantic_score=round(best_semantic, 4),
        prompt_version=PROMPT_VERSION,
        llm_model=settings.gemini_llm_model,
        embedding_model=settings.embedding_model,
        retrieval_ms=round(retrieval_ms),
        llm_ms=round(llm_ms),
        request_id=request_id_var.get(),
    )


def _retrieve(
    db: Session, org_id: int, question: str, top_k: int, history: list[dict] | None,
) -> tuple[list[dict], float, bool, float, str]:
    """Shared by answer_question and stream_answer: retrieval and the
    no-evidence guardrail are identical either way -- only what happens with
    the LLM afterwards (block vs. stream) differs.

    Also returns the retrieval_query it built: that's what actually hit
    retrieval, and it differs from `question` whenever history was folded in
    -- an eval trace scored against the wrong one would be measuring
    something that never ran."""
    # A follow-up like "what about semester 5?" has no retrievable content on
    # its own, so fold recent user turns into the retrieval query. Cheaper than
    # a dedicated LLM condensation call, and good enough for short follow-ups.
    # ponytail: naive concatenation, swap for query rewriting if follow-ups
    # start retrieving the wrong chunks.
    retrieval_query = question
    if history:
        prior_user_turns = " ".join(m["content"] for m in history if m["role"] == "user")
        retrieval_query = f"{prior_user_turns} {question}".strip()

    t0 = time.perf_counter()
    hits = hybrid_search(db, org_id, retrieval_query, top_k)
    retrieval_ms = (time.perf_counter() - t0) * 1000

    # No-evidence guardrail. Checks the best *semantic* score across the fused
    # results (not the RRF score, which is on a different scale): a keyword-only
    # match on a common word is not evidence that the corpus answers this.
    best_semantic = max((h.get("semantic_score", 0.0) for h in hits), default=0.0)
    refused = not hits or best_semantic < RELEVANCE_THRESHOLD
    return hits, best_semantic, refused, retrieval_ms, retrieval_query


def answer_question(
    db: Session, org_id: int, question: str, top_k: int = 5, history: list[dict] | None = None
) -> dict:
    hits, best_semantic, refused, retrieval_ms, retrieval_query = _retrieve(db, org_id, question, top_k, history)
    if refused:
        _log_answer(org_id, question, history, hits, best_semantic, True, [], retrieval_ms, 0.0,
                    retrieval_query=retrieval_query, answer_text=NO_EVIDENCE_RESPONSE)
        return {"answer": NO_EVIDENCE_RESPONSE, "citations": []}

    # Sanitize retrieved text before it ever enters the prompt (M40).
    sanitized_hits = [{**hit, "text": sanitize_context(hit["text"])} for hit in hits]

    prompt = build_rag_prompt(question, sanitized_hits, history=history)
    t1 = time.perf_counter()
    result = get_llm_provider().generate(prompt)
    llm_ms = (time.perf_counter() - t1) * 1000

    # Only surface the sources the answer actually cites. Passing the
    # retrieval threshold means the corpus looked relevant; it does not mean
    # the model found an answer in every chunk, and it may still have declined
    # to answer at all.
    answer, citations = keep_cited_sources(result.text, sanitized_hits)
    _log_answer(org_id, question, history, hits, best_semantic, False, citations, retrieval_ms, llm_ms,
                usage=result.usage, retrieval_query=retrieval_query, answer_text=answer)
    return {"answer": answer, "citations": citations}


def stream_answer(
    db: Session, org_id: int, question: str, top_k: int = 5, history: list[dict] | None = None
) -> Iterator[dict]:
    """Same retrieval, guardrail and citation logic as answer_question, but
    yields the answer as it's generated instead of blocking for the whole
    thing.

    keep_cited_sources needs the COMPLETE answer text to know which markers
    survived and how to renumber them contiguously -- that's inherently a
    whole-text operation, not something a token stream can do incrementally.
    So the contract is: every event up to the last is
    {"type": "delta", "text": ...}, carrying the model's raw, un-renumbered
    output, for a live "typing" UI. The FINAL event is
    {"type": "done", "answer": ..., "citations": [...]}, carrying the exact
    same renumbered text and citation list answer_question would have
    returned in one shot. A client that ignores every delta and reads only
    the final "done" event gets an identical result to the non-streaming
    endpoint -- streaming changes the transport, not the contract.
    """
    hits, best_semantic, refused, retrieval_ms, retrieval_query = _retrieve(db, org_id, question, top_k, history)
    if refused:
        yield {"type": "delta", "text": NO_EVIDENCE_RESPONSE}
        yield {"type": "done", "answer": NO_EVIDENCE_RESPONSE, "citations": []}
        _log_answer(org_id, question, history, hits, best_semantic, True, [], retrieval_ms, 0.0,
                    retrieval_query=retrieval_query, answer_text=NO_EVIDENCE_RESPONSE)
        return

    sanitized_hits = [{**hit, "text": sanitize_context(hit["text"])} for hit in hits]
    prompt = build_rag_prompt(question, sanitized_hits, history=history)

    t1 = time.perf_counter()
    ttft_ms: float | None = None
    chunks: list[str] = []
    usage: TokenUsage | None = None
    try:
        for chunk in get_llm_provider().generate_stream(prompt):
            if chunk.usage is not None:
                usage = chunk.usage  # the final sentinel chunk; carries no text
            if not chunk.text:
                continue
            if ttft_ms is None:
                ttft_ms = (time.perf_counter() - t1) * 1000
            chunks.append(chunk.text)
            yield {"type": "delta", "text": chunk.text}
        llm_ms = (time.perf_counter() - t1) * 1000
        answer, citations = keep_cited_sources("".join(chunks), sanitized_hits)
        yield {"type": "done", "answer": answer, "citations": citations}
        _log_answer(org_id, question, history, hits, best_semantic, False, citations, retrieval_ms, llm_ms, ttft_ms,
                    usage, retrieval_query=retrieval_query, answer_text=answer)
    except GeneratorExit:
        # The client disconnected mid-stream (closed tab, StreamingResponse
        # torn down early) -- without this, an abandoned answer just vanishes
        # from the record instead of showing up as a partial one. Must not
        # yield again after catching this; log, then propagate the close.
        llm_ms = (time.perf_counter() - t1) * 1000
        partial, citations = keep_cited_sources("".join(chunks), sanitized_hits)
        _log_answer(org_id, question, history, hits, best_semantic, False, citations, retrieval_ms, llm_ms, ttft_ms,
                    usage, retrieval_query=retrieval_query, answer_text=partial)
        raise
