import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";

export default function Login() {
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
      navigate("/chat");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="card" onSubmit={onSubmit}>
        <h1>CampusBrain AI</h1>
        <p className="muted">Sign in to ask questions about your institution's documents.</p>

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
          No account? <Link to="/register">Register as a student</Link>
        </p>
      </form>
    </div>
  );
}
