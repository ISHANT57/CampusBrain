import * as React from 'react'
import { AlertTriangle, CircleAlert } from 'lucide-react'
import { cn } from '../lib/utils'
import { StarMark } from '../Logo'

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  function Card({ className, ...props }, ref) {
    return (
      <div
        ref={ref}
        className={cn('rounded-[var(--radius-panel)] border border-border bg-surface', className)}
        {...props}
      />
    )
  },
)

export function Badge({
  className,
  variant = 'default',
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & {
  variant?: 'default' | 'accent' | 'outline' | 'success' | 'warning' | 'error'
}) {
  const variants = {
    default: 'bg-sunken text-muted border-border',
    accent: 'bg-accent-soft text-accent border-accent-border',
    outline: 'bg-transparent text-muted border-border',
    success: 'bg-success-soft text-success border-transparent',
    warning: 'bg-warning-soft text-warning border-transparent',
    error: 'bg-error-soft text-error border-transparent',
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
        'inline-flex h-5 min-w-5 items-center justify-center rounded-[6px] border border-border bg-surface px-1.5 font-mono text-[10px] font-medium text-muted',
        className,
      )}
    >
      {children}
    </kbd>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-shimmer rounded-[6px] bg-border', className)} aria-hidden="true" />
}

/* Answer placeholder — mirrors the real answer's line-height and rhythm so
   the swap to live text doesn't shift the layout. */
export function AnswerSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-hidden="true">
      <Skeleton className="h-[13px] w-[94%]" />
      <Skeleton className="h-[13px] w-[88%]" />
      <Skeleton className="h-[13px] w-[62%]" />
    </div>
  )
}

/* Avatar — square-rounded like the reference's message gutter, not circular,
   so it reads as a product identity rather than a social profile photo. */
export function Avatar({ kind, className }: { kind: 'user' | 'assistant'; className?: string }) {
  const base = 'flex size-8 shrink-0 items-center justify-center rounded-[10px] border'
  if (kind === 'assistant') {
    return (
      <span
        className={cn(base, 'border-accent-border bg-accent-soft text-accent', className)}
        aria-hidden="true"
      >
        <StarMark className="size-[15px]" />
      </span>
    )
  }
  return (
    <span
      className={cn(base, 'border-border bg-sunken font-medium text-[11px] text-muted', className)}
      aria-hidden="true"
    >
      You
    </span>
  )
}

/* One error/warning surface for the whole app — the chat's failed answer, the
   login form's rejection, anything else. Was three different treatments. */
export function ErrorCard({
  title,
  description,
  action,
  variant = 'error',
  className,
}: {
  title: React.ReactNode
  description?: React.ReactNode
  action?: React.ReactNode
  variant?: 'error' | 'warning'
  className?: string
}) {
  const Icon = variant === 'warning' ? AlertTriangle : CircleAlert
  return (
    <div
      role="alert"
      className={cn(
        'flex items-start gap-3 rounded-[var(--radius-card)] border p-4',
        variant === 'warning'
          ? 'border-warning/25 bg-warning-soft'
          : 'border-error/25 bg-error-soft',
        className,
      )}
    >
      <Icon
        className={cn('mt-px size-[18px] shrink-0', variant === 'warning' ? 'text-warning' : 'text-error')}
        aria-hidden="true"
      />
      <div className="min-w-0 flex-1">
        <p className="text-[14px] font-medium leading-[1.45] text-ink">{title}</p>
        {description && <p className="mt-1 text-[13.5px] leading-[1.55] text-muted">{description}</p>}
        {action && <div className="mt-3">{action}</div>}
      </div>
    </div>
  )
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
          'pointer-events-none absolute z-50 flex items-center gap-1.5 whitespace-nowrap rounded-[var(--radius-control)] border border-border bg-raised px-2.5 py-1.5 text-[12px] text-ink opacity-0 shadow-[var(--shadow-float)] transition-opacity duration-150 group-hover/tt:opacity-100 group-focus-within/tt:opacity-100',
          pos,
        )}
      >
        {label}
      </span>
    </span>
  )
}
