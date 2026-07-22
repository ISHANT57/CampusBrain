# Docker

Run the stack from the **repo root** with the root `.env`:

```
cp .env.example .env
docker compose -f docker/docker-compose.yml --env-file .env up -d --build
```

`--env-file .env` is required: Compose only auto-loads a `.env` next to the compose file (`docker/`), but ours lives at the repo root so it isn't committed as a secret.

## Services & ports

| Service  | Port        | Purpose               |
|----------|-------------|------------------------|
| postgres | 5432        | Relational DB          |
| backend  | 8000        | FastAPI (`/health`)    |
| frontend | 5173        | Vite dev server        |
| qdrant   | 6333        | Vector DB              |

Object storage has no local dev container either — dev uses Supabase Storage
the same as production, via `STORAGE_*` in `.env` (see `.env.example`).
Everything is free-tier: a Supabase project costs nothing to create.

No separate worker or cache service: document processing runs as a FastAPI
`BackgroundTask` inside `backend` (see `backend/app/services/document_processing_service.py`),
and the LLM (OpenRouter) and embeddings (Gemini, see `backend/MIGRATION.md`) are
both hosted APIs rather than self-hosted arq/Redis/Ollama. This is a deliberate
change from the original M5 stack, made so the whole thing fits Render's free
tier — see `backend/MIGRATION.md` for the full reasoning and what to check if
you're diagnosing something that behaves differently than before.

---

# Production deployment — self-hosted VPS alternative (M60 / M61)

**This is not the chosen deployment path.** The actual target is Render
(backend) + Vercel (frontend) — see `DEPLOYMENT.md` at the repo root for that.
This section documents `docker-compose.prod.yml` as a documented alternative
if you'd rather run everything on your own VPS instead.

What differs from the dev file, and why:

- **No bind mounts.** Code is baked into images, so the thing you tested is the
  thing that runs.
- **Only nginx publishes ports.** Postgres and Qdrant sit on the internal
  Docker network and are unreachable from the internet. In dev they're both
  exposed on the host, which would be a serious hole in production. (Object
  storage is Supabase, not a container, in both dev and prod — see
  `backend/MIGRATION.md`.)
- **`uvicorn` without `--reload`**, with 4 workers. The dev image's `CMD` ends
  in `--reload`; the prod Compose file overrides it.
- **Migrations are gated.** A one-shot `migrate` service runs
  `alembic upgrade head` and must exit cleanly before backend/worker start, so
  the API never serves against an unmigrated schema.
- **Nginx replaces the Vite dev proxy.** In dev, `vite.config.ts` proxies
  `/api` to the backend. That proxy does not exist in a production build — nginx
  takes over both serving the SPA and routing `/api/*`.

## First deploy

On a fresh VM with Docker installed (~2–4 GB RAM is enough — the LLM is
OpenRouter and embeddings are Gemini, both hosted APIs; no Ollama, no GPU):

```bash
git clone https://github.com/ISHANT57/CampusBrain.git
cd CampusBrain

cp .env.production.example .env.production
# Fill in every blank. Generate real secrets:
#   openssl rand -base64 32   # POSTGRES_PASSWORD
#   openssl rand -hex 32      # JWT_SECRET_KEY
# plus your OpenRouter key, Gemini key, and Supabase Storage S3 credentials
# (endpoint/region/access key/secret — see the STORAGE_* section in the file).
nano .env.production

cd docker
docker compose -f docker-compose.prod.yml --env-file ../.env.production up -d --build
```

Verify:

```bash
curl -f http://localhost/health          # {"status":"ok"} — proxied to the backend
curl -fI http://localhost/               # 200, serves the SPA
docker compose -f docker-compose.prod.yml ps   # all Up; migrate shows Exited (0)
```

The app is now on port 80.

## Enabling HTTPS

Requires a domain whose DNS A record points at the server. Then:

1. Issue a certificate:
   ```bash
   docker run --rm -p 80:80 \
     -v /etc/letsencrypt:/etc/letsencrypt \
     certbot/certbot certonly --standalone -d your-domain.example
   ```
   (stop the `web` service first so port 80 is free)
2. Uncomment the TLS `server` block in `nginx/nginx.conf` and set
   `server_name` / cert paths to your domain.
3. Uncomment the `443:443` port and the `certbot_certs` volume on the `web`
   service in `docker-compose.prod.yml`, and add the volume to the top-level
   `volumes:` list.
4. Turn the `:80` block into a redirect (snippet is in `nginx.conf`).
5. `docker compose -f docker-compose.prod.yml up -d --build web`

## Still open before calling this production-ready

- **CORS** — resolved. `backend/app/main.py` reads `CORS_ALLOWED_ORIGINS`
  (comma-separated) instead of a hardcoded `["*"]`; set it to your real
  frontend origin(s) in `.env.production`.
- **Backups** — no Postgres dump schedule yet (roadmap M64).
- **CI/CD** — images are built on the server here; M62–M63 move that to
  GitHub Actions.
- **.doc/.ppt/.xls uploads** — need LibreOffice in `backend/Dockerfile` (added,
  not build-verified — see the comment there and `backend/MIGRATION.md`).
