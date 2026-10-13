import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Development only: the browser talks to one origin (http://127.0.0.1:5173). /api and /auth are forwarded to the
// loopback backend, which checks Origin against that exact value; no CORS is enabled anywhere. The OIDC redirect
// URI itself is registered on the backend (http://127.0.0.1:8000/auth/callback). Always use 127.0.0.1, never localhost.
const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: backend, changeOrigin: false },
      "/auth": { target: backend, changeOrigin: false },
    },
  },
});
