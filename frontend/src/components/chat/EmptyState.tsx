import { motion } from 'framer-motion'
import { ArrowUpRight } from 'lucide-react'
import { StarMark } from './Logo'
import type { Org } from '../../orgs'

const ease = [0.16, 1, 0.3, 1] as const

// Copy and suggestions come from src/orgs.ts. They were written against what
// is actually in each knowledge base, so a first-time visitor's first click
// returns a real cited answer instead of "I don't have information on that" —
// which means they have to move whenever a tenant's corpus does.
export function EmptyState({ org, onAsk }: { org: Org; onAsk: (text: string) => void }) {
  return (
    <div className="mx-auto flex w-full max-w-[820px] flex-col items-center px-5 pb-10 pt-[max(6vh,40px)] text-center sm:px-8">
      <motion.span
        initial={{ opacity: 0, scale: 0.85 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.32, ease }}
        className="flex size-12 items-center justify-center rounded-[14px] bg-accent text-accent-fg shadow-[var(--shadow-card)]"
      >
        <StarMark className="size-6" />
      </motion.span>

      <motion.h2
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.04, duration: 0.32, ease }}
        className="mt-6 text-balance text-[28px] font-[650] leading-[1.2] tracking-[-0.025em] text-ink sm:text-[32px]"
      >
        Every question about {org.short},
        {/* Only break the line once there's room for it to read as two
            deliberate lines; on narrow screens it wraps naturally instead. */}
        <br className="hidden sm:inline" /> answered with its sources.
      </motion.h2>

      <motion.p
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08, duration: 0.32, ease }}
        className="mt-3 max-w-[560px] text-[15px] leading-[1.6] text-muted"
      >
        {org.blurb}
      </motion.p>

      <div className="mt-10 grid w-full gap-2 text-left sm:grid-cols-2">
        {org.suggestions.map((s, i) => (
          <motion.button
            key={s.label}
            type="button"
            onClick={() => onAsk(s.label)}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.12 + i * 0.03, duration: 0.28, ease }}
            className="group flex items-center gap-3 rounded-[var(--radius-card)] border border-border bg-surface p-4 text-left transition-[border-color,background-color,box-shadow] duration-150 hover:border-accent-border hover:bg-hover hover:shadow-[var(--shadow-card)]"
          >
            <span className="flex size-9 shrink-0 items-center justify-center rounded-[10px] bg-sunken text-faint transition-colors duration-150 group-hover:bg-accent-soft group-hover:text-accent">
              <s.icon className="size-4" />
            </span>
            <span className="min-w-0 flex-1">
              {/* Wraps to a second line rather than truncating — these are
                  full questions, and a clipped question can't be read. */}
              <span className="block text-[13.5px] font-medium leading-[1.4] text-balance text-ink">
                {s.label}
              </span>
              <span className="eyebrow mt-1 block">{s.hint}</span>
            </span>
            <ArrowUpRight
              className="size-4 shrink-0 text-faint opacity-0 transition-opacity duration-150 group-hover:opacity-100"
              aria-hidden="true"
            />
          </motion.button>
        ))}
      </div>
    </div>
  )
}
