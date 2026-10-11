import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the browser talks to /api, which Vite forwards to the local Python server
// (see backend: `make api`). In production set VITE_API_BASE_URL to the API Gateway URL.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8787",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  build: {
    sourcemap: true,
    target: "es2022",
  },
});
