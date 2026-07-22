import { chromium } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const output =
  process.env.CMP_T70_METAL_RECIPE_SCREENSHOT ??
  "docs/17-evidence/images/t70-metal-recipe-batch-evidence.png";

const browser = await chromium.launch();
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 1.25,
  });
  const tokenResponse = await context.request.get(`${webUrl}/api/v1/demo-identity/token`);
  if (!tokenResponse.ok()) throw new Error("local demo identity is unavailable");
  const { access_token: accessToken } = await tokenResponse.json();
  const materialsResponse = await context.request.get(`${webUrl}/api/v1/materials?limit=100`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!materialsResponse.ok()) throw new Error("demo Material catalog is unavailable");
  const { items } = await materialsResponse.json();
  const metal = items.find(
    (item) => item.current_revision.content.material_code === "CMP-DEMO-DP780",
  );
  if (!metal) throw new Error("CMP-DEMO-DP780 is not seeded");

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
  await page.goto(`${webUrl}/materials/${metal.material_id}/models`);
  await page.locator(".app-header").evaluate((header) => {
    header.style.position = "static";
  });
  const workbench = page.locator(".reference-elastoplastic-workbench");
  const open = workbench.getByRole("button", { name: "Build an elastoplastic Solver Card" });
  await open.waitFor();
  await open.click();
  const modelSelect = workbench.getByLabel("Tabulated-plasticity IR revision");
  await modelSelect.waitFor();
  const processedOption = modelSelect.locator("option").filter({ hasText: "Processing Output" });
  const processedModelId = await processedOption.getAttribute("value");
  if (!processedModelId) throw new Error("processed metal IR is not available");
  await modelSelect.selectOption(processedModelId);
  await workbench.getByText(/Published Recipe revision:/).waitFor();
  await workbench.getByText(/Successful Batch attempt #1/).waitFor();
  await workbench.getByRole("link", { name: "Open Recipe library and Batch monitor" }).waitFor();
  await workbench.screenshot({ path: output });
  console.log(`captured ${output}`);
} finally {
  await browser.close();
}
