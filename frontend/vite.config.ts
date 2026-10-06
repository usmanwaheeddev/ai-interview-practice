/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";

function blockProcRequests(): Plugin {
  return {
    name: "block-proc-requests",
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        if (request.url?.startsWith("/proc/")) {
          response.statusCode = 404;
          response.end();
          return;
        }
        next();
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const proxyTarget = env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [blockProcRequests(), react()],
    server: {
      port: 5173,
      fs: {
        strict: true,
        allow: ["."],
      },
      watch: {
        ignored: ["**/proc/**"],
      },
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
