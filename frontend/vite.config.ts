import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
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
