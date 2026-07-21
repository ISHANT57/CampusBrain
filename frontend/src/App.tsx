import { useEffect, useState } from "react";

// Overridable per environment (Codespaces forwarded URL, prod, etc.).
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  const [status, setStatus] = useState("checking…");

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((r) => r.json())
      .then((d) => setStatus(d.status))
      .catch((e) => setStatus(`error: ${e.message}`));
  }, []);

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>CampusBrain AI</h1>
      <p>
        Backend health: <strong>{status}</strong>
      </p>
    </main>
  );
}
