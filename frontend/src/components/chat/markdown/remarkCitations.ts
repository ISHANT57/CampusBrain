/* Turns inline [n] citation markers into <sup data-cite="n"> elements.

   Why a remark plugin and not a regex over the rendered output, or a
   pre-pass that swaps [1] for real HTML:

   - A regex over rendered HTML cannot tell prose from code. An answer that
     quotes "results[1]" or a regex like [0-9] would have part of it turned
     into a footnote.
   - Pre-substituting HTML into the markdown string requires rehype-raw to
     render it, which enables arbitrary HTML from LLM output. That is an XSS
     surface on untrusted text. Not worth it for a superscript.

   Operating on the syntax tree means code spans and fenced blocks are simply
   different node types, so they're skipped structurally rather than by
   pattern-guessing. */

type MdNode = {
  type: string
  value?: string
  children?: MdNode[]
  data?: {
    hName?: string
    hProperties?: Record<string, unknown>
    hChildren?: MdNode[]
  }
}

const MARKER = /\[(\d+)\]/g

/* Node types whose text is verbatim and must never be rewritten. */
const OPAQUE = new Set(['code', 'inlineCode'])

function splitText(value: string): MdNode[] | null {
  const matches = [...value.matchAll(MARKER)]
  if (matches.length === 0) return null

  const out: MdNode[] = []
  let cursor = 0

  for (const m of matches) {
    const at = m.index ?? 0
    if (at > cursor) out.push({ type: 'text', value: value.slice(cursor, at) })

    const n = Number(m[1])
    /* hName/hChildren is mdast-util-to-hast's documented escape hatch: it
       promotes this text node to a real <sup> element during the mdast ->
       hast conversion. hChildren is required — without it applyData()
       creates the element with an empty child list and the number vanishes. */
    out.push({
      type: 'text',
      value: String(n),
      data: {
        hName: 'sup',
        hProperties: { 'data-cite': String(n) },
        hChildren: [{ type: 'text', value: String(n) }],
      },
    })
    cursor = at + m[0].length
  }

  if (cursor < value.length) out.push({ type: 'text', value: value.slice(cursor) })
  return out
}

function transform(node: MdNode): void {
  const children = node.children
  if (!children) return

  const next: MdNode[] = []
  let changed = false

  for (const child of children) {
    if (child.type === 'text' && typeof child.value === 'string') {
      const parts = splitText(child.value)
      if (parts) {
        next.push(...parts)
        changed = true
        continue
      }
      next.push(child)
      continue
    }
    if (!OPAQUE.has(child.type)) transform(child)
    next.push(child)
  }

  if (changed) node.children = next
}

export function remarkCitations() {
  return (tree: MdNode) => {
    transform(tree)
  }
}
