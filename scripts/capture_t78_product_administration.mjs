import { chromium } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const browser = await chromium.launch();
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
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

  await page.goto(`${webUrl}/administration`);
  await page.getByRole("heading", { name: "Configure the material workspace" }).waitFor();
  await page.screenshot({ path: "docs/15-demo/images/t78-administration-overview.png", fullPage: true });

  await page.getByRole("button", { name: /Design the database/ }).click();
  await page.getByRole("heading", { name: "Tables, Attributes and relationships" }).waitFor();
  await page.getByRole("button", { name: /Demo Material Records/ }).waitFor();
  await page.getByText("8 Attributes", { exact: true }).waitFor();
  await page.screenshot({ path: "docs/15-demo/images/t78-database-design.png", fullPage: true });

  await page.getByRole("button", { name: /Users & access/ }).click();
  await page.getByRole("heading", { name: "Choose what each team can do" }).waitFor();
  await page.getByText("cmp-demo-material-team", { exact: true }).waitFor();
  await page.screenshot({ path: "docs/15-demo/images/t78-users-access.png", fullPage: true });
} finally {
  await browser.close();
}
