import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "../../.cache/playwright",
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173",
    viewport: { width: 1440, height: 900 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
