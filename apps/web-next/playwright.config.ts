import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [
    ["list"],
    ["json", { outputFile: "../../.artifacts/frontend-redesign-prototype/playwright.json" }],
  ],
  outputDir: "../../.artifacts/frontend-redesign-prototype/playwright-output",
  use: {
    baseURL: "http://127.0.0.1:5175",
    deviceScaleFactor: 1,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "off",
  },
  webServer: {
    command: "npm run dev:prototype -- --port 5175",
    url: "http://127.0.0.1:5175/",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
