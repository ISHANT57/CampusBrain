"""Evaluation trace persistence (Phase 4) -- infrastructure, not metrics.

Fail-open, same contract as usage_service and for the same reason: a trace
that fails to write costs a future evaluation one data point; failing the
chat answer over it costs a user their answer.

There is deliberately NO scoring here. Recall, precision, groundedness and
hallucination rate all require a labelled golden set that does not exist yet
(P1-7), and a function returning a plausible-looking number computed from
nothing would be worse than its absence -- it would get quoted. What this
module does is make those metrics *possible later* by durably recording what
each answer was actually built from.
"""

import logging

from sqlalchemy import func, text as sql_text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.eval_trace import EvalTrace

logger = logging.getLogger("eval")


def _join(values) -> str:
    return ",".join(str(v) for v in values)


def record_trace(
    *,
    org_id: int,
    question: str,
    retrieval_query: str,
    hits: list[dict],
    answer: str,
    citations: list[dict],
    refused: bool,
    best_semantic_score: float | None,
    prompt_version: str | None,
    llm_model: str | None,
    embedding_model: str | None,
    retrieval_ms: int | None,
    llm_ms: int | None,
    request_id: str | None,
) -> None:
    try:
        db = SessionLocal()
        try:
            db.add(EvalTrace(
                org_id=org_id,
                request_id=request_id,
                question=question,
                retrieval_query=retrieval_query,
                retrieved_chunk_ids=_join(h["chunk_id"] for h in hits),
                # semantic_score, not the fused RRF score: the guardrail and
                # any future relevance metric are both calibrated on cosine
                # similarity, and mixing the two scales is exactly the unit
                # error §10 of the roadmap calls out as its best story.
                retrieved_scores=_join(round(h.get("semantic_score", 0.0), 4) for h in hits),
                answer=answer,
                cited_chunk_ids=_join(c["chunk_id"] for c in citations),
                refused=refused,
                best_semantic_score=best_semantic_score,
                prompt_version=prompt_version,
                llm_model=llm_model,
                embedding_model=embedding_model,
                retrieval_ms=retrieval_ms,
                llm_ms=llm_ms,
            ))
            db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("eval trace write failed", extra={"event": {
            "event": "eval_trace_write_failed", "org_id": org_id,
        }})


def trace_stats(db: Session, org_id: int, *, days: int = 30) -> dict:
    """Label-free aggregates only -- every number here is derivable from what
    the system itself recorded, with no ground truth required.

    Refusal rate and zero-citation rate are the two proxy signals that
    actually detect retrieval degradation without labels (PILLAR_02's
    argument); they are reported as what they are, not dressed up as recall.
    """
    window = func.now() - sql_text(f"interval '{days} days'")

    base = db.query(EvalTrace).filter(EvalTrace.org_id == org_id, EvalTrace.created_at >= window)
    total = base.count()
    if total == 0:
        return {"window_days": days, "total_traces": 0, "note": "no traces recorded in this window"}

    refused = base.filter(EvalTrace.refused.is_(True)).count()
    uncited = base.filter(EvalTrace.refused.is_(False), EvalTrace.cited_chunk_ids == "").count()
    avg_best = db.query(func.avg(EvalTrace.best_semantic_score)).filter(
        EvalTrace.org_id == org_id, EvalTrace.created_at >= window, EvalTrace.best_semantic_score.isnot(None),
    ).scalar()

    return {
        "window_days": days,
        "total_traces": total,
        "refusal_rate": round(refused / total, 3),
        # An answer that cited nothing while claiming to have evidence is the
        # cheapest available hallucination *smell* -- explicitly not a
        # hallucination RATE, which needs a human or a judge model to call.
        "uncited_answer_rate": round(uncited / total, 3),
        "avg_best_semantic_score": round(float(avg_best), 4) if avg_best is not None else None,
        "scored_metrics_available": False,
        "note": (
            "Label-free signals only. Recall/precision/groundedness require a golden set "
            "(P1-7), which does not exist yet; these traces are the substrate for scoring "
            "them later, not a substitute."
        ),
    }
