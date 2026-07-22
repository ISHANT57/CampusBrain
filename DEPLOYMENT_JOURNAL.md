# CampusBrain — Build & Deployment Journal

A record of what was planned, what was built, everything that broke on the way
to production, and every privacy issue found — each with its root cause and
the fix that was actually applied.

Written as a factual log rather than a tidy narrative: the failures are the
useful part, and several of them were caused by decisions that looked correct
at the time.

---

## 1. What the system is

A retrieval-augmented (RAG) chatbot over a university's own documents.
Students ask questions in plain language; answers are generated only from the
uploaded corpus and carry numbered citations back to the source document and
page. If the corpus does not answer the question, the bot refuses instead of
guessing.

**Final production topology**

| Concern | Service |
|---|---|
| Frontend | Vercel (static Vite/React build) |
| Backend API | Render (Docker, free tier) |
| Relational DB | Neon PostgreSQL |
| Vector DB | Qdrant Cloud |
| Object storage | Supabase Storage (S3-compatible) |
| Embeddings | Gemini `gemini-embedding-001` (768-dim) |
| LLM | OpenRouter (`openai/gpt-oss-20b:free`) |

---

## 2. What was planned and built before deployment

Development ran as ~60 numbered milestones (`Roadmap.md`), each with a
definition of done. The pre-deployment build, in dependency order:

1. **Infrastructure skeleton** — docker-compose (Postgres), FastAPI skeleton,
   Vite/React frontend calling `/health`.
2. **Data model** — Organization → User → Collection → Document → Chunk, all
   org-scoped, with Alembic migrations.
3. **Auth & tenancy** — JWT auth, role-based access (Student/Faculty/Admin/
   Super Admin), and an `OrgScopedRepository` base class so every query is
   filtered by `org_id` at one control point rather than relying on each
   future query to remember.
4. **Ingestion pipeline** — upload → validate → store → extract → clean →
   chunk → embed → index:
   - PyMuPDF for PDF text, PaddleOCR fallback for pages whose text layer is
     under 20 characters (i.e. scanned pages only)
   - `unstructured` for DOCX/PPTX/XLSX/CSV/MD/TXT
   - recursive chunking via `langchain-text-splitters`
   - per-organization Qdrant collections (tenant isolation is structural: one
     org's search cannot reach another's vectors because they are in separate
     collections, not merely filtered)
5. **Retrieval** — hybrid search: semantic (vector) + keyword (Postgres
   full-text) fused with Reciprocal Rank Fusion.
6. **Answering** — RAG prompt instructing inline `[n]` citations, a
   no-evidence guardrail, and context sanitization against prompt injection.
7. **Frontend** — auth pages, protected routes, upload UI with status polling,
   chat UI with citations.

### Security work done during the build (before deployment)

Four vulnerabilities were found and fixed during development, each with a
regression test so a future change re-breaking them fails in CI rather than in
production (`backend/tests/test_security.py`):

| # | Vulnerability | Fix |
|---|---|---|
| 1 | **Privilege escalation** — public registration accepted a client-supplied `role`, so anyone could self-register as Super Admin | Role forced server-side; client value ignored |
| 2 | **Path traversal** — the client filename was spliced into the object-storage key, so `../../` escaped the org prefix | Storage key built from `org_id` + UUID; the real filename is stored only in the DB column, never used for addressing |
| 3 | **401 vs 403 confusion** — a missing auth header returned 403, conflating "not authenticated" with "authenticated but not allowed" | `auto_error=False`, correct 401 |
| 4 | **IDOR** — org scoping alone let any user in the same organization read another user's private conversation by guessing its id | Ownership check (`get_for_user`), not just org check |

Two further hardening measures were built in rather than retrofitted:

- **Prompt-injection sanitization** — retrieved chunk text is sanitized before
  entering the prompt, so a malicious uploaded document cannot issue
  instructions to the model.
