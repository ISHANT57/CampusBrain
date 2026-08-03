# Production Engineering Concepts in CampusBrain

A one-page index: every production concept in this system, why it exists, where it
lives, what it cost, and — the part most project write-ups omit — **whether it is
actually finished**.

This file is deliberately short. It links into the deep documents rather than
restating them:

| For | Read |
|---|---|
| Why a decision was made, with rejected alternatives | [`ENGINEERING_ROADMAP.md`](ENGINEERING_ROADMAP.md) (ADR-001 … ADR-017) |
| Interview-depth Q&A per concept | [`INTERVIEW_HANDBOOK.md`](INTERVIEW_HANDBOOK.md) |
| Ranked findings and pillar scorecard | [`PRODUCTION_REVIEW.md`](PRODUCTION_REVIEW.md) |
| How to run and verify any of it | [`OPERATIONS_RUNBOOK.md`](OPERATIONS_RUNBOOK.md) |
| Every architecture diagram | [`DIAGRAMS.md`](DIAGRAMS.md) |

**Status vocabulary**, used honestly throughout:

- **Built** — implemented, exercised by tests, and running in the deployed service.
- **Partial** — real, with a named limitation stated in the row.
- **Rejected** — evaluated and deliberately not shipped. The reasoning is the artifact.
- **Gap** — known missing. Listed because a gap you have named is not the same as one you have not noticed.

---

## 1. Reliability & durability

| Concept | Why it exists | Where | Trade-off accepted | Status |
|---|---|---|---|---|
| **Durable job queue** | An uploaded document must not vanish because the process died between two steps. Ingestion is minutes long; a request is not. | [`ingestion_queue.py`](backend/app/services/ingestion_queue.py) | Postgres is slower than Redis, but needs no second stateful system to reason about. | **Built** |
| **Atomic job claim** | Two workers must never process one document twice. `SELECT … FOR UPDATE SKIP LOCKED` makes it impossible by construction rather than by convention. | [`ingestion_queue.py`](backend/app/services/ingestion_queue.py) | Postgres-specific SQL; not portable to another engine. | **Built** — proven in [`test_integration_api.py`](backend/tests/test_integration_api.py) |
| **Lease + reaper** | A worker killed mid-job leaves a row claimed forever. The reaper resets rows whose 15-minute lease expired. | [`ingestion_queue.py`](backend/app/services/ingestion_queue.py) | Up to 15 minutes before a crashed job restarts. | **Built** |
| **Bounded retry** | `attempts` increments **at claim time**, not on success, so a crash loop terminates instead of retrying forever. | [`ingestion_queue.py`](backend/app/services/ingestion_queue.py) | A job that fails for a transient reason can exhaust attempts. | **Built** |
| **Idempotent re-index** | New vectors are written **before** old ones are deleted, so a crash mid-embed degrades the index instead of destroying it. | [`document_processing_service.py`](backend/app/services/document_processing_service.py) | Brief window where both old and new chunks exist. | **Built** |
| **Classified retry** | Retrying a 400 is pointless; retrying a 503 is correct. Errors are classified before any retry decision. | [`retry.py`](backend/app/infrastructure/retry.py) | More code than a blanket retry wrapper. | **Built** |
| **Background worker** | Long ingestion leaves the request path so uploads return `202 Accepted` immediately. | [`main.py`](backend/app/main.py) lifespan | **In-process `asyncio` task, not a separate service** — the free tier has no worker type, so it shares a fate with the API. Migration trigger is written down (ADR-012). | **Partial** |

## 2. Trust & evidence

This is the section the project is actually about.

| Concept | Why it exists | Where | Trade-off accepted | Status |
|---|---|---|---|---|
| **Refuse before generating** | Below a semantic-similarity floor the corpus does not contain the answer, and a fluent fabrication is worse than "I don't know". | [`rag_service.py`](backend/app/services/rag_service.py) | The threshold (`0.35`) is **unvalidated** — see Gaps. | **Built** |
| **Grounding metadata, not a confidence label** | A High/Medium/Low badge requires cutoffs. None were validated against labelled data, so the API returns the **measurements** — closest-match score *paired with the floor it was compared against*, plus cited-vs-retrieved counts. | [`answer.py`](backend/app/schemas/answer.py), [`GroundingBar.tsx`](frontend/src/components/chat/GroundingBar.tsx) | Requires the reader to interpret numbers instead of trusting a label. That is the point. | **Built** (ADR-017) |
| **Citations survive parsing** | `[n]` markers become superscripts via a syntax-tree plugin, so a marker inside `` `results[1]` `` is left alone and no raw HTML from LLM output is ever rendered. | [`remarkCitations.ts`](frontend/src/components/chat/markdown/remarkCitations.ts) | More code than a regex, and `rehype-raw` permanently excluded. | **Built** — 18 checks, `npm run verify:markdown` |
| **Retrieved ≠ cited** | The sources panel shows documents being *read* during generation, then narrows to those actually *cited*. Conflating the two overstates the evidence. | [`SourceCard.tsx`](frontend/src/components/chat/SourceCard.tsx) | Two visual states to design instead of one. | **Built** (ADR-017) |
| **Source deduplication** | Five chunks from one handbook is **one** source. Rendering five cards inflates apparent evidence breadth. | [`SourceCard.tsx`](frontend/src/components/chat/SourceCard.tsx) | "3 sources" counts documents while markers count chunks, so each card must state its markers. | **Built** |
| **Context sanitisation** | Retrieved document text reaches an LLM prompt, so it is untrusted input and is stripped before injection. | [`guardrails.py`](backend/app/services/guardrails.py) | Cannot defeat every prompt-injection variant. | **Partial** |

