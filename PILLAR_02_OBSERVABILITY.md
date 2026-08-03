# Pillar 2 — Observability

**Goal of this pillar:** make any request reconstructable, make degradation detectable
without labels, and make the platform's restart decisions correct.

**Why this pillar is first:** every other pillar consumes it. Reliability needs to know what
failed. Evaluation needs real user questions, which only exist in request logs. Cost needs
somewhere to put token counts. Performance needs stage timings to know what to optimise.
Building observability first is what converts the other nine pillars from speculation into
measurement.

**Total effort:** roughly one day. Concept 2.1 alone is ~60 lines and delivers most of the
value.

---

## Where you actually are

Not zero. Three things are already right, and you should know which, because an interviewer
who reads your code will find them and you should be the one who points first.

| Already correct | Where | Why it counts |
|---|---|---|
| Unhandled exceptions log with a traceback | `main.py:47` — `logging.exception` | The 500 path is covered. Most demos swallow it |
| That middleware exists to preserve CORS headers on a 500 | `main.py:30-48` | Born from a real incident: an exhausted LLM quota looked like a CORS bug for an afternoon. That is observability reasoning already |
| `/health` is **deliberately** dependency-free | `main.py:64-71` | The comment states the liveness principle exactly: a probe that checks Postgres lets a Postgres blip kill a healthy process |

| Missing | Consequence |
|---|---|
| Anything on the chat happy path | Six questions about any answer are unanswerable |
| A request/correlation ID | Log lines cannot be joined into a request |
| Any metric | Degradation is invisible until a human notices |
| A **readiness** probe | `/health/storage` exists but nothing consumes it, and it checks only storage |
| Log retention policy | You are about to start logging user questions |

---

# Concept 2.1 — Request Correlation and Structured Logging

## 1. The theory

A log line is only useful if you can answer *"what else happened during this request?"*
That requires two properties, and unstructured logging has neither.

**Correlation.** Every log line emitted while handling one request carries the same unique
ID. This turns scattered lines into a reconstructable narrative. The ID is generated at the
edge, propagated through every layer, returned to the client, and — in a distributed system
— passed to downstream services in a header.

**Structure.** The line is a machine-parseable object with named fields, not a sentence.
`"Retrieved 5 chunks for org 3 in 310ms"` is readable by a human and useless to a query
engine. `{"event":"retrieval","org_id":3,"n_hits":5,"latency_ms":310}` can answer
*"what is p95 retrieval latency for org 3 this week"* with a filter and an aggregation.

The mental model that makes this stick: **logs are events, metrics are aggregates, traces
are causal paths.** They are not three formats for the same thing. Metrics tell you
*something is wrong*; traces tell you *where*; logs tell you *what*. Structured logging is
what lets you derive the first two from the third, which is why it is the one to build
first on a small system.

## 2. The production problem it solves

A user says: *"the chatbot gave me a wrong answer about fees yesterday."*

Today that is unanswerable. Six specific questions, six no's:

| Question | Answerable now? |
|---|---|
| What did they ask? | No |
| Which chunks were retrieved? | No |
| Was the relevance guardrail triggered? | No |
| Which model version answered? | No — and `gemini-3.5-flash-lite` is a moving alias |
| What prompt version was used? | No — there is no prompt version |
| How long did each stage take? | No |

Without the retrieved chunk IDs you cannot tell a **retrieval miss** from a **generation
drift** — two failures with completely different fixes in completely different chapters of
your own notes. You are guessing which half of the system to debug.

## 3. How large companies implement it

| Layer | Typical implementation |
|---|---|
| ID generation | Edge proxy or API gateway injects `X-Request-Id`; services propagate it |
| Propagation | W3C Trace Context (`traceparent` header); OpenTelemetry SDK handles it automatically |
| Emission | Structured JSON to stdout — never to a file, because containers are ephemeral |
| Collection | A sidecar or node agent (Fluent Bit, Vector, OTel Collector) tails stdout and ships it |
| Storage | Elasticsearch, Loki, Datadog, Splunk |
| Query | Kibana / Grafana / Datadog, with retention tiering — hot for 7 days, cold for 90 |

The important part is not the tool list. It is the **contract**: applications write
structured JSON to stdout and know nothing about where it goes. Collection is
infrastructure's problem. That separation is what makes the pattern portable from a
1000-node fleet down to a free Render instance — you implement the same contract and let
the platform do less.

## 4. How CampusBrain implements the same principle, free

Three pieces. No dependencies beyond the standard library.

### (a) The request ID lives in a `contextvar`, not a parameter

Threading a `request_id` argument through `chat()` → `answer_question()` →
`hybrid_search()` → `semantic_search()` would touch every signature in the call stack for
a value none of them use. A `contextvars.ContextVar` is the standard-library mechanism for
exactly this: request-scoped ambient state, correct under both `async` and threadpool
execution.

**`backend/app/core/observability.py`** (new, ~55 lines):

```python
"""Request correlation and structured logging.

The request id lives in a ContextVar rather than being threaded through every
call signature: it is ambient request state that no business function needs to
know about, and passing it explicitly would touch rag_service, retrieval_service
and vector_store to carry a value none of them use.

ContextVar (not threading.local) because FastAPI runs async endpoints on an
event loop and sync ones in a threadpool; ContextVar is correct under both, and
copy_context() means a value set in the middleware is visible inside a
BackgroundTask spawned from the same request.
"""

import contextvars
import json
import logging
import time
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Inject the current request id into every record.

    A Filter rather than a custom Logger: this way third-party libraries'
    log records — and main.py's existing logging.exception on the 500 path —
    pick up the id without any of them knowing it exists.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line, to stdout.

    stdout, never a file: Render's filesystem is ephemeral and has no
    persistent disk, so a log file is deleted on every deploy and invisible to
    the platform's log stream.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "msg": record.getMessage(),
        }
        # Anything passed as logger.info("...", extra={"event": {...}}) is
        # merged in flat, so queries filter on top-level keys.
        if hasattr(record, "event"):
            payload.update(record.event)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()          # uvicorn installs its own; replace it
    root.addHandler(handler)
    root.setLevel(level)
```

### (b) One middleware, registered outermost

**`backend/app/main.py`** — the ordering is the subtle part:

