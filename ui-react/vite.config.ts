// Forge React UI. `npm run dev` serves it on 127.0.0.1:5173 and forwards the API and the event socket to a
// Forge started with `forge ui --react --dev` (port 8766); `npm run build` writes the static files that
// `forge ui --react` serves — no Node.js is needed to use Forge.
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

const FORGE = process.env.FORGE_URL ?? "http://127.0.0.1:8766";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: FORGE, changeOrigin: true },
      "/ws": { target: FORGE.replace("http", "ws"), ws: true, changeOrigin: true },
    },
  },
  build: {
    outDir: "../src/forge/web/react",
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
  },
});
