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
  // One AbortController per in-flight reply, keyed by that message's id —
  // not a single ref, because switching conversations while a background
  // reply is still streaming and starting a second one is a real path (the
  // Composer's streaming guard only looks at the ACTIVE conversation).
  const controllers = useRef<Map<string, AbortController>>(new Map())

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
  // one guard every caller (every delta, the final "done") routes through,
  // so a late-arriving chunk can't resurrect a stopped bubble.
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

  // Matches the previous clearTimers()'s scope exactly: global, not scoped
  // to the active conversation. Stop's visibility is per-active-conversation
  // (via `streaming` above), but its effect — like the old interval-based
  // reveal — has always killed every in-flight reply, not just the visible
  // one.
  const abortAll = () => {
    controllers.current.forEach((c) => c.abort())
    controllers.current.clear()
  }

  const stop = useCallback(() => {
    abortAll()
    setConversations((cs) =>
      cs.map((c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.phase === 'searching' || m.phase === 'revealing' ? { ...m, phase: 'stopped' } : m,
        ),
      })),
    )
  }, [])

  const send = useCallback(
    async (text: string) => {
      const q = text.trim()
      if (!q) return

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

      const controller = new AbortController()
      controllers.current.set(replyId, controller)

      // acc, not reading m.content back out of state: the full text is
      // already known here as it arrives, so building it locally sidesteps
      // any stale-closure race with concurrent state updates entirely.
      let acc = ''
      let gotDone = false
      try {
        for await (const event of api.chatStream(orgSlug, q, history, controller.signal)) {
          if (event.type === 'delta') {
            acc += event.text
            patch(localId, replyId, { phase: 'revealing', content: acc })
          } else {
            // "done" carries the RENUMBERED answer, which is not the same
            // string as `acc`: markers in the raw stream ([3]) can renumber
            // to something else ([1]) once the whole answer is known, and
            // citations only exist paired with the final numbering — so
            // this must replace the streamed text, not append to it.
            gotDone = true
            patch(localId, replyId, { phase: 'done', content: event.answer, citations: event.citations })
          }
        }
        if (!gotDone) {
          // The connection ended without a "done" event — a dropped
          // connection, not a clean finish. Left as 'revealing' this would
          // show a permanent typing cursor with no way to know it stalled.
          patch(localId, replyId, {
            phase: 'error',
            content: 'The response was interrupted before it finished. Please try again.',
          })
        }
      } catch (err) {
        // AbortError means the user hit Stop (or navigated away) — stop()
        // has already set phase: 'stopped', and patch()'s own guard would
        // no-op this anyway, but skip it explicitly rather than relying on
        // that timing.
        if ((err as Error).name !== 'AbortError') {
          patch(localId, replyId, { phase: 'error', content: (err as Error).message })
        }
      } finally {
        controllers.current.delete(replyId)
      }
    },
    [activeLocalId, active, patch, orgSlug],
  )

  const newChat = useCallback(() => {
    abortAll()
    setActiveLocalId(null)
  }, [])

  const openChat = useCallback((localId: string) => {
    abortAll()
    setActiveLocalId(localId)
  }, [])

  const removeChat = useCallback(
    (localId: string) => {
      setConversations((cs) => cs.filter((c) => c.localId !== localId))
      setActiveLocalId((id) => (id === localId ? null : id))
    },
    [],
  )

  useEffect(() => abortAll, [])

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
