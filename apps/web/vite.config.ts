import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, ".", "");
  const runtimeEnvironment = (
    globalThis as typeof globalThis & {
      process?: { env?: Record<string, string | undefined> };
    }
  ).process?.env;
  const apiTarget =
    runtimeEnvironment?.VITE_CMP_API_TARGET ??
    environment.VITE_CMP_API_TARGET ??
    "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.endsWith("/engineering-curve-plot.tsx")) {
              return "engineering-curve-plot";
            }
          },
        },
      },
    },
    server: {
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      include: ["src/**/*.test.{ts,tsx}"],
      testTimeout: 10_000,
    },
  };
});
