import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { Loader2 } from 'lucide-react'
import { cn } from '../lib/utils'

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium transition-[background-color,border-color,color,box-shadow,transform] duration-150 disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:shrink-0 active:scale-[0.985] motion-reduce:active:scale-100 select-none",
  {
    variants: {
      variant: {
        primary: 'bg-ink text-canvas hover:bg-ink/90 shadow-[0_1px_2px_rgb(0_0_0/0.08)]',
        accent: 'bg-accent text-accent-fg hover:brightness-110',
        outline: 'border border-border bg-surface text-ink hover:bg-sunken hover:border-border-strong',
        ghost: 'text-muted hover:bg-sunken hover:text-ink',
        subtle: 'bg-sunken text-ink hover:bg-border/60',
      },
      size: {
        sm: 'h-8 px-3 text-[13px] rounded-[8px] [&_svg]:size-3.5',
        md: 'h-9 px-3.5 text-[14px] rounded-[10px] [&_svg]:size-4',
        lg: 'h-11 px-5 text-[15px] rounded-[12px] [&_svg]:size-[18px]',
        icon: 'size-9 rounded-[10px] [&_svg]:size-[18px]',
        'icon-sm': 'size-8 rounded-[8px] [&_svg]:size-4',
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

// asChild is never combined with loading anywhere in this app — Slot needs
// exactly one child, and a spinner would break that. Not guarded for, since
// nothing today calls Button asChild with loading=true.
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
