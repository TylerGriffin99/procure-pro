import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    allowedHosts: true,
    proxy: {
      // Native dev defaults to the backend on localhost:8000; in Docker the
      // compose file sets VITE_API_PROXY to the api service (http://api:8000).
      "/api": process.env.VITE_API_PROXY || "http://localhost:8000",
    },
  },
});
