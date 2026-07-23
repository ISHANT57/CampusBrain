import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type ChatTurn } from '../../api/client'
import type { ChatMessage, Conversation } from './types'

// Per organization, not one shared key: each tenant is its own chatbot, so a
// visitor who uses two of them must not see one's history in the other's
// sidebar — the threads cite different corpora and would be nonsense mixed.
const storeKey = (orgSlug: string) => `cb-chat-conversations:${orgSlug}`
// Mirrors MAX_HISTORY_TURNS / the per-turn max_length in
// backend/app/schemas/chat.py — the server rejects (422) anything past these,
// so trim here rather than let a long chat start failing to send.
const MAX_HISTORY_TURNS = 12
const MAX_TURN_CHARS = 4000
const uid = () => Math.random().toString(36).slice(2, 10)
const titleFrom = (text: string) => (text.length > 46 ? text.slice(0, 46).trimEnd() + '…' : text)

// Local-only history, and now the only copy that exists: students chat
// anonymously, so the backend stores no transcript at all. Clearing site data
// clears the chats. That's the trade for zero-friction access — if history
// needs to survive a browser wipe, it needs an account to hang off.
function load(orgSlug: string): Conversation[] {
  try {
    const raw = JSON.parse(localStorage.getItem(storeKey(orgSlug)) || 'null')
    if (!Array.isArray(raw)) return []
    // A message can be persisted mid-flight (refresh, crash, dropped
    // connection) and never finish — resurrect it as "stopped", not a
    // permanent phantom spinner that also blocks all new sends.
    return raw.map((c: Conversation) => ({
      ...c,
      messages: c.messages.map((m: ChatMessage) =>
        m.phase === 'searching' || m.phase === 'revealing' ? { ...m, phase: 'stopped' as const } : m,
      ),
    }))
  } catch {
    return []
  }
}

export function useChat(orgSlug: string) {
  const [conversations, setConversations] = useState<Conversation[]>(() => load(orgSlug))
  const [activeLocalId, setActiveLocalId] = useState<string | null>(
    () => load(orgSlug)[0]?.localId ?? null,
  )
  const timers = useRef<Array<ReturnType<typeof setTimeout>>>([])

  // Switching tenants swaps the whole thread list. Without this the state
  // initialised for the first org would persist and then be written back
  // under the second org's key, silently copying one tenant's history onto
  // the other.
  useEffect(() => {
    const next = load(orgSlug)
    setConversations(next)
    setActiveLocalId(next[0]?.localId ?? null)
  }, [orgSlug])

  useEffect(() => {
    localStorage.setItem(storeKey(orgSlug), JSON.stringify(conversations.slice(0, 50)))
  }, [conversations, orgSlug])

  const active = conversations.find((c) => c.localId === activeLocalId) ?? null
  const messages = active?.messages ?? []
  const streaming = messages.some((m) => m.phase === 'searching' || m.phase === 'revealing')

  // Never overwrite a message the user has already stopped — this is the
  // one guard every caller (the async response, the reveal ticker) routes
  // through, so a late-arriving response can't resurrect a stopped bubble.
  const patch = useCallback((localId: string, msgId: string, next: Partial<ChatMessage>) => {
    setConversations((cs) =>
      cs.map((c) =>
        c.localId !== localId
          ? c
          : {
              ...c,
              messages: c.messages.map((m) =>
                m.id === msgId && m.phase !== 'stopped' ? { ...m, ...next } : m,
              ),
            },
      ),
    )
  }, [])

  const clearTimers = () => {
    timers.current.forEach((t) => (clearTimeout(t), clearInterval(t)))
    timers.current = []
  }

  const stop = useCallback(() => {
    clearTimers()
    setConversations((cs) =>
      cs.map((c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.phase === 'searching' || m.phase === 'revealing' ? { ...m, phase: 'stopped' } : m,
        ),
      })),
    )
  }, [])

  // The backend returns one complete JSON answer, not a token stream. This
  // reveals the already-fetched text at a reading cadence for polish — it
  // is not simulating a real stream. Citations are attached up front (the
  // response already has them) so the source rail appears with the first
  // token, the same order Perplexity-style UIs use.
  const reveal = useCallback(
    (localId: string, msgId: string, text: string) => {
      const words = text.split(/(\s+)/)
      let i = 0
      const iv = setInterval(() => {
        const step = 2 + (i % 3)
        const chunk = words.slice(i, i + step).join('')
        i += step
        setConversations((cs) =>
          cs.map((c) =>
            c.localId !== localId
              ? c
              : {
                  ...c,
                  messages: c.messages.map((m) =>
                    m.id === msgId && m.phase === 'revealing' ? { ...m, content: m.content + chunk } : m,
                  ),
                },
          ),
        )
        if (i >= words.length) {
          clearInterval(iv)
          patch(localId, msgId, { phase: 'done' })
        }
      }, 18)
      timers.current.push(iv)
    },
    [patch],
  )

  const send = useCallback(
    async (text: string) => {
      const q = text.trim()
      if (!q) return
      clearTimers()

      const replyId = uid()
      const userMsg: ChatMessage = { id: uid(), role: 'user', content: q }
      const replyMsg: ChatMessage = { id: replyId, role: 'assistant', content: '', phase: 'searching' }

      const localId = activeLocalId ?? uid()
      // Anonymous chat has no server-side transcript, so multi-turn context
      // is whatever this browser still holds. Skip failed/in-flight bubbles —
      // an error message's text is a stack of nonsense to feed a model.
      const history: ChatTurn[] = (active?.messages ?? [])
        .filter((m) => m.content && m.phase !== 'error' && m.phase !== 'searching')
        .slice(-MAX_HISTORY_TURNS)
        .map((m) => ({ role: m.role, content: m.content.slice(0, MAX_TURN_CHARS) }))

      setConversations((cs) => {
        const existing = cs.find((c) => c.localId === localId)
        if (existing) {
          return cs.map((c) =>
            c.localId === localId ? { ...c, messages: [...c.messages, userMsg, replyMsg] } : c,
          )
        }
        return [
          { localId, title: titleFrom(q), createdAt: Date.now(), messages: [userMsg, replyMsg] },
          ...cs,
        ]
      })
      if (!activeLocalId) setActiveLocalId(localId)

      try {
        const res = await api.chat(orgSlug, q, history)
        patch(localId, replyId, { phase: 'revealing', citations: res.citations ?? [] })
        reveal(localId, replyId, res.answer)
      } catch (err) {
        patch(localId, replyId, { phase: 'error', content: (err as Error).message })
      }
    },
    [activeLocalId, active, patch, reveal, orgSlug],
  )

  const newChat = useCallback(() => {
    clearTimers()
    setActiveLocalId(null)
  }, [])

  const openChat = useCallback((localId: string) => {
    clearTimers()
    setActiveLocalId(localId)
  }, [])

  const removeChat = useCallback(
    (localId: string) => {
      setConversations((cs) => cs.filter((c) => c.localId !== localId))
      setActiveLocalId((id) => (id === localId ? null : id))
    },
    [],
  )

  useEffect(() => clearTimers, [])

  return {
    conversations,
    active,
    activeLocalId,
    messages,
    streaming,
    send,
    stop,
    newChat,
    openChat,
    removeChat,
  }
}
