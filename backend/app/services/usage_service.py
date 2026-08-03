"""Token-usage ledger and the read-side aggregations the admin dashboard
needs. Fail-open by design, like the cache and unlike the audit log: a
usage-tracking write must never break the chat response or the ingestion job
it's describing. record() opens its own short-lived session, completely
isolated from whatever session the caller is using -- there is nothing here
worth risking a real user-facing failure over.
"""

import logging

from sqlalchemy import func, text as sql_text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.infrastructure.usage import TokenUsage
from app.models.document import Document
from app.models.usage_log import UsageLog
from app.models.user import User

logger = logging.getLogger("usage")

# $ per 1M tokens, (prompt_rate, completion_rate). Every model in active use
# here runs on Gemini's FREE tier (ADR-003), so the honest cost today is
# $0 -- these are placeholders for the day that changes, not a claim about
# current spend. Verify against https://ai.google.dev/pricing before
# trusting a number this produces for a paid tier; an unlisted model prices
# at $0 rather than a guessed rate.
PRICING_USD_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {}


def _estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prompt_rate, completion_rate = PRICING_USD_PER_MILLION_TOKENS.get(model, (0.0, 0.0))
    return (prompt_tokens * prompt_rate + completion_tokens * completion_rate) / 1_000_000


def record(
    *,
    org_id: int,
    operation: str,
    model: str,
    usage: TokenUsage,
    user_id: int | None = None,
    document_id: int | None = None,
    request_id: str | None = None,
    latency_ms: int | None = None,
) -> None:
    try:
        db = SessionLocal()
        try:
            db.add(UsageLog(
                org_id=org_id,
                user_id=user_id,
                document_id=document_id,
                request_id=request_id,
                operation=operation,
                model=model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                latency_ms=latency_ms,
            ))
            db.commit()
        finally:
            db.close()
    except Exception:
        # Never propagate: losing one usage row is a rounding error on a
        # dashboard. Failing the chat answer or the ingestion job over it
        # would not be.
        logger.exception("usage log write failed", extra={"event": {
            "event": "usage_log_write_failed", "org_id": org_id, "operation": operation,
        }})


def summary(db: Session, org_id: int, *, days: int = 30) -> dict:
    """Everything the Phase 3 admin dashboard asks for, in one query set:
    totals, a daily series, top spenders, top documents. All scoped to one
    org -- this is a tenant's own spend, never visible across the boundary.
    """
    window = func.now() - sql_text(f"interval '{days} days'")

    totals = db.query(
        func.coalesce(func.sum(UsageLog.total_tokens), 0),
        func.coalesce(func.sum(UsageLog.prompt_tokens), 0),
        func.coalesce(func.sum(UsageLog.completion_tokens), 0),
    ).filter(UsageLog.org_id == org_id, UsageLog.created_at >= window).one()
    total_tokens, prompt_tokens, completion_tokens = totals

    by_model = db.query(UsageLog.model, func.sum(UsageLog.prompt_tokens), func.sum(UsageLog.completion_tokens)).filter(
        UsageLog.org_id == org_id, UsageLog.created_at >= window,
    ).group_by(UsageLog.model).all()
    estimated_cost_usd = sum(_estimate_cost_usd(m, p or 0, c or 0) for m, p, c in by_model)

    daily = db.query(
        func.date_trunc("day", UsageLog.created_at).label("day"),
        func.sum(UsageLog.total_tokens),
    ).filter(
        UsageLog.org_id == org_id, UsageLog.created_at >= window,
    ).group_by("day").order_by("day").all()

    top_users = db.query(
        User.email, func.sum(UsageLog.total_tokens).label("tokens"),
    ).join(User, User.id == UsageLog.user_id).filter(
        UsageLog.org_id == org_id, UsageLog.created_at >= window,
    ).group_by(User.email).order_by(func.sum(UsageLog.total_tokens).desc()).limit(10).all()

    top_documents = db.query(
        Document.filename, func.sum(UsageLog.total_tokens).label("tokens"),
    ).join(Document, Document.id == UsageLog.document_id).filter(
        UsageLog.org_id == org_id, UsageLog.created_at >= window,
    ).group_by(Document.filename).order_by(func.sum(UsageLog.total_tokens).desc()).limit(10).all()

    return {
        "window_days": days,
        "total_tokens": int(total_tokens),
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "estimated_cost_usd": round(estimated_cost_usd, 6),
        "daily_tokens": [{"date": day.date().isoformat(), "tokens": int(tokens)} for day, tokens in daily],
        "top_users": [{"email": email, "tokens": int(tokens)} for email, tokens in top_users],
        "top_documents": [{"filename": name, "tokens": int(tokens)} for name, tokens in top_documents],
    }
