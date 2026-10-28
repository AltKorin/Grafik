import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // No data: URIs — CSP allows fonts/images only from our own origin (Caddyfile).
  build: { assetsInlineLimit: 0 },
  server: { proxy: Object.fromEntries(["/api", "/admin", "/static"].map((p) => [p, process.env.API ?? "http://127.0.0.1:8000"])) },
});
