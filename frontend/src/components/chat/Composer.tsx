import { forwardRef, useImperativeHandle, useLayoutEffect, useRef, useState } from 'react'
import { ArrowUp, Paperclip, Square } from 'lucide-react'
import { Button } from './ui/button'
import { Kbd, Tooltip } from './ui/primitives'
import { mod } from './lib/utils'

export interface ComposerHandle {
  focus: () => void
}

const MAX_HEIGHT = 200

export const Composer = forwardRef<
  ComposerHandle,
  {
    onSubmit: (text: string) => void
    onStop: () => void
    streaming: boolean
    placeholder?: string
    /** Names the organization in the screen-reader label for the input. */
    orgName?: string
  }
>(function Composer({ onSubmit, onStop, streaming, placeholder, orgName }, ref) {
  const [value, setValue] = useState('')
  const ta = useRef<HTMLTextAreaElement>(null)

  useImperativeHandle(ref, () => ({ focus: () => ta.current?.focus() }))

  // Auto-grow: collapse to 0 first so scrollHeight reports the content height
  // rather than the previously-set height, then clamp.
  useLayoutEffect(() => {
    const el = ta.current
    if (!el) return
    el.style.height = '0px'
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`
    el.style.overflowY = el.scrollHeight > MAX_HEIGHT ? 'auto' : 'hidden'
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
      className="group relative rounded-[var(--radius-composer)] border border-border bg-surface shadow-[var(--shadow-float)] transition-[border-color,box-shadow] duration-200 ease-out focus-within:border-accent focus-within:shadow-[0_0_0_4px_var(--accent-soft),var(--shadow-float)]"
    >
      <label htmlFor="cb-composer" className="sr-only">
        Ask a question about {orgName ?? 'the knowledge base'}
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
        placeholder={placeholder ?? 'Ask a follow-up question…'}
        className="block max-h-[200px] w-full resize-none bg-transparent px-5 pt-4 text-[15px] leading-[1.6] text-ink outline-none placeholder:text-faint"
      />

      <div className="flex items-center gap-2 px-3 pb-3 pt-2">
        <Tooltip label="Uploading is done from the admin portal">
          {/* Decorative, not a control — cursor stays default so it doesn't
              read as clickable next to buttons that are. */}
          <span
            aria-hidden="true"
            className="flex size-8 cursor-default items-center justify-center rounded-[var(--radius-control)] text-faint/60"
          >
            <Paperclip className="size-[18px]" />
          </span>
        </Tooltip>

        <p className="hidden items-center gap-1.5 text-[11.5px] text-faint sm:flex">
          <Kbd>Enter</Kbd> to send
          <span className="text-border-strong">·</span>
          <Kbd>Shift Enter</Kbd> new line
        </p>

        <div className="ml-auto flex items-center gap-2">
          {streaming ? (
            <Button type="button" variant="outline" size="sm" onClick={onStop}>
              <Square className="size-3 fill-current" />
              Stop
              <Kbd className="ml-0.5 hidden sm:inline-flex">Esc</Kbd>
            </Button>
          ) : (
            <Tooltip label="Send message" side="top">
              <Button
                type="submit"
                variant="accent"
                size="icon-sm"
                disabled={!value.trim()}
                aria-label="Send message"
                className="rounded-full"
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
