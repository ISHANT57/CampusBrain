import { memo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, ChevronDown, Copy, FileText, RotateCcw, Search } from 'lucide-react'
import { Button } from './ui/button'
import { Alert, Skeleton, Tooltip } from './ui/primitives'
import { cn } from './lib/utils'
import type { ChatMessage, Citation } from './types'

const ease = [0.16, 1, 0.3, 1] as const

/* Inline markdown-lite: **bold**, *italic*, `code`, and [n] citation
   markers — the four constructs the backend prompt actually produces.
   A full markdown parser would be overkill for that. */
const INLINE = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`|\[\d+\])/g

function Inline({ text, citations }: { text: string; citations?: Citation[] }) {
  return (
    <>
      {text.split(INLINE).map((part, i) => {
        if (!part) return null
        if (part.startsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>
        if (part.startsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>
        if (part.startsWith('*')) return <em key={i}>{part.slice(1, -1)}</em>
        const m = part.match(/^\[(\d+)\]$/)
        if (m) {
          const n = Number(m[1])
          const src = citations?.find((c) => c.index === n)
          if (!src) return null
          return <CitationChip key={i} src={src} />
        }
        return <span key={i}>{part}</span>
      })}
    </>
  )
}

function CitationChip({ src }: { src: Citation }) {
  return (
    <Tooltip
      side="top"
      label={
        <span className="max-w-[240px] truncate text-left">
          {src.filename} · p.{src.page_number}
        </span>
      }
      className="align-baseline"
    >
      <a
        href={`#source-${src.index}`}
        aria-label={`Source ${src.index}: ${src.filename}, page ${src.page_number}`}
        className="mx-0.5 inline-flex h-[17px] min-w-[17px] translate-y-[-1px] items-center justify-center rounded-[5px] border border-border bg-sunken px-[5px] align-middle font-mono text-[10px] font-medium text-muted no-underline transition-colors hover:border-accent hover:bg-accent-soft hover:text-accent"
      >
        {src.index}
      </a>
    </Tooltip>
  )
}

function Blocks({ text, citations }: { text: string; citations?: Citation[] }) {
  return (
    <>
      {text.split('\n\n').map((block, bi) => {
        const lines = block.split('\n')
        if (lines[0].startsWith('- ')) {
          return (
            <ul key={bi}>
              {lines.map((l, li) => (
                <li key={li}>
                  <Inline text={l.replace(/^-\s*/, '')} citations={citations} />
                </li>
              ))}
            </ul>
          )
        }
        return (
          <p key={bi}>
            <Inline text={block} citations={citations} />
          </p>
        )
      })}
    </>
  )
}

/* Sources rail — arrives with the first token, same order Perplexity uses.
   These are uploaded PDFs, not web pages, so each card expands its excerpt
   in place instead of linking out. */
function SourceRail({ citations, loading }: { citations: Citation[]; loading: boolean }) {
  const [openIdx, setOpenIdx] = useState<number | null>(null)

  if (!loading && citations.length === 0) return null

  return (
    <div className="mb-5">
      <div className="mb-2 flex items-center gap-2">
        <Search className="size-3 text-faint" aria-hidden="true" />
        <span className="eyebrow">{loading ? 'Searching your documents' : `${citations.length} sources`}</span>
      </div>

      {loading ? (
        <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {[0, 1, 2].map((i) => (
            <div key={i} className="w-[190px] shrink-0 rounded-[10px] border border-border bg-surface p-2.5">
              <Skeleton className="h-2.5 w-3/4" />
              <Skeleton className="mt-2 h-2 w-1/2" />
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          {citations.map((c, i) => {
            const open = openIdx === c.index
            return (
              <motion.div
                key={c.index}
                id={`source-${c.index}`}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05, duration: 0.35, ease }}
                className="overflow-hidden rounded-[10px] border border-border bg-surface"
              >
                <button
                  type="button"
                  onClick={() => setOpenIdx(open ? null : c.index)}
                  aria-expanded={open}
                  className="flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors hover:bg-sunken"
                >
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-[5px] bg-sunken font-mono text-[10px] font-medium text-muted">
                    {c.index}
                  </span>
                  <FileText className="size-3.5 shrink-0 text-faint" />
                  <span className="min-w-0 flex-1 truncate text-[12.5px] text-ink">{c.filename}</span>
                  <span className="shrink-0 font-mono text-[10.5px] text-faint">p.{c.page_number}</span>
                  <ChevronDown
                    className={cn('size-3.5 shrink-0 text-faint transition-transform', open && 'rotate-180')}
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
                      <p className="border-t border-border px-3 py-2.5 text-[12.5px] leading-[1.55] text-muted">
                        “{c.excerpt}”
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function Actions({ text, onRetry }: { text: string; onRetry: () => void }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className="mt-4 flex items-center gap-1 opacity-70 transition-opacity focus-within:opacity-100 group-hover/msg:opacity-100">
      <Tooltip label={copied ? 'Copied' : 'Copy answer'}>
        <Button variant="ghost" size="icon-sm" onClick={copy} aria-label="Copy answer">
          <AnimatePresence initial={false} mode="wait">
            <motion.span
              key={copied ? 'y' : 'n'}
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.6, opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="flex"
            >
              {copied ? <Check className="text-accent" /> : <Copy />}
            </motion.span>
          </AnimatePresence>
        </Button>
      </Tooltip>
      <Tooltip label="Regenerate">
        <Button variant="ghost" size="icon-sm" onClick={onRetry} aria-label="Regenerate answer">
          <RotateCcw />
        </Button>
      </Tooltip>
    </div>
  )
}

export const Message = memo(function Message({
  message,
  onRetry,
}: {
  message: ChatMessage
  onRetry: () => void
}) {
  const { role, content, phase, citations = [] } = message

  if (role === 'user') {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease }}
        className="flex justify-end"
      >
        <div className="max-w-[85%] rounded-[16px] rounded-br-[6px] border border-border bg-sunken px-4 py-2.5 text-[15px] leading-[1.55] text-ink sm:max-w-[75%]">
          {content}
        </div>
      </motion.div>
    )
  }

  const searching = phase === 'searching'

  if (phase === 'error') {
    return (
      <Alert
        title={content || 'Something went wrong answering that.'}
        action={
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RotateCcw />
            Try again
          </Button>
        }
      />
    )
  }

  return (
    <div className="group/msg">
      <SourceRail citations={citations} loading={searching} />

      {searching ? (
        <div className="space-y-2.5" aria-hidden="true">
          <Skeleton className="h-3.5 w-[92%]" />
          <Skeleton className="h-3.5 w-[85%]" />
          <Skeleton className="h-3.5 w-[60%]" />
        </div>
      ) : (
        <div className="prose-answer text-ink" aria-live="polite" aria-busy={phase === 'revealing'}>
          <Blocks text={content} citations={citations} />
          {phase === 'revealing' && (
            <span className="ml-0.5 inline-block h-[1.05em] w-[2px] translate-y-[2px] animate-caret bg-accent align-baseline" />
          )}
        </div>
      )}

      {phase === 'stopped' && <p className="mt-3 text-[12px] text-faint">Stopped.</p>}

      {phase === 'done' && <Actions text={content} onRetry={onRetry} />}
    </div>
  )
})
