import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build to ./dist, which the FastAPI backend serves at /.
// During `npm run dev`, proxy the API to the running backend on :8000.
export default defineConfig({
  plugins: [react()],
  // The backend mounts this build at /static, so emitted asset URLs must be /static/…
  base: "/static/",
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
