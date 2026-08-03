"""Shared retry helper for outbound Gemini calls.

INC-002, encoded: a 429 means one of two different things -- "slow down"
(retryable) or "come back tomorrow" (a daily quota; no backoff schedule fixes
that, and OpenRouter's 5/10/20/40s loop once turned a 400ms failure into 75
seconds while burning 4x the exhausted quota). Gemini's free tier is a
per-minute limit rather than OpenRouter's per-day one, so 429 is treated as
retryable here -- but capped at 3 attempts, not 5, so a genuine quota
exhaustion still fails fast instead of amplifying the outage.

4xx other than 429 is never retried: a bad request or a bad key doesn't get
fixed by trying again, and retrying it only adds latency to a failure that
was already final.
"""

import logging
import random
import time

import httpx

logger = logging.getLogger("retry")

# Public (no leading underscore): shared with gemini_provider.generate_stream,
# which needs the same classification for the streaming endpoint's initial
# connection but can't reuse post_with_retry itself (a streamed response has
# no single body to retry once bytes have started arriving).
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def backoff(attempt: int) -> float:
    base = 1.0 * (2**attempt)  # 1s, 2s, 4s
    return base + random.uniform(0, base * 0.25)  # jitter: avoid a thundering herd on a shared quota


def post_with_retry(url: str, *, max_attempts: int = 3, **kwargs) -> httpx.Response:
    """httpx.post with retry on 5xx / 429 / connection errors and timeouts.

    Anything else (a 4xx, a malformed request) raises immediately via
    response.raise_for_status() on the final or only attempt.
    """
    for attempt in range(max_attempts):
        try:
            response = httpx.post(url, **kwargs)
        except (httpx.TimeoutException, httpx.ConnectError):
            if attempt == max_attempts - 1:
                raise
            logger.warning("retrying after connection failure", extra={"event": {
                "event": "http_retry", "url": url, "attempt": attempt + 1, "reason": "connection",
            }})
            time.sleep(backoff(attempt))
            continue

        if response.status_code in RETRYABLE_STATUS and attempt < max_attempts - 1:
            logger.warning("retrying after error status", extra={"event": {
                "event": "http_retry", "url": url, "attempt": attempt + 1, "status": response.status_code,
            }})
            time.sleep(backoff(attempt))
            continue

        response.raise_for_status()
        return response
