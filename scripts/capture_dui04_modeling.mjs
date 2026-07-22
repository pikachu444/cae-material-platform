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
const stageHeadings = {
  Data: "Verify source & channel mapping",
  Process: "Prepare observed curves",
  Fit: "Compare response, residual & extrapolation",
  Export: "Review selected model & deliver solver card",
};

async function waitForSettled(page) {
  await page.waitForLoadState("networkidle");
  await page.waitForFunction(() => {
    const text = document.body.innerText;
    return !["Checking…", "Loading…", "Calculating…", "Loading source revisions…", "Loading the Metal elastoplastic engine…"]
      .some((label) => text.includes(label));
  }, undefined, { timeout: 20_000 });
}

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
    await page.getByRole("heading", { name: stageHeadings.Data }).waitFor({ timeout: 20_000 });
    await page.getByRole("combobox", { name: "Data-stage Test Data revision" }).waitFor();
    if (!(await page.getByRole("combobox", { name: "Data-stage Test Data revision" }).inputValue())) {
      await page.getByRole("combobox", { name: "Data-stage Test Data revision" }).selectOption({ index: 1 });
    }
    await page.getByText(/Loaded exact Test Data revision/).waitFor({ timeout: 20_000 });
    const plot = page.locator(".persistent-modeling-plot svg[role=img]");
    if (!(await plot.isVisible())) {
      await page.getByRole("button", { name: "Preview source" }).click();
    }
    await plot.waitFor({ timeout: 20_000 });
    await waitForSettled(page);

    let graphBeforeExport;
    let exportLayout;
    for (const stage of stages) {
      await page.locator(".workspace-command-bar").getByRole("button", { name: stage, exact: true }).click();
      await page.waitForURL(new RegExp(`stage=${stage.toLowerCase()}`));
      await page.getByRole("heading", { name: stageHeadings[stage] }).waitFor({ timeout: 20_000 });
      if (stage === "Export") {
        await page.getByText("Loading the Metal elastoplastic engine…", { exact: true }).waitFor({ state: "detached", timeout: 20_000 });
        await page.getByText("Loading source revisions…", { exact: true }).waitFor({ state: "detached", timeout: 20_000 });
        await page.locator(".modeling-workspace-dock .neutral-solver-export").waitFor({ timeout: 20_000 });
      }
      await plot.waitFor();
      await waitForSettled(page);
      if (stage === "Data" && await page.getByText("Metal hardening candidates", { exact: true }).count()) {
        throw new Error(`Fit-only settings leaked into Data at ${viewport.width}x${viewport.height}`);
      }
      if (stage === "Process" && await page.getByText("Fit evidence", { exact: true }).count()) {
        throw new Error(`Fit controls leaked into Process at ${viewport.width}x${viewport.height}`);
      }
      if (stage === "Fit" && !(await page.getByText("Fit evidence", { exact: true }).count())) {
        throw new Error(`Fit controls missing at ${viewport.width}x${viewport.height}`);
      }
      if (stage === "Fit") graphBeforeExport = await plot.elementHandle();
      if (stage === "Export") exportLayout = await page.evaluate(() => {
        const surface = document.querySelector(".modeling-main-surface");
        const dock = document.querySelector(".modeling-workspace-dock")?.getBoundingClientRect();
        const graph = document.querySelector(".persistent-modeling-plot")?.getBoundingClientRect();
        return {
          surfaceHeight: surface?.getBoundingClientRect().height ?? 0,
          gridRows: surface ? getComputedStyle(surface).gridTemplateRows : "",
          graphTop: graph?.top ?? 0,
          graphHeight: graph?.height ?? 0,
          dockTop: dock?.top ?? 0,
          dockHeight: dock?.height ?? 0,
        };
      });
      const filename = `${outputDir}/dui-04-modeling-${stage.toLowerCase()}-${viewport.width}x${viewport.height}.png`;
      await page.evaluate(() => window.scrollTo(0, 0));
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
      const surface = document.querySelector(".modeling-main-surface");
      const dock = document.querySelector(".modeling-workspace-dock")?.getBoundingClientRect();
      return {
        workspace: workspace?.width ?? 0,
        navigator: navigator?.width ?? 0,
        main: main?.width ?? 0,
        plot: plot?.width ?? 0,
        surfaceHeight: surface?.getBoundingClientRect().height ?? 0,
        gridRows: surface ? getComputedStyle(surface).gridTemplateRows : "",
        dockTop: dock?.top ?? 0,
        dockHeight: dock?.height ?? 0,
        horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    if (!graphPreserved) throw new Error(`graph remounted at ${viewport.width}x${viewport.height}`);
    if (measurements.horizontalOverflow !== 0) throw new Error(`horizontal overflow at ${viewport.width}x${viewport.height}`);

    const sessionBefore = await page.locator(".modeling-session-context").innerText();
    const testDataBefore = await page.locator(".modeling-dataset-list article.active button").getAttribute("title");
    const curvesBefore = await page.locator('.curve-include-toggle input[type="checkbox"]:checked').evaluateAll((items) => items.map((item) => item.getAttribute("aria-label")));
    await page.getByRole("navigation", { name: "Primary navigation" }).getByRole("button", { name: "Activity" }).click();
    await page.waitForURL(/\/activity$/);
    await page.getByRole("heading", { name: "Current workspace activity" }).waitFor();
    await page.getByTestId("recent-modeling-session").getByText(/Fit · .* r\d+ · \d+ selected curves/).waitFor();
    await page.getByRole("button", { name: "Resume Fit" }).click();
    await page.waitForURL(/\/modeling\?stage=fit&family=metal$/);
    await page.getByRole("heading", { name: stageHeadings.Fit }).waitFor();
    await plot.waitFor();
    await waitForSettled(page);
    const sessionAfter = await page.locator(".modeling-session-context").innerText();
    const testDataAfter = await page.locator(".modeling-dataset-list article.active button").getAttribute("title");
    const curvesAfter = await page.locator('.curve-include-toggle input[type="checkbox"]:checked').evaluateAll((items) => items.map((item) => item.getAttribute("aria-label")));
    const activityResume = sessionBefore === sessionAfter
      && testDataBefore === testDataAfter
      && JSON.stringify(curvesBefore) === JSON.stringify(curvesAfter);
    if (!activityResume) throw new Error(`Activity did not restore the exact Modeling selection at ${viewport.width}x${viewport.height}`);
    console.log(JSON.stringify({ viewport, graphPreserved, activityResume, session: sessionAfter, selectedCurves: curvesAfter, measurements, exportLayout }));
    await context.close();
  }
} finally {
  await browser.close();
}
