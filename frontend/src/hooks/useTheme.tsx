import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const KEY = "cb-chat-theme";

// App-wide now (originally scoped to the Chat page only, back when admin
// pages had their own separate dark-only CSS). One toggle, one persisted
// preference, everywhere.
type ThemeContextValue = { dark: boolean; toggle: () => void };

const ThemeContext = createContext<ThemeContextValue | null>(null);

// Must track theme.css's --canvas for each theme: installed on a phone, this
// is the colour of the status bar and the pull-to-refresh area, so a mismatch
// shows up as a visible band above the app.
const THEME_COLOR = { dark: "#0c0e12", light: "#fafafa" };

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [dark, setDark] = useState(() => localStorage.getItem(KEY) !== "light");
  useEffect(() => {
    localStorage.setItem(KEY, dark ? "dark" : "light");
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", dark ? THEME_COLOR.dark : THEME_COLOR.light);
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
