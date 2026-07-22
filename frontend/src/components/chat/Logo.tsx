import { cn } from './lib/utils'

/* Four-point star drawn as one path — "sitare" means stars. One glyph, no
   icon dependency, legible from 12px to hero size. */
export function StarMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={cn('size-5', className)} aria-hidden="true">
      <path
        d="M12 1.5c.55 5.2 5.3 9.95 10.5 10.5-5.2.55-9.95 5.3-10.5 10.5C11.45 17.3 6.7 12.55 1.5 12 6.7 11.45 11.45 6.7 12 1.5Z"
        fill="currentColor"
      />
    </svg>
  )
}

// One brand mark everywhere it appears (chat, admin) — `context` adds a small
// suffix instead of every screen inventing its own name.
export function Logo({ className, context }: { className?: string; context?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <span
        className="flex size-7 items-center justify-center rounded-[9px] bg-accent text-accent-fg"
        aria-hidden="true"
      >
        <StarMark className="size-[15px]" />
      </span>
      <span className="text-[15px] font-[650] tracking-[-0.015em] text-ink">
        Ask&nbsp;Sitare
        {context && <span className="font-medium text-muted"> · {context}</span>}
      </span>
    </span>
  )
}
