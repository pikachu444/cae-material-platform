import { chromium } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const output = process.env.CMP_DEMO_SCREENSHOT
  ?? "docs/15-demo/images/t85-engineering-modeling-shell.png";
const dashboardOutput = process.env.CMP_DEMO_DASHBOARD_SCREENSHOT
  ?? "docs/15-demo/images/t85-workspace-dashboard.png";
const ensembleOutput = process.env.CMP_DEMO_ENSEMBLE_SCREENSHOT;

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

  await page.goto(webUrl);
  await page.getByRole("heading", { name: "Material data to solver-ready models" }).waitFor();
  await page.getByRole("heading", { name: "Find and inspect material data" }).waitFor();
  await page.getByRole("heading", { name: "Process test curves and create cards" }).waitFor();
  await page.getByText("Material Database · 3 records").first().waitFor();
  await page.screenshot({ path: dashboardOutput, fullPage: false });
  console.log(`captured ${dashboardOutput}`);

  await page.goto(`${webUrl}/modeling`);
  await page.getByRole("heading", { name: "Test curves to material model" }).waitFor();
  await page.getByRole("img", { name: "Hardening candidate and selected extrapolation curves" }).waitFor();
  await page.getByRole("button", { name: "Zoom in" }).waitFor();
  await page.getByText("stress.hardening [MPa]", { exact: true }).waitFor();
  await page.getByRole("button", { name: /Metal elastic modulus/ }).click();
  const plot = page.getByRole("img", { name: "Mapped and selected processing stage curve overlay" });
  await page.getByRole("button", { name: "Select range" }).click();
  const plotBox = await plot.boundingBox();
  if (!plotBox) throw new Error("engineering plot bounds are unavailable");
  await page.mouse.move(plotBox.x + plotBox.width * 0.28, plotBox.y + plotBox.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(plotBox.x + plotBox.width * 0.52, plotBox.y + plotBox.height * 0.5);
  await page.mouse.up();
  if (!(await page.getByRole("button", { name: "Apply selection" }).isEnabled())) {
    throw new Error("graph range selection did not enable Apply selection");
  }
  await page.screenshot({ path: output, fullPage: false });
  console.log(`captured ${output}`);
  if (ensembleOutput) {
    const addMean = page.getByRole("button", { name: "Add mean & band" });
    await addMean.waitFor();
    if (!(await addMean.isEnabled())) {
      throw new Error("the demo must expose at least two exact tensile replicates");
    }
    await addMean.click();
    await page.getByRole("img", {
      name: "Aligned replicate curves with pointwise mean and confidence interval",
    }).waitFor();
    await page.screenshot({ path: ensembleOutput, fullPage: false });
    console.log(`captured ${ensembleOutput}`);
  }
} finally {
  await browser.close();
}
