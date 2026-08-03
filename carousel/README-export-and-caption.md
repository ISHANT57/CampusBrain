# CampusBrain Carousel — Export Guide + LinkedIn Caption

## Files
- `campusbrain-carousel.html` — the deck. Open in a browser (Chrome/Edge/Safari).
- `carousel-content-and-design-spec.md` — per-slide copy, layout, diagram, icon, hierarchy, animation + speaker notes.

## How to export (no design tools needed)

**Option A — PDF (recommended for review / backup)**
1. Open `campusbrain-carousel.html` in Chrome.
2. `Cmd/Ctrl + P` → Save as PDF.
3. In *More settings*, set **Paper size** to `1200 x 675 px` (custom) and **Margins: None**, tick *Background graphics*.
4. Each slide prints on exactly one page (page size + page breaks are already set via `@page`).

**Option B — PNG slides (for the LinkedIn carousel upload)**
1. Open the file in Chrome.
2. `Cmd/Ctrl + Shift + I` → DevTools → `Cmd/Ctrl + Shift + P` → "Capture node screenshot".
3. Right-click each `<section class="slide">` node → *Capture node screenshot* → saves a crisp PNG at 1200×675. For retina quality, zoom to 200% before capturing.
4. Upload the 10 PNGs in order as a LinkedIn carousel document.

> LinkedIn carousels accept a PDF **or** up to 20 images. PNG gives sharper per-slide text.

## Design notes for any manual rebuild (Figma/Canva)
- Canvas **1200 × 675** (landscape 16:9) per slide.
- Colors: Ink `#111827` · Secondary `#2563EB` · Accent `#14B8A6` · Hairline `#E5E7EB` · Background `#FFFFFF`.
- Type: **Inter** (weights 600/700/800). Body ≤ 2 sizes per slide.
- Margins: 72px horizontal, ~54px top, ~52px bottom; keep the footer hairline at bottom-34.
- Keep the header block identical on every slide: index (top-left), headline, muted subtitle.

## Suggested LinkedIn caption (post text)

> I didn't build another RAG chatbot. I built a production-oriented AI knowledge platform.
>
> Most RAG projects stop after Upload → Vector Search → LLM → Answer. CampusBrain is built around everything that happens **after the demo works**:
>
> • Durable, Postgres-backed ingestion jobs (`SKIP LOCKED`, stale-lease reaper)
> • Hybrid retrieval (semantic + keyword, fused) with citation-enforced answers
> • SSE streaming, audit logs, correlation IDs, liveness vs readiness
> • A cost ledger — and a reranker we measured, then deliberately rejected with data
>
> The demo is table stakes. The operating layer — reliability, observability, security, cost, recovery, trade-offs — is the product.
>
> I'd love feedback from backend, platform, and AI engineers on the architecture and engineering trade-offs. 👇
>
> #SystemDesign #RAG #BackendEngineering #AISystems #Reliability #SoftwareEngineering

## Honesty guardrail
Keep the framing *"production-oriented / built using production engineering principles"* — the codebase's own production review shows the operational envelope is still maturing, and this deck treats that journey as the story. Never claim "production ready."
