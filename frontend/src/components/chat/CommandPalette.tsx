import { Command } from 'cmdk'
import { MessageSquare, MessageSquarePlus, Moon, PanelLeft, Sun } from 'lucide-react'
import { Kbd } from './ui/primitives'
import { mod } from './lib/utils'
import type { Conversation } from './types'

const itemCls =
  'flex cursor-pointer items-center gap-2.5 rounded-[8px] px-2.5 py-2 text-[13.5px] text-muted outline-none data-[selected=true]:bg-sunken data-[selected=true]:text-ink'

export function CommandPalette({
  open,
  onOpenChange,
  onNew,
  onToggleTheme,
  onToggleSidebar,
  dark,
  conversations,
  onOpenChat,
  container,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onNew: () => void
  onToggleTheme: () => void
  onToggleSidebar: () => void
  dark: boolean
  conversations: Conversation[]
  onOpenChat: (id: string) => void
  // The .cb-scope element. Without it this portals to document.body, where
  // none of the theme's CSS variables are defined, and the palette renders
  // with a transparent background over the conversation.
  container?: HTMLElement | null
}) {
  const run = (fn: () => void) => () => {
    onOpenChange(false)
    fn()
  }

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Command palette"
      shouldFilter
      container={container ?? undefined}
      overlayClassName="fixed inset-0 z-50 bg-ink/40 backdrop-blur-[2px]"
      contentClassName="fixed left-1/2 top-[15vh] z-50 w-[min(560px,calc(100vw-2rem))] -translate-x-1/2 animate-rise overflow-hidden rounded-[16px] border border-border bg-surface shadow-[var(--shadow-card)]"
    >
      <div className="flex items-center gap-2.5 border-b border-border px-4">
        <Command.Input
          placeholder="Search actions or conversations…"
          className="h-12 w-full bg-transparent text-[14.5px] text-ink outline-none placeholder:text-faint"
        />
        <Kbd>Esc</Kbd>
      </div>

      <Command.List className="max-h-[min(56vh,400px)] overflow-y-auto p-2">
        <Command.Empty className="px-2.5 py-8 text-center text-[13px] text-faint">
          Nothing matches that.
        </Command.Empty>

        <Command.Group heading="Actions">
          <Command.Item className={itemCls} onSelect={run(onNew)}>
            <MessageSquarePlus className="size-4 text-faint" />
            New conversation
          </Command.Item>
          <Command.Item className={itemCls} onSelect={run(onToggleTheme)} value="theme dark light appearance">
            {dark ? <Sun className="size-4 text-faint" /> : <Moon className="size-4 text-faint" />}
            Switch to {dark ? 'light' : 'dark'} mode
            <Kbd className="ml-auto">{mod} J</Kbd>
          </Command.Item>
          <Command.Item className={itemCls} onSelect={run(onToggleSidebar)} value="sidebar history panel">
            <PanelLeft className="size-4 text-faint" />
            Toggle sidebar
            <Kbd className="ml-auto">{mod} B</Kbd>
          </Command.Item>
        </Command.Group>

        {conversations.length > 0 && (
          <Command.Group heading="Recent">
            {conversations.slice(0, 8).map((c) => (
              <Command.Item key={c.localId} className={itemCls} onSelect={run(() => onOpenChat(c.localId))}>
                <MessageSquare className="size-4 text-faint" />
                <span className="truncate">{c.title}</span>
              </Command.Item>
            ))}
          </Command.Group>
        )}
      </Command.List>
    </Command.Dialog>
  )
}
