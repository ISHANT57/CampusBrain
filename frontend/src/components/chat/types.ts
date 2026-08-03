export type Citation = {
  index: number
  document_id: number
  filename: string
  page_number: number
  excerpt: string
}

/* A document retrieval surfaced, before the model decided whether to use it.
   Arrives with the leading "retrieved" SSE event so the sources panel can fill
   as soon as retrieval finishes instead of holding a skeleton for the whole
   generation.

   Carries NO excerpt, deliberately, and the backend does not send one: a
   retrieved chunk the answer never cited is not evidence for that answer, and
   showing its text would invite the reader to treat it as support. */
export type RetrievedDocument = {
  document_id: number
  filename: string
  pages: number[]
  chunks: number
}

/* Measured basis for an answer. Every field is a value the backend already
   computed; there is deliberately no high/medium/low verdict, because bucketing
   these numbers would mean inventing cutoffs nothing validated. The UI's job is
   to show them with their basis visible, not to collapse them into a label. */
export type Grounding = {
  /** Similarity of the closest matching passage, 0-1. */
  best_semantic_score: number
  /** Below this, the assistant refuses outright rather than answer ungrounded. */
  relevance_threshold: number
  retrieved_chunks: number
  cited_chunks: number
  cited_documents: number
  refused: boolean
}

export type MessagePhase = 'searching' | 'revealing' | 'done' | 'stopped' | 'error'

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  phase?: MessagePhase
  citations?: Citation[]
  /** What was searched. Set mid-stream, before any citations exist. */
  retrieved?: RetrievedDocument[]
  /** Set with the final "done" event, alongside citations. */
  grounding?: Grounding
}

export type Conversation = {
  localId: string
  title: string
  createdAt: number
  messages: ChatMessage[]
}
