import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Set by Codespaces and passed into the container by docker-compose. Empty
// when running Docker locally, which is what we want — the HMR overrides
// below only apply behind the Codespaces HTTPS proxy.
const codespace = process.env.CODESPACE_NAME;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    // Vite 5.4.12+ rejects any request whose Host header isn't localhost (a
    // DNS-rebinding guard). Codespaces serves this app from
    // <name>-5173.app.github.dev, so without this every request 403s before it
    // reaches the app and the forwarded URL just looks "not found".
    // Leading dot = this domain and all its subdomains, so it keeps working
    // when the Codespace name changes.
    allowedHosts: [".app.github.dev"],
    // Behind the Codespaces HTTPS proxy the HMR socket has to go to
    // wss://<host>:443; the default ws://<host>:5173 can't get through, and hot
    // reload fails silently.
    hmr: codespace
      ? { protocol: "wss", host: `${codespace}-5173.app.github.dev`, clientPort: 443 }
      : undefined,
    // Same-origin API calls: browser hits /api/*, Vite forwards to the backend
    // container over the Docker network. Avoids CORS and works behind any
    // Codespaces/prod forwarded URL.
    // No rewrite: the backend serves its routes under /api/v1/* already, so
    // the path passes through unchanged.
    proxy: {
      "/api": {
        target: "http://backend:8000",
        changeOrigin: true,
      },
    },
  },
});
