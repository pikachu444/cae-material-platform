import { chromium } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const output =
  process.env.CMP_DEMO_SCREENSHOT ?? "docs/17-evidence/images/historical-task-screenshots/t66-reverse-workflow-navigation.png";

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
  await page.goto(`${webUrl}/datasets/test-json`);
  const related = page.getByLabel("CMP-DEMO-DP780-TEST-JSON r1 related governed data");
  await related.getByRole("link", { name: "Open Workflow Explorer" }).click();
  await page.locator(".workflow-node-list").getByText(
    "DP780 OpenRadioss native material card",
    { exact: true },
  ).waitFor();
  await page.screenshot({ path: output, fullPage: true });
  console.log(`captured ${output}`);
} finally {
  await browser.close();
}
