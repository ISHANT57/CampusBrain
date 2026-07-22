# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.ask import router as ask_router
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
app.include_router(ask_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")

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
