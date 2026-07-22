import { motion } from 'framer-motion'
import {
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
    <div className="mx-auto flex max-w-[720px] flex-col items-center px-5 pb-8 pt-[max(8vh,48px)] text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.85 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease }}
      >
        <StarMark className="size-7 text-accent" />
      </motion.div>

      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05, duration: 0.5, ease }}
        className="mt-5 font-serif text-[30px] leading-[1.15] tracking-[-0.02em] text-ink sm:text-[34px]"
      >
        What would you like to know?
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.5, ease }}
        className="mt-3 max-w-[440px] text-[15px] leading-[1.6] text-muted"
      >
        Ask about admissions, the scholarship, coursework, or life on campus. Every answer cites its
        sources.
      </motion.p>

      <div className="mt-9 grid w-full gap-2 text-left sm:grid-cols-2">
        {SUGGESTIONS.map((s, i) => (
          <motion.button
            key={s.label}
            type="button"
            onClick={() => onAsk(s.label)}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.14 + i * 0.04, duration: 0.45, ease }}
            className="group flex items-start gap-3 rounded-[12px] border border-border bg-surface p-3.5 text-left transition-[border-color,background-color,transform] hover:-translate-y-px hover:border-border-strong hover:bg-sunken"
          >
            <s.icon className="mt-px size-4 shrink-0 text-faint transition-colors group-hover:text-accent" />
            <span className="min-w-0">
              <span className="block text-[13.5px] leading-[1.45] text-ink">{s.label}</span>
              <span className="mt-1 block font-mono text-[10.5px] uppercase tracking-[0.08em] text-faint">
                {s.hint}
              </span>
            </span>
          </motion.button>
        ))}
      </div>
    </div>
  )
}
