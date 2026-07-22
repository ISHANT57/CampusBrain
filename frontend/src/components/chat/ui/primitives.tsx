import * as React from 'react'
import { cn } from '../lib/utils'

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  function Card({ className, ...props }, ref) {
    return (
      <div ref={ref} className={cn('rounded-[16px] border border-border bg-surface', className)} {...props} />
    )
  },
)

export function Badge({
  className,
  variant = 'default',
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: 'default' | 'accent' | 'outline' }) {
  const variants = {
    default: 'bg-sunken text-muted border-border',
    accent: 'bg-accent-soft text-accent border-transparent',
    outline: 'bg-transparent text-muted border-border',
  }
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium leading-5',
        variants[variant],
        className,
      )}
      {...props}
    />
  )
}

export function Kbd({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        'inline-flex h-5 min-w-5 items-center justify-center rounded-[5px] border border-border bg-surface px-1.5 font-mono text-[10px] font-medium text-muted',
        className,
      )}
    >
      {children}
    </kbd>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-shimmer rounded-md bg-border', className)} aria-hidden="true" />
}

/* CSS-only tooltip — no portal/dependency for a label. */
export function Tooltip({
  label,
  children,
  side = 'bottom',
  className,
}: {
  label: React.ReactNode
  children: React.ReactNode
  side?: 'bottom' | 'top' | 'right'
  className?: string
}) {
  const pos =
    side === 'bottom'
      ? 'top-full mt-2 left-1/2 -translate-x-1/2'
      : side === 'top'
        ? 'bottom-full mb-2 left-1/2 -translate-x-1/2'
        : 'left-full ml-2 top-1/2 -translate-y-1/2'
  return (
    <span className={cn('group/tt relative inline-flex', className)}>
      {children}
      <span
        role="tooltip"
        className={cn(
          'pointer-events-none absolute z-50 flex items-center gap-1.5 whitespace-nowrap rounded-[8px] border border-border bg-surface px-2 py-1 text-[12px] text-ink opacity-0 shadow-[var(--shadow-card)] transition-[opacity,transform] duration-150 group-hover/tt:opacity-100 group-focus-within/tt:opacity-100',
          pos,
        )}
      >
        {label}
      </span>
    </span>
  )
}
