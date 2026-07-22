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
| Docker Command *(Settings → Advanced, NOT "Start Command" — that field is for native-runtime services and does nothing for a Docker-runtime one)* | `sh scripts/render-start.sh` |

**Pre-Deploy Command would be the clean way to run migrations, but it's a
paid-plan feature — confirmed unavailable on Render's free tier.** A first
attempt at a free-tier equivalent — chaining `sh -c "alembic upgrade head &&
uvicorn ..."` directly in the Docker Command field — failed in practice:
Render didn't pass that string through a real shell, and the whole thing got
tokenized as one literal (unfindable) command
(`sh: 1: alembic upgrade head && uvicorn ...: not found`). `backend/scripts/render-start.sh`
(checked into the repo, copied into the image by the Dockerfile's `COPY . .`)
holds the actual `alembic upgrade head && exec uvicorn ...` logic instead, so
the Docker Command field only has to hold something too simple to
mis-parse. `alembic upgrade head` is idempotent (a no-op check if nothing's
changed), so running it on every boot rather than only before a deploy costs
nothing, and the script exits on migration failure before ever starting
uvicorn (`set -e`).

Two things that aren't optional:

- **`$PORT`, not a hardcoded `8000`.** Render assigns a port via the `PORT`
  env var and expects the service to bind to it — the Dockerfile's own `CMD`
  hardcodes `--port 8000` and ends in `--reload` (correct for local dev, wrong
  for both reasons in production), which is why the Docker Command above
  overrides it rather than relying on the image default. If you leave this
  field blank, Render silently runs the Dockerfile's dev `CMD` instead — it
  won't error, it'll just quietly serve the wrong thing, exactly as happened
  on the first deploy.
- **Don't rely on Render's Shell tab as a one-off migration workaround** —
  SSH/shell access also appears to be paid-tier only. The Docker Command
  chain above is the actual free-tier path, not a manual per-deploy step.

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

**`frontend/vercel.json` (already added) — required for client-side routing.**
Vercel's own docs are explicit that a Vite SPA's deep links ("won't work out
of the box") without this: visiting `/login` or `/chat` directly (or
refreshing on one) has no matching physical file in the build output, so
Vercel's static host 404s instead of falling back to `index.html`, where
React Router would actually handle the route. The file:
```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```
No dashboard setting for this — it has to be a committed file, which is why
it's already in the repo rather than something to configure per-deploy.

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