```python
from app.core.observability import configure_logging, request_id_var

configure_logging()

# ... existing unhandled_errors_keep_cors middleware ...
# ... existing add_middleware(CORSMiddleware) ...

# Registered LAST, therefore OUTERMOST, therefore runs FIRST — so the id is
# set before unhandled_errors_keep_cors can log an exception, and that
# existing logging.exception call picks it up for free via RequestIdFilter.
@app.middleware("http")
async def request_context(request: Request, call_next):
    # Honour an inbound id if a proxy or the frontend supplied one, so a
    # client-side error report can be joined to the server-side trace.
    incoming = request.headers.get("X-Request-Id")
    rid = incoming if incoming and len(incoming) <= 64 else str(uuid.uuid4())
    token = request_id_var.set(rid)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-Id"] = rid
    logging.getLogger("http").info("request", extra={"event": {
        "event": "http_request",
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": round((time.perf_counter() - started) * 1000),
    }})
    return response
```

Two decisions worth being able to defend:

**Why accept an inbound `X-Request-Id`?** So a frontend error report ("request
`abc-123` failed") joins to the server-side record. The length cap is there because an
unbounded client-controlled string ends up in your logs — that is log injection, and
`\n` in a value would forge a log line if you were not emitting JSON. JSON escaping
already handles it; the cap is defence in depth.

**Why is it returned in the response header?** So a user can quote it. A support flow
where the user reads you an ID beats one where they try to remember their wording.

### (c) The RAG event — the line that actually matters

**`backend/app/services/rag_service.py`**:

```python
def answer_question(db, org_id, question, top_k=5, history=None):
    t0 = time.perf_counter()
    # ... existing retrieval_query construction ...
    hits = hybrid_search(db, org_id, retrieval_query, top_k)
    t_retrieval = time.perf_counter() - t0

    best_semantic = max((h.get("semantic_score", 0.0) for h in hits), default=0.0)
    refused = not hits or best_semantic < RELEVANCE_THRESHOLD

    t1 = time.perf_counter()
    if not refused:
        # ... existing sanitize + prompt + generate + keep_cited_sources ...
        pass
    t_llm = time.perf_counter() - t1

    logging.getLogger("rag").info("answered", extra={"event": {
        "event": "rag_answer",
        "org_id": org_id,
        "question": question,
        "question_len": len(question),
        "history_turns": len(history or []),
        "retrieved_chunk_ids": [h["chunk_id"] for h in hits],
        "n_hits": len(hits),
        "best_semantic_score": round(best_semantic, 4),
        "keyword_hits": sum(1 for h in hits if h.get("semantic_score", 0.0) == 0.0),
        "refused": refused,
        "citation_count": len(citations),
        "relevance_threshold": RELEVANCE_THRESHOLD,
        "prompt_version": PROMPT_VERSION,
        "llm_model": settings.gemini_llm_model,
        "embedding_model": settings.embedding_model,
        "retrieval_ms": round(t_retrieval * 1000),
        "llm_ms": round(t_llm * 1000),
    }})
```

Every one of the six unanswerable questions is now a `grep`.

Note `keyword_hits`: a chunk with `semantic_score == 0.0` reached the fused set through the
keyword arm alone. That single derived field is your early warning for the exact bug that
already happened once — `plainto_tsquery` ANDing every term so the keyword arm returned
nothing for months while the semantic arm quietly covered for it. **A hybrid system hides
the death of either arm; per-arm counts are the only thing that does not.**

### (d) Retention and PII — decide this before you turn it on

You are about to start logging user questions, which are user-generated content and may
contain personal data.

| Decision | Recommendation for this system |
|---|---|
| Log the full question? | **Yes** — it is the highest-value field, and it is the seed of your golden set (Pillar 5) |
| Retention | Render free streams logs with short retention already. Treat that as the policy and document it |
| If you ship logs off-platform | Set retention explicitly at the sink. 30 days is defensible for a public-info bot |
| Log the answer text? | **No.** Large, and the citation IDs plus prompt version make it reproducible |
| Log the full prompt? | **No.** It is derivable from `retrieved_chunk_ids` + `prompt_version` |

That last pair is a real design decision and a good one to articulate: **log the inputs and
the identifiers, not the derived artefacts.** It is smaller, cheaper, and it means a prompt
change does not invalidate your log history.

## 5. Why this is appropriate today

- **One process.** No cross-service propagation is needed, so a `ContextVar` is sufficient
  and an OpenTelemetry SDK would be ceremony with no consumer.
- **stdout is the right sink.** Render captures it, there is no persistent disk, and the
  application stays ignorant of collection — the same contract a large fleet uses.
- **Zero dependencies.** `contextvars`, `logging`, `json`, `uuid` are all standard library.
  Nothing to pin, nothing to CVE-scan, nothing that can break the 512 MB budget.
- **It is not a toy version of the real thing.** JSON-to-stdout *is* what production
  services do. The only difference is what reads the stdout.

## 6. At what scale it stops being appropriate

Four distinct thresholds, and they arrive in this order:

| Threshold | What breaks | Signal you have reached it |
|---|---|---|
| **Log volume vs. platform retention** | Render free retains a small window. You cannot answer "what happened last Tuesday" | You want to investigate something older than the retention window |
| **A second process or service** | `ContextVar` does not cross a process boundary. IDs stop correlating | You add a worker (Pillar 1) or split the API |
| **A third-party call you need timed inside a request** | Flat log lines cannot express parent/child spans or concurrency | You want to know whether the embedding call and the keyword query overlapped |
| **Grep stops scaling** | Filtering by hand over thousands of lines per day | You find yourself writing `jq` pipelines repeatedly |

The one that will actually arrive first for you is **retention**, and it arrives the moment
you start building a golden set from real questions, because that is a *historical* query.

## 7. What I would migrate to next

In order, each triggered by the specific threshold above:

1. **Ship logs to a free-tier sink.** Grafana Cloud, Better Stack, or Axiom all have free
   tiers with real retention and a query language. **The application does not change at
   all** — it still writes JSON to stdout — which is the payoff of the contract. This is
   the migration you will actually need.
2. **OpenTelemetry, when a second process exists.** Swap the `ContextVar` for an OTel
   context and the manual timings for spans. Use the **GenAI semantic conventions**
   (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`) so the fields are
   standard rather than yours.
3. **An LLM-native tool — Langfuse, LangSmith, Phoenix — when you care about prompt/response
   pairs as first-class objects.** These capture the prompt, the completion and the token
   usage as a trace with a UI built for it. Langfuse self-hosts and has a free cloud tier.
   The honest trigger: when you are iterating on prompts often enough that reading them out
   of raw logs is the bottleneck.

**The judgement to state:** you do not adopt OpenTelemetry to be modern. You adopt it when
you have a second process, because that is the problem it solves.

## 8. How to test it

Observability code needs tests for the same reason any code does, and it is frequently
untested because it "just logs".

```python
# backend/tests/test_observability.py
import json, logging
from app.core.observability import configure_logging, request_id_var, JsonFormatter


def test_request_id_appears_in_unrelated_module_logs(caplog):
    """The whole point of a Filter: a module that knows nothing about
    request ids still emits them."""
    configure_logging()
    token = request_id_var.set("test-abc")
    try:
        logging.getLogger("some.third.party").warning("hello")
    finally:
        request_id_var.reset(token)
    assert any(getattr(r, "request_id", None) == "test-abc" for r in caplog.records)


def test_formatter_emits_valid_json_with_flattened_event():
    rec = logging.LogRecord("rag", logging.INFO, __file__, 1, "answered", None, None)
    rec.event = {"event": "rag_answer", "org_id": 3, "refused": False}
    parsed = json.loads(JsonFormatter().format(rec))
    assert parsed["org_id"] == 3 and parsed["event"] == "rag_answer"


def test_newline_in_client_request_id_cannot_forge_a_log_line():
    """Log injection: a client-supplied id containing \\n must not split
    one JSON line into two."""
    rec = logging.LogRecord("http", logging.INFO, __file__, 1, "request", None, None)
    rec.request_id = "abc\nlevel=ERROR msg=fake"
    line = JsonFormatter().format(rec)
    assert line.count("\n") == 0
    assert json.loads(line)["request_id"] == "abc\nlevel=ERROR msg=fake"


def test_endpoint_returns_request_id_header(client):
    r = client.post("/api/v1/chat", json={"question": "test"})
    assert len(r.headers["X-Request-Id"]) > 0


def test_inbound_request_id_is_honoured(client):
    r = client.post("/api/v1/chat", json={"question": "test"},
                    headers={"X-Request-Id": "client-supplied-123"})
    assert r.headers["X-Request-Id"] == "client-supplied-123"
```

The third test is the one worth pointing at in an interview. **Log injection is a real
vulnerability class** — if you emitted plain text, a client-supplied ID containing a
newline could forge log entries and hide an attack. JSON encoding makes it structurally
impossible, and the test proves it rather than assuming it.

## 9. How to intentionally break it

Four failure injections, each proving one property:

| Inject | Command | Should observe |
|---|---|---|
| **An unhandled exception mid-request** | Add `raise RuntimeError("boom")` inside `answer_question` | A 500 **and** an ERROR line with a traceback **and the same `request_id`** as the `http_request` line. This proves the middleware ordering is right |
| **A hostile request ID** | `curl -H 'X-Request-Id: a\nlevel=ERROR'` | One JSON line, not two. The `\n` is escaped |
| **A slow stage** | `time.sleep(3)` inside `hybrid_search` | `retrieval_ms ≈ 3000`, `llm_ms` unchanged. Proves the timings are independent, not a single total |
| **A dead keyword arm** | Return `[]` from `keyword_search` | `keyword_hits` drops to 0 while answers still look fine. **This is the drill that matters** — it reproduces a bug you actually had, and shows the signal catches it |

Run the fourth one. It is the cheapest possible demonstration that you understand why
redundancy is dangerous without observability.

## 10. Interview questions to expect

1. What is the difference between logging, metrics and tracing?
2. Why structured logs instead of plain text?
3. What is a correlation ID and where is it generated?
4. Walk me through debugging a user-reported wrong answer.
5. Why did you use a `ContextVar` instead of passing the ID as a parameter?
6. Why not OpenTelemetry?
7. What would you *not* log, and why?
8. How do you correlate a frontend error with a backend log?
9. What is log injection?
10. Your logs go to stdout. What happens when the container restarts?

## 11. Model answers

**"What's the difference between logging, metrics and tracing?"**

> Logs are discrete events with full detail about one occurrence. Metrics are pre-aggregated
> numbers over time — cheap to store, cheap to query, but you lose the individual case.
> Traces are the causal path of one request across stages, which is what you need when the
> question is "where did the time go". You need all three: metrics tell you something is
> wrong, traces tell you where, logs tell you what. On a single-process app you can derive
> the first two from structured logs, which is why I built logging first.

**"Walk me through debugging a user-reported wrong answer."**

> They give me a request ID — it's returned in the `X-Request-Id` header, so support can ask
> for it. I pull the `rag_answer` event and look at `retrieved_chunk_ids` first, because
> that splits the problem in half: if the relevant chunk isn't there it's a retrieval
> failure and I'm looking at chunking, embeddings or the fusion; if it is there, the model
> had the context and ignored it, so it's a prompt or generation problem. Then I check
> `best_semantic_score` against the threshold to see whether the guardrail nearly fired, and
> `prompt_version` and `llm_model` to see whether either changed since. Without the chunk
> IDs I'd be guessing which half of the system to open, and those two halves have completely
> different fixes.

**"Why a `ContextVar` rather than passing the ID down?"**

> Because it's ambient request state that none of the business functions need. Threading it
> through would change the signature of `answer_question`, `hybrid_search`, `semantic_search`
> and `keyword_search` to carry a value none of them read — that's coupling every layer to a
> cross-cutting concern. `ContextVar` specifically, not `threading.local`, because FastAPI
> runs async endpoints on the event loop and sync ones in a threadpool, and `ContextVar` is
> correct under both. It also propagates into `BackgroundTasks` via `copy_context()`, which
> matters because my document ingestion runs there.
>
> The trade-off is that it's implicit state — you can't tell from a function's signature
> that it depends on it. I accept that for logging because logging is genuinely
> cross-cutting, and I'd reject the same argument for anything the business logic branches
> on.

**"Why not OpenTelemetry?"**

> Because I have one process. OTel's core value is context propagation across service
> boundaries, and I don't have one to cross — I'd be adding an SDK, a collector and a
> vendor decision to get correlation I already have from a 20-line `ContextVar`. What I did
> do is keep the shape compatible: structured JSON to stdout, an ID generated at the edge
> and honoured from inbound headers. The day I add a worker process — which is Pillar 1,
> because my ingestion currently runs in-process and dies when the instance sleeps — is the
> day the `ContextVar` stops working and OTel earns its keep. I'd adopt the GenAI semantic
> conventions at that point rather than inventing field names.

**"What would you not log?"**

> The full prompt and the answer text. Both are derivable — the prompt from
> `retrieved_chunk_ids` plus `prompt_version`, and I keep the citation IDs rather than the
> prose. Logging inputs and identifiers rather than derived artefacts keeps the volume down
> and means a prompt change doesn't invalidate my log history. I do log the question
> verbatim, which is a deliberate call: it's the single highest-value field for debugging
> and it's the seed of my evaluation golden set. That makes it user content, so it needs a
> stated retention period — I treat the platform's log retention as the policy and document
> it rather than pretending the question doesn't leave the request.

**"What is log injection?"**

> If you emit plain-text logs and interpolate user-controlled data, a value containing a
> newline can forge a log entry — an attacker writes what looks like a legitimate line to
> hide their activity or mislead an investigation. My request ID is client-supplied when
> present, so it's exactly that surface. JSON encoding makes it structurally impossible
> because the newline is escaped inside a string, and I have a test asserting a malicious ID
> produces exactly one line. I also cap the inbound length, because an unbounded
> client-controlled string in every log line is a cost and volume problem even when it isn't
> a security one.

**"Your logs go to stdout. What happens on restart?"**

> They're gone, unless something is collecting them. On Render free that's the platform's
> log stream with a short retention window, which I'm treating as the policy. The important
> part is that the application doesn't know or care — it writes JSON to stdout and
> collection is infrastructure's problem. That's the same contract a large fleet uses with a
> node agent, which means shipping to a real sink later is a configuration change and not a
> code change. The threshold that forces it is when I want to answer a question about
> something older than the retention window — and that arrives as soon as I start building a
> golden set from real user questions, because that's inherently a historical query.

---

# Concept 2.2 — RED Metrics and RAG Quality Signals

## 1. The theory

Logs answer questions about one request. **Metrics answer questions about the population**,
and they are the only thing that can wake you up, because nobody watches a log stream.

**RED** is the standard framing for a request-driven service:

| | Metric | Why |
|---|---|---|
| **R**ate | Requests per second | Load, and the cost driver |
| **E**rrors | Failed requests / total | The obvious one |
| **D**uration | Latency distribution — **percentiles, never the mean** | The user-visible property |

Percentiles matter more than most people internalise. **A mean latency hides the tail
completely**: if 95 requests take 200 ms and 5 take 8 seconds, the mean is 590 ms and looks
fine, while one user in twenty is watching a spinner for eight seconds. You alert on p95
and p99, not on the average.

For a RAG system, RED is necessary and not sufficient — it tells you the service is *up*,
not that the answers are *good*. That needs a second family.

## 2. The production problem it solves

Two distinct problems.

**(a) You cannot watch a log stream.** With logging alone, degradation is detected when a
human notices. That is not a detection strategy.

**(b) Quality degrades silently, and you have no labels in production.** Real cases that
would produce no error, no exception, and no log-level warning:

- The corpus is re-ingested and something breaks. Retrieval returns nothing relevant. The
  system starts refusing everything. **No error is raised** — refusal is a valid answer.
- The keyword arm dies. The semantic arm covers. Quality drops for exact-identifier
  questions only. **Already happened to you**, for months.
- The embedding model changes behind its alias. Score distributions shift. Your `0.35`
  threshold is now calibrated for a different distribution.
- A tenant uploads a large document. Retrieval starts returning its chunks for everything.

Every one is invisible to RED and to a status page. **Refusal rate catches three of the
four**, and it requires no labelled data at all.

## 3. How large companies implement it

Prometheus-shaped, almost universally: the application exposes a `/metrics` endpoint in a
text exposition format; a Prometheus server scrapes it every 15–60 s; Grafana queries it;
Alertmanager routes alerts. Counters, gauges and histograms are the primitives, with
percentiles computed from histogram buckets.

The relevant detail for you: **metrics are pull-based and in-process counters are
per-instance.** Prometheus scrapes each replica separately and aggregates at query time.
That design assumption is exactly what breaks on a platform that restarts your single
instance frequently — which is section 6.

## 4. How CampusBrain implements the same principle, free

Two layers, because they answer different questions.

### (a) Derive metrics from logs — the durable layer

The `rag_answer` event already contains everything needed. Aggregation is a query, not a
counter:

```bash
# Refusal rate today
grep '"event":"rag_answer"' logs.jsonl | jq -s 'map(.refused) | (map(select(.)) | length) / length'

# p95 total latency
grep '"event":"rag_answer"' logs.jsonl \
  | jq -s 'map(.retrieval_ms + .llm_ms) | sort | .[(length * 0.95 | floor)]'

# Queries where the keyword arm contributed nothing
grep '"event":"rag_answer"' logs.jsonl | jq -s 'map(select(.keyword_hits == 0)) | length'
```

**This is the layer that survives restarts**, because the logs are outside the process. It
is also why Concept 2.1 comes first: build the event well and the metrics are free.

### (b) In-process counters for the live view — the cheap layer

```python
# backend/app/core/metrics.py
"""In-process counters for a live operational view.

Deliberately NOT durable: these reset on every restart, and Render's free tier
restarts often. They answer "what is happening right now", not "what happened
last Tuesday" — that second question is answered by querying the logs, which
outlive the process.

No prometheus_client: it would add a dependency to produce an exposition format
nothing here scrapes. A JSON endpoint is the same information for one import
fewer. The moment a real Prometheus exists, swapping this out is contained to
this file and the endpoint.
"""

import threading
from collections import deque

_lock = threading.Lock()          # uvicorn runs sync endpoints in a threadpool
_counters: dict[str, int] = {}
_latencies: dict[str, deque] = {}   # bounded ring buffers -- memory is capped


def incr(name: str, n: int = 1) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0) + n


def observe(name: str, value_ms: float) -> None:
    with _lock:
        _latencies.setdefault(name, deque(maxlen=1000)).append(value_ms)


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return round(s[min(int(len(s) * p), len(s) - 1)], 1)


def snapshot() -> dict:
    with _lock:
        counters = dict(_counters)
        latencies = {k: list(v) for k, v in _latencies.items()}

    answers = counters.get("rag.answers", 0)
    return {
        "counters": counters,
        "rates": {
            # Guard the divisor: these are the fields most likely to be read by
            # a dashboard, and a ZeroDivisionError in a metrics endpoint is a
            # self-inflicted outage.
            "refusal_rate": round(counters.get("rag.refused", 0) / answers, 3) if answers else None,
            "zero_keyword_hit_rate": round(counters.get("rag.zero_keyword", 0) / answers, 3) if answers else None,
            "mean_citations": round(counters.get("rag.citations", 0) / answers, 2) if answers else None,
        },
        "latency_ms": {
            name: {"n": len(v), "p50": _pct(v, 0.50), "p95": _pct(v, 0.95), "p99": _pct(v, 0.99)}
            for name, v in latencies.items()
        },
    }
```

Wire it into the same place as the log event, and expose it:

```python
# main.py -- admin-only: this is operational data, not public.
@app.get("/metrics")
def metrics(_: int = Depends(require_search_access)) -> dict:
    return metrics_module.snapshot()
```

Note the `maxlen=1000` ring buffers. On a 512 MB box, an unbounded list of every latency
ever observed is a slow memory leak that eventually OOMs the only worker — which is exactly
the failure mode this deployment has already experienced once. **A metrics system that
takes down the service it monitors is the classic own-goal**, and bounding the buffer is the
one-word fix.

### (c) The RAG-specific signals — the ones that matter most

| Signal | What a change means | Why it needs no labels |
|---|---|---|
| **Refusal rate** | Spikes when retrieval breaks, the corpus changes, or embeddings drift | The system tells you it found nothing |
| **`zero_keyword_hit_rate`** | The keyword arm is dying | Derived from the fused result composition |
| **`best_semantic_score` distribution** | Shifts when the embedding model or corpus changes | Distribution shift is detectable without knowing the right answer |
| **Mean citations per answer** | Drops when grounding degrades or `keep_cited_sources` regresses | Structural property of the output |
| **p95 `llm_ms` / `retrieval_ms`** | Which stage regressed | Independent stage timing |

**Alert on distribution shift, not on absolute thresholds.** An absolute refusal-rate
threshold set today is wrong in a month because the corpus grew. "Refusal rate is 2× its
7-day median" stays meaningful.

## 5. Why this is appropriate today

- **One instance**, so in-process counters have no aggregation problem.
- **Logs are the durable layer**, so restart-resetting counters are an acceptable
  limitation rather than a data loss.
- **No dependency.** `prometheus_client` would add an import to emit a format nothing
  scrapes.
- **The RAG signals are the point**, and they are custom regardless — no off-the-shelf
  library knows what your refusal rate means.

## 6. At what scale it stops being appropriate

| Threshold | What breaks |
|---|---|
| **More than one instance or worker** | Counters are per-process. `/metrics` returns whichever instance answered — the numbers become meaningless, not merely incomplete |
| **You want history** | Counters reset on restart, and Render free restarts often. Any trend question already has to go to the logs |
| **You want to be woken up** | A pull endpoint nobody polls is not an alert |
| **Cardinality grows** | Per-org, per-model, per-archetype breakdowns turn a dict into a combinatorial explosion. This is *the* classic metrics scaling failure |

The second one is the honest headline: **these counters are a live debugging view, not a
monitoring system.** Say that plainly rather than overselling it.

## 7. What I would migrate to next

1. **A free-tier hosted metrics backend** — Grafana Cloud free includes Prometheus and
   alerting. Push from the app or expose `/metrics` in Prometheus format and let it scrape.
   This solves history and alerting together, which are the two real gaps.
2. **`prometheus_client` when there is a scraper**, not before. It gives correct histogram
   buckets rather than my percentile-over-a-ring-buffer approximation, which is only valid
   for the last 1000 requests.
3. **A synthetic canary.** A free external cron (cron-job.org, GitHub Actions) posting a
   known question every 15 minutes and asserting the answer contains an expected fact. This
   is the cheapest real *alerting* available, it needs no metrics backend at all, and on
   Render free it doubles as the keep-alive that stops the instance sleeping mid-ingestion
   (Pillar 1). **One free cron job solving a monitoring problem and a reliability problem is
   exactly the kind of leverage this project should be looking for.**

## 8. How to test it

```python
def test_percentile_on_empty_returns_zero_not_crash():
    """A metrics endpoint that 500s during an incident is worse than useless."""
    assert _pct([], 0.95) == 0.0


def test_rates_are_none_not_zerodivision_before_first_request():
    metrics._counters.clear()
    assert snapshot()["rates"]["refusal_rate"] is None


def test_latency_buffer_is_bounded():
    """Unbounded growth would OOM the only worker on a 512Mi box."""
    for i in range(5000):
        observe("t", float(i))
    assert len(_latencies["t"]) == 1000


def test_refusal_rate_reflects_a_refusal(client, monkeypatch):
    monkeypatch.setattr(rag_service, "RELEVANCE_THRESHOLD", 0.99)
    client.post("/api/v1/chat", json={"question": "anything"})
    assert snapshot()["rates"]["refusal_rate"] == 1.0


def test_metrics_endpoint_requires_credentials(client):
    assert client.get("/metrics").status_code == 401
```

The first three test *the monitoring system's own failure modes*, which is the part people
skip. The last one matters because `/metrics` leaks operational detail — query volume per
tenant, latency, error rates — and a public metrics endpoint is a genuine information
disclosure.

## 9. How to intentionally break it

| Inject | Should observe |
|---|---|
| Set `RELEVANCE_THRESHOLD = 0.99` | `refusal_rate` → 1.0 within a few requests. The quality alarm fires with no errors and no exceptions anywhere |
| Return `[]` from `keyword_search` | `zero_keyword_hit_rate` → 1.0 while answers still look correct |
| `time.sleep(5)` in `get_llm_provider().generate` | p95 `llm_ms` moves, `retrieval_ms` does not |
| Delete the Qdrant collection | `refusal_rate` → 1.0 **and** `best_semantic_score` → 0. Two independent signals agreeing is what a real incident looks like |
| Remove the `maxlen` and drive 10 M requests | Memory climbs until OOM. **Do this in local Docker with a memory limit, never on Render** |

The last one is the most instructive and the one nobody does. Watching your own monitoring
take down your service teaches the lesson permanently.

## 10. Interview questions to expect

1. What are RED metrics? What about USE?
2. Why percentiles instead of averages?
3. How do you monitor quality when you have no ground-truth labels in production?
4. What would you alert on, and at what threshold?
5. Why in-process counters instead of Prometheus?
6. What is cardinality and why does it matter?
7. Your metrics reset on restart. Is that acceptable?
8. How would you detect that half of a hybrid retrieval system had died?

## 11. Model answers

**"Why percentiles, not averages?"**

> Because the mean hides the tail, and the tail is what users experience. If 95 requests
> take 200 ms and 5 take 8 seconds, the mean is 590 ms and looks healthy while one user in
> twenty waits eight seconds. Percentiles also compose badly — you can't average two p95s
> across instances, which is why proper metrics systems store histogram buckets and compute
> percentiles at query time. My ring-buffer approach approximates it over the last 1000
> requests, which is fine at one instance and is exactly what I'd replace with a real
> histogram when there's a scraper.

**"How do you monitor quality with no labels in production?"**

> Proxy signals that don't need ground truth. Refusal rate is the best single one — my
> system refuses when nothing retrieved clears a similarity threshold, so a spike means
> retrieval broke, the corpus changed, or embeddings drifted, and none of those raise an
> error. Then the distribution of the top semantic score, which shifts when the embedding
> model changes behind its alias. Mean citations per answer, which drops when grounding
> degrades. And a per-arm hit count, because a hybrid system hides the death of either arm —
> that's not hypothetical for me, my keyword arm returned nothing for months because
> `plainto_tsquery` ANDs every term, and the semantic arm covered for it.
>
> I alert on shift against a rolling median rather than absolute thresholds, because
> absolutes drift as the corpus grows. And the cheapest real alerting is a synthetic canary
> — a free external cron posting a known question every fifteen minutes and asserting the
> answer contains an expected fact. That needs no metrics backend at all.

**"Why not Prometheus?"**

> Because Prometheus is a pull-based system and I have nothing pulling. Adding
> `prometheus_client` would give me an exposition format with no scraper, which is a
> dependency for zero benefit. What I have instead is two layers: in-process counters for a
> live view, and the structured logs as the durable layer — every metric I care about is
> derivable from the `rag_answer` event with a `jq` aggregation, and the logs outlive the
> process where the counters don't.
>
> The threshold that changes it is a second instance, because in-process counters are
> per-process and `/metrics` would return whichever one answered — that's meaningless
> rather than merely incomplete. At that point I'd move to Grafana Cloud's free tier, which
> gets me history and alerting, and those are the two things I'm genuinely missing rather
> than the format.

**"What is cardinality and why does it matter?"**

> Cardinality is the number of distinct label combinations on a metric. It matters because
> each combination is a separate time series stored separately, so it multiplies. If I broke
> latency down by org, model, prompt version and question archetype, that's the product of
> all four — and if I ever labelled by something unbounded like user ID or the question text,
> it explodes and takes down the metrics backend. It's the classic way people bring down
> their own monitoring. The rule is that labels must be bounded and low-cardinality; anything
> high-cardinality belongs in a log line, where it's one field on one event, not a new time
> series. That's actually a good argument for my log-derived approach at this scale — logs
> have no cardinality problem at all.

**"Your metrics reset on restart. Is that acceptable?"**

> Yes, because I've been explicit that they're a live operational view rather than a
> monitoring system, and the durable layer is the logs. Every metric I expose is derivable
> from the `rag_answer` event, so a restart loses the convenience, not the data. It would
> stop being acceptable the moment I need to answer a question about a time window longer
> than the current uptime — and on Render's free tier, which restarts often, that's a low
> bar. That's the migration trigger for a hosted metrics backend, and I'd rather state the
> trigger than pretend the limitation isn't there.

---

# Concept 2.3 — Liveness versus Readiness

## 1. The theory

Two probes that look identical and mean opposite things:

| | **Liveness** | **Readiness** |
|---|---|---|
| Asks | "Is this process alive?" | "Can this instance serve traffic *right now*?" |
| Failing means | **Kill and restart me** | **Stop routing to me** (do not restart) |
| Checks | Nothing external | Dependencies |
| Wrong answer costs | Restart loops, or a hung process never restarted | Serving errors, or being removed when healthy |

**The rule that follows and that most people get backwards: a liveness probe must never
check a dependency.** If liveness checks Postgres and Postgres blips, the platform kills a
perfectly healthy process — turning a brief dependency failure into a restart storm, during
which nothing serves at all. You have amplified an outage with your own health check.

Readiness is where dependencies belong, because the correct response to "Postgres is down"
is to stop sending traffic, not to restart a process that will come back up equally unable
to reach Postgres.

## 2. The production problem it solves

**Restart amplification.** A dependency has a 30-second blip. A dependency-checking liveness
probe fails. The orchestrator kills every instance. They restart, still cannot reach the
dependency, fail again, and enter `CrashLoopBackOff`. **The 30-second blip is now a
multi-minute outage caused entirely by the health check.**

**The inverse:** a liveness probe that only checks the HTTP server is alive will happily
report healthy while the process is deadlocked or has a leaked connection pool, so a hung
instance is never restarted.

**And the readiness case:** without one, a freshly started instance receives traffic before
migrations have run or the vector client has connected, and serves errors for the first few
seconds of every deploy.

## 3. How large companies implement it

Kubernetes formalises three, and knowing all three is a standard interview beat:

| Probe | Failure action | Typical check |
|---|---|---|
| **Liveness** | Restart the container | Process responds. Nothing external |
| **Readiness** | Remove from the load-balancer pool | DB, cache, downstream services |
| **Startup** | Delay the other two until it passes | Slow initialisation — model loading, migrations |

The startup probe exists because a slow-booting service would otherwise be killed by
liveness before it ever finished booting. That is directly relevant to you: this app imports
PaddlePaddle and PaddleOCR, which is a slow, memory-heavy startup.

## 4. How CampusBrain implements the same principle, free

**Your `/health` is already correct**, and the comment already states the principle. Do not
change it. What is missing is the readiness half.

```python
@app.get("/health/ready")
def readiness() -> JSONResponse:
    """Readiness: can this instance actually serve? Checks dependencies, and
    returns 503 when it cannot.

    Kept strictly separate from /health, which is liveness and must stay
    dependency-free — a liveness probe that checks Postgres turns a 30-second
    Postgres blip into a restart storm.

    Render's free tier has no configurable readiness probe and no load
    balancer to remove an instance from, so nothing consumes this
    automatically today. It exists for two consumers that do: a human during
    an incident, and the synthetic canary cron -- which needs to distinguish
    "the app is broken" from "a dependency is down" to avoid paging on the
    wrong thing.
    """
    checks: dict[str, str] = {}

    try:
        db = SessionLocal()
        db.execute(sql_text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {type(e).__name__}"
    finally:
        db.close()

    try:
        vector_store.get_client().get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {type(e).__name__}"

    ok, detail = storage.health_check()
    checks["storage"] = "ok" if ok else f"error: {detail}"

    # Storage is deliberately NOT fatal. Object storage is only needed to
    # ingest a new document; chat reads chunk text from Postgres and vectors
    # from Qdrant and never touches a blob. Failing readiness on storage would
    # take the chatbot down for every student because an admin cannot upload,
    # which is the wrong trade.
    critical_ok = checks["postgres"] == "ok" and checks["qdrant"] == "ok"
    return JSONResponse(
        status_code=200 if critical_ok else 503,
        content={"status": "ready" if critical_ok else "degraded", "checks": checks},
    )
```

**The `critical_ok` distinction is the most interview-valuable thing in this concept.** It
is not a technical detail, it is a product decision expressed in code: *storage being down
degrades ingestion, not chat, so it must not remove the instance from service.* That is
**graceful degradation** — a Pillar 1 concept appearing here — and articulating why one
dependency is fatal and another is not demonstrates you have reasoned about the blast radius
of each rather than checking everything you could think of.

Note also that the error strings use `type(e).__name__` and not `str(e)`. A raw exception
message can contain a connection string with credentials, and this endpoint is
unauthenticated. Leaking a Neon password through a health check would be a genuinely
embarrassing way to be breached.

## 5. Why this is appropriate today

- The liveness/readiness **split** is the transferable idea; whether a platform consumes it
  is incidental.
- Render free has no configurable readiness probe and no pool to be removed from, so this
  is for humans and the canary. **Say that** rather than implying it is wired up.
- Not fatal-on-storage matches the actual dependency graph of the request path.

## 6. At what scale it stops being appropriate

| Threshold | What breaks |
|---|---|
| **Multiple instances behind a load balancer** | Now readiness must be *consumed*, or a degraded instance keeps receiving traffic |
| **Slow startup becomes fatal** | PaddleOCR import time plus a liveness timeout equals a kill loop before boot completes. You need a **startup probe** or a generous initial delay |
| **Dependency checks become expensive** | If a probe runs every 5 s and does three network round trips, you have built a load generator against your own dependencies. Cache the result for a few seconds |
| **A dependency is slow rather than down** | A readiness check with no timeout hangs, so the probe times out and the instance is marked unready — correct outcome, accidental mechanism. Give the checks explicit short timeouts |

The third one is a real and commonly-shipped bug: **health checks that DoS the database
they are checking.**

## 7. What I would migrate to next

1. **Wire readiness to something that consumes it** — the moment there is more than one
   instance, or a platform with configurable probes (Render paid, Fly, Railway).
2. **A startup probe / initial delay**, once cold-start time is measured. Today it is
   unmeasured, which is itself the finding.
3. **Cache the readiness result** for ~5 seconds once anything polls it frequently.
4. **A dependency-health dashboard** fed by the canary hitting `/health/ready` on a
   schedule, so you have history rather than a point-in-time answer.

## 8. How to test it

```python
def test_liveness_stays_200_when_postgres_is_down(client, monkeypatch):
    """The single most important test in this concept: liveness must NOT
    check dependencies, or a DB blip becomes a restart storm."""
    monkeypatch.setattr(database, "SessionLocal", _raises_connection_error)
    assert client.get("/health").status_code == 200


def test_readiness_returns_503_when_postgres_is_down(client, monkeypatch):
    monkeypatch.setattr(database, "SessionLocal", _raises_connection_error)
    r = client.get("/health/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["postgres"].startswith("error")


def test_readiness_stays_200_when_only_storage_is_down(client, monkeypatch):
    """Graceful degradation: storage is needed to ingest, not to chat.
    Failing readiness here would take chat down for every student."""
    monkeypatch.setattr(storage, "health_check", lambda: (False, "unreachable"))
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["checks"]["storage"].startswith("error")


def test_readiness_does_not_leak_credentials(client, monkeypatch):
    """Unauthenticated endpoint: an exception message can contain a DSN."""
    def boom():
        raise Exception("could not connect to postgresql://user:hunter2@host/db")
    monkeypatch.setattr(database, "SessionLocal", boom)
    assert "hunter2" not in client.get("/health/ready").text
```

Those four tests encode four distinct pieces of judgement, which is why this concept is
worth its length despite being ~30 lines of code.

## 9. How to intentionally break it

| Inject | Should observe |
|---|---|
| Point `DATABASE_URL` at a dead host, restart | `/health` → **200**. `/health/ready` → **503**, `postgres: error`. This is the whole concept in one drill |
| Revoke the Qdrant API key | `/health/ready` → 503, `qdrant: error`, `postgres: ok`. Chat refuses everything; refusal rate confirms from the other direction |
| Break Supabase credentials | `/health/ready` → **200**, `storage: error`. **Chat still works.** Graceful degradation, demonstrated |
| Add `time.sleep(30)` to the Qdrant check | The probe hangs. Now add a 2 s timeout and watch it fail fast instead — the difference between a correct outcome by accident and by design |

## 10. Interview questions to expect

1. Liveness versus readiness — what happens when each fails?
2. Why must a liveness probe not check the database?
3. What is a startup probe for?
4. Which dependencies should fail readiness, and which should not?
5. Your health check passes but users get errors. What did you miss?
6. How do you avoid health checks overloading a dependency?

## 11. Model answers

**"Liveness versus readiness?"**

> Liveness asks whether the process is alive; failing it means restart me. Readiness asks
> whether this instance can serve right now; failing it means stop routing to me, but don't
> restart. The critical rule is that liveness must never check a dependency — if it checks
> Postgres and Postgres blips for thirty seconds, the platform kills every healthy instance
> and they crash-loop trying to reach a database that's still down. You've turned a
> thirty-second blip into a multi-minute outage with your own health check. Dependencies
> belong in readiness, because the right response to a dependency being down is to stop
> serving, not to restart.

**"Which dependencies should fail readiness?"**

> Only the ones on the path of the request you're protecting, which means it's a product
> decision rather than a technical one. In mine, Postgres and Qdrant are fatal — chat reads
> chunk text from Postgres and vectors from Qdrant, so without either it cannot answer. Object
> storage is deliberately not fatal: it's only needed to ingest a new document, and chat
> never reads a blob. If I failed readiness on storage I'd take the chatbot down for every
> student because an admin can't upload, which is clearly the wrong trade. So the endpoint
> reports storage as degraded and still returns 200. That's graceful degradation — the
> system loses a capability instead of losing service.

**"Your health check passes but users get errors. What did you miss?"**

> Almost certainly that the health check doesn't exercise the real request path. A probe
> that returns `{"status": "ok"}` proves the HTTP server is accepting connections and
> nothing else. Mine has exactly that limitation — `/health` is deliberately dependency-free
> for the liveness reason, and `/health/ready` checks that dependencies are *reachable*, not
> that retrieval returns anything sensible. The gap is closed by a synthetic canary: an
> external cron posting a real question every fifteen minutes and asserting the answer
> contains a known fact. That's the only check that exercises embed, search, fuse, prompt and
> generate end to end, and it's the one that would have caught my keyword arm being dead —
> which no probe and no error rate ever did.

**"How do you stop health checks overloading a dependency?"**

> Cache the result and give every check an explicit timeout. If a probe runs every five
> seconds and does three network round trips, and you have twenty instances, that's twelve
> dependency calls a second purely from monitoring — you've built a load generator aimed at
> the thing you're trying to protect. Caching for a few seconds costs you a slightly stale
> answer, which is fine for a signal that's polled continuously. The timeout matters
> separately: without one, a *slow* dependency hangs the probe until the platform's own
> timeout fires, so you get the right outcome by accident rather than by design, and you
> can't distinguish slow from down in your logs.

---

# Closing artifacts

## ADR-001 — Structured logging with in-process correlation

**Status:** Proposed · **Date:** 2026-07-30

**Context.** No observability on the request path. A user-reported wrong answer cannot be
investigated: the retrieved chunks, prompt version and model version are all unrecorded.
Deployment is a single Render free instance — one worker, 512 MB, no persistent disk, short
log retention.

**Decision.** Structured JSON logging to stdout, with a request ID carried in a
`contextvars.ContextVar`, injected into every record by a `logging.Filter`, honoured from an
inbound `X-Request-Id` and returned in the response. Metrics derived from those logs, plus
bounded in-process counters for a live view. No OpenTelemetry, no `prometheus_client`, no
log-shipping service.

**Consequences.**
*Positive:* zero dependencies; the app is ignorant of log collection, so shipping to a real
sink later is configuration rather than code; every RAG-quality metric becomes derivable.
*Negative:* counters reset on restart; retention is the platform's short window; no
parent/child span relationships; the `ContextVar` will not cross a process boundary.
*Revisit when:* a second process exists (→ OpenTelemetry), or a question needs answering
outside the retention window (→ hosted log sink).

**Alternatives rejected.** OpenTelemetry — solves cross-service propagation, and there is
one process. `prometheus_client` — an exposition format with no scraper. Threading
`request_id` as a parameter — couples four layers to a value none of them read.

## ADR-002 — Liveness and readiness as separate endpoints

**Status:** Proposed · **Date:** 2026-07-30

**Context.** `/health` exists and is correctly dependency-free. `/health/storage` exists but
nothing consumes it and it covers only one dependency. No endpoint answers "can this
instance serve".

**Decision.** Add `/health/ready` checking Postgres, Qdrant and storage. Postgres and Qdrant
are fatal (503); **storage is reported but not fatal**, because chat does not read blobs.
Error details are exception *type names*, never messages, because the endpoint is
unauthenticated and messages can contain a DSN.

**Consequences.** Nothing consumes readiness on Render free — it serves humans and the
canary. Adds three network calls per invocation, acceptable while nothing polls it
frequently; cache when something does.

**Revisit when:** more than one instance exists, or cold-start time is measured and found to
need a startup probe.

## Production incident example — write this one up

> **INC-001 — Silent keyword-arm failure**
>
> **Impact.** For an unknown period, questions containing exact identifiers — company names,
> course codes — returned generic prospectus text instead of the specific chunk. No errors,
> no alerts, no user reports. Discovered by hand while debugging an unrelated question.
>
> **Root cause.** `plainto_tsquery` ANDs every term, so a natural-language question matched
> no chunk unless one contained every word. The keyword arm returned zero results for most
> queries. The semantic arm covered the failure completely.
>
> **Why detection took months.** Hybrid retrieval is redundant by design, and redundancy
> masks single-component failure. Nothing measured per-arm contribution.
>
> **Resolution.** `_to_or_tsquery` ORs the terms and lets `ts_rank` order the results.
>
> **Prevention.** `keyword_hits` on every `rag_answer` event and `zero_keyword_hit_rate` as a
> metric. A synthetic canary asserting an exact-identifier question returns the expected
> chunk.
>
> **Lesson.** Every redundant subsystem needs per-component observability, or redundancy
> converts a loud failure into a silent degradation.

This is a real incident from your own history. Writing it up in this format is a Pillar 8
artifact you can produce today, and *"here's a postmortem I wrote for an incident in my own
system"* is a strong thing to hand an interviewer.

## Common mistakes

| Mistake | Why it bites |
|---|---|
| Dependency checks in the liveness probe | Turns a dependency blip into a restart storm |
| Logging text rather than structure | Unqueryable. You will regret it at the worst moment |
| No request ID | Log lines cannot be joined into a request |
| Threading the ID through every signature | Couples every layer to a cross-cutting concern |
| Alerting on the mean | Hides the tail entirely |
| Absolute-threshold alerts | Drift into uselessness as the corpus grows |
| Unbounded metric buffers | Your monitoring OOMs the service it monitors |
| High-cardinality metric labels | Explodes the time-series backend. Put it in a log field |
| Raw exception messages in an unauthenticated health check | Leaks connection strings |
| Logging prompts and questions with no retention decision | A compliance problem created while fixing a debugging problem |
| No per-arm metrics in a redundant system | Redundancy hides failure — INC-001 |

## Resume bullets

Pick one or two. Each is defensible line by line against the code.

> Instrumented a multi-tenant RAG service with structured JSON logging and request
> correlation via `contextvars`, capturing retrieved chunk IDs, prompt and model versions,
> and per-stage latency — reducing a previously un-investigable class of "wrong answer"
> report to a single log query.

> Designed RAG-specific quality signals (refusal rate, per-arm retrieval hit rate,
> similarity-score distribution) that detect retrieval degradation without labelled data,
> after a silent keyword-arm failure went undetected because hybrid retrieval masked it.

> Separated liveness from readiness probes with per-dependency criticality — object-storage
> failure degrades ingestion but does not remove the instance from service — preventing
> dependency blips from triggering restart amplification.

---

## Definition of done for Pillar 2

- [ ] `app/core/observability.py` — `ContextVar`, `RequestIdFilter`, `JsonFormatter`, `configure_logging`
- [ ] `request_context` middleware registered **last** (outermost), returning `X-Request-Id`
- [ ] `rag_answer` event with chunk IDs, scores, versions and per-stage timings
- [ ] `PROMPT_VERSION` constant exists and is logged *(also unblocks Pillar 4)*
- [ ] `app/core/metrics.py` with **bounded** buffers; `/metrics` behind credentials
- [ ] `/health/ready` with per-dependency criticality and type-name-only errors
- [ ] All tests from §8 of each concept, including the log-injection and
      liveness-survives-DB-death cases
- [ ] All four failure injections from §9 performed and the observations recorded
- [ ] INC-001 written up as a postmortem
- [ ] Retention decision documented

**Then, and only then, Pillar 1 (Reliability)** — where the first thing built is a durable
job table, and the first thing you will want when it fails is the request ID you can now
follow into a background task.
