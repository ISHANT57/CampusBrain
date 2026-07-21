import { useState, type FormEvent } from "react";

import { api } from "../api/client";

type Citation = {
  index: number;
  document_id: number;
  filename: string;
  page_number: number;
  excerpt: string;
};

type Turn = { role: "user" | "assistant"; content: string; citations?: Citation[] };

export default function Chat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;

    setTurns((t) => [...t, { role: "user", content: q }]);
    setQuestion("");
    setError("");
    setBusy(true);
    try {
      const res = await api.chat(q, conversationId);
      setConversationId(res.conversation_id);
      setTurns((t) => [...t, { role: "assistant", content: res.answer, citations: res.citations }]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="chat">
      <div className="messages">
        {turns.length === 0 && (
          <p className="muted center">
            Ask a question about your institution's documents — answers are grounded in uploaded
            sources and cite them.
          </p>
        )}

        {turns.map((turn, i) => (
          <div key={i} className={`bubble ${turn.role}`}>
            <div className="bubble-text">{turn.content}</div>

            {turn.citations && turn.citations.length > 0 && (
              <div className="citations">
                <div className="citations-title">Sources</div>
                {turn.citations.map((c) => (
                  <div key={c.index} className="citation">
                    <strong>
                      [{c.index}] {c.filename} — page {c.page_number}
                    </strong>
                    <p>{c.excerpt}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {busy && <div className="bubble assistant muted">Thinking…</div>}
        {error && <p className="error">{error}</p>}
      </div>

      <form className="composer" onSubmit={onSubmit}>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Who founded the university?"
          disabled={busy}
        />
        <button disabled={busy || !question.trim()}>Ask</button>
      </form>
    </div>
  );
}
