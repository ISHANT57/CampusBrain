import { forwardRef, useImperativeHandle, useLayoutEffect, useRef, useState } from 'react'
import { ArrowUp, Paperclip, Square } from 'lucide-react'
import { Button } from './ui/button'
import { Kbd, Tooltip } from './ui/primitives'
import { cn, mod } from './lib/utils'

export interface ComposerHandle {
  focus: () => void
}

export const Composer = forwardRef<
  ComposerHandle,
  {
    onSubmit: (text: string) => void
    onStop: () => void
    streaming: boolean
    placeholder?: string
  }
>(function Composer({ onSubmit, onStop, streaming, placeholder }, ref) {
  const [value, setValue] = useState('')
  const ta = useRef<HTMLTextAreaElement>(null)

  useImperativeHandle(ref, () => ({ focus: () => ta.current?.focus() }))

  useLayoutEffect(() => {
    const el = ta.current
    if (!el) return
    el.style.height = '0px'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [value])

  const submit = () => {
    const v = value.trim()
    if (!v || streaming) return
    onSubmit(v)
    setValue('')
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
      className="group relative rounded-[20px] border border-border bg-surface shadow-[var(--shadow-card)] transition-[border-color,box-shadow] duration-200 focus-within:border-accent/50 focus-within:shadow-[0_0_0_4px_var(--color-accent-soft)]"
    >
      <label htmlFor="cb-composer" className="sr-only">
        Ask a question about your institution's documents
      </label>
      <textarea
        id="cb-composer"
        ref={ta}
        rows={1}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            submit()
          }
        }}
        placeholder={placeholder ?? "e.g. Who founded the university?"}
        className="block w-full resize-none bg-transparent px-4 pt-3.5 text-[15px] leading-[1.55] text-ink outline-none placeholder:text-faint"
      />

      <div className="flex items-center gap-2 px-3 pb-3 pt-2">
        <Tooltip label="Uploading is done from the Upload page">
          <span
            aria-hidden="true"
            className="flex size-8 items-center justify-center rounded-[8px] text-faint"
          >
            <Paperclip className="size-4" />
          </span>
        </Tooltip>

        <p className="hidden items-center gap-1.5 text-[11px] text-faint sm:flex">
          <Kbd>Enter</Kbd> to send
          <span className="text-border-strong">·</span>
          <Kbd>Shift Enter</Kbd> new line
        </p>

        <div className="ml-auto flex items-center gap-2">
          {streaming ? (
            <Button type="button" variant="outline" size="sm" onClick={onStop}>
              <Square className="fill-current" />
              Stop
              <Kbd className="ml-0.5 hidden sm:inline-flex">Esc</Kbd>
            </Button>
          ) : (
            <Tooltip label={<>Send · {mod} Enter</>} side="top">
              <Button
                type="submit"
                variant="primary"
                size="icon-sm"
                disabled={!value.trim()}
                aria-label="Send message"
                className={cn('rounded-full')}
              >
                <ArrowUp />
              </Button>
            </Tooltip>
          )}
        </div>
      </div>
    </form>
  )
})
