# CampusBrain — LinkedIn Carousel
## Content & Design Specification (10 Slides)

**Positioning (consistent on every slide):** *Production-Oriented AI Knowledge Platform*
**Framing language (use verbatim):**
- ✅ Production-Oriented AI Knowledge Platform
- ✅ Enterprise AI Knowledge Platform
- ✅ Built using Production Engineering Principles
- ✅ Production-Grade RAG Architecture
- ❌ never "AI chatbot," never "chat with PDFs," never "production ready" (we are honest: *production-oriented*, not yet *production-ready*)

**Primary message, stated once early and echoed at the end:** Most RAG projects stop after *Upload → Vector Search → LLM → Answer*. CampusBrain is built around everything that happens **after the demo works** — reliability, scalability, security, observability, cost control, failure recovery, and engineering trade-offs.

**Design system**
- Primary `#111827` (ink) · Secondary `#2563EB` (blue) · Accent `#14B8A6` (teal) · Background `#FFFFFF`
- Type: Inter / SF Pro Display / IBM Plex Sans. One display weight + one text weight. No more than 3 type sizes per slide.
- Mood: Apple Keynote + Stripe Docs + Linear. Massive whitespace, hairline rules, high contrast, minimal icons.
- Iconography: 1px-stroke line icons (Feather/Lucide style), teal or blue accent, never filled multicolor.
- Every slide: small section index top-left (e.g. `01 / PROBLEM`), one large headline, one muted subtitle, one focal diagram or card layout, and a footer rule.

---

## SLIDE 1 — Cover

**Slide title:** I didn't build another RAG chatbot.
**Subtitle:** I built a production-oriented AI knowledge platform.

**Project name:** CampusBrain
**Short subtitle (verbatim):** Production-Oriented AI Knowledge Platform

**Body content:**
- Eyebrow: `CASE STUDY · SYSTEM DESIGN · 2026`
- Headline (large, 2-line): *I didn't build another RAG chatbot.*
- Second line (blue/ink): *I built a production-oriented AI knowledge platform.*
- Bottom strip: `CampusBrain` + `Multi-tenant RAG · Cited answers · Built on production engineering principles`

**Visual layout suggestion:** Centered composition. Eyebrow top-center. Headline in the upper third, two lines with the second line in a muted treatment. Below the headline, a full-width minimal hero illustration (a node-graph or a three-tier "pipeline" motif) spanning the lower two-thirds. Project name set as a small wordmark lockup in the bottom-left, subtitle bottom-right. Huge whitespace — the hero is the visual anchor.

**Diagram recommendation:** A single abstract SVG: three soft horizontal tiers (Input / Processing / Output) connected by thin connector lines with small nodes — suggesting a system, not a chat bubble. Keep it geometric, gray with one teal node.

**Icon recommendations:** None heavy on the cover. Optional small glyphs inside the hero tiers (upload, cpu, spark).

**Design hierarchy:** 1) Hero illustration (visual weight), 2) Headline (type weight ~80–120px), 3) eyebrow + subtitle, 4) wordmark strip.

**Speaker notes:** Frame the whole post in one line: *"The demo is the easy part. This is a story about the 90% that comes after it."* Preview the arc — problem, architecture, decisions, trade-offs, failure, concepts, scale, lessons, close.

**Animation suggestion:** Hero nodes draw in left-to-right; headline fades up after 600ms.

---

## SLIDE 2 — The Problem

**Slide title:** The Gap Between Demo and System
**Subtitle:** Most RAG projects stop when the demo works.

**Body content — two columns:**

*Left column — "Typical RAG" (4 boxes, minimal):*
`Upload → Chunk → Embed → Answer`

*Right column — "Production RAG" (11 boxes):*
`Upload → Validate → Store → Queue → Worker → Embed → Vector DB → Monitor → Audit → Stream → Answer`

**Bottom takeaway (single line, high emphasis):** *The complexity that matters begins after the demo works.*

**Body copy (small, muted, one or two lines):** A demo answers a question. A system answers it *reliably, at scale, securely, auditable, within cost* — and survives a crash.

**Visual layout suggestion:** A "before / after" split. Left one-third: 4 stacked nodes under a muted header. Right two-thirds: 11 stacked nodes under a filled header, connected as a single flow. A vertical divider and a subtle "+7 steps" callout between them. The right column is visually denser to communicate added complexity.

