import { chromium } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const output = process.env.CMP_DEMO_SCREENSHOT
  ?? "docs/15-demo/images/t85-engineering-modeling-shell.png";

const browser = await chromium.launch();
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const tokenResponse = await context.request.get(`${webUrl}/api/v1/demo-identity/token`);
  if (!tokenResponse.ok()) throw new Error("local demo identity is unavailable");
  const { access_token: accessToken } = await tokenResponse.json();
  const page = await context.newPage();
  await page.addInitScript(
    ({ token }) => window.localStorage.setItem(
      "cmp.material-platform.api-config",
      JSON.stringify({ baseUrl: "/api/v1", accessToken: token }),
    ),
    { token: accessToken },
  );

  await page.goto(`${webUrl}/modeling`);
  await page.getByRole("heading", { name: "Test curves to material model" }).waitFor();
  await page.getByRole("img", { name: "Hardening candidate and selected extrapolation curves" }).waitFor();
  await page.getByRole("button", { name: "Zoom in" }).waitFor();
  await page.getByText("stress.hardening [MPa]", { exact: true }).waitFor();
  await page.screenshot({ path: output, fullPage: false });
  console.log(`captured ${output}`);
} finally {
  await browser.close();
}
