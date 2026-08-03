"""Phase 2 architectural rule, enforced rather than just documented: Redis
(Upstash) is a cache/rate-limit store, never a source of truth. PostgreSQL
holds every durable fact in this system.

This is a "fitness function" test -- it doesn't exercise behavior, it scans
the source tree so a future PR that quietly starts using Redis as a queue,
a session store, or anything else load-bearing fails here with a pointer to
why, instead of the drift going unnoticed until an incident explains it.
"""

from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"

# Every file allowed to mention Redis/Upstash, and why. Adding a new file to
# this list should mean you've just re-read ADR-013 (cache.py's fail-open
# design) and are confident the new usage is cache/rate-limit/ephemeral, not
# durable state -- not that the test was merely in the way.
ALLOWED_FILES = {
    "core/config.py",  # settings fields (URL/token) -- configuration, not usage
    "infrastructure/cache.py",  # the one real usage: a fail-open, off-by-default embedding cache
    "core/rate_limit.py",  # comment only, naming Upstash as the future migration target
}


def test_redis_mentions_are_confined_to_the_allowed_files():
    offenders = []
    for path in APP_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(APP_DIR).as_posix()
        if rel in ALLOWED_FILES:
            continue
        text = path.read_text(encoding="utf-8").lower()
        if "redis" in text or "upstash" in text:
            offenders.append(rel)

    assert offenders == [], (
        f"Redis/Upstash mentioned outside the allowed files: {offenders}. "
        "If this is a genuine new cache/rate-limit use, add the file to "
        "ALLOWED_FILES here with a one-line reason. If it's anything durable "
        "(a queue, a session, a record nothing else can reconstruct), it "
        "belongs in Postgres instead -- see ADR-013 in ENGINEERING_ROADMAP.md."
    )


def test_cache_module_is_fail_open_not_a_dependency(monkeypatch):
    """The other half of the rule: even the one real usage must degrade to
    "no cache" on any failure, never to a broken request. Re-asserts what
    test_cache.py already covers in detail, as a one-line pointer from the
    architectural rule to where it's actually verified."""
    from app.infrastructure import cache

    monkeypatch.setattr(cache.settings, "upstash_redis_rest_url", "https://x.upstash.io")
    monkeypatch.setattr(cache.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("down")))
    assert cache.get_embedding("ns", "anything") is None  # never raises