- **No-evidence guardrail** — if the best semantic similarity is below a
  threshold, the bot refuses rather than answering ungrounded. Deliberately
  thresholds on the *semantic* score, not the fused RRF score, because RRF
  scores are on a different scale (~0.03) and thresholding on them would
  refuse everything.

---

## 3. The pre-deployment architecture migration

The development stack could not run on free-tier hosting. Three components had
to go, and each removal was a deliberate trade rather than a simplification.

### 3.1 Ollama (self-hosted embeddings) → Gemini API

**Problem.** Embeddings were served by a local Ollama container running BGE-M3.
Render's free tier has 512 MB RAM and no persistent disk — it cannot host a
local embedding model.

**Solution.** Introduced an `EmbeddingProvider` Protocol
(`app/infrastructure/embeddings/`) mirroring the existing `LLMProvider`
pattern, with `GeminiEmbeddingProvider` as the first implementation. Every
caller goes through a single `get_embedding_provider()` factory, so adding
OpenAI / Voyage / Jina / Ollama later means writing one class and changing one
line — the RAG pipeline never imports a concrete provider.

**Consequence recorded, not hidden.** The `RELEVANCE_THRESHOLD = 0.35`
no-evidence guardrail was calibrated against BGE-M3's cosine-similarity
distribution. A different embedding model can produce a different
distribution, so this threshold may need recalibrating. Documented in
`backend/MIGRATION.md` rather than silently inherited.

### 3.2 Redis + arq worker → FastAPI BackgroundTasks

**Problem.** Document processing ran as an `arq` task on a Redis queue in a
separate worker container. Free tier = one process, no Redis.

**Solution.** `process_document` never actually depended on the queue
transport — it only touches Postgres, object storage and Qdrant. Moved it to
`BackgroundTasks`, deleted `app/workers/` entirely. Rate limiting fell back to
slowapi's in-memory store.

**Consequence recorded.** In-memory rate limiting counts *per process*. With
more than one worker process, limits under-enforce proportionally. Noted
inline next to the worker-count setting so the connection is visible at the
point where someone would change it.

### 3.3 Self-hosted MinIO → Supabase Storage

**Problem.** MinIO ran as a container with a persistent volume. No equivalent
on free hosting.

**Solution.** Supabase Storage's S3-compatible API, private bucket.

**A wrong assumption caught by checking.** The plan was to keep the existing
`minio` Python client, since Supabase speaks S3. Checking `minio-py`'s own
documentation first showed its `endpoint` parameter accepts only a bare
hostname or `host:port` — every documented example is `s3.amazonaws.com`,
`server:9000`. Supabase's endpoint carries a mandatory path
(`.../storage/v1/s3`) that the client has no field for. Switched to `boto3`,
whose `endpoint_url` takes a full URL, with `addressing_style: "path"` so the
bucket name stays in the path instead of being prepended as a subdomain.

Had this not been checked, the migration would have been written, reviewed and
deployed before failing.

---

## 4. Deployment problems — every one

Ordered roughly as encountered. Several were caused by the fix for a previous
one.

### 4.1 GitHub Codespaces: port 5173 returned 404

**Symptom.** Vite logged `ready in 832 ms` and bound to `0.0.0.0:5173`, the
port was forwarded and public, but the browser showed a 404.

**False starts.** Rebuilt the image; suspected a stale `node_modules` volume;
suspected the redesign hadn't been pulled. None were the cause.

**Root cause, found by testing rather than reasoning.** Ran Vite locally and
curled it with the Codespaces `Host` header:

```
curl localhost:5199                              → 200
curl -H "Host: <name>.app.github.dev" localhost  → 403 Blocked request
```

Vite 5.4.12+ added a DNS-rebinding guard that rejects any request whose `Host`
header is not localhost. Codespaces serves from `*.app.github.dev`, so every
request was rejected before reaching the app; the Codespaces proxy surfaced
that as its own generic 404.

