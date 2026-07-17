import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API calls to the FastAPI backend (run separately via
// `uvicorn app.main:app --reload --port 8090`). The production build is
// copied into the backend's app/static/ dir and served by FastAPI itself,
// so no proxy is needed there — same origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/incidents": "http://localhost:8090",
      "/findings": "http://localhost:8090",
      "/health": "http://localhost:8090",
    },
  },
  build: {
    outDir: "dist",
  },
});
