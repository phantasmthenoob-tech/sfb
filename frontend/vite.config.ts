import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend runs separately (FastAPI on :8000) and is proxied in development
// so the dashboard can talk to it without CORS on the preview origin.

// Only the hostname of the machine serving this dev server is injected.
declare const process: { env: Record<string, string | undefined> };
const previewHost = process.env.PREVIEW_HOST;

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    strictPort: true,
    // Only the current cloud preview hostname, supplied per-process.
    allowedHosts: previewHost ? [previewHost] : [],
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
