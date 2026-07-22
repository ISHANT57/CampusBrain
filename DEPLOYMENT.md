# Deployment: Render (backend) + Vercel (frontend)

The chosen production path. `docker/docker-compose.prod.yml` documents a
self-hosted-VPS alternative if you ever want it instead, but isn't used here.

## Status before you start

Fully wired and ready:
- **Object storage** — Supabase Storage, S3-compatible (`backend/app/infrastructure/storage.py`)
- **Embeddings** — Gemini API (`backend/app/infrastructure/embeddings/`)
- **LLM** — OpenRouter (`backend/app/infrastructure/llm/`)
- **Database** — Neon, via `DATABASE_URL` (`backend/app/core/config.py`'s
  `database_url` property prefers this over the discrete `POSTGRES_*` fields
  when set — verified: Neon's connection string works with SQLAlchemy's
  default `postgresql://` dialect resolution, no `+psycopg2` suffix needed)
- **Vector database** — Qdrant Cloud, via `QDRANT_URL` + `QDRANT_API_KEY`
  (`backend/app/infrastructure/vector_store.py` — verified against
  qdrant-client's own docs for the Cloud connection pattern)
- **CORS** — configurable via `CORS_ALLOWED_ORIGINS`
- **Frontend → backend calls** — configurable via `VITE_API_BASE_URL`

All five external services this app depends on are now configurable purely
through environment variables, with no code path assuming self-hosted
infrastructure is the only option.

## 1. Render — backend

**New Web Service** → connect the GitHub repo.

| Setting | Value |
|---|---|
| Root Directory | `backend` |
| Runtime | Docker (uses `backend/Dockerfile`) |
| Docker Command *(Settings → Advanced, NOT "Start Command" — that field is for native-runtime services and does nothing for a Docker-runtime one)* | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4` |
| Pre-Deploy Command | `alembic upgrade head` |

Two things that aren't optional:

- **`$PORT`, not a hardcoded `8000`.** Render assigns a port via the `PORT`
  env var and expects the service to bind to it — the Dockerfile's own `CMD`
  hardcodes `--port 8000` and ends in `--reload` (correct for local dev, wrong
  for both reasons in production), which is why the Docker Command above
  overrides it rather than relying on the image default. If you leave this
  field blank, Render silently runs the Dockerfile's dev `CMD` instead — it
  won't error, it'll just quietly serve the wrong thing, exactly as happened
  on the first deploy.
- **Pre-Deploy Command runs `alembic upgrade head` before each deploy** —
  Render's mechanism for exactly this (not a cron job, not manual). Without
  it, a deploy with a new migration serves against a stale schema.

**Environment variables** (Render dashboard → Environment):

```
DATABASE_URL=...              # Neon's connection string, verbatim (includes ?sslmode=require&channel_binding=require)

JWT_SECRET_KEY=...            # openssl rand -hex 32 — do not reuse the dev default
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

QDRANT_URL=...                # e.g. https://xxxx.aws.cloud.qdrant.io
QDRANT_API_KEY=...

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
