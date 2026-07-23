import logging

import httpx

from app.core.config import settings

# API contract confirmed against a live call with a real key (2026):
#   POST https://api.jina.ai/v1/rerank
#   header: Authorization: Bearer <key>
#   body:   {"model": ..., "query": ..., "documents": [str], "top_n": N}
#   response: {"results": [{"index": i, "relevance_score": float}], "usage": {...}}
#
# Note results come back ORDERED BY SCORE, not by input index — hence the
# realignment below. Reading them positionally would silently scramble every
# chunk's score onto the wrong chunk.
_ENDPOINT = "https://api.jina.ai/v1/rerank"

# Short on purpose. This runs inside a question the user is waiting on, after
# retrieval and before the LLM call, so a slow reranker is worse than no
# reranker — the fused order it would have replaced is already decent.
_TIMEOUT = 8.0


def rerank(query: str, texts: list[str]) -> list[float] | None:
    """Relevance score per text, aligned to the ORDER TEXTS WERE PASSED IN.

    Returns None when reranking is unavailable, and the caller keeps its
    existing order. Never raises, which is the whole point: this is a quality
    improvement sitting in the request path of a public endpoint, and an
    expired key, a 503, or a slow response must degrade to plain hybrid search
    rather than take the chatbot down. That failure mode is not hypothetical
    here — an exhausted free tier on a different provider 500'd every question
    on this app once already.

    Off entirely when JINA_API_KEY is unset, so deploys without one behave
    exactly as they did before.
    """
    if not settings.jina_api_key or not texts:
        return None

    try:
        response = httpx.post(
            _ENDPOINT,
            headers={"Authorization": f"Bearer {settings.jina_api_key}"},
            json={
                "model": settings.rerank_model,
                "query": query,
                "documents": texts,
                # Every candidate scored, not just the winners — the caller
                # needs a score for each text to reorder the whole list.
                "top_n": len(texts),
                # The documents are echoed back by default; we already hold
                # them, and a 20-chunk payload doubles the response for no use.
                "return_documents": False,
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        results = response.json()["results"]
    except Exception:
        # Broad by intent: httpx timeouts, connection errors, HTTP status
        # errors and a changed response shape all mean the same thing to the
        # caller — no scores, carry on.
        logging.exception("Reranking unavailable, falling back to fused order")
        return None

    scores = [0.0] * len(texts)
    for result in results:
        index = result["index"]
        if 0 <= index < len(texts):
            scores[index] = result["relevance_score"]
    return scores