**Diagram recommendation:** Two vertical flow SVGs. Left = 4 gray boxes in a straight line. Right = 11 boxes in a straight line with accent on the "Validate / Audit / Monitor" boxes to show production concerns. Connect with thin arrows.

**Icon recommendations:** Arrow-down connectors; a "plus/badge" glyph marking the extra production steps; a small "shield" on Validate and "eye" on Audit.

**Design hierarchy:** 1) Headline, 2) the two-column comparison (primary focal), 3) takeaway bar, 4) caption.

**Speaker notes:** *"The left column is where 90% of 'AI projects' stop. Everything I'm about to show is the right column — the work that makes it a platform rather than a notebook."*

---

## SLIDE 3 — Architecture

**Slide title:** System Architecture
**Subtitle:** One deployment graph, every layer production-aware.

**Body content — the diagram legend (as a compact list under the diagram):**
- **Frontend** — React + TypeScript on Vercel
- **API** — FastAPI, one uvicorn worker (deliberate — see trade-offs)
- **PostgreSQL** — Neon; source of truth, durable job queue, chat history
- **Supabase Storage** — S3-compatible object store for uploaded documents
- **Qdrant** — vector database; one collection per organization
- **Redis** — Upstash; query-embedding cache + rate limiting only
- **Worker** — in-process asyncio ingestion worker over the job table
- **LLM** — Gemini (embeddings `gemini-embedding-001` · answers `gemini-3.5-flash-lite`)
- **Streaming** — Server-Sent Events, token-by-token with a final citation event
- **Monitoring** — structured logs + correlation IDs, `/metrics`, separate liveness/readiness

**Body copy (one line):** *Hybrid retrieval (semantic + keyword, fused) with citation-enforced, no-evidence-refusal answers.*

**Visual layout suggestion:** Full-bleed architecture diagram centered. Frontend (top) → API (center) → a row of data services below (Postgres / Supabase / Qdrant / Redis), with the worker + LLM + streaming off to the right, and a thin "observability" band beneath everything. No more than 10 labeled nodes. Use neutral box borders, accent only for the data path.

**Diagram recommendation:** An SVG layered graph: Browser → React (Vercel) → FastAPI, fanning down to four data stores, and a right-hand column for Worker → LLM → SSE, with a horizontal observability rail at the bottom. Arrows show the request path in blue and the ingestion path in teal.

**Icon recommendations:** Database, cloud, cpu, arrow, radio (stream), gauge (monitor).

**Design hierarchy:** 1) Diagram (primary), 2) headline, 3) legend list.

**Speaker notes:** *"Read the architecture top to bottom as a request, then right-to-left as ingestion. Two paths share one deployment graph."*

**Animation suggestion:** Reveal tiers one at a time; animate the request path arrow then the ingestion path.

---

## SLIDE 4 — Production Engineering Decisions

**Slide title:** Decisions, Not Technologies
**Subtitle:** Every choice exists for a reason — here is why.

**Body content — 10 decision cards, each with the WHY:**

| Decision | Why it exists |
|---|---|
| **Durable ingestion** | An uploaded document must not silently vanish if the process dies. |
| **Postgres-backed job queue** | A queue you can inspect, migrate, and trust — not a black box. |
| **Redis for caching only** | Speed where it helps; never a second source of truth. |
| **Streaming responses (SSE)** | Honest token-by-token output; perceived latency drops. |
| **Audit logs** | Know who did what, when — a fail-closed contract. |
| **Health checks (liveness vs readiness)** | "Am I alive" and "can I serve traffic" are different questions. |
| **Correlation IDs** | One request, one traceable thread through every log line. |
| **Retry strategy** | Classify errors; only retry the retryable — never the fatal. |
| **Rate limiting** | Protect a shared, finite model quota from one noisy tenant. |
| **CI/CD** | Every merge is a linted, migrated, tested, deployable artifact. |

**Visual layout suggestion:** A 2-column × 5-row responsive card grid (or 3×3 + 1). Each card: a 1px-stroke icon in the top-left, a short bold label, and a one-line "why" in muted text. Heavy gridlines (hairline borders) so it reads as a table of decisions, not a feature dump.

