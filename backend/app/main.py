from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router

app = FastAPI(title="CampusBrain AI")
app.include_router(auth_router, prefix="/api/v1")

# Dev: allow any origin so the Vite frontend (and Codespaces forwarded URLs)
# can call the API. Locked down to explicit origins in production (M60).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
