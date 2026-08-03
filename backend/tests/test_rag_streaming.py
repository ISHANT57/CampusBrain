"""stream_answer: the streaming counterpart to answer_question.

hybrid_search and get_llm_provider are monkeypatched -- no DB, no Qdrant, no
Gemini key needed. Guards the contract stated in stream_answer's own
docstring: every event but the last is a raw delta, the last is a "done"
event whose answer/citations exactly match what keep_cited_sources would
produce on the fully-assembled text.
"""

import pytest

from app.infrastructure.llm.base import StreamChunk
from app.infrastructure.usage import TokenUsage
from app.services import rag_service


@pytest.fixture(autouse=True)
def _no_real_db_writes(monkeypatch):
    """rag_service now records a usage row and an eval trace, both of which
    open their own DB session. These tests have no database -- both services
    fail open by design, so they'd still pass, but each would burn a
    connection timeout first. Stub them out; their own test files cover the
    real behavior."""
    monkeypatch.setattr(rag_service.eval_service, "record_trace", lambda **kw: None)
    monkeypatch.setattr(rag_service.usage_service, "record", lambda **kw: None)

HITS = [
    {"chunk_id": 1, "document_id": 10, "page_number": 1, "text": "Fees are 50000.", "semantic_score": 0.9},
    {"chunk_id": 2, "document_id": 11, "page_number": 3, "text": "Other info.", "semantic_score": 0.8},
]


class _FakeProvider:
    def __init__(self, pieces, usage: TokenUsage | None = None):
        self._pieces = pieces
        self._usage = usage

    def generate_stream(self, _prompt):
        for text in self._pieces:
            yield StreamChunk(text=text)
        if self._usage is not None:
            yield StreamChunk(text="", usage=self._usage)


class _FakeBlockingProvider:
    def __init__(self, text, usage: TokenUsage | None = None):
        self._text = text
        self._usage = usage

    def generate(self, _prompt):
        from app.infrastructure.llm.base import GenerationResult
        return GenerationResult(text=self._text, usage=self._usage)


def test_answer_question_records_usage_from_the_blocking_response(monkeypatch):
    monkeypatch.setattr(rag_service, "hybrid_search", lambda db, org_id, q, k: HITS)
    monkeypatch.setattr(rag_service, "sanitize_context", lambda t: t)
    usage = TokenUsage(prompt_tokens=50, completion_tokens=10, total_tokens=60)
    monkeypatch.setattr(rag_service, "get_llm_provider", lambda: _FakeBlockingProvider("Fees are 50000 [1].", usage))

    recorded = []
    monkeypatch.setattr(rag_service.usage_service, "record", lambda **kw: recorded.append(kw))

    result = rag_service.answer_question(db=None, org_id=1, question="how much are fees?")

    assert result["answer"] == "Fees are 50000 [1]."
    assert len(recorded) == 1
    assert recorded[0]["usage"] == usage


def test_refusal_short_circuits_without_ever_calling_the_llm(monkeypatch):
    monkeypatch.setattr(rag_service, "hybrid_search", lambda db, org_id, q, k: [])

    def must_not_be_called():
        raise AssertionError("get_llm_provider must not be called on a refusal")
    monkeypatch.setattr(rag_service, "get_llm_provider", must_not_be_called)

    events = list(rag_service.stream_answer(db=None, org_id=1, question="anything"))
    assert events == [
        {"type": "delta", "text": rag_service.NO_EVIDENCE_RESPONSE},
        {
            "type": "done",
            "answer": rag_service.NO_EVIDENCE_RESPONSE,
            "citations": [],
            # Grounding is reported on the refusal path too: "nothing retrieved
            # reached 0.35" is a measured statement, and omitting it here would
            # make a refusal indistinguishable from a backend too old to report
            # grounding at all.
            "grounding": {
                "best_semantic_score": 0.0,
                "relevance_threshold": rag_service.RELEVANCE_THRESHOLD,
                "retrieved_chunks": 0,
                "cited_chunks": 0,
                "cited_documents": 0,
                "refused": True,
            },
        },
    ]


def test_deltas_forward_raw_chunks_then_done_carries_renumbered_citations(monkeypatch):
    monkeypatch.setattr(rag_service, "hybrid_search", lambda db, org_id, q, k: HITS)
    monkeypatch.setattr(rag_service, "sanitize_context", lambda t: t)
    monkeypatch.setattr(rag_service, "get_llm_provider", lambda: _FakeProvider(["Fees are 50000 ", "[1]."]))

    events = list(rag_service.stream_answer(db=None, org_id=1, question="how much are fees?"))

    deltas = [e for e in events if e["type"] == "delta"]
    done = [e for e in events if e["type"] == "done"]
    assert [d["text"] for d in deltas] == ["Fees are 50000 ", "[1]."]
    assert len(done) == 1
    assert done[0]["answer"] == "Fees are 50000 [1]."
    assert done[0]["citations"] == [
        {"index": 1, "document_id": 10, "page_number": 1, "chunk_id": 1, "excerpt": "Fees are 50000."},
    ]