**Diagram recommendation:** None needed — this is a card grid. Optionally a thin left color rail on each card (blue/teal alternating) for rhythm.

**Icon recommendations:** Shield (durable), Layers (queue), RefreshCw (cache), Radio (stream), FileText (audit), Activity (health), Hash (correlation), RotateCcw (retry), Gauge (rate limit), GitBranch (CI/CD).

**Design hierarchy:** 1) Headline/subtitle, 2) decision cards (primary), 3) footnote.

**Speaker notes:** *"Notice these are verbs and reasons, not logos. The deliverable is the reasoning, and the technology is the implementation detail."*

**Animation suggestion:** Cards stagger in; the "why" lines fade in after the labels.

---

## SLIDE 5 — Engineering Trade-offs

**Slide title:** Engineering Is About Trade-offs
**Subtitle:** Five decisions, each with a considered alternative.

**Body content — five trade-off cards (Problem / Chosen / Alternative / Trade-off):**

**1. Ingestion queue — why Postgres, not Redis/Arq**
- Problem: In-process background work can be killed mid-flight (15-min idle sleep, OOM).
- Chosen: Durable `ingestion_jobs` table; workers claim jobs with `SKIP LOCKED`; stale-lease reaper.
- Alternative: Redis/Arq or a separate worker fleet.
- Trade-off: Inspectability + durability for throughput; single-process coupling for zero extra infra.

**2. Redis — cache & rate-limit only**
- Problem: You need fast shared state without inventing a second datastore.
- Chosen: Redis only for query-embedding cache and rate-limit counters.
- Alternative: Redis as a source of truth / job store.
- Trade-off: Speed without dual-write complexity; Redis never holds the ground truth.

**3. Background workers — in-process asyncio**
- Problem: Long ingestion must not block the request, but free-tier has no worker service.
- Chosen: In-process `asyncio` worker over the durable job table.
- Alternative: Separate worker containers.
- Trade-off: Zero extra infrastructure for crash-coupling; scaled later to a real fleet.

**4. Object storage — S3-compatible (Supabase)**
- Problem: Files must be durable and URL-safe, not local to a stateless container.
- Chosen: S3-compatible bucket; opaque keys, no filesystem on the server.
- Alternative: Local disk / SQLite sidecar.
- Trade-off: Network dependency for durable, portable, horizontally-shareable blobs.

**5. Streaming — SSE over WebSocket/polling**
- Problem: Answers take seconds; the user should see them arrive.
- Chosen: Server-Sent Events, with a final structured citation event.
- Alternative: WebSockets or plain polling.
- Trade-off: Simple one-way HTTP streaming for no bidirectional channel; renumber citations at the end.

**6. Evaluation — honest signals now**
- Problem: You cannot tune what you cannot measure.
- Chosen: Label-free signals + `eval_traces` substrate; reranker was *measured and rejected* with data.
- Alternative: Full golden-set judge pipeline up front.
- Trade-off: Honest early signal for a rigorous, scored metric gate later.

**Visual layout suggestion:** Six stacked full-width rows, each split into four mini-cells (Problem / Chosen / Alternative / Trade-off) with column headers above. Reads like a decision log. Keep each cell to one sentence.

**Diagram recommendation:** None — a structured table. Optional small "→" between Chosen and Alternative cells to imply the pivot.

**Icon recommendations:** Scale/balance glyph (trade-off), or minimal per-row index numbers (`01`–`06`).

**Design hierarchy:** 1) Headline, 2) table columns, 3) row content.

**Speaker notes:** *"Engineers trust decisions that name what was given up. Every one of these rows names the alternative and the cost."*

---

## SLIDE 6 — Failure Handling

**Slide title:** What Happens When Things Go Wrong?
**Subtitle:** Designed for recovery, not for luck.

**Body content — scenario rows (Failure → Recovery):**

| Failure | Recovery |
|---|---|
| Instance sleeps after 15 min idle | Durable job table survives; worker re-claims on wake. |
| Worker crash mid-ingestion | Job stays leased/pending; stale-lease reaper reclaims and retries with backoff. |
| Embedding API timeout / daily quota | Classified error → backoff retry; daily quota is fail-open and surfaced, not silently swallowed. |
| Database reconnect | Connection pooling + retry on transient errors; readiness reflects real dependency state. |
| Partial indexing / destructive re-index | Upsert-then-prune idempotency — re-indexing can no longer destroy data. |