## 3. Multi-tenancy & security

| Concept | Why it exists | Where | Trade-off accepted | Status |
|---|---|---|---|---|
| **Tenant isolation at the data layer** | If one institution can read another's documents the product is finished. `org_id` comes from a **verified credential**, never a request parameter. | [`base.py`](backend/app/repositories/base.py) `OrgScopedRepository` | Every query must go through the scoped repository; a raw query bypasses the guard. | **Built** — cross-tenant 404s tested |
| **Per-org vector collections** | Isolation in the vector store too, not only in Postgres. | [`vector_store.py`](backend/app/infrastructure/vector_store.py) | Collection count grows with tenants; migration path to a shared collection with a tenant filter is documented. | **Built** |
| **RBAC** | Access is a role decision checked at the boundary, not a UI concern. | [`dependencies.py`](backend/app/core/dependencies.py) `require_role` | — | **Built** — tested across anonymous / student / admin |
| **Rate limiting** | One noisy client must not exhaust a shared, finite model quota. Buckets are keyed on a *verified* credential, so nobody can mint a fresh bucket per request. | [`rate_limit.py`](backend/app/core/rate_limit.py) | **Storage is in-process.** Correct at one worker; needs shared state at two. | **Partial** |
| **Signed URLs** | Documents are served by time-limited URL (15 min) rather than proxying bytes through a 512 MB process. | [`documents.py`](backend/app/api/v1/documents.py) | URL is valid until expiry if leaked. | **Built** |
| **Audit log — fails closed** | Written in the **same transaction** as the mutation it records. An unaudited change is worse than a slow one. | [`audit_service.py`](backend/app/services/audit_service.py) | A failing audit write fails the user's request, by design. | **Built** |
| **Security headers** | `nosniff`, `DENY`, `no-referrer` on every response, including 404s and 500s. | [`main.py`](backend/app/main.py) | No CSP or HSTS — reasons recorded in ADR-016 (this serves JSON, and Render owns TLS). | **Built** |

## 4. Observability & cost

| Concept | Why it exists | Where | Trade-off accepted | Status |
|---|---|---|---|---|
| **Structured logging** | One JSON object per line, so logs are queryable rather than greppable. | [`observability.py`](backend/app/core/observability.py) | Less readable by eye without `jq`. | **Built** |
| **Correlation IDs** | One request ID ties an answer, its cost row, and its evaluation trace together across three tables. | [`observability.py`](backend/app/core/observability.py) | Ambient state via `ContextVar` rather than explicit parameters. | **Built** |
| **Tenant/user log context** | Reset at request start — without it, an anonymous request following an authenticated one logs the **previous** caller's identity on a reused event-loop task. | [`main.py`](backend/app/main.py) middleware | — | **Built** — the leak has its own test |
| **Liveness ≠ readiness** | "Is the process alive" and "can it serve traffic" are different questions with different answers. Storage being down is reported but **not** fatal, because chat never reads a blob. | [`main.py`](backend/app/main.py) | Three endpoints to explain instead of one. | **Built** |
| **Cost tracking — fails open** | Real provider token usage per answer, attributed to org / user / document. Opposite contract to the audit log: a cost row must **never** break an answer. | [`usage_service.py`](backend/app/services/usage_service.py) | Cost data can be silently incomplete under failure. | **Built** |
| **RED metrics** | In-process counters and latency percentiles (retrieval, generation, time-to-first-token measured separately). | [`metrics.py`](backend/app/core/metrics.py) | Resets on restart — an operational view, not a monitoring system. | **Partial** |
| **Evaluation traces** | Records the query that *actually ran*, retrieved chunks with scores, and what was cited — the substrate a future scoring harness needs. | [`eval_service.py`](backend/app/services/eval_service.py) | Storage grows per answer. | **Built** |

## 5. Retrieval

