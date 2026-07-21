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
| redis    | 6379        | Cache / job queue      |
| minio    | 9000 / 9001 | Object storage / console |
| qdrant   | 6333        | Vector DB              |
| ollama   | 11434       | Local LLM runtime      |

No app code uses redis/minio/qdrant/ollama yet — they're wired in at M5 purely to prove the full stack boots; each gets real code in its own later phase.
