import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown, FileText, Search } from 'lucide-react'
import { Skeleton } from './ui/primitives'
import { cn } from './lib/utils'
import type { Citation, RetrievedDocument } from './types'

const ease = [0.16, 1, 0.3, 1] as const

type SourceGroup = {
  documentId: number
  filename: string
  /** Every citation drawn from this document, in the order the answer cites them. */
  citations: Citation[]
  /** Distinct pages, ascending. */
  pages: number[]
}

/* One card per DOCUMENT, not per retrieved chunk.

   Five chunks from the admission handbook used to render as five cards that
   all said the same filename — which reads as five sources when it is one.
   That overstates the breadth of evidence behind an answer, which is exactly
   the kind of quiet dishonesty this product is supposed to avoid.

   Group order follows first mention in the answer, so the rail reads top to
   bottom in the same order the reader meets the markers. */
export function groupSources(citations: Citation[]): SourceGroup[] {
  const byDoc = new Map<number, SourceGroup>()

  for (const c of citations) {
    let g = byDoc.get(c.document_id)
    if (!g) {
      g = { documentId: c.document_id, filename: c.filename, citations: [], pages: [] }
      byDoc.set(c.document_id, g)
    }
    g.citations.push(c)
    if (!g.pages.includes(c.page_number)) g.pages.push(c.page_number)
  }

  const groups = [...byDoc.values()]
  for (const g of groups) {
    g.citations.sort((a, b) => a.index - b.index)
    g.pages.sort((a, b) => a - b)
  }
  groups.sort((a, b) => a.citations[0].index - b.citations[0].index)
  return groups
}

