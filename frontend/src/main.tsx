import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./hooks/useAuth";
import { ThemeProvider } from "./hooks/useTheme";
import "./index.css";
import "./theme.css";

// Registered after load so it never competes with the app's own first paint.
// Dev is excluded deliberately: a service worker caching a Vite dev server's
// module graph makes hot reload behave unpredictably.
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", async () => {
    try {
      const reg = await navigator.serviceWorker.register("/sw.js");
      // This build's hashed JS/CSS were already fetched before the worker
      // existed, so it never got to cache them. Hand it the list explicitly,
      // otherwise the shell boots offline but its own scripts 404.
      const urls = [
        ...document.querySelectorAll<HTMLScriptElement | HTMLLinkElement>(
          'script[src], link[rel="stylesheet"]',
        ),
      ]
        .map((el) => ("src" in el ? el.src : el.href))
        .filter((u) => u.startsWith(location.origin));

      await navigator.serviceWorker.ready;
      reg.active?.postMessage({ type: "CACHE_ASSETS", urls });
    } catch {
      // Registration failing (private mode, unsupported browser, blocked by
      // policy) costs the install prompt and nothing else — the app works.
    }
  });
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
