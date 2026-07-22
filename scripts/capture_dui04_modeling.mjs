import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const outputDir = "docs/15-demo/images/ux-redesign-v2";
const viewports = [
  { width: 1366, height: 768 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
];
const stages = ["Data", "Process", "Fit", "Export"];

await mkdir(outputDir, { recursive: true });
const browser = await chromium.launch();
try {
  for (const viewport of viewports) {
    const context = await browser.newContext({ viewport });
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

    await page.goto(`${webUrl}/modeling?stage=data&family=metal`);
    await page.getByRole("heading", { name: "Test data and channel mapping" }).waitFor({ timeout: 20_000 });
    await page.getByRole("combobox", { name: "Test Data revision" }).waitFor();
    if (!(await page.getByRole("combobox", { name: "Test Data revision" }).inputValue())) {
      await page.getByRole("combobox", { name: "Test Data revision" }).selectOption({ index: 1 });
    }
    await page.getByText(/Loaded exact Test Data revision/).waitFor({ timeout: 20_000 });
    const plot = page.locator(".persistent-modeling-plot svg[role=img]");
    if (!(await plot.isVisible())) {
      await page.getByRole("button", { name: "Preview changes" }).click();
    }
    await plot.waitFor({ timeout: 20_000 });

    let graphBeforeExport;
    for (const stage of stages) {
      await page.locator(".workspace-command-bar").getByRole("button", { name: stage, exact: true }).click();
      await page.waitForURL(new RegExp(`stage=${stage.toLowerCase()}`));
      if (stage === "Export") {
        await page.getByRole("heading", { name: "Neutral model to solver-native material card" }).waitFor({ timeout: 20_000 });
        await page.getByText("Loading the Metal elastoplastic engine…", { exact: true }).waitFor({ state: "detached", timeout: 20_000 });
        await page.getByText("Loading source revisions…", { exact: true }).waitFor({ state: "detached", timeout: 20_000 });
        await page.getByRole("heading", { name: /DP780 reference calibration|Metal elastoplastic/ }).last().waitFor({ timeout: 20_000 });
      } else {
        await plot.waitFor();
      }
      if (stage === "Fit") graphBeforeExport = await plot.elementHandle();
      const filename = `${outputDir}/dui-04-modeling-${stage.toLowerCase()}-${viewport.width}x${viewport.height}.png`;
      await page.screenshot({ path: filename, fullPage: false });
    }

    await page.locator(".workspace-command-bar").getByRole("button", { name: "Fit", exact: true }).click();
    const graphAfterExport = await plot.elementHandle();
    const graphPreserved = graphBeforeExport && graphAfterExport
      ? await page.evaluate(([before, after]) => before === after, [graphBeforeExport, graphAfterExport])
      : false;
    const measurements = await page.evaluate(() => {
      const workspace = document.querySelector(".modeling-split-workspace")?.getBoundingClientRect();
      const navigator = document.querySelector(".modeling-workspace-rail")?.getBoundingClientRect();
      const main = document.querySelector(".modeling-main-panel")?.getBoundingClientRect();
      const plot = document.querySelector(".persistent-modeling-plot")?.getBoundingClientRect();
      return {
        workspace: workspace?.width ?? 0,
        navigator: navigator?.width ?? 0,
        main: main?.width ?? 0,
        plot: plot?.width ?? 0,
        horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    if (!graphPreserved) throw new Error(`graph remounted at ${viewport.width}x${viewport.height}`);
    if (measurements.horizontalOverflow !== 0) throw new Error(`horizontal overflow at ${viewport.width}x${viewport.height}`);
    console.log(JSON.stringify({ viewport, graphPreserved, measurements }));
    await context.close();
  }
} finally {
  await browser.close();
}
