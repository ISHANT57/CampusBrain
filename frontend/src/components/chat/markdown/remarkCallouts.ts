/* GitHub alert syntax -> callout boxes.

       > [!NOTE]
       > Applications close on 31 March.

   Markdown has no callout primitive, so something has to define the syntax.
   Using GitHub's spelling rather than inventing one means the raw answer text
   still reads correctly anywhere markdown is rendered without this plugin
   (GitHub, an editor preview, a copy-paste into a doc) — it degrades to a
   normal blockquote instead of leaking a made-up token.

   Only top-level blockquotes are considered: a callout nested inside a list
   item or another quote is not a shape the answer prompt asks for, and
   matching it would mean guessing at intent. */

type MdNode = {
  type: string
  value?: string
  children?: MdNode[]
  data?: { hName?: string; hProperties?: Record<string, unknown> }
}

/* Mapped to the four semantic colours the theme already defines, not to a new
   palette. CAUTION folds into warning and TIP into success on purpose —
   distinct colours for near-identical severities is noise, and the theme has
   no fifth semantic ramp to spend on it. */
const KINDS: Record<string, string> = {
  NOTE: 'note',
  IMPORTANT: 'important',
  WARNING: 'warning',
  CAUTION: 'warning',
  TIP: 'success',
  SUCCESS: 'success',
}

const LEAD = /^\[!(\w+)\][ \t]*\n?/

export function remarkCallouts() {
  return (tree: MdNode) => {
    for (const node of tree.children ?? []) {
      if (node.type !== 'blockquote') continue

      const firstBlock = node.children?.[0]
      if (firstBlock?.type !== 'paragraph') continue

      const lead = firstBlock.children?.[0]
      if (lead?.type !== 'text' || typeof lead.value !== 'string') continue

      const m = lead.value.match(LEAD)
      if (!m) continue

      const kind = KINDS[m[1].toUpperCase()]
      if (!kind) continue

      lead.value = lead.value.slice(m[0].length)

      /* The marker was the paragraph's entire first line. If nothing is left
         of that text node, drop it — and if it was the paragraph's only
         child, drop the paragraph too, or the callout renders with a blank
         line above its content. */
      if (!lead.value) {
        firstBlock.children?.shift()
        if (firstBlock.children?.length === 0) node.children?.shift()
      }

      node.data = {
        ...node.data,
        hName: 'div',
        hProperties: { 'data-callout': kind },
      }
    }
  }
}
