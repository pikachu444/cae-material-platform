import { chromium } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const evidenceOutput =
  process.env.CMP_T69_RECIPE_EVIDENCE_SCREENSHOT ??
  "docs/17-evidence/images/historical-task-screenshots/t69-polymer-recipe-batch-evidence.png";
const monitorOutput =
  process.env.CMP_T69_BATCH_MONITOR_SCREENSHOT ??
  "docs/17-evidence/images/historical-task-screenshots/t69-polymer-recipe-batch-monitor.png";

const browser = await chromium.launch();
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 1.25,
  });
  const tokenResponse = await context.request.get(`${webUrl}/api/v1/demo-identity/token`);
  if (!tokenResponse.ok()) throw new Error("local demo identity is unavailable");
  const { access_token: accessToken } = await tokenResponse.json();
  const headers = { Authorization: `Bearer ${accessToken}` };
  const materialsResponse = await context.request.get(`${webUrl}/api/v1/materials?limit=100`, {
    headers,
  });
  if (!materialsResponse.ok()) throw new Error("demo Material catalog is unavailable");
  const { items } = await materialsResponse.json();
  const polymer = items.find(
    (item) => item.current_revision.content.material_code === "CMP-DEMO-POLYMER-PRONY",
  );
  if (!polymer) throw new Error("CMP-DEMO-POLYMER-PRONY is not seeded");

  const page = await context.newPage();
  await page.addInitScript(
    ({ token }) => {
      window.localStorage.setItem(
        "cmp.material-platform.api-config",
        JSON.stringify({ baseUrl: "/api/v1", accessToken: token }),
      );
    },
    { token: accessToken },
  );

  await page.goto(`${webUrl}/materials/${polymer.material_id}/models`);
  await page.locator(".app-header").evaluate((header) => {
    header.style.position = "static";
  });
  const workbench = page.locator(".reference-linear-viscoelastic-workbench");
  await workbench.getByText("automatic_bic", { exact: true }).waitFor();
  await workbench.getByText(/Loaded exact Neutral Material JSON r1/).waitFor();
  await workbench.getByText("Successful Batch attempt", { exact: true }).waitFor();
  await page.locator(".viscoelastic-result").screenshot({ path: evidenceOutput });

  await page.goto(`${webUrl}/datasets/processing`);
  await page.locator(".app-header").evaluate((header) => {
    header.style.position = "static";
  });
  const monitor = page.locator(".batch-monitor-card");
  await monitor.getByText("CMP demo polymer Prony batch", { exact: true }).waitFor();
  await monitor.getByText("succeeded", { exact: true }).first().waitFor();
  await monitor.screenshot({ path: monitorOutput });

  console.log(`captured ${evidenceOutput}`);
  console.log(`captured ${monitorOutput}`);
} finally {
  await browser.close();
}
