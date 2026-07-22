import { motion } from 'framer-motion'
import {
  ArrowUpRight,
  Briefcase,
  ClipboardCheck,
  GraduationCap,
  MapPin,
  Sparkles,
  Wallet,
  type LucideIcon,
} from 'lucide-react'
import { StarMark } from './Logo'

const ease = [0.16, 1, 0.3, 1] as const

// Written against what's actually in the knowledge base (the Sitare corpus
// loaded via tools/ingest.py), so a first-time visitor's first click returns
// a real cited answer instead of "I don't have information on that".
const SUGGESTIONS: { icon: LucideIcon; label: string; hint: string }[] = [
  { icon: ClipboardCheck, label: 'How do I apply to Sitare University?', hint: 'Admissions' },
  { icon: Wallet, label: 'What does the full scholarship cover?', hint: 'Fees' },
  { icon: GraduationCap, label: 'Walk me through the four-year curriculum', hint: 'Academics' },
  { icon: MapPin, label: 'What is campus life like in Lucknow?', hint: 'Campus' },
  { icon: Briefcase, label: 'What happens after graduation?', hint: 'Careers' },
  { icon: Sparkles, label: 'Why was Sitare University founded?', hint: 'About' },
]

export function EmptyState({ onAsk }: { onAsk: (text: string) => void }) {
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
        className="mt-6 text-[28px] font-[650] leading-[1.2] tracking-[-0.025em] text-ink sm:text-[32px]"
      >
        What would you like to know?
      </motion.h2>

      <motion.p
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08, duration: 0.32, ease }}
        className="mt-3 max-w-[460px] text-[15px] leading-[1.6] text-muted"
      >
        Ask about admissions, the scholarship, coursework, or life on campus. Every answer cites its
        sources.
      </motion.p>

      <div className="mt-10 grid w-full gap-2 text-left sm:grid-cols-2">
        {SUGGESTIONS.map((s, i) => (
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