export function SourceRail({
  citations,
  retrieved,
  loading,
  activeCite,
}: {
  citations: Citation[]
  /** What retrieval found, available before generation finishes. Superseded by
      `citations` the moment those arrive — see the three-state note below. */
  retrieved: RetrievedDocument[]
  loading: boolean
  /** Marker the reader just clicked. Reruns on every click, including a
      repeat of the same marker — see the `seq` note in Message. */
  activeCite: { n: number; seq: number } | null
}) {
  const groups = useMemo(() => groupSources(citations), [citations])
  const [openDocs, setOpenDocs] = useState<Set<number>>(new Set())
  const buttons = useRef<Map<number, HTMLButtonElement>>(new Map())
  /* Every rail on the page renders documents with the same ids, so element ids
     have to be scoped per rail. Without this, `aria-controls` on the third
     answer's source card points at the FIRST answer's panel — and the old
     href="#source-1" markers had the same collision, silently scrolling to the
     earliest matching source in the thread rather than the one clicked. */
  const uid = useId()

  /* Clicking a marker in the prose has to do three things, because a jump
     alone leaves the reader looking at a collapsed card that doesn't show the
     sentence they asked about: expand the owning document, bring it into
     view, and move focus there so a keyboard user follows the same path a
     mouse user does. */
  useEffect(() => {
    if (!activeCite) return
    const owner = groups.find((g) => g.citations.some((c) => c.index === activeCite.n))
    if (!owner) return

    setOpenDocs((prev) => new Set(prev).add(owner.documentId))
    const btn = buttons.current.get(owner.documentId)
    btn?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    /* preventScroll: scrollIntoView above is already animating a smooth
       scroll; letting focus() do its own instant one fights it and lands the
       card half off-screen. */
    btn?.focus({ preventScroll: true })
  }, [activeCite, groups])

  /* Three states, and the middle one is the reason P2-2 exists.

     1. searching  — retrieval hasn't returned. Nothing true to show: skeleton.
     2. searched   — retrieval returned, generation is still running. Real
                     document names, but they are candidates, NOT sources: the
                     model may cite none of them. Labelled "searched", not
                     expandable, and carries no excerpt text (the backend
                     deliberately withholds it) so nothing here can be mistaken
                     for evidence behind the answer.
     3. cited      — the answer is complete. Now these are sources.

     State 2 shrinking to a smaller list in state 3 is expected, not a glitch:
     5 documents searched, 3 actually cited. The label change is what makes the
     difference legible instead of looking like items disappeared. */
  const cited = groups.length > 0
  const searched = !cited && retrieved.length > 0
  if (!loading && !cited && !searched) return null

  return (
    <section className="mb-6" aria-label="Sources">
      <div className="mb-3 flex items-center gap-2">
        <Search className="size-3.5 text-faint" aria-hidden="true" />
        <span className="eyebrow">
          {cited
            ? `${groups.length} source${groups.length === 1 ? '' : 's'}`
            : searched
              ? `Reading ${retrieved.length} document${retrieved.length === 1 ? '' : 's'}`
              : 'Searching documents'}
        </span>
      </div>

      {searched ? (
        <div className="flex flex-col gap-2">
          {retrieved.map((d, i) => (
            <RetrievedRow key={d.document_id} doc={d} delay={i * 0.04} />
          ))}
        </div>
      ) : loading ? (
        <div className="flex flex-col gap-2">
          {['w-[62%]', 'w-[48%]', 'w-[55%]'].map((w, i) => (
            <div
              key={i}
              className="rounded-[var(--radius-card)] border border-border bg-surface px-4 py-3.5"
            >
              <div className="flex items-center gap-3">
                <Skeleton className="size-6 rounded-[7px]" />
                <Skeleton className={cn('h-[11px]', w)} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {groups.map((g, i) => (
            <DocumentCard
              key={g.documentId}
              group={g}
              uid={uid}
              open={openDocs.has(g.documentId)}
              activeCite={activeCite?.n ?? null}
              onToggle={() =>
                setOpenDocs((prev) => {
                  const next = new Set(prev)
                  next.has(g.documentId) ? next.delete(g.documentId) : next.add(g.documentId)
                  return next
                })
              }
              buttons={buttons}
              delay={i * 0.04}
            />
          ))}
        </div>
      )}
    </section>
  )
}

/* A candidate document, mid-generation. Static on purpose — no disclosure
   affordance, because there is nothing to disclose: retrieved-but-uncited text
   is not evidence for this answer, so the backend sends no excerpt for it and
   this row must not imply one is hiding behind a chevron. */
function RetrievedRow({ doc, delay }: { doc: RetrievedDocument; delay: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.24, ease }}
      className="flex items-center gap-3 rounded-[var(--radius-card)] border border-border bg-surface px-4 py-3.5"
    >
      <FileText className="size-4 shrink-0 text-faint" aria-hidden="true" />
      <span className="min-w-0 flex-1 truncate text-[13.5px] text-muted">{doc.filename}</span>
      <span className="shrink-0 rounded-full border border-border bg-sunken px-2 py-0.5 font-mono text-[10.5px] text-faint">
        {doc.pages.length === 1 ? `p.${doc.pages[0]}` : `pp.${doc.pages.join(',')}`}
      </span>
    </motion.div>
  )
}

function DocumentCard({
  group: g,
  uid,
  open,
  activeCite,
  onToggle,
  buttons,
  delay,
}: {
  group: SourceGroup
  uid: string
  open: boolean
  activeCite: number | null
  onToggle: () => void
  buttons: React.MutableRefObject<Map<number, HTMLButtonElement>>
  delay: number
}) {
  const panelId = `${uid}-doc-${g.documentId}`
  const ownsActive = g.citations.some((c) => c.index === activeCite)

  /* Stable identity. An inline ref arrow is a new function every render, which
     makes React detach and reattach the ref each time — the map is briefly
     empty on every re-render, including the ones streaming causes. */
  const setButton = useCallback(
    (el: HTMLButtonElement | null) => {
      if (el) buttons.current.set(g.documentId, el)
      else buttons.current.delete(g.documentId)
    },
    [buttons, g.documentId],
  )

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.24, ease }}
      className={cn(
        'overflow-hidden rounded-[var(--radius-card)] border bg-surface transition-[border-color,box-shadow] duration-150',
        open || ownsActive
          ? 'border-accent-border shadow-[var(--shadow-card)]'
          : 'border-border hover:border-border-strong',
      )}
    >
      <button
        ref={setButton}
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="group/src flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors duration-150 hover:bg-hover"
      >
        <FileText className="size-4 shrink-0 text-faint" aria-hidden="true" />

        <span className="min-w-0 flex-1 truncate text-[13.5px] text-ink">{g.filename}</span>

        {/* Which markers in the prose this document backs. After grouping,
            "Sources (3)" counts documents while the superscripts still carry
            the model's own numbering — so the mapping between the two has to
            be stated on the card rather than left for the reader to infer. */}
        <span className="shrink-0 font-mono text-[10.5px] text-faint" aria-hidden="true">
          {g.citations.map((c) => c.index).join(' · ')}
        </span>

        <span className="shrink-0 rounded-full border border-border bg-sunken px-2 py-0.5 font-mono text-[10.5px] text-muted">
          {g.pages.length === 1 ? `p.${g.pages[0]}` : `pp.${g.pages.join(',')}`}
        </span>

        <ChevronDown
          className={cn(
            'size-4 shrink-0 text-faint transition-transform duration-200 ease-out',
            open && 'rotate-180',
          )}
          aria-hidden="true"
        />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={panelId}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease }}
          >
            <div className="flex flex-col gap-3 border-t border-border px-4 py-4">
              {g.citations.map((c) => (
                <div key={c.index} id={`${uid}-cite-${c.index}`}>
                  <div className="mb-1.5 flex items-center gap-2">
                    <span
                      className={cn(
                        'flex size-[18px] items-center justify-center rounded-[5px] border font-mono text-[10px] font-medium transition-colors duration-150',
                        c.index === activeCite
                          ? 'border-accent-border bg-accent text-accent-fg'
                          : 'border-border bg-sunken text-muted',
                      )}
                    >
                      {c.index}
                    </span>
                    <span className="font-mono text-[10.5px] text-faint">page {c.page_number}</span>
                  </div>
                  {/* Verbatim source text — the left rule marks it as a
                      quotation rather than the assistant's own prose. */}
                  <p
                    className={cn(
                      'border-l-2 pl-3 text-[13.5px] leading-[1.65] transition-colors duration-300',
                      c.index === activeCite
                        ? 'border-accent bg-accent-soft/40 text-ink'
                        : 'border-accent-border text-muted',
                    )}
                  >
                    {c.excerpt}
                  </p>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