**Fix.** `server.allowedHosts: ['.app.github.dev']` in `vite.config.ts`.
Leading dot = domain and all subdomains, so it survives a Codespace rename.
Verified after the fix: the Codespaces host returns 200, an unrelated host
still returns 403 — the security guard remains intact.

**Also fixed alongside.** HMR over the Codespaces HTTPS proxy needs
`wss://…:443`; the default `ws://…:5173` fails silently.

### 4.2 Port 8000 returned 404 — not a bug

`backend/app/main.py` registers no route at `/`, only `/health` and
`/api/v1/*`. FastAPI correctly 404s the bare root. This wasted debugging time
because it *looked* like the same failure as 4.1. Recorded here because
"correct behaviour that resembles a bug" is worth naming.

### 4.3 Docker Compose reused a stale `node_modules`

The frontend service uses an anonymous volume (`/app/node_modules`) so the
container keeps its own dependencies instead of having the host's shadow them
through the bind mount. Compose **reuses anonymous volumes on recreate**, so
after `package.json` changed, `docker compose up --build` still ran with the
old dependency set.

**Fix.** `-V` / `--renew-anon-volumes` on rebuild. Documented inline in the
compose file next to the volume, since that is where someone hits it.

### 4.4 Render ran the development command in production

**Symptom.** Production logs showed `Will watch for changes… using WatchFiles`
(i.e. `--reload`) and a hardcoded port 8000 instead of Render's assigned
`$PORT`.

**Root cause — a documentation error, mine.** `DEPLOYMENT.md` said to set the
**"Start Command"**. For a Docker-runtime service Render's field is
**"Docker Command"** (Settings → Advanced); "Start Command" applies to native
runtimes and silently does nothing. The field was never set, so Render fell
back to the Dockerfile's `CMD` — which is correct for local dev and wrong on
both counts in production.

**Fix.** Corrected the docs, with an explicit note that leaving the field blank
fails silently rather than erroring.

### 4.5 Render's Pre-Deploy Command is paid-only

The plan used Render's Pre-Deploy Command to run `alembic upgrade head`. It is
a paid-plan feature. Render's Shell/SSH access — the obvious manual
workaround — also appears to be paid-only.

**Fix.** Fold the migration into the start command, which has no tier
restriction.

### 4.6 `sh -c "a && b"` was not parsed as a shell command

First attempt at 4.5:

```
sh -c "alembic upgrade head && uvicorn app.main:app …"
```

Render did not pass this through a shell; the entire string was tokenized as
one command name:

```
sh: 1: alembic upgrade head && uvicorn …: not found
```

**Fix.** Moved the logic into a real checked-in script,
`backend/scripts/render-start.sh`, so the dashboard field holds only
`sh scripts/render-start.sh` — two tokens, nothing to mis-parse. `set -e`
means a failed migration stops the boot rather than serving against a stale
schema. Verified the committed blob's shebang is LF-terminated (`0a`, not
`0d 0a`) so Windows line-ending conversion could not break it inside a Linux
container.

### 4.7 Out of memory on Render (512 MB)

**Symptom.** `Out of memory (used over 512Mi)` immediately after uvicorn bound.

**Root cause.** `--workers 4` forks four full copies of a process that imports
`paddlepaddle`/`paddleocr`. Render's own log had already suggested
`WEB_CONCURRENCY=1` for the instance size; the hardcoded `--workers 4`
overrode it.

**Fix.** `--workers 1`. This also silently fixed a correctness bug: the
in-memory rate limiter (3.2) counts per process, so four workers had been
under-enforcing rate limits roughly fourfold.

### 4.8 `relation "users" does not exist`

**Symptom.** Login returned 500. Traceback:
`psycopg2.errors.UndefinedTable: relation "users" does not exist`.

**Root cause.** Neon was a brand-new empty database. Migrations had never run
against it — a direct consequence of 4.5/4.6 not yet being resolved.

