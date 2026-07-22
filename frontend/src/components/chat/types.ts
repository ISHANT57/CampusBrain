export type Citation = {
  index: number
  document_id: number
  filename: string
  page_number: number
  excerpt: string
}

export type MessagePhase = 'searching' | 'revealing' | 'done' | 'stopped' | 'error'

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  phase?: MessagePhase
  citations?: Citation[]
}

export type Conversation = {
  localId: string
  title: string
  createdAt: number
  messages: ChatMessage[]
}
