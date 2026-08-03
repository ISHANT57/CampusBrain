"""ingestion_queue's pure/stubbable logic: backoff and the completed/retry/
failed state transitions. claim_next, recover_stale_jobs and enqueue all
need real Postgres (SKIP LOCKED, a real transaction) and are covered by
integration testing instead:
    docker compose exec backend python -m pytest tests/test_ingestion_queue.py
"""

from app.models.ingestion_job import IngestionJob, IngestionJobStatus
from app.services import ingestion_queue as iq


class StubDB:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def test_backoff_grows_and_is_capped():
    values = [iq._backoff_seconds(a) for a in range(1, 8)]
    # Strictly increasing up to the cap (jitter can't push a later attempt
    # below an earlier one's base, since base itself doubles each time).
    bases = [30.0 * (2 ** (a - 1)) for a in range(1, 8)]
    for v, base in zip(values, bases):
        capped_base = min(base, 15 * 60)
        assert capped_base <= v <= capped_base * 1.25
    assert iq._backoff_seconds(10) <= 15 * 60 * 1.25  # cap holds for a large attempt count


def test_mark_completed_sets_status():
    db = StubDB()
    job = IngestionJob(attempts=1, max_attempts=5)
    iq.mark_completed(db, job)
    assert job.status == IngestionJobStatus.COMPLETED
    assert db.commits == 1


def test_mark_failed_or_retry_schedules_a_retry_when_attempts_remain():
    db = StubDB()
    job = IngestionJob(attempts=2, max_attempts=5)
    iq.mark_failed_or_retry(db, job, RuntimeError("transient"))
    assert job.status == IngestionJobStatus.PENDING
    assert job.next_attempt_at is not None
    assert "RuntimeError" in job.last_error
    assert db.commits == 1


def test_mark_failed_or_retry_gives_up_once_attempts_are_exhausted():
    db = StubDB()
    job = IngestionJob(attempts=5, max_attempts=5)
    iq.mark_failed_or_retry(db, job, RuntimeError("still broken"))
    assert job.status == IngestionJobStatus.FAILED
    assert "RuntimeError" in job.last_error