**Fix.** Resolved by 4.6 (migrations now run on every boot). `alembic upgrade
head` is idempotent, so running it per-boot rather than per-deploy costs
nothing and self-heals a missed migration.

### 4.9 Vercel 404 on every client-side route

**Symptom.** Visiting `/login` directly returned Vercel's platform 404 (not the
app's).

**Root cause.** A Vite SPA's routes have no corresponding files in the build
output. Vercel's static host looks for `/login`, finds nothing, and 404s
before `index.html` — which contains the router — ever loads. Vercel's own
documentation states deep linking "won't work out of the box" for Vite SPAs.

**Fix.** `frontend/vercel.json` rewriting `/(.*)` → `/index.html`. No dashboard
equivalent exists; it must be a committed file.

### 4.10 CORS blocked every API call

**Symptom.** `No 'Access-Control-Allow-Origin' header is present`, from the
Vercel origin to the Render backend.

**Root cause.** `allow_origins=["*"]` was hardcoded for local dev.

**Fix.** `CORS_ALLOWED_ORIGINS` environment variable. `"*"` remains the local
default; production must set the real origin. Left as `"*"` in production it
would let any website call the API using a logged-in user's browser session.

### 4.11 Frontend called itself instead of the backend

Split-origin deployment (Vercel + Render) breaks relative `fetch('/api/v1/…')`
— it resolves against Vercel's domain, where there is no API.

**Fix.** `VITE_API_BASE_URL` build-time variable, plus a declaration in
`vite-env.d.ts` so `tsc` (which runs as part of the build) does not fail on
the new key.

### 4.12 Codespace ran out of disk

**Symptom.** `failed to extract layer … no space left on device` during image
export.

**Root causes, two.** Orphaned containers and images from services deleted
during the migration (Redis, MinIO, Ollama — the Ollama image alone is several
GB), plus accumulated build cache. Compounded by a `libreoffice` package added
to the Dockerfile for `.doc/.ppt/.xls` support (~700 MB–1 GB).

**Fix.** `docker compose down --remove-orphans` + `docker system prune -af`.
Explicitly **without** `--volumes`, which would have destroyed the local
Postgres and Qdrant data volumes.

### 4.13 Codespace `.env` predated the storage migration

**Symptom.** `pydantic_core.ValidationError: 4 validation errors for Settings —
storage_endpoint / storage_region / storage_access_key / storage_secret_key
Field required`.

**Root cause.** The Codespace's `.env` was created from an older
`.env.example` and had no `STORAGE_*` keys.

**Fix.** Rewrote it — pointed at Neon + Qdrant Cloud + Supabase, i.e. the same
services production uses. This mattered beyond fixing the error: ingesting
into the local dev containers would have loaded documents the deployed app
could never see.

Also required `--force-recreate`, because containers capture environment
variables at creation time and a plain `up -d` does not pick up a rewritten
`.env`.

### 4.14 Supabase bucket name mismatch

`STORAGE_BUCKET_NAME` defaulted to `documents`; the real bucket was
`campusbrain-documents`. Surfaced as a startup warning
(`could not confirm bucket … 404`) rather than a crash — see 4.15.

### 4.15 Bucket check crashed startup (design fix, not a bug report)

`_ensure_bucket()` originally called `make_bucket()` if the bucket was absent.
Managed S3 services commonly disallow bucket creation over the S3 protocol.

**Fix.** Made it best-effort: confirm reachability, log a warning on failure,
never raise. A slow or misconfigured storage provider should not prevent the
API from booting and serving `/health`. Bucket creation became a documented
one-time dashboard action. This is why 4.14 appeared as a warning instead of
taking the service down.

### 4.16 Neon connection string was unusable

`config.py` built a connection string from discrete fields
(`POSTGRES_USER`/`HOST`/…) and could not express Neon's required
`?sslmode=require&channel_binding=require`.

