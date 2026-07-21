import { Navigate, NavLink, Outlet, Route, Routes } from "react-router-dom";

import { useAuth } from "./hooks/useAuth";
import Chat from "./pages/Chat";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Upload from "./pages/Upload";

const UPLOAD_ROLES = ["faculty", "admin", "super_admin"];

function Shell() {
  const { user, logout } = useAuth();
  return (
    <div className="shell">
      <header>
        <span className="brand">CampusBrain AI</span>
        <nav>
          <NavLink to="/chat">Chat</NavLink>
          {UPLOAD_ROLES.includes(user!.role) && <NavLink to="/upload">Upload</NavLink>}
        </nav>
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

function ProtectedRoute() {
  const { user, loading } = useAuth();
  if (loading) return <p className="center muted">Loading…</p>;
  return user ? <Shell /> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/chat" element={<Chat />} />
        <Route path="/upload" element={<Upload />} />
      </Route>
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  );
}
