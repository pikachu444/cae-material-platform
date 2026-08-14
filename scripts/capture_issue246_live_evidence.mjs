import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

import { chromium } from "@playwright/test";

const baseUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const output = resolve(
  process.env.CMP_ISSUE246_EVIDENCE_DIR ??
    "docs/17-evidence/images/issue-246-source-v2-categories/after",
);
const viewports = [
  [1366, 768],
  [1440, 900],
  [1920, 1080],
  [2560, 1440],
  [3840, 2160],
];

await Promise.all([
  mkdir(resolve(output, "originals"), { recursive: true }),
  mkdir(resolve(output, "crops"), { recursive: true }),
  mkdir(resolve(output, "measurements"), { recursive: true }),
]);

async function crop(page, selector, path) {
  const region = page.locator(selector).first();
  await region.waitFor({ state: "visible" });
  await region.screenshot({ path });
}

async function measurements(page, state, width, height) {
  return page.evaluate(
    ({ state, width, height }) => {
      const element = (selector) => document.querySelector(selector);
      const rect = (selector) => {
        const target = element(selector);
        if (!target) return null;
        const value = target.getBoundingClientRect();
        return {
          x: value.x,
          y: value.y,
          width: value.width,
          height: value.height,
        };
      };
      const scroll = (selector) => {
        const target = element(selector);
        if (!target) return null;
        const style = getComputedStyle(target);
        return {
          clientHeight: target.clientHeight,
          scrollHeight: target.scrollHeight,
          clientWidth: target.clientWidth,
          scrollWidth: target.scrollWidth,
          overflowX: style.overflowX,
          overflowY: style.overflowY,
        };
      };
      const firstTreeRow = element('[role="treeitem"]');
      return {
        state,
        viewport: { width, height, devicePixelRatio: window.devicePixelRatio },
        zoom: 1,
        body: {
          scrollWidth: document.body.scrollWidth,
          clientWidth: document.body.clientWidth,
        },
        shell: rect(".application-shell"),
        header: rect(".application-menu-bar"),
        navigator: rect(".materials-left-pane"),
        main: rect(
          state === "categories"
            ? ".materials-results"
            : ".exact-record-datasheet",
        ),
        navigatorScroll: scroll(".materials-tree-scroll"),
        resultsScroll: scroll(".materials-result-table-wrap"),
        treeRowHeight: firstTreeRow?.getBoundingClientRect().height ?? null,
        bodyFontSize: getComputedStyle(document.body).fontSize,
        dataFontSize: element(".materials-result-table tbody td")
          ? getComputedStyle(element(".materials-result-table tbody td"))
              .fontSize
          : null,
        activeDisplayTier:
          document.documentElement.dataset.displayDensity ?? "standard",
        primaryCommandCount:
          document.querySelectorAll(".button-primary").length,
        nestedPersistentCardCount: document.querySelectorAll(
          ".content-card .content-card",
        ).length,
        visibleCategories: [...document.querySelectorAll('[role="treeitem"]')]
          .map((item) => item.textContent?.trim())
          .filter(Boolean),
        capturedFromLiveApi: true,
      };
    },
    { state, width, height },
  );
}

