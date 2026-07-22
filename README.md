# CampusBrain AI

Multi-tenant RAG platform that lets institutions upload documents and get natural-language, **cited** answers over them. First customer: Sitare University. Domain-agnostic by design.

Planning docs: [PRD](prd.md) · [Architecture](Articheture.md) · [Roadmap](Roadmap.md) · [Development Strategy](DEVELOPMENT_STRATEGY.md)

## Status

Working MVP. Upload a document → it is extracted (with OCR for scans), chunked, embedded and indexed in the background → ask questions in the browser and get answers that cite the exact document and page.

**Built:** multi-format ingestion (PDF/DOCX/PPTX/XLSX/CSV/MD/TXT/images), background processing, BGE-M3 embeddings, per-organization Qdrant collections, hybrid retrieval (semantic + BM25 fused with RRF), citation-enforced answers with a no-evidence refusal, JWT auth with role-based access, per-user rate limiting, durable multi-turn chat, and a React UI.

**Not built yet:** reranking (dropped deliberately — see the decision record in `DEVELOPMENT_STRATEGY.md`), streaming responses, admin/analytics panels, malware scanning, evaluation harness, production deployment.

## Running it

Requires Docker. Everything runs from one Compose file.

```bash
cp .env.example .env          # then set OPENROUTER_API_KEY (see below)
docker compose -f docker/docker-compose.yml --env-file .env up -d --build
```

Then open **http://localhost:5173**.

| Service | URL | Notes |
| --- | --- | --- |
| Frontend | http://localhost:5173 | the app |
| API docs | http://localhost:8000/docs | interactive Swagger UI |
| MinIO console | http://localhost:9001 | browse uploaded files |
| Qdrant | http://localhost:6333/dashboard | inspect vectors |

**Required config:** `OPENROUTER_API_KEY` in `.env` — get one at https://openrouter.ai/keys. `LLM_MODEL` defaults to a free-tier model; free tiers throttle, so an occasional request may need a retry. Everything else in `.env.example` has working dev defaults.

### First run

There are no users until you make one. Register at `/register` — public self-registration always creates a **Student** (Students can ask questions but not upload). To create a Faculty/Admin account, insert one directly:

```bash
docker compose -f docker/docker-compose.yml --env-file .env exec backend python -c "
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole
db = SessionLocal()
db.add(User(org_id=1, email='admin@yourcollege.edu',
            hashed_password=hash_password('changeme'), role=UserRole.ADMIN))
db.commit()"
```

An organization with `id=1` must exist first; `app/services/org_service.py::create_organization` creates one *and* provisions its Qdrant collection.

### Running on GitHub Codespaces

Same command, with two Codespaces-specific gotchas:

1. Containers do **not** restart automatically when a Codespace resumes — re-run the `up -d` command above.
2. Forwarded ports revert to **private** on restart, which makes them return 404 in the browser. Set ports 5173 and 8000 to *Public* in the **Ports** tab (or `gh codespace ports visibility 5173:public 8000:public -c <codespace-name>`).

## Tests

```bash
docker compose -f docker/docker-compose.yml --env-file .env exec backend python -m pytest tests/ -v
```

`backend/tests/test_security.py` covers the security regressions found during development (privilege escalation, path traversal, 401-vs-403, and cross-user chat access), plus RBAC and file-type validation. Each test names the attack it prevents.

## Structure

```
backend/    FastAPI app — api/ services/ repositories/ models/ infrastructure/ workers/
frontend/   React + TypeScript (Vite)
docker/     Compose file and service config
resources/  Sample corpus used for testing retrieval
```

Database migrations are Alembic (`backend/alembic/`) and run automatically as part of the
documented setup only if you invoke them — after a schema change run:

```bash
docker compose -f docker/docker-compose.yml --env-file .env exec backend alembic upgrade head
```