**Fix.** A `DATABASE_URL` override that takes priority when set. Needed an
explicit pydantic alias, because the field name `database_url` was already
taken by the property that composes the discrete fields — without the alias,
pydantic-settings would have looked for `DATABASE_URL_RAW`.

### 4.17 Qdrant Cloud rejected unauthenticated connections

`QdrantClient(host=…, port=…)` has no `api_key` and no TLS. Qdrant Cloud
requires both.

**Fix.** `QDRANT_URL` + `QDRANT_API_KEY`, taking priority over host/port when
set. Verified the exact Cloud connection form against qdrant-client's own
documentation before writing it.

### 4.18 Vector deletion failed on Qdrant Cloud

**Symptom.** `400 Bad Request: Index required but not found for "document_id"`.

**Root cause.** Deleting vectors used a payload filter on `document_id`.
Qdrant only permits filtering on an indexed payload key. **Self-hosted Qdrant
is lenient about this; Qdrant Cloud enforces it** — so this passed in
development and failed in production.

**Fix.** Delete by point ID instead. Chunk IDs *are* the Qdrant point IDs, and
both callers already hold the chunk rows, so no payload index needs to exist
or be maintained. Batched at 1000 IDs per request.

**Wider than it appeared.** The same code path clears a document's old vectors
before re-embedding, so **re-indexing any document would have failed
identically** — it would have surfaced the first time a source file was edited
and re-ingested.

### 4.19 Command palette rendered fully transparent

**Symptom.** The `⌘K` palette had no background; conversation text showed
through it.

**Root cause.** The chat theme's CSS variables are scoped to a `.cb-scope`
wrapper so they cannot disturb the existing plain-CSS auth/upload pages. Radix
and cmdk portal dialogs to `document.body` — outside that wrapper — so
`bg-surface`, `text-ink` and the backdrop resolved to undefined variables.

**Fix.** Portal the dialogs into the scoped element. The obvious alternative
(hoisting tokens to `:root`) was checked and rejected: `--accent`, `--border`
and `--muted` collide with names `index.css` already uses for the auth pages,
so a global redefinition would have restyled them.

Affected all three portalled components — palette, shortcuts dialog, mobile
sidebar drawer — though only the palette had been noticed.

### 4.20 No webfonts were ever loaded

`chat-theme.css` referenced Inter / Source Serif 4 / JetBrains Mono, but
`index.html` loaded none of them, so every one fell back to a system default
and serif headings rendered as Georgia. This was the single largest reason the
deployed UI looked unlike the design despite identical component code.

**Fix.** Added the font links, and verified the Google Fonts URL actually
returns all three families rather than assuming — a typo there fails silently,
which is exactly how the original omission survived.

### 4.21 Assorted operational friction

Small, repeated, and worth listing because they cost real time:

- **`no configuration file provided: not found`** — running `docker compose`
  from the repo root instead of `docker/`. Happened several times.
- **`mv`/`rm` "No such file or directory"** — same cause: relative paths run
  from `docker/` resolved to `docker/resources/…`.
- **`git pull` refused to merge** — untracked local files (`askilainfos.md`,
  `sitarefoundation.md`) would be overwritten by incoming tracked versions.
  Resolved with `git stash -u`.
- **`git stash pop` could not restore** — after the pull, those paths existed
  as tracked files. Git refused to overwrite and **kept the stash**, so nothing
  was lost; the stash just had to be verified against the pulled versions and
  dropped.
- **PowerShell corrupted a UTF-8 file** — `Get-Content -Raw | Set-Content`
  round-tripped em-dashes into mojibake (`â€"`). Rewritten with a UTF-8-aware
  tool; subsequent file edits avoided PowerShell text munging entirely.
- **Only 2 of 5 knowledge-base files reached the Codespace** — the other three
  were untracked locally and had never been pushed. The ingest tool reported 2
  files found, which correctly reflected reality but looked like a tool bug.

---

## 5. Privacy and safety

