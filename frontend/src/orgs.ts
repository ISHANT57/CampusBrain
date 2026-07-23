import {
  Briefcase,
  ClipboardCheck,
  GraduationCap,
  MapPin,
  Sparkles,
  Wallet,
  Building2,
  FileText,
  HelpCircle,
  type LucideIcon,
} from 'lucide-react'

/* Every tenant the public chatbot serves.
 *
 * The slug is the URL segment AND the organizations.slug column the backend
 * looks up — they have to match, or the route resolves to a 404 from
 * /api/v1/chat/<slug>. Adding a college is a row in that table plus an entry
 * here; no other file needs to change.
 *
 * Corpora never mix: a visitor on /goqii reaches org 2's Qdrant collection
 * only, because the backend derives org_id from this slug and every retrieval
 * query is scoped to it.
 */
export type Suggestion = { icon: LucideIcon; label: string; hint: string }

export type Org = {
  slug: string
  /** Full legal-ish name, used in sentences: "…about Sitare University". */
  name: string
  /** Brand name in the logo and as the assistant's name on each answer. */
  brand: string
  /** Short form for the empty-state headline: "Every question about X". */
  short: string
  /** One line under the conversation title. */
  subtitle: string
  /** Sub-headline on the welcome screen. */
  blurb: string
  suggestions: Suggestion[]
}

export const ORGS: Record<string, Org> = {
  sitare: {
    slug: 'sitare',
    name: 'Sitare University',
    brand: 'Ask Sitare',
    short: 'Sitare',
    subtitle: 'Grounded in Sitare University documents',
    blurb:
      'Admissions, the full scholarship, curriculum, campus life. Ask in plain language and get a cited answer in seconds — not a PDF hunt.',
    // Written against what's actually in the knowledge base (the Sitare corpus
    // loaded via tools/ingest.py), so a first-time visitor's first click
    // returns a real cited answer instead of "I don't have information".
    suggestions: [
      { icon: ClipboardCheck, label: 'How do I apply to Sitare University?', hint: 'Admissions' },
      { icon: Wallet, label: 'What does the full scholarship cover?', hint: 'Fees' },
      { icon: GraduationCap, label: 'Walk me through the four-year curriculum', hint: 'Academics' },
      { icon: MapPin, label: 'What is campus life like in Lucknow?', hint: 'Campus' },
      { icon: Briefcase, label: 'What happens after graduation?', hint: 'Careers' },
      { icon: Sparkles, label: 'Why was Sitare University founded?', hint: 'About' },
    ],
  },
  goqii: {
    slug: 'goqii',
    name: 'Goqii Technologies',
    brand: 'Ask Goqii',
    short: 'Goqii',
    subtitle: 'Grounded in Goqii Technologies documents',
    blurb:
      'Ask in plain language and get an answer with the document and page it came from.',
    // Deliberately generic: org 2 has no documents indexed yet, and prompts
    // naming specific content would send a first visitor straight into "I
    // don't have information on that". Rewrite these against the real corpus
    // once it is loaded.
    suggestions: [
      { icon: Building2, label: 'What does Goqii Technologies do?', hint: 'Overview' },
      { icon: FileText, label: 'Summarise the documents you can see', hint: 'Contents' },
      { icon: HelpCircle, label: 'What can I ask you about?', hint: 'Getting started' },
    ],
  },
}

/** Where "/" lands, and the fallback for an unrecognised slug. */
export const DEFAULT_ORG_SLUG = 'sitare'

export const getOrg = (slug: string | undefined): Org | null =>
  (slug && ORGS[slug]) || null
