from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CampusBrain AI")

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
