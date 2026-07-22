import { PanelLeft, Search } from 'lucide-react'
import { Button } from './ui/button'
import { Kbd, Tooltip } from './ui/primitives'
import { ThemeToggle } from './ThemeToggle'
import { mod } from './lib/utils'

/* 64px tall to match the sidebar's logo row, so the two align across the
   divider instead of meeting at a seam. */
export function Header({
  title,
  subtitle,
  sidebarOpen,
  onOpenSidebar,
  onOpenSearch,
  dark,
  onToggleTheme,
}: {
  title: string
  subtitle: string
  sidebarOpen: boolean
  onOpenSidebar: () => void
  onOpenSearch: () => void
  dark: boolean
  onToggleTheme: () => void
}) {
  return (
    <header
      data-safe-x
      className="flex h-16 shrink-0 items-center gap-3 border-b border-border bg-canvas/80 px-4 backdrop-blur-md sm:px-6"
    >
      {!sidebarOpen && (
        <Tooltip label={<>Show sidebar <Kbd>{mod} B</Kbd></>}>
          <Button variant="ghost" size="icon-sm" onClick={onOpenSidebar} aria-label="Show sidebar">
            <PanelLeft />
          </Button>
        </Tooltip>
      )}

      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[14.5px] font-semibold leading-tight tracking-[-0.01em] text-ink">
          {title}
        </h1>
        <p className="truncate text-[12px] leading-tight text-muted">{subtitle}</p>
      </div>

      <div className="flex shrink-0 items-center gap-1">
        <Button variant="ghost" size="sm" onClick={onOpenSearch} className="gap-2">
          <Search />
          <span className="hidden sm:inline">Search</span>
          <Kbd className="hidden sm:inline-flex">{mod} K</Kbd>
        </Button>
        <ThemeToggle dark={dark} toggle={onToggleTheme} />
      </div>
    </header>
  )
}
