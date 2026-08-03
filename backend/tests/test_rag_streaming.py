"""stream_answer: the streaming counterpart to answer_question.

hybrid_search and get_llm_provider are monkeypatched -- no DB, no Qdrant, no
Gemini key needed. Guards the contract stated in stream_answer's own
docstring: every event but the last is a raw delta, the last is a "done"
event whose answer/citations exactly match what keep_cited_sources would
produce on the fully-assembled text.
"""

from app.infrastructure.llm.base import StreamChunk
from app.infrastructure.usage import TokenUsage
from app.services import rag_service

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
        {"type": "done", "answer": rag_service.NO_EVIDENCE_RESPONSE, "citations": []},
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
    next(gen)  # consume exactly one delta, as if the client read one chunk then vanished
    gen.close()  # what Python/Starlette does on early teardown -- must not raise

    assert len(logged) == 1
    assert logged[0]["event"]["event"] == "rag_answer"
    assert logged[0]["event"]["refused"] is False
