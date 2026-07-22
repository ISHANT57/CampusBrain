import { motion } from 'framer-motion'
import { Sparkles } from 'lucide-react'

const ease = [0.16, 1, 0.3, 1] as const

// Generic starter prompts — this is document QA for whatever an org has
// uploaded, not tied to any one institution's content.
const STARTERS = [
  'Summarize what this document collection covers',
  'What are the key dates or deadlines mentioned?',
  'Who is responsible for [a specific policy]?',
  'Explain [a specific term] the way the documents define it',
]

export function EmptyState({ onAsk }: { onAsk: (text: string) => void }) {
  return (
    <div className="mx-auto flex max-w-[640px] flex-col items-center px-5 pb-8 pt-[max(6vh,32px)] text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.85 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease }}
      >
        <Sparkles className="size-7 text-accent" />
      </motion.div>
      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05, duration: 0.5, ease }}
        className="mt-5 font-serif text-[26px] leading-[1.15] tracking-[-0.02em] text-ink sm:text-[30px]"
      >
        Ask about your institution's documents
      </motion.h1>
      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.5, ease }}
        className="mt-3 max-w-[440px] text-[14.5px] leading-[1.6] text-muted"
      >
        Answers are grounded in what's been uploaded and cite the page they came from.
      </motion.p>

      <div className="mt-8 flex w-full flex-col gap-2 text-left">
        {STARTERS.map((s, i) => (
          <motion.button
            key={s}
            type="button"
            onClick={() => onAsk(s)}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.14 + i * 0.04, duration: 0.4, ease }}
            className="rounded-[10px] border border-border bg-surface px-3.5 py-2.5 text-left text-[13.5px] text-ink transition-[border-color,background-color,transform] hover:-translate-y-px hover:border-border-strong hover:bg-sunken"
          >
            {s}
          </motion.button>
        ))}
      </div>
    </div>
  )
}
