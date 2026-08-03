"""_stream_events: the SSE line formatting + citation hydration that sits
between rag_service.stream_answer and the wire. stream_answer and
DocumentRepository are both stubbed -- no DB, no Gemini, no Qdrant.
"""

import json

# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import chat as chat_module
from app.core.rate_limit import limiter
from app.schemas.chat import ChatRequest


class _StubDoc:
    def __init__(self, filename: str):
        self.filename = filename


class _StubDocRepo:
    def __init__(self, _db, _org_id):
        pass

    def get(self, document_id: int):
        return _StubDoc(f"doc-{document_id}.pdf")


GROUNDING = {
    "best_semantic_score": 0.82,
    "relevance_threshold": 0.35,
    "retrieved_chunks": 3,
    "cited_chunks": 1,
    "cited_documents": 1,
    "refused": False,
}


def _fake_stream_answer(_db, _org_id, _question, top_k=5, history=None):
    yield {"type": "retrieved", "documents": [{"document_id": 7, "pages": [2, 5], "chunks": 2}]}
    yield {"type": "delta", "text": "Hello "}
    yield {"type": "delta", "text": "world."}
    yield {
        "type": "done",
        "answer": "Hello world. [1]",
        "citations": [{"index": 1, "document_id": 7, "page_number": 2, "chunk_id": 99, "excerpt": "hi"}],
        "grounding": GROUNDING,
    }


def _parse(line: str) -> dict:
    assert line.startswith("data: ") and line.endswith("\n\n")
    return json.loads(line[len("data: "):-2])


def test_deltas_pass_through_unchanged_and_done_gets_hydrated_citations(monkeypatch):
    monkeypatch.setattr(chat_module, "stream_answer", _fake_stream_answer)
    monkeypatch.setattr(chat_module, "DocumentRepository", _StubDocRepo)

    lines = list(chat_module._stream_events(db=None, org_id=1, payload=ChatRequest(question="hi")))
    events = [_parse(line) for line in lines]

    # The retrieved event is hydrated with filenames too -- rag_service deals in
    # document ids and this layer is the only place a display string is resolved,
    # so an un-hydrated retrieved event would surface a bare id to the user.
    assert events[0] == {
        "type": "retrieved",
        "documents": [{"document_id": 7, "filename": "doc-7.pdf", "pages": [2, 5], "chunks": 2}],
    }
    assert events[1] == {"type": "delta", "text": "Hello "}
    assert events[2] == {"type": "delta", "text": "world."}
    assert events[3]["type"] == "done"
    assert events[3]["citations"] == [
        {"index": 1, "document_id": 7, "filename": "doc-7.pdf", "page_number": 2, "excerpt": "hi"},
    ]
    # Passed through untouched: grounding needs no hydration, and this layer must
    # not reshape it (the blocking endpoint returns the identical object).
    assert events[3]["grounding"] == GROUNDING


def test_unknown_document_id_hydrates_to_unknown_filename(monkeypatch):
    class _MissingDocRepo(_StubDocRepo):
        def get(self, _document_id):
            return None

    monkeypatch.setattr(chat_module, "stream_answer", _fake_stream_answer)
    monkeypatch.setattr(chat_module, "DocumentRepository", _MissingDocRepo)

    lines = list(chat_module._stream_events(db=None, org_id=1, payload=ChatRequest(question="hi")))
    done = _parse(lines[-1])
    assert done["citations"][0]["filename"] == "(unknown)"


def test_slash_stream_routes_to_the_sse_handler_not_the_org_slug_catch_all(monkeypatch):
    """Regression guard for the exact bug the registration-order comment in
    chat.py warns about: "/chat/stream" also matches "/{org_slug}" with
    org_slug="stream", and FastAPI resolves in registration order. If
    chat_stream / chat_stream_for_org ever get moved after chat_for_org in
    the file, this starts returning a JSON ChatResponse instead of SSE."""
    monkeypatch.setattr(chat_module, "_org_id", lambda db, slug: 1)
    monkeypatch.setattr(chat_module, "stream_answer", _fake_stream_answer)
    monkeypatch.setattr(chat_module, "DocumentRepository", _StubDocRepo)

    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(chat_module.router, prefix="/api/v1")
    client = TestClient(app)

    response = client.post("/api/v1/chat/stream", json={"question": "hi"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [_parse(line + "\n\n") for line in response.text.strip("\n").split("\n\n") if line]
    assert events[0]["type"] == "retrieved"
    assert events[1] == {"type": "delta", "text": "Hello "}
