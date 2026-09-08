import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  build: {
    outDir: mode === "prototype" ? "dist-prototype" : "dist",
    rollupOptions: {
      output: {
        manualChunks: (id) => id.includes("node_modules") && (id.includes("react") || id.includes("@tanstack/react-query")) ? "reader-vendor" : undefined,
      },
    },
  },
  server: {
    proxy: {
      "/api": {
        target: (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.CMP_API_PROXY_TARGET
          ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./vitest.setup.ts",
    include: ["src/**/*.test.{ts,tsx}"],
    testTimeout: 10_000,
  },
}));