| Concept | Why it exists | Where | Trade-off accepted | Status |
|---|---|---|---|---|
| **Hybrid retrieval** | Semantic search misses exact proper nouns; keyword search misses paraphrase. Both arms run. | [`retrieval_service.py`](backend/app/services/retrieval_service.py) | Two indexes to maintain. | **Built** |
| **RRF fusion on rank, not score** | Cosine similarity and Postgres `ts_rank` are **not comparable scales** — summing them lets one arm silently dominate. | [`retrieval_service.py`](backend/app/services/retrieval_service.py) | Loses score magnitude. Consequence: the semantic score is retained *separately*, because the refusal threshold must read it — thresholding on the fused score would refuse nearly everything. | **Built** |
| **Embedding cache** | Re-embedding an identical query is wasted latency and spend. | [`cache.py`](backend/app/infrastructure/cache.py) | Cache invalidation on model change. | **Built** |
| **Redis for caching only** | A lost cache entry costs latency; a lost queue job costs data. Those failures must not share a system. | [`test_redis_usage_boundary.py`](backend/tests/test_redis_usage_boundary.py) | A test asserting on *source files* rather than behaviour — unusual, but conventions rot and tests do not. | **Built** (ADR-015) |
| **SSE streaming** | Answers take seconds; the reader should see them arrive. Citation renumbering needs the whole answer, so it is deferred to one final structured event. | [`chat.py`](backend/app/api/v1/chat.py) | One-way transport only; no bidirectional channel. | **Built** |

## 6. Delivery

| Concept | Why it exists | Where | Trade-off accepted | Status |
|---|---|---|---|---|
| **CI: migrations from empty** | Catches a migration that works against an already-migrated dev database but not from scratch. | [`ci.yml`](.github/workflows/ci.yml) | — | **Built** — and it *would* have caught the outage below, had anyone checked it was green |
| **CI: lint + fast test tier** | 87 tests against a real Postgres service container on every PR. | [`ci.yml`](.github/workflows/ci.yml) | Qdrant and object storage are **not** in CI, so those tests run locally only. Named rather than hidden. | **Partial** |
| **Layered architecture** | `api → services → repositories → infrastructure`. A layer may call downward, never upward. | `backend/app/` | Boilerplate for trivial operations. | **Built** |

---

## 7. Deliberately rejected

The reasoning is the deliverable. Each of these was considered and declined.

| Rejected | Why |
|---|---|
| **Cross-encoder reranker** | Hybrid retrieval already surfaced the correct chunk in the top 2, and all `top_k=5` chunks reach the LLM regardless of order — so reranking would optimise a value nothing consumes. Cost: ~2 GB of `torch` on a 512 MB tier. **Honest caveat: this rested on a handful of manual queries, not a golden set. Directionally right, not rigorous — flagged for re-test.** Three revisit triggers recorded (ADR-006). |
| **A confidence label** | Requires cutoffs nothing validated. See §2. |
| **Recall / precision / groundedness metrics** | All three need a labelled golden set that does not exist. Two tests assert these keys never appear in any response — an invented metric is worse than a missing one, because a blank gets questioned and a number gets quoted. |
| **`rehype-raw` in the answer renderer** | Would allow arbitrary HTML from LLM output — an XSS surface accepted in exchange for a superscript. |
| **Syntax highlighting** | ~90 KB of `highlight.js` to colour code blocks in a corpus of admission handbooks and fee policies. |
| **Virtualised chat history** | Unmounts the DOM that citation scroll-to-source depends on, and breaks Ctrl+F, at message counts far below where it would pay. Revisit at p95 > 100 messages **with** measured jank. |
| **Kafka / Kubernetes / microservices** | No scale problem exists that they solve here. Adding them would be resume-driven architecture. |

## 8. Known gaps

| Gap | Consequence |
|---|---|
| **No labelled golden set** | Seven tuning decisions are formally blocked on it — including `RELEVANCE_THRESHOLD = 0.35`, which is the binary switch between "I don't know" and a confident fabrication. This is the highest-value next piece of work. |
| **Rate limit storage is in-process** | Correct at one worker, unenforceable at two. |
| **Worker shares a process with the API** | Ingestion load and request latency are coupled. |
| **Qdrant / storage tiers absent from CI** | Those tests require a local stack. |
| **`verify:markdown` not in CI** | Needs Node ≥ 23 for native type stripping; CI pins 20. |

---

## Why this file exists

Most project documentation lists what was built. The rows above that say **Partial**,
**Rejected** and **Gap** are the ones worth reading, because a system's design is
defined as much by what it refused to do as by what it shipped.

The claim this project makes is **production-oriented**, not production-ready — built
using production engineering principles, on free-tier infrastructure, with the
trade-offs and the unfinished parts written down rather than smoothed over.
