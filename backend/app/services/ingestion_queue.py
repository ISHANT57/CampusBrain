"""Postgres-backed durable job queue for document ingestion.

Replaces FastAPI BackgroundTasks (in-process, non-durable -- lost on a crash
or a Render free-tier sleep mid-job) with rows in ingestion_jobs. The worker
is still in-process (Render free has no free background-worker service type),
but the WORK now survives a process death: a claimed-but-never-finished job
is just a row with a stale claimed_at, and the reaper below puts it back to
pending. Nothing here depends on FastAPI or the request path, so splitting
it into a real second process later (if this ever leaves free tier) is
pointing a new entrypoint at run_worker_loop(), not a redesign.

Job lifecycle, exactly the four states asked for -- no fifth "retrying"
state: a failed attempt with retries left goes back to PENDING with a
delayed next_attempt_at; FAILED is reserved for attempts exhausted.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.document import Document, DocumentStatus
from app.models.ingestion_job import IngestionJob, IngestionJobStatus

logger = logging.getLogger("ingestion_queue")

# How often the worker checks for pending work. Cheap indexed query on a
# single-tenant-scale table; no need to make this configurable yet.
POLL_INTERVAL_SECONDS = 5.0

# A claimed job whose worker hasn't finished within this long is presumed
# dead (crashed, or the instance slept/restarted mid-job) and is recovered by
# the reaper. Generously above the ~250s worst-case ingest this deployment
# has actually measured, so a slow-but-alive job is never double-processed.
LEASE_TIMEOUT_SECONDS = 15 * 60


def _backoff_seconds(attempt: int) -> float:
    # Minutes-scale, not the seconds-scale backoff in infrastructure/retry.py
    # -- that one covers a single HTTP call; this covers a whole ingestion
    # job, where the likely cause of failure (a sleeping instance, a
    # transient Gemini 5xx across dozens of chunks) needs longer to clear.
    base = 30.0 * (2 ** (attempt - 1))  # 30s, 60s, 120s, ...
    capped = min(base, 15 * 60)
    return capped + random.uniform(0, capped * 0.25)


def enqueue(db: Session, *, org_id: int, document_id: int, user_id: int | None = None) -> IngestionJob:
    """Create a pending job. Caller owns the transaction -- this only adds
    and flushes, so it commits atomically with whatever else the caller is
    persisting (the Document row, the audit log entry)."""
    job = IngestionJob(org_id=org_id, document_id=document_id, user_id=user_id)
    db.add(job)
    db.flush()
    return job


def claim_next(db: Session) -> IngestionJob | None:
    """Atomically claim the oldest eligible pending job, or None if there
    isn't one. FOR UPDATE SKIP LOCKED means two pollers (or a poller and a
    manual retry) can never claim the same row -- the second one just skips
    it instead of blocking or erroring.
    """
    row = db.execute(
        sql_text(
            """
            UPDATE ingestion_jobs
            SET status = 'processing', claimed_at = now(), attempts = attempts + 1
            WHERE id = (
                SELECT id FROM ingestion_jobs
                WHERE status = 'pending' AND next_attempt_at <= now()
                ORDER BY next_attempt_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id
            """
        )
    ).first()
    db.commit()
    if row is None:
        return None
    return db.get(IngestionJob, row.id)


def mark_completed(db: Session, job: IngestionJob) -> None:
    job.status = IngestionJobStatus.COMPLETED
    db.commit()


def mark_failed_or_retry(db: Session, job: IngestionJob, error: Exception) -> None:
    # Type name + a truncated message, not the full traceback: this lands in
    # a column an admin endpoint could plausibly expose later, and a raw
    # exception message can carry more detail than intended for that
    # audience (same reasoning as the /health/ready error handling).
    job.last_error = f"{type(error).__name__}: {str(error)[:500]}"
    if job.attempts >= job.max_attempts:
        job.status = IngestionJobStatus.FAILED
    else:
        job.status = IngestionJobStatus.PENDING
        job.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=_backoff_seconds(job.attempts))
    db.commit()


def recover_stale_jobs(db: Session) -> int:
    """Jobs stuck at PROCESSING with an expired lease -- their worker died
    without ever calling mark_completed/mark_failed_or_retry (a crash, or the
    instance restarting mid-job). Put back to PENDING for immediate reclaim;
    attempts was already incremented at claim time, so this naturally counts
    toward max_attempts without any extra bookkeeping here.
    """
    result = db.execute(
        sql_text(
            """
            UPDATE ingestion_jobs
            SET status = 'pending', claimed_at = NULL
            WHERE status = 'processing'
              AND claimed_at < now() - (:lease_seconds * interval '1 second')
            """
        ),
        {"lease_seconds": LEASE_TIMEOUT_SECONDS},
    )
    db.commit()
    if result.rowcount:
        logger.warning("recovered stale ingestion jobs", extra={"event": {
            "event": "ingestion_jobs_recovered", "count": result.rowcount,
        }})
    return result.rowcount


def _process_one(job_id: int) -> None:
    """Runs in a worker thread (see run_worker_loop) so a slow ingest never
    blocks the event loop / concurrent HTTP requests -- BackgroundTasks
    already gave this property via Starlette's threadpool; this preserves
    it rather than regressing to a blocking async loop.
    """
    from app.infrastructure import storage  # local import: avoids a cycle with document_processing_service
    from app.services.document_processing_service import index_document

    db = SessionLocal()
    try:
        job = db.get(IngestionJob, job_id)
        if job is None:
            return
        document = db.get(Document, job.document_id)
        if document is None:
            mark_failed_or_retry(db, job, RuntimeError("document row missing"))
            return

        try:
            document.status = DocumentStatus.PROCESSING
            db.commit()
            content = storage.get_object(document.storage_key)
            index_document(db, document, content, user_id=job.user_id)
            document.status = DocumentStatus.PROCESSED
            db.commit()
            mark_completed(db, job)
        except Exception as e:
            db.rollback()  # undoes any uncommitted new chunks/status from this attempt; old content is untouched
            logger.exception("ingestion job failed", extra={"event": {
                "event": "ingestion_job_failed", "job_id": job.id, "document_id": document.id,
                "attempt": job.attempts, "error": type(e).__name__,
            }})
            mark_failed_or_retry(db, job, e)  # decides retry (PENDING) vs exhausted (FAILED), commits
            # A job with retries left is NOT a failed document -- it's about
            # to be tried again. Only the terminal state should ever read as
            # FAILED to an admin polling GET /documents/{id}; a retry means
            # PENDING is still the honest, user-facing status.
            document.status = (
                DocumentStatus.FAILED if job.status == IngestionJobStatus.FAILED else DocumentStatus.PENDING
            )
            db.commit()
    finally:
        db.close()


async def run_worker_loop() -> None:
    """The in-process 'worker'. Started from main.py's lifespan, cancelled
    on shutdown. One iteration: reap stale claims, then claim and process at
    most one job (leaving the next poll to pick up the rest keeps any single
    iteration bounded and the loop responsive to cancellation)."""
    logger.info("ingestion worker loop started")
    while True:
        try:
            db = SessionLocal()
            try:
                recover_stale_jobs(db)
                job = claim_next(db)
            finally:
                db.close()

            if job is not None:
                await asyncio.to_thread(_process_one, job.id)
                continue  # check for more pending work immediately instead of sleeping
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("ingestion worker loop iteration failed")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)
