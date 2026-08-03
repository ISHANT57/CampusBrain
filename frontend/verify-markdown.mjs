/* Runnable check for the two remark plugins.
   Asserts against the hast tree react-markdown actually consumes, so a
   regression in citation conversion or callout detection fails here instead
   of silently in the browser.

   Run from frontend/:  node verify-markdown.mjs
   (Node >= 23 strips the .ts types natively; no build step, no test framework.) */
import { unified } from 'unified'
import remarkParse from 'remark-parse'
import remarkGfm from 'remark-gfm'
import remarkRehype from 'remark-rehype'

import { remarkCitations } from './src/components/chat/markdown/remarkCitations.ts'
import { remarkCallouts } from './src/components/chat/markdown/remarkCallouts.ts'

const proc = unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkCallouts)
  .use(remarkCitations)
  .use(remarkRehype)

const hast = (md) => proc.runSync(proc.parse(md))

const text = (n) =>
  n.type === 'text' ? n.value : (n.children ?? []).map(text).join('')

const all = (n, pred, acc = []) => {
  if (pred(n)) acc.push(n)
  for (const c of n.children ?? []) all(c, pred, acc)
  return acc
}

const tag = (n, name) => all(n, (x) => x.type === 'element' && x.tagName === name)
const cites = (n) => tag(n, 'sup').map((s) => s.properties?.['data-cite'] ?? s.properties?.dataCite)

let failed = 0
function check(label, md, assertion) {
  let ok = false
  let detail = ''
  try {
    const tree = hast(md)
    ok = assertion(tree)
    if (!ok) detail = JSON.stringify(tree.children?.[0] ?? tree, null, 1).slice(0, 400)
  } catch (e) {
    detail = `threw: ${e.message}`
  }
  console.log(`${ok ? 'ok   ' : 'FAIL '} ${label}`)
  if (!ok) {
    failed++
    if (detail) console.log(`       ${detail.replace(/\n/g, '\n       ')}`)
  }
}

// --- citations ------------------------------------------------------------
check(
  'inline [1] becomes <sup data-cite="1">1</sup>',
  'Students above 7.5 CGPA receive support [1].',
  (t) => {
    const s = tag(t, 'sup')
    return s.length === 1 && text(s[0]) === '1' && cites(t)[0] === '1'
  },
)

check('two markers in one sentence', 'Both apply [1][2].', (t) => {
  const c = cites(t)
  return c.length === 2 && c[0] === '1' && c[1] === '2'
})

check('surrounding prose is preserved', 'Fees are waived [4] fully.', (t) =>
  text(t).includes('Fees are waived') && text(t).includes('fully'),
)

check('marker inside INLINE CODE is left alone', 'Use `results[1]` to index.', (t) =>
  tag(t, 'sup').length === 0 && text(t).includes('results[1]'),
)

check('marker inside FENCED CODE is left alone', '```\nvalues[1] = 2\n```', (t) =>
  tag(t, 'sup').length === 0 && text(t).includes('values[1]'),
)

check('marker inside a list item converts', '- Eligible students [3]', (t) => cites(t)[0] === '3')

check('marker inside bold converts', '**Important [2]**', (t) => cites(t)[0] === '2')

check('marker inside a table cell converts', '| a | b |\n|---|---|\n| x [5] | y |', (t) =>
  cites(t)[0] === '5' && tag(t, 'table').length === 1,
)

// --- callouts ------------------------------------------------------------
check('> [!NOTE] becomes a note callout', '> [!NOTE]\n> Closes 31 March.', (t) => {
  const d = all(t, (x) => x.properties?.['data-callout'] === 'note')
  return d.length === 1 && text(d[0]).includes('Closes 31 March')
})

check('> [!WARNING] maps to warning', '> [!WARNING]\n> Late fees apply.', (t) =>
  all(t, (x) => x.properties?.['data-callout'] === 'warning').length === 1,
)

check('> [!CAUTION] folds into warning', '> [!CAUTION]\n> Careful.', (t) =>
  all(t, (x) => x.properties?.['data-callout'] === 'warning').length === 1,
)

check('> [!TIP] folds into success', '> [!TIP]\n> Apply early.', (t) =>
  all(t, (x) => x.properties?.['data-callout'] === 'success').length === 1,
)

check('callout marker text is stripped from the body', '> [!NOTE]\n> Body only.', (t) => {
  const d = all(t, (x) => x.properties?.['data-callout'] === 'note')[0]
  return d && !text(d).includes('[!NOTE]')
})

check('a plain blockquote stays a blockquote', '> Just a quote.', (t) =>
  tag(t, 'blockquote').length === 1 && all(t, (x) => x.properties?.['data-callout']).length === 0,
)

check('unknown alert kind stays a blockquote', '> [!BOGUS]\n> hm.', (t) =>
  tag(t, 'blockquote').length === 1 && all(t, (x) => x.properties?.['data-callout']).length === 0,
)

check('citations work INSIDE a callout', '> [!NOTE]\n> See the handbook [2].', (t) =>
  all(t, (x) => x.properties?.['data-callout'] === 'note').length === 1 && cites(t)[0] === '2',
)

// --- gfm passthrough -----------------------------------------------------
check('task list renders checkboxes', '- [ ] one\n- [x] two', (t) => tag(t, 'input').length === 2)
check('strikethrough renders', '~~gone~~', (t) => tag(t, 'del').length === 1)

console.log(failed === 0 ? '\nALL PASS' : `\n${failed} FAILURE(S)`)
process.exit(failed === 0 ? 0 : 1)
