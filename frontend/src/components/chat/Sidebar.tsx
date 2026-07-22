import { useMemo, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { AnimatePresence, motion } from 'framer-motion'
import { Info, MessageSquarePlus, PanelLeftClose, Search, Trash2, X } from 'lucide-react'
import { Button } from './ui/button'
import { Kbd, Tooltip } from './ui/primitives'
import { cn, mod, useMediaQuery } from './lib/utils'
import { Logo } from './Logo'
import type { Conversation } from './types'

const DAY = 86_400_000
const WIDTH = 288

function group(conversations: Conversation[]) {
  const now = Date.now()
  const buckets: Record<string, Conversation[]> = { Today: [], 'Previous 7 days': [], Earlier: [] }
  for (const c of conversations) {
    const age = now - (c.createdAt ?? now)
    buckets[age < DAY ? 'Today' : age < 7 * DAY ? 'Previous 7 days' : 'Earlier'].push(c)
  }
  return Object.entries(buckets).filter(([, v]) => v.length)
}

/* One conversation row. The delete control only materialises on hover or
   keyboard focus, so the resting row stays a clean single line of text. */
function SidebarItem({
  conversation: c,
  active,
  onOpen,
  onDelete,
}: {
  conversation: Conversation
  active: boolean
  onOpen: () => void
  onDelete: () => void
}) {
  return (
    <li className="group/row relative">
      <button
        type="button"
        onClick={onOpen}
        aria-current={active ? 'page' : undefined}
        className={cn(
          'w-full truncate rounded-[var(--radius-control)] py-2.5 pl-3 pr-9 text-left text-[13.5px] leading-[1.4] transition-colors duration-150',
          active
            ? 'bg-surface font-medium text-ink shadow-[var(--shadow-card)]'
            : 'text-muted hover:bg-hover hover:text-ink',
        )}
      >
        {c.title}
      </button>
      <button
        type="button"
        onClick={onDelete}
        aria-label={`Delete conversation: ${c.title}`}
        className="absolute right-1.5 top-1/2 flex size-7 -translate-y-1/2 items-center justify-center rounded-[6px] text-faint opacity-0 transition-[opacity,color,background-color] duration-150 hover:bg-error-soft hover:text-error focus-visible:opacity-100 group-hover/row:opacity-100"
      >
        <Trash2 className="size-3.5" />
      </button>
    </li>
  )
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
      <div className="flex h-16 shrink-0 items-center gap-2 px-4">
        <Logo />
        <Tooltip
          className="ml-auto"
          label={isOverlay ? 'Close' : <>Hide sidebar <Kbd>{mod} B</Kbd></>}
        >
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Hide sidebar">
            {isOverlay ? <X /> : <PanelLeftClose />}
          </Button>
        </Tooltip>
      </div>

      <div className="flex flex-col gap-2 px-4 pb-2">
        <Button variant="outline" size="md" onClick={onNew} className="w-full justify-start gap-2.5">
          <MessageSquarePlus className="text-muted" />
          New conversation
          <Kbd className="ml-auto">{mod} ⇧ O</Kbd>
        </Button>

        {/* Icon is centered against the input itself, not this wrapper — the
            wrapper's own padding would otherwise offset it upward. */}
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint"
            aria-hidden="true"
          />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search conversations"
            aria-label="Search conversations"
            className="h-9 w-full rounded-[var(--radius-control)] border border-transparent bg-canvas pl-9 pr-3 text-[13.5px] text-ink outline-none transition-colors duration-150 placeholder:text-faint focus:border-accent focus:bg-surface"
          />
        </div>
      </div>

      <nav aria-label="Conversation history" className="flex-1 overflow-y-auto px-4 py-2">
        {groups.length === 0 && (
          <p className="px-1 py-8 text-center text-[13px] leading-relaxed text-faint">
            {conversations.length ? 'No matching conversations.' : 'Your conversations will appear here.'}
          </p>
        )}
        {groups.map(([label, items]) => (
          <section key={label} className="mb-6 last:mb-0">
            <h2 className="eyebrow mb-2 px-1">{label}</h2>
            <ul className="flex flex-col gap-1">
              {items.map((c) => (
                <SidebarItem
                  key={c.localId}
                  conversation={c}
                  active={c.localId === activeLocalId}
                  onOpen={() => onOpen(c.localId)}
                  onDelete={() => onDelete(c.localId)}
                />
              ))}
            </ul>
          </section>
        ))}
      </nav>

      <div className="shrink-0 border-t border-border p-4">
        <div className="flex items-start gap-2.5 rounded-[var(--radius-control)] bg-canvas p-3">
          <Info className="mt-px size-3.5 shrink-0 text-faint" aria-hidden="true" />
          <p className="text-[11.5px] leading-[1.5] text-faint">
            History is stored in this browser only. Answers cite uploaded documents — verify anything
            critical against the source.
          </p>
        </div>
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
        animate={{ width: open ? WIDTH : 0 }}
        transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
        className="relative shrink-0 overflow-hidden border-r border-border"
      >
        <div className="absolute inset-y-0 right-0" style={{ width: WIDTH }}>
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
                transition={{ duration: 0.2 }}
                className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px]"
              />
            </Dialog.Overlay>
            <Dialog.Content asChild aria-label="Conversation history">
              <motion.div
                initial={{ x: '-100%' }}
                animate={{ x: 0 }}
                exit={{ x: '-100%' }}
                transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
                className="fixed inset-y-0 left-0 z-50 w-[300px] max-w-[85vw] border-r border-border shadow-[var(--shadow-float)]"
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
