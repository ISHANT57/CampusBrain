from fastapi import FastAPI

app = FastAPI(title="CampusBrain AI")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
