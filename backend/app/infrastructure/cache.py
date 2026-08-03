"""Query-embedding cache via Upstash Redis's free-tier REST API.

REST, not the TCP redis-py client: Upstash's REST API is a single HTTPS POST
with a command array, which is what every other outbound call in this app
already does (raw httpx, no SDK -- see the Gemini providers) rather than
adding a new client library and a TCP connection to manage on a 512 MB box.

Best-effort by design: any cache failure (unreachable, misconfigured,
timeout) is treated as a miss, never as a request failure. A cache is a
latency/cost optimisation; a chat request must still answer correctly with
the cache down or turned off entirely.

Off by default: UPSTASH_REDIS_REST_URL unset means every call below is a
no-op, so a deploy with no Upstash account configured behaves exactly as if
this file didn't exist.
"""

import hashlib
import json
import logging

import httpx

from app.core import metrics
from app.core.config import settings

logger = logging.getLogger("cache")

# Popular questions repeat within a class day, not across a semester -- and a
# short TTL means a corpus re-index is never shadowed by a stale cached
# embedding for longer than this.
TTL_SECONDS = 6 * 60 * 60


def _key(namespace: str, text: str) -> str:
    # Hash rather than the raw query text: keeps keys a fixed short length,
    # and Upstash's dashboard/logs don't need to hold user questions verbatim.
    return f"emb:{namespace}:{hashlib.sha256(text.encode()).hexdigest()}"


def _command(*args) -> object | None:
    if not settings.upstash_redis_rest_url:
        return None
    try:
        response = httpx.post(
            settings.upstash_redis_rest_url,
            headers={"Authorization": f"Bearer {settings.upstash_redis_rest_token}"},
            json=list(args),
            # A slow cache must never make chat slower than no cache at all --
            # 2s is generous for a same-region REST round trip and still far
            # cheaper than falling through to a real embedding call.
            timeout=2.0,
        )
        response.raise_for_status()
        return response.json().get("result")
    except Exception as e:
        logger.warning("cache request failed, treating as a miss", extra={"event": {
            "event": "cache_error", "command": args[0] if args else None, "error": type(e).__name__,
        }})
        return None


def get_embedding(namespace: str, text: str) -> list[float] | None:
    raw = _command("GET", _key(namespace, text))
    if raw is None:
        metrics.incr("cache.embedding.miss")
        return None
    metrics.incr("cache.embedding.hit")
    return json.loads(raw)


def set_embedding(namespace: str, text: str, vector: list[float]) -> None:
    _command("SET", _key(namespace, text), json.dumps(vector), "EX", TTL_SECONDS)
