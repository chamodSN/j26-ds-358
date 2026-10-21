import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// The Google Client ID is read from the ROOT .env (one folder up) or from the
// GOOGLE_CLIENT_ID build argument in Docker. It is public, so baking it in is fine.
export default defineConfig(({ mode }) => {
  const rootDir = fileURLToPath(new URL("..", import.meta.url));
  const env = loadEnv(mode, rootDir, "");
  return {
    plugins: [react()],
    define: {
      __GOOGLE_CLIENT_ID__: JSON.stringify(env.GOOGLE_CLIENT_ID || ""),
    },
    server: {
      port: 5173,
      proxy: { "/api": "http://localhost:8000" },
    },
  };
});