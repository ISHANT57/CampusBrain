import { useEffect, useState } from "react";

export default function App() {
  const [status, setStatus] = useState("checking…");

  useEffect(() => {
    // Same-origin: Vite dev-proxies /api/* to the backend (see vite.config.ts).
    fetch("/api/health")
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
