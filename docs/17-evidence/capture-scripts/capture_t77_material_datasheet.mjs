import { chromium } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const output =
  process.env.CMP_DEMO_SCREENSHOT ?? "docs/17-evidence/images/historical-task-screenshots/t77-material-datasheet.png";
const compareOutput =
  process.env.CMP_DEMO_COMPARE_SCREENSHOT
  ?? "docs/17-evidence/images/historical-task-screenshots/t77-material-search-compare.png";

const browser = await chromium.launch();
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const tokenResponse = await context.request.get(`${webUrl}/api/v1/demo-identity/token`);
  if (!tokenResponse.ok()) throw new Error("local demo identity is unavailable");
  const { access_token: accessToken } = await tokenResponse.json();
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
  await page.goto(`${webUrl}/database`);
  for (const name of ["Material Library", "Metals", "Steels", "DP780 Dual-Phase Steel"]) {
    await page.getByRole("button", { name: new RegExp(name) }).click();
  }
  await page.getByRole("button", { name: /DP780 synthetic demo steel/ }).click();
  await page.getByRole("tab", { name: "Datasheet" }).click();
  await page.getByText("Young's modulus", { exact: true }).first().waitFor();
  await page.screenshot({ path: output, fullPage: true });
  console.log(`captured ${output}`);
  await page.getByLabel("Search database").fill("DP780");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByRole("heading", { name: /matching records/ }).waitFor();
  await page.getByLabel("Compare DP780 synthetic demo steel").click();
  await page.getByLabel("Compare DP780 reference Material State").click();
  await page.getByRole("button", { name: "Compare 2" }).click();
  await page.getByRole("heading", { name: "Material overview" }).waitFor();
  await page.screenshot({ path: compareOutput, fullPage: true });
  console.log(`captured ${compareOutput}`);
} finally {
  await browser.close();
}
