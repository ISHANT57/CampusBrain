import logging

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Request
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.documents import router as documents_router
from app.api.v1.search import router as search_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.infrastructure import storage

app = FastAPI(title="CampusBrain AI")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")


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
