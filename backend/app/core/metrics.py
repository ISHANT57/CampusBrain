"""In-process counters for a live operational view.

Deliberately NOT durable: these reset on every restart, and Render's free
tier restarts often. They answer "what is happening right now", not "what
happened last Tuesday" -- that second question is answered by querying the
structured logs (observability.py), which outlive the process.

No prometheus_client: it would add a dependency to produce an exposition
format nothing here scrapes. A JSON endpoint is the same information for one
import fewer.
"""

import threading
from collections import deque

_lock = threading.Lock()  # uvicorn runs sync endpoints in a threadpool
_counters: dict[str, int] = {}
_latencies: dict[str, deque] = {}  # bounded ring buffers -- memory is capped


def incr(name: str, n: int = 1) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0) + n


def observe(name: str, value_ms: float) -> None:
    with _lock:
        _latencies.setdefault(name, deque(maxlen=1000)).append(value_ms)


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return round(s[min(int(len(s) * p), len(s) - 1)], 1)


def snapshot() -> dict:
    with _lock:
        counters = dict(_counters)
        latencies = {k: list(v) for k, v in _latencies.items()}

    answers = counters.get("rag.answers", 0)
    return {
        "counters": counters,
        "rates": {
            # Guard the divisor: these are the fields most likely to be read
            # by a dashboard, and a ZeroDivisionError in a metrics endpoint
            # is a self-inflicted outage.
            "refusal_rate": round(counters.get("rag.refused", 0) / answers, 3) if answers else None,
            "zero_keyword_hit_rate": round(counters.get("rag.zero_keyword", 0) / answers, 3) if answers else None,
            "mean_citations": round(counters.get("rag.citations", 0) / answers, 2) if answers else None,
        },
        "latency_ms": {
            name: {"n": len(v), "p50": _pct(v, 0.50), "p95": _pct(v, 0.95), "p99": _pct(v, 0.99)}
            for name, v in latencies.items()
        },
    }
