import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

# pyrefly: ignore [missing-import]
from fastapi import Depends, FastAPI, Request
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse
from sqlalchemy import text as sql_text

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.documents import router as documents_router
from app.api.v1.search import router as search_router
from app.core import database, metrics
from app.core.config import settings
from app.core.dependencies import require_search_access
from app.core.observability import configure_logging, request_id_var
from app.core.rate_limit import limiter
from app.infrastructure import storage, vector_store
from app.services import ingestion_queue

configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # The "worker" from Phase 1: an asyncio task in this SAME process, not a
    # second Render service (the free tier has no free background-worker
    # slot). Cancelled on shutdown rather than left to be killed mid-poll,
    # so a graceful restart never looks like the crash the job queue exists
    # to survive in the first place.
    worker_task = asyncio.create_task(ingestion_queue.run_worker_loop())
    try:
        yield
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="CampusBrain AI", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")


@app.middleware("http")
async def unhandled_errors_keep_cors(request: Request, call_next):
    """Turn an unhandled exception into a normal 500 response, here.

    Starlette's own 500 handler sits OUTSIDE every middleware including CORS,
    so an unhandled exception produced a bare `Internal Server Error` with no
    `Access-Control-Allow-Origin` header. The browser then reported it as a
    CORS failure and the frontend only ever saw "Failed to fetch" — which is
    how an exhausted LLM quota spent an afternoon looking like a CORS bug.

    Registered BEFORE add_middleware(CORSMiddleware) on purpose: the
    last-added middleware is the outermost, so CORS wraps this one and gets to
    stamp its headers on the response this returns.
    """
    try:
        return await call_next(request)
    except Exception:
        logging.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# CORS_ALLOWED_ORIGINS defaults to "*" for local dev (Vite dev server,
# Codespaces forwarded URLs, arbitrary ports). A split-origin production
# deploy — Vercel frontend, Render backend — MUST set this to the real
# Vercel origin(s); "*" in production means any website can call this API
# using a logged-in user's browser session.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Stamp every request with a correlation id, registered LAST so it is
    OUTERMOST and runs FIRST — the id is set before unhandled_errors_keep_cors
    can log an exception, and that existing logging.exception call picks it
    up for free via RequestIdFilter.
    """
    # Honour an inbound id (a proxy or the frontend may supply one) so a
    # client-side error report can be joined to the server-side trace. The
    # length cap bounds an otherwise-unbounded client-controlled string
    # landing in every log line for the rest of the request.
    incoming = request.headers.get("X-Request-Id")
    rid = incoming if incoming and len(incoming) <= 64 else str(uuid.uuid4())
    token = request_id_var.set(rid)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-Id"] = rid
    logging.getLogger("http").info("request", extra={"event": {
        "event": "http_request",
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": round((time.perf_counter() - started) * 1000),
    }})
    return response


@app.get("/health")
def health() -> dict:
    # Deliberately dependency-free — this is the liveness probe a host
    # (Render, a load balancer) polls to decide whether to keep this instance
    # running. If it started checking Postgres/Qdrant/storage and one of them
    # blipped, the platform could kill and restart a perfectly healthy
    # process. See /health/storage for an actual dependency check.
    return {"status": "ok"}


@app.get("/health/storage")
def health_storage() -> dict:
    ok, detail = storage.health_check()
    return {"status": "ok" if ok else "error", "detail": detail}


@app.get("/health/ready")
def readiness() -> JSONResponse:
    """Readiness: can this instance actually serve? Checks dependencies and
    returns 503 when it cannot. Kept strictly separate from /health (liveness,
    dependency-free by design) — a liveness probe that checks Postgres would
    turn a 30-second Postgres blip into a restart storm.
    """
    checks: dict[str, str] = {}

    db = None
    try:
        db = database.SessionLocal()
        db.execute(sql_text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        # type name only: this endpoint is unauthenticated, and a raw
        # exception message can contain a DSN with credentials in it.
        checks["postgres"] = f"error: {type(e).__name__}"
    finally:
        if db is not None:
            db.close()

    try:
        vector_store.get_client().get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {type(e).__name__}"

    ok, _detail = storage.health_check()
    checks["storage"] = "ok" if ok else "error"

    # Storage is deliberately NOT fatal: chat reads chunk text from Postgres
    # and vectors from Qdrant and never touches a blob. Failing readiness on
    # storage would take chat down for every student because an admin can't
    # upload, which is the wrong trade.
    critical_ok = checks["postgres"] == "ok" and checks["qdrant"] == "ok"
    return JSONResponse(
        status_code=200 if critical_ok else 503,
        content={"status": "ready" if critical_ok else "degraded", "checks": checks},
    )


@app.get("/metrics")
def metrics_endpoint(_org_id: int = Depends(require_search_access)) -> dict:
    # Admin-only: query volume, latency and refusal rate per tenant are
    # operational detail, not something to expose publicly.
    return metrics.snapshot()
