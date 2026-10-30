import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Docker resolves `backend`; local development resolves localhost instead.
const proxy = {
  "/api": {
    target: process.env.API_PROXY_TARGET || "http://127.0.0.1:8000",
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ""),
  },
};
export default defineConfig({
  plugins: [react()],
  server: { host: "0.0.0.0", port: 5173, strictPort: true, proxy },
  preview: { host: "0.0.0.0", port: 5173, strictPort: true, proxy },
});
