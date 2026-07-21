import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";

export default function Register() {
  const { register } = useAuth();
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
      await register(Number(orgId), email, password);
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
        <h1>Create account</h1>
        <p className="muted">
          Self-registration creates a Student account. Faculty and Admin accounts are created by an
          administrator.
        </p>

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

        <button disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
        <p className="muted">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
