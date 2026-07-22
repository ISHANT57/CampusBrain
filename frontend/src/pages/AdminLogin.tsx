import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Logo } from "../components/chat/Logo";
import { Button } from "../components/chat/ui/button";
import { Alert } from "../components/chat/ui/primitives";
import { useAuth } from "../hooks/useAuth";

const inputCls =
  "h-10 w-full rounded-[10px] border border-border bg-canvas px-3 text-[14px] text-ink outline-none transition-colors placeholder:text-faint focus:border-accent focus:ring-4 focus:ring-accent-soft";

// Wrapping the input in the label (instead of a bare <label>text</label>
// followed by an unrelated <input>) is what actually associates the two —
// the previous version had no htmlFor/id pairing at all, so a screen reader
// announced every field with no name.
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[12.5px] font-medium text-muted">{label}</span>
      {children}
    </label>
  );
}

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
    <div className="flex flex-1 items-center justify-center px-6 py-12">
      <div className="w-full max-w-[380px]">
        <div className="mb-7 flex flex-col items-center text-center">
          <Logo />
          <h1 className="mt-5 text-[19px] font-medium tracking-[-0.01em] text-ink">Admin sign in</h1>
          <p className="mt-1.5 text-[13.5px] leading-[1.5] text-muted">
            Staff access for managing the knowledge base.
          </p>
        </div>

        <form
          onSubmit={onSubmit}
          className="rounded-[16px] border border-border bg-surface p-6 shadow-[var(--shadow-card)]"
        >
          <div className="flex flex-col gap-4">
            <Field label="Organization ID">
              <input
                value={orgId}
                onChange={(e) => setOrgId(e.target.value)}
                required
                inputMode="numeric"
                className={inputCls}
              />
            </Field>
            <Field label="Email">
              <input
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className={inputCls}
              />
            </Field>
            <Field label="Password">
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className={inputCls}
              />
            </Field>
          </div>

          {error && <Alert className="mt-4" title="Couldn't sign you in" description={error} />}

          <Button type="submit" variant="primary" size="lg" loading={busy} className="mt-5 w-full">
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-5 text-center text-[13px] text-faint">
          Looking for the chatbot?{" "}
          <Link to="/" className="font-medium text-accent hover:underline">
            Ask a question
          </Link>
        </p>
      </div>
    </div>
  );
}
