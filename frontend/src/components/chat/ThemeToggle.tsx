import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Moon, Sun } from 'lucide-react'
import { Button } from './ui/button'
import { Kbd, Tooltip } from './ui/primitives'
import { mod } from './lib/utils'

const KEY = 'cb-chat-theme'

// Scoped to the Chat page — toggles a class on this page's own wrapper,
// never <html>/<body>, so it never affects Login/Register/Upload.
export function useLocalTheme() {
  const [dark, setDark] = useState(() => localStorage.getItem(KEY) !== 'light')
  useEffect(() => {
    localStorage.setItem(KEY, dark ? 'dark' : 'light')
  }, [dark])
  return { dark, toggle: () => setDark((d) => !d) }
}

export function ThemeToggle({ dark, toggle }: { dark: boolean; toggle: () => void }) {
  return (
    <Tooltip
      label={
        <>
          {dark ? 'Light' : 'Dark'} mode <Kbd>{mod} J</Kbd>
        </>
      }
    >
      <Button
        variant="ghost"
        size="icon"
        onClick={toggle}
        aria-label={`Switch to ${dark ? 'light' : 'dark'} mode`}
        aria-pressed={dark}
        className="relative overflow-hidden"
      >
        <AnimatePresence initial={false} mode="wait">
          <motion.span
            key={dark ? 'moon' : 'sun'}
            initial={{ y: 12, opacity: 0, rotate: -25 }}
            animate={{ y: 0, opacity: 1, rotate: 0 }}
            exit={{ y: -12, opacity: 0, rotate: 25 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="flex"
          >
            {dark ? <Moon /> : <Sun />}
          </motion.span>
        </AnimatePresence>
      </Button>
    </Tooltip>
  )
}
