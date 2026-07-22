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

export const api = {
  register: (org_id: number, email: string, password: string) =>
    request("/auth/register", { method: "POST", body: JSON.stringify({ org_id, email, password }) }),

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

  chat: (question: string, conversationId: number | null) =>
    request("/chat", {
      method: "POST",
      body: JSON.stringify({ question, conversation_id: conversationId }),
    }),
};
