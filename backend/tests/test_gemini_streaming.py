"""Gemini SSE streaming: the line parser (pure, no network) and
generate_stream's retry-before-first-byte behavior (httpx.stream mocked).

No real network or API key needed anywhere in this file.
"""

import httpx
import pytest

from app.infrastructure.llm import gemini_provider as gp
from app.infrastructure.llm.gemini_provider import _sse_text_fragments


# ---- _sse_text_fragments: pure parsing, one line in, zero or more strings out ----

def test_data_line_with_one_text_part():
    line = 'data: {"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]}'
    assert list(_sse_text_fragments(line)) == ["Hello"]


def test_data_line_with_multiple_parts_yields_each_in_order():
    line = 'data: {"candidates": [{"content": {"parts": [{"text": "A"}, {"text": "B"}]}}]}'
    assert list(_sse_text_fragments(line)) == ["A", "B"]


def test_blank_line_yields_nothing():
    assert list(_sse_text_fragments("")) == []


def test_non_data_line_yields_nothing():
    assert list(_sse_text_fragments("event: ping")) == []


def test_finish_reason_only_chunk_yields_nothing_not_an_error():
    """The terminal chunk of a stream often carries a finishReason and no
    parts at all -- that's normal, not the same as the blocking generate()'s
    'no text anywhere' error case."""
    line = 'data: {"candidates": [{"finishReason": "STOP", "content": {"parts": []}}]}'
    assert list(_sse_text_fragments(line)) == []


def test_no_candidates_yields_nothing():
    assert list(_sse_text_fragments('data: {"candidates": []}')) == []


# ---- generate_stream: httpx.stream mocked, no real network ----

class _FakeStream:
    """Enough of httpx.stream's context-manager return value to drive
    generate_stream: status_code, raise_for_status(), iter_lines()."""

    def __init__(self, status_code: int, lines: list[str]):
        self.status_code = status_code
        self._lines = lines

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error", request=httpx.Request("POST", "https://x"),
                response=httpx.Response(self.status_code, request=httpx.Request("POST", "https://x")),
            )

    def iter_lines(self):
        yield from self._lines

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _no_sleep(monkeypatch):
    monkeypatch.setattr(gp.time, "sleep", lambda _s: None)


def test_yields_text_pieces_in_order(monkeypatch):
    _no_sleep(monkeypatch)
    lines = [
        'data: {"candidates": [{"content": {"parts": [{"text": "Hello "}]}}]}',
        'data: {"candidates": [{"content": {"parts": [{"text": "world."}]}}]}',
        'data: {"candidates": [{"finishReason": "STOP"}]}',
    ]
    monkeypatch.setattr(gp.httpx, "stream", lambda *a, **k: _FakeStream(200, lines))
    chunks = list(gp.GeminiProvider().generate_stream("prompt"))
    assert [c.text for c in chunks] == ["Hello ", "world."]


def test_final_sentinel_chunk_carries_usage_when_present(monkeypatch):
    _no_sleep(monkeypatch)
    lines = [
        'data: {"candidates": [{"content": {"parts": [{"text": "Hi"}]}}]}',
        'data: {"candidates": [{"finishReason": "STOP"}], '
        '"usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 2, "totalTokenCount": 12}}',
    ]
    monkeypatch.setattr(gp.httpx, "stream", lambda *a, **k: _FakeStream(200, lines))
    chunks = list(gp.GeminiProvider().generate_stream("prompt"))
    assert [c.text for c in chunks] == ["Hi", ""]
    assert chunks[0].usage is None
    assert chunks[-1].usage.total_tokens == 12


def test_no_usage_metadata_means_no_sentinel_chunk(monkeypatch):
    _no_sleep(monkeypatch)
    lines = ['data: {"candidates": [{"content": {"parts": [{"text": "Hi"}]}}]}']
    monkeypatch.setattr(gp.httpx, "stream", lambda *a, **k: _FakeStream(200, lines))
    chunks = list(gp.GeminiProvider().generate_stream("prompt"))
    assert len(chunks) == 1  # no trailing empty-usage sentinel when there's nothing to report


def test_empty_stream_raises_instead_of_silently_returning_nothing(monkeypatch):
    _no_sleep(monkeypatch)
    monkeypatch.setattr(gp.httpx, "stream", lambda *a, **k: _FakeStream(200, []))
    with pytest.raises(RuntimeError):
        list(gp.GeminiProvider().generate_stream("prompt"))


def test_retryable_status_on_first_attempt_is_retried(monkeypatch):
    _no_sleep(monkeypatch)
    attempts = {"n": 0}

    def fake_stream(*_a, **_k):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return _FakeStream(503, [])
        return _FakeStream(200, ['data: {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}'])

    monkeypatch.setattr(gp.httpx, "stream", fake_stream)
    chunks = list(gp.GeminiProvider().generate_stream("prompt"))
    assert [c.text for c in chunks] == ["ok"]
    assert attempts["n"] == 2


def test_client_error_is_not_retried(monkeypatch):
    """A 4xx (other than 429) on the initial response is final, same
    classification as the non-streaming path in retry.py."""
    _no_sleep(monkeypatch)
    monkeypatch.setattr(gp.httpx, "stream", lambda *a, **k: _FakeStream(404, []))
    with pytest.raises(httpx.HTTPStatusError):
        list(gp.GeminiProvider().generate_stream("prompt"))
