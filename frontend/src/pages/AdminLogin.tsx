import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";

export default function AdminLogin() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [orgId, setOrgId] = useState("1");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(Number(orgId), email, password);
      navigate("/admin");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="card" onSubmit={onSubmit}>
        <h1>CampusBrain Admin</h1>
        {/* No "create an account" link on purpose: accounts are created with
            backend/scripts/create_admin.py, never through the browser. */}
        <p className="muted">Staff sign-in for managing the knowledge base.</p>

        <label>Organization ID</label>
        <input value={orgId} onChange={(e) => setOrgId(e.target.value)} required />

        <label>Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />

        <label>Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        {error && <p className="error">{error}</p>}

        <button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <p className="muted">
          Looking for the chatbot? <Link to="/">Ask a question</Link>
        </p>
      </form>
    </div>
  );
}