async function openCategories(page) {
  await page.goto(`${baseUrl}/materials`);
  await page.waitForLoadState("networkidle");
  for (const category of [
    "Technical Data",
    "Test Data",
    "Simulation Data",
    "Solver Cards",
  ]) {
    const treeItem = page.getByRole("treeitem", {
      name: new RegExp(`^${category}`),
    });
    await treeItem.waitFor({ state: "visible" });
    if ((await treeItem.getAttribute("aria-expanded")) !== "true")
      await treeItem.click();
  }
  const expectedItems = [
    /DP780 synthetic reference steel/,
    /DP780 tensile · 23 °C · 0\.0067 s⁻¹/,
    /PA66-GF30 DMA · 23 °C frequency sweep/,
    /DP780 FLD · Nakajima/,
    /DP780 elastoplasticity · selected Voce result/,
    /DP780 tensile statistics · mean and 5% envelope/,
    /DP780 Abaqus native material card/,
  ];
  for (const name of expectedItems) {
    await page.getByRole("treeitem", { name }).waitFor();
  }
  for (const [category, expectedCount] of [
    ["Technical Data", 3],
    ["Test Data", 9],
    ["Simulation Data", 3],
    ["Solver Cards", 1],
  ]) {
    await page
      .getByRole("treeitem", { name: new RegExp(`^${category}`) })
      .click();
    await page.waitForFunction(
      (count) =>
        document.querySelectorAll(".materials-results tbody tr").length ===
        count,
      expectedCount,
    );
    const categoryCount = await page
      .locator(".materials-results tbody tr")
      .count();
    if (categoryCount !== expectedCount) {
      throw new Error(
        `Expected ${expectedCount} ${category} rows, received ${categoryCount}`,
      );
    }
  }
  for (const category of [
    "Technical Data",
    "Simulation Data",
    "Solver Cards",
    "Test Data",
  ]) {
    await page
      .getByRole("treeitem", { name: new RegExp(`^${category}`) })
      .click();
  }
  await page
    .getByRole("row", { name: /DP780 tensile · 23 °C · 0\.0067 s⁻¹/ })
    .waitFor();
  const count = await page.locator(".materials-results tbody tr").count();
  if (count !== 9)
    throw new Error(`Expected 9 populated Test Data rows, received ${count}`);
  if (
    page.viewportSize()?.width === 1366 &&
    (await page
      .locator(".materials-tree-scroll")
      .evaluate((node) => node.scrollHeight <= node.clientHeight))
  ) {
    throw new Error(
      "The populated long Materials tree did not produce independent local overflow",
    );
  }
  const body = await page.locator("body").innerText();
  if (body.includes("Catalog placement") || body.includes("Context")) {
    throw new Error(
      "Internal placement/context copy leaked into the Materials workspace",
    );
  }
}

async function openDetail(page) {
  await page
    .getByRole("row", { name: /DP780 tensile · 23 °C · 0\.0067 s⁻¹/ })
    .click();
  await page
    .getByRole("heading", {
      name: "DP780 tensile · 23 °C · 0.0067 s⁻¹",
      level: 1,
    })
    .waitFor({ timeout: 30_000 });
  await page.getByRole("heading", { name: "Related data", level: 2 }).waitFor();
  await page
    .getByText("DP780 elastoplasticity · selected Voce result", { exact: true })
    .waitFor();
  await page
    .getByText("DP780 tensile statistics · mean and 5% envelope", {
      exact: true,
    })
    .waitFor();
  await page.reload();
  await page
    .getByRole("heading", {
      name: "DP780 tensile · 23 °C · 0.0067 s⁻¹",
      level: 1,
    })
    .waitFor({ timeout: 30_000 });
  await page.waitForFunction(
    () => !document.body.textContent?.includes("Loading configured datasheet"),
    undefined,
    { timeout: 30_000 },
  );
  const detail = await page.locator(".exact-record-datasheet").innerText();
  for (const expected of [
    "Material and specimen form",
    "DP780 synthetic reference sheet, 1.2 mm",
    "Test method",
    "Synthetic uniaxial tensile characterization",
    "Specimen",
    "DP780-T-01",
    "Test conditions",
    "23 °C; 0.0067 s⁻¹",
    "Results",
    "E 210 GPa; 0.2% proof stress 410 MPa; maximum measured stress 775 MPa; maximum measured strain 14.0%.",
    "Measured curve coverage",
    "Engineering strain: 0 to 0.14 1; Engineering stress: 0 to 775000000 Pa",
    "Source data",
    "Technical Data selected by the materials engineer",
  ]) {
    if (!detail.includes(expected))
      throw new Error(`Missing readable detail value: ${expected}`);
  }
  if (detail.includes("No saved datasheet layout is available")) {
    throw new Error(
      "The populated test record has no user-facing datasheet layout",
    );
  }
}

