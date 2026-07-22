import { useEffect, useRef, useState } from 'react'
import { ArrowDown, PanelLeft, Search } from 'lucide-react'
import '../components/chat/chat-theme.css'
import { Button } from '../components/chat/ui/button'
import { Kbd, Tooltip } from '../components/chat/ui/primitives'
import { Composer, type ComposerHandle } from '../components/chat/Composer'
import { Message } from '../components/chat/Message'
import { EmptyState } from '../components/chat/EmptyState'
import { Sidebar } from '../components/chat/Sidebar'
import { CommandPalette } from '../components/chat/CommandPalette'
import { ShortcutsDialog } from '../components/chat/ShortcutsDialog'
import { ThemeToggle, useLocalTheme } from '../components/chat/ThemeToggle'
import { useChat } from '../components/chat/useChat'
import { cn, mod, useMediaQuery } from '../components/chat/lib/utils'

const isTyping = (el: Element | null) =>
  !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || (el as HTMLElement).isContentEditable)

export default function Chat() {
  const { dark, toggle: toggleTheme } = useLocalTheme()
  const chat = useChat()
  const desktop = useMediaQuery('(min-width: 900px)')

  const [sidebarOpen, setSidebarOpen] = useState(desktop)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [pinned, setPinned] = useState(true)
  const composer = useRef<ComposerHandle>(null)
  const scroller = useRef<HTMLDivElement>(null)
  // Radix/cmdk portal their dialogs to document.body by default — which is
  // OUTSIDE .cb-scope, where every --surface/--ink/--border token is defined.
  // Portaled content therefore rendered with those variables undefined, i.e.
  // a fully transparent command palette. Portalling into this element instead
  // keeps them inside the scope. Can't fix by hoisting the tokens to :root:
  // --accent/--border/--muted collide with the names index.css already uses
  // for the auth/upload pages, so that would restyle those.
  const scope = useRef<HTMLDivElement>(null)
  // Portal targets are read during render but the ref is only populated after
  // the first commit, so the first render would hand the dialogs null (which
  // silently falls back to document.body — the bug this is fixing). One extra
  // render after mount gives them the real element.
  const [scopeReady, setScopeReady] = useState(false)
  useEffect(() => setScopeReady(true), [])
  const portalTarget = scopeReady ? scope.current : null

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
    if (!pinned) return
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

  return (
    <div ref={scope} className={cn('cb-scope flex min-h-0 flex-1', dark && 'dark')}>
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
        <header className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-3">
          {!sidebarOpen && (
            <Tooltip label={<>Show sidebar <Kbd>{mod} B</Kbd></>}>
              <Button variant="ghost" size="icon-sm" onClick={() => setSidebarOpen(true)} aria-label="Show sidebar">
                <PanelLeft />
              </Button>
            </Tooltip>
          )}
          <h1 className="min-w-0 truncate px-1 text-[13.5px] font-medium text-ink">
            {chat.active?.title ?? 'New conversation'}
          </h1>
          <div className="ml-auto flex items-center gap-1">
            <Button variant="ghost" size="sm" onClick={() => setPaletteOpen(true)} className="gap-2">
              <Search />
              <span className="hidden sm:inline">Search</span>
              <Kbd className="hidden sm:inline-flex">{mod} K</Kbd>
            </Button>
            <ThemeToggle dark={dark} toggle={toggleTheme} />
          </div>
        </header>

        <div ref={scroller} onScroll={onScroll} className="relative flex-1 overflow-y-auto">
          {chat.messages.length === 0 ? (
            <EmptyState onAsk={chat.send} />
          ) : (
            <div className="mx-auto max-w-[720px] px-5 py-8">
              <div className="flex flex-col gap-9">
                {chat.messages.map((m) => (
                  <Message key={m.id} message={m} onRetry={retry} />
                ))}
              </div>
              <div className="h-8" />
            </div>
          )}
        </div>

        <div className="relative shrink-0 px-5 pb-5 pt-1">
          {!pinned && chat.messages.length > 0 && (
            <div className="absolute -top-11 left-1/2 z-10 -translate-x-1/2">
              <Button
                variant="outline"
                size="icon-sm"
                onClick={toBottom}
                aria-label="Scroll to latest"
                className="rounded-full shadow-[var(--shadow-card)]"
              >
                <ArrowDown />
              </Button>
            </div>
          )}

          <div className="mx-auto max-w-[720px]">
            <Composer ref={composer} onSubmit={chat.send} onStop={chat.stop} streaming={chat.streaming} />
            <p className="mt-2.5 text-center text-[11px] text-faint">
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
