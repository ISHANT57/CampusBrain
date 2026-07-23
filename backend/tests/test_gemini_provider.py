"""Unit tests for the Gemini LLM provider's response parsing.

No network — httpx.post is stubbed:
    docker compose exec backend pytest tests/test_gemini_provider.py

Guards the one branch that isn't a straight-line JSON read: a candidate that
comes back with no text parts (safety block, token limit) must name the reason
instead of KeyError-ing into an opaque 500.
"""

import httpx
import pytest

from app.infrastructure.llm import gemini_provider


def stub_response(payload: dict):
    return httpx.Response(200, json=payload, request=httpx.Request("POST", "https://x"))


@pytest.fixture
def post(monkeypatch):
    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["json"] = kwargs.get("json")
        return calls["response"]

    monkeypatch.setattr(gemini_provider.httpx, "post", fake_post)
    return calls


def test_returns_the_candidate_text(post):
    post["response"] = stub_response(
        {"candidates": [{"content": {"parts": [{"text": "Fees are 50,000."}]}}]}
    )
    assert gemini_provider.GeminiProvider().generate("how much?") == "Fees are 50,000."
    assert post["json"] == {"contents": [{"parts": [{"text": "how much?"}]}]}


def test_joins_multiple_text_parts_and_skips_non_text(post):
    # Gemini 3.x can split a reply across parts, and can interleave parts with
    # no "text" key at all — taking parts[0]["text"] would truncate or KeyError.
    post["response"] = stub_response(
        {"candidates": [{"content": {"parts": [{"text": "Fees "}, {"thought": True}, {"text": "are 50,000."}]}}]}
    )
    assert gemini_provider.GeminiProvider().generate("how much?") == "Fees are 50,000."


def test_empty_candidate_names_the_finish_reason(post):
    post["response"] = stub_response({"candidates": [{"finishReason": "SAFETY"}]})
    with pytest.raises(RuntimeError, match="SAFETY"):
        gemini_provider.GeminiProvider().generate("how much?")
