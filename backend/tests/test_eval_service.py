"""Phase 4 evaluation infrastructure.

The important assertion in this file is the negative one: trace_stats must
NOT report recall/precision/groundedness/hallucination-rate, because no
golden set exists to compute them from (P1-7). A number that looks like a
metric but was computed from nothing is worse than an absent one -- it gets
quoted.
"""

from app.services import eval_service, rag_service


def test_record_trace_never_raises_when_the_db_is_unreachable(monkeypatch):
    """Fail-open, same contract as usage_service: losing a trace costs a
    future evaluation one data point; failing the chat answer over it costs
    a user their answer."""
    def boom():
        raise ConnectionError("db unreachable")
    monkeypatch.setattr(eval_service, "SessionLocal", boom)

    eval_service.record_trace(
        org_id=1, question="q", retrieval_query="q", hits=[], answer="a", citations=[],
        refused=False, best_semantic_score=0.5, prompt_version="v1", llm_model="m",
        embedding_model="e", retrieval_ms=1, llm_ms=2, request_id="r",
    )  # must not raise


def test_join_serialises_ids_and_scores_in_parallel_order():
    hits = [{"chunk_id": 7, "semantic_score": 0.91}, {"chunk_id": 3, "semantic_score": 0.44}]
    assert eval_service._join(h["chunk_id"] for h in hits) == "7,3"
    assert eval_service._join(round(h["semantic_score"], 4) for h in hits) == "0.91,0.44"


def test_a_trace_is_recorded_even_for_a_refusal(monkeypatch):
    """A refusal IS a result -- refusal rate is one of the few quality
    signals measurable without labels, so dropping refusals would blind the
    one metric this infrastructure can honestly produce."""
    monkeypatch.setattr(rag_service, "hybrid_search", lambda db, org_id, q, k: [])
    monkeypatch.setattr(rag_service.usage_service, "record", lambda **kw: None)

    traces = []
    monkeypatch.setattr(rag_service.eval_service, "record_trace", lambda **kw: traces.append(kw))

    rag_service.answer_question(db=None, org_id=1, question="unanswerable")

    assert len(traces) == 1
    assert traces[0]["refused"] is True
    assert traces[0]["answer"] == rag_service.NO_EVIDENCE_RESPONSE


def test_trace_records_the_retrieval_query_not_just_the_question(monkeypatch):
    """With history folded in, the query that hit retrieval differs from the
    raw question -- scoring a retrieval metric against the wrong one would
    measure something that never ran."""
    monkeypatch.setattr(rag_service, "hybrid_search", lambda db, org_id, q, k: [])
    monkeypatch.setattr(rag_service.usage_service, "record", lambda **kw: None)

    traces = []
    monkeypatch.setattr(rag_service.eval_service, "record_trace", lambda **kw: traces.append(kw))

    rag_service.answer_question(
        db=None, org_id=1, question="what about year 2?",
        history=[{"role": "user", "content": "tell me about the curriculum"}],
    )

    assert traces[0]["question"] == "what about year 2?"
    assert "curriculum" in traces[0]["retrieval_query"]  # history was folded in
    assert traces[0]["retrieval_query"] != traces[0]["question"]


def test_stats_does_not_claim_scored_metrics_it_cannot_compute():
    """Guards the honesty of the endpoint's own output shape."""
    class _EmptyQuery:
        def filter(self, *a, **k):
            return self

        def count(self):
            return 0

        def scalar(self):
            return None

    class _StubDB:
        def query(self, *_a, **_k):
            return _EmptyQuery()

    result = eval_service.trace_stats(_StubDB(), org_id=1, days=30)
    assert result["total_traces"] == 0
    # No fabricated recall/precision/groundedness anywhere in the payload.
    for forbidden in ("recall", "precision", "groundedness", "hallucination_rate"):
        assert forbidden not in result
