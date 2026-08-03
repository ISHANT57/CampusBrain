import { memo, useCallback, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, Copy, RotateCcw } from 'lucide-react'
import { Button } from './ui/button'
import { AnswerSkeleton, Avatar, ErrorCard, Tooltip } from './ui/primitives'
import { SourceRail } from './SourceCard'
import { AnswerBody } from './AnswerBody'
import { GroundingBar } from './GroundingBar'
import type { ChatMessage, MessagePhase } from './types'

const ease = [0.16, 1, 0.3, 1] as const

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

/* Screen-reader status, and the reason it is a separate node from the answer.

   aria-live used to sit on the answer container itself. That container's text
   grows with every streamed token, so assistive tech was asked to re-announce
   a continuously changing region hundreds of times per answer — which in
   practice means the whole answer read from the top, repeatedly. A live
   region has to carry something SHORT that changes at MEANINGFUL moments, so
   it carries the phase and nothing else. The prose is left un-live and is
   read normally, on demand, once it has settled. */
const STATUS: Partial<Record<MessagePhase, string>> = {
  searching: 'Searching documents',
  revealing: 'Generating answer',
  done: 'Answer complete',
  stopped: 'Generation stopped',
}

function StreamStatus({ phase }: { phase?: MessagePhase }) {
  const label = phase ? STATUS[phase] : undefined
  return (
    <>
      <p role="status" aria-live="polite" className="sr-only">
        {label}
      </p>
      {phase === 'revealing' && (
        <p className="mb-2 flex items-center gap-2 text-[12.5px] text-faint" aria-hidden="true">
          <span className="size-1.5 animate-shimmer rounded-full bg-accent" />
          Generating answer
        </p>
      )}
    </>
  )
}

/* One row shape for both roles — avatar gutter, name, then content. Keeping
   the gutter identical is what makes a thread read as one continuous
   conversation instead of alternating left/right islands. */
function Turn({
  kind,
  name,
  children,
}: {
  kind: 'user' | 'assistant'
  name: string
  children: React.ReactNode
}) {
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
  brand,
  onRetry,
}: {
  message: ChatMessage
  /** Tenant's assistant name, shown above every answer. */
  brand: string
  onRetry: () => void
}) {
  const { role, content, phase, citations = [], retrieved = [], grounding } = message

  /* seq, not a bare number: clicking the SAME marker twice has to re-scroll
     and re-highlight. With plain state the second click is a no-op because
     the value didn't change, so the effect in SourceRail never reruns and the
     card appears unresponsive. A counter makes every click a distinct value. */
  const [activeCite, setActiveCite] = useState<{ n: number; seq: number } | null>(null)
  const onCite = useCallback((n: number) => {
    setActiveCite((prev) => ({ n, seq: (prev?.seq ?? 0) + 1 }))
  }, [])

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
      <Turn kind="assistant" name={brand}>
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
  // Citations only exist once the final "done" event arrives (see useChat's
  // send()) — real streaming means text can already be revealing while the
  // source list is still empty. Keep the rail's skeleton up across that gap
  // instead of it disappearing after "searching" and popping back in at the
  // end, which reads as broken rather than as "still resolving".
  //
  // Since P2-2 the gap is usually filled by the "retrieved" event instead of a
  // skeleton, so this only covers the window before retrieval returns — or a
  // backend too old to send that event, which still degrades to the old
  // skeleton-until-done behaviour rather than showing an empty rail.
  const sourcesLoading = searching || (phase === 'revealing' && citations.length === 0)

  return (
    <Turn kind="assistant" name={brand}>
      <StreamStatus phase={phase} />

      <SourceRail
        citations={citations}
        retrieved={retrieved}
        loading={sourcesLoading}
        activeCite={activeCite}
      />

      {searching ? (
        <AnswerSkeleton />
      ) : (
        <div className="prose-answer">
          <AnswerBody
            text={content}
            citations={citations}
            activeCite={activeCite?.n ?? null}
            onCite={onCite}
          />
          {phase === 'revealing' && (
            <span
              className="ml-0.5 inline-block h-[1.05em] w-[2px] translate-y-[2px] animate-caret bg-accent align-baseline"
              aria-hidden="true"
            />
          )}
        </div>
      )}

      {phase === 'stopped' && <p className="mt-3 text-[12.5px] text-faint">Stopped generating.</p>}

      {/* Only on a completed answer, and only when the backend actually sent
          grounding. A stopped or interrupted answer has no settled basis to
          report, and an older backend sends none — in both cases the honest
          thing is to show nothing rather than a placeholder. */}
      {phase === 'done' && grounding && <GroundingBar grounding={grounding} />}

      {phase === 'done' && <Actions text={content} onRetry={onRetry} />}
    </Turn>
  )
})