**Bottom takeaway (one line):** *A system is judged by how it behaves when it breaks.*

**Visual layout suggestion:** Top: a small job-lifecycle diagram. Bottom: five failure→recovery rows as paired cards (red/neutral failure glyph → teal recovery). Consistent left/right alignment so the eye moves failure→recovery.

**Diagram recommendation:** An SVG job-lifecycle state machine: `PENDING → RUNNING (lease) → DONE | FAILED`, with a loop back `RUNNING →(stale)→ PENDING` for the reaper. Small, labeled, minimal.

**Icon recommendations:** Power/cloud (sleep), AlertTriangle (crash), Clock (timeout), RefreshCw (reconnect), Layers (reindex), ShieldCheck (recovery).

**Design hierarchy:** 1) Headline, 2) lifecycle diagram, 3) scenario table.

**Speaker notes:** *"The 15-minute idle sleep and a 248-second ingestion pipeline were a real collision — this is the design that made it recover instead of lose data."*

---

## SLIDE 7 — Production Concepts

**Slide title:** Concepts Over Technologies
**Subtitle:** The ideas behind the system — each with a job to do.

**Body content — 15 concept cards, each with "why it exists":**

1. **Distributed Systems** — many parts must act as one; failure is the default assumption.
2. **Caching** — skip expensive work when the answer is already known.
3. **Retry Logic** — not all errors are equal; retry the retryable only.
4. **Observability** — you cannot fix what you cannot see.
5. **Audit Logging** — every consequential action leaves a durable record.
6. **Structured Logging** — machine-readable logs that a correlation ID can tie together.
7. **RBAC** — access is a role decision, not a feature flag.
8. **Multi-tenancy** — one platform, isolated per organization at the data layer.
9. **Hybrid Retrieval** — semantic recall plus exact-keyword precision, fused.
10. **Reranking** — measured, found to add no value on our data, and deliberately rejected.
11. **Streaming** — deliver the result as it is produced.
12. **Evaluation** — quality is a number you can move, or it is an opinion.
13. **Cost Tracking** — model spend is a ledger with an owner, not a surprise invoice.
14. **Background Workers** — long work leaves the request path.
15. **Health Checks** — liveness and readiness are different contracts.

**Visual layout suggestion:** A 3-column × 5-row grid of concept cards. Each card: a 1px-stroke icon, a bold concept name, and a one-line "why" in muted text. Generous gutters. Use the teal accent sparingly (e.g., on "Reranking" to flag it as a *negative* decision — proof of honest engineering).

**Diagram recommendation:** None — a concept grid. Keep the grid the hero.

**Icon recommendations:** Share2 (distributed), Zap (cache), RotateCcw (retry), Eye (observability), FileText (audit), AlignLeft (structured logs), Key (RBAC), Users (tenancy), Layers (hybrid), Filter (rerank), Radio (stream), Target (eval), Coins (cost), Cog (workers), Activity (health).

**Design hierarchy:** 1) Headline, 2) grid, 3) footnote.

**Speaker notes:** *"If I list technologies, you see a shopping list. If I list concepts, you see the reasoning of an engineer. Reranking is here as a rejected option — that honesty is the point."*

---

## SLIDE 8 — Scaling Journey

**Slide title:** The Scaling Journey
**Subtitle:** What breaks, what changes, what evolves — at each order of magnitude.

**Body content — six stages (10 → 100 → 1k → 10k → 100k → 1M), each with What breaks / What changes / What evolves:**

- **10 users** — Nothing; a single worker and free tier are enough. *What evolves:* nothing yet.
- **100 users** — Concurrent chats; per-org collections + RBAC start paying off. *Evolves:* auth/tenancy are now load-bearing.
- **1,000 users** — Hybrid retrieval's hand-rolled IDF filter becomes the latency floor. *Evolves:* move to real BM25 (ADR-005 revisit).
- **10,000 users** — Per-chunk HTTP embedding (248s on a 35KB doc) becomes the bottleneck. *Evolves:* batch embeddings; scale ingestion workers.
- **100,000 users** — One-collection-per-org strains Qdrant; single uvicorn worker saturates. *Evolves:* shared collections with tenant filters; horizontal API workers.
- **1,000,000 users** — Everything becomes a distributed-systems problem. *Evolves:* dedicated worker fleet, sharded Qdrant, cost/usage governance at scale.

