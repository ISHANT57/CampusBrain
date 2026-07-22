import { useMemo, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { AnimatePresence, motion } from 'framer-motion'
import { MessageSquarePlus, PanelLeftClose, Search, Trash2, X } from 'lucide-react'
import { Button } from './ui/button'
import { Kbd, Tooltip } from './ui/primitives'
import { cn, mod, useMediaQuery } from './lib/utils'
import type { Conversation } from './types'

const DAY = 86_400_000

function group(conversations: Conversation[]) {
  const now = Date.now()
  const buckets: Record<string, Conversation[]> = { Today: [], 'Previous 7 days': [], Earlier: [] }
  for (const c of conversations) {
    const age = now - (c.createdAt ?? now)
    buckets[age < DAY ? 'Today' : age < 7 * DAY ? 'Previous 7 days' : 'Earlier'].push(c)
  }
  return Object.entries(buckets).filter(([, v]) => v.length)
}

function SidebarContent({
  conversations,
  activeLocalId,
  onOpen,
  onNew,
  onDelete,
  onClose,
  isOverlay,
}: {
  conversations: Conversation[]
  activeLocalId: string | null
  onOpen: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  onClose: () => void
  isOverlay?: boolean
}) {
  const [q, setQ] = useState('')
  const filtered = useMemo(
    () => conversations.filter((c) => c.title.toLowerCase().includes(q.toLowerCase())),
    [conversations, q],
  )
  const groups = group(filtered)

  return (
    <div className="flex h-full flex-col bg-sunken">
      <div className="flex items-center gap-2 px-3 py-3">
        <span className="eyebrow px-1">History</span>
        <div className="ml-auto flex items-center gap-1">
          <Tooltip label={isOverlay ? 'Close' : <>Hide sidebar <Kbd>{mod} B</Kbd></>}>
            <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Hide sidebar">
              {isOverlay ? <X /> : <PanelLeftClose />}
            </Button>
          </Tooltip>
        </div>
      </div>

      <div className="px-3">
        <Button variant="outline" size="md" onClick={onNew} className="w-full justify-start">
          <MessageSquarePlus className="text-muted" />
          New conversation
        </Button>
      </div>

      <div className="relative px-3 pt-3">
        <Search className="pointer-events-none absolute left-6 top-1/2 size-3.5 -translate-y-1/2 text-faint" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search conversations"
          aria-label="Search conversations"
          className="h-8 w-full rounded-[8px] border border-transparent bg-surface/60 pl-8 pr-2 text-[13px] text-ink outline-none placeholder:text-faint focus:border-border"
        />
      </div>

      <nav aria-label="Conversation history" className="mt-3 flex-1 overflow-y-auto px-3 pb-3">
        {groups.length === 0 && (
          <p className="px-2 py-6 text-[13px] leading-relaxed text-faint">
            {conversations.length ? 'No matches.' : 'Your conversations will appear here.'}
          </p>
        )}
        {groups.map(([label, items]) => (
          <section key={label} className="mb-4">
            <h2 className="eyebrow px-2 pb-1.5">{label}</h2>
            <ul className="flex flex-col gap-px">
              {items.map((c) => (
                <li key={c.localId} className="group/row relative">
                  <button
                    type="button"
                    onClick={() => onOpen(c.localId)}
                    aria-current={c.localId === activeLocalId ? 'page' : undefined}
                    className={cn(
                      'w-full truncate rounded-[8px] py-2 pl-2 pr-8 text-left text-[13px] transition-colors',
                      c.localId === activeLocalId
                        ? 'bg-surface text-ink shadow-[inset_0_0_0_1px_var(--color-border)]'
                        : 'text-muted hover:bg-surface/70 hover:text-ink',
                    )}
                  >
                    {c.title}
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(c.localId)}
                    aria-label={`Delete conversation: ${c.title}`}
                    className="absolute right-1 top-1/2 flex size-7 -translate-y-1/2 items-center justify-center rounded-[6px] text-faint opacity-0 transition-[opacity,color] hover:text-clay focus-visible:opacity-100 group-hover/row:opacity-100"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </nav>

      <div className="border-t border-border px-4 py-3">
        <p className="text-[11px] leading-[1.5] text-faint">
          History is stored in this browser only. Answers cite uploaded documents — verify anything
          critical against the source.
        </p>
      </div>
    </div>
  )
}

export function Sidebar({
  open,
  onOpenChange,
  container,
  ...props
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  // See CommandPalette — the mobile drawer is portalled, so it needs the
  // scope element or it renders unthemed.
  container?: HTMLElement | null
} & Omit<Parameters<typeof SidebarContent>[0], 'onClose'>) {
  const desktop = useMediaQuery('(min-width: 900px)')

  if (desktop) {
    return (
      <motion.aside
        initial={false}
        animate={{ width: open ? 260 : 0 }}
        transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
        className="relative shrink-0 overflow-hidden border-r border-border"
      >
        <div className="absolute inset-y-0 right-0 w-[260px]">
          <SidebarContent {...props} onClose={() => onOpenChange(false)} />
        </div>
      </motion.aside>
    )
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount container={container ?? undefined}>
            <Dialog.Overlay asChild>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-40 bg-ink/40 backdrop-blur-[2px]"
              />
            </Dialog.Overlay>
            <Dialog.Content asChild aria-label="Conversation history">
              <motion.div
                initial={{ x: '-100%' }}
                animate={{ x: 0 }}
                exit={{ x: '-100%' }}
                transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                className="fixed inset-y-0 left-0 z-50 w-[280px] border-r border-border"
              >
                <Dialog.Title className="sr-only">Conversation history</Dialog.Title>
                <SidebarContent {...props} onClose={() => onOpenChange(false)} isOverlay />
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  )
}
