import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown, ShieldCheck, ShieldOff } from 'lucide-react'
import { cn } from './lib/utils'
import type { Grounding } from './types'

const ease = [0.16, 1, 0.3, 1] as const

/* "Why this answer" — the measured basis for what was just said.

   There is deliberately no High/Medium/Low badge here, and that absence is the
   design. Bucketing a similarity score into three labels means choosing
   cutoffs, and no cutoff in this system has ever been validated against a
   labelled set — the same reason eval_service refuses to report recall or
   precision (ADR-016). A badge reading "High confidence" would be quoted back
   as though something measured it.

   So the summary line states counts, which are exact, and the disclosure holds
   the score alongside the threshold it was compared against. A reader who
   wants to judge can; nobody is told what to conclude.

   Two audiences, one component: a student needs "based on 3 documents", an
   admin debugging a bad answer needs the score. The summary serves the first
   without the second having to leave the conversation. */
export function GroundingBar({ grounding: g }: { grounding: Grounding }) {
  const [open, setOpen] = useState(false)

  if (g.refused) {
    return (
      <div className="mt-4 flex items-start gap-2.5 rounded-[var(--radius-card)] border border-border bg-sunken px-3.5 py-3">
        <ShieldOff className="mt-px size-4 shrink-0 text-faint" aria-hidden="true" />
        <p className="text-[13px] leading-[1.55] text-muted">
          Nothing in the documents matched closely enough to answer from.{' '}
          <span className="text-faint">
            Closest passage scored {g.best_semantic_score.toFixed(2)}, below the{' '}
            {g.relevance_threshold.toFixed(2)} minimum this assistant requires before answering.
          </span>
        </p>
      </div>
    )
  }

  const docs = `${g.cited_documents} document${g.cited_documents === 1 ? '' : 's'}`
  const excerpts = `${g.cited_chunks} excerpt${g.cited_chunks === 1 ? '' : 's'}`

  return (
    <div className="mt-4 rounded-[var(--radius-card)] border border-border bg-sunken">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left transition-colors duration-150 hover:bg-hover"
      >
        <ShieldCheck className="size-4 shrink-0 text-success" aria-hidden="true" />
        <span className="min-w-0 flex-1 text-[13px] text-muted">
          Answered from <span className="font-medium text-ink">{docs}</span>, {excerpts}
        </span>
        <span className="shrink-0 text-[12px] text-faint">Why this answer?</span>
        <ChevronDown
          className={cn(
            'size-3.5 shrink-0 text-faint transition-transform duration-200 ease-out',
            open && 'rotate-180',
          )}
          aria-hidden="true"
        />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease }}
          >
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 border-t border-border px-3.5 py-3 text-[12.5px]">
              <Row label="Documents cited">{g.cited_documents}</Row>
              {/* Cited AND retrieved together: an answer using 2 of 14 passages
                  is a different thing from one using 9 of 14, and only showing
                  the numerator hides that. */}
              <Row label="Excerpts used">
                {g.cited_chunks} of {g.retrieved_chunks} retrieved
              </Row>
              <Row label="Closest match">
                {g.best_semantic_score.toFixed(2)}{' '}
                <span className="text-faint">
                  (minimum {g.relevance_threshold.toFixed(2)} to answer at all)
                </span>
              </Row>
            </dl>
            <p className="border-t border-border px-3.5 py-2.5 text-[11.5px] leading-[1.5] text-faint">
              Match scores measure text similarity, not correctness. This assistant does not
              score its own accuracy — check the cited pages for anything that matters.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="whitespace-nowrap text-faint">{label}</dt>
      <dd className="text-muted">{children}</dd>
    </>
  )
}
