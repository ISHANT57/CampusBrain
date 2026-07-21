# CampusBrain AI — Development Strategy

Granular, sequential milestones from empty repo to production. Each milestone is the smallest unit that produces a verifiable result. Do not start milestone N+1 until N's Definition of Done is met.

Assumed project structure (referenced throughout):

```
backend/app/{core,api/v1,services,repositories,models,schemas,infrastructure,workers}
backend/alembic/
backend/tests/
frontend/src/{pages,components,api,hooks}
docker/
.github/workflows/
```

---

## PHASE 1 — Foundation & Infrastructure

### M1 — Repo & tooling bootstrap
- **Goal**: A version-controlled, conventionally-structured empty project.
- **Why it exists**: Everything else needs a home; conventions set now (folder layout, commit style) prevent churn later.
- **Problem it solves**: "Where does new code go?" ambiguity.
- **Concepts to learn first**: Git basics, monorepo vs polyrepo (you're using monorepo), `.gitignore` conventions, EditorConfig.
- **Technologies**: Git, GitHub.
- **Files created**: `README.md`, `.gitignore`, `.editorconfig`, `backend/`, `frontend/`, `docker/` (empty dirs with `.gitkeep`).
- **Expected output**: `git log` shows an initial commit; folder tree matches the structure above.
- **Definition of Done**: Repo pushed to GitHub, structure in place, README states project name and one-line purpose.

### M2 — Docker Compose skeleton: PostgreSQL only
- **Goal**: One service (Postgres) running under Compose with a persistent volume.
- **Why it exists**: Prove Docker Compose fundamentals before adding six more services at once.
- **Problem it solves**: Local environment reproducibility.
- **Concepts to learn first**: Docker images vs containers, volumes, Compose service definitions, environment variables in Compose.
- **Technologies**: Docker, Docker Compose, PostgreSQL.
- **Files created**: `docker/docker-compose.yml`, `.env.example`.
- **Expected output**: `docker compose up` starts Postgres; `psql` or a GUI client can connect.
- **Definition of Done**: Container restarts without data loss (volume verified by restart + reconnect).

### M3 — FastAPI hello-world + health endpoint
- **Goal**: A containerized FastAPI app with `GET /health` returning `{"status": "ok"}`.
- **Why it exists**: Establishes the backend container pattern (Dockerfile, hot reload, dependency install) before real logic exists.
- **Problem it solves**: "Is the backend container wired correctly?" — isolate infra issues from business-logic issues.
- **Concepts to learn first**: FastAPI basics, Uvicorn, Python virtual envs vs container-based deps.
- **Technologies**: FastAPI, Uvicorn, Docker.
- **Files created**: `backend/app/main.py`, `backend/Dockerfile`, `backend/requirements.txt`, add `backend` service to `docker/docker-compose.yml`.
- **Expected output**: `curl localhost:8000/health` returns 200 while running under Compose.
- **Definition of Done**: Backend container starts from `docker compose up`, health check passes, code-reload works on file save (dev mode).

### M4 — React + TypeScript + Vite skeleton
- **Goal**: A containerized frontend that renders one page and calls `/health`.
- **Why it exists**: Confirms frontend↔backend connectivity and CORS before real UI work starts.
- **Problem it solves**: Cross-origin/networking issues discovered early, not during Phase 15.
- **Concepts to learn first**: Vite dev server, CORS, React function components + TypeScript basics.
- **Technologies**: React, TypeScript, Vite, Tailwind CSS.
- **Files created**: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/Dockerfile`, `frontend/package.json`, `frontend/tailwind.config.ts`; add `frontend` service to Compose; add CORS middleware in `backend/app/main.py`.
- **Expected output**: Browser at `localhost:5173` shows backend health status fetched live.
- **Definition of Done**: Frontend container runs under Compose, successfully fetches `/health` across origins with no CORS errors.

### M5 — Add Redis, MinIO, Qdrant, Ollama to Compose
- **Goal**: Every infrastructure dependency the PRD names is running, even if unused by app code yet.
- **Why it exists**: De-risk infra setup (image pulls, ports, volumes, model downloads) as one focused step, separate from writing code against them.
- **Problem it solves**: "Does the full stack even boot?" before any service integration work begins.
- **Concepts to learn first**: Redis basics, object storage concepts (S3-compatible API), vector DB basics, local LLM serving (Ollama).
- **Technologies**: Redis, MinIO, Qdrant, Ollama.
- **Files created**: Updates to `docker/docker-compose.yml` only (services, volumes, healthchecks); `docker/README.md` documenting ports.
- **Expected output**: `docker compose up` brings up all 7 services (Postgres, Redis, MinIO, Qdrant, Ollama, backend, frontend); MinIO console reachable, Qdrant dashboard reachable, `ollama pull qwen3` succeeds inside the container.
- **Definition of Done**: `docker compose ps` shows all services healthy; this is the "everything starts with `docker compose up`" deliverable from the PRD.

---

## PHASE 2 — Database & Core Domain Models

### M6 — SQLAlchemy + Alembic wiring
- **Goal**: Backend connects to Postgres via SQLAlchemy; Alembic can generate and run migrations.
- **Why it exists**: All domain models depend on this plumbing existing first.
- **Problem it solves**: Schema changes need to be versioned and repeatable, not manual SQL.
- **Concepts to learn first**: ORMs, SQLAlchemy sessions/engine, Alembic migration lifecycle (autogenerate, upgrade, downgrade).
- **Technologies**: SQLAlchemy, Alembic, PostgreSQL, Pydantic Settings.
- **Files created**: `backend/app/core/config.py`, `backend/app/core/database.py`, `backend/alembic.ini`, `backend/alembic/env.py`.
- **Expected output**: `alembic upgrade head` runs against an empty DB with zero errors (no tables yet, just the migration framework working).
- **Definition of Done**: A throwaway test model + migration round-trips (create, migrate, drop) successfully.

### M7 — Organization model
- **Goal**: `Organization` table exists with the tenant-isolation boundary fields.
- **Why it exists**: Every other table will have a foreign key to this one — it must exist first.
- **Problem it solves**: Establishes the multi-tenancy root.
- **Concepts to learn first**: Primary/foreign keys, indexing strategy for tenant_id-style columns.
- **Technologies**: SQLAlchemy, Alembic.
- **Files created**: `backend/app/models/organization.py`, `backend/app/schemas/organization.py`, migration file.
- **Expected output**: Table `organizations` in Postgres with columns `id, name, slug, created_at, updated_at`.
- **Definition of Done**: Migration applies cleanly; a row can be inserted and queried via a throwaway script.

### M8 — User model (with roles)
- **Goal**: `User` table with role enum (Student/Faculty/Admin/Super Admin) and FK to `Organization`.
- **Why it exists**: Needed before Auth (Phase 3) can exist.
- **Problem it solves**: Identity and role representation.
- **Concepts to learn first**: Enum columns in SQLAlchemy, unique constraints (email scoped per org vs globally — decide and document).
- **Technologies**: SQLAlchemy, Alembic.
- **Files created**: `backend/app/models/user.py`, `backend/app/schemas/user.py`, migration file.
- **Expected output**: Table `users` with `id, org_id, email, hashed_password, role, created_at`.
- **Definition of Done**: Migration applies; FK constraint to `organizations` verified (inserting a user with a bad org_id fails).

### M9 — Collection model
- **Goal**: `Collection` table (e.g., "Hostel", "Placements") scoped to an organization.
- **Why it exists**: Documents need a grouping unit before Documents themselves are modeled.
- **Problem it solves**: Metadata-filterable document grouping, per PRD §6 Collections.
- **Concepts to learn first**: Nothing new — reuse Phase 2 patterns.
- **Technologies**: SQLAlchemy, Alembic.
- **Files created**: `backend/app/models/collection.py`, `backend/app/schemas/collection.py`, migration file.
- **Expected output**: Table `collections` with `id, org_id, name, description, created_at`.
- **Definition of Done**: Migration applies; a collection can be created under an org via a throwaway script.

### M10 — Document model (metadata only)
- **Goal**: `Document` table storing metadata and processing status — no processing logic yet.
- **Why it exists**: Upload (Phase 4) needs a row to attach the file to; this milestone deliberately stops at "table exists."
- **Problem it solves**: Separates "can we model a document" from "can we process a document."
- **Concepts to learn first**: Status/state columns (enum: pending/processing/processed/failed), soft-delete vs hard-delete strategy.
- **Technologies**: SQLAlchemy, Alembic.
- **Files created**: `backend/app/models/document.py`, `backend/app/schemas/document.py`, migration file.
- **Expected output**: Table `documents` with `id, org_id, collection_id, filename, mime_type, size_bytes, status, storage_key, created_at`.
- **Definition of Done**: Migration applies; FK constraints to `organizations` and `collections` verified.

---

## PHASE 3 — Authentication & Multi-Tenancy

*(Deliberately placed before Storage/Upload — every endpoint from here on needs an authenticated, org-scoped user.)*

### M11 — Password hashing + registration service
- **Goal**: A service function that creates a `User` row with a securely hashed password.
- **Why it exists**: Login (M12) needs something to check against.
- **Problem it solves**: Never store plaintext passwords.
- **Concepts to learn first**: bcrypt/passlib hashing, salt, why plain SHA-256 is wrong for passwords.
- **Technologies**: passlib (bcrypt).
- **Files created**: `backend/app/core/security.py` (hash/verify functions), `backend/app/services/user_service.py`, `backend/app/api/v1/auth.py` (`POST /auth/register`).
- **Expected output**: `POST /auth/register` creates a user; the stored `hashed_password` is never the raw input.
- **Definition of Done**: Registering with a duplicate email in the same org returns a 409 Conflict; password is verifiably hashed (not equal to input) in the DB.

### M12 — JWT login/logout
- **Goal**: `POST /auth/login` returns a signed JWT; token encodes `user_id`, `org_id`, `role`.
- **Why it exists**: Stateless auth for a REST API.
- **Problem it solves**: How does the API know who's calling without a server-side session store?
- **Concepts to learn first**: JWT structure (header/payload/signature), expiry, signing secrets, why JWTs shouldn't hold sensitive data unencrypted.
- **Technologies**: python-jose (or PyJWT).
- **Files created**: `backend/app/core/security.py` (extended: create/decode token), `backend/app/api/v1/auth.py` (extended: `POST /auth/login`).
- **Expected output**: Login with correct credentials returns a JWT; wrong credentials return 401.
- **Definition of Done**: A decoded token round-trips the correct `user_id`/`org_id`/`role`; expired tokens are rejected.

### M13 — Auth dependency (`get_current_user`)
- **Goal**: A reusable FastAPI dependency that extracts and validates the JWT on any protected route.
- **Why it exists**: Every future endpoint needs this exact same check — build it once.
- **Problem it solves**: Duplicated auth-checking code in every route.
- **Concepts to learn first**: FastAPI's Dependency Injection system, `Depends()`.
- **Technologies**: FastAPI.
- **Files created**: `backend/app/core/dependencies.py`.
- **Expected output**: A test-only protected route (`GET /auth/me`) returns the current user's identity when a valid token is supplied, 401 otherwise.
- **Definition of Done**: Calling any protected route with no token, a malformed token, and an expired token all return 401.

### M14 — RBAC route guards
- **Goal**: A dependency/decorator restricting a route to specific roles (e.g., Admin-only).
- **Why it exists**: PRD requires role-differentiated capabilities (Student vs Faculty vs Admin vs Super Admin).
- **Problem it solves**: Prevents privilege escalation (a Student calling an Admin endpoint).
- **Concepts to learn first**: Authorization vs authentication distinction.
- **Technologies**: FastAPI.
- **Files created**: `backend/app/core/dependencies.py` (extended: `require_role(*roles)`).
- **Expected output**: A test-only Admin route rejects Student/Faculty tokens with 403.
- **Definition of Done**: All four roles tested against a role-gated route; only permitted roles pass.

### M15 — Organization-scoping base repository
- **Goal**: A base repository class that automatically injects `org_id` into every query — no repository method can accidentally return cross-tenant data.
- **Why it exists**: This is the single control point that guarantees the "no cross-organization access" architecture requirement — safer than trusting every future repository method to remember the filter.
- **Problem it solves**: Data leakage between tenants.
- **Concepts to learn first**: Repository Pattern, generic/base classes in Python.
- **Technologies**: SQLAlchemy.
- **Files created**: `backend/app/repositories/base.py`.
- **Expected output**: A throwaway repository built on the base class, tested with two orgs' data, only ever returns the calling org's rows.
- **Definition of Done**: A written test proves that querying as Org A can never return an Org B row, even by ID guess.

---

## PHASE 4 — Object Storage & Upload

### M16 — MinIO repository
- **Goal**: A service wrapping MinIO's S3-compatible API for put/get/delete of file blobs.
- **Why it exists**: Isolates storage-provider specifics behind an interface (per the architecture's "every external dependency abstracted" principle).
- **Problem it solves**: Backend needs somewhere durable to put uploaded files.
- **Concepts to learn first**: Object storage vs filesystem storage, S3 API basics (buckets, keys, presigned URLs).
- **Technologies**: MinIO, `boto3` or `minio` Python SDK.
- **Files created**: `backend/app/infrastructure/storage.py`.
- **Expected output**: A throwaway script uploads a file, retrieves it byte-identical, deletes it.
- **Definition of Done**: Round-trip upload/download/delete verified against the MinIO container.

### M17 — Document upload endpoint
- **Goal**: `POST /documents` accepts a file, validates it, stores it in MinIO, creates a `Document` row (status: `pending`).
- **Why it exists**: The actual entry point of the ingestion pipeline.
- **Problem it solves**: Turns a raw file into a tracked, org-scoped, storage-backed record.
- **Concepts to learn first**: FastAPI file uploads (`UploadFile`), MIME sniffing vs trusting the extension, max file size enforcement.
- **Technologies**: FastAPI, python-magic (MIME detection).
- **Files created**: `backend/app/api/v1/documents.py`, `backend/app/services/document_service.py`.
- **Expected output**: Uploading a PDF returns a `Document` object with `status=pending`; uploading a disallowed type (e.g., `.exe`) returns 400.
- **Definition of Done**: File type, size limit, and org-scoping all enforced and tested; file is retrievable from MinIO afterward.

### M18 — Background job queue (Arq + Redis)
- **Goal**: A working async job runner separate from the API process.
- **Why it exists**: Upload must not block the HTTP response while extraction/embedding runs — this is an explicit NFR.
- **Problem it solves**: Long-running processing work needs to happen off the request/response cycle.
- **Concepts to learn first**: Producer/consumer pattern, Redis as a message broker, Arq's worker model.
- **Technologies**: Arq, Redis.
- **Files created**: `backend/app/workers/worker.py`, `backend/app/workers/tasks.py`, add `worker` service to `docker/docker-compose.yml`.
- **Expected output**: A throwaway task (e.g., "sleep 2s, log a message") enqueued from the API is picked up and run by the separate worker container.
- **Definition of Done**: Worker container runs independently under Compose; enqueued job executes and its result/status is checkable.

### M19 — Wire upload to enqueue processing job
- **Goal**: `POST /documents` enqueues a real "process this document" job instead of a throwaway one.
- **Why it exists**: Connects Phase 4's upload to Phase 5's processing without either phase needing to know the other's internals yet (job body is still a stub).
- **Problem it solves**: Establishes the seam between upload and processing.
- **Concepts to learn first**: Idempotency (what happens if the same job runs twice).
- **Technologies**: Arq.
- **Files created**: `backend/app/workers/tasks.py` (extended: `process_document(document_id)` stub that just flips status to `processing` then `processed`).
- **Expected output**: Uploading a document transitions its status `pending → processing → processed` without any manual intervention.
- **Definition of Done**: Status transition observable via `GET /documents/{id}` polling, with no real extraction logic yet (stubbed).

---

## PHASE 5 — Document Processing (Extraction & OCR)

### M20 — PDF text extraction (PyMuPDF)
- **Goal**: Extract raw text + page numbers from a PDF.
- **Why it exists**: PDFs are the primary institutional document format (syllabi, circulars, policies).
- **Problem it solves**: Turns a binary file into retrievable text.
- **Concepts to learn first**: PDF internals basics (text layer vs scanned image), page-level extraction.
- **Technologies**: PyMuPDF (fitz).
- **Files created**: `backend/app/services/extraction/pdf_extractor.py`.
- **Expected output**: A sample PDF produces a list of `{page_number, text}` objects.
- **Definition of Done**: Tested against one text-based PDF and one scanned (image-only) PDF — the latter correctly returns near-empty text (proving OCR is needed, not silently failing).

### M21 — Multi-format extraction (Unstructured)
- **Goal**: Extend extraction to DOCX, PPTX, XLSX, CSV, Markdown, TXT.
- **Why it exists**: PRD requires all these formats.
- **Problem it solves**: One unified extraction interface regardless of input format.
- **Concepts to learn first**: Unstructured library's partitioning strategies per file type.
- **Technologies**: Unstructured.
- **Files created**: `backend/app/services/extraction/unstructured_extractor.py`, `backend/app/services/extraction/router.py` (dispatches by MIME type).
- **Expected output**: One sample file per supported format extracts non-empty text via the router.
- **Definition of Done**: All 6 non-PDF formats produce text; unsupported formats raise a clear `ValidationError`, not a crash.

### M22 — OCR fallback (PaddleOCR)
- **Goal**: Detect low/no extractable text and run OCR on page images instead.
- **Why it exists**: Scanned documents (old circulars, handwritten notices) have no text layer.
- **Problem it solves**: Otherwise those documents are silently unsearchable.
- **Concepts to learn first**: OCR fundamentals, confidence scores, when to trigger OCR vs trust the text layer.
- **Technologies**: PaddleOCR.
- **Files created**: `backend/app/services/extraction/ocr_extractor.py`.
- **Expected output**: The scanned PDF from M20 (previously near-empty) now returns meaningful extracted text.
- **Definition of Done**: A heuristic (e.g., "extracted text length < threshold → trigger OCR") is implemented and tested against both a text PDF (OCR skipped) and scanned PDF (OCR triggered).

### M23 — Cleaning + metadata extraction + status update
- **Goal**: Normalize extracted text (whitespace, encoding) and populate `Document` metadata (page count, language, extraction method used); flip status to `processed` (real, not stubbed).
- **Why it exists**: Closes out the extraction stage of the pipeline with a real, inspectable result.
- **Problem it solves**: Downstream chunking needs clean, consistent text.
- **Concepts to learn first**: Text normalization pitfalls (encoding issues, ligatures, hyphenation across line breaks).
- **Technologies**: Python `re`/`unicodedata`.
- **Files created**: `backend/app/services/extraction/cleaner.py`, updates to `backend/app/workers/tasks.py` (`process_document` now calls real extraction).
- **Expected output**: `GET /documents/{id}` shows populated metadata and `status=processed` after real extraction runs.
- **Definition of Done**: Extraction failures set `status=failed` with an error message (not a silent crash of the worker).

---

## PHASE 6 — Chunking

### M24 — Recursive chunking
- **Goal**: Split cleaned document text into overlapping chunks of a configurable size.
- **Why it exists**: Embeddings and LLM context windows need bounded, retrievable units, not whole documents.
- **Problem it solves**: Enables precise retrieval (return the relevant paragraph, not the whole 50-page policy doc).
- **Concepts to learn first**: Why chunk size/overlap matters, recursive character/token splitting, token counting.
- **Technologies**: Python (or `langchain-text-splitters` used standalone, ahead of full LangChain adoption).
- **Files created**: `backend/app/services/chunking/recursive_chunker.py`.
- **Expected output**: A processed document's text is split into a list of chunk strings with page provenance retained.
- **Definition of Done**: Chunk boundaries never split mid-sentence for >90% of chunks on a manual sample review; overlap is verifiably present.

### M25 — Chunk persistence
- **Goal**: A `Chunk` table storing each chunk's text, position, page, and FK to `Document`.
- **Why it exists**: Chunks need stable IDs to be referenced later by vector search results and citations.
- **Problem it solves**: Links a future Qdrant vector back to human-readable source (doc name, page, paragraph).
- **Concepts to learn first**: Nothing new — reapply Phase 2 modeling patterns.
- **Technologies**: SQLAlchemy, Alembic.
- **Files created**: `backend/app/models/chunk.py`, `backend/app/schemas/chunk.py`, migration file; worker task extended to persist chunks.
- **Expected output**: After processing, `chunks` table has N rows per document, each traceable to its page and org.
- **Definition of Done**: Chunk count matches expected split for a known sample document; all chunks correctly FK'd.

### M26 — Chunking evaluation (manual, not production code)
- **Goal**: Compare 2–3 chunk-size/overlap configurations on a handful of representative documents (a syllabus, a long policy PDF, a short circular).
- **Why it exists**: Picking a default now avoids re-processing the whole corpus later when retrieval quality turns out poor.
- **Problem it solves**: Prevents guessing at a critical tuning parameter.
- **Concepts to learn first**: What "good" chunking looks like qualitatively (does a chunk read as a coherent unit?).
- **Technologies**: Jupyter notebook or a throwaway script (not part of the shipped app).
- **Files created**: `backend/scripts/chunking_eval.ipynb` (or `.py`) — explicitly a scratch/eval artifact, not production code.
- **Expected output**: A short written note (in the notebook or a `NOTES.md`) recording the chosen default chunk size/overlap and why.
- **Definition of Done**: A default is picked and set as the config value used by M24 going forward; decision is documented, not left implicit.

---

## PHASE 7 — Embeddings

### M27 — BGE-M3 embedding service
- **Goal**: A service that turns text into a vector using BGE-M3.
- **Why it exists**: Chunks need a numeric representation for similarity search.
- **Problem it solves**: Bridges text and vector search.
- **Concepts to learn first**: What an embedding is, cosine similarity, embedding dimensionality, model loading (local inference vs API call).
- **Technologies**: BAAI bge-m3 (via `sentence-transformers` or served through Ollama).
- **Files created**: `backend/app/infrastructure/embeddings.py`.
- **Expected output**: `embed("some text")` returns a fixed-length float vector; two similar sentences produce vectors with high cosine similarity, dissimilar ones low.
- **Definition of Done**: A written test asserts similarity ordering on 3 known sentence pairs (near-duplicate, related, unrelated).

### M28 — Batch chunk embedding pipeline step
- **Goal**: All chunks of a processed document get embedded and the vectors stored in-memory/temporarily (not yet in Qdrant — that's Phase 8).
- **Why it exists**: Proves the embedding step works at pipeline scale (batches, not one-off calls) before wiring persistence.
- **Problem it solves**: Isolates embedding-pipeline correctness from vector-DB correctness.
- **Concepts to learn first**: Batching for throughput, embedding failure handling (partial batch failures).
- **Technologies**: BGE-M3 service from M27.
- **Files created**: `backend/app/services/embedding_service.py`.
- **Expected output**: Given a document's chunk list, returns a parallel list of vectors, same length, same order.
- **Definition of Done**: A 100-chunk document embeds without memory errors or timeouts; failed individual chunks are logged, not silently dropped.

---

## PHASE 8 — Vector Database

### M29 — Qdrant collection provisioning
- **Goal**: A per-organization Qdrant collection is created automatically when an org is created.
- **Why it exists**: Implements the tenant-isolation decision from planning — one collection per org, not a shared collection with a filter.
- **Problem it solves**: Vector-level data isolation between tenants.
- **Concepts to learn first**: Qdrant collections, vector dimensions/distance metric config (cosine for BGE-M3).
- **Technologies**: Qdrant.
- **Files created**: `backend/app/infrastructure/vector_store.py`, hook into `backend/app/services/org_service.py` (org creation triggers collection creation).
- **Expected output**: Creating an org via the API results in a matching Qdrant collection (verifiable via Qdrant dashboard/API).
- **Definition of Done**: Two orgs created → two isolated collections exist; deleting an org removes its collection.

### M30 — Vector upsert repository
- **Goal**: Store `{vector, payload: org_id, doc_id, chunk_id, page, text}` into the correct org's Qdrant collection.
- **Why it exists**: Makes chunks searchable.
- **Problem it solves**: Persists the output of embedding into retrievable storage.
- **Concepts to learn first**: Qdrant payload filtering, point IDs, upsert semantics.
- **Technologies**: Qdrant.
- **Files created**: `backend/app/repositories/vector_repository.py`.
- **Expected output**: After upsert, a direct Qdrant query by ID returns the correct vector and payload.
- **Definition of Done**: Upserting the same chunk twice updates (not duplicates) the point.

### M31 — Full ingestion pipeline wiring
- **Goal**: Upload → extract → chunk → embed → store-in-Qdrant runs end-to-end automatically from a single upload call.
- **Why it exists**: This is the first true end-to-end milestone — the PRD's entire "Document Processing" section working as one flow.
- **Problem it solves**: Validates all Phase 4–8 pieces compose correctly, not just individually.
- **Concepts to learn first**: Nothing new — integration only.
- **Technologies**: All of the above.
- **Files created**: `backend/app/workers/tasks.py` (final `process_document` implementation chaining all steps).
- **Expected output**: Upload a real PDF → within seconds its chunks are queryable directly in Qdrant.
- **Definition of Done**: A document uploaded through the API is fully searchable in Qdrant with zero manual steps; status correctly reflects `processed` or `failed` with a reason.

---

## PHASE 9 — Retrieval

### M32 — Semantic search endpoint
- **Goal**: `POST /search` embeds a query and returns top-k nearest chunks from the caller's org collection.
- **Why it exists**: First user-facing search capability.
- **Problem it solves**: "Find relevant content for this question."
- **Concepts to learn first**: k-NN search, similarity thresholds.
- **Technologies**: Qdrant, BGE-M3.
- **Files created**: `backend/app/services/retrieval_service.py`, `backend/app/api/v1/search.py`.
- **Expected output**: A query like "attendance requirement semester 4" returns the correct chunk from a sample uploaded policy doc, ranked #1 or #2.
- **Definition of Done**: Cross-org isolation verified (Org A's query never surfaces Org B's chunks) — reuses the M15/M29 guarantees at the retrieval layer explicitly.

### M33 — Keyword (BM25) search
- **Goal**: A parallel search path using term-frequency matching, not vectors.
- **Why it exists**: Semantic search misses exact-term queries (course codes, IDs, acronyms) that BM25 handles better.
- **Problem it solves**: Complements semantic recall gaps.
- **Concepts to learn first**: BM25 algorithm basics, Postgres full-text search (`tsvector`) as the implementation choice.
- **Technologies**: PostgreSQL full-text search (or `rank_bm25` in-process).
- **Files created**: `backend/app/services/retrieval_service.py` (extended), migration adding a `tsvector` column/index on `chunks`.
- **Expected output**: A query for an exact course code returns the right chunk even when semantic search ranks it low.
- **Definition of Done**: Same org-isolation test as M32 applied to the BM25 path.

### M34 — Hybrid fusion
- **Goal**: Combine semantic + BM25 result lists into one ranked list.
- **Why it exists**: PRD explicitly requires Hybrid Search as a supported mode.
- **Problem it solves**: Neither method alone is sufficient; fusion captures both strengths.
- **Concepts to learn first**: Reciprocal Rank Fusion (RRF) or a weighted-score fusion approach.
- **Technologies**: Python.
- **Files created**: `backend/app/services/retrieval_service.py` (extended: `hybrid_search()`), `backend/app/api/v1/search.py` (extended with a `mode` param: semantic/keyword/hybrid).
- **Expected output**: `mode=hybrid` outperforms either individual mode on a small hand-built eval set (semantic-only-answerable query + keyword-only-answerable query).
- **Definition of Done**: All three modes selectable via the API and manually verified against the eval set.

---

## PHASE 10 — Re-ranking

### M35 — BGE-reranker-v2-m3 wrapper
- **Goal**: A service that takes a query + candidate chunk list and returns a relevance-reordered list.
- **Why it exists**: Initial retrieval (bi-encoder) is fast but coarse; reranking (cross-encoder) is slow but precise — used only on the small top-k set.
- **Problem it solves**: Improves precision of what actually reaches the LLM.
- **Concepts to learn first**: Bi-encoder vs cross-encoder tradeoffs, why reranking only makes sense on a small candidate set.
- **Technologies**: BAAI bge-reranker-v2-m3.
- **Files created**: `backend/app/infrastructure/reranker.py`.
- **Expected output**: Given a query and 20 candidate chunks, returns them reordered by relevance score.
- **Definition of Done**: On the M34 eval set, reranking measurably improves top-1 relevance versus hybrid-search-alone ordering (manual comparison, scores recorded).

### M36 — Wire reranker into retrieval pipeline
- **Goal**: `POST /search` optionally reranks its top-k before returning.
- **Why it exists**: Makes reranking part of the real request path, not just a standalone service.
- **Problem it solves**: Closes the retrieval-quality loop before LLM integration begins.
- **Concepts to learn first**: Nothing new — integration only.
- **Technologies**: Same as M35.
- **Files created**: `backend/app/services/retrieval_service.py` (extended).
- **Expected output**: Search responses include a reranked-relevance score alongside vector-similarity score.
- **Definition of Done**: Latency of the full retrieve+rerank path measured and logged (informs Phase 12's latency budget).

---

## PHASE 11 — LLM Integration

### M37 — Ollama client wrapper (interface-based)
- **Goal**: An `LLMProvider` interface with an Ollama implementation, model name configurable via env var (Qwen3 default, Gemma3 supported).
- **Why it exists**: Keeps the LLM swappable, per the architecture's abstraction principle.
- **Problem it solves**: Avoids hardcoding one model/provider throughout the codebase.
- **Concepts to learn first**: Local LLM serving via Ollama, streaming vs non-streaming completions, prompt/response token limits.
- **Technologies**: Ollama, Qwen3.
- **Files created**: `backend/app/infrastructure/llm/base.py` (interface), `backend/app/infrastructure/llm/ollama_provider.py`.
- **Expected output**: `generate(prompt)` returns a text completion from the local Qwen3 model.
- **Definition of Done**: Swapping the configured model to Gemma3 (env var change only, no code change) still works.

### M38 — Citation-forcing prompt template
- **Goal**: A prompt template that injects retrieved chunks as context and instructs the model to cite sources inline.
- **Why it exists**: PRD requires every answer to include document/page/collection citations.
- **Problem it solves**: Without explicit prompting, LLMs answer without grounding.
- **Concepts to learn first**: Prompt engineering basics, context-window budgeting (how many chunks fit).
- **Technologies**: None new.
- **Files created**: `backend/app/services/prompt_templates.py`.
- **Expected output**: Given a question + 3 retrieved chunks, the model's answer references specific source chunks by an identifiable marker.
- **Definition of Done**: 5 manually reviewed sample answers all contain traceable citations back to the injected chunks.

### M39 — "No evidence → refuse" guardrail
- **Goal**: If retrieval returns nothing above a relevance threshold, the system returns a fixed "I don't have information on this" response instead of calling the LLM freely.
- **Why it exists**: PRD's explicit requirement: "the model should never answer without retrieved evidence."
- **Problem it solves**: Prevents hallucinated answers on out-of-corpus questions.
- **Concepts to learn first**: Relevance-score thresholding, the tradeoff between being too strict (refusing answerable questions) and too loose (hallucinating).
- **Technologies**: None new.
- **Files created**: `backend/app/services/rag_service.py` (guardrail check before LLM call).
- **Expected output**: An out-of-corpus question (e.g., about an unrelated topic) returns the fixed refusal, not a fabricated answer.
- **Definition of Done**: Threshold tuned against both an in-corpus and out-of-corpus test question set with zero false refusals on the in-corpus set.

### M40 — Prompt-injection sanitization pass
- **Goal**: Extracted document text is scanned for obvious instruction-like patterns (e.g., "ignore previous instructions") before being injected into the LLM context, and flagged/stripped.
- **Why it exists**: Uploaded documents are untrusted content from many users — indirect prompt injection is a real attack surface for this architecture.
- **Problem it solves**: Reduces risk of a malicious document hijacking the assistant's behavior.
- **Concepts to learn first**: Indirect prompt injection, why this can only ever be mitigation, not a full solve.
- **Technologies**: Python (regex/heuristic pass); no new dependency.
- **Files created**: `backend/app/services/guardrails.py`.
- **Expected output**: A test document containing an injected instruction has that portion flagged/neutralized before reaching the prompt.
- **Definition of Done**: A hand-crafted injection test document no longer alters the model's behavior on an unrelated question.

---

## PHASE 12 — Complete RAG Pipeline

### M41 — `/ask` endpoint (single-turn, non-streaming)
- **Goal**: One endpoint chaining retrieve → rerank → guardrail → LLM → citation-formatted response.
- **Why it exists**: This is the product's core value delivered end-to-end for the first time.
- **Problem it solves**: Proves the full RAG loop works as a single coherent feature, not disjoint pieces.
- **Concepts to learn first**: Nothing new — integration only.
- **Technologies**: All prior phases.
- **Files created**: `backend/app/api/v1/ask.py`, `backend/app/services/rag_service.py` (extended: `answer_question()`).
- **Expected output**: `POST /ask {"question": "..."}` returns `{answer, citations: [{doc, page, collection, excerpt}]}`.
- **Definition of Done**: 10 hand-picked realistic questions against sample uploaded documents each return a correct, cited answer or the correct refusal.

### M42 — Latency instrumentation
- **Goal**: Log retrieval time, rerank time, LLM time, and total time per `/ask` call.
- **Why it exists**: PRD's NFR (average response < 3s excluding LLM generation) is unverifiable without measurement.
- **Problem it solves**: Makes performance visible instead of assumed.
- **Concepts to learn first**: Structured logging, correlation/request IDs across async boundaries.
- **Technologies**: Python `logging`, structured (JSON) log format.
- **Files created**: `backend/app/core/logging.py`, `backend/app/api/v1/ask.py` (extended with timing).
- **Expected output**: Every `/ask` response is accompanied by a log line with per-stage timings and a request ID.
- **Definition of Done**: Retrieval+rerank latency (excluding LLM) measured against the <3s target across the 10-question test set from M41.

### M43 — Citation response schema finalized
- **Goal**: Lock down the exact citation shape (document name, page number, collection, highlighted paragraph) as a stable Pydantic schema.
- **Why it exists**: Frontend (Phase 15) will build against this contract — it must be finalized before that work starts.
- **Problem it solves**: Prevents breaking API changes once the frontend depends on the shape.
- **Concepts to learn first**: API contract stability, Pydantic response models.
- **Technologies**: Pydantic.
- **Files created**: `backend/app/schemas/answer.py`.
- **Expected output**: OpenAPI docs (`/docs`) show a fully typed, documented response schema for `/ask`.
- **Definition of Done**: Schema reviewed and declared frozen for v1 (documented in-code, not just implicit).

---

## PHASE 13 — Chat & Conversation Memory

### M44 — Conversation + Message tables
- **Goal**: Durable Postgres tables for conversations and their messages, scoped by org and user.
- **Why it exists**: PRD requires saved chat history; this must be durable storage, not cache.
- **Problem it solves**: Chat history surviving beyond a Redis TTL.
- **Concepts to learn first**: One-to-many modeling (conversation → messages), ordering by timestamp.
- **Technologies**: SQLAlchemy, Alembic.
- **Files created**: `backend/app/models/conversation.py`, `backend/app/models/message.py`, migrations.
- **Expected output**: A conversation with several messages persists across backend restarts.
- **Definition of Done**: Org-scoping (M15 pattern) verified on conversation access.

### M45 — Multi-turn context assembly
- **Goal**: `/ask` becomes conversation-aware: recent message history is included when forming the retrieval query and the LLM prompt.
- **Why it exists**: Follow-up questions ("what about semester 5?") are meaningless without prior turns.
- **Problem it solves**: Naive single-turn RAG fails on natural conversational follow-ups.
- **Concepts to learn first**: Context-window budgeting with history included, query rewriting/condensation techniques.
- **Technologies**: None new.
- **Files created**: `backend/app/services/rag_service.py` (extended), `backend/app/api/v1/chat.py` (replaces/extends `ask.py` with conversation_id).
- **Expected output**: A 2-turn conversation ("What's the attendance policy?" → "What about for semester 4 specifically?") produces a coherent second answer.
- **Definition of Done**: 5 hand-crafted multi-turn conversations all produce contextually correct follow-up answers.

### M46 — SSE streaming responses
- **Goal**: `/chat` streams tokens to the client as they're generated instead of waiting for the full answer.
- **Why it exists**: PRD requires streaming; also directly improves perceived latency.
- **Problem it solves**: Long LLM generations otherwise feel unresponsive.
- **Concepts to learn first**: Server-Sent Events, FastAPI streaming responses.
- **Technologies**: FastAPI `StreamingResponse`, SSE.
- **Files created**: `backend/app/api/v1/chat.py` (extended to stream).
- **Expected output**: A `curl` with `--no-buffer` shows tokens arriving incrementally, not all at once.
- **Definition of Done**: Citations are still correctly delivered at stream end (e.g., as a final SSE event) despite token-by-token streaming.

### M47 — Related-questions suggestion
- **Goal**: After each answer, return 2–3 suggested follow-up questions.
- **Why it exists**: PRD-listed chat feature improving discoverability of institutional knowledge.
- **Problem it solves**: Helps users who don't know what to ask next.
- **Concepts to learn first**: Nothing new — a small additional LLM call or prompt extension.
- **Technologies**: Same LLM provider.
- **Files created**: `backend/app/services/rag_service.py` (extended).
- **Expected output**: Each `/chat` response includes a `related_questions` array.
- **Definition of Done**: Suggested questions are topically relevant on the M41 test set (manual review).

---

## PHASE 14 — Rate Limiting & Hardening

### M48 — Rate limiting
- **Goal**: Auth and `/ask`/`/chat` endpoints are rate-limited per user.
- **Why it exists**: Explicit NFR; also protects the (expensive) LLM/embedding pipeline from abuse.
- **Problem it solves**: Prevents a single client from degrading service for everyone.
- **Concepts to learn first**: Token bucket/sliding window rate-limiting concepts.
- **Technologies**: slowapi (Redis-backed).
- **Files created**: `backend/app/core/rate_limit.py`.
- **Expected output**: Exceeding the configured request rate returns 429.
- **Definition of Done**: Rate limit verified per-user (not global) so one user's abuse doesn't lock out others in the same org.

### M49 — Malware scanning on upload
- **Goal**: Uploaded files are scanned before processing; infected files are rejected.
- **Why it exists**: Files come from many untrusted end users; "file validation" in the PRD should include this.
- **Problem it solves**: Prevents malware from entering shared storage.
- **Concepts to learn first**: ClamAV basics, scan-before-process pipeline placement.
- **Technologies**: ClamAV (containerized).
- **Files created**: `backend/app/services/document_service.py` (extended), add `clamav` service to `docker/docker-compose.yml`.
- **Expected output**: The EICAR test file is rejected with a clear error; a clean file passes through unaffected.
- **Definition of Done**: Scan runs before the file is persisted to MinIO (reject before storage, not after).

### M50 — Centralized error model
- **Goal**: All API errors map to the documented error taxonomy (ValidationError, AuthenticationError, AuthorizationError, NotFoundError, ConflictError, InternalServerError) with consistent JSON shape.
- **Why it exists**: Architecture doc specifies this as a requirement; ad-hoc error handling has accumulated across Phases 1–13 and needs consolidating.
- **Problem it solves**: Inconsistent error responses are hard for the frontend to handle generically.
- **Concepts to learn first**: FastAPI exception handlers, custom exception classes.
- **Technologies**: FastAPI.
- **Files created**: `backend/app/core/exceptions.py`, `backend/app/main.py` (extended: exception handler registration).
- **Expected output**: Every existing endpoint's error responses now follow one consistent `{error_type, message, details}` shape.
- **Definition of Done**: A sweep of all endpoints built so far confirms no raw/unhandled 500s leak stack traces to the client.

---

## PHASE 15 — Frontend

### M51 — Auth pages + protected routing
- **Goal**: Login/register pages; JWT stored client-side; route guards redirect unauthenticated users.
- **Why it exists**: Every other UI screen needs an authenticated session.
- **Problem it solves**: Real user-facing entry point to the system.
- **Concepts to learn first**: React Router, token storage tradeoffs (httpOnly cookie vs localStorage), protected route patterns.
- **Technologies**: React, React Router, TanStack Query.
- **Files created**: `frontend/src/pages/Login.tsx`, `frontend/src/pages/Register.tsx`, `frontend/src/api/auth.ts`, `frontend/src/hooks/useAuth.ts`.
- **Expected output**: A user can register, log in, and reach a protected dashboard; a logged-out user is redirected to `/login`.
- **Definition of Done**: Refreshing the page preserves the session (token persistence verified); logout clears it.

### M52 — Upload UI
- **Goal**: Drag-and-drop batch upload with per-file progress and collection selection.
- **Why it exists**: Faculty/Admin need a real interface for the upload capability built in Phase 4.
- **Problem it solves**: Makes document ingestion usable without curl/Postman.
- **Concepts to learn first**: File input handling in React, multipart form uploads, progress events.
- **Technologies**: React, TanStack Query, shadcn/ui.
- **Files created**: `frontend/src/pages/Upload.tsx`, `frontend/src/components/FileDropzone.tsx`, `frontend/src/api/documents.ts`.
- **Expected output**: Selecting 5 files uploads them all, each showing live status (pending/processing/processed/failed).
- **Definition of Done**: A failed upload (bad file type) shows a clear inline error, not a silent failure.

### M53 — Chat UI
- **Goal**: A chat interface with streaming answer display, citation panel, and related-question chips.
- **Why it exists**: The primary end-user surface of the whole product.
- **Problem it solves**: Makes `/chat` (Phase 13) usable by Students/Faculty.
- **Concepts to learn first**: Consuming SSE streams in the browser, incremental UI updates.
- **Technologies**: React, EventSource/fetch streaming, shadcn/ui.
- **Files created**: `frontend/src/pages/Chat.tsx`, `frontend/src/components/ChatMessage.tsx`, `frontend/src/components/CitationCard.tsx`, `frontend/src/api/chat.ts`.
- **Expected output**: Typing a question streams a live-updating answer with clickable citations that show the source excerpt.
- **Definition of Done**: A full multi-turn conversation works end-to-end in the browser, matching the backend behavior verified in M45.

### M54 — Admin panel
- **Goal**: User management, document management (view/delete), and an analytics view for Admin-role users.
- **Why it exists**: PRD-required Administrator capabilities.
- **Problem it solves**: Gives non-technical staff a way to manage their org's content and users.
- **Concepts to learn first**: Role-conditional UI rendering, data tables with pagination/sorting.
- **Technologies**: React, TanStack Query, shadcn/ui.
- **Files created**: `frontend/src/pages/admin/Users.tsx`, `frontend/src/pages/admin/Documents.tsx`, `frontend/src/pages/admin/Analytics.tsx`.
- **Expected output**: An Admin user can deactivate a user and delete a document, both reflected immediately in the UI.
- **Definition of Done**: A Student-role user cannot reach `/admin/*` routes at all (client-side guard) and gets 403 if they hit the API directly (server-side guard already exists from M14).

### M55 — Super Admin panel
- **Goal**: Cross-organization management and global analytics view.
- **Why it exists**: PRD-required Super Admin capabilities, distinct from single-org Admin.
- **Problem it solves**: Platform operator needs a view above any single tenant.
- **Concepts to learn first**: Nothing new — same patterns as M54, applied without org scoping.
- **Technologies**: React, TanStack Query.
- **Files created**: `frontend/src/pages/superadmin/Organizations.tsx`, `frontend/src/pages/superadmin/GlobalAnalytics.tsx`; backend: `backend/app/api/v1/superadmin.py` (new endpoints bypassing single-org scoping, still role-gated).
- **Expected output**: A Super Admin sees all organizations and aggregate usage stats across them.
- **Definition of Done**: Non-Super-Admin roles cannot reach this data via any route (backend-enforced, not just hidden in UI).

---

## PHASE 16 — Analytics

### M56 — Analytics event capture
- **Goal**: Key events (upload, query, failed query) are recorded with latency and metadata.
- **Why it exists**: PRD requires tracking uploads, queries, latency, most-searched topics, failed queries.
- **Problem it solves**: Without capture, the Analytics dashboards (M54/M55) have nothing to show.
- **Concepts to learn first**: Event logging patterns, avoiding capture on the hot path blocking responses (fire-and-forget or queued).
- **Technologies**: PostgreSQL (an `analytics_events` table), Arq (async write).
- **Files created**: `backend/app/models/analytics_event.py`, migration, `backend/app/services/analytics_service.py`.
- **Expected output**: Every upload and `/ask`/`/chat` call produces a corresponding event row.
- **Definition of Done**: Capturing an event never adds noticeable latency to the user-facing request (verified by comparing M42 timings before/after).

### M57 — Analytics query endpoints
- **Goal**: Endpoints aggregating the raw events into the metrics the PRD names (most searched topics, failure rate, latency trends).
- **Why it exists**: Turns raw events into the dashboards built in M54/M55.
- **Problem it solves**: Raw event rows aren't directly useful to an Admin.
- **Concepts to learn first**: SQL aggregation (GROUP BY, time bucketing).
- **Technologies**: PostgreSQL, SQLAlchemy.
- **Files created**: `backend/app/api/v1/analytics.py`.
- **Expected output**: `GET /analytics/summary` returns query counts, average latency, top topics, and failure rate for the requesting org.
- **Definition of Done**: M54's Analytics tab renders real data (not mock data) from this endpoint.

---

## PHASE 17 — Evaluation & Monitoring

### M58 — Langfuse integration
- **Goal**: Every retrieval + LLM call in `/ask`/`/chat` is traced in Langfuse.
- **Why it exists**: PRD-required monitoring/observability tool for LLM-specific behavior (prompts, latency, token usage) that generic logging doesn't capture well.
- **Problem it solves**: Debugging "why did the model answer this way" without tracing is guesswork.
- **Concepts to learn first**: LLM observability concepts (traces, spans, generations).
- **Technologies**: Langfuse, add `langfuse` service to `docker/docker-compose.yml`.
- **Files created**: `backend/app/infrastructure/tracing.py`, instrumentation added to `rag_service.py`.
- **Expected output**: Every `/ask` call produces a viewable trace in the Langfuse UI showing retrieval results and the exact prompt sent to the LLM.
- **Definition of Done**: A trace can be used to diagnose a deliberately-triggered bad answer (manual test).

### M59 — RAGAS evaluation harness
- **Goal**: A repeatable script scoring the RAG pipeline on faithfulness, recall, and precision against a golden question/answer set.
- **Why it exists**: PRD requires measurable quality, not just "it seems to work."
- **Problem it solves**: Gives a regression signal — future changes (chunking, reranking, prompt tweaks) can be checked against a baseline instead of eyeballing.
- **Concepts to learn first**: RAGAS metrics definitions, building a golden evaluation dataset.
- **Technologies**: RAGAS.
- **Files created**: `backend/scripts/evaluate.py`, `backend/scripts/golden_dataset.json`.
- **Expected output**: Running the script produces faithfulness/recall/precision scores for the current pipeline.
- **Definition of Done**: A baseline score is recorded (documented, e.g., in `NOTES.md`) as the reference point for all future pipeline changes.

---

## PHASE 18 — Production Deployment

### M60 — Production Docker Compose
- **Goal**: A separate `docker-compose.prod.yml` with environment separation, secrets handling, and resource limits — no dev-only conveniences (hot reload, exposed debug ports).
- **Why it exists**: Dev Compose config is unsafe/unsuited for production (bind mounts, default passwords, no resource caps).
- **Problem it solves**: Prevents dev-environment assumptions leaking into production.
- **Concepts to learn first**: Docker secrets/env separation, resource limits (`mem_limit`, `cpus`), production vs dev build targets.
- **Technologies**: Docker Compose.
- **Files created**: `docker/docker-compose.prod.yml`, `.env.production.example`.
- **Expected output**: The full stack runs under the prod compose file with no dev-only ports exposed and secrets sourced from environment, not hardcoded.
- **Definition of Done**: A diff review between dev and prod compose files confirms no debug/hot-reload settings leaked into prod.

### M61 — Nginx reverse proxy + HTTPS
- **Goal**: Nginx terminates TLS and routes to frontend/backend; HTTP redirects to HTTPS.
- **Why it exists**: Explicit security NFR (HTTPS).
- **Problem it solves**: Encrypts traffic, provides a single public entry point.
- **Concepts to learn first**: Reverse proxy basics, TLS termination, Let's Encrypt/certbot (or a provided cert).
- **Technologies**: Nginx.
- **Files created**: `docker/nginx/nginx.conf`, `docker/nginx/Dockerfile`; Nginx service added to `docker-compose.prod.yml`.
- **Expected output**: The site is reachable over HTTPS; HTTP requests redirect.
- **Definition of Done**: SSL Labs (or equivalent) check shows no critical TLS misconfiguration.

### M62 — CI pipeline
- **Goal**: On every PR, GitHub Actions runs lint + backend tests + frontend tests + a build check.
- **Why it exists**: "Tests pass" is part of the project's own Definition of Done for every phase — CI is what actually enforces that going forward.
- **Problem it solves**: Prevents regressions from merging silently.
- **Concepts to learn first**: GitHub Actions workflow syntax, job/step structure, caching dependencies for speed.
- **Technologies**: GitHub Actions, pytest, Vitest.
- **Files created**: `.github/workflows/ci.yml`.
- **Expected output**: A PR with a deliberately broken test shows a failing CI check.
- **Definition of Done**: CI is required (branch protection) before merge to main.

### M63 — CD pipeline
- **Goal**: On merge to main, build and push Docker images (and optionally deploy).
- **Why it exists**: Closes the loop from "code merged" to "running in production" without manual steps.
- **Problem it solves**: Manual deploys are error-prone and undocumented.
- **Concepts to learn first**: Container registries, image tagging strategy, deployment triggers.
- **Technologies**: GitHub Actions, Docker registry (GitHub Container Registry).
- **Files created**: `.github/workflows/cd.yml`.
- **Expected output**: Merging to main produces a new tagged image in the registry automatically.
- **Definition of Done**: A full deploy from a clean environment using only the pushed images succeeds.

### M64 — Backup strategy
- **Goal**: Scheduled Postgres dumps and Qdrant/MinIO snapshots, with a documented restore procedure.
- **Why it exists**: No prior milestone addresses data durability beyond the running containers — this is the last gap before calling v1 "production-ready."
- **Problem it solves**: Data loss recovery; also the honest answer to the 99.9% availability aspiration flagged during planning.
- **Concepts to learn first**: Backup scheduling (cron), Postgres `pg_dump`, Qdrant snapshot API, restore testing (a backup nobody has restored isn't verified).
- **Technologies**: `pg_dump`, Qdrant snapshot API, MinIO mirroring/versioning, cron (or a scheduled GitHub Action).
- **Files created**: `docker/scripts/backup.sh`, `docker/scripts/restore.sh`, `docs/DISASTER_RECOVERY.md`.
- **Expected output**: A scheduled backup runs and produces restorable artifacts.
- **Definition of Done**: A full restore into a clean environment is actually performed once and verified to work — not just assumed.

---

## How to use this document

Work top to bottom. Each milestone assumes every prior one is done. Do not skip ahead to "make it look finished" — a later milestone built on a skipped one (e.g., Chat before Auth) will need rework once the gap surfaces. Update this file if a milestone's scope changes during implementation — it should stay a living plan, not a snapshot.
