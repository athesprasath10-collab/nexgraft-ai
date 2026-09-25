import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the Vite dev server (http://localhost:5173) proxies API calls
// to the Python backend. In production FastAPI serves the built `dist/` folder.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: false },
    },
  },
  build: {
    outDir: "dist",
    chunkSizeWarningLimit: 2500,
  },
});
