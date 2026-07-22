import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { Button } from './ui/button'
import { Kbd } from './ui/primitives'
import { mod } from './lib/utils'

const GROUPS: [string, [string, string[]][]][] = [
  [
    'General',
    [
      ['Command palette', [mod, 'K']],
      ['Toggle sidebar', [mod, 'B']],
      ['Toggle theme', [mod, 'J']],
      ['Shortcuts', ['?']],
    ],
  ],
  [
    'Conversation',
    [
      ['New conversation', [mod, '⇧', 'O']],
      ['Focus the input', ['/']],
      ['Send', ['Enter']],
      ['New line', ['⇧', 'Enter']],
      ['Stop generating', ['Esc']],
    ],
  ],
]

export function ShortcutsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(440px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 animate-rise rounded-[16px] border border-border bg-surface p-6 shadow-[var(--shadow-card)]">
          <div className="flex items-start justify-between gap-4">
            <Dialog.Title className="font-serif text-[19px] text-ink">Keyboard shortcuts</Dialog.Title>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Close">
                <X />
              </Button>
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">Keyboard shortcuts available on this page.</Dialog.Description>

          {GROUPS.map(([label, rows]) => (
            <section key={label} className="mt-6 first:mt-5">
              <h3 className="eyebrow">{label}</h3>
              <dl className="mt-2 divide-y divide-border">
                {rows.map(([name, keys]) => (
                  <div key={name} className="flex items-center justify-between gap-4 py-2">
                    <dt className="text-[13.5px] text-muted">{name}</dt>
                    <dd className="flex gap-1">
                      {keys.map((k, i) => (
                        <Kbd key={i}>{k}</Kbd>
                      ))}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
