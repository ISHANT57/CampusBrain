# CampusBrain AI — Interview Handbook

**Status:** Living document · **Created:** 2026-07-30 · **Last revised:** 2026-07-30
**Companion to:** `ENGINEERING_ROADMAP.md` (the blueprint), `LLM_ENGINEERING.md` (the theory)

---

## How to use this handbook

Every answer here is defensible against the source. Nothing is aspirational.

**Never regenerate a chapter.** Append or revise after a pillar lands. Chapters 4–6 are
deliberately stubs — they map to pillars that are *designed but not implemented*, and
writing their answers now would produce exactly the claims this handbook exists to prevent.

### The two modes

| Mode | Assumes | Use when |
|---|---|---|
| **A — Current Implementation** | Only what is in the codebase today | You are interviewing **before** Pillars 1, 2 and 5 ship |
| **B — Target Architecture** *(default)* | Every pillar in `ENGINEERING_ROADMAP.md` is built, tested and deployed | You are rehearsing the answers you will give **after** shipping |

Mode B answers are written unhedged — present tense, defended as shipped, no "planned"
qualifiers. Migration history appears only when an interviewer explicitly asks how the
architecture evolved.

> **The only guard rail:** every chapter carries a mode tag. That tag is the difference
> between rehearsing a future answer and misremembering which one is true today. Check it
> before you use a chapter, and re-read Mode A before any interview that lands before the
> work does.

### The status marker

Every conversation is tagged. Read the tag before you read the answer.

| Marker | Meaning | How you answer |
|---|---|---|
| **`[BUILT]`** | It is in the code. Constants cited from the file | Describe it in the present tense |
| **`[MEASURED & REJECTED]`** | Considered, measured, deliberately not shipped | Lead with this. It is your strongest card |
| **`[GAP]`** | Not built. You will still be asked | Name it, name the cause, name the fix. **Never** describe it as built |
| **`[DESIGNED]`** | A design exists; no code | *"Here's what I'd build and why"* — never *"here's what we do"* |

### The rule that makes this work

> **A gap you volunteer reads as self-awareness. The same gap extracted from you reads as a
> catch.** Identical facts, opposite outcomes. Every `[GAP]` answer below is structured
> gap → cause → fix, in that order, in one breath.

### A note on the reference examples that seeded this handbook

Three of the four described features CampusBrain does not have — a unique content-hash
constraint, resumable per-chunk ingestion, and golden-dataset gating. They are all on the
roadmap (P0-3, P0-1, P1-7). They are written up here as `[GAP]` conversations, because an
answer you cannot survive a follow-up on is worse than no answer.

The fourth example — Qdrant vs pgvector — is *true* but generic: the answer as written could
describe any project. Chapter 3.1 gives the CampusBrain-specific version, which is stronger
precisely because it cites numbers only someone who built this system would know.

---

# Chapter 1 — Architecture & System Design

> **Mode A.** Ten of these twelve conversations describe shipped code, so they read
> identically in both modes. The two exceptions are **1.3** (ingestion durability) and
> **1.4** (upload idempotency) — those are the pre-shipping versions, kept because they are
> what you say if you interview before Pillar 1 lands. Their Mode B counterparts are
> **4.1** and **4.2**, where the topics belong anyway.

---

## 1.1 · Multi-tenant vector isolation `[BUILT]` · Mid → Senior

**Interviewer:**
> You create a separate Qdrant collection for every organisation. Most systems would use one
> collection with a tenant ID filter. Why did you go the other way?

**You:**

Because the two options fail differently, and I cared more about the failure mode than the
efficiency.

In CampusBrain every org gets its own collection — `org_1`, `org_2`, and so on. Isolation is
structural: a query against `org_1` physically cannot reach `org_2`'s vectors, because
they're not in the same index. With a shared collection and a payload filter, isolation is
*conditional* — it holds as long as every query remembers the predicate. One repository
method that forgets a `WHERE`, one new endpoint written in a hurry, and you have a
cross-tenant data leak. And it's silent. Nothing errors. The user just sees another
institution's documents in their citations.

We intentionally chose the design where that class of bug is unrepresentable. You can't
forget a filter that doesn't exist.

The trade-off we accepted is real, though, and it's not the one people expect. It isn't
storage — it's per-collection overhead. Qdrant keeps index structures and memory per
collection, so **CampusBrain's scaling limit is tenants, not vectors.** At 273 chunks across
one real tenant that's irrelevant. At a few hundred orgs it's still fine. Somewhere around a
thousand collections the overhead starts to dominate, and that's the migration trigger.

At that point I'd move to a shared collection with a mandatory tenant filter — but I'd
implement it so the mistake is still structurally impossible: one repository method that
every query goes through, with no public way to construct a search without the tenant
predicate, and a test asserting that. The whole risk is a call site that forgets, so you
remove the ability to have a call site that can.

The other thing I'd want before that migration is a payload index on the tenant key.
Filtered ANN with an unindexed payload field is a real performance trap — you either
pre-filter and lose the graph traversal's efficiency, or post-filter and get back fewer
results than you asked for, which looks exactly like a recall bug and isn't one.

### Follow-up Questions

1. Post-filtering returns fewer than `top_k` results. Is that a bug? How would you tell it
   apart from genuine recall loss?
2. One tenant has 10 million chunks and the other 499 have a thousand each. Does your design
   still hold?
3. How would you run the migration from per-collection to shared without downtime?
4. Your Qdrant point ID is the Postgres chunk ID. What does that buy you, and what does it
   constrain?
5. If a tenant asks you to prove their data was never accessible to another tenant, what can
   you actually show them?

### What the Interviewer is Testing

**Concept:** multi-tenancy isolation models, and whether you reason about failure modes
rather than features.
**Hidden objective:** do you evaluate designs by *what happens when they break*, or by
throughput and elegance? Senior candidates optimise; staff candidates ask what the blast
radius is.
**Common mistakes:** answering "for security" with no mechanism; not knowing the crossover
point; assuming the constraint is storage when it's per-collection overhead.
**Red flags:** claiming per-tenant collections scale indefinitely; not knowing what a payload
index is; treating this as a preference rather than a trade.
**Excellent answer:** names both failure modes, states the crossover, and — the part that
separates it — describes how to make the *shared-filter* version safe too, rather than
implying one design is simply correct.

### If CampusBrain Didn't Have This

**Production:** a missing filter on any new query path leaks one institution's corpus into
another's answers. **User:** a student at one college receives cited answers from another
college's prospectus. **Business:** for a product sold per-institution, this is the
credibility-ending failure — you cannot un-leak it, and every tenant now asks what else
leaked. **Engineering:** the correctness of every future query depends on a convention no
compiler enforces, so the risk grows with every endpoint you add.

### Real Production Incident

A team adds an internal "search across all documents" admin endpoint for support staff. It
reuses the vector search helper but drops the tenant filter, because the whole point is to
search everything. Six weeks later that helper is refactored, and the *student-facing*
endpoint inherits the filterless code path. Nobody notices, because retrieval still returns
plausible chunks — just occasionally from the wrong institution. It surfaces when a student
asks about fees and gets a citation naming a college they've never heard of.

Under per-collection isolation, that refactor produces an empty result or a missing-collection
error — loud, immediate, and caught in development.

### Whiteboard Discussion

Draw two boxes: **Qdrant — collection per org** versus **Qdrant — one collection + payload
filter**. Under each, write the failure mode, not the feature. Then draw the query path for
both and mark where the isolation decision is enforced — in the *collection name* versus in a
*predicate*. Justify: why structural beats conditional at low tenant count. Then take the
scaling discussion yourself — draw the crossover at ~1,000 collections and sketch the shared
design with a single repository chokepoint and a payload index.

---

## 1.2 · An unauthenticated chat endpoint `[BUILT]` · Senior

**Interviewer:**
> Your chat endpoint has no authentication at all, and the organisation is taken from the URL
> path. Anyone who guesses a slug reads that tenant's corpus. Defend that.

**You:**

It's deliberate, it's documented in the code, and I'll give you the condition under which
it's indefensible — because it's closer than it sounds.

The corpus is a university's public information: prospectus, fee structure, admissions
criteria, placement lists. It's the same content the institution publishes on its website.
Putting a login in front of a chatbot that answers questions about publicly available
material adds friction for every student and protects nothing. The org slug in the path is a
routing mechanism, not an authorisation boundary, and the docstring says exactly that so
nobody mistakes it for one later.

Everything that *isn't* public-by-design takes org from a verified JWT, never from a path —
uploads, document listing, and `/search` all resolve the tenant from the credential.

Now the part I'd volunteer before you ask. The design is only sound while the invariant
"every ingested document is public" holds, and **nothing in the system enforces that
invariant.** An admin can upload an internal spreadsheet and has now published it through a
chatbot, with no warning, no classification step, and no way to notice. The failure is
silent and it's a one-click distance away.

So the fix isn't authentication — adding a login wouldn't stop an admin publishing an
internal document to the students who *are* logged in. The fix is a **classification step at
upload**: documents get marked public or internal, and the anonymous chat path only ever
retrieves from public collections. That's the missing control, and it's a schema field plus a
filter, not an auth system.

The migration trigger is the first non-public document, and honestly the safer version is to
build the classification *before* that happens rather than after, because there's no way to
detect that it has happened.

One more thing I'd mention: because there's no account, the rate limit falls back to client
IP, and a whole campus behind one NAT is a single IP. That's why the limit is 120 a minute
rather than something tighter — it exists to cap a runaway script, not to ration students. If
abuse became real, the next step is a signed per-browser session token issued on first load,
keyed the same way. That gets me per-visitor limits without an account.

### Follow-up Questions

1. An admin uploads an internal document by mistake. How do you detect it? How do you
   recover?
2. Your rate limit is per IP. Design a limit that survives both NAT and a distributed abuser.
3. The client sends conversation history and the server stores none. What can a malicious
   client do with that?
4. How would you add per-student personalisation without authenticating students?
5. If the institution asks for an audit log of every question asked, what do you need to
   change?

### What the Interviewer is Testing

**Concept:** authorisation boundaries, and whether the candidate can distinguish
authentication from authorisation from *data classification*.
**Hidden objective:** will you defend a weak design, or state the condition under which it
fails? The question is phrased as an accusation to see whether you fold or over-defend.
**Common mistakes:** answering "we'll add auth later"; failing to notice the *enforcement*
gap is separate from the *access* decision; not knowing what the JWT-protected paths are.
**Red flags:** claiming the slug is a security control; not being able to name the invariant
the design depends on.
**Excellent answer:** identifies that the real fix is classification rather than
authentication, and volunteers that the invariant is unenforced before being pushed to it.

### If CampusBrain Didn't Have This

Inverting the question — if the endpoint *were* authenticated: every student needs an
account, so the institution needs identity integration, password resets, and a support
burden, all to gate public information. Adoption drops because the friction is front-loaded
onto a five-second interaction. **Business:** the product's whole appeal is "ask a question,
get a cited answer" — a login screen is the most expensive thing you can put in front of that.

### Real Production Incident

An admin bulk-uploads a folder that happens to contain `placements_internal_2026.xlsx` with
student names, phone numbers and offer amounts. Ingestion succeeds. Two weeks later a student
asks "what salaries did people get?" and receives a cited answer quoting real offer figures
against real names. There is no access log, no classification field, and no way to determine
who saw it — the chat endpoint is anonymous and unlogged.

Every control that would have helped is a different pillar: classification at upload
(Security), an audit log (Security), and request logging (Observability).

### Whiteboard Discussion

Draw the two request paths side by side — **anonymous chat** (slug → org) and
**authenticated admin** (JWT → org) — and mark clearly where org comes from in each. Then
draw the missing box: a **classification gate at ingestion**, with public and internal
corpora, and the anonymous path physically wired only to public. Justify: why auth is the
wrong lever for this problem. Then take the discussion to audit logging and what "prove no
student saw this document" requires.

---

## 1.3 · One process doing API and background work `[BUILT]` → `[GAP]` · Staff

**Interviewer:**
> Walk me through exactly what happens when your host suspends the instance while a document
> is being ingested.

**You:**

The document is lost, and in the worst case the *previous* version of it is lost too. This is
my top open issue and I can walk you through the mechanism.

Ingestion runs in FastAPI `BackgroundTasks` — same process, kicked off after the HTTP
response has already been sent. Render's free tier suspends the instance after fifteen
minutes with no inbound requests. Ingesting a 35 KB file takes about 248 seconds because
embedding is one sequential HTTPS call per chunk. So the job runs for four minutes with
nothing keeping the instance awake, and if it's the last request of the evening, the
instance goes to sleep partway through.

When that happens, no exception is raised — the process is gone. The `except` block that
would have set the status to `FAILED` never runs. The document sits at `PROCESSING` forever.
There's no reaper, no timeout, no retry, and the admin sees a spinner that never resolves.

The worse case is a re-index. `index_document` deletes the existing Qdrant points first, then
the chunk rows, *then* re-chunks and re-embeds. The ordering is actually correct — the chunk
ID is the Qdrant point ID, so once you delete the rows you can't address the points any more
— but it means a crash in that window leaves the document with zero chunks and zero vectors.
The old content is gone and the new content was never written. That's real data loss, not a
stuck job.

The fix I've designed is a `jobs` table in Postgres with `SELECT ... FOR UPDATE SKIP LOCKED`
for claiming, a lease timestamp so a dead worker's job can be reclaimed, an attempt counter
with a dead-letter state at three, and a reaper that runs on startup and resets expired
leases. The work becomes durable because it was never *in* the process to begin with.

Two things I want to be explicit about. First — **this doesn't bring Redis back.** We removed
arq and Redis deliberately, because it was a fourth managed service for one job type at very
low volume, and that simplification still stands. What was wrong wasn't the transport, it was
assuming in-memory state would survive. Postgres is already running, already durable, already
transactional, and `SKIP LOCKED` is a battle-tested claiming primitive. I'd only reach for
Redis past roughly a hundred jobs a second, which this will never see.

Second, the durable queue doesn't fix the destructive re-index on its own. That needs the
ingestion to be resumable — persist the chunks first, embed in batches, record an
`embedded_at` per chunk, and never delete the old version until the new one is ready to
replace it. Then a crash at chunk 42 resumes at chunk 42 instead of restarting, and it never
leaves the document empty in between.

And the cheapest mitigation is almost embarrassing: a free external cron pinging `/health`
every ten minutes stops the instance idling out at all. That's one free cron job solving a
reliability problem, and it doubles as the synthetic canary for monitoring.

### Follow-up Questions

1. Two instances start simultaneously after a deploy. Both reapers run. What breaks?
2. How do you set the lease duration? What happens if you pick it too short?
3. A job fails three times and goes to the dead-letter state. Now what — who finds out?
4. `SKIP LOCKED` — what problem does it solve that `SELECT ... FOR UPDATE` alone doesn't?
5. At what job rate does Postgres-as-a-queue stop being the right answer, and what's the
   signal you're approaching it?
6. How do you make the re-index safe without doubling storage?

### What the Interviewer is Testing

**Concept:** durability of asynchronous work, and the difference between *losing progress*
and *losing data*.
**Hidden objective:** can you reason about a partial failure precisely — not "it might fail"
but *which lines run and which don't*? And do you reach for infrastructure or for what you
already run?
**Common mistakes:** saying "add Celery/Redis" without justifying a new service; missing the
delete-before-write window entirely; not noticing that no `except` runs when the process is
killed.
**Red flags:** claiming the pipeline is resumable when it isn't; not knowing the host's
suspension behaviour; treating the stuck job and the data loss as the same bug.
**Excellent answer:** separates the two failure modes, gets the delete-ordering reasoning
right, chooses Postgres over Redis *with a stated threshold*, and mentions the cron keep-alive
as a cheap mitigation that also serves monitoring.

### If CampusBrain Didn't Have This

This is the current state, so this section describes today. **Production:** ingestion has an
unbounded failure rate with no visibility. **User:** an admin uploads a document, sees a
spinner forever, retries — and each retry creates a *duplicate* document, because the API
path doesn't dedupe. **Business:** the core admin workflow is unreliable, and the failure is
silent, which is worse than an error. **Engineering:** no recovery path exists after the
fact; a lost document is only detectable by someone noticing a question can't be answered.

### Real Production Incident

An admin uploads six documents at 6 pm and leaves. The first four complete. The fifth is
mid-embed when the instance idles out. The sixth never starts — `BackgroundTasks` state died
with the process.

Next morning: documents five and six show `PROCESSING`. The admin re-uploads both. Now
there are duplicate rows for four documents' worth of content (the two stuck plus the two
re-uploads), because `content_hash` is NULL on the API path. Retrieval starts returning
near-duplicate chunks, which consumes the `top_k` budget, and counting questions begin
returning inflated numbers — the exact failure the prompt's dedupe clause was written to
suppress.

**Three separate open issues compounding: no durability, no idempotency, no observability.**

### Whiteboard Discussion

Draw the ingestion timeline as a horizontal bar: `response sent → delete points → delete rows
→ chunk → embed ×47 → upsert → PROCESSED`. Mark the 15-minute suspension line across it, and
shade the window where a crash means data loss rather than lost progress. That shaded region
is the whole argument.

