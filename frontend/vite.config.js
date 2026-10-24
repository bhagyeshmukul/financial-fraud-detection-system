/** Compile React and proxy local API requests, keeping browser calls on one origin. */
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      // Compose uses backend:8000; native development uses a loopback API target.
      "/api": {
        target: process.env.API_PROXY_TARGET || "http://127.0.0.1:8000",
      },
      "/health": {
        target: process.env.API_PROXY_TARGET || "http://127.0.0.1:8000",
      },
    },
  },
});
