import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api, clearToken, getToken, setToken } from "../api/client";

type User = { id: number; org_id: number; email: string; role: string };

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  login: (orgId: number, email: string, password: string) => Promise<void>;
  register: (orgId: number, email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore the session on refresh: the token lives in localStorage, so
  // re-fetch the user it belongs to (and drop it if it's expired).
  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setLoading(false));
  }, []);

  const login = async (orgId: number, email: string, password: string) => {
    const { access_token } = await api.login(orgId, email, password);
    setToken(access_token);
    setUser(await api.me());
  };

  const register = async (orgId: number, email: string, password: string) => {
    await api.register(orgId, email, password);
    await login(orgId, email, password);
  };

  const logout = () => {
    clearToken();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
