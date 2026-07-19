import { chromium } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const responseOutput = process.env.CMP_T87_RESPONSE_SCREENSHOT
  ?? "docs/15-demo/images/t87-metal-fit-candidate-comparison.png";
const residualOutput = process.env.CMP_T87_RESIDUAL_SCREENSHOT
  ?? "docs/15-demo/images/t87-metal-fit-residual.png";

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
  await page.getByRole("tab", { name: "Stress response" }).waitFor();
  await page.getByLabel("Hardening candidate numerical comparison").waitFor();
  await page.getByText("Observed plastic workup").waitFor();
  await page.getByText("EXTRAPOLATED · UNOBSERVED").waitFor();
  await page.screenshot({ path: responseOutput, fullPage: false });
  console.log(`captured ${responseOutput}`);

  await page.getByRole("tab", { name: "Residual" }).click();
  await page.getByText("predicted - observed [MPa]", { exact: true }).waitFor();
  await page.screenshot({ path: residualOutput, fullPage: false });
  console.log(`captured ${residualOutput}`);
} finally {
  await browser.close();
}
