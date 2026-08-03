import { createContext, memo, useContext, useMemo } from 'react'
import Markdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { AlertTriangle, CheckCircle2, Info, Megaphone } from 'lucide-react'
import { remarkCitations } from './markdown/remarkCitations'
import { remarkCallouts } from './markdown/remarkCallouts'
import type { Citation } from './types'

/* Module-level constants, not inline literals: react-markdown re-runs the
   whole parse when `remarkPlugins` or `components` change identity, so
   defining these in the render body would re-parse the answer on every
   render — the exact cost this file is arranged to avoid. */
const PLUGINS = [remarkGfm, remarkCallouts, remarkCitations]

/* Two contexts rather than props, and this is the load-bearing decision in
   this file.

   Clicking a citation changes `activeCite`. If that were a prop on the
   markdown body, React would re-render it and react-markdown would re-parse
   the entire answer on every click — visible jank on a long answer. Passing
   it through context instead means the memoized <Body> never re-renders,
   while the handful of <sup> consumers inside it do. Context deliberately
   pierces memo; that's the mechanism being used, not a leak. */
const CiteData = createContext<{
  citations: Citation[]
  onCite: (n: number) => void
}>({ citations: [], onCite: () => {} })

const ActiveCite = createContext<number | null>(null)

function CitationRef({ n }: { n: number }) {
  const { citations, onCite } = useContext(CiteData)
  const active = useContext(ActiveCite) === n
  const src = citations.find((c) => c.index === n)

  /* No matching source. This happens legitimately mid-stream: the raw token
     stream carries the model's own marker numbers, and the backend only sends
     the renumbered set with the final "done" event. Rendering a marker with
     nothing behind it would show the user a reference to evidence that may
     not exist — so render nothing until the citation is real. */
  if (!src) return null

  return (
    <sup data-cite={n}>
      <button
        type="button"
        onClick={() => onCite(n)}
        data-active={active || undefined}
        aria-label={`Source ${n}: ${src.filename}, page ${src.page_number}. Show excerpt.`}
      >
        {n}
      </button>
    </sup>
  )
}

const CALLOUT_ICONS = {
  note: Info,
  important: Megaphone,
  warning: AlertTriangle,
  success: CheckCircle2,
} as const

type MdProps = { children?: React.ReactNode; node?: unknown } & Record<string, unknown>

/* <sup> in the tree can only have come from remarkCitations — markdown has no
   superscript syntax and raw HTML is disabled — but the guard keeps this
   component honest if that ever changes. */
function Sup({ node: _node, children, ...rest }: MdProps) {
  const n = Number(rest['data-cite'])
  if (!Number.isFinite(n)) return <sup {...rest}>{children}</sup>
  return <CitationRef n={n} />
}

function Div({ node: _node, children, ...rest }: MdProps) {
  const kind = rest['data-callout'] as keyof typeof CALLOUT_ICONS | undefined
  if (!kind || !CALLOUT_ICONS[kind]) return <div {...rest}>{children}</div>

  const Icon = CALLOUT_ICONS[kind]
  return (
    <div data-callout={kind} role="note">
      <Icon aria-hidden="true" />
      <div data-callout-body>{children}</div>
    </div>
  )
}

/* A wide table must scroll inside its own box — otherwise a fee table with
   six columns makes the entire conversation scroll sideways on a phone.
   tabIndex + role make that scroll container reachable by keyboard, which an
   overflow div otherwise is not. */
function Table({ node: _node, children, ...rest }: MdProps) {
  return (
    <div data-table-scroll tabIndex={0} role="region" aria-label="Table">
      <table {...rest}>{children}</table>
    </div>
  )
}

/* react-markdown already refuses javascript:/data: URLs via its default
   urlTransform, so this only adds the target/rel hardening. */
function Link({ node: _node, children, ...rest }: MdProps) {
  return (
    <a {...rest} target="_blank" rel="noopener noreferrer nofollow">
      {children}
    </a>
  )
}

const COMPONENTS = { sup: Sup, div: Div, table: Table, a: Link } as Components

/* Depends on `text` alone. Everything interactive arrives by context, so a
   completed answer is parsed exactly once no matter how many times the user
   clicks its citations.

   Partial markdown during streaming is fine and needs no special handling:
   an unclosed ** renders as literal asterisks for one frame and resolves
   itself on the next token. */
const Body = memo(function Body({ text }: { text: string }) {
  return (
    <Markdown remarkPlugins={PLUGINS} components={COMPONENTS}>
      {text}
    </Markdown>
  )
})

export function AnswerBody({
  text,
  citations,
  activeCite,
  onCite,
}: {
  text: string
  citations: Citation[]
  activeCite: number | null
  onCite: (n: number) => void
}) {
  const data = useMemo(() => ({ citations, onCite }), [citations, onCite])
  return (
    <CiteData.Provider value={data}>
      <ActiveCite.Provider value={activeCite}>
        <Body text={text} />
      </ActiveCite.Provider>
    </CiteData.Provider>
  )
}
