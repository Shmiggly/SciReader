import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: Vite on 5173 proxies /api to the backend on 8765. Prod: the backend serves dist/.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
  build: { chunkSizeWarningLimit: 4000 },
});