Then draw the `jobs` table with its state machine and the reaper. Justify Postgres over Redis
with the job-rate threshold. Take the discussion to resumability and idempotency yourself —
they're the two things the queue alone doesn't fix.

---

## 1.4 · Preventing duplicate uploads `[GAP]` · Mid → Senior

**Interviewer:**
> How do you prevent duplicate document uploads?

**You:**

On the bulk-ingest path I do. On the HTTP upload path I don't, and it's a P0 on my roadmap.

The mechanism is half-built, which is the interesting part. There's a `content_hash` column
on documents and a composite index on `(org_id, content_hash)` — both added in a migration
specifically for the operator tool, `tools/ingest.py`, which SHA-256s each file and skips
anything it's already indexed. That path is properly idempotent, and it needs to be, because
it's how the corpus gets bulk-loaded and re-run incrementally.

The API upload path leaves `content_hash` NULL. So uploading the same PDF twice creates two
documents, two full sets of chunks, and two full sets of vectors.

What makes this a correctness bug rather than a cost bug is the bit I'd want you to push on.
My prompt contains a clause telling the model to count each person or item once no matter how
many documents mention it — that clause exists because the corpus genuinely repeats facts
across files, and without it counting questions came back inflated. But duplicate ingestion
manufactures that exact condition artificially. So I have a deterministic component creating
a problem I'm compensating for in a non-deterministic one. That's the wrong layer. A prompt
clause is a request to a model; a unique index is a guarantee.

The fix is small: hash on the API path too, make the index unique on `(org_id, content_hash)`,
and on a collision return 200 with the existing document rather than 201 with a new one.
That last detail matters for the retry story — if the network drops after the server has
committed but before the client sees the response, the client retries, and the correct
behaviour is to get the same document back, not a second copy. Idempotency is what makes
retries safe, which is why this is a prerequisite for the reliability work rather than a
nice-to-have alongside it.

The one thing content hashing doesn't cover is a document that's been *edited* — same
document, different bytes, so different hash, so a new row. That's correct behaviour, but it
means I'd want an explicit "replace" operation rather than relying on dedupe to handle
updates.

### Follow-up Questions

1. Two identical uploads arrive concurrently. Both hash, both miss, both insert. What
   happens, and what saves you?
2. Why hash the content rather than trusting the filename?
3. Should the hash be scoped per organisation or global? What does each choice imply?
4. A user uploads the same content as a `.docx` and a `.pdf`. Different bytes, same
   information. Does your scheme catch it? Should it?
5. Storage keys use a UUID, not the hash. Why? Would content-addressed storage be better?

### What the Interviewer is Testing

**Concept:** idempotency, and its relationship to safe retries.
**Hidden objective:** do you understand that idempotency is a *prerequisite* for reliability
work, not a parallel feature? And can you locate a bug at the right layer?
**Common mistakes:** describing dedupe as a cost optimisation only; missing the concurrent-
insert race; not knowing the difference between the index existing and the constraint being
enforced.
**Red flags:** claiming a unique constraint exists when the index is non-unique; not
connecting duplicate ingestion to answer quality.
**Excellent answer:** the layering argument — a deterministic component manufacturing the
condition a probabilistic component is patching — plus returning 200-with-existing rather
than 201, and naming the concurrent-insert race that the database constraint (not the
application check) is what actually closes.

### If CampusBrain Didn't Have This

This is today. **Production:** every retry after a timeout creates a duplicate. **User:**
counting and list questions return inflated answers, and the sources panel shows the same
content twice under different filenames. **Business:** the answers are wrong in a way that
looks like the AI is bad, when it's an ingestion bug. **Engineering:** you can't safely retry
anything, which blocks the entire reliability pillar — retries without idempotency just
multiply the damage.

### Real Production Incident

An admin's upload times out at the proxy after 30 seconds — the server actually succeeded and
started background processing, but the client never saw the 201. The admin retries. Twice.
Three documents now exist for one file, each with its own chunk set. A month later someone
asks "how many students interned at KlearNow?" and gets triple the real number. The
investigation starts in the prompt and the retrieval layer — because that's where counting
bugs live — and takes days to reach the ingestion path.

### Whiteboard Discussion

Draw the upload sequence with the client, the API, and the database, and mark the window
where a timeout leaves the client uncertain but the server committed. That window is why
idempotency exists.

