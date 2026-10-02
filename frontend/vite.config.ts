/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const proxyTarget = env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: proxyTarget,
        },
        "/ws": {
          target: proxyTarget,
          ws: true,
        },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
    },
  };
});
