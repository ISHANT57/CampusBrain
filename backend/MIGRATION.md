# Migration: free-tier-deployable backend

Removes every self-hosted piece Render's free tier can't run (a separate
worker process, real Redis, a self-hosted embedding model needing its own
RAM/disk) so the backend deploys at $0/month on Render + Neon + Cloudflare R2
+ Qdrant Cloud. No public API route's request/response shape changed — every
difference below is internal or environment configuration.

## What changed

### 1. Embeddings are now behind a provider abstraction

`app/infrastructure/embeddings/` (new package) replaces the single
`app/infrastructure/embeddings.py` module that called a local Ollama instance
directly.

- `base.py` — `EmbeddingProvider` Protocol: `embed(text) -> list[float]` and a
  `dimension` property. Mirrors the existing `LLMProvider` Protocol in
  `app/infrastructure/llm/base.py` on purpose — same shape, same pattern.
- `gemini_provider.py` — `GeminiEmbeddingProvider`, calling Gemini's free-tier
  `embedContent` REST endpoint directly via `httpx` (no SDK — one JSON call
  didn't justify a dependency, consistent with `OpenRouterProvider`).
- `provider.py` — `get_embedding_provider()`, the single factory function.
  Every caller (`retrieval_service.py`, `document_processing_service.py`,
  `vector_store.py`) goes through this, never instantiates a provider class
  directly.

**Adding OpenAI / Voyage AI / Jina AI / Ollama later:** write a class
implementing `EmbeddingProvider` (an `embed()` method and a `dimension`
property), then change the one line in `provider.py` that returns
`GeminiEmbeddingProvider()`. Nothing in `retrieval_service.py`,
`document_processing_service.py`, or the RAG pipeline (`rag_service.py`,
`prompt_templates.py`) needs to change — none of them import a concrete
provider, only `get_embedding_provider()`.

**Known follow-up, not fixed here:** `RELEVANCE_THRESHOLD = 0.35` in
`rag_service.py`'s no-evidence guardrail was calibrated against BGE-M3's
cosine-similarity distribution. A different embedding model can produce a
different distribution for similar/dissimilar text, so this threshold may
need recalibrating against real queries once Gemini embeddings are live —
watch for the guardrail firing too often (refusing answerable questions) or
too rarely (answering off-corpus questions) and adjust the constant.

### 2. Qdrant collections auto-recreate on a dimension change

`vector_store.ensure_collection()` now checks the existing collection's
configured vector size against the active provider's `dimension`, and
recreates the collection (delete + create) if they differ, instead of
assuming a collection created for a previous provider is still valid. Qdrant
rejects upserting a vector whose length doesn't match the collection's
configured size, so without this check, switching providers would turn every
upload into a hard failure rather than a clean transition.

**This drops existing vectors for that org.** Recreating the collection does
not re-embed anything — every document in that org needs reprocessing
afterward (re-run `process_document`, e.g. by re-uploading, or add an admin
"reprocess" action if this becomes a recurring need) before search returns
results again. This only fires on an actual dimension mismatch, so a normal
deploy with an unchanged `EMBEDDING_MODEL`/`EMBEDDING_DIM` never touches
existing collections.

### 3. Redis is gone. Two things used it; both work without it now

- **Rate limiting** (`core/rate_limit.py`) — `slowapi`'s `Limiter` no longer
  gets a `storage_uri`, so it falls back to in-memory counters. Correct for a
  single free-tier instance; **if this backend ever runs multiple processes
  or instances**, the limiter counts per-process and effectively under-limits
  in aggregate (see the comment in `docker-compose.prod.yml` next to
  `--workers 4`). At that point, point `storage_uri` at a shared store
  (Upstash Redis's free tier is the natural fit) rather than reducing worker
  count.
- **Document processing queue** (`api/v1/documents.py`) — `arq` enqueuing
  `process_document` onto a Redis-backed queue is replaced by FastAPI's
  `BackgroundTasks.add_task(...)`, running the same function in-process after
  the response is sent. `process_document` itself never depended on the
  queue transport — it only reads/writes Postgres, object storage, and
  Qdrant — so this removed indirection, not capability.

`app/workers/` (`pool.py`, `worker.py`, `tasks.py`) is deleted.
`process_document` now lives in
`app/services/document_processing_service.py`, as a plain sync function
(previously `async def` with no `await` in its body — an artifact of arq's
calling convention, not a real need for async).

### 4. Ollama is gone

Was serving embeddings only (the LLM already went out to OpenRouter). No
self-hosted equivalent replaces it — that's the point; the embedding
provider abstraction above is what makes this possible without hardcoding a
new host to call.

## Environment variables

| Removed | Replaced by |
|---|---|
| `REDIS_PORT` | — (no Redis service) |
| `OLLAMA_PORT` | — (no Ollama service) |
| *(embedding_model/embedding_dim were code defaults, not env-configurable)* | `GEMINI_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` |

`EMBEDDING_MODEL` defaults to `gemini-embedding-001`, `EMBEDDING_DIM` to `768`
(one of Gemini's documented Matryoshka truncation points — smaller than the
model's native 3072 dims to fit comfortably in Qdrant Cloud's free 1GB
cluster). Change them together, never one alone — see the dimension-migration
behavior above.

## Not changed

Every route's request/response shape: `POST /documents` still returns the
document immediately at `PENDING`/`PROCESSING` and the client still polls
`GET /documents/{id}` for status — callers can't tell background processing
moved from a Redis queue to `BackgroundTasks` by looking at the API. `/ask`
and `/chat` are untouched; they only ever called `get_llm_provider()` and
(transitively, via retrieval) the embedding provider, never Redis or arq
directly.
