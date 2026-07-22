import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const KEY = "cb-chat-theme";

// App-wide now (originally scoped to the Chat page only, back when admin
// pages had their own separate dark-only CSS). One toggle, one persisted
// preference, everywhere.
type ThemeContextValue = { dark: boolean; toggle: () => void };

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [dark, setDark] = useState(() => localStorage.getItem(KEY) !== "light");
  useEffect(() => {
    localStorage.setItem(KEY, dark ? "dark" : "light");
  }, [dark]);
  return (
    <ThemeContext.Provider value={{ dark, toggle: () => setDark((d) => !d) }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
