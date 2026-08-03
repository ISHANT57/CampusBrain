"""usage_service: cost estimation math and the fail-open guarantee on
record(). summary()'s actual queries need real Postgres (joins against
users/documents) and are integration-tier:
    docker compose exec backend python -m pytest tests/test_usage_service.py
"""

from app.infrastructure.usage import TokenUsage
from app.services import usage_service


def test_unlisted_model_prices_at_zero_not_a_guessed_rate():
    assert usage_service._estimate_cost_usd("some-future-model", 1_000_000, 1_000_000) == 0.0


def test_cost_estimate_uses_the_configured_rate(monkeypatch):
    monkeypatch.setitem(usage_service.PRICING_USD_PER_MILLION_TOKENS, "test-model", (1.0, 2.0))
    # 1M prompt tokens @ $1/M + 500k completion tokens @ $2/M = $1 + $1 = $2
    assert usage_service._estimate_cost_usd("test-model", 1_000_000, 500_000) == 2.0


def test_record_never_raises_even_when_the_db_is_unreachable(monkeypatch):
    """The whole point of fail-open: a usage-tracking outage must never
    surface as a broken chat response or a failed ingestion job."""
    def boom():
        raise ConnectionError("db unreachable")
    monkeypatch.setattr(usage_service, "SessionLocal", boom)

    usage_service.record(
        org_id=1, operation="chat.generate", model="gemini-3.5-flash-lite",
        usage=TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )  # must not raise
