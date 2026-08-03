import type { Citation } from "../components/chat/types";

const TOKEN_KEY = "campusbrain_token";

// Empty by default: same-origin (dev's Vite proxy, or nginx in the VPS path)
// resolves "/api/v1/..." against its own host with no change in behavior.
// Deploying frontend and backend to different origins (Vercel + Render)
// requires this — set VITE_API_BASE_URL to the Render backend's URL at
// build time, or every request here would target Vercel's own domain
// instead of the backend and 404.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

async function request(path: string, options: RequestInit = {}) {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}/api/v1${path}`, { ...options, headers });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}

export type ChatTurn = { role: "user" | "assistant"; content: string };

// Mirrors backend/app/api/v1/chat.py's _stream_events exactly: every event up
// to the last is a raw, UN-renumbered fragment of model output (a "typing"
// UI has nothing else to show yet); the last carries the final renumbered
// answer and the citations that go with those numbers. citations is only
// ever populated on "done" — the backend can't renumber [n] markers until it
// has seen the whole answer, so there is nothing correct to send earlier.
export type ChatStreamEvent =
  | { type: "delta"; text: string }
  | { type: "done"; answer: string; citations: Citation[] };

// SSE-over-fetch, not EventSource: EventSource is GET-only with no request
// body, and the question + conversation history have to travel in a POST
// body. The wire format needs no more than that — one "data: {json}\n\n"
// frame per event, no "event:"/"id:" lines, no reconnection semantics to
// replicate (a dropped connection here means "let the user hit Send again",
// not "resume a partial answer").
async function* chatStream(
  orgSlug: string,
  question: string,
  history: ChatTurn[],
  signal: AbortSignal,
): AsyncGenerator<ChatStreamEvent, void, undefined> {
  const token = getToken();
  const headers = new Headers({ "Content-Type": "application/json" });
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE}/api/v1/chat/stream/${encodeURIComponent(orgSlug)}`, {
    method: "POST",
    headers,
    body: JSON.stringify({ question, history }),
    signal,
  });

  if (!res.ok) {
    // A 404 (unknown org) or a 429 (rate limit) is resolved by the backend
    // BEFORE it ever opens the SSE body, so this is a normal JSON error
    // response, not a stream — same shape request() already handles.
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `Request failed (${res.status})`);
  }
  if (!res.body) {
    throw new Error("Streaming responses are not supported in this browser.");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // A network chunk boundary doesn't have to land on an SSE frame
      // boundary, so buffer across reads and only consume complete frames
      // ("\n\n"-terminated). Anything left over when the stream ends is an
      // incomplete trailing frame -- discarded rather than JSON.parse'd,
      // which would throw on a truncated body instead of just stopping.
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        for (const line of frame.split("\n")) {
          if (line.startsWith("data: ")) {
            yield JSON.parse(line.slice("data: ".length)) as ChatStreamEvent;
          }
        }
      }
    }
  } finally {
    // Runs whether the stream ended normally, was aborted (Stop button /
    // navigating away), or a parse error unwound the loop -- always release
    // the underlying connection rather than leaking it.
    reader.cancel().catch(() => {});
  }
}

export const api = {
  login: (org_id: number, email: string, password: string) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ org_id, email, password }) }),

  me: () => request("/auth/me"),

  uploadDocument: (file: File, collectionId?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (collectionId) form.append("collection_id", collectionId);
    return request("/documents", { method: "POST", body: form });
  },

  getDocument: (id: number) => request(`/documents/${id}`),

  // Public — no token needed. The backend keeps no transcript for anonymous
  // students, so prior turns travel with the question (the sidebar was
  // already localStorage-only; this just forwards what it holds).
  //
  // orgSlug picks which organization's documents are searched, and must match
  // an organizations.slug row — the backend 404s otherwise. It is a path
  // segment rather than a body field so each tenant's chatbot has its own URL
  // end to end, browser address bar through to server log.
  chatStream,
};
