import { useEffect, useRef, useState } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { Loader2, LogOut } from "lucide-react";

import { useAuth } from "./hooks/useAuth";
import { useTheme } from "./hooks/useTheme";
import { Logo } from "./components/chat/Logo";
import { ThemeToggle } from "./components/chat/ThemeToggle";
import { Button } from "./components/chat/ui/button";
import { Tooltip } from "./components/chat/ui/primitives";
import { cn } from "./components/chat/lib/utils";
import AdminLogin from "./pages/AdminLogin";
import Chat from "./pages/Chat";
import Upload from "./pages/Upload";

const ADMIN_ROLES = ["admin", "super_admin"];

function AdminShell() {
  const { user, logout } = useAuth();
  const { dark, toggle } = useTheme();
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border px-5">
        <Logo context="Admin" />
        <div className="ml-auto flex items-center gap-1">
          <ThemeToggle dark={dark} toggle={toggle} />
          <div className="mx-1.5 h-5 w-px bg-border" aria-hidden="true" />
          <div className="flex items-center gap-2.5 pl-0.5">
            <span
              className="flex size-7 shrink-0 items-center justify-center rounded-full bg-accent-soft font-mono text-[11px] font-medium text-accent"
              aria-hidden="true"
            >
              {user!.email[0]!.toUpperCase()}
            </span>
            <span className="hidden flex-col leading-tight sm:flex">
              <span className="max-w-[200px] truncate text-[13px] font-medium text-ink">
                {user!.email}
              </span>
              <span className="text-[11px] capitalize text-faint">{user!.role.replace("_", " ")}</span>
            </span>
          </div>
          <Tooltip label="Sign out">
            <Button variant="ghost" size="icon-sm" onClick={logout} aria-label="Sign out">
              <LogOut />
            </Button>
          </Tooltip>
        </div>
      </header>
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}

// The real enforcement is server-side — every /documents and /search route
// requires an admin token. This only decides what the browser bothers to
// render, so someone poking at /admin gets the login page rather than a
// screen full of 403s.
function AdminRoute() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center gap-2 text-[13.5px] text-muted">
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        Loading…
      </div>
    );
  }
  if (!user) return <Navigate to="/admin/login" replace />;
  return ADMIN_ROLES.includes(user.role) ? <AdminShell /> : <Navigate to="/" replace />;
}

export default function App() {
  const { dark } = useTheme();

  // Radix/cmdk portal their dialogs to document.body by default, which is
  // outside .cb-scope — every --surface/--ink/--border token would be
  // undefined there. This ref gives Chat's dialogs (sidebar drawer, command
  // palette, shortcuts) a real themed element to portal into instead. See
  // Chat.tsx for where it's consumed.
  const scopeRef = useRef<HTMLDivElement>(null);
  const [scopeReady, setScopeReady] = useState(false);
  useEffect(() => setScopeReady(true), []);
  const portalTarget = scopeReady ? scopeRef.current : null;

  return (
    /* h-dvh, not min-h-dvh: the chat's thread and the admin shell's main
       both scroll internally, so the app frame must be exactly one viewport
       tall. With min-h- the frame grew past the viewport instead, which
       scrolled the whole page and pushed the composer below the fold. */
    <div ref={scopeRef} className={cn("cb-scope flex h-dvh flex-col overflow-hidden", dark && "dark")}>
      <Routes>
        {/* Public: no token, no account, no redirect — a student lands here
            and can ask immediately. */}
        <Route path="/" element={<Chat portalTarget={portalTarget} />} />
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route element={<AdminRoute />}>
          <Route path="/admin" element={<Upload />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