### 5.1 Student personal data in a public repository — prevented

`resources/SU 2024 batch student details … .pdf` contains individual student
records. `github.com/ISHANT57/CampusBrain` is **public**.

Committing it would have published real students' personal data to the open
internet, permanently: git retains it in history after deletion, it propagates
to every clone and fork, and GitHub code search plus third-party scrapers index
public repositories within minutes. Removal would require history rewriting and
a force push, and still could not recall what had been cloned.

**Action.** The file was **not committed**. The two other resource files were
scanned for personal data before committing (they contained only institutional
`@sitare.org` addresses and no phone numbers) and were pushed. The PDF was
transferred into the Codespace by direct upload, which never touches git.

### 5.2 Student personal data served by a public chatbot — found and removed

More serious than 5.1, and initially missed. That same PDF had already been
**ingested into the knowledge base**, and chat had been made anonymous/public.
A query in a screenshot — *"who is pragati chauhan"* — returned a named
student's academic details, internship and personal interests.

So the data was reachable by anyone who found the URL, through a different door
than the repository.

**Why deleting the file was not enough.** Extracted text lives in Postgres
`chunks` and embeddings in Qdrant. A document remains fully answerable long
after its source file is gone.

**Action.** Built `tools/ingest.py --forget PATTERN`, which removes all four
traces: Qdrant vectors, chunk rows, the document row, and the stored blob.
Design decisions:
- **Previews by default; requires `--yes`** to delete, because it runs against
  production and a too-broad pattern would silently take out more than
  intended.
- **Chunk IDs are read before the rows are deleted** — they are the Qdrant
  point IDs, so deleting rows first would leave vectors unreachable and still
  being served.
- **Blob-deletion failures are reported, not fatal** — leaving vectors live
  because object storage hiccuped would defeat the purpose.

Confirmed removed: 44 chunks, document id 1.

### 5.3 Secrets pasted into a chat transcript

Neon, Qdrant Cloud, Supabase, Gemini and OpenRouter credentials were shared in
conversation to be configured.

**Action.** They were written only to `.env.production`, which was confirmed
gitignored *before* anything was written to it, and verified absent from every
staged diff. The file itself carries a note recommending rotation of the
cheaply-rotatable keys (Supabase S3 pair, OpenRouter) after the first
successful deploy, since the exposure already occurred when they were pasted.

### 5.4 Production secrets that must not be defaults

- `JWT_SECRET_KEY` — reusing the dev default would let anyone forge a valid
  session token for any account. A fresh value was generated
  (`secrets.token_hex(32)`).
- `CORS_ALLOWED_ORIGINS` — see 4.10.

### 5.5 Object storage access model

Supabase S3 access keys bypass Row Level Security and are explicitly
server-only per Supabase's documentation. This is not a gap here: the real
access boundary is enforced in the application, where every document read and
write is scoped by `current_user.org_id` before reaching storage. The bucket is
**private**; RLS policies are Supabase's mechanism for client-side JWT access,
which this backend does not use.

### 5.6 Standing risk: the knowledge base is effectively public

With anonymous chat, anything ingested is world-readable through the bot.
Removing one PDF fixed one exposure; it did not change the property. Any future
document needs to be evaluated on the assumption that its contents can be
retrieved by anyone with the URL.

---

## 6. Knowledge base preloading

**Requirement.** Preload the corpus before launch so users can ask immediately,
without changing the existing upload feature.

**Approach — reuse, not duplication.** `index_document(db, document, content)`
was extracted out of `process_document`, so the ingest tool and the upload
background task run *the same function* for extract → clean → chunk → embed →
index. The only difference between the two paths is where the bytes come from.
Sharing is therefore structural rather than parallel implementations that can
drift.

