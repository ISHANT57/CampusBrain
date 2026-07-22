import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { Loader2 } from 'lucide-react'
import { cn } from '../lib/utils'

/* Heights are on an 8px rhythm (32/40/48) with one 36px step for dense
   toolbars. Radius comes from the token ramp, never an arbitrary value. */
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium select-none transition-[background-color,border-color,color,box-shadow,transform] duration-150 ease-out disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:shrink-0 active:scale-[0.97] motion-reduce:active:scale-100',
  {
    variants: {
      variant: {
        accent: 'bg-accent text-accent-fg hover:brightness-110 shadow-[var(--shadow-card)]',
        primary: 'bg-ink text-canvas hover:opacity-90 shadow-[var(--shadow-card)]',
        outline: 'border border-border bg-surface text-ink hover:bg-hover hover:border-border-strong',
        ghost: 'text-muted hover:bg-hover hover:text-ink',
        subtle: 'bg-sunken text-ink hover:bg-hover',
      },
      // coarse: bumps toward the ~44px touch guideline on finger input while
      // leaving the desktop scale alone.
      size: {
        sm: 'h-8 coarse:h-10 px-3 text-[13px] rounded-[var(--radius-control)] [&_svg]:size-4',
        md: 'h-9 coarse:h-11 px-3.5 text-[13.5px] rounded-[var(--radius-control)] [&_svg]:size-4',
        lg: 'h-12 px-5 text-[15px] rounded-[var(--radius-card)] [&_svg]:size-[18px]',
        icon: 'size-9 coarse:size-11 rounded-[var(--radius-control)] [&_svg]:size-[18px]',
        'icon-sm': 'size-8 coarse:size-10 rounded-[var(--radius-control)] [&_svg]:size-4',
      },
    },
    defaultVariants: { variant: 'outline', size: 'md' },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  loading?: boolean
}

// asChild is never combined with loading — Slot needs exactly one child and a
// spinner would break that. Nothing in the app does it today.
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, asChild = false, loading = false, disabled, children, ...props },
  ref,
) {
  const Comp = asChild ? Slot : 'button'
  return (
    <Comp
      ref={ref}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    >
      {loading && <Loader2 className="animate-spin" aria-hidden="true" />}
      {children}
    </Comp>
  )
})