async function verifyAdditionalEngineeringValues(page) {
  await page.getByRole("button", { name: "Results" }).click();
  await page.getByRole("treeitem", { name: /^Test Data/ }).click();
  await page
    .getByRole("row", { name: /PA66-GF30 DMA · 23 °C frequency sweep/ })
    .click();
  await page
    .getByRole("heading", {
      name: "PA66-GF30 DMA · 23 °C frequency sweep",
      level: 1,
    })
    .waitFor();
  await page.waitForFunction(
    () => !document.body.textContent?.includes("Loading configured datasheet"),
  );
  const dmaDetail = await page.locator(".exact-record-datasheet").innerText();
  for (const expected of [
    "storage modulus 7.31 GPa",
    "loss modulus 445 MPa",
    "loss factor 0.061",
  ]) {
    if (!dmaDetail.includes(expected))
      throw new Error(`Missing realistic DMA value: ${expected}`);
  }
  const dmaRelated = await page.locator(".exact-record-related").innerText();
  if (/elastoplastic/i.test(dmaRelated)) {
    throw new Error(
      "DMA detail must not expose an automatic elastoplasticity relation",
    );
  }

  await page.getByRole("button", { name: "Results" }).click();
  await page.getByRole("treeitem", { name: /^Test Data/ }).click();
  await page.getByRole("row", { name: /DP780 FLD · Nakajima/ }).click();
  await page
    .getByRole("heading", { name: "DP780 FLD · Nakajima", level: 1 })
    .waitFor();
  await page.waitForFunction(
    () => !document.body.textContent?.includes("Loading configured datasheet"),
  );
  const fldDetail = await page.locator(".exact-record-datasheet").innerText();
  if (!fldDetail.includes("Plane-strain limit ε1=0.31 at ε2=0.00")) {
    throw new Error("Missing realistic Nakajima FLD value");
  }
}

const browser = await chromium.launch({ headless: true });
try {
  for (const [width, height] of viewports) {
    const page = await browser.newPage({
      viewport: { width, height },
      deviceScaleFactor: 1,
    });
    const failures = [];
    page.on("console", (message) => {
      if (message.type() === "error") failures.push(message.text());
    });
    await openCategories(page);
    const suffix = `${width}x${height}`;
    await page.screenshot({
      path: resolve(output, "originals", `issue246-categories-${suffix}.png`),
    });
    await crop(
      page,
      ".application-menu-bar",
      resolve(output, "crops", `issue246-categories-${suffix}-header-crop.png`),
    );
    await crop(
      page,
      ".materials-left-pane",
      resolve(
        output,
        "crops",
        `issue246-categories-${suffix}-navigator-crop.png`,
      ),
    );
    await crop(
      page,
      ".materials-results table",
      resolve(output, "crops", `issue246-categories-${suffix}-record-crop.png`),
    );
    await crop(
      page,
      ".materials-results-header",
      resolve(output, "crops", `issue246-categories-${suffix}-detail-crop.png`),
    );
    await writeFile(
      resolve(output, "measurements", `issue246-categories-${suffix}.json`),
      `${JSON.stringify(await measurements(page, "categories", width, height), null, 2)}\n`,
    );

    await openDetail(page);
    await page.screenshot({
      path: resolve(output, "originals", `issue246-detail-${suffix}.png`),
    });
    await crop(
      page,
      ".application-menu-bar",
      resolve(output, "crops", `issue246-detail-${suffix}-header-crop.png`),
    );
    await crop(
      page,
      ".materials-left-pane",
      resolve(output, "crops", `issue246-detail-${suffix}-navigator-crop.png`),
    );
    await crop(
      page,
      ".exact-record-datasheet",
      resolve(output, "crops", `issue246-detail-${suffix}-record-crop.png`),
    );
    await crop(
      page,
      ".exact-record-related",
      resolve(output, "crops", `issue246-detail-${suffix}-detail-crop.png`),
    );
    await writeFile(
      resolve(output, "measurements", `issue246-detail-${suffix}.json`),
      `${JSON.stringify(await measurements(page, "detail", width, height), null, 2)}\n`,
    );
    if (width === 1366) await verifyAdditionalEngineeringValues(page);
    if (failures.length)
      throw new Error(`Browser console errors: ${failures.join(" | ")}`);
    await page.close();
  }
} finally {
  await browser.close();
}

console.log(`Captured live Issue #246 Materials evidence from ${baseUrl}`);
