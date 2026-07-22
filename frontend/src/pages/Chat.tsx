import { useEffect, useRef, useState } from 'react'
import { ArrowDown } from 'lucide-react'
import { Button } from '../components/chat/ui/button'
import { Composer, type ComposerHandle } from '../components/chat/Composer'
import { Header } from '../components/chat/Header'
import { Message } from '../components/chat/Message'
import { EmptyState } from '../components/chat/EmptyState'
import { Sidebar } from '../components/chat/Sidebar'
import { CommandPalette } from '../components/chat/CommandPalette'
import { ShortcutsDialog } from '../components/chat/ShortcutsDialog'
import { useChat } from '../components/chat/useChat'
import { useMediaQuery } from '../components/chat/lib/utils'
import { useTheme } from '../hooks/useTheme'

// One reading column, shared by the thread and the composer so the two stay
// optically aligned. ~820px keeps answer lines near the 75-character mark.
const COLUMN = 'mx-auto w-full max-w-[820px] px-5 sm:px-8'

const isTyping = (el: Element | null) =>
  !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || (el as HTMLElement).isContentEditable)

// portalTarget: the app-level .cb-scope element (see App.tsx) — Radix/cmdk
// dialogs need it to portal into a themed element instead of document.body.
export default function Chat({ portalTarget }: { portalTarget: HTMLElement | null }) {
  const { dark, toggle: toggleTheme } = useTheme()
  const chat = useChat()
  const desktop = useMediaQuery('(min-width: 900px)')

  const [sidebarOpen, setSidebarOpen] = useState(desktop)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [pinned, setPinned] = useState(true)
  const composer = useRef<ComposerHandle>(null)
  const scroller = useRef<HTMLDivElement>(null)

  useEffect(() => setSidebarOpen(desktop), [desktop])

  const newChat = () => {
    chat.newChat()
    setTimeout(() => composer.current?.focus(), 60)
  }

  const retry = () => {
    const lastUser = [...chat.messages].reverse().find((m) => m.role === 'user')
    if (lastUser) chat.send(lastUser.content)
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const cmd = e.metaKey || e.ctrlKey
      if (cmd && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((o) => !o)
        return
      }
      if (cmd && e.key.toLowerCase() === 'b') {
        e.preventDefault()
        setSidebarOpen((o) => !o)
        return
      }
      if (cmd && e.key.toLowerCase() === 'j') {
        e.preventDefault()
        toggleTheme()
        return
      }
      if (cmd && e.shiftKey && e.key.toLowerCase() === 'o') {
        e.preventDefault()
        newChat()
        return
      }
      if (e.key === 'Escape' && chat.streaming) {
        chat.stop()
        return
      }
      if (isTyping(document.activeElement)) return
      if (e.key === '/') {
        e.preventDefault()
        composer.current?.focus()
      }
      if (e.key === '?') {
        e.preventDefault()
        setShortcutsOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat.streaming])

  useEffect(() => {
    // Skip while the thread is empty. The welcome screen is taller than a
    // phone viewport, so pinning it to the bottom on mount opened the app
    // scrolled past its own headline.
    if (!pinned || chat.messages.length === 0) return
    const el = scroller.current
    if (el) el.scrollTop = el.scrollHeight
  }, [chat.messages, pinned])

  const onScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 120)
  }

  const toBottom = () => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' })
    setPinned(true)
  }

  const empty = chat.messages.length === 0

  return (
    <div className="flex min-h-0 flex-1">
      <Sidebar
        container={portalTarget}
        open={sidebarOpen}
        onOpenChange={setSidebarOpen}
        conversations={chat.conversations}
        activeLocalId={chat.activeLocalId}
        onOpen={(id) => {
          chat.openChat(id)
          if (!desktop) setSidebarOpen(false)
        }}
        onNew={newChat}
        onDelete={chat.removeChat}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Header
          title={chat.active?.title ?? 'New conversation'}
          subtitle="Grounded in Sitare University documents"
          sidebarOpen={sidebarOpen}
          onOpenSidebar={() => setSidebarOpen(true)}
          onOpenSearch={() => setPaletteOpen(true)}
          dark={dark}
          onToggleTheme={toggleTheme}
        />

        <div
          ref={scroller}
          onScroll={onScroll}
          data-scroll
          className="relative flex-1 overflow-y-auto"
        >
          {empty ? (
            <EmptyState onAsk={chat.send} />
          ) : (
            <div className={`${COLUMN} py-8`}>
              <div className="mb-8 flex justify-center">
                <span className="rounded-full border border-border bg-surface px-3.5 py-1.5 text-[12px] text-muted">
                  Answers are drawn from Sitare University's documents
                </span>
              </div>

              {/* 40px between turns — enough to separate speakers without the
                  thread breaking into isolated blocks. */}
              <div className="flex flex-col gap-10">
                {chat.messages.map((m) => (
                  <Message key={m.id} message={m} onRetry={retry} />
                ))}
              </div>
              <div className="h-4" />
            </div>
          )}
        </div>

        <div className="relative shrink-0">
          {/* Fades the thread out behind the composer so messages dissolve
              into it rather than colliding with a hard edge. */}
          <div
            className="pointer-events-none absolute inset-x-0 -top-8 h-8 bg-gradient-to-t from-canvas to-transparent"
            aria-hidden="true"
          />

          {!pinned && !empty && (
            <div className="absolute -top-14 left-1/2 z-10 -translate-x-1/2">
              <Button
                variant="outline"
                size="icon"
                onClick={toBottom}
                aria-label="Scroll to latest"
                className="rounded-full shadow-[var(--shadow-float)]"
              >
                <ArrowDown />
              </Button>
            </div>
          )}

          {/* data-safe-bottom keeps the composer clear of the iOS home
              indicator; pb-5 is the padding it adds to. */}
          <div data-safe-bottom className={`${COLUMN} pb-5 pt-1`}>
            <Composer
              ref={composer}
              onSubmit={chat.send}
              onStop={chat.stop}
              streaming={chat.streaming}
              placeholder={empty ? 'Ask anything about Sitare University…' : 'Ask a follow-up question…'}
            />
            <p className="mt-3 text-center text-[11.5px] text-faint">
              Answers cite uploaded documents — verify anything critical against the source.
            </p>
          </div>
        </div>
      </div>

      <CommandPalette
        container={portalTarget}
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        onNew={newChat}
        onToggleTheme={toggleTheme}
        onToggleSidebar={() => setSidebarOpen((o) => !o)}
        dark={dark}
        conversations={chat.conversations}
        onOpenChat={(id) => {
          chat.openChat(id)
          if (!desktop) setSidebarOpen(false)
        }}
      />
      <ShortcutsDialog
        container={portalTarget}
        open={shortcutsOpen}
        onOpenChange={setShortcutsOpen}
      />
    </div>
  )
}
