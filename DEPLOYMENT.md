# Deployment: Render (backend) + Vercel (frontend)

The chosen production path. `docker/docker-compose.prod.yml` documents a
self-hosted-VPS alternative if you ever want it instead, but isn't used here.

## Status before you start

Fully wired and ready:
- **Object storage** — Supabase Storage, S3-compatible (`backend/app/infrastructure/storage.py`)
- **Embeddings** — Gemini API (`backend/app/infrastructure/embeddings/`)
- **LLM** — OpenRouter (`backend/app/infrastructure/llm/`)
- **CORS** — configurable via `CORS_ALLOWED_ORIGINS`
- **Frontend → backend calls** — configurable via `VITE_API_BASE_URL`

**Not yet wired — flagging honestly rather than claiming this is fully done:**
- **Neon Postgres** — `backend/app/core/config.py`'s `database_url` builds a
  connection string from discrete fields (`POSTGRES_USER`/`POSTGRES_HOST`/etc.).
  Neon's connection string needs `?sslmode=require&channel_binding=require`
  query params this doesn't produce. Until this is updated, point
  `POSTGRES_HOST` at Neon's pooler hostname and this will likely fail to
  connect (SSL required, not offered). Smallest real fix: add a
  `DATABASE_URL: str | None = None` field to `Settings` that, if set,
  overrides the discrete-field construction — then `DATABASE_URL` can be
  Neon's connection string verbatim. Not done in this pass.
- **Qdrant Cloud** — `backend/app/infrastructure/vector_store.py` constructs
  `QdrantClient(host=..., port=...)` with no `api_key` and no `https=True`.
  Qdrant Cloud requires both. Until updated, this will fail to authenticate
  against a Qdrant Cloud cluster. Fix is small (`QdrantClient(url=settings.qdrant_url,
  api_key=settings.qdrant_api_key)`) but wasn't part of this migration's scope
  (Supabase Storage was) — say the word and I'll do it next.

Everything below assumes those two are resolved first, since the backend
can't actually start against Neon/Qdrant Cloud without them.

## 1. Render — backend

**New Web Service** → connect the GitHub repo.

| Setting | Value |
|---|---|
| Root Directory | `backend` |
| Runtime | Docker (uses `backend/Dockerfile`) |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4` |
| Pre-Deploy Command | `alembic upgrade head` |

Two things that aren't optional:

- **`$PORT`, not a hardcoded `8000`.** Render assigns a port via the `PORT`
  env var and expects the service to bind to it — the Dockerfile's own `CMD`
  hardcodes `--port 8000` and ends in `--reload` (correct for local dev, wrong
  for both reasons in production), which is why the Start Command above
  overrides it rather than relying on the image default.
- **Pre-Deploy Command runs `alembic upgrade head` before each deploy** —
  Render's mechanism for exactly this (not a cron job, not manual). Without
  it, a deploy with a new migration serves against a stale schema.

**Environment variables** (Render dashboard → Environment):

```
POSTGRES_USER=...            # from Neon, once DATABASE_URL support lands (see above)
POSTGRES_PASSWORD=...
POSTGRES_DB=...
POSTGRES_HOST=...
POSTGRES_INTERNAL_PORT=5432

JWT_SECRET_KEY=...           # openssl rand -hex 32 — do not reuse the dev default
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

STORAGE_ENDPOINT=https://<project_ref>.storage.supabase.co/storage/v1/s3
STORAGE_REGION=...
STORAGE_ACCESS_KEY=...
STORAGE_SECRET_KEY=...
STORAGE_BUCKET_NAME=documents

GEMINI_API_KEY=...
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIM=768

OPENROUTER_API_KEY=...
LLM_MODEL=openai/gpt-oss-20b:free

QDRANT_HOST=...              # once Qdrant Cloud support lands (see above)
QDRANT_INTERNAL_PORT=6333

CORS_ALLOWED_ORIGINS=https://your-app.vercel.app   # set after step 2, once you have the real URL
```

Free-tier note carried over from the earlier free-tier analysis: Render's free
web service sleeps after 15 minutes idle (30–60s cold start on the next
request). Fine for low traffic; if that matters, it's a paid-tier toggle, not
a code change.

## 2. Vercel — frontend

**New Project** → import the same repo.

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Framework Preset | Vite |
| Build Command | `npm run build` (default) |
| Output Directory | `dist` (default) |

**Environment variable:**

```
VITE_API_BASE_URL=https://your-backend.onrender.com
```

Without this, `frontend/src/api/client.ts` fetches `/api/v1/...` against
Vercel's own domain (no backend there) and every request 404s — this is the
one frontend change that split-origin deployment requires, and it's now in
place.

## 3. Close the loop

Once both are deployed:
1. Copy the real Vercel URL into Render's `CORS_ALLOWED_ORIGINS`, redeploy the backend.
2. Confirm: `curl https://your-backend.onrender.com/health` → `{"status":"ok"}`.
3. Confirm storage connectivity specifically: `curl https://your-backend.onrender.com/health/storage`
   → `{"status":"ok","detail":"reachable"}`. If it errors, the bucket
   likely isn't created yet — see the Supabase Dashboard steps below.
4. Open the Vercel URL, log in, try a chat and an upload end to end.

## Manual steps in the Supabase Dashboard (not something code can do for you)

1. Storage → **New bucket** → name it `documents` (matches
   `STORAGE_BUCKET_NAME`'s default) → **keep it Private**.
2. Storage → **Settings** (the S3 Connection section) → **New access key** →
   copy the Access Key ID, Secret Access Key, Endpoint, and Region into
   Render's environment variables above.
