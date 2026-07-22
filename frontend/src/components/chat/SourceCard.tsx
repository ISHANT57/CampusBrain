import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown, FileText, Search } from 'lucide-react'
import { Skeleton } from './ui/primitives'
import { cn } from './lib/utils'
import type { Citation } from './types'

const ease = [0.16, 1, 0.3, 1] as const

/* Sources rail — arrives with the first token, the order Perplexity uses.
   These are uploaded documents, not web pages, so a card expands its excerpt
   in place rather than linking out. */
export function SourceRail({ citations, loading }: { citations: Citation[]; loading: boolean }) {
  const [openIdx, setOpenIdx] = useState<number | null>(null)

  if (!loading && citations.length === 0) return null

  return (
    <section className="mb-6" aria-label="Sources">
      <div className="mb-3 flex items-center gap-2">
        <Search className="size-3.5 text-faint" aria-hidden="true" />
        <span className="eyebrow">
          {loading ? 'Searching documents' : `${citations.length} source${citations.length === 1 ? '' : 's'}`}
        </span>
      </div>

      {loading ? (
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
          {citations.map((c, i) => (
            <SourceCard
              key={c.index}
              citation={c}
              open={openIdx === c.index}
              onToggle={() => setOpenIdx(openIdx === c.index ? null : c.index)}
              delay={i * 0.04}
            />
          ))}
        </div>
      )}
    </section>
  )
}

function SourceCard({
  citation: c,
  open,
  onToggle,
  delay,
}: {
  citation: Citation
  open: boolean
  onToggle: () => void
  delay: number
}) {
  return (
    <motion.div
      id={`source-${c.index}`}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.24, ease }}
      className={cn(
        'overflow-hidden rounded-[var(--radius-card)] border bg-surface transition-[border-color,box-shadow] duration-150',
        open ? 'border-accent-border shadow-[var(--shadow-card)]' : 'border-border hover:border-border-strong',
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="group/src flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors duration-150 hover:bg-hover"
      >
        <span
          className={cn(
            'flex size-6 shrink-0 items-center justify-center rounded-[7px] border font-mono text-[10.5px] font-medium transition-colors duration-150',
            open
              ? 'border-accent-border bg-accent text-accent-fg'
              : 'border-border bg-sunken text-muted group-hover/src:border-accent-border group-hover/src:text-accent',
          )}
        >
          {c.index}
        </span>

        <FileText className="size-4 shrink-0 text-faint" aria-hidden="true" />

        <span className="min-w-0 flex-1 truncate text-[13.5px] text-ink">{c.filename}</span>

        <span className="shrink-0 rounded-full border border-border bg-sunken px-2 py-0.5 font-mono text-[10.5px] text-muted">
          p.{c.page_number}
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
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease }}
          >
            {/* Excerpt is verbatim source text — the left rule marks it as a
                quotation rather than the assistant's own prose. */}
            <div className="border-t border-border px-4 py-4">
              <p className="border-l-2 border-accent-border pl-3 text-[13.5px] leading-[1.65] text-muted">
                {c.excerpt}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