def test_usage_from_the_final_chunk_is_recorded_once_streaming_completes(monkeypatch):
    monkeypatch.setattr(rag_service, "hybrid_search", lambda db, org_id, q, k: HITS)
    monkeypatch.setattr(rag_service, "sanitize_context", lambda t: t)
    usage = TokenUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120)
    monkeypatch.setattr(rag_service, "get_llm_provider", lambda: _FakeProvider(["ok"], usage=usage))

    recorded = []
    monkeypatch.setattr(rag_service.usage_service, "record", lambda **kw: recorded.append(kw))

    list(rag_service.stream_answer(db=None, org_id=1, question="how much are fees?"))

    assert len(recorded) == 1
    assert recorded[0]["usage"] == usage
    assert recorded[0]["operation"] == "chat.generate"
    assert recorded[0]["org_id"] == 1


def test_a_client_disconnecting_mid_stream_still_logs_the_partial_answer(monkeypatch):
    monkeypatch.setattr(rag_service, "hybrid_search", lambda db, org_id, q, k: HITS)
    monkeypatch.setattr(rag_service, "sanitize_context", lambda t: t)
    monkeypatch.setattr(rag_service, "get_llm_provider", lambda: _FakeProvider(["a ", "b ", "c "]))

    logged = []
    monkeypatch.setattr(rag_service.logger, "info", lambda _msg, extra=None: logged.append(extra))

    gen = rag_service.stream_answer(db=None, org_id=1, question="q")
    assert next(gen)["type"] == "retrieved"  # the leading sources event
    next(gen)  # consume exactly one delta, as if the client read one chunk then vanished
    gen.close()  # what Python/Starlette does on early teardown -- must not raise

    assert len(logged) == 1
    assert logged[0]["event"]["event"] == "rag_answer"
    assert logged[0]["event"]["refused"] is False


def test_a_client_disconnecting_before_generation_is_still_logged(monkeypatch):
    """Disconnect at the "retrieved" event, before a single token exists.

    Regression guard: the retrieved event was briefly emitted ABOVE the
    try/except GeneratorExit, and because GeneratorExit is raised at whichever
    yield the generator is parked on, a client that left during this window
    skipped the partial-answer log entirely -- an abandoned answer vanishing
    from the record, which is exactly what that handler exists to prevent.
    """
    monkeypatch.setattr(rag_service, "hybrid_search", lambda db, org_id, q, k: HITS)
    monkeypatch.setattr(rag_service, "sanitize_context", lambda t: t)
    monkeypatch.setattr(rag_service, "get_llm_provider", lambda: _FakeProvider(["a ", "b "]))

    logged = []
    monkeypatch.setattr(rag_service.logger, "info", lambda _msg, extra=None: logged.append(extra))

    gen = rag_service.stream_answer(db=None, org_id=1, question="q")
    assert next(gen)["type"] == "retrieved"
    gen.close()

    assert len(logged) == 1
    assert logged[0]["event"]["event"] == "rag_answer"
    # No tokens were produced, so the recorded answer is empty -- the point is
    # that the attempt is on the record at all, not that it produced text.
    assert logged[0]["event"]["citation_count"] == 0


def test_retrieved_event_groups_chunks_by_document_in_rank_order(monkeypatch):
    """The leading event collapses chunks to documents, so the sources panel can
    fill during generation instead of holding a skeleton until "done"."""
    hits = [
        {"chunk_id": 1, "document_id": 10, "page_number": 4, "text": "a", "semantic_score": 0.9},
        {"chunk_id": 2, "document_id": 11, "page_number": 3, "text": "b", "semantic_score": 0.8},
        {"chunk_id": 3, "document_id": 10, "page_number": 2, "text": "c", "semantic_score": 0.7},
    ]
    monkeypatch.setattr(rag_service, "hybrid_search", lambda db, org_id, q, k: hits)
    monkeypatch.setattr(rag_service, "sanitize_context", lambda t: t)
    monkeypatch.setattr(rag_service, "get_llm_provider", lambda: _FakeProvider(["x [1]"]))

    events = list(rag_service.stream_answer(db=None, org_id=1, question="q"))

    assert events[0]["type"] == "retrieved"  # must precede every delta
    assert events[0]["documents"] == [
        # doc 10 first: it owns the top-ranked chunk. Pages ascending, not
        # retrieval order -- "pp.2,4" is how a reader expects to see them.
        {"document_id": 10, "pages": [2, 4], "chunks": 2},
        {"document_id": 11, "pages": [3], "chunks": 1},
    ]


def test_a_refusal_emits_no_retrieved_event(monkeypatch):
    """Nothing cleared the relevance floor, so there are no sources to show.

    Listing the retrieved-but-rejected documents next to "I don't have
    information on that" would invite the reader to go read them as though they
    were relevant, when the refusal's entire meaning is that they are not.
    """
    weak = [{"chunk_id": 1, "document_id": 10, "page_number": 1, "text": "x", "semantic_score": 0.1}]
    monkeypatch.setattr(rag_service, "hybrid_search", lambda db, org_id, q, k: weak)

    events = list(rag_service.stream_answer(db=None, org_id=1, question="q"))

    assert [e["type"] for e in events] == ["delta", "done"]
    assert events[-1]["grounding"]["refused"] is True
    assert events[-1]["grounding"]["retrieved_chunks"] == 1
    assert events[-1]["grounding"]["cited_documents"] == 0
