# Docker

Run the stack from the **repo root** with the root `.env`:

```
cp .env.example .env
docker compose -f docker/docker-compose.yml --env-file .env up -d --build
```

`--env-file .env` is required: Compose only auto-loads a `.env` next to the compose file (`docker/`), but ours lives at the repo root so it isn't committed as a secret.

## Services & ports

| Service  | Port | Purpose            |
|----------|------|--------------------|
| postgres | 5432 | Relational DB      |
| backend  | 8000 | FastAPI (`/health`)|
