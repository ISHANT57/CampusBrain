import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { useAuth } from "./hooks/useAuth";
import AdminLogin from "./pages/AdminLogin";
import Chat from "./pages/Chat";
import Upload from "./pages/Upload";

const ADMIN_ROLES = ["admin", "super_admin"];

function AdminShell() {
  const { user, logout } = useAuth();
  return (
    <div className="shell">
      <header>
        <span className="brand">CampusBrain Admin</span>
        <span className="user">
          {user!.email} <em>({user!.role})</em>
          <button className="link" onClick={logout}>
            Sign out
          </button>
        </span>
      </header>
      <main>
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
  if (loading) return <p className="center muted">Loading…</p>;
  if (!user) return <Navigate to="/admin/login" replace />;
  return ADMIN_ROLES.includes(user.role) ? <AdminShell /> : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <Routes>
      {/* Public: no token, no account, no redirect — a student lands here and
          can ask immediately. */}
      <Route path="/" element={<Chat />} />
      <Route path="/admin/login" element={<AdminLogin />} />
      <Route element={<AdminRoute />}>
        <Route path="/admin" element={<Upload />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
