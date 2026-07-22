import { memo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, Copy, RotateCcw } from 'lucide-react'
import { Button } from './ui/button'
import { AnswerSkeleton, Avatar, ErrorCard, Tooltip } from './ui/primitives'
import { SourceRail } from './SourceCard'
import { cn } from './lib/utils'
import type { ChatMessage, Citation } from './types'

const ease = [0.16, 1, 0.3, 1] as const

/* Inline markdown-lite: **bold**, *italic*, `code`, and [n] citation markers
   — the constructs the backend prompt actually produces. A full markdown
   parser would be overkill for that. */
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
        <span className="block max-w-[240px] truncate text-left">
          {src.filename} · p.{src.page_number}
        </span>
      }
      className="align-baseline"
    >
      <a
        href={`#source-${src.index}`}
        aria-label={`Source ${src.index}: ${src.filename}, page ${src.page_number}`}
        /* Left margin only. A right margin left a visible gap before the
           punctuation that almost always follows a citation ("… student 1 ."). */
        className="ml-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-px items-center justify-center rounded-[6px] border border-border bg-sunken px-[5px] align-middle font-mono text-[10px] font-medium text-muted no-underline transition-colors duration-150 hover:border-accent-border hover:bg-accent-soft hover:text-accent"
      >
        {src.index}
      </a>
    </Tooltip>
  )
}

const BULLET = /^\s*[-*]\s+/
const NUMBERED = /^\s*\d+[.)]\s+/
const MARKER = /^\s*(?:[-*]|\d+[.)])\s+/

type Run = { kind: 'p' | 'ul' | 'ol'; lines: string[] }

/* Splits one block into consecutive runs of the same kind, so a paragraph and
   the list that follows it inside the same block each render correctly. */
function groupLines(block: string): Run[] {
  const runs: Run[] = []
  for (const line of block.split('\n')) {
    if (!line.trim()) continue
    const kind: Run['kind'] = BULLET.test(line) ? 'ul' : NUMBERED.test(line) ? 'ol' : 'p'
    const last = runs[runs.length - 1]
    if (last && last.kind === kind) last.lines.push(line)
    else runs.push({ kind, lines: [line] })
  }
  return runs
}

function Blocks({ text, citations }: { text: string; citations?: Citation[] }) {
  // Split on fenced code first so a ``` block's blank lines don't get chopped
  // into separate paragraphs by the double-newline split below.
  const segments = text.split(/(```[\s\S]*?```)/g)

  return (
    <>
      {segments.map((segment, si) => {
        if (!segment) return null

        if (segment.startsWith('```')) {
          const body = segment.replace(/^```[^\n]*\n?/, '').replace(/```$/, '')
          return (
            <pre key={si}>
              <code>{body.replace(/\n$/, '')}</code>
            </pre>
          )
        }

        return segment.split('\n\n').map((block, bi) =>
          // Group consecutive lines by kind rather than typing the whole block
          // from its first line: models routinely emit a lead-in sentence
          // followed by bullets in one block ("What it covers:\n- …"), which
          // first-line detection rendered as one run-on paragraph with the
          // dashes left inline.
          groupLines(block).map((run, ri) => {
            const key = `${si}-${bi}-${ri}`
            if (run.kind === 'p') {
              return (
                <p key={key}>
                  <Inline text={run.lines.join(' ')} citations={citations} />
                </p>
              )
            }
            const List = run.kind === 'ul' ? 'ul' : 'ol'
            return (
              <List key={key}>
                {run.lines.map((l, li) => (
                  <li key={li}>
                    <Inline text={l.replace(MARKER, '')} citations={citations} />
                  </li>
                ))}
              </List>
            )
          }),
        )
      })}
    </>
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
    <div className="-ml-2 mt-4 flex items-center gap-1 opacity-0 transition-opacity duration-150 focus-within:opacity-100 group-hover/msg:opacity-100 max-md:opacity-100">
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
              {copied ? <Check className="text-success" /> : <Copy />}
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

/* One row shape for both roles — avatar gutter, name, then content. Keeping
   the gutter identical is what makes a thread read as one continuous
   conversation instead of alternating left/right islands. */
function Turn({ kind, name, children }: { kind: 'user' | 'assistant'; name: string; children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease }}
      className="group/msg flex gap-4"
    >
      <Avatar kind={kind} />
      <div className="min-w-0 flex-1 pt-1">
        <p className="mb-2 text-[13px] font-semibold tracking-[-0.005em] text-ink">{name}</p>
        {children}
      </div>
    </motion.div>
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
      <Turn kind="user" name="You">
        <div className="w-fit max-w-full rounded-[var(--radius-card)] rounded-tl-[4px] border border-border bg-sunken px-4 py-2.5 text-[15px] leading-[1.6] text-ink">
          {content}
        </div>
      </Turn>
    )
  }

  if (phase === 'error') {
    return (
      <Turn kind="assistant" name="Ask Sitare">
        <ErrorCard
          title="That answer didn't come through"
          description={content || 'Something went wrong reaching the assistant.'}
          action={
            <Button variant="outline" size="sm" onClick={onRetry}>
              <RotateCcw />
              Try again
            </Button>
          }
        />
      </Turn>
    )
  }

  const searching = phase === 'searching'

  return (
    <Turn kind="assistant" name="Ask Sitare">
      <SourceRail citations={citations} loading={searching} />

      {searching ? (
        <AnswerSkeleton />
      ) : (
        <div className="prose-answer" aria-live="polite" aria-busy={phase === 'revealing'}>
          <Blocks text={content} citations={citations} />
          {phase === 'revealing' && (
            <span
              className="ml-0.5 inline-block h-[1.05em] w-[2px] translate-y-[2px] animate-caret bg-accent align-baseline"
              aria-hidden="true"
            />
          )}
        </div>
      )}

      {phase === 'stopped' && (
        <p className="mt-3 text-[12.5px] text-faint">Stopped generating.</p>
      )}

      {phase === 'done' && <Actions text={content} onRetry={onRetry} />}
    </Turn>
  )
})
