# Operations Runbook — every command to check, verify, and access CampusBrain

One file, copy-paste-able. Organized by "what do I want to do", not by
architecture layer. Companion to `DEPLOYMENT.md` (how to deploy) and
`ENGINEERING_ROADMAP.md` (why things are built the way they are — every ADR
referenced below lives there).

Set this once per terminal session and every command below just works:

```bash
# Local Docker Compose (this repo's dev stack)
export BASE_URL=http://localhost:8000

# OR a GitHub Codespace / forwarded port — copy the forwarded 8000 URL from
# the Ports tab (must be set to Public, or requests hit the Codespaces auth
# gate — see "Codespace port visibility" in Troubleshooting)
export BASE_URL=https://<your-codespace>-8000.app.github.dev

# OR the deployed backend (Render). Frontend lives at
# https://campus-brain-inky.vercel.app/<org-slug>
export BASE_URL=https://campusbrain.onrender.com
```

⚠️ **Against the deployed backend, read the cautions first:** this is real
tenant data and there is **no delete endpoint**, so don't upload throwaway test
files. Rate limits apply per IP (login 5/min, upload 10/min, search 60/min,
chat 120/min) — don't loop these in a script. And on Render's free tier the
first request after ~15 minutes idle wakes the instance, so expect 30–60s
before anything responds.

---

## Table of contents

