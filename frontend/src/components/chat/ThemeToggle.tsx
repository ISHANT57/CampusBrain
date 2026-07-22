import { AnimatePresence, motion } from 'framer-motion'
import { Moon, Sun } from 'lucide-react'
import { Button } from './ui/button'
import { Kbd, Tooltip } from './ui/primitives'
import { mod } from './lib/utils'

// The dark/light state itself lives in ../../hooks/useTheme (app-wide, since
// admin pages now share this same design system) — this component is just
// the button.
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
