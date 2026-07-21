const TOKEN_KEY = "campusbrain_token";

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

  const res = await fetch(`/api/v1${path}`, { ...options, headers });
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