1. [Bring the stack up](#1-bring-the-stack-up)
2. [Migrations](#2-migrations)
3. [Run the tests](#3-run-the-tests)
4. [Health & readiness](#4-health--readiness)
5. [Get an admin token (needed for most calls below)](#5-get-an-admin-token)
6. [Chat](#6-chat)
7. [Search](#7-search)
8. [Documents](#8-documents)
9. [Audit logs](#9-audit-logs)
10. [Cost / token usage](#10-cost--token-usage)
11. [Evaluation stats](#11-evaluation-stats)
12. [Metrics (RED signals)](#12-metrics-red-signals)
13. [Ingestion worker / job queue](#13-ingestion-worker--job-queue)
14. [Reading the structured logs](#14-reading-the-structured-logs)
15. [Direct database queries](#15-direct-database-queries)
16. [Frontend](#16-frontend)
17. [CI](#17-ci)
18. [Troubleshooting — problems actually hit, and the fix](#18-troubleshooting--problems-actually-hit-and-the-fix)

---

## 1. Bring the stack up

```bash
docker compose -f docker/docker-compose.yml up -d --build
docker compose -f docker/docker-compose.yml ps                    # confirm all healthy/running
docker compose -f docker/docker-compose.yml logs backend --tail=50 -f   # watch it boot
```

Look for `"ingestion worker loop started"` in the backend log — that's the
Phase 1 durable-queue worker (an `asyncio` task in the same process, not a
separate Render service; see ADR-012) confirming it's polling.

Stop everything:
```bash
docker compose -f docker/docker-compose.yml down
```

---

## 2. Migrations

```bash
docker compose -f docker/docker-compose.yml exec backend alembic upgrade head
docker compose -f docker/docker-compose.yml exec backend alembic current   # confirm the head revision
docker compose -f docker/docker-compose.yml exec backend alembic history   # full chain
```

`render-start.sh` already runs `alembic upgrade head` on every boot in
production — you only need this by hand locally, or right after a `git pull`
that added a migration.

---

## 3. Run the tests

```bash
# Everything (unit + integration; needs the stack up from step 1)
docker compose -f docker/docker-compose.yml exec backend pytest

# Just the fast tier (no real Postgres/Qdrant/storage needed — same set CI runs)
docker compose -f docker/docker-compose.yml exec backend pytest \
  tests/test_cache.py tests/test_retry.py tests/test_gemini_provider.py \
  tests/test_gemini_streaming.py tests/test_rag_citations.py tests/test_rag_streaming.py \
  tests/test_chat_org_routing.py tests/test_chat_stream_sse.py tests/test_audit_service.py \
  tests/test_ingestion_queue.py tests/test_document_processing_idempotency.py \
  tests/test_usage_service.py tests/test_service_api_key.py tests/test_redis_usage_boundary.py \
  tests/test_eval_service.py

# One file
docker compose -f docker/docker-compose.yml exec backend pytest tests/test_security.py -v

# Lint (same rule set as CI — see backend/ruff.toml for what's deliberately excluded and why)
docker compose -f docker/docker-compose.yml exec backend ruff check .
```

---

## 4. Health & readiness

Three distinct endpoints, three distinct purposes (ADR-002) — don't conflate them:

```bash
# Liveness — dependency-free on purpose. "Is the process alive at all."
curl -s $BASE_URL/health | jq
# {"status": "ok"}

# Storage connectivity only
curl -s $BASE_URL/health/storage | jq

# Readiness — Postgres + Qdrant are FATAL (503 if either is down);
# storage is reported but NOT fatal (chat never reads a blob — ADR-002).
curl -s $BASE_URL/health/ready | jq
# {"status": "ready", "checks": {"postgres": "ok", "qdrant": "ok", "storage": "ok"}}
```

If `/health/ready` ever returns `503`, read `checks` to see which dependency
failed — error values are exception *type names* only (never a raw message,
which could leak a DSN with credentials — this endpoint is unauthenticated).

---

## 5. Get an admin token

Needed for every endpoint in sections 7–12. There's no self-registration
endpoint (students never authenticate) — an admin account is created via
`backend/scripts/create_admin.py` or the `ADMIN_EMAIL` env var on first boot.

```bash
curl -s -X POST $BASE_URL/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"org_id": 1, "email": "admin@example.com", "password": "your-password"}' | jq

# Save the token for reuse in every command below:
export TOKEN=$(curl -s -X POST $BASE_URL/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"org_id": 1, "email": "admin@example.com", "password": "your-password"}' \
  | jq -r .access_token)

echo $TOKEN   # sanity check it's non-empty
```

Who am I:
```bash
curl -s $BASE_URL/api/v1/auth/me -H "Authorization: Bearer $TOKEN" | jq
```

Rate limit: 5/minute (brute-force defense, not audited on failure — see ADR-014).

---

## 6. Chat

Public, anonymous, no token needed. `sitare` is the default seeded org slug
(swap for whatever org you've created).

**Blocking:**
```bash
curl -s -X POST $BASE_URL/api/v1/chat/sitare \
  -H "Content-Type: application/json" \
  -d '{"question": "What does the full scholarship cover?", "history": [], "top_k": 5}' | jq
```

**Streaming (SSE)** — watch the tokens arrive incrementally with `-N` (disables curl's output buffering):
```bash
curl -N -X POST $BASE_URL/api/v1/chat/stream/sitare \
  -H "Content-Type: application/json" \
  -d '{"question": "What does the full scholarship cover?"}'
```
Event order on the wire:

1. One `data: {"type": "retrieved", "documents": [...]}` as soon as retrieval
   returns, before generation starts. These are documents **searched**, not
   sources cited — the model may cite none of them, so they carry no excerpt
   text. Absent entirely on a refusal, where nothing cleared the relevance
   floor and there is no honest list to show.
2. Many `data: {"type": "delta", "text": ...}` lines, carrying the model's raw
   output with **un-renumbered** `[n]` markers (renumbering needs the whole
   answer, so it can't happen incrementally).
3. Exactly one `data: {"type": "done", "answer": ..., "citations": [...],
   "grounding": {...}}` with the final renumbered text, the citations matching
   those numbers, and the measured basis for the answer.

`grounding` reports `best_semantic_score` alongside the `relevance_threshold`
it was compared against, plus `retrieved_chunks` / `cited_chunks` /
`cited_documents`. There is deliberately **no** high/medium/low confidence
field — see ADR-017 for why a bucketed label would be a fabrication.

A client that ignores every delta and reads only `done` gets a result identical
to the blocking endpoint: streaming changes the transport, not the contract.

With conversation history (mirrors what the frontend sends):
```bash
curl -s -X POST $BASE_URL/api/v1/chat/sitare \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What about after that?",
    "history": [
      {"role": "user", "content": "Tell me about the curriculum"},
      {"role": "assistant", "content": "The curriculum spans four years..."}
    ]
  }' | jq
```

Rate limit: 120/minute, per IP (deliberately loose — a whole campus can sit
behind one NAT).

---

## 7. Search

Raw retrieval (semantic/keyword/hybrid), not a grounded answer — a knowledge-base
inspection tool. Needs EITHER an admin JWT or a service `X-API-Key`.

```bash
curl -s -X POST $BASE_URL/api/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "scholarship", "mode": "hybrid", "top_k": 5}' | jq

# mode: "semantic" | "keyword" | "hybrid" (default)
```

With a service API key instead (if `SERVICE_API_KEY` is configured):
```bash
curl -s -X POST $BASE_URL/api/v1/search \
  -H "X-API-Key: $SERVICE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "scholarship", "mode": "keyword"}' | jq
```

Every call here is audited (ADR-014) — see section 9 to confirm a row landed.
Rate limit: 60/minute.

---

## 8. Documents

All admin-only (`Authorization: Bearer $TOKEN`).

**Upload** (returns `202 Accepted` — durable ingestion job enqueued, not
processed synchronously; see ADR-012):
```bash
curl -s -X POST $BASE_URL/api/v1/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/your/file.pdf" | jq

# Save the id to poll its status:
export DOC_ID=$(curl -s -X POST $BASE_URL/api/v1/documents \
  -H "Authorization: Bearer $TOKEN" -F "file=@/path/to/your/file.pdf" | jq -r .id)
```

**Poll ingestion status** (`pending` → `processing` → `processed`/`failed`):
```bash
curl -s $BASE_URL/api/v1/documents/$DOC_ID -H "Authorization: Bearer $TOKEN" | jq '.status'
```

**List** (paginated, filterable):
```bash
curl -s "$BASE_URL/api/v1/documents?limit=20&offset=0" -H "Authorization: Bearer $TOKEN" | jq
curl -s "$BASE_URL/api/v1/documents?status=processed" -H "Authorization: Bearer $TOKEN" | jq
```

**Full extracted text** (page-by-page, optionally ranged):
```bash
curl -s $BASE_URL/api/v1/documents/$DOC_ID/text -H "Authorization: Bearer $TOKEN" | jq
curl -s "$BASE_URL/api/v1/documents/$DOC_ID/text?page_from=1&page_to=3" -H "Authorization: Bearer $TOKEN" | jq
```

**Signed download URL** (Phase 9 — 15-minute expiry, audited):
```bash
curl -s $BASE_URL/api/v1/documents/$DOC_ID/download -H "Authorization: Bearer $TOKEN" | jq
# {"url": "https://...supabase.co/...&X-Amz-Signature=...", "expires_in": 900}

# Actually download it:
curl -s "$(curl -s $BASE_URL/api/v1/documents/$DOC_ID/download -H "Authorization: Bearer $TOKEN" | jq -r .url)" -o downloaded_file.pdf
```

Upload rate limit: 10/minute.

---

## 9. Audit logs

Who did what, when (Phase 8: upload, login, search, download — see ADR-014
for what's deliberately NOT covered, e.g. anonymous chat).

```bash
curl -s "$BASE_URL/api/v1/audit-logs?limit=20" -H "Authorization: Bearer $TOKEN" | jq

# Most-recent-first by default. Look at the "action" field:
#   document.upload | document.download | user.login | search.query
curl -s "$BASE_URL/api/v1/audit-logs?limit=50" -H "Authorization: Bearer $TOKEN" \
  | jq '.logs[] | {action, user_id, resource_type, created_at}'
```

---

## 10. Cost / token usage

Real Gemini `usageMetadata`, captured on every chat generation and every
ingestion embedding call (Phase 3, ADR-013). Cost is estimated at *read*
time from a pricing table that's correctly `$0` on the free tier — see the
`note` field if it looks like nothing is priced.

```bash
curl -s "$BASE_URL/api/v1/usage/summary?days=30" -H "Authorization: Bearer $TOKEN" | jq
```

Returns: `total_tokens`, `prompt_tokens`, `completion_tokens`,
`estimated_cost_usd`, `daily_tokens` (time series), `top_users`,
`top_documents`.

---

## 11. Evaluation stats

Label-free quality signals only — **no** recall/precision/groundedness (Phase
4, ADR-016: those need a golden set that doesn't exist yet; this endpoint
will not fabricate them).

```bash
curl -s "$BASE_URL/api/v1/evaluation/stats?days=30" -H "Authorization: Bearer $TOKEN" | jq
```

Returns: `total_traces`, `refusal_rate`, `uncited_answer_rate`,
`avg_best_semantic_score`, `scored_metrics_available: false`, and a `note`
explaining why.

---

## 12. Metrics (RED signals)

In-process counters (Pillar 2) — resets on restart, not a monitoring system,
a live operational view. Same auth as `/search` (admin JWT or service key).

```bash
curl -s $BASE_URL/metrics -H "Authorization: Bearer $TOKEN" | jq
```

Returns: request counters, `rates` (refusal_rate, zero_keyword_hit_rate,
mean_citations), `latency_ms` (p50/p95/p99 for retrieval/llm/llm_ttft).

---

## 13. Ingestion worker / job queue

The durable queue is Postgres-backed (ADR-012) — inspect it directly rather
than guessing from logs:

```bash
docker compose -f docker/docker-compose.yml exec postgres \
  psql -U campusbrain -d campusbrain -c \
  "SELECT id, document_id, status, attempts, last_error, claimed_at, next_attempt_at
   FROM ingestion_jobs ORDER BY id DESC LIMIT 10;"
```

A job stuck at `processing` with an old `claimed_at` will self-heal within
`LEASE_TIMEOUT_SECONDS` (15 min) via the reaper — no manual intervention
needed. To force-check the worker is actually looping:

```bash
docker compose -f docker/docker-compose.yml logs backend | grep "ingestion_job"
```

---

## 14. Reading the structured logs

Every log line is one JSON object (Pillar 2) with a `request_id` that ties
a chat answer, its cost row, and its eval trace together.

```bash
# Tail everything, pretty-printed
docker compose -f docker/docker-compose.yml logs backend -f --tail=100 \
  | grep -oE '\{.*\}' | jq .

# Just the RAG answer events (question, retrieved chunks, tokens, timings)
docker compose -f docker/docker-compose.yml logs backend \
  | grep '"event":"rag_answer"' | grep -oE '\{.*\}' | jq .

# Follow one request end-to-end by its X-Request-Id (returned in every response header)
docker compose -f docker/docker-compose.yml logs backend | grep '"request_id":"<paste-id-here>"'

# Refusal rate today, computed from logs directly (works even without hitting /metrics)
docker compose -f docker/docker-compose.yml logs backend \
  | grep '"event":"rag_answer"' | grep -oE '\{.*\}' \
  | jq -s 'map(.refused) | (map(select(.)) | length) / length'
```

---

## 15. Direct database queries

For anything the API doesn't surface yet:

```bash
docker compose -f docker/docker-compose.yml exec postgres psql -U campusbrain -d campusbrain
```

Then, inside `psql`:
```sql
\dt                                  -- list every table
SELECT * FROM organizations;
SELECT id, email, role, org_id FROM users;
SELECT id, filename, status, content_hash FROM documents ORDER BY id DESC LIMIT 10;
SELECT id, org_id, status, attempts FROM ingestion_jobs ORDER BY id DESC LIMIT 10;
SELECT action, user_id, resource_type, created_at FROM audit_logs ORDER BY id DESC LIMIT 20;
SELECT model, SUM(total_tokens), SUM(prompt_tokens), SUM(completion_tokens)
  FROM usage_logs GROUP BY model;
SELECT question, refused, best_semantic_score, retrieval_ms, llm_ms
  FROM eval_traces ORDER BY id DESC LIMIT 10;
```

---

## 16. Frontend

```bash
cd frontend
npm install
npm run dev              # Vite dev server, http://localhost:5173
npm run build             # tsc + production build (same as CI's frontend job)
npm run preview           # serve the production build locally
```

Point it at a non-default backend:
```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

---

## 17. CI

`.github/workflows/ci.yml` runs on every PR and push to `main` (ADR-016):
backend lint (`ruff check`) + migrations-from-empty + the fast test tier
against a real Postgres service container, and frontend `tsc && vite build`.

Run the exact same checks locally before pushing:
```bash
cd backend && ruff check .
cd frontend && npm run build
```

---

## 18. Troubleshooting — problems actually hit, and the fix

**`docker compose exec backend pytest` → "no configuration file provided: not found"**
Every `docker compose` command needs `-f docker/docker-compose.yml` explicitly
— without it, Compose looks for a compose file in the repo root and finds none.

**`docker compose exec backend pytest` → `ModuleNotFoundError: No module named 'app'`**
Fixed as of this repo's `backend/pytest.ini` (`pythonpath = .`). If you still
see this, you're on a commit from before that fix — `git pull`.

**`git checkout <branch>` → "untracked working tree files would be overwritten"**
An untracked file on disk collides with one the target branch tracks. Move it
aside first: `mv <file> /tmp/<file>.bak`, then retry the checkout.

**Browser shows a CORS error on `/manifest.webmanifest` in a Codespace**
Not a real CORS bug — the forwarded port is set to **Private**, so the
manifest fetch (sent without your GitHub auth cookie) hits the Codespaces
sign-in gate, and the redirect to a different origin looks like a CORS
failure. Fix: Ports tab → right-click the port → Port Visibility → **Public**.
Doesn't block chat/streaming, which work regardless.

**A pytest run seems to hang forever with no output**
Almost always a module that imports `app.main` (which makes a real boto3 call
to object storage at import time) or `app.infrastructure.vector_store`
(connects to Qdrant at import) running with no reachable backend configured.
These files are integration-tier — they need the real stack from section 1,
or dummy env vars if you're just checking syntax:
```bash
export JWT_SECRET_KEY=test STORAGE_ENDPOINT=http://localhost:9000 \
       STORAGE_REGION=us-east-1 STORAGE_ACCESS_KEY=test STORAGE_SECRET_KEY=test
```

**A `git push` appears to succeed but the branch didn't update on GitHub**
Silent timeout is possible on a slow connection. Always verify:
```bash
git log origin/<branch>..HEAD --oneline   # empty output = fully pushed
```
If it lists commits, just retry the push.

**`/health/ready` returns 503**
Check the `checks` object in the response — it names which dependency
(`postgres` or `qdrant`) is down by exception type. `storage` failing alone
does NOT cause a 503 (by design — chat never reads a blob).