**Bottom takeaway (one line):** *The architecture changes at every stage. The invariants — tenancy, durability, audit — do not.*

**Visual layout suggestion:** A horizontal timeline across the slide. Six evenly-spaced stage cards ascending left→right, each a small stacked mini-card (stage number, "what breaks," "what changes," "what evolves"). Connect with an ascending line to imply growth.

**Diagram recommendation:** A gentle ascending step-line (like a staircase), each step labeled with the user count. Above each step, a tiny 3-line "what breaks / what changes / what evolves" chip.

**Icon recommendations:** TrendingUp / staircase, User glyphs scaling in count, small arrows.

**Design hierarchy:** 1) Headline, 2) timeline, 3) takeaway.

**Speaker notes:** *"Scale isn't one threshold — it's a series of them. Each one forces a different bottleneck to the surface. This slide is honest that the free-tier setup is the *first* stage, not the end state."*

---

## SLIDE 9 — Lessons Learned

**Slide title:** Lessons From Building — and Operating
**Subtitle:** What the demo never teaches you.

**Body content — principles (one per line, large, quote-style):**
- *Building AI is easy. Operating AI systems is hard.*
- *Reliability matters more than features.*
- *Good architecture is about trade-offs, not choices.*
- *Simple systems outperform unnecessary complexity.*
- *Measure before you build — we rejected the reranker with data, not opinion.*
- *Production engineering begins where the demo ends.*

**Visual layout suggestion:** Editorial list — each principle as a large line with a hairline rule beneath, staggered left-indentation for rhythm. One or two lines per principle, muted secondary text after the bold statement if needed. Maximal whitespace; this is the "breath" slide.

**Diagram recommendation:** None — typography is the design.

**Icon recommendations:** None, or a single small quote mark / spark glyph at the head of each line.

**Design hierarchy:** 1) Headline, 2) principles (large type), 3) whitespace.

**Speaker notes:** *"The last one is the thesis of the whole deck: the demo is table stakes. The operating layer is the product."*

---

## SLIDE 10 — Conclusion

**Slide title:** CampusBrain
**Subtitle:** A production-oriented AI knowledge platform.

**Body content — three summary columns:**
- **What it is** — A multi-tenant RAG knowledge platform for institutions, with cited, no-evidence-refusal answers. First customer: Sitare University.
- **What I learned** — Production engineering is the product; the demo is table stakes.
- **Why I built it** — To prove I can design and operate a system, not just call a model API.

**Closing line (verbatim, high emphasis):** *"I'd love feedback from backend, platform, and AI engineers on the architecture and engineering trade-offs."*

**Footer:** `CampusBrain · Production-Oriented AI Knowledge Platform · #SystemDesign #RAG #Backend` + contact/placeholder handle.

**Visual layout suggestion:** Three equal columns for the summary, then a full-width closing statement bar, then a footer strip. Centered or left-aligned. Clean, minimal, no clutter.

**Diagram recommendation:** None — or a tiny repeating node-graph motif to bookend the cover.

**Icon recommendations:** Info (what it is), BookOpen/Lightbulb (learned), Target/Flag (why).

**Design hierarchy:** 1) Closing statement (primary), 2) three columns, 3) footer.

**Speaker notes:** *"I'm not claiming production-ready. I'm showing production-oriented decisions and asking the exact audience this is for to pressure-test them."*

---

## Animation + Export Notes (optional)

- **Motion:** Fade-up on text (300–500ms), left-to-right draw on diagrams, stagger on grids (50–80ms). No bounce, no 3D, no scale-pop. Restraint is the premium signal.
- **LinkedIn spec:** 1080×1350 (portrait) or 1200×675 (landscape) per slide. This deck is authored **1200×675 landscape**; portrait requires re-laying the grids. Export each slide as a crisp PNG (2× for retina) or a single PDF, then re-upload as separate carousel images.
- **Consistency:** identical margins (e.g. 72px), identical hairline color `#E5E7EB`, identical header block (index / headline / subtitle) on every slide so the carousel reads as one piece.

---

*Accurate to the CampusBrain codebase and decision records (ADR-004 through ADR-016), deployment docs, and the production design review as of 2026-08-03.*