Then draw both paths — `tools/ingest.py` (hashes) versus `POST /documents` (doesn't) — and
show the asymmetry. Justify the unique constraint at the *database* rather than a
check-then-insert in the application, and be ready to explain why: the application check has
a race, the constraint doesn't. Then connect it forward to retries and the reliability pillar.

---

# Chapter 2 — RAG Pipeline

---

## 2.1 · RAG versus fine-tuning `[BUILT]` · Junior → Mid

**Interviewer:**
> Would fine-tuning a model on the university's documents have been better than building a
> retrieval system?

**You:**

No, and the deciding factor isn't cost — it's attribution.

CampusBrain shows a sources panel under every answer, with the document and page number. That
isn't decoration; for a system answering questions about fees and admissions criteria, a
student needs to be able to check the claim. A fine-tuned model has that knowledge smeared
across its weights with nothing to point at. It can produce a citation-shaped string, but not
a verifiable one. That single product requirement settles the architecture before anything
else enters the conversation.

The second reason is freshness. The fee structure, the placement lists and the curriculum
change every semester. With retrieval, updating means re-indexing one document — seconds.
With a fine-tune, it means retraining, and the model goes stale the day training finishes.

Third, and this one gets overlooked: RAG gives you access control at query time. If we ever
need internal documents visible only to staff, that's a filter on retrieval. With a
fine-tuned model you'd need a separate model per permission set, which doesn't scale past two.

The trade-off I accepted is that RAG costs tokens on every request — the retrieved context is
about 1,250 tokens per question, roughly 70% of the prompt. A fine-tuned model would carry
that knowledge for free. At our volume that's not close to worth it.

What I'd say to close, because it's the answer interviewers actually want: they're not
alternatives. The mature version is both — RAG for facts and attribution, and a light
fine-tune if I needed the model to consistently hit a specific output format or handle domain
vocabulary. But I'd only reach for that after RAG plateaued, and I'd want evidence from an
eval harness that the remaining failures were *behavioural* rather than retrieval misses.
Right now I don't have that evidence, so it would be a guess.

### Follow-up Questions

1. You say attribution decides it. What if the product didn't need citations?
2. Context windows are a million tokens now. Why retrieve at all — why not stuff the corpus?
3. What would you fine-tune *for* in this system, specifically?
4. How would you decide, with data, that RAG had plateaued?
5. What does LoRA change about this calculus?

### What the Interviewer is Testing

**Concept:** whether the architecture was *chosen* or *defaulted to*.
**Hidden objective:** most candidates say "RAG is cheaper", which is true, incomplete, and
not the deciding factor. The interviewer wants to know whether you can identify the property
that actually forced the decision.
**Common mistakes:** leading with cost; saying "I didn't have training data", which is an
excuse rather than a decision; treating them as mutually exclusive.
**Red flags:** not knowing that a fine-tuned model can't cite; claiming a fine-tune would be
more accurate without qualification.
**Excellent answer:** names attribution as the deciding row, gives freshness and access
control as supporting reasons, states the token cost as the accepted trade, and ends with the
"they're complementary, and here's the evidence I'd need" framing.

### If CampusBrain Didn't Have This

If the system were a fine-tune: **User** gets confident answers with no way to verify, and no
way to tell a correct answer from a fabricated one. **Business:** the institution can't
approve a system that states fee figures without provenance — the legal and reputational
exposure of a wrong number stated confidently is the whole risk. **Engineering:** every
corpus change becomes a training run, so the update cadence goes from seconds to days.

### Real Production Incident

A student asks about the scholarship criteria and gets a fluent, confident, slightly wrong
answer — an eligibility threshold from a previous year. With citations, the student clicks
through, sees the source is a 2024 document, and reports it. Without citations, the student
acts on it, misses a deadline, and the institution finds out through a complaint. The same
model error; completely different blast radius, entirely because of attribution.

### Whiteboard Discussion

Draw a three-column table — **prompting / RAG / fine-tuning** — with rows for knowledge
freshness, attribution, access control, setup cost, and per-query cost. Circle the
attribution row and say "this one decided it." Then draw the retrieval path and mark where
the chunk ID and page number originate, because that's the mechanism attribution actually
depends on. Take it forward to "when would you add a fine-tune on top of this."

---

## 2.2 · The three prompt clauses `[BUILT]` · Mid → Senior

**Interviewer:**
> Your prompt has some unusual instructions in it — something about counting, something about
> not narrating. Where did those come from?

**You:**

Each one is a bug fix. They're regression tests written in English, and I'll say up front
that none of them has a test, which is the uncomfortable part.

The first came from a question that got refused when it shouldn't have. "Which students went
to KlearNow?" listed eight names correctly. "How many students went to KlearNow?" returned
"I don't have information on that in the available documents" — from the same retrieved
chunks. The model had the information and had just used it.

The cause was my own instruction. The prompt said "answer using ONLY the numbered context",
and I meant *don't use outside knowledge*. The model read it as *don't emit any string that
isn't literally present* — and the number eight isn't written anywhere, you have to count the
rows. So it refused. The fix was disambiguating the word, not strengthening the model: I
added a clause saying that counting or listing what the context states is reading it, not
going beyond it. What I take from that is that the model was obeying me precisely and my
instruction was ambiguous.

The second came from shipping the first. Once it would count, it started showing its work:
"There are 6 students: 1... 8... Wait, counting the names again — that makes a total of 8."
Correct final number, arrived at in front of the user. That's chain-of-thought doing exactly
what it's good at — counting across a dozen chunks is where reasoning helps most — and
nothing had told it that the reasoning and the answer are different artifacts with different
audiences. So: work out the count before you begin writing, give only the final answer, never
narrate.

I'd flag that this one is a request, not a guarantee. A structural version — have the model
emit reasoning in a delimited block and strip it server-side, or use a model with native
thinking tokens — would be robust. The instruction can silently stop working when the model
version moves under me, and it's a floating alias, so it will.

The third is deduplication. The same student appears in a placements table, a success-stories
paragraph and an interns list, so retrieval returns all three — correctly, they're all
relevant — and the model counted the person once per chunk. The clause says count each item
once regardless of how many documents mention it.

That one's interesting because the fix is in the wrong layer. It's a *retrieval* problem —
near-duplicate chunks eating the `top_k` budget — and the retrieval-layer fix is MMR, which
explicitly trades relevance against diversity and is deterministic code I could unit test. I
put it in the prompt because it was one line and it worked. Where you fix a bug reveals which
layer you think owns it, and prompt fixes are cheap and accumulate into a pile nobody can
reason about.

### Follow-up Questions

1. Does the dedupe clause interfere with the counting clause? How would you know?
2. Which of the three could you assert deterministically, without a judge?
3. The model version changes tomorrow. How do you find out if these still work?
4. Why not use a system prompt role instead of one flat string?
5. Talk me through moving the dedupe fix from the prompt into retrieval.

### What the Interviewer is Testing

**Concept:** prompt engineering as accumulated bug fixes, and the discipline of only adding a
clause after an observed failure.
**Hidden objective:** does the candidate understand that prompts are *untested code*? The
best answer arrives at that on its own.
**Common mistakes:** describing prompt techniques generically; not being able to name the
failure each clause fixed; missing that "never narrate" is checkable with a regex.
**Red flags:** claiming the prompt is tested; treating a prompt instruction as a guarantee
rather than a request.
**Excellent answer:** names the specific failure behind each clause, identifies the "ONLY"
ambiguity as *my instruction was wrong, not the model was weak*, and volunteers that the
dedupe fix sits at the wrong layer with MMR named as the right one.

### If CampusBrain Didn't Have This

**User:** counting questions either refuse outright or return inflated numbers, and the model
narrates its own confusion mid-answer. **Business:** "how many students got placed" is one of
the highest-intent questions a prospective student asks — getting it wrong or refusing it is a
direct credibility hit. **Engineering:** each of these presents as "the AI is bad" and sends
you to the model, when the causes are an ambiguous instruction, a missing output constraint
and a retrieval redundancy problem — three different fixes in three different places.

### Real Production Incident

The model version behind `gemini-3.5-flash-lite` updates. The new weights follow the "never
narrate" instruction less strictly. Counting answers start including their working again.
Nothing errors, no metric moves, no test fails — because there are no tests on the prompt.
It's discovered when someone screenshots an answer that says "Wait, counting again."

Prevention is a deterministic assertion — the answer must not contain "wait", "let me count",
"counting again" — running in CI against a golden set. It's a regex, and the clause that
looked unassertable turns out to be the easiest one to check.

### Whiteboard Discussion

Draw the prompt as a stack of blocks: role, base instruction, three behavioural clauses,
history, numbered context, question. Annotate each clause with the bug that caused it. Then
draw a second column: for each clause, is it deterministically checkable? Two of three are —
that's the bridge to the evaluation discussion, and you should take it yourself.

---

## 2.3 · Refusing before generating `[BUILT]` · Senior → Staff

**Interviewer:**
> How do you stop the system answering questions it has no evidence for?

**You:**

There are four layers, and the strongest one is the one that runs before the model is called
at all.

After retrieval, I check the best *semantic* similarity score across the fused results
against a threshold of 0.35. If nothing clears it, I return a fixed refusal string and never
call the LLM. No tokens spent, no opportunity to hallucinate, no output to filter. Refusing
before generating is architecturally cheaper than any output-side check.

There's a subtlety in that it checks the semantic score specifically, not the fused score. A
chunk can reach the result set purely through the keyword arm because it contains a common
word — that's a lexical match, not evidence that the corpus answers the question. Requiring
semantic evidence is the correct bar.

That detail also nearly caused a serious bug, and it's the one I'd want to tell you about.
The threshold is calibrated on cosine similarity, which runs 0 to 1. After Reciprocal Rank
Fusion, the score field holds an RRF score, which is around 0.03. If I'd thresholded the
fused score, `0.03 < 0.35` would be true for every result of every query — **the system would
have refused every question ever asked**, silently, with no error anywhere. It was avoided
only because I deliberately carried the raw semantic score through fusion as a separate
field. Both values are floats and both were called `score`; the type system couldn't help.
The general lesson is that when you transform a value you have to find every downstream
consumer of its old semantics — that's a unit error, the same class as passing metres to a
function expecting feet.

The other three layers: sanitising retrieved text for injection patterns before it enters the
prompt; a prompt that forces inline citations, which makes every claim attributable; and an
output validator that drops citation markers pointing at chunks that weren't retrieved — if
the model emits `[9]` when five chunks came back, that reference is removed entirely rather
than shown to a user who can't check it.

Now what I'd volunteer. **0.35 has never been validated.** There's no comment, no reference,
no measurement — it's a plausible-looking number on a cosine scale. And it's the
highest-stakes constant in the system, because it's a binary switch between "I don't know"
and a confident fabrication. Set it too high and the system is useless; too low and it makes
things up. I genuinely don't know which side of that trade I'm on.

The fix is cheap, which is why it's annoying that it isn't done: ten out-of-corpus questions
labelled should-refuse, sweep the threshold from 0.20 to 0.60, and plot refusal precision
against recall. It's almost entirely deterministic because the refusal string is an exact
match, so no LLM judge is needed. And I'd bias toward over-refusal — for a college chatbot an
unnecessary "I don't know" is mildly annoying, and a fabricated fee figure is something a
student acts on.

### Follow-up Questions

1. Walk me through how you'd calibrate 0.35 properly. What data, what metrics?
2. Refusal rate suddenly doubles in production. What are your three hypotheses, in order?
3. Why is checking the semantic score better than checking the fused score — beyond the
   scale issue?
4. Your refusal is a single fixed string. What does that buy and what does it cost?
5. How would you catch a *near-miss* — a question that scored 0.36 and shouldn't have been
   answered?

### What the Interviewer is Testing

**Concept:** guardrail design, and the recognition that a guardrail has an input *contract*,
including units.
**Hidden objective:** the RRF-scale trap. An excellent candidate raises it unprompted,
because it demonstrates systems thinking rather than component knowledge.
**Common mistakes:** listing hallucination mitigations generically; not knowing where the
threshold came from; claiming the number is tuned.
**Red flags:** saying the system "prevents" hallucinations; not being able to state what
happens if the threshold is wrong in each direction.
**Excellent answer:** leads with refuse-before-generate as an *architectural* choice, tells
the unit-mismatch story, and volunteers that 0.35 is unvalidated along with the exact,
cheap experiment that would validate it.

### If CampusBrain Didn't Have This

**Production:** every out-of-corpus question gets a fluent answer assembled from whatever
loosely-related chunks came back. **User:** asks about a scholarship the university doesn't
offer and receives a confident description of it. **Business:** for admissions information,
a confidently wrong answer is worse than no product — it creates commitments the institution
never made. **Engineering:** with no pre-generation gate, every defence is output-side, which
means you're spending tokens to generate text you then have to detect and discard.

### Real Production Incident

A subtly worse version of the RRF bug: someone changes the guardrail to use `hit["score"]`
instead of `hit["semantic_score"]` during a refactor, believing they're the same. Every
question now refuses. Health checks pass, error rate is zero, latency *improves* because the
LLM is never called. The system looks healthier than ever on every dashboard while being
completely broken. The only signal that would catch it is refusal rate — which is exactly why
it's the first metric in the observability design.

### Whiteboard Discussion

Draw the query path with the four guardrails marked at their positions — two input-side, two
output-side — and highlight that only the first can prevent the LLM call. Then draw two
number lines: cosine 0–1 with 0.35 marked, and RRF scores clustered near 0.03. That picture
*is* the bug. Justify carrying `semantic_score` through fusion. Then take it to calibration —
refusal precision and recall against a labelled set — which hands you the evaluation
discussion.

---

# Chapter 3 — Retrieval & Qdrant

---

## 3.1 · Qdrant versus pgvector — the CampusBrain answer `[BUILT]` · Mid → Senior

**Interviewer:**
> You already run Postgres. Why add a second datastore for vectors instead of using pgvector?

**You:**

I'll give you the honest answer first, which is that at my actual scale neither is necessary
— and then why I still think the decision was right.

CampusBrain has 273 chunks at 768 dimensions. That's about 840 kilobytes of vectors. An exact
brute-force search in numpy would be a single matrix multiply, sub-millisecond, and faster
than the network round trip to Qdrant. So if you're asking whether a vector database is
*justified by the query load*, it isn't, and I'd rather say that than pretend otherwise.

The reasons it's still the right call are about what happens next, and one of them is
specific to running on free tiers.

The free-tier one first, because it's the least obvious. Qdrant Cloud gives 1 GB of vector
storage that is *separate from* Neon's Postgres allowance. Putting vectors in pgvector means
they consume the same free-tier budget as my chunk text, my documents table and my full-text
index. Splitting the workloads across two providers means neither budget is the binding
constraint. That's not an architectural principle, it's an economics one — but it's a real
constraint that shaped a real decision, and on free infrastructure resource budgets are the
design.

The second is isolation. Qdrant gives me a collection per organisation, which makes tenant
isolation structural — a query can't reach another tenant's vectors because they're in a
different index. With pgvector, isolation is a `WHERE org_id = ?`, which is conditional on
every query remembering it. I'd rather have a design where the leak is unrepresentable.

The third is the migration cost, which is the real argument. Adopting Qdrant on day one costs
one dependency and one client. Migrating to it at a million vectors, under load, with a live
corpus, is a project. I'm buying an option on scale and the option is cheap.

The trade-off I accepted is a second managed service to operate, a second thing that can be
down, and a consistency problem — the chunk text lives in both Postgres and the Qdrant
payload. That denormalisation is deliberate, so search doesn't need a join, and it holds
because chunk text is never edited in place; re-processing deletes and recreates both. But
it's an invariant maintained by discipline rather than by a constraint, which is the kind of
thing that breaks when a second developer arrives.

Where I'd reconsider: if operational simplicity became the dominant concern — say I wanted
one backup story, one connection pool, one thing to monitor — pgvector with an HNSW index is
genuinely good now, and consolidating would be defensible. And if I ever needed a query that
joins vector similarity against relational predicates in one statement, pgvector wins
outright, because with Qdrant that's two round trips and application-side merging.

### Follow-up Questions

1. You said numpy would be faster. At what corpus size does that stop being true, and how
   would you find out?
2. Chunk text is stored in both Postgres and the Qdrant payload. What happens when they
   diverge? How would you detect it?
3. Qdrant is down. What should the chat endpoint do?
4. Give me a query pgvector could serve and your current design can't.
5. Your Qdrant point ID is the Postgres chunk ID. Defend that, and tell me what it constrains.

### What the Interviewer is Testing

**Concept:** justifying infrastructure against actual requirements rather than convention.
**Hidden objective:** will you admit the scale doesn't require it? Candidates who can't
concede that a choice is over-provisioned usually can't evaluate any trade-off honestly.
**Common mistakes:** reciting vector-database features with no reference to scale; not
knowing the corpus size; missing the dual-storage consistency issue.
**Red flags:** claiming pgvector can't do ANN (it can, with HNSW); implying a vector database
is always required for RAG.
**Excellent answer:** concedes numpy would win today, gives the free-tier budget argument
(which is specific and unusual), names structural isolation, and lands on migration cost as
the real justification — with the denormalisation risk volunteered.

### If CampusBrain Didn't Have This

If vectors lived in pgvector: **Engineering:** one fewer service, one backup story — a real
win — but tenant isolation becomes a predicate that every query must remember, and vector
storage competes with everything else for the same free-tier allowance. **Production:** the
first large corpus fills a shared budget and takes down document storage *and* search
together, rather than degrading one.

### Real Production Incident

A team on pgvector adds a "search all documents" support tool, drops the `org_id` predicate
because searching everything is the point, and later that helper gets reused on the
student-facing path. Cross-tenant results appear in citations. It's the same incident as
Chapter 1.1 — which is the point: the datastore choice and the isolation model are the same
decision viewed twice.

### Whiteboard Discussion

Draw both topologies: **Postgres + Qdrant** versus **Postgres alone with pgvector**. Under
each, write four rows — isolation mechanism, free-tier budget, consistency surface,
operational surface. Say the quiet part: "at 273 chunks, numpy beats both." Then draw the
crossover — where exact search stops being viable — and justify the decision as buying an
option rather than meeting a requirement.

---

## 3.2 · Why hybrid retrieval `[BUILT]` · Senior → Staff

**Interviewer:**
> You run vector search and Postgres full-text search in parallel and fuse them. Semantic
> search is supposed to be strictly better than keyword matching. Why keep both?

**You:**

Because they fail in complementary ways, and my corpus is full of exactly the thing
embeddings are worst at — rare proper nouns.

The corpus is a university's documents: student names, company names, course codes, city
names. An embedding model has seen "KlearNow" rarely or never in training, so its vector is
poorly positioned — it lands somewhere near other capitalised tech-company-shaped tokens
rather than anywhere meaningful. Keyword search doesn't care; the string is either there or
it isn't. Conversely, semantic search finds "financial aid" when someone asks about
"scholarships", which keyword search structurally cannot. Neither arm covers the other's
blind spot, so I run both.

That's the design justification. The interesting part is that the keyword arm was broken
twice, and both bugs are worth telling you about.

The first: I was using `plainto_tsquery`, which ANDs every term. So a natural-language
question like "what programming languages are taught in year one" required a chunk to contain
every one of those words. Essentially nothing matched. The keyword arm returned zero results
for most questions for months, and I didn't notice — because the semantic arm covered for it
completely. That's the general lesson I took: **redundancy hides failure.** A two-arm system
looks fine when one arm is dead, and you can't tell a working component from a corpse by
looking at the output. The fix was ORing the terms and letting `ts_rank` order them, and the
real fix is per-arm observability, which is on my roadmap.

The second bug is the one I'd lead with. A question about how many students interned at
KlearNow returned generic prospectus boilerplate. The cause is that Postgres `ts_rank` **is
not BM25** — it scores term frequency within a chunk with length normalisation, and it has no
inverse document frequency term at all. It has no idea how many *other* chunks contain a
word. In my corpus "students" appears in 66% of chunks and "klearnow" in 5%, and `ts_rank`
weighted them identically. So chunks stuffed with prospectus filler outranked the three
chunks that actually named the company.

I fixed it by computing document frequency per term at query time and dropping any term above
10%. That's IDF used as a filter rather than a weight, because `ts_rank` gives you nowhere to
put a weight. I calibrated the 10% by measuring: klearnow 5%, job 10%, ai 15%, currently 23%,
internship 27%, students 66%. Ten percent sits above every proper noun and below every filler
word, and it moved the answering chunks from unranked to ranks one and seven. There's also a
fallback — if every term is common, like "what do students study", it returns the original
terms rather than an empty query. Degrade to the previous behaviour, never to zero.

Two honest caveats. That calibration was six terms and one query — it's directionally right,
not rigorous, and re-running it against a real golden set is on my list. And it recomputes
document frequency on every request, which is fine at 273 chunks and becomes the latency floor
around a hundred thousand. At that point I'd precompute the frequencies into a table, which is
exactly what a real BM25 index does at build time. That's the migration trigger, and past
that, moving the sparse arm to a proper BM25 implementation.

### Follow-up Questions

1. Give me a query where hybrid is *worse* than keyword alone. Why does that happen?
2. Why use document frequency as a filter rather than a weight? What would it take to weight?
3. Your DF query runs per request. Show me the version that doesn't.
4. How would you detect that one arm had died, before a user does?
5. You called it BM25 in your own documentation. How did you find out it wasn't?
6. Would SPLADE or sparse vectors in Qdrant change this design?

### What the Interviewer is Testing

**Concept:** the complementary failure modes of dense and sparse retrieval, and whether the
candidate understands ranking functions rather than importing them.
**Hidden objective:** does the candidate know what their library actually implements? "I
found out `ts_rank` isn't BM25" is a strong signal, because it means they read the behaviour
rather than the label.
**Common mistakes:** justifying hybrid as best practice rather than from corpus properties;
not knowing what IDF contributes; assuming hybrid always beats both arms.
**Red flags:** calling `ts_rank` BM25; no per-arm visibility and no awareness that's a
problem.
**Excellent answer:** the corpus-specific justification (rare proper nouns), the IDF story
with the real calibration numbers, the "redundancy hides failure" generalisation, and both
caveats volunteered — the weak calibration and the per-query DF cost with its threshold.

### If CampusBrain Didn't Have This

**Semantic-only:** questions naming a specific company, course code or student return
thematically related but wrong chunks, and the model answers from them — which looks like
hallucination and is actually retrieval. **Keyword-only:** any paraphrase fails; asking about
"financial help" finds nothing when the corpus says "scholarships". **Business:** placement
and admissions questions are the highest-intent queries a prospective student asks, and
they're exactly the proper-noun-heavy ones that dense retrieval handles worst.

### Real Production Incident

This one is real and it's INC-001. The keyword arm returned nothing for months because
`plainto_tsquery` ANDs every term. No error, no alert, no user report — the semantic arm
covered it. It was found by accident while debugging an unrelated question. Detection took
months for a component that was completely dead.

The prevention is a `keyword_hits` field on every retrieval event and a
`zero_keyword_hit_rate` metric, plus a synthetic canary asserting that an
exact-identifier question returns the expected chunk. That's the only check that would have
caught it.

### Whiteboard Discussion

Draw the two arms feeding a fusion box, with the over-fetch count on each edge. Underneath,
write a small table: which arm wins for "scholarship" versus "financial aid", for "CS 111",
for "KlearNow". Then write the DF calibration numbers — 5%, 10%, 15%, 23%, 27%, 66% — and
draw the 10% cut line. That table is the best single artifact you have; it shows a measured
decision with a stated failure direction.

Take the scaling discussion yourself: mark where the per-query DF lookup becomes the
bottleneck and what replaces it.

---

## 3.3 · Fusing on rank, not score `[BUILT]` · Staff

**Interviewer:**
> You've got two ranked lists with scores. Why not normalise the scores and combine them?
> Why throw the magnitudes away?

**You:**

Because the two scales aren't comparable, and normalising them is fragile in a way that only
shows up on the queries you care about.

Cosine similarity is bounded 0 to 1 and typically lands between 0.3 and 0.9. `ts_rank` is
unbounded, usually somewhere in 0.001 to 0.6, and — this is the part that kills
normalisation — its range depends on the query. Min-max normalising means the transform is a
function of whichever result set you happened to get back, so the same chunk gets a different
normalised score depending on what else was retrieved. Z-scoring assumes a distribution
neither of these has.

Reciprocal Rank Fusion sidesteps it by using position instead. Each list contributes
`1/(K + rank)` per chunk, summed across lists. I use K = 60, which is the value from the
original paper. The property you're buying is that **agreement between two independent
rankers beats a strong signal from one** — a chunk that both arms placed third scores higher
than a chunk one arm placed first. For retrieval feeding an LLM, that's the right bias,
because I'd rather have five chunks two systems agree are relevant than one system's
confident pick.

What K controls is how much the top positions dominate. At K = 1, rank one is worth about 5.5
times rank ten. At K = 60 it's about 1.15 times. So 60 is heavily on the consensus end — the
*number* of lists agreeing matters far more than where any one of them ranked it.

And the cost of that is real, so I'll state it: **fusion trades peak precision for
robustness.** On a query where the keyword arm is overwhelmingly right — an exact course
code, say — it ranked that chunk first with a huge margin, and RRF gives it exactly 1/61,
identical to any other first place. The margin is discarded. So hybrid can be *worse* than
keyword alone on that query. Hybrid is more consistent across query types, not better on
every one.

The thing I'd want to tell you about is what fusion broke downstream. My no-evidence
guardrail thresholds at 0.35, calibrated on cosine. After fusion, the `score` field holds an
RRF score of about 0.03. Both are floats, both are called `score`, and thresholding the fused
value would have refused every question ever asked — silently, no error. It was avoided
because I carry the raw semantic score through fusion as a separate field.

That's the general lesson and it's bigger than RRF: **fusion changed the units of a value
while keeping its name and its type.** A type system that only sees `float` can't help you. If
the guardrail's input were a distinct type — a `CosineSimilarity` newtype rather than a float
— the bug wouldn't compile. I avoided it by being careful, and being careful isn't a
mechanism. The structural fix is what I'd do in a codebase with more than one person in it.

### Follow-up Questions

1. Compute the RRF score for a chunk ranked third semantically and first by keyword. Now do
   it at K = 10 and K = 200. Which K lets the keyword arm's confidence win?
2. You over-fetch `max(top_k * 4, 20)` from each arm. Where did the 4 come from?
3. How would you weight the arms differently, and how would you pick the weights?
4. Give me a concrete query where fusion produces a worse top-1 than one arm alone.
5. How would you prevent the unit-mismatch class of bug structurally, not by care?

### What the Interviewer is Testing

**Concept:** rank fusion versus score normalisation, and the downstream consequences of
transforming a value.
**Hidden objective:** the unit-mismatch story. It's the difference between knowing what RRF
does and understanding what it does *to the rest of your system*.
**Common mistakes:** describing RRF mechanically without explaining why score normalisation
fails; not knowing what K controls; claiming hybrid is universally better.
**Red flags:** thinking RRF scores are comparable to similarities; not being able to name the
precision cost of fusion.
**Excellent answer:** explains why normalisation is fragile *specifically* (query-dependent
range), quantifies K's damping with numbers, concedes that fusion trades peak precision for
consistency, and tells the unit story with the structural fix — a distinct type — rather than
"we were careful".

### If CampusBrain Didn't Have This

With naive score addition: `ts_rank`'s unbounded values swamp cosine's 0–1 range, so the
keyword arm effectively dictates the ranking and the semantic arm becomes decorative. The
system would look like hybrid search and behave like keyword search — and nothing would
indicate it. **That's the worst kind of failure: a feature that's present, wired up, and
inert.**

### Real Production Incident

A refactor "simplifies" the guardrail to use `hit["score"]` — reasonably, since that's the
field name. Every question now returns the no-evidence refusal. Error rate: zero. Latency:
improved, because the LLM is never called. Health checks: green. The system is completely
broken and every dashboard says it's healthier than usual.

The only signal that catches it is refusal rate, which is precisely why it's the first metric
in the observability design and not an afterthought.

### Whiteboard Discussion

Draw two ranked lists side by side with the RRF arithmetic written out, and show a chunk
ranked 3rd/2nd beating one ranked 1st/absent. Then draw the two number lines — cosine 0–1 with
0.35 marked, RRF clustered at 0.03 — and put a big arrow from the fusion box to the guardrail
box. That arrow is the bug.

Justify carrying `semantic_score` separately, then take it to the structural fix: distinct
types for distinct units, and what it would take to adopt that here.

---

## 3.4 · The reranker you didn't build `[MEASURED & REJECTED]` · Staff → Principal

**Interviewer:**
> Most serious RAG systems put a cross-encoder reranker after retrieval. Yours doesn't. Why?

**You:**

I built it far enough to measure it, and then I removed it. That's a decision I'd defend, and
I'll give you the three conditions that would reverse it.

The reasoning had three parts. First, with hybrid search already in place, the correct chunk
was landing in the top two for every query I tested. There wasn't much ordering left to fix.
Second — and this is the part that actually decided it — **RAG passes all `top_k` chunks to
the LLM regardless of their order.** Whether the right chunk is ranked first or second, the
same five chunks go into the prompt. So the reranker would have been optimising a value
nothing downstream consumes. Third, BGE-reranker-v2-m3 means `sentence-transformers` and
`torch`, which is roughly 2 GB of image on a deployment with 512 MB of RAM that had already
been OOM-killed once.

So it was dropped, not deferred, and I wrote down what would change my mind. One: if I cut
`top_k` to one or two to save tokens, then order *does* determine the prompt contents and
reranking starts mattering. Two: if I add a search-results UI where rank is visible to a user,
rank becomes a product surface rather than an implementation detail. Three: if the corpus
grows enough that the answer stops reliably being in the top five, precision at five stops
being roughly one and there's real work for a reranker to do.

The caveat I'd volunteer: "every test query" was a handful of manual queries, not a golden
set. So it's directionally right, not rigorous. Re-running that measurement properly is on my
list once the eval harness exists, and I'd hold myself to the same standard — if a golden set
shows the correct chunk is *not* reliably top-two, the decision flips.

What I'd add if you want the theory: the reason a cross-encoder is better is the same reason
it can't scale. A bi-encoder has to compress a document into a vector *before* it knows the
query, so whatever the query turns out to be about, the representation is already fixed. A
cross-encoder reads both together with full attention across the pair, so it can attend to
the part of the document the query is actually asking about. That's a richer computation, and
it means nothing can be precomputed — cost is linear in candidates scored. That's why the
standard shape is retrieve-then-rerank: cheap and approximate to narrow, expensive and
accurate to order. Same pattern as a query planner using an index before applying an
expensive predicate.

And if I did need one, I'd probably reach for a hosted reranker — Cohere or Jina — rather than
self-hosting BGE. It inverts the trade that killed the decision: no 2 GB dependency, no model
to serve, at the cost of a per-call fee and document text leaving my infrastructure. For a
corpus of public college information that data concern is negligible, which makes it the
right shape for this system specifically.

### Follow-up Questions

1. Why can't a cross-encoder's scores be precomputed? Be precise.
2. You have a 200 ms retrieval budget. Where does a reranker fit, and what do you cut?
3. Your top-5 has three near-duplicate chunks. Is a reranker the fix?
4. How would you prove, with data, that the reranker isn't earning its latency?
5. What would make you choose ColBERT over either option?

### What the Interviewer is Testing

**Concept:** the retrieve-then-rerank cascade, and — more importantly — whether the candidate
can justify *not* building something.
**Hidden objective:** most candidates have two categories, "built" and "didn't get to". A
third — *evaluated and consciously declined* — is the strongest signal available, because it
requires having measured and having reasoned about the whole system.
**Common mistakes:** adding a reranker because it's best practice; not knowing the LLM sees
all `top_k` chunks regardless of order; missing the operational cost.
**Red flags:** claiming a reranker always improves quality; not being able to state a
reversal condition — a decision with no reversal condition is a preference.
**Excellent answer:** the system-level insight that order doesn't reach the prompt, three
named reversal triggers, and the volunteered caveat that the measurement wasn't rigorous.

### If CampusBrain Didn't Have This (inverted — if you *had* shipped it)

**Production:** ~2 GB added to a 512 MB-RAM deployment, which almost certainly means it
doesn't boot. **Engineering:** longer builds, slower cold starts on a platform that already
sleeps and restarts frequently. **Business:** no measurable answer-quality change, because the
same five chunks reach the model either way. **The cost is entirely real and the benefit is
entirely theoretical** — which is exactly what the measurement showed.

### Real Production Incident

A team adds a reranker because a blog post recommended it, without measuring first. Image size
triples, cold starts go from seconds to a minute on a platform that suspends idle instances,
and p95 latency rises by 100 ms per request. Answer quality is unchanged — the same chunks
were already reaching the model. Six months later nobody remembers why it's there, and it's
in the critical path of every request, so nobody's willing to remove it.

**Unmeasured additions become permanent.** That's the incident this decision prevents, and
it's the most common one in AI engineering.

### Whiteboard Discussion

Draw the cascade — 1M docs → ANN → 50 candidates → cross-encoder → 5 — then draw *your*
pipeline underneath and mark where the reranker would slot in. Now draw the arrow from
retrieval to the prompt and label it "all 5, in any order." That arrow is the whole argument:
the reranker's output has no consumer.

Then write the three reversal triggers on the board. Justify hosted-over-self-hosted if it
came back. Take the discussion to MMR, because the near-duplicate problem is real and a
reranker doesn't solve it — that's a diversity problem, not a relevance one.

---

# Chapter 4 — Reliability

> **Mode B.** Durable job queue, resumable ingestion, idempotent uploads, retry
> classification and the keep-alive canary are all shipped. Supersedes the pre-shipping
> versions in 1.3 and 1.4.

---

## 4.1 · Durable background work without a queue service · Staff

**Interviewer:**
> Your host suspends idle instances after fifteen minutes, and your ingestion takes minutes.
> Walk me through what happens when it gets suspended mid-job.

**You:**

Nothing is lost, because the job was never in the process to begin with.

In CampusBrain the upload endpoint writes a row into a `jobs` table and returns. That's the
whole durability story — the work is a committed database row before the HTTP response is
sent, so a process death is a scheduling problem rather than a data problem.

A job runner polls with `SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`, which is the primitive
that makes this work. `SKIP LOCKED` means a second runner walks past a row someone else has
claimed instead of blocking on it, so claiming is concurrent without a distributed lock.
When a job is claimed we stamp a `claimed_at` lease. If the instance is suspended mid-job,
that lease simply expires — and a reaper that runs on startup and periodically resets any
job whose lease is older than the timeout back to pending. So a suspension costs us the
in-flight progress on one job, not the job.

Retries are bounded. Each attempt increments a counter, and at three the job moves to a
`dead` state rather than looping. Dead jobs are surfaced on an admin endpoint, because a
dead-letter queue nobody looks at is just a slower way of losing work.

We intentionally did *not* bring in Redis or Celery for this. We'd removed arq and Redis
earlier — it was a fourth managed service for one job type at very low volume — and the
lesson from that wasn't "we needed Redis", it was "we assumed in-memory state would survive a
process that suspends". Postgres was already running, already durable, already transactional,
and `SKIP LOCKED` is a well-worn claiming primitive. The trade-off we accepted is polling
latency — a job waits up to the poll interval instead of being pushed — and that Postgres
takes write load it wouldn't otherwise. At our job rate that's nothing. I'd move to a real
broker somewhere past a hundred jobs a second, and the signal would be poll contention
showing up in the queue-depth metric.

The other thing worth mentioning is the cheapest part of the whole design. A free external
cron pings `/health` every ten minutes, which stops the instance idling out at all. So
suspension goes from a certainty to an exception, and the durable queue is the belt to that
cron's braces. That same cron doubles as the synthetic canary — it also posts a known
question and asserts the answer contains an expected fact, which is our only true end-to-end
check.

### Follow-up Questions

1. Two instances start after a deploy and both reapers run. What breaks?
2. How do you pick the lease duration? What goes wrong if it's too short?
3. A job dies three times and lands in `dead`. Who finds out, and how?
4. What does `SKIP LOCKED` give you that `FOR UPDATE` alone doesn't?
5. Your poll interval is the floor on job latency. How would you cut it without a broker?
6. Queue depth is growing steadily. Walk me through the diagnosis.

### What the Interviewer is Testing

**Concept:** durability of asynchronous work, and whether you reach for infrastructure or for
what you already run.
**Hidden objective:** can you reason about partial failure precisely — which lines run, which
don't — and can you name the threshold where your choice stops being right?
**Common mistakes:** reaching for Celery/Redis without justifying a new service; no lease, so
a dead worker's job is stuck forever; unbounded retries; a DLQ with no consumer.
**Red flags:** not knowing what `SKIP LOCKED` does; claiming Postgres-as-a-queue scales
indefinitely.
**Excellent answer:** names the lease and the reaper as the recovery mechanism, justifies
Postgres over a broker *with a stated job-rate threshold*, and mentions the cron keep-alive
as a cheap mitigation that also serves monitoring.

### If CampusBrain Didn't Have This

**Production:** ingestion has an unbounded silent failure rate. **User:** an admin uploads a
document, watches a spinner that never resolves, and retries — creating duplicates.
**Business:** the core admin workflow is unreliable and fails *silently*, which is worse than
failing loudly. **Engineering:** no recovery path exists after the fact; a lost document is
only detectable when someone notices a question can't be answered.

### Real Production Incident

An admin uploads six documents at 6 pm and leaves. Four complete; the fifth is mid-embed when
the instance idles out; the sixth hasn't started. With in-process background tasks, five and
six vanish with the process, no exception runs, and both sit at `PROCESSING` forever. Next
morning the admin re-uploads, creating duplicate chunk sets that inflate every counting
answer for months.

With the durable queue: the leases on five and six expire, the reaper resets them on the next
startup, and both complete. The admin sees `PROCESSED` in the morning and never knows
anything happened.

### Whiteboard Discussion

Draw the `jobs` table with its state machine — `pending → claimed → done | dead` — and mark
the lease as the edge from `claimed` back to `pending`. That edge *is* the recovery. Then
draw the timeline with the suspension line across it and show the job surviving.

Justify Postgres over a broker with the job-rate number. Then take the scaling discussion
yourself: poll interval as the latency floor, and what changes at a dedicated worker process.

---

## 4.2 · Idempotency and resumable ingestion · Senior → Staff

**Interviewer:**
> Suppose embedding fails on chunk 42 of 47. What happens?

**You:**

We resume at 42. Chunks 1 through 41 are already embedded and we don't pay for them again.

The pipeline persists chunks to Postgres *before* any embedding happens, and each chunk row
carries an `embedded_at` timestamp that stays null until its vector is successfully upserted.
So the embedding stage is just "find chunks in this document where `embedded_at is null`,
embed them in batches, stamp them". Retrying is naturally incremental because the query
naturally narrows.

That ordering was a deliberate change and it fixed something worse than slowness. The
original pipeline deleted the existing Qdrant points and chunk rows *first*, then re-chunked
and re-embedded. The delete ordering was actually correct — the chunk ID is the Qdrant point
ID, so once you drop the rows you can't address the points any more — but it meant a crash in
that window left the document with zero chunks and zero vectors. Old content gone, new
content never written. That's data loss, not lost progress. Now we build the new version
alongside and only swap once it's complete, so a failure mid-way leaves the previous version
serving.

On idempotency: every upload is hashed, and there's a unique constraint on
`(org_id, content_hash)`. If the same bytes arrive again the API returns 200 with the existing
document rather than 201 with a new one. That distinction matters for the retry story — if the
network drops after the server commits but before the client sees the response, the client
retries, and the correct behaviour is to get the same document back rather than a second copy.

I'd emphasise that the constraint is in the *database*, not a check-then-insert in the
application. Two concurrent uploads of the same file both hash, both miss, and both try to
insert — the application check has a race and the constraint doesn't. We catch the integrity
error and return the existing row.

Why this matters beyond tidiness: **idempotency is a prerequisite for retries, not a feature
alongside them.** Retrying a non-idempotent operation just multiplies the damage. So this had
to land before the retry logic in 4.3, not after.

The one case content hashing doesn't cover is an edited document — same document, different
bytes, so a new row. That's correct, but it means updates go through an explicit replace
operation rather than relying on dedupe.

### Follow-up Questions

1. Two identical uploads arrive concurrently. Trace both, precisely.
2. Why hash the content rather than trust the filename?
3. Should the hash be scoped per org or global? What does each imply?
4. Someone uploads the same content as a `.docx` and a `.pdf`. Different bytes. Should you
   catch that?
5. How do you build the new chunk set alongside the old without doubling storage?
6. What invalidates `embedded_at` — when *must* a chunk be re-embedded?

### What the Interviewer is Testing

**Concept:** idempotency, resumability, and their relationship to safe retries.
**Hidden objective:** do you understand that idempotency *gates* reliability work? And can
you spot the delete-before-write window as data loss rather than slowness?
**Common mistakes:** treating dedupe as a cost optimisation; missing the concurrent-insert
race; enforcing uniqueness in application code.
**Red flags:** claiming resumability without a per-chunk state field; not seeing why the
delete ordering was originally required.
**Excellent answer:** the database-constraint-not-application-check point, 200-with-existing
for retry safety, and the build-alongside-then-swap reasoning for re-indexing.

### If CampusBrain Didn't Have This

**Production:** a transient 503 on chunk 42 fails the whole document, and the retry re-embeds
all 47. **User:** counting and list answers inflate as duplicates accumulate; the sources
panel shows the same content twice under different filenames. **Business:** answers are wrong
in a way that looks like the AI is bad when it's an ingestion bug. **Engineering:** you can't
safely retry anything, which blocks the entire reliability pillar.

### Real Production Incident

An upload times out at the proxy after 30 seconds. The server actually succeeded and started
processing; the client never saw the 201. The admin retries twice. Without the unique
constraint, three documents now exist for one file. A month later "how many students interned
at KlearNow?" returns triple the real number, and the investigation starts in the prompt and
the retrieval layer — because that's where counting bugs live — and takes days to reach
ingestion.

With the constraint, both retries return 200 and the same document ID, and nothing downstream
ever sees a duplicate.

### Whiteboard Discussion

Draw the upload sequence — client, API, database — and shade the window where a timeout
leaves the client uncertain but the server committed. That window is why idempotency exists.

Then draw the chunk table with `embedded_at` and show the resume query narrowing on each
attempt. Justify the constraint at the database over a check in the application by drawing
the two concurrent inserts. Then connect forward: idempotency is what makes 4.3's retries
safe.

---

## 4.3 · Retry classification and the quota that isn't a rate limit · Senior → Staff

**Interviewer:**
> Gemini returns a 429. What does your system do?

**You:**

It depends what the 429 means, and that distinction is the whole answer — because we learned
it the hard way.

We classify before we retry. Connection resets, timeouts and 5xx are transient, so those get
exponential backoff with jitter. A 429 carrying `Retry-After` gets exactly that wait, because
the server has told us. A 400 or a 401 never gets retried — it's deterministic and will fail
identically forever. Content-safety refusals aren't retried either, for the same reason.

The interesting case is a 429 from a **daily quota**, and that one is not retryable at all.
We hit this on a previous provider whose free tier was fifty requests *per day*, not per
minute. We had exponential backoff in front of it — five, ten, twenty, forty seconds — and
what that did was turn a 400-millisecond failure into a 75-second one while burning four
extra requests of the quota we'd already exhausted. The retry loop made the outage worse and
consumed the resource it was waiting for.

So the rule we encoded is that **429 is ambiguous** — it means "slow down" *and* "come back
tomorrow", and only the first is retryable. We read the provider's quota documentation before
writing the retry policy rather than after.

On top of that there's a circuit breaker. If the provider fails repeatedly we stop calling it
for a cooling-off window and fail fast, because at that point every request is a slow failure
that holds a connection open — and we run a single worker, so slow failures block real
traffic. Fast failure is the kinder outcome.

Jitter matters more than people expect. Without it, every client that hit the same outage
backs off on an identical schedule and they all retry in lockstep, recreating the thundering
herd that caused the outage. We multiply each backoff by a random factor.

The trade-off is that retries hide transient failures from the user, which is the point, but
they also hide them from *you* — so every retry is logged with its attempt number and the
classification decision, and retry rate is a metric. A rising retry rate is an early warning
that a provider is degrading before it starts failing outright.

Where this changes: today the retries are in-process and synchronous within a job. If we ever
had a multi-provider setup, the escalation would be to fail over behind the `LLMProvider`
Protocol rather than to keep retrying one vendor — that abstraction has already paid for
itself once during a provider migration, and failover is the second time it would.

### Follow-up Questions

1. Why is jitter necessary? What exactly goes wrong without it?
2. Distinguish a rate-limit 429 from a quota 429 at runtime, programmatically.
3. Where should the circuit breaker live — per provider, per endpoint, per tenant?
4. A timeout fires. Is the operation retryable? What do you need to know first?
5. Retry rate doubles overnight but the error rate is flat. What's happening?

### What the Interviewer is Testing

**Concept:** retry classification, and the recognition that retrying the wrong error is
actively harmful.
**Hidden objective:** does the candidate know that 429 encodes two different failures? Almost
nobody does until they've been burned.
**Common mistakes:** retrying everything; no jitter; no cap; treating a safety refusal as
transient.
**Red flags:** "we retry 429s" with no qualification; not knowing what a circuit breaker
protects against.
**Excellent answer:** the quota-versus-rate distinction with the concrete incident, jitter
justified by the thundering herd, and the observation that retries hide failures from you as
well as from users — hence the retry-rate metric.

### If CampusBrain Didn't Have This

**Production:** a single transient 503 during a 47-chunk ingest fails the whole document.
**User:** uploads fail intermittently for no visible reason. **Business:** the system looks
flaky in a way nobody can reproduce. **Engineering:** with no classification, adding retries
to fix the transient case *amplifies* the quota case — you make one failure mode better and
another dramatically worse.

### Real Production Incident

The free-tier daily cap is exhausted at 3 pm. Every subsequent chat request enters a
five-attempt backoff — 75 seconds each, four extra calls each — against a quota that resets
at midnight. On a single worker, those held connections starve everything else. The service
appears completely down rather than degraded, and it self-heals at midnight UTC with no
deploy, which makes the cause maximally confusing.

With classification: the quota 429 fails fast, the circuit breaker opens, and the system
degrades to refusals in a few hundred milliseconds instead of hanging. The logged
classification says exactly which kind of 429 it was.

### Whiteboard Discussion

Draw a decision tree from the response: status → classification → retry / fail fast / circuit
open. Put 429 at the centre with two branches and label them "slow down" and "come back
tomorrow."

Then draw the timeline of the bad case — 5, 10, 20, 40 — against a quota that resets at
midnight, and show that no schedule fits inside it. Justify jitter with two clients retrying
in lockstep. Take it to multi-provider failover as the next escalation.

---

# Chapter 5 — Observability

> **Mode B.** Structured logging with request correlation, RAG quality signals, in-process
> metrics and split liveness/readiness probes are shipped.

---

## 5.1 · Debugging a wrong answer from yesterday · Senior

**Interviewer:**
> A user says the chatbot gave them a wrong answer about fees yesterday. Walk me through it.

**You:**

I'd start from the request ID. Every response carries an `X-Request-Id` header, so support
asks the user for it, and if they don't have it I search the log by the question text and the
timestamp.

That gives me one JSON event with everything the request did. The first field I look at is
`retrieved_chunk_ids`, because it splits the problem in half. If the chunk that contains the
right answer isn't in that list, it's a retrieval failure — and I'm looking at chunking,
embeddings or the fusion. If it *is* in the list, the model had the correct context and
produced a wrong answer anyway, which is a generation problem and sends me to the prompt. Those
are completely different fixes, and without the chunk IDs I'd be guessing which half of the
system to open.

Then `best_semantic_score` against the threshold, to see whether the refusal guardrail nearly
fired — a score of 0.36 that squeaked through is a different story from 0.85. Then
`prompt_version` and `llm_model`, because both can change under me and either would explain a
behaviour change with no code deploy. The model is behind a floating alias, so "did the model
change" is a real hypothesis, not a paranoid one.

The stage timings tell me if it was slow as well as wrong, which occasionally points at
something like a cold start.

We intentionally log the question verbatim but not the answer text or the full prompt. The
prompt is reconstructable from `retrieved_chunk_ids` plus `prompt_version` — logging inputs
and identifiers rather than derived artifacts keeps the volume down, and it means a prompt
change doesn't invalidate the log history. The trade-off is that reconstructing an old prompt
requires the chunks to still exist, so a re-index makes very old requests only partly
reproducible. We accepted that.

Logging the question does make it user content, so it has a stated retention period rather
than living forever by default.

The correlation itself is a request ID in a `contextvars.ContextVar`, set by the outermost
middleware and injected into every log record by a `logging.Filter`. That means third-party
libraries and our own error handler pick it up without knowing it exists. We deliberately
didn't thread it through as a parameter — that would have changed the signature of four
layers to carry a value none of them read.

### Follow-up Questions

1. Why a `ContextVar` rather than `threading.local`?
2. You accept an inbound `X-Request-Id`. What could a client do with that?
3. The user has no request ID and can't remember their exact wording. Now what?
4. How do you tell a retrieval failure from a chunking failure? Both look like a missing chunk.
5. Why not OpenTelemetry?

### What the Interviewer is Testing

**Concept:** debuggability as a design property, and whether logs are structured for
*queries* rather than for reading.
**Hidden objective:** does the candidate know which single field splits the problem space?
Naming `retrieved_chunk_ids` and explaining why is the signal.
**Common mistakes:** listing fields without a diagnostic order; logging everything including
prompts and answers with no retention thought; no correlation ID.
**Red flags:** "we'd reproduce it locally" — that stops working the moment someone else hits
the bug.
**Excellent answer:** the diagnostic *sequence*, the inputs-not-derived-artifacts principle,
and volunteering the retention decision before being asked.

### If CampusBrain Didn't Have This

**Production:** every wrong-answer report is unreproducible unless the developer can guess
the user's exact wording. **User:** reports a problem and nothing happens, because nobody can
find it. **Business:** quality complaints can't be triaged, so you can't tell one systemic bug
from ten unrelated ones. **Engineering:** you can't distinguish retrieval failure from
generation drift, so every investigation searches the whole pipeline.

### Real Production Incident

A model version changes behind its alias. Answers get subtly worse on counting questions —
the "never narrate" instruction is followed less strictly. No error, no metric moves, no
deploy. Without `llm_model` in the log there is nothing tying the behaviour change to
anything, and the team spends days re-reading their own prompt looking for a bug they didn't
introduce.

With it, the first query is "group by `llm_model`, compare before and after", and the answer
takes a minute.

### Whiteboard Discussion

Draw the `rag_answer` event as a box with its fields listed, and number them in *diagnostic
order* — chunk IDs first, then score, then versions, then timings. Explain that the ordering
is the actual content: it's a decision procedure, not a field list.

Then draw the three failure surfaces — retrieval miss, context poisoning, generation drift —
and show which field discriminates between them. Take it to what you'd add for a second
process: OTel, and why not before.

---

## 5.2 · Detecting silent degradation without labels · Staff

**Interviewer:**
> Your error rate is zero, latency is fine, health checks are green. How would you know
> retrieval quality had degraded?

**You:**

Proxy signals, because in production I have no ground truth — nobody tells me the right
answer.

The best single one is **refusal rate**. CampusBrain refuses when nothing retrieved clears a
similarity floor, so a spike means retrieval broke, the corpus changed, or the embedding model
drifted — and none of those raise an error. Refusal is a valid response, so it's completely
invisible to error-rate monitoring. That's what makes it valuable: it's a quality signal
hiding inside a success path.

Second is the distribution of the top semantic score. That shifts when the embedding model
changes behind its alias or the corpus changes shape, and a distribution shift is detectable
without knowing any right answer.

Third is per-arm retrieval hit rate — how many of the fused results came from each arm. We
track that specifically because a hybrid system hides the death of either arm, and we learned
that the expensive way: our keyword arm returned nothing for months because `plainto_tsquery`
ANDs every term, and the semantic arm covered for it completely. No error, no alert, no user
report. Found by accident. So now `zero_keyword_hit_rate` is a metric, and the general
principle we took from it is that **every redundant subsystem needs per-component
observability, or redundancy converts a loud failure into a silent degradation.**

Fourth is mean citations per answer, which drops when grounding degrades or the citation
validator regresses.

We alert on shift against a rolling median rather than absolute thresholds, because absolutes
drift as the corpus grows — a threshold set today is wrong in a month.

And the check that actually catches things end to end is a synthetic canary: a free external
cron posts a known question every fifteen minutes and asserts the answer contains an expected
fact. That's the only check that exercises embed, search, fuse, prompt and generate together.
A health check proves the HTTP server is accepting connections; the canary proves the system
still answers correctly. It also keeps the instance from idling out, so one free cron job is
doing monitoring and reliability work at once.

On the metrics implementation itself — in-process counters with bounded ring buffers, exposed
on an authenticated endpoint. Bounded specifically because an unbounded latency list is a slow
leak on a memory-constrained box, and a metrics system that OOMs the service it monitors is a
classic own-goal. They reset on restart, which is fine because they're a live operational view;
the durable layer is the logs, and every one of these metrics is derivable from the
`rag_answer` event.

The migration trigger is a second instance — in-process counters are per-process, so
`/metrics` would return whichever one answered, which is meaningless rather than merely
incomplete. That's when a hosted metrics backend earns its keep, and it brings history and
alerting with it.

### Follow-up Questions

1. Refusal rate doubles. Give me three hypotheses in order of likelihood.
2. Why alert on distribution shift rather than a threshold? Show me a case where the
   threshold fails.
3. Your canary asserts one fact. How many canaries do you need, and how do you pick them?
4. Metrics reset on restart. Defend that.
5. What's cardinality, and why does it constrain how you label these?

### What the Interviewer is Testing

**Concept:** monitoring quality without ground truth — the defining problem of production ML.
**Hidden objective:** does the candidate understand that error rate is blind to a whole class
of AI failure, because wrong answers are successful responses?
**Common mistakes:** proposing user feedback as the primary signal (too sparse, too late);
absolute thresholds; no per-component visibility in a redundant system.
**Red flags:** "we'd monitor accuracy" with no explanation of where labels come from.
**Excellent answer:** refusal rate as the primary signal *with the reasoning*, the per-arm
lesson from a real incident, shift-not-threshold, and the canary as the only true end-to-end
check.

### If CampusBrain Didn't Have This

**Production:** quality regressions are detected by users, or never. **User:** answers quietly
get worse and people stop using it rather than reporting it. **Business:** you lose trust
before you learn there's a problem. **Engineering:** with no signal, every quality change is
unattributable — you can't tell whether last week's chunking change helped or hurt.

### Real Production Incident

A corpus re-ingest partially fails. Half the documents are indexed. Retrieval still returns
chunks — just fewer relevant ones. Error rate: zero. Latency: *improved*, because there's less
to search. Health checks: green. Every dashboard says the system is healthier than usual while
it silently can't answer half the questions it could yesterday.

Refusal rate is the only thing that moves, and it moves immediately.

### Whiteboard Discussion

Draw the request path and mark where each signal is emitted. Then draw two graphs side by side
for the partial-reingest incident: error rate flat at zero, refusal rate spiking. That
contrast is the entire argument for quality-specific monitoring.

Justify shift-based alerting by drawing a threshold line and showing the corpus growing under
it. Then take it to the canary and what it covers that no probe does.

---

## 5.3 · Liveness versus readiness · Mid → Senior

**Interviewer:**
> You have two health endpoints. Why not one?

**You:**

Because they answer different questions and failing them means opposite things.

`/health` is liveness — is this process alive? It's deliberately dependency-free. It checks
nothing external and returns immediately. `/health/ready` is readiness — can this instance
actually serve? That one checks Postgres, Qdrant and object storage.

The reason liveness must not touch dependencies is the failure mode. If liveness checked
Postgres and Postgres blipped for thirty seconds, the platform would kill every healthy
instance, they'd restart, still fail to reach the database, and crash-loop. **You've turned a
thirty-second blip into a multi-minute outage using your own health check.** Dependencies
belong in readiness, because the right response to a dependency being down is to stop routing
traffic, not to restart a process that will come back equally unable to reach it.

The part I'd want to draw out is which dependencies are fatal, because that's a product
decision rather than a technical one. Postgres and Qdrant are fatal — chat reads chunk text
from Postgres and vectors from Qdrant, so without either it cannot answer, and readiness
returns 503. Object storage is reported but **not** fatal. Storage is only needed to ingest a
new document; chat never reads a blob. If we failed readiness on storage we'd take the
chatbot down for every student because an admin can't upload, which is obviously the wrong
trade. So it returns 200 with storage marked degraded.

That's graceful degradation — the system loses a capability rather than losing service — and
deciding it required tracing which dependency is actually on which request path.

One detail that isn't obvious: the error strings are exception *type names*, never messages.
The endpoint is unauthenticated, and a raw connection error can contain a DSN with a
password. Leaking a database credential through a health check would be an embarrassing way
to get breached.

Where this evolves: we don't have a startup probe yet, and we should measure cold-start time
before deciding — the app imports a heavy OCR stack, and a slow boot plus an aggressive
liveness timeout is a kill loop before the process ever finishes starting. And once anything
polls readiness frequently, the checks need caching and explicit timeouts, otherwise you've
built a load generator aimed at the dependencies you're trying to protect.

### Follow-up Questions

1. What's a startup probe for, and when would you need one here?
2. Your readiness check has no timeout. A dependency gets slow rather than dying. What
   happens?
3. Health checks pass but users get errors. What did you miss?
4. How do you stop readiness checks overloading the database?
5. Nothing on your platform consumes readiness. Why build it?

### What the Interviewer is Testing

**Concept:** probe semantics, and per-dependency blast-radius reasoning.
**Hidden objective:** the restart-amplification trap. Most candidates get liveness and
readiness backwards, or check everything in both.
**Common mistakes:** dependency checks in liveness; treating all dependencies as equally
fatal; leaking exception messages.
**Red flags:** can't say what happens when each probe fails; no reasoning about which
dependency is on which path.
**Excellent answer:** the restart-storm mechanism, the storage-is-not-fatal product decision,
and the credential-leak detail — that last one shows you thought about the endpoint as an
attack surface.

### If CampusBrain Didn't Have This

**Single combined probe checking everything:** a Postgres blip restarts every instance and
turns a brief degradation into a full outage. **Single probe checking nothing:** a deadlocked
or dependency-less instance keeps receiving traffic and serving errors indefinitely, because
nothing ever restarts it. **Business:** either way, a recoverable incident becomes a prolonged
one.

### Real Production Incident

A managed Postgres provider does a routine failover — about forty seconds of connection
errors. With a dependency-checking liveness probe, every instance is killed, restarts into
the same failure, and enters backoff. What should have been forty seconds of elevated errors
becomes a ten-minute outage, and the postmortem's root cause is the health check.

With the split: liveness stays green, readiness goes 503, traffic stops routing, and when
Postgres returns, readiness recovers on its own with no restart.

### Whiteboard Discussion

Draw two probes with arrows to their failure actions: liveness → **restart**, readiness →
**remove from pool**. Then draw the restart-storm loop and make it visibly a cycle — that
picture is the argument.

Next draw the dependency graph for a *chat* request and a *upload* request separately, and
show storage appearing only in the second. That's the justification for `critical_ok`. Then
take it to startup probes and cold-start measurement.

---

# Chapter 6 — Evaluation

> **Mode B.** The 75-question golden set, the retrieval harness, the calibrated judge and the
> two-tier CI gate are shipped.
>
> **Numbers below appear as `[measured]` placeholders.** Every other Mode B claim is a design
> that exists on paper and can be built as described; a specific eval score is a *measurement*
> and cannot be rehearsed honestly. Run the harness, then fill these in — those are the only
> numbers in this handbook you must supply yourself.

---

## 6.1 · Proving a retrieval change is an improvement · Senior → Staff

**Interviewer:**
> You change your chunking strategy. How do you know it helped?

**You:**

I run it against the golden set and compare, and the discipline around *how* matters more
than the metric.

The golden set is 75 questions with known relevant sources. I picked 75 deliberately — at
that size a hit-rate around 0.8 has a 95% confidence interval of roughly plus or minus nine
points, so I can detect a ten-point change and I can't detect a five-point one. Below about
thirty questions it isn't measurement, it's anecdote. Above a couple of hundred I wouldn't
maintain it, and honestly the corpus doesn't contain that many genuinely distinct answerable
facts.

The procedure: freeze the golden set before touching anything, measure the baseline on the
shipped configuration, change one variable, re-measure, and report with the confidence
interval. Then confirm on a held-out fifteen questions I've touched exactly once, so I'm not
tuning on my own test set.

The metrics are hit-rate@5 as the primary — did at least one relevant chunk make it in,
because if it didn't the model *cannot* answer correctly and the failure is guaranteed
upstream — plus recall@5 for list-type questions where the answer is spread across chunks, and
MRR for ordering. I compute nDCG too and I'll be honest that it adds almost nothing here: my
relevance labels are binary with one to three relevant chunks per question, so it's close to a
monotone transform of MRR. It would earn its keep if I graded relevance on a scale.

The part that matters most for a chunking change specifically is that the golden set is
labelled by **document plus a quoted span**, not by chunk ID, and resolved to chunk IDs at
evaluation time. Chunk IDs are stable until you re-chunk — and "is my chunk size right" is
exactly the experiment you want to run, so an ID-labelled set can't survive the experiment it
exists to enable. That's a small design decision with a large consequence.

I report per archetype, never one aggregate. I tag questions as lookup, count, list,
comparison or synthesis, because they stress different parts of the pipeline — an average
happily hides "counting questions are at 0.4" behind "lookups are at 0.95". A net improvement
that regresses one category is a different decision from a uniform one.

Concretely, on chunk size: the sweep across 500, 1000 and 2000 moved hit-rate@5 by
`[measured]`, which was `[inside / outside]` the noise floor — so the honest conclusion was
`[keep 1000 / move to X]`. Reporting the changes that did *nothing* is what makes the ones
that did something credible.

The whole thing runs in CI on every pull request. No LLM calls — retrieval evaluation is pure
arithmetic against chunk IDs — so it's free, deterministic and fast enough to block a merge.
The gate fails on a hit-rate drop larger than the noise floor, about five points, not on any
drop at all, because a gate that fires on random variation gets disabled within a week.

### Follow-up Questions

1. Hit-rate is identical for two configurations. Which is better and how do you tell?
2. Your change improves hit-rate six points at n=75. Ship it?
3. Why label by quoted span rather than chunk ID? What breaks otherwise?
4. Where do the 75 questions come from? How do you avoid biasing them?
5. How do you keep a golden set from rotting as the corpus changes?
6. When is nDCG the right metric?

### What the Interviewer is Testing

**Concept:** offline evaluation methodology, and statistical honesty about small samples.
**Hidden objective:** does the candidate know their sample size doesn't support the precision
they're implying? Volunteering the confidence interval is the strongest signal in this entire
chapter.
**Common mistakes:** one metric; no confidence interval; tuning on the test set; sweeping
several variables at once; reporting only the wins.
**Red flags:** quoting scores to three decimals at n=75; claiming statistical significance
from a small move; evaluating retrieval by reading answers, which confounds retrieval with
generation.
**Excellent answer:** states the noise floor unprompted, explains the span-not-ID labelling
with its reason, reports per archetype, and mentions the null results.

### If CampusBrain Didn't Have This

**Production:** every tuning decision is a guess, and you can't tell an improvement from
noise. **User:** quality changes randomly with each deploy. **Business:** you cannot answer
"is it good?" or "is it getting better?" — the two questions any buyer asks. **Engineering:**
seven separate parameters stay untuned indefinitely, because tuning without measurement is
just churn.

### Real Production Incident

A team ships a chunking change based on ten hand-checked queries that "looked better".
Retrieval quality actually regresses for counting and list questions, which weren't in the
ten. It surfaces six weeks later as scattered complaints that never get connected to the
change, and rolling back is now entangled with three other deploys.

With a frozen golden set and per-archetype reporting, the regression appears in the pull
request as a red gate on the `count` archetype, before merge.

### Whiteboard Discussion

Draw the harness: golden set → retrieval → metrics → report, with the config snapshot hanging
off the report. Emphasise that no LLM is involved — that's what makes it CI-viable.

Then draw a confidence interval as an error bar and put two candidate results inside each
other's bars. That picture *is* the honesty argument. Then sketch the per-archetype table and
show an aggregate hiding a regression. Take it to the judged metrics as the next tier.

---

## 6.2 · Judging what a metric can't measure · Staff → Principal

**Interviewer:**
> Retrieval metrics tell you the right chunk was there. How do you know the *answer* was good?

**You:**

That's where the RAG triad comes in, and where I have to use a model to grade a model — which
introduces its own error, so most of the design is about controlling that.

Three metrics, and the value is that each blames a different component. Context relevance
blames retrieval. Faithfulness — is every claim supported by the retrieved context — blames
generation, and a low score there is a hallucination. Answer relevance blames generation too,
but differently: it's grounded and off-target. So a bad answer becomes a pointer to which part
of the pipeline to open, rather than a vague quality complaint.

Faithfulness is implemented as **claim decomposition**, not a holistic score. We split the
answer into atomic claims and ask a binary supported / not-supported question per claim, then
take the ratio. Two reasons. It localises the failure — "faithfulness 0.5" is a number,
"claim B is unsupported" is a bug report with the exact sentence. And each sub-judgement is
far more reliable: "is this one sentence supported by this context" is close to an entailment
task, which models do consistently. "Rate the overall faithfulness one to five" requires
holistic judgement, which they do badly — the boundary between three and four isn't defined
anywhere, so the model invents one and invents a different one next time. Test-retest
reliability on a binary judgement is much better than on a Likert scale. We get gradation from
aggregation, not from the scale.

On controlling variance: temperature zero, the judge model pinned to a dated snapshot and
recorded in every report, three samples with a majority vote, randomised option order for any
pairwise comparison, and structured output so parsing isn't a second source of error.

The one I'd emphasise is that **the judge is a different model from the generator.** Our
generator is a Gemini Flash model; if we judged with the same model we'd be grading its own
homework, and self-preference bias is well documented — models rate their own outputs higher.
We use a stronger model as the judge, which is affordable because judging is cheaper than
generating and runs nightly rather than per request.

And we calibrated it. Twenty-five hand-labelled examples, run the judge on the same
twenty-five, compute Cohen's kappa — agreement corrected for chance, because raw agreement is
inflated when one class dominates. If ninety percent of answers are faithful, a judge that
always says "faithful" gets ninety percent agreement and a kappa near zero. Ours is
`[measured]`; above 0.6 I trust it for relative comparisons, and I report the kappa alongside
every faithfulness score, because a judge score without its agreement figure is unattributable.

The rule underneath all of it: **every assertion that can be deterministic must be.** Judges
are the last resort, not the first. In our system a surprising amount is deterministic — the
refusal string is an exact match, citation markers must be in range and contiguous,
non-refusals must cite at least one source, expected facts appear as substrings for count and
lookup questions, and even the "don't narrate your counting" prompt clause is a regex. That's
eight assertions with no model call, running on every commit for free. Judged metrics run
nightly on the residue that's genuinely semantic.

### Follow-up Questions

1. Why does a binary rubric beat a 1–5 scale? Be specific about the mechanism.
2. Your judge and generator share a family. What's the concrete risk?
3. Kappa comes back at 0.35. What do you change?
4. Which of your quality checks could be deterministic that currently aren't?
5. Nightly judged metrics regress but retrieval metrics are flat. Diagnose it.
6. How do you stop 225 judge calls hitting the same daily quota that took you down before?

### What the Interviewer is Testing

**Concept:** LLM-as-judge, and the recognition that a judge is an *instrument* requiring
calibration.
**Hidden objective:** self-preference bias and calibration. Almost nobody mentions either
unprompted, and both are the difference between a measurement and a number.
**Common mistakes:** Likert scales; judging whole answers rather than claims; no calibration;
unpinned judge version; a single sample.
**Red flags:** quoting a faithfulness score with no judge named; using the generator as the
judge without noticing.
**Excellent answer:** claim decomposition with both justifications, self-preference named
explicitly, kappa reported alongside the score, and the deterministic-first rule with concrete
examples from the system.

### If CampusBrain Didn't Have This

**Production:** hallucinations are invisible — retrieval metrics say the chunk was there, and
nothing checks whether the answer used it. **User:** confident wrong answers about fees and
eligibility, grounded in correct context that the model ignored. **Business:** the failure
mode with the most reputational damage is precisely the one you can't see.
**Engineering:** prompt changes ship unverified, because prose output has no assertion.

### Real Production Incident

A prompt change adds a clause that improves counting and, as a side effect, makes the model
slightly more willing to fill gaps — it starts inferring beyond the context on questions where
the answer is partial. Retrieval metrics are unchanged, because retrieval is unchanged. No
error, no latency change. Faithfulness is the only thing that moves, and without it the
regression ships and is discovered weeks later by a user disputing a fee figure.

### Whiteboard Discussion

Draw the triad as a triangle — question, context, answer — with each metric labelling an edge,
and annotate which component each one blames. That's the diagnostic value in one picture.

Then draw the judge pipeline: answer → claims → per-claim binary → aggregate, with the
calibration set hanging off it feeding kappa. Justify binary over Likert. Then draw the
two-tier CI split — deterministic per commit, judged nightly — and take the cost discussion
yourself, including the daily-quota lesson from the provider incident.

---

# Chapters 7-8 - Pending

| Ch | Chapter | Mode | Note |
|---|---|---|---|
| 7 | Security | A | 1.2 covers the core today. Pillar 3 adds streaming upload + history sanitisation |
| 8 | Performance & Scaling | A | The 248 s ingestion and its interface-shape root cause is a strong story available now |

# Chapter 9 — Production Incidents

> **Mode A.** Every incident here actually happened. Nothing is reconstructed or embellished.
> Sources: code comments written at the time, `DEPLOYMENT_JOURNAL.md`, and git history.

## Before you narrate anything: the structure

Most candidates tell an incident chronologically — *"so I was working on X, and then I
noticed…"* — which buries the impact and makes the interviewer wait for the point. Use this
order instead. It is how a postmortem is written and how a senior engineer speaks.

| Order | Beat | Why it's here |
|---|---|---|
| 1 | **Impact** | What broke, for whom, for how long. Lead with it |
| 2 | **Detection** | How you found out. *"A user told me"* is a finding about your monitoring |
| 3 | **The wrong hypothesis** | What you thought it was first. **Most candidates skip this. It is the most credible part of any incident story** |
| 4 | **Root cause** | The actual mechanism, precisely |
| 5 | **Fix** | What you changed |
| 6 | **Prevention** | What stops it recurring — usually different from the fix |
| 7 | **The generalisable lesson** | One sentence that transfers beyond this system |

Beat 3 is the differentiator. An incident story with no wrong turn sounds rehearsed, because
real debugging always has one. Naming what you believed and why you were wrong is what makes
the rest believable.

## The honesty question you will be asked

> *"How many users were affected?"*

Answer it directly: **the system is deployed and live, but I don't have usage data from those
periods, because request logging didn't exist yet.** That is not a dodge — it is the same gap
that made several of these incidents hard to detect, and saying so converts an awkward
question into the observability discussion you want to have anyway.

Never inflate. *"Thousands of users were impacted"* collapses on one follow-up. *"I can't tell
you, and the reason I can't tell you is itself the finding"* does not.

---

## 9.1 · The outage that looked like a CORS bug `INC-002 + INC-004` · Mid → Senior

**Interviewer:**
> Tell me about a production outage you had to debug.

**You:**

The chatbot went down for an afternoon, and I spent most of that afternoon fixing the wrong
thing.

**Impact:** every chat request failed. Not intermittently — every single one. It self-healed
around 5:30 the next morning with no deploy from me, which turned out to be the biggest clue
and I didn't recognise it at the time.

**Detection:** I noticed it myself. The frontend showed "Failed to fetch" on every question.

**What I thought it was:** a CORS problem. The browser console was reporting a CORS failure —
no `Access-Control-Allow-Origin` header on the response — and CampusBrain is a split-origin
deploy, Vercel frontend and Render backend, so CORS misconfiguration was a completely
plausible hypothesis. I went through the allowed origins, checked the environment variables,
redeployed twice.

**The actual root cause was two bugs stacked.** The underlying failure was that our LLM
provider's free tier had a quota of **fifty requests per day**, not per minute, and we'd
exhausted it. Every call was returning 429, which raised an exception in the request handler.

The reason it *looked* like CORS is the second bug. Starlette's default 500 handler sits
outside every middleware, including the CORS middleware. So an unhandled exception produced a
bare `Internal Server Error` response with none of the CORS headers attached — and the browser
doesn't tell you "the server returned a 500 without CORS headers", it tells you it was blocked
by CORS policy. The real error was completely invisible from the client side.

**The fix** was two things. I added a middleware that catches unhandled exceptions and returns
a proper JSON 500 — registered deliberately *before* the CORS middleware, so that CORS wraps
it and gets to stamp its headers on the response it returns. That way a server error presents
as a server error. Then I swapped providers, because there is no fix for a daily cap.

**And I removed the retry logic**, which is the part I find most instructive. We had
exponential backoff on 429 — five, ten, twenty, forty seconds. That code was written assuming
429 means "you're going too fast". It can also mean "come back tomorrow", and those need
opposite responses. What our retry loop actually did was turn a 400-millisecond failure into a
75-second one and consume four extra requests of the quota we had already exhausted. The
retry logic made the outage measurably worse and burned the resource it was waiting for.

**Prevention:** classify errors before retrying — transient gets backoff with jitter, a daily
quota fails fast. And structured error logging with a request ID, so the server-side cause is
visible even when the client-side symptom points somewhere else entirely.

**The lesson I took:** an error's *presentation* can point at a completely unrelated
subsystem, and middleware ordering determines whether a failure is diagnosable at all. Also —
read the provider's quota documentation before writing the retry policy, not after.

### Follow-up Questions

1. How would you distinguish a rate-limit 429 from a quota 429 programmatically?
2. What would have told you the truth in five minutes instead of four hours?
3. Why did the self-healing at 5:30 am matter, and why didn't you notice?
4. You added a middleware *before* CORS. Explain the ordering.
5. What's the right retry policy for each 4xx and 5xx class?

### What the Interviewer is Testing

**Concept:** debugging under a misleading symptom, and retry classification.
**Hidden objective:** did you follow the evidence or your first hypothesis? Volunteering the
wrong turn — four hours on CORS — is what makes this a credible story rather than a rehearsed
one.
**Common mistakes:** telling it chronologically; omitting the wrong hypothesis; presenting
the retry loop as a good thing that didn't help, rather than a thing that actively hurt.
**Red flags:** claiming you found it immediately; not being able to explain the middleware
ordering mechanism.
**Excellent answer:** the two-bug stack explained separately, the retry loop identified as an
*amplifier*, and the self-healing-at-midnight detail recognised in hindsight as the clue that
would have solved it in minutes.

### If CampusBrain Didn't Have This

Without the error middleware, every unhandled server error still presents to the browser as a
CORS failure. **Engineering:** every future 500 is misdiagnosed the same way, and the cost is
paid again on each one. **Business:** mean time to resolution stays high for an entire class of
failure, permanently.

### Real Production Incident

This is one. The compounding detail worth stating: on a single worker, those 75-second retries
hold connections open, so during the outage the service didn't just fail — it became
unresponsive. A fast failure would have been strictly better for everyone.

### Whiteboard Discussion

Draw the middleware stack as concentric boxes with Starlette's default 500 handler *outside*
all of them. That picture explains the whole misdiagnosis. Then draw the fix — the error
middleware inside CORS — and show the response now carrying headers.

Next, draw the retry timeline (5, 10, 20, 40) against a quota resetting at midnight and show
that no schedule fits inside it. Take it to a retry-classification decision tree.

---

## 9.2 · The component that was dead for months `INC-001 + INC-008` · Senior → Staff

**Interviewer:**
> Tell me about the bug that took you longest to find.

**You:**

Half my retrieval system was returning nothing for months and I had no idea, because the other
half was covering for it.

**Impact:** questions containing exact identifiers — a company name, a course code, a student
name — returned generic prospectus text instead of the specific chunk that answered them.
Degraded quality on exactly the highest-intent questions, and no errors anywhere.

**Detection:** by accident, while debugging something unrelated. No alert, no error, no user
report. That's the finding, really — detection took months for a component that was completely
dead.

**Root cause, and there were two.** CampusBrain runs hybrid retrieval: vector search plus
Postgres full-text search, fused with reciprocal rank fusion. The keyword arm was built on
`plainto_tsquery`, which **ANDs every term.** So a natural-language question like "what
programming languages are taught in year one" required a single chunk to contain every one of
those words. Essentially nothing matched. The keyword arm was returning zero results for most
questions.

I only found it because I was investigating a second, separate bug in the same arm. A question
about how many students interned at a company called KlearNow was returning boilerplate. When
I fixed the AND problem so the arm returned results at all, it was still ranking badly — and
that's when I found the real one.

**Postgres `ts_rank` is not BM25.** I had been calling it BM25 in my own documentation. It
scores term frequency within a chunk with length normalisation, and it has **no inverse
document frequency term at all** — it has no idea how many *other* chunks contain a word. In
my corpus, "students" appears in 66% of chunks and "klearnow" in 5%, and `ts_rank` weighted
them identically. So chunks stuffed with prospectus filler outranked the three chunks that
actually named the company.

**The fix:** ORing the terms and letting `ts_rank` order them, plus a query-time document
frequency filter that drops any term appearing in more than 10% of the corpus. That's IDF used
as a filter rather than a weight, because `ts_rank` gives you nowhere to put a weight. I
calibrated the 10% by measuring — klearnow 5%, job 10%, ai 15%, currently 23%, internship 27%,
students 66%. Ten percent sits above every proper noun and below every filler word. It moved
the two answering chunks from unranked to ranks one and seven.

There's a fallback too: if every term in a query is common — something like "what do students
study" — dropping them all would leave an empty query, so it returns the original terms. The
principle is degrade to the previous behaviour, never to zero.

**Prevention:** a per-arm hit count on every retrieval event and a `zero_keyword_hit_rate`
metric. Plus a synthetic canary that asks an exact-identifier question every fifteen minutes
and asserts the expected chunk comes back — that's the only check that would have caught the
original failure.

**The lesson, and it's the one I use most:** redundancy hides failure. A two-arm system looks
completely healthy when one arm is dead, because the other one covers. **Every redundant
subsystem needs per-component observability, or redundancy converts a loud failure into a
silent degradation.** That generalises well beyond retrieval — it's true of any fallback, any
replica, any secondary path.

### Follow-up Questions

1. How did you find out `ts_rank` wasn't BM25? What made you check?
2. Your calibration was six terms and one query. How much do you trust it?
3. Why a filter rather than a weight? What would weighting require?
4. The DF query runs per request. When does that stop being viable?
5. Design the monitoring that would have caught this in a day instead of months.
6. Name another place in your system where redundancy could be hiding a failure right now.

### What the Interviewer is Testing

**Concept:** silent degradation, and whether the candidate knows what their libraries
actually do rather than what they're labelled.
**Hidden objective:** *"I found out `ts_rank` isn't BM25"* is a strong signal — it means you
read the behaviour, not the documentation. Bonus signal for admitting your own docs were wrong.
**Common mistakes:** presenting only the ranking bug and missing the more interesting
detection failure; not generalising past retrieval.
**Red flags:** still calling it BM25; no plan for detecting the next silent failure.
**Excellent answer:** both bugs separated, the real calibration numbers quoted, the
degrade-to-previous-behaviour fallback mentioned, and the redundancy lesson stated as a
transferable principle with a second example.

### If CampusBrain Didn't Have This

Still today, without per-arm metrics: the same failure could recur and take months again.
**User:** the questions most likely to convert a prospective student — placement companies,
specific courses — are exactly the proper-noun-heavy ones that fail. **Business:** the product
looks mediocre for reasons nobody can name, because nothing is technically broken.

### Real Production Incident

This one. The detail I'd add if pushed: this is *why* hybrid retrieval is dangerous without
observability. The architecture was correct — two arms with complementary failure modes is the
right design for a corpus full of proper nouns — and the correctness of the design is precisely
what let a dead component go unnoticed. Good architecture can mask its own breakage.

### Whiteboard Discussion

Draw the two arms feeding the fusion box, then cross out the keyword arm and show the output
still looking plausible. That's the picture of the whole incident.

Then write the DF calibration numbers — 5, 10, 15, 23, 27, 66 — and draw the 10% cut line.
That table is your best single artifact: a measured decision with a stated failure direction.
Take it to per-arm metrics and the canary.

---

## 9.3 · The bug that only affected the best answers `INC-005` · Mid → Senior

**Interviewer:**
> Tell me about a bug that users reported.

**You:**

The sources panel was empty — sometimes. And the pattern turned out to be the opposite of what
you'd expect, which is what made it interesting.

**Impact:** CampusBrain shows a citation panel under every answer with the document and page
number. Users reported it was blank for some answers. Not all. Not obviously random.

**Detection:** user reports. Which is a finding in itself — nothing on my side flagged that an
answer had returned zero citations, and "answered with no sources" is a condition I should
have been able to alert on.

**What I thought it was:** intermittent retrieval failure. If nothing was retrieved, there'd be
nothing to cite. That was wrong, and the thing that killed the hypothesis was noticing *which*
answers had the empty panel — they were the thorough ones. The answers that synthesised across
several documents. The ones the whole system exists to produce.

**Root cause.** The prompt asks the model to cite sources inline as `[1]`, `[2]`. My parser was
a regex matching a single bracketed number. But models group their markers — when a claim rests
on several chunks, the natural output is "eight students were placed [1, 2, 4]", not
"[1][2][4]". My regex matched none of those. So every answer grounded in multiple sources
parsed to **zero citations**, and the better-evidenced the answer, the more likely it showed no
evidence at all.

**The deeper cause is the one I'd emphasise.** My prompt said "cite the sources you use inline
with their number in square brackets, e.g. `[1]`". That's an **example**, not a specification.
`[1, 2, 4]` is a perfectly reasonable reading of it. So I had the output contract expressed
twice, in two different languages — English in the prompt and a regex in the parser — with
nothing keeping them consistent. The gap between those two definitions is where the bug lived,
and it's invisible, because nothing type-checks a regex against a paragraph of English.

**The fix** extended the regex to grouped markers, and while I was in there I added two things
that weren't strictly the bug. Markers pointing outside the retrieved set get dropped entirely
— if the model emits `[9]` when five chunks came back, that's a reference to nothing, and
showing it to a user is worse than showing nothing because it *looks* verifiable. And the
remaining markers get renumbered contiguously, so citing chunks 2 and 4 shows the user sources
1 and 2 rather than 2 and 4 with a gap that reads as missing items.

**Prevention:** deterministic assertions in CI — every marker in range, citations contiguous
from one, at least one citation on any non-refusal. Those are the best-tested paths in my
codebase now, about ten cases. And the structural fix is constrained output: have the model
return a validated schema with a citations array rather than prose I parse afterwards. That
would have made the bug unrepresentable instead of merely fixed.

**The lesson:** if code consumes the output, constrain it with a schema. Parsing prose means
maintaining two definitions of the same contract and hoping they agree.

### Follow-up Questions

1. Why drop an out-of-range marker rather than render it?
2. Why renumber? What does the user experience if you don't?
3. Show me the structured-output version. What does it cost?
4. Which of your citation rules can be asserted without a model?
5. What monitoring would have caught this before a user did?

### What the Interviewer is Testing

**Concept:** the model's output as a contract, and the difference between validating and
constraining.
**Hidden objective:** does the candidate identify the *example-versus-specification* root
cause, or stop at "my regex was too narrow"? The second is a fix; the first is a class of bug.
**Common mistakes:** describing it as a regex bug; missing that the failure correlated with
answer quality; not knowing structured outputs exist.
**Red flags:** no tests on the citation path; treating hallucinated citation markers as
harmless.
**Excellent answer:** notices the inverse correlation with quality as the diagnostic clue,
names the two-languages-one-contract root cause, and volunteers that constrained decoding is
the structural fix.

### If CampusBrain Didn't Have This

**User:** the sources panel is empty exactly when the answer is most worth verifying, so the
feature is broken precisely where it matters. **Business:** citations are the trust mechanism
for the entire product — an unreliable citation panel is worse than none, because users learn
not to rely on it. **Engineering:** a hallucinated `[9]` renders as a checkable-looking
reference to nothing.

### Real Production Incident

This one. The counterintuitive shape is what makes it worth telling: **the bug was inversely
correlated with answer quality.** Any sampling strategy that checked "a few answers" would
likely have missed it, because the well-grounded answers are the minority. That's an argument
for assertions over spot checks.

### Whiteboard Discussion

Write three model outputs on the board — `[1]`, `[1][2]`, `[1, 2, 4]` — and the original regex
underneath. Show which ones match. Then draw the pipeline: prompt says X, parser expects Y,
nothing reconciles them.

Draw the structured-output alternative — `{text, citations[]}` — and be honest about the cost:
you lose the inline marker positions, and this UI renders citations inline, so it's not a free
swap. That trade-off is the interesting part.

---

## 9.4 · The fix that caused the next bug `INC-006 → INC-007` · Senior

**Interviewer:**
> Tell me about a time your fix introduced a new problem.

**You:**

I fixed a refusal bug and immediately created a presentation bug, and both were in the prompt.

**Impact, first bug:** "Which students went to KlearNow?" returned eight names correctly.
"How many students went to KlearNow?" returned "I don't have information on that in the
available documents." Same corpus, same retrieved chunks. It had the information and had just
used it.

**What I thought it was:** retrieval. Two similar questions, different results — the obvious
hypothesis is that the second one retrieved different chunks. It hadn't. Same chunk IDs.

**Root cause:** my own instruction. The prompt said "answer using ONLY the numbered context
below." I meant *don't use outside knowledge*. The model read it as *don't produce any string
that isn't literally present* — and the number eight isn't written anywhere in the corpus, you
have to count the rows of a table. So it refused, correctly, by its reading.

The model was obeying me precisely. My instruction was ambiguous. That reframing mattered: I'd
been about to try a bigger model.

**Fix:** a clause stating that counting, totalling or listing what the context states is part
of answering from the context, not going beyond it.

**Then the second bug.** Once it would count, it started showing its work: *"There are 6
students: 1… 2… … 8… Wait, counting the names again — that makes a total of 8."* Correct final
number, arrived at in front of the user, including its own mid-answer correction. Technically a
success. As a product, unusable.

**Root cause of that one:** counting across a dozen chunks is exactly where chain-of-thought
reasoning helps most, so the model naturally produced it — and nothing had told it that the
reasoning and the answer are different artifacts with different audiences. I'd unlocked a
capability without specifying its output format.

**Fix:** work out any count before you begin writing, give only the final answer, never narrate
and never self-correct mid-answer.

**What I'd flag about that fix:** it's a request, not a guarantee. A structural version — have
the model emit reasoning inside a delimited block and strip it server-side, or use a model
with native thinking tokens — would be robust. A prompt instruction can silently stop working
when the model version moves underneath me, and it's behind a floating alias, so it will.

**Prevention:** both of these are checkable. The counting one is an expected-fact substring
assertion against a golden question. The narration one is a regex — the answer must not
contain "wait", "let me count", "counting again". The clause that looked unassertable is
actually the easiest one to test.

**The lesson:** prompt clauses are regression tests written in English, executed by a
non-deterministic interpreter. Each of mine was added after a specific observed failure, and
until I wrote assertions for them, none of them was ever checked again — including against each
other. I still don't know whether the dedupe clause I added later interferes with the counting
one.

### Follow-up Questions

1. Do your prompt clauses conflict? How would you find out?
2. Which of the three could be deterministic, and which genuinely needs a judge?
3. The model version changes tomorrow. How do you learn that these stopped working?
4. Why is "never narrate" fragile? What's the robust version?
5. You almost switched to a bigger model. What stopped you, and what's the general lesson?

### What the Interviewer is Testing

**Concept:** prompts as untested code, and the discipline of diagnosing an instruction rather
than blaming the model.
**Hidden objective:** does the candidate recognise that the *instruction* was wrong? Reaching
for a bigger model is the reflex, and resisting it is the signal.
**Common mistakes:** telling only the first bug; not noticing the second was caused by the
first; no plan for verifying prompt behaviour.
**Red flags:** treating a prompt instruction as a guarantee; claiming the prompt is tested
when it isn't.
**Excellent answer:** the "ONLY" ambiguity identified as the root cause, the causal link
between the two bugs, the request-versus-guarantee distinction, and admitting the clauses have
never been tested against each other.

### If CampusBrain Didn't Have This

**User:** "how many students got placed" is one of the highest-intent questions a prospective
student asks. Without the first fix it refuses; without the second it answers correctly while
visibly second-guessing itself. Either destroys confidence. **Business:** it reads as an
unreliable AI when it's an ambiguous sentence in a prompt.

### Real Production Incident

The recurrence risk is live. The model sits behind a floating alias, so the weights change
without any deploy from me. New weights follow "never narrate" less strictly, counting answers
start including their working again, and nothing errors, no metric moves, no test fails —
because there are no tests on the prompt. It surfaces when someone screenshots an answer that
says "Wait, counting again."

That's precisely why the regex assertion goes in CI.

### Whiteboard Discussion

Draw the prompt as a stack: role, base instruction, three behavioural clauses, history,
context, question. Annotate each clause with the bug that caused it and the date. That stack is
a changelog.

Then draw a second column: for each clause, deterministic or judged? Two of three are
deterministic. That's the bridge to the evaluation discussion — take it yourself.

---

## 9.5 · The constraint that shaped the architecture `INC-003` · Mid → Senior

**Interviewer:**
> Tell me about a time you hit a hard resource constraint.

**You:**

The service wouldn't start. `Out of memory, used over 512Mi`, immediately after uvicorn bound
the port.

**Impact:** total failure to deploy. Not degraded — the process was killed before it served a
single request.

**Root cause:** I was running four uvicorn workers on a host with 512 MB of RAM total. Each
worker is a full process copy, and this application imports PaddlePaddle and PaddleOCR for the
OCR fallback path. Those are heavy. Four copies didn't fit.

**Fix:** one worker. The platform itself recommends one for an instance that size, and my
`--workers 4` was overriding that.

**The interesting part is what that decision then constrained**, because it stopped being a
deploy fix and became an architectural input.

One worker means no request parallelism — a slow request blocks others, and one out-of-memory
event is a total outage rather than a degraded one. It also means my rate limiter, which uses
an in-memory store, is **correct** — counters only work if there's exactly one process
counting. So a memory constraint is silently holding up a correctness property two files away,
and the day I add a second worker, my rate limits become per-process and silently under-enforce
in aggregate. I documented that coupling in the startup script, because it is not
discoverable otherwise.

It also rules things out. When I later evaluated a cross-encoder reranker, `sentence-transformers`
and `torch` would have added roughly 2 GB to the image. On a box that had already been
OOM-killed once, that wasn't a trade-off discussion — it was disqualifying. The constraint made
the decision.

**Prevention:** the memory ceiling is documented as a binding constraint in my architecture
notes, alongside the other free-tier limits — no persistent disk, suspension after fifteen
minutes idle, no shell access. Those four shape every design.

And I'd volunteer that the same failure mode is still reachable by a different path: my upload
endpoint reads the entire request body into memory *before* checking it against the 100 MB
limit. So a large upload can reproduce this OOM without any worker misconfiguration. That's
open, and the fix is to reject on `Content-Length` and stream to a spooled temporary file
rather than buffering.

**The lesson:** on constrained infrastructure, resource limits aren't a detail you tune at the
end — they're a design input that rules out whole categories of solution, and they create
couplings between unrelated files that nothing enforces.

### Follow-up Questions

1. Your rate limiter is correct because of a memory decision. How do you stop someone breaking
   that?
2. Fix the upload path. What does streaming validation look like?
3. One worker means no parallelism. How do you serve concurrent requests at all?
4. How would you find out how much memory you actually need per worker?
5. What else does the 512 MB ceiling rule out that you haven't mentioned?

### What the Interviewer is Testing

**Concept:** resource constraints as architectural forcing functions, and second-order
coupling between decisions.
**Hidden objective:** can the candidate trace a constraint's consequences beyond the immediate
fix? The rate-limiter coupling is the payload here.
**Common mistakes:** presenting this as a config fix and stopping; not knowing why the app is
memory-heavy; missing the coupling entirely.
**Red flags:** "we'd just upgrade the instance" as the only answer; no awareness of what the
constraint disqualifies.
**Excellent answer:** connects the worker count to the rate limiter's correctness, cites the
reranker rejection as downstream of the same constraint, and volunteers that the OOM is still
reachable through the upload path.

### If CampusBrain Didn't Have This

Without the constraint being *documented*: someone raises the worker count for throughput, the
rate limiter silently under-enforces by a factor of four, and unmetered LLM spend follows.
**Engineering:** the coupling is invisible in the code — the rate limiter and the start script
are in different directories and neither imports the other.

### Real Production Incident

The forward-looking version: an engineer adds `--workers 4` back for throughput. Memory is now
sufficient, so it boots fine and nothing looks wrong. Rate limits become per-process, so the
120-per-minute chat limit is effectively 480. A scripted abuser exhausts the daily model quota
in an afternoon — reproducing the outage from 9.1, by a completely different route, with no
error at the moment of the change.

### Whiteboard Discussion

Draw the memory budget as a bar: base process, PaddlePaddle, PaddleOCR, per-request working
set — then multiply by worker count and show it overflowing 512 MB.

Then draw an arrow from `--workers 1` to the rate limiter's correctness, in a different colour.
That arrow is the point of the story: a coupling that exists in reality and nowhere in the
code. Take it to the upload path as the remaining route to the same failure.

---

## 9.6 · Quick reference — the full incident library

For questions that want breadth rather than one deep story.

| ID | One-line | The transferable lesson |
|---|---|---|
| INC-001 | Keyword arm dead for months; semantic arm covered | Redundancy converts a loud failure into a silent degradation |
| INC-002 | Free-tier **daily** quota exhausted; every chat 500'd | 429 means two different things and only one is retryable |
| INC-003 | OOM at 512 MB from 4 workers × a heavy OCR import | Resource limits are a design input, not a tuning step |
| INC-004 | Unhandled 500 lost CORS headers; looked like a CORS bug | Middleware ordering decides whether a failure is diagnosable |
| INC-005 | Grouped citation markers unparsed; best answers showed no sources | An example in a prompt is not a specification |
| INC-006 | "How many" refused while "which" answered | "ONLY" is a behavioural instruction, not a factual constraint |
| INC-007 | Model narrated its counting and corrected itself mid-answer | A prompt instruction is a request; structure is a guarantee |
| INC-008 | `ts_rank` has no IDF; "students" (66%) outranked "klearnow" (5%) | Verify what a library implements before you name it |

**Pairings that make one story:** 002 + 004 (the outage), 001 + 008 (the keyword arm),
006 + 007 (the fix that caused the next bug).

---

# Chapter 10 — HR and Project Deep Dive

> **Mode A.** Everything here is true today. If you have shipped pillars since, update the
> numbers and add them to 10.4.
>
> **Format note:** the standard sections don't map to behavioural questions, so three are
> swapped: *If CampusBrain Didn't Have This* → **What a weak answer sounds like**, *Real
> Production Incident* → **The story to reach for**, *Whiteboard* → **Where to take it next**.

---

## 10.1 · "Walk me through your project" · All levels

This is the most common opener in any interview and the most commonly wasted. You get
ninety seconds before the interviewer decides what kind of conversation this is.

**Interviewer:**
> Tell me about CampusBrain.

**You (30 seconds — use this unless asked for more):**

> It's a multi-tenant RAG chatbot over a university's public documents. A question runs two
> searches in parallel — dense vector search over Gemini embeddings in Qdrant, and Postgres
> full-text search — fuses the rankings with reciprocal rank fusion, and passes the top five
> chunks to Gemini with a prompt that forces inline citations. If nothing retrieved clears a
> similarity floor, it refuses instead of guessing. Each organisation gets its own vector
> collection, so tenant isolation is structural rather than a filter. It's small — about 110KB
> of corpus, 273 chunks — and the interesting problems were all in the keyword arm and in
> deciding what *not* to build.

Then stop. That last clause is bait and interviewers take it.

**You (3 minutes — only if asked to go deeper):**

Give the 30-second version, then pick **one** story and go deep. Default to the IDF one:

> The keyword arm is Postgres full-text search, and I'd been calling it BM25 in my own
> documentation. It isn't — `ts_rank` scores term frequency within a chunk and has no inverse
> document frequency term at all. So in a question like "how many students interned at
> KlearNow", the word "students" — which is in 66% of my chunks — was weighted the same as
> "klearnow", which is in 5%. Prospectus boilerplate outranked the three chunks that actually
> named the company.
>
> I fixed it with a query-time document frequency filter that drops any term above 10%. I
> calibrated that by measuring — klearnow 5, job 10, ai 15, currently 23, internship 27,
> students 66 — so 10% sits above every proper noun and below every filler word. It moved the
> answering chunks from unranked to ranks one and seven. There's a fallback for when every
> term is common, so it degrades to the old behaviour rather than to an empty query.
>
> Two things I'd flag. That calibration was six terms and one query, so it's directionally
> right rather than rigorous — re-running it against a proper golden set is on my list. And it
> recomputes document frequency on every request, which is fine at 273 chunks and becomes the
> latency floor around a hundred thousand. At that point I'd precompute it into a table, which
> is exactly what a real BM25 index does at build time.

### Follow-up Questions

The ones this opener reliably produces — and each is one you want:

1. What *didn't* you build?
2. How do you know the retrieval is any good?
3. Why not just use BM25 properly / Elasticsearch?
4. What breaks at a hundred times the corpus?
5. Why does the keyword arm exist at all if you have embeddings?

### What the Interviewer is Testing

**Concept:** can you scope your own work accurately and pick the interesting part?
**Hidden objective:** the pitch tells them whether to interview you as a builder or a
designer. Leading with architecture reads as a tour; leading with a specific problem reads as
an engineer.
**Common mistakes:** narrating the tech stack as a list; going five minutes without pausing;
opening with "it's a production-ready platform".
**Red flags:** vague scale claims; can't say what's small about it.
**What makes it excellent:** stating the corpus size unprompted, and ending on "what not to
build" — which volunteers judgement rather than output.

### What a weak answer sounds like

> *"I built a production-ready, scalable, multi-tenant AI knowledge platform using FastAPI,
> React, Postgres, Qdrant and Gemini, with enterprise-grade security and optimised retrieval."*

Every word is either unfalsifiable or a tech name. It invites exactly the four questions that
expose the gaps — what's your QPS, how do you know retrieval is optimised, what's
enterprise-grade about it, what's your p95 — and it has spent the credibility you needed for
the parts that are genuinely good.

### The story to reach for

IDF, every time, unless the interviewer has steered elsewhere. It has a real bug, a real
measurement, a calibration table you can recite, a stated failure direction, and an honest
caveat. Second choice: the reranker you measured and rejected.

### Where to take it next

Toward retrieval. That's where your strongest material is and where the code is best. If they
steer to reliability or evaluation, go — but know you're on `[GAP]` ground and lead with the
design and its cause, not with a claim.

---

## 10.2 · "It's a personal project with no users" · Senior → Staff

**Interviewer:**
> This is a side project. No traffic, 273 chunks. Why should that tell me anything about
> whether you can work on production systems?

**You:**

It's a fair challenge and I'd rather answer it directly than argue with the premise.

You're right that I can't demonstrate operating at scale. What I can demonstrate is knowing
where each design stops being correct, and I've written that down rather than left it implied.
My per-tenant Qdrant collections stop working around a thousand tenants, because the binding
constraint is per-collection overhead rather than vector count — and I know what the migration
looks like and how I'd keep the shared-filter version safe. My document-frequency lookup
becomes the latency floor around a hundred thousand chunks, and the fix is precomputing it into
a table, which is what a real BM25 index does at build time. I've got about fourteen of those
written up with their triggers.

The second thing is that small systems are actually *better* for demonstrating judgement,
because I know all of one. Ask me about any constant in the codebase and I can tell you where
it came from and whether it was measured — and for several the honest answer is "it's a
LangChain default and I never tuned it, and the reason is that tuning requires an evaluation
harness I haven't built, so it was structurally blocked rather than forgotten." That's a more
useful thing to know about an engineer than a throughput number.

Third — and this is the part I'd push back on gently — the constraints here are real, they're
just different ones. 512 MB of RAM and an instance that suspends after fifteen minutes idle
disqualified a cross-encoder reranker on image size alone, and forced a durability design for
background work. Those are the same *kind* of decision you make with a budget, just with the
numbers moved. I had a genuine out-of-memory incident and it changed my architecture.

What I'd concede without being pushed: some problems never surfaced because the system is
small. I have a latent chunking bug that only wakes up on a real PDF, because my corpus is
Markdown with no pagination. My rate limiter is correct only because I run one worker. Both of
those are things I know about and neither has ever bitten, and I'd be more confident about my
judgement if they had.

So the honest summary is: I can show you decisions, trade-offs and failure analysis. I can't
show you scale, and I wouldn't pretend the two are the same thing.

### Follow-up Questions

1. Give me a decision where being small led you to the *wrong* conclusion.
2. What would you do first if this suddenly had ten thousand daily users?
3. Which of your scaling triggers are you least confident in?
4. You mention a latent chunking bug. Why haven't you fixed it?
5. What's the hardest thing about this project that has nothing to do with scale?

### What the Interviewer is Testing

**Concept:** self-assessment calibration. This is a pressure question and the content matters
less than the composure.
**Hidden objective:** do you fold, over-defend, or engage? Both extremes are disqualifying. A
candidate who agrees the project is worthless has no judgement; one who insists it's
production-grade has none either.
**Common mistakes:** listing technologies as a defence; getting defensive; conceding
everything.
**Red flags:** claiming users or traffic that don't exist; no examples of scale limits.
**What makes it excellent:** conceding the real limitation in the first sentence, then
reframing around what small systems *do* demonstrate — with specific numbers and named
thresholds, not assertions.

### What a weak answer sounds like

> *"Well, the architecture is designed to scale — it's stateless, it's containerised, it uses a
> vector database that handles millions of vectors, so it would work at scale."*

"Designed to scale" is the phrase interviewers use to identify candidates who haven't operated
anything. It's unfalsifiable, it dodges the question, and it invites "okay, what's your
bottleneck at ten thousand QPS?" — which you can't answer.

### The story to reach for

The reranker rejection. It's the cleanest proof that you make decisions rather than accumulate
features, and it's *strengthened* by being small: the reason not to ship it was that the
correct chunk was already top-two, which is a property of the system you measured.

### Where to take it next

Offer the migration list. *"I've written up fourteen of these with triggers — want to take one
apart?"* You've converted a challenge into an invitation to discuss architecture on ground you
prepared.

---

## 10.3 · "What was the hardest problem?" · All levels

**Interviewer:**
> What was the hardest technical problem you solved on this?

**You:**

Not the one I expected. The hardest wasn't building anything — it was a bug I nearly shipped
that would have broken the entire product silently.

CampusBrain refuses to answer when nothing retrieved is relevant enough. That's the main
defence against making things up: if the best semantic similarity is below 0.35, it returns a
fixed refusal and never calls the model at all. Refusing before generating rather than
filtering afterwards — no tokens spent, no opportunity to hallucinate.

Then I added hybrid retrieval with reciprocal rank fusion. RRF deliberately throws the scores
away and fuses on rank position, because cosine similarity and Postgres `ts_rank` aren't
comparable numbers — one is bounded zero to one, the other is unbounded and query-dependent.
So each list contributes one over sixty-plus-rank, summed.

The problem is that RRF scores come out around 0.03. My guardrail thresholds at 0.35. If I'd
pointed the guardrail at the fused score — which is the obvious thing to do, it's the score
the function returns — then `0.03 < 0.35` would have been true for every result of every
query. **The system would have refused every question ever asked**, silently, with no error
anywhere. Health checks green, error rate zero, latency actually *improved* because the model
is never called.

I caught it because I was reasoning about what the threshold was calibrated on, and carried the
raw semantic score through fusion as a separate field.

What makes it the hardest problem isn't the difficulty — the fix is one extra field. It's that
nothing would have caught it. Both values are floats. Both were called `score`. The type
system can't distinguish a cosine similarity from a reciprocal-rank sum. There's no test that
fails, because I didn't have a golden set. And every dashboard would have said the system was
healthier than usual.

The generalisable version: **fusion changed the units of a value while keeping its name and
its type.** It's the same class of bug as passing metres to a function expecting feet. And the
lesson I took is that I avoided it by being careful, and being careful isn't a mechanism. The
structural fix is distinct types for distinct units — a `CosineSimilarity` newtype rather than
a float — so the bug wouldn't compile. I haven't done that, and in a codebase with more than
one person in it I would.

### Follow-up Questions

1. How would you have found this if you *hadn't* reasoned about it in advance?
2. What's the monitoring signal that catches it?
3. Show me the type-level fix. What does it cost in ergonomics?
4. Where else in your system could a unit mismatch hide right now?
5. Why fuse on rank at all, if it creates this problem?

### What the Interviewer is Testing

**Concept:** systems thinking — the ability to reason about how a change propagates beyond
the component you touched.
**Hidden objective:** picking a *near-miss* rather than a triumph is itself the signal. It
shows you evaluate risk rather than output.
**Common mistakes:** picking the most technically complex thing rather than the most dangerous
one; not explaining why detection would have failed.
**Red flags:** "being careful" presented as an adequate solution; can't name the monitoring
signal.
**What makes it excellent:** the observation that every dashboard would have shown improvement
— that's what makes it genuinely frightening, and it demonstrates you understand what silent
failure means.

### What a weak answer sounds like

Anything that ends at "and then I fixed it." The fix is the least interesting part. The
interviewer wants the *mechanism of the failure* and *why it wouldn't have been caught*.

Also weak: picking the thing that took longest. Difficulty and importance aren't the same, and
choosing the important one is part of what's being assessed.

### The story to reach for

This one, or the keyword arm being dead for months. Both are about **silent failure**, which
is the theme that runs through your whole system and the most senior thing you can talk about.

### Where to take it next

Toward evaluation and monitoring — both of which are gaps, and both of which this story makes
you sound like you understand deeply. *"That's the incident that convinced me refusal rate is
the first metric I'd build, not the fifth."*

---

## 10.4 · "What would you do differently?" · Senior → Staff

**Interviewer:**
> If you started this again tomorrow, what would you change?

**You:**

Build the evaluation harness first. Everything else follows from that.

Right now I have seven tuning decisions I can't make — chunk size and overlap, the
document-frequency ratio, the relevance threshold, the RRF constant, the over-fetch multiplier,
whether query condensation helps, and re-testing the reranker rejection properly. All seven are
blocked on the same missing thing, and I didn't notice they were blocked. I had a milestone for
chunking evaluation, and I skipped it as lower priority than "core path" work — but it wasn't
lower priority, it was a *prerequisite* I'd mislabelled. My plan had no edge between "tune the
chunk size" and "build a way to measure chunk size", so tuning quietly became never.

The principle I'd carry forward: **measurement is a prerequisite, not a follow-up.** Any
"we'll tune this later" item is secretly blocked on an evaluation item, and if you don't draw
that dependency, later means never.

Second thing: I'd design the embedding interface with a plural. My ingestion takes 248 seconds
for a 35 KB file because it makes one HTTP call per chunk, forty-seven of them, sequentially.
The API has a batch endpoint. The reason I never used it is that my `EmbeddingProvider`
protocol declares `embed(text: str)` — singular. Batching wasn't rejected on its merits, it was
never *expressible*. A type signature written in week three set the performance ceiling for the
whole pipeline. Now, when a function is going to be called in a loop, I write the plural first,
because it costs nothing on day one and a single-item call is just a one-element list.

Third, and smaller: I'd have logged from the beginning. Not because debugging is hard — because
the request log is the only realistic source of real user questions, and I've permanently lost
every question anyone has ever asked this system. That's not recoverable. My golden set will
have to be built from questions I imagine users ask, which I already know is different from
what they actually ask.

What I *wouldn't* change: the provider abstraction, which let me swap the entire LLM in one
line during an outage; the structural tenant isolation; and the decision not to ship a
reranker. Those three have all been tested by events.

### Follow-up Questions

1. You skipped the evaluation milestone deliberately. Walk me through that call at the time.
2. How would you make the "prerequisite vs follow-up" distinction visible in a plan?
3. The singular interface — where else does that pattern bite you?
4. You lost every user question. Can you recover anything?
5. What's on this list that you're *still* not going to fix, and why?

### What the Interviewer is Testing

**Concept:** retrospective judgement, and whether you can distinguish a mistake from a
constraint.
**Hidden objective:** this is the question where most candidates either say "nothing" or list
cosmetic regrets. Naming a *sequencing* error — building things in the wrong order — is a
senior answer, because sequencing is what seniority is mostly about.
**Common mistakes:** technology regrets ("I'd use a different framework"); nothing-to-change;
listing things that were reasonable given the constraints.
**Red flags:** blaming tools; no distinction between what you'd change and what you'd keep.
**What makes it excellent:** the mislabelled-prerequisite insight, and the interface-arity
lesson — both generalise well past this project, and the second one is genuinely
non-obvious.

### What a weak answer sounds like

> *"I'd probably add more tests and improve the documentation."*

True of every project ever written, so it conveys nothing. The question is asking what *this*
project taught you specifically.

### The story to reach for

The M26 skip — the chunking evaluation milestone deferred as lower priority when it was
actually a prerequisite. It's a mistake you can name precisely, explain the reasoning behind at
the time, and generalise.

### Where to take it next

Toward how you'd sequence work now. That's a Staff-level conversation and you have a concrete
example to anchor it. If they bite, the roadmap's dependency ordering — observability first,
because every other pillar consumes it — is the answer.

---

## 10.5 · Positioning: which engineer are you? · All levels

**Interviewer:**
> What kind of role are you looking for?

**You:**

Applied LLM engineering, or backend engineering on a team that's building AI features. I don't
train models and I'd rather be clear about that than imply otherwise.

What I'm good at is the system around the model — retrieval, evaluation, cost, the failure
modes, how it behaves when the provider is down or the quota is gone. I've had a provider go
down on me and swapped it in one line because the abstraction was in the right place. I've had
half my retrieval system dead for months and learned why redundancy hides failure. I know where
my architecture stops working and roughly what I'd replace it with.

What I haven't done is train or fine-tune anything, serve my own inference, or work with a
GPU fleet. I can talk about KV caching, PagedAttention and quantization at the level of "this
is why output tokens cost more than input tokens and why long conversations get expensive to
serve" — because that's what you need to reason about what you're renting. But I'd be learning
on the job if you wanted me operating an inference stack, and I'd rather you know that going
in.

The distinction I'd draw is that most AI product work is backend engineering with a
probabilistic component in the middle. The hard parts of my project were multi-tenancy,
durability, ranking, observability and knowing what not to build — those are all normal
engineering problems. The genuinely AI-specific part is that you can't write an equality
assertion against the output, which is what makes evaluation a discipline rather than a test
file. That's the part I've thought about most and built least, and it's what I'd want to go
deeper on.

### Follow-up Questions

1. Where does your project sit between "backend engineer" and "ML engineer"?
2. What would you need to learn to own an inference stack?
3. What's the AI-specific skill you think is most undervalued?
4. If we put you on a non-AI backend team, would that be a disappointment?

### What the Interviewer is Testing

**Concept:** self-knowledge and honest scoping.
**Hidden objective:** can you say what you don't know without either apologising for it or
hiding it? Overclaiming the ML side is the single most common way candidates lose LLM
engineering interviews, because the follow-ups are easy to construct and hard to bluff.
**Common mistakes:** claiming the full stack from training to serving; being vague to keep
options open.
**Red flags:** claiming fine-tuning or inference experience that doesn't exist.
**What makes it excellent:** the "backend engineering with a probabilistic component" framing,
plus naming the one genuinely AI-specific skill — that you can't assert equality on the output
— and admitting it's the thing you've thought about most and built least.

### What a weak answer sounds like

> *"I'm interested in anything AI — LLMs, machine learning, data science, whatever the team
> needs."*

Reads as no preference and no self-assessment. "Applied LLM engineer, not a model trainer" is
a real, in-demand, respected position, and claiming it specifically is stronger than staying
open.

### The story to reach for

The provider swap during the outage. It's the cleanest demonstration that you build systems
*around* models: the failure was a vendor quota, the fix was an abstraction boundary, and
neither had anything to do with machine learning.

### Where to take it next

Toward evaluation, and be honest about it being designed rather than built. *"The thing I'd
most want to go deep on is evaluation, because it's the part that's genuinely different from
normal backend work and it's the part of my own system I'm least happy with."* That's a real
answer to "where do you want to grow" and it doesn't sound rehearsed.

---

---

## Revision log

| Date | Change |
|---|---|
| 2026-07-30 | Chapters **9** (Production Incidents, Mode A - 5 incident narrations + quick-reference table) and **10** (HR & Deep Dive, Mode A - 5 conversations) written. Incident-narration structure documented. Ch 7-8 remain |
| 2026-07-30 | Mode A/B convention added. Chapters 4–6 written in **Mode B** (Reliability, Observability, Evaluation) - 8 conversations. Eval scores left as `[measured]` placeholders |
| 2026-07-30 | Created. Chapters 1–3 written in full (12 conversations). Status-marker convention established. Three reference examples corrected from aspirational to actual: content-hash constraint (1.4), resumable ingestion (1.3), golden-dataset gating (deferred to Ch 6). Chapters 4–10 stubbed with unlock triggers |