**Deduplication.** SHA-256 of file content, stored on `documents.content_hash`
(nullable, indexed on `(org_id, content_hash)`). Content-addressed rather than
path-addressed: a renamed or moved file is correctly recognised as already
indexed, and an edited file gets a new hash and is correctly re-indexed. API
uploads leave it NULL and it is absent from `DocumentRead`, so the public API
shape is unchanged.

**Citations carry folder structure.** Ingested documents store their path
relative to the scan root in `filename`, so a citation reads
`handbook/fees.pdf`. Done via the existing column rather than adding
`source_path`, specifically to leave the `Citation` and `DocumentRead` schemas
untouched.

**A bug this surfaced.** Re-indexing was silently broken — chunk ID *is* the
Qdrant point ID, and re-inserted chunks get new IDs, so old vectors could never
be overwritten by the upsert. They would linger indefinitely, returning stale
text pointing at deleted chunk rows. This affected the upload path too, not
just ingest.

**Deliberate difference from uploads.** Ingest does not push blobs to object
storage by default (`--upload-blobs` opts in): the corpus already exists on
disk, and copying hundreds of files would consume the free 1 GB tier for data
nothing reads back — retrieval only uses chunk text from Postgres. Consequence:
ingested documents have `storage_key = NULL`, so a future "download original"
feature will not work for them.

**Result.** 6 files, 49 chunks/vectors on the final incremental run, 0 failures.

---

## 7. Patterns worth carrying forward

1. **Verify the API contract before writing against it.** The `minio-py`
   endpoint limitation (3.3), the Gemini response shape, Qdrant's Cloud
   connection form, and Render's field names were all checked against primary
   documentation first. The two places this was *not* done — Render's "Start
   Command" (4.4) and the Pre-Deploy tier restriction (4.5) — both produced
   failed deployments.

2. **Test the hypothesis, don't reason about it.** The Codespaces 404 (4.1)
   survived several plausible-sounding theories and multiple rebuilds. One
   `curl` with the right `Host` header settled it in seconds.

3. **Dev-vs-production leniency is a recurring failure class.** Qdrant payload
   indexes (4.18), Vite's host guard (4.1), MinIO's bucket creation (4.15) —
   all worked locally and failed managed. Anything that "works in dev" against
   a self-hosted equivalent deserves suspicion.

4. **Silent fallbacks cost the most time.** An unset Render field ran the wrong
   command; a null portal container fell back to `document.body`; missing fonts
   fell back to system defaults. None errored. Each was found by noticing a
   symptom, not by a failure message.

5. **Record consequences at the point of the decision.** The recalibration risk
   in 3.1, the rate-limiting caveat in 3.2, and the `storage_key = NULL`
   trade-off in §6 are all written next to the code that causes them.

---

## 8. Current state and known gaps

**Working:** deployed backend (Render) and frontend (Vercel), Neon, Qdrant
Cloud, Supabase Storage, Gemini embeddings, OpenRouter LLM, preloaded
knowledge base, admin-gated uploads, anonymous public chat with citations.

**Open:**

- **No backups.** No Postgres dump schedule (roadmap M64).
- **No CI/CD.** Images build on push; automated pipeline is M62–M63.
- **HTTPS for the self-hosted path** is staged but disabled — the TLS block in
  `docker/nginx/nginx.conf` is commented out deliberately, because nginx
  refuses to start if certificate files are absent, which would break a first
  deploy. Not relevant to the Render/Vercel path.
- **`.doc/.ppt/.xls` support is unverified.** It requires LibreOffice in the
  image, which was added but never build-verified, and it materially increases
  image size and cold-start time on the free tier. The corpus in use needs none
  of these three formats.
- **Free-tier cold starts.** Render's free web service sleeps after 15 minutes
  idle; the next request waits 30–60 s.
- **Retrieval threshold may need recalibration** for Gemini embeddings (3.1).
- **Duplicate-ish source documents.** `interns.md` and `internshipinfo.md` are
  distinct files with likely overlapping content — not deduplicated (their
  bytes differ), but they may compete in retrieval and split citations.
