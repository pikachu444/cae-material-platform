import { expect, test, type Locator, type Page } from "@playwright/test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

import {
  approveSyntheticDmaFitSetup,
  ensureSyntheticRelaxationFitSetup,
} from "./polymer-linear-viscoelastic-fit-governance";
import {
  deriveNistSrm2491CyclicHzUpload,
  NIST_SRM_2491_HOLDOUT_SWEEP_ORDINAL,
  NIST_SRM_2491_REFERENCE_SWEEP_ORDINAL,
  NIST_SRM_2491_REFERENCE_TEMPERATURE_K,
} from "./issue-392-dma-tts-fixture";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const evidenceDir =
  process.env.CMP_POLYMER_FIT_EVIDENCE_DIR ??
  resolve(process.cwd(), "../../.artifacts/polymer-linear-viscoelastic-fit");
const sessionStatePath = resolve(evidenceDir, "modeling-fit-polymer-session.json");
const issue392EvidenceDir = resolve(
  process.cwd(),
  "../../docs/17-evidence/issue-392-dma-tts-process-ui",
);
const currentGuideImageDir = resolve(
  process.cwd(),
  "../../docs/user-guide/images/current",
);

const acceptanceViewports = [
  { width: 1366, height: 768 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
  { width: 2560, height: 1440 },
  { width: 3840, height: 2160 },
] as const;

test.describe.configure({ mode: "serial" });

async function writeScreenshot(path: string, image: Uint8Array): Promise<void> {
  let lastError: unknown;
  for (let attempt = 0; attempt < 10; attempt += 1) {
    try {
      await writeFile(path, image);
      return;
    } catch (error) {
      lastError = error;
      await new Promise((resolveDelay) => setTimeout(resolveDelay, 100 * (attempt + 1)));
    }
  }
  throw lastError;
}

async function installDemoUser(page: Page, persona?: "administrator"): Promise<string> {
  const tokenResponse = await page.request.get(
    `${webUrl}/api/v1/demo-identity/token${persona ? `?persona=${persona}` : ""}`,
  );
  expect(tokenResponse.ok()).toBeTruthy();
  const token = (await tokenResponse.json()) as { access_token: string };
  await page.addInitScript(
    ({ accessToken }) => {
      window.localStorage.setItem(
        "cmp.material-platform.api-config",
        JSON.stringify({ baseUrl: "/api/v1", accessToken }),
      );
    },
    { accessToken: token.access_token },
  );
  return token.access_token;
}

async function openPolymerModeling(
  page: Page,
  accessToken: string,
): Promise<void> {
  const headers = { Authorization: `Bearer ${accessToken}` };
  const materialsResponse = await page.request.get(
    `${webUrl}/api/v1/materials?q=CMP-DEMO-POLYMER-PRONY&limit=20`,
    { headers },
  );
  expect(materialsResponse.ok()).toBeTruthy();
  const materials = (await materialsResponse.json()) as {
    items: Array<{
      material_id: string;
      current_revision: { id: string; content: { material_code: string } };
    }>;
  };
  expect(materials.items).toHaveLength(1);
  const material = materials.items[0];
  expect(material.current_revision.content.material_code).toBe(
    "CMP-DEMO-POLYMER-PRONY",
  );

  const detailResponse = await page.request.get(
    `${webUrl}/api/v1/materials/${material.material_id}`,
    { headers },
  );
  expect(detailResponse.ok()).toBeTruthy();
  const detail = (await detailResponse.json()) as {
    states: Array<{
      material_state_id: string;
      current_revision: { id: string; content: { name: string } };
    }>;
  };
  expect(detail.states).toHaveLength(1);
  const state = detail.states[0];
  expect(state.current_revision.content.name).toBe("Reference conditioned");
  const query = new URLSearchParams({
    stage: "data",
    family: "polymer",
    material_id: material.material_id,
    material_revision_id: material.current_revision.id,
    material_state_id: state.material_state_id,
    material_state_revision_id: state.current_revision.id,
  });
  await page.goto(`/modeling?${query.toString()}`);
  await expect(page).toHaveURL(
    /\/modeling\?stage=data&family=polymer&material_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+&material_state_id=[0-9a-f-]+&material_state_revision_id=[0-9a-f-]+$/,
  );
}

async function selectRelaxationInputAndOpenFit(page: Page): Promise<void> {
  await expect(
    page.getByRole("heading", { name: "Select Test Data" }),
  ).toBeVisible({ timeout: 30_000 });
  const row = page.locator(
    '[data-document-key="CMP-DEMO-POLYMER-FIT-RELAXATION-CSV"]',
  );
  await expect(row).toHaveCount(1);
  const sourceButton = row.locator(".modeling-data-record-button");
  await sourceButton.focus();
  await page.keyboard.press("Enter");
  await expect(row).toHaveClass(/active/, { timeout: 30_000 });
  const session = await page.evaluate(() => JSON.parse(
    window.sessionStorage.getItem("cmp.modeling.recent-session.v4") ?? "null",
  )) as {
    material: ExactRevision;
    materialState: ExactRevision;
    testData: ExactRevision;
  };
  await ensureSyntheticRelaxationFitSetup({
    request: page.request,
    webUrl,
    material: session.material,
    materialState: session.materialState,
    testData: session.testData,
  });
  const fitStage = page.locator(".modeling-stage-shell button").filter({
    has: page.locator("strong", { hasText: /^Fit$/ }),
  });
  await expect(fitStage).toHaveCount(1);
  await fitStage.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/stage=fit/);
  await expect(page.locator(".polymer-calibration-fit")).toBeVisible({
    timeout: 30_000,
  });
}

interface FitDecision {
  recommendedTerm: number;
  selectedTerm: number;
  reason: string;
}

interface ExactRevision {
  id: string;
  revisionId: string;
}

async function calculateAndSelectAlternateModel(
  page: Page,
  reason: string,
): Promise<FitDecision> {
  const calculate = page.getByRole("button", { name: "Calculate Prony models" });
  await expect(calculate).toBeEnabled({ timeout: 30_000 });
  await calculate.focus();
  await page.keyboard.press("Enter");

  const candidates = page.getByRole("table", { name: "Calculated model comparison" });
  await expect(candidates).toBeVisible({ timeout: 240_000 });
  await expect(candidates.locator("tbody > tr")).toHaveCount(10);
  for (const term of [1, 5, 10]) {
    await expect(candidates.getByText(`${term}-term Prony`, { exact: true })).toBeAttached();
  }

  const recommendedRow = candidates.locator("tbody > tr").filter({ hasText: "Recommended" }).first();
  await expect(recommendedRow).toBeAttached();
  const recommendedTerm = Number.parseInt(await recommendedRow.locator("th strong").innerText(), 10);
  expect(recommendedTerm).toBeGreaterThanOrEqual(1);
  expect(recommendedTerm).toBeLessThanOrEqual(10);

  const alternateTerms = Array.from({ length: 10 }, (_, index) => index + 1)
    .filter((term) => term !== recommendedTerm)
    .sort((left, right) => Math.abs(left - recommendedTerm) - Math.abs(right - recommendedTerm));
  let selectedTerm = 0;
  let selectedRadio: Locator | null = null;
  for (const term of alternateTerms) {
    const radio = candidates.getByRole("radio", { name: `Select ${term}-term Prony` });
    if (await radio.count() && await radio.isEnabled()) {
      selectedTerm = term;
      selectedRadio = radio;
      break;
    }
  }
  expect(selectedRadio, "an available non-recommended candidate is required").not.toBeNull();
  await selectedRadio!.focus();
  await page.keyboard.press("Space");
  await expect(selectedRadio!).toBeChecked();

  const reasonInput = page.getByRole("textbox", { name: "Reason for selection" });
  await reasonInput.focus();
  await page.keyboard.type(reason);
  await expect(reasonInput).toHaveValue(reason);
  for (const warning of await page.locator('.polymer-warning-list input[type="checkbox"]').all()) {
    if (!(await warning.isChecked())) {
      await warning.focus();
      await page.keyboard.press("Space");
    }
  }

  const selection = page.locator(".modeling-fit-selection-pane");
  await expect(selection).toContainText(`${selectedTerm}-term Prony`);
  await expect(selection).not.toContainText("Recommended");
  const legend = page.getByLabel("Response graph legend");
  await expect(legend.getByText("Recommended model", { exact: true })).toBeVisible();
  await expect(legend.getByText("Selected model", { exact: true })).toBeVisible();

  return { recommendedTerm, selectedTerm, reason };
}

async function expectDistinctFitDecision(page: Page, decision: FitDecision): Promise<void> {
  const candidates = page.getByRole("table", { name: "Calculated model comparison" });
  await expect(candidates).toBeVisible({ timeout: 30_000 });
  const recommendedRow = candidates.locator("tbody > tr").filter({ hasText: "Recommended" }).first();
  await expect(recommendedRow).toContainText(`${decision.recommendedTerm}-term Prony`);
  await expect(
    candidates.getByRole("radio", { name: `Select ${decision.selectedTerm}-term Prony` }),
  ).toBeChecked();
  await expect(page.getByRole("textbox", { name: "Reason for selection" })).toHaveValue(decision.reason);
  const legend = page.getByLabel("Response graph legend");
  await expect(legend.getByText("Recommended model", { exact: true })).toBeVisible();
  await expect(legend.getByText("Selected model", { exact: true })).toBeVisible();
}

async function expectInsideViewport(locator: Locator): Promise<void> {
  await expect(locator).toBeVisible();
  const geometry = await locator.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      left: rect.left,
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
    };
  });
  expect(geometry.left).toBeGreaterThanOrEqual(-1);
  expect(geometry.top).toBeGreaterThanOrEqual(-1);
  expect(geometry.right).toBeLessThanOrEqual(geometry.viewportWidth + 1);
  expect(geometry.bottom).toBeLessThanOrEqual(geometry.viewportHeight + 1);
}

async function expectUsableFitComposition(page: Page): Promise<void> {
  const geometry = await page
    .locator(".modeling-main-surface")
    .evaluate((surface) => {
      const graph = surface.querySelector<HTMLElement>(
        ".polymer-fit-graph-region",
      );
      const dock = surface.querySelector<HTMLElement>(
        ".modeling-workspace-dock",
      );
      if (!graph || !dock) throw new Error("Polymer Fit regions are missing");
      const surfaceRect = surface.getBoundingClientRect();
      const graphRect = graph.getBoundingClientRect();
      const dockRect = dock.getBoundingClientRect();
      const surfaceStyle = getComputedStyle(surface);
      return {
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
        surfaceWidth: surfaceRect.width,
        surfaceRight: surfaceRect.right,
        surfaceHeight: surfaceRect.height,
        graphHeight: graphRect.height,
        graphWidth: graphRect.width,
        dockHeight: dockRect.height,
        dockWidth: dockRect.width,
        graphBottom: graphRect.bottom,
        dockTop: dockRect.top,
        gridTemplateColumns: surfaceStyle.gridTemplateColumns,
        gridTemplateRows: surfaceStyle.gridTemplateRows,
        surfacePadding: surfaceStyle.padding,
        hasResults: Boolean(surface.querySelector(".modeling-fit-decision-dock")),
      };
  });

  const message = JSON.stringify(geometry);
  expect(geometry.surfaceHeight, message).toBeGreaterThanOrEqual(
    Math.max(480, geometry.viewportHeight - 210),
  );
  expect(geometry.dockHeight, message).toBeGreaterThanOrEqual(
    geometry.hasResults ? 160 : 48,
  );
  expect(geometry.graphHeight, message).toBeGreaterThanOrEqual(
    geometry.hasResults ? 260 : 360,
  );
  expect(geometry.surfaceRight, message).toBeGreaterThanOrEqual(
    geometry.viewportWidth - 2,
  );
  expect(geometry.graphWidth, message).toBeGreaterThanOrEqual(
    geometry.surfaceWidth - 2,
  );
  expect(geometry.dockWidth, message).toBeGreaterThanOrEqual(
    geometry.surfaceWidth - 2,
  );
  expect(Math.abs(geometry.graphBottom - geometry.dockTop)).toBeLessThanOrEqual(
    2,
  );
}

async function capture(
  page: Page,
  name: string,
  locator?: Locator,
): Promise<void> {
  await mkdir(evidenceDir, { recursive: true });
  const path = resolve(evidenceDir, name);
  if (locator) await locator.screenshot({ path, animations: "disabled" });
  else await page.screenshot({ path, animations: "disabled", fullPage: false });
}

async function captureIssue392ProcessState(
  page: Page,
  state: "recommendation" | "saved",
): Promise<void> {
  const originals = resolve(issue392EvidenceDir, "after/originals");
  const crops = resolve(issue392EvidenceDir, "after/crops");
  await Promise.all([
    mkdir(originals, { recursive: true }),
    mkdir(crops, { recursive: true }),
    mkdir(currentGuideImageDir, { recursive: true }),
  ]);
  for (const viewport of acceptanceViewports) {
    const size = `${viewport.width}x${viewport.height}`;
    await page.setViewportSize(viewport);
    await page.evaluate(() => new Promise<void>((resolveFrame) => {
      requestAnimationFrame(() => requestAnimationFrame(() => resolveFrame()));
    }));
    const geometry = await page.evaluate(() => ({
      width: innerWidth,
      height: innerHeight,
      dpr: devicePixelRatio,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(geometry).toMatchObject({ width: viewport.width, height: viewport.height, dpr: 1 });
    expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.clientWidth + 1);
    await expectInsideViewport(page.locator(".dma-tts-process-surface"));
    await expectInsideViewport(page.locator(".dma-tts-sweep-rail"));

    const guideName = state === "saved"
      ? `modeling-process-polymer-dma-tts-saved-${size}.png`
      : `modeling-process-polymer-dma-tts-${size}.png`;
    const originalPath = resolve(
      originals,
      `modeling-process-polymer-dma-tts-${state}-${size}.png`,
    );
    const viewportImage = await page.screenshot({
      animations: "disabled",
      fullPage: false,
    });
    await writeScreenshot(originalPath, viewportImage);
    await writeScreenshot(resolve(currentGuideImageDir, guideName), viewportImage);
    for (const [role, locator] of [
      ["header", page.locator(".application-menu-bar")],
      ["navigator", page.locator(".dma-tts-sweep-rail")],
      ["controls", page.locator(".dma-tts-work-area")],
      ["graph", page.locator(".dma-tts-graph")],
    ] as const) {
      await expect(locator).toBeVisible();
      const cropImage = await locator.screenshot({
        animations: "disabled",
      });
      await writeScreenshot(
        resolve(crops, `modeling-process-polymer-dma-tts-${state}-${role}-${size}.png`),
        cropImage,
      );
    }
  }
  await page.setViewportSize({ width: 1920, height: 1080 });
}

async function persistModelingSession(page: Page): Promise<void> {
  const value = await page.evaluate(() =>
    window.sessionStorage.getItem("cmp.modeling.recent-session.v4"),
  );
  expect(value).not.toBeNull();
  await mkdir(evidenceDir, { recursive: true });
  await writeFile(sessionStatePath, `${value}\n`, "utf-8");
}

async function restoreModelingSession(page: Page): Promise<void> {
  const value = (await readFile(sessionStatePath, "utf-8")).trim();
  expect(JSON.parse(value)).toMatchObject({ version: 4, materialFamily: "polymer" });
  await page.addInitScript(
    ({ modelingSession }) => {
      window.sessionStorage.setItem(
        "cmp.modeling.recent-session.v4",
        modelingSession,
      );
    },
    { modelingSession: value },
  );
}

async function createChangedUpstreamRevision(
  page: Page,
  accessToken: string,
): Promise<string> {
  const savedSession = JSON.parse(
    (await readFile(sessionStatePath, "utf-8")).trim(),
  ) as { testData: { id: string } };
  const headers = { Authorization: `Bearer ${accessToken}` };
  const listResponse = await page.request.get(
    `${webUrl}/api/v1/test-data-documents`,
    { headers },
  );
  expect(listResponse.ok()).toBeTruthy();
  const list = (await listResponse.json()) as {
    items: Array<{
      test_data_document_id: string;
      current_revision: {
        id: string;
        revision_no: number;
        content_hash: string;
      };
      governed_source?: Record<string, unknown>;
    }>;
  };
  const current = list.items.find(
    (item) => item.test_data_document_id === savedSession.testData.id,
  );
  expect(current).toBeTruthy();
  const contentResponse = await page.request.get(
    `${webUrl}/api/v1/test-data-documents/${current!.test_data_document_id}/revisions/${current!.current_revision.id}/content`,
    { headers },
  );
  expect(contentResponse.ok()).toBeTruthy();
  const revisionResponse = await page.request.post(
    `${webUrl}/api/v1/test-data-documents/${current!.test_data_document_id}/revisions`,
    {
      headers: {
        ...headers,
        "If-Match": `"revision:${current!.current_revision.revision_no}:sha256:${current!.current_revision.content_hash}"`,
      },
      data: {
        document: await contentResponse.json(),
        governed_source: current!.governed_source,
        change_reason:
          "Create a new exact upstream revision for stale-result recovery acceptance.",
      },
    },
  );
  expect(revisionResponse.ok()).toBeTruthy();
  const revised = (await revisionResponse.json()) as {
    current_revision: { id: string };
  };
  return revised.current_revision.id;
}

async function captureAcceptanceViewports(page: Page): Promise<void> {
  for (const viewport of acceptanceViewports) {
    const size = `${viewport.width}x${viewport.height}`;
    await page.setViewportSize(viewport);
    await page.evaluate(
      () => new Promise<void>((resolveFrame) => requestAnimationFrame(() => resolveFrame())),
    );

    await expectInsideViewport(page.locator(".polymer-calibration-fit"));
    await expectInsideViewport(page.locator(".polymer-fit-command-ribbon"));
    await expectInsideViewport(page.locator(".polymer-fit-graph-region"));
    await expectInsideViewport(page.locator(".modeling-workspace-dock"));
    await expectUsableFitComposition(page);
    const candidateTable = page.getByRole("table", { name: "Calculated model comparison" });
    await expect(candidateTable).toBeVisible();
    const lastCandidate = candidateTable.getByText("10-term Prony", { exact: true });
    await expect(lastCandidate).toBeAttached();
    const candidateScroller = page.locator(".modeling-fit-candidate-table-wrap");
    await candidateScroller.evaluate((element) => {
      element.scrollTop = element.scrollHeight;
    });
    await expect(lastCandidate).toBeVisible();
    await candidateScroller.evaluate((element) => {
      element.scrollTop = 0;
    });
    await expect(
      page.getByRole("textbox", { name: "Reason for selection" }),
    ).toBeVisible();

    await capture(page, `modeling-fit-polymer-saved-${size}.png`);
    await capture(
      page,
      `modeling-fit-polymer-saved-header-${size}.png`,
      page.locator(".application-menu-bar"),
    );
    await capture(
      page,
      `modeling-fit-polymer-saved-decision-${size}.png`,
      page.locator(".modeling-fit-decision-dock"),
    );
    await capture(
      page,
      `modeling-fit-polymer-saved-controls-${size}.png`,
      page.locator(".modeling-workspace-dock"),
    );
    await capture(
      page,
      `modeling-fit-polymer-saved-graph-${size}.png`,
      page.locator(".polymer-fit-graph-region"),
    );
  }

  await page.setViewportSize({ width: 1920, height: 1080 });
  const residuals = page.getByRole("button", { name: "Point differences" });
  await residuals.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("img", { name: /Differences on used points/i }),
  ).toBeVisible();
  const response = page.getByRole("button", { name: "Response curves" });
  await response.focus();
  await page.keyboard.press("Space");
  await expect(
    page.getByRole("img", {
      name: /Measured relaxation data with recommended and selected model responses/i,
    }),
  ).toBeVisible();
}

test("Polymer Fit without an exact source offers one direct return to Data", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  const accessToken = await installDemoUser(page);
  await openPolymerModeling(page, accessToken);
  await page.goto(page.url().replace("stage=data", "stage=fit"));
  await expect(page).toHaveURL(/stage=fit/, { timeout: 30_000 });
  await expect(page.locator(".modeling-work-title")).toContainText("POLYMER-PRONY", {
    timeout: 30_000,
  });
  await expect.poll(() => pageErrors, { message: pageErrors.join("\n") }).toEqual([]);
  await expect(page.getByRole("region", { name: "Fit input required" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Test Data required" })).toBeVisible();
  await expect(page.getByText("Select relaxation or DMA Test Data before calculating models.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Choose Test Data", exact: true })).toHaveCount(1);
  await expect(page.locator(".polymer-calibration-fit")).toBeVisible();
  await expect(page.locator(".polymer-fit-graph-region")).toHaveCount(0);
  await expect(page.locator(".modeling-workspace-rail")).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText(
    /Compare exact relaxation|The graph stays here|Run the exact governed Plan/i,
  );

  for (const viewport of acceptanceViewports) {
    await page.setViewportSize(viewport);
    await page.evaluate(
      () => new Promise<void>((resolveFrame) => requestAnimationFrame(() => resolveFrame())),
    );
    await expect(page.locator(".modeling-work-title")).toContainText("POLYMER-PRONY");
    await expectInsideViewport(page.getByRole("region", { name: "Fit input required" }));
    await expectInsideViewport(page.getByRole("button", { name: "Choose Test Data", exact: true }));
    await capture(
      page,
      `modeling-fit-polymer-source-blocked-${viewport.width}x${viewport.height}.png`,
    );
  }

  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.getByRole("button", { name: "Choose Test Data", exact: true }).click();
  await expect(page).toHaveURL(/stage=data/, { timeout: 30_000 });
  await expect(page.getByRole("region", { name: "Test Data results" })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "Relaxation test 0001" })).toHaveCount(1);
});

test("a fixed-frequency DMA temperature sweep creates one shifted response before Fit", async ({
  page,
}) => {
  test.setTimeout(360_000);
  await mkdir(evidenceDir, { recursive: true });
  const token = await installDemoUser(page);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await openPolymerModeling(page, token);

  const row = page.locator(
    '[data-document-key="CMP-DMA-TEMPERATURE-SWEEP-REFERENCE"]',
  );
  await expect(row).toHaveCount(1);
  await row.locator(".modeling-data-record-button").click();
  await expect(row).toHaveClass(/active/, { timeout: 30_000 });
  await page.getByRole("button", { name: "Continue to Process" }).click();
  await expect(page).toHaveURL(/stage=process/);
  await expect(page.locator(".dma-tts-process-surface")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".modeling-context-strip")).toContainText("DMA test 0001");
  await expect(page.locator(".stage-process .modeling-workspace-rail")).toHaveCount(0);
  await expect(page.locator(".stage-process .modeling-pane-divider")).toHaveCount(0);
  await expect(page.locator(".stage-process .modeling-split-workspace-no-navigator")).toHaveCount(1);

  const prepare = page.getByRole("button", { name: "Prepare recommendation" });
  await expect(prepare).toBeVisible({ timeout: 30_000 });
  await expect(prepare).toBeEnabled();
  await expect(page.getByText("1. Prepare the DMA master curve", { exact: true })).toBeVisible();
  await expect(page.getByLabel("C1")).toHaveCount(0);
  const processGeometry = await page.locator(".dma-tts-process-surface").evaluate((surface) => {
    const graph = surface.querySelector<HTMLElement>(".dma-tts-graph")!;
    const work = surface.querySelector<HTMLElement>(".dma-tts-work-area")!;
    const graphRect = graph.getBoundingClientRect();
    const workRect = work.getBoundingClientRect();
    return {
      graphHeight: graphRect.height,
      workHeight: workRect.height,
      graphBottom: graphRect.bottom,
      workTop: workRect.top,
    };
  });
  expect(processGeometry.graphHeight).toBeGreaterThan(processGeometry.workHeight);
  expect(Math.abs(processGeometry.graphBottom - processGeometry.workTop)).toBeLessThanOrEqual(2);
  for (const viewport of acceptanceViewports) {
    const size = `${viewport.width}x${viewport.height}`;
    await page.setViewportSize(viewport);
    await expectInsideViewport(page.locator(".dma-tts-process-surface"));
    await expectInsideViewport(page.locator(".dma-tts-graph"));
    await expectInsideViewport(prepare);
    await capture(page, `modeling-process-polymer-dma-tts-${size}.png`);
  }
  await page.setViewportSize({ width: 1920, height: 1080 });

  await prepare.click();
  const create = page.getByRole("button", { name: "Save TTS result" });
  await expect(create).toBeVisible({ timeout: 30_000 });
  await expect(create).toBeEnabled();
  await expect(page.getByText("Shift method")).toBeVisible();
  await expect(page.getByText("WLF", { exact: true })).toBeVisible();

  const createdResponsePromise = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && response.url().endsWith("/api/v1/processing/dma-frequency-master-curves")
  ));
  await create.click();
  const createdResponse = await createdResponsePromise;
  expect(createdResponse.ok()).toBeTruthy();
  const created = (await createdResponse.json()) as {
    master_curve_output: { output_id: string; revision_id: string };
  };
  await expect(page.getByRole("heading", { name: "TTS result saved" })).toBeVisible({
    timeout: 30_000,
  });
  const continueToFit = page.getByRole("button", { name: "Continue to Prony Fit" });
  await expect(continueToFit).toHaveCount(1);
  for (const viewport of acceptanceViewports) {
    const size = `${viewport.width}x${viewport.height}`;
    await page.setViewportSize(viewport);
    await expectInsideViewport(page.locator(".dma-tts-process-surface"));
    await expectInsideViewport(page.locator(".dma-tts-graph"));
    await expectInsideViewport(continueToFit);
    await capture(page, `modeling-process-polymer-dma-tts-saved-${size}.png`);
  }
  await page.setViewportSize({ width: 1920, height: 1080 });
  await continueToFit.click();
  await expect(page).toHaveURL(/stage=fit/);
  await expect(page.getByRole("heading", { name: "Shifted DMA response" })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Review calculation settings" })).toBeVisible({ timeout: 30_000 });
  const dmaSession = await page.evaluate(() => JSON.parse(
    window.sessionStorage.getItem("cmp.modeling.recent-session.v4") ?? "null",
  )) as {
    material: { id: string; revisionId: string };
    materialState: { id: string; revisionId: string };
  };
  await approveSyntheticDmaFitSetup({
    request: page.request,
    webUrl,
    material: dmaSession.material,
    materialState: dmaSession.materialState,
    processingOutput: {
      id: created.master_curve_output.output_id,
      revisionId: created.master_curve_output.revision_id,
    },
  });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Shifted DMA response" })).toBeVisible({ timeout: 30_000 });
  const decision = await calculateAndSelectAlternateModel(
    page,
    "Selected the adjacent model after comparing the DMA response and point differences.",
  );
  const save = page.getByRole("button", { name: "Save fit & continue" });
  await expect(save).toBeEnabled();
  await save.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/stage=export/, { timeout: 60_000 });
  const fitStage = page.locator(".modeling-stage-shell button").filter({
    has: page.locator("strong", { hasText: /^Fit$/ }),
  });
  await fitStage.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/stage=fit/);
  await expectDistinctFitDecision(page, decision);
  await capture(page, "modeling-fit-polymer-dma-saved-1920x1080.png");
  await page.reload();
  await expect(page).toHaveURL(/stage=fit/);
  await expect(page.getByRole("heading", { name: "Shifted DMA response" })).toBeVisible({ timeout: 30_000 });
  await expectDistinctFitDecision(page, decision);
});

test("Issue #392 imports NIST multi-frequency DMA, saves exact TTS, and restores a Prony selection", async ({
  page,
}) => {
  test.setTimeout(600_000);
  const pageErrors: string[] = [];
  const processCreateRequests: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().endsWith("/api/v1/processing/dma-frequency-master-curves")) {
      processCreateRequests.push(request.url());
    }
  });

  const accessToken = await installDemoUser(page);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await openPolymerModeling(page, accessToken);
  await expect(page.getByRole("heading", { name: "Select Test Data" })).toBeVisible({ timeout: 30_000 });
  await page.getByRole("tab", { name: "Local file", exact: true }).click();

  const upload = deriveNistSrm2491CyclicHzUpload();
  await page.getByLabel("Import Test Data file").setInputFiles({
    name: "nist-srm-2491-dma-multi-frequency.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(upload, "utf8"),
  });
  const runSelect = page.getByLabel("Imported file Test record");
  await expect(runSelect).toBeVisible({ timeout: 30_000 });
  await expect.poll(() => runSelect.locator("option").count()).toBeGreaterThan(1);
  const runOption = await runSelect.locator("option").evaluateAll((options) => options
    .map((option) => ({
      value: (option as HTMLOptionElement).value,
      text: option.textContent?.trim() ?? "",
    }))
    .find((option) => option.value && /DMA/i.test(option.text))
    ?? options.map((option) => ({
      value: (option as HTMLOptionElement).value,
      text: option.textContent?.trim() ?? "",
    })).find((option) => option.value));
  expect(runOption?.value, "an exact polymer Test record is required for the governed import").toBeTruthy();
  await runSelect.selectOption(runOption!.value);

  const inspectResponse = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && response.url().endsWith("/api/v1/tabular-import-previews")
  ));
  await page.getByRole("button", { name: "Inspect file", exact: true }).click();
  expect((await inspectResponse).ok()).toBeTruthy();
  const schema = page.getByLabel("Local data schema");
  if (!await schema.count()) {
    await page.getByRole("button", { name: "Change mapping", exact: true }).click();
  }
  await expect(schema).toBeVisible({ timeout: 30_000 });
  await schema.selectOption("dma_frequency_temperature_sweep");
  for (const [label, column, unit] of [
    ["Source sweep ordinal", "source_sweep_ordinal", "1"],
    ["Temperature", "temperature_degC", "degC"],
    ["Frequency", "frequency_Hz", "Hz"],
    ["Storage modulus", "storage_modulus_Pa", "Pa"],
    ["Loss modulus", "loss_modulus_Pa", "Pa"],
  ] as const) {
    await page.getByLabel(`${label} source column`).selectOption(column);
    await page.getByLabel(`${label} original unit`).selectOption(unit);
  }
  await expect(page.getByText("DMA 1.3.0 mapping:", { exact: false })).toBeVisible();
  await page.getByText("Save details", { exact: true }).click();
  await page.locator('input[name="test-data-name"]').fill("ISSUE-392-NIST-SRM-2491-DMA");
  await page.locator('input[name="test-data-maker"]').fill("NIST public SRM 2491 reference");
  await page.locator('input[name="test-data-operator"]').fill("Issue 392 browser acceptance");
  await page.locator('input[name="test-data-laboratory"]').fill("Public fixture validation");
  await page.getByLabel("Mapping change reason").fill(
    "Map the immutable NIST frequency, temperature, storage, loss, and sweep ordinal columns.",
  );

  const previewResponse = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && response.url().endsWith("/api/v1/test-data:convert-tabular")
  ));
  await page.getByRole("button", { name: "Update preview", exact: true }).click();
  expect((await previewResponse).ok()).toBeTruthy();
  await expect(page.getByRole("button", { name: "Save Test Data", exact: true })).toBeEnabled({ timeout: 30_000 });
  const saveDocumentResponse = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && /\/api\/v1\/test-data-documents(?:\/[^/]+\/revisions)?$/.test(response.url())
  ));
  await page.getByRole("button", { name: "Save Test Data", exact: true }).click();
  expect((await saveDocumentResponse).status()).toBe(201);
  const imported = page.locator('[data-document-key="ISSUE-392-NIST-SRM-2491-DMA"]');
  await expect(imported).toHaveClass(/active/, { timeout: 30_000 });
  await page.getByRole("button", { name: "Continue to Process", exact: true }).click();

  await expect(page).toHaveURL(/stage=process/);
  await expect(page.locator(".dma-tts-sweep-rail")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".dma-tts-sweep-entry")).toHaveCount(6);
  await expect(page.getByText("Curves on graph", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Reference curve")).toHaveValue(String(NIST_SRM_2491_REFERENCE_SWEEP_ORDINAL));
  await expect(page.getByRole("checkbox", { name: /^Show .* K on graph$/ })).toHaveCount(6);
  await expect(page.getByRole("button", { name: "Prepare recommendation", exact: true })).toBeEnabled();
  await expect(page.locator(".curve-legend button")).toHaveCount(6);
  await expect(page.locator(".dma-legend-line-key", { hasText: "G′" })).toBeVisible();
  await expect(page.locator(".dma-legend-line-key", { hasText: "G″" })).toBeVisible();
  const graphOnlyToggle = page.getByLabel("Show 283.15 K on graph");
  await graphOnlyToggle.uncheck();
  await expect(page.locator(".curve-legend button")).toHaveCount(5);

  const recommendationResponse = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && response.url().endsWith("/api/v1/processing/dma-frequency-master-curves/recommendations/multi-frequency")
  ));
  await page.getByRole("button", { name: "Prepare recommendation", exact: true }).click();
  const recommendationHttp = await recommendationResponse;
  expect(recommendationHttp.ok()).toBeTruthy();
  const recommendation = await recommendationHttp.json() as {
    reference_sweep_ordinal: number;
    reference_temperature_k: number;
    sweep_dispositions: Array<{ source_sweep_ordinal: number; partition: string }>;
  };
  expect(recommendation.reference_sweep_ordinal).toBe(NIST_SRM_2491_REFERENCE_SWEEP_ORDINAL);
  expect(recommendation.reference_temperature_k).toBe(NIST_SRM_2491_REFERENCE_TEMPERATURE_K);
  expect(recommendation.sweep_dispositions.find(
    (item) => item.source_sweep_ordinal === NIST_SRM_2491_HOLDOUT_SWEEP_ORDINAL,
  )?.partition).toBe("HOLDOUT");
  await expect(page.getByText("Sweeps included", { exact: true })).toBeVisible();
  await expect(page.getByText("6 of 6", { exact: true })).toBeVisible();
  await expect(graphOnlyToggle).not.toBeChecked();
  await graphOnlyToggle.check();
  await expect(page.locator(".curve-legend button")).toHaveCount(6);
  await expect(page.getByText(`${NIST_SRM_2491_REFERENCE_TEMPERATURE_K} K · #${NIST_SRM_2491_REFERENCE_SWEEP_ORDINAL}`, { exact: true })).toBeVisible();

  const settingsDisclosure = page.locator("details.dma-tts-settings-disclosure");
  await expect(settingsDisclosure).not.toHaveAttribute("open", "");
  await expect(page.getByLabel("Shift method")).toBeHidden();
  await expect(page.getByRole("button", { name: "TTS settings", exact: true })).toHaveCount(0);
  await settingsDisclosure.locator("summary").click();
  await expect(settingsDisclosure).toHaveAttribute("open", "");
  await expect(page.getByLabel("Reference curve")).toHaveValue(String(NIST_SRM_2491_REFERENCE_SWEEP_ORDINAL));
  await expect(page.getByLabel(`Analysis role for sweep ${NIST_SRM_2491_REFERENCE_SWEEP_ORDINAL}`)).toBeDisabled();
  const visibleSweepRole = page.getByLabel("Analysis role for sweep 2");
  await expect(visibleSweepRole.locator("option")).toHaveText([
    "Fit — calculate TTS",
    "Validate — check result only",
    "Ignore — exclude",
  ]);
  await visibleSweepRole.selectOption("EXCLUDED");
  const ignoreReason = page.getByLabel("Reason for ignoring sweep 2");
  await expect(ignoreReason).toBeVisible();
  await ignoreReason.fill("Outside the selected fit range");
  await visibleSweepRole.selectOption("CALIBRATION");
  await expect(ignoreReason).toHaveCount(0);
  const law = page.getByLabel("Shift method");
  await expect(law).toBeVisible();
  await expect(law.locator("option")).toHaveText([
    "WLF fit",
    "Arrhenius fit",
    "Manual",
  ]);
  await expect(page.locator('input[name="dma-tts-adjacent-xatol"]')).toHaveAttribute("readonly", "");
  await expect(page.locator('input[name="dma-tts-law-ftol"]')).toHaveAttribute("readonly", "");
  await page.setViewportSize({ width: 1920, height: 1080 });
  await capture(page, "issue-392-central-tts-settings-1920x1080.png");
  await settingsDisclosure.locator("summary").click();
  await expect(settingsDisclosure).not.toHaveAttribute("open", "");
  await captureIssue392ProcessState(page, "recommendation");

  const createResponse = page.waitForResponse((response) => (
    response.request().method() === "POST"
    && response.url().endsWith("/api/v1/processing/dma-frequency-master-curves")
  ));
  const exactReadResponse = page.waitForResponse((response) => (
    response.request().method() === "GET"
    && /\/api\/v1\/processing\/dma-frequency-master-curves\/[^/]+\/revisions\/[^/?]+\?content_sha256=/.test(response.url())
  ));
  await page.getByRole("button", { name: "Save TTS result", exact: true }).click();
  const createdHttp = await createResponse;
  expect(createdHttp.status()).toBe(201);
  const created = await createdHttp.json() as {
    master_curve_output: { output_id: string; revision_id: string; content_sha256: string };
  };
  const exactReadHttp = await exactReadResponse;
  expect(exactReadHttp.ok()).toBeTruthy();
  expect(new URL(exactReadHttp.url()).searchParams.get("content_sha256"))
    .toBe(created.master_curve_output.content_sha256);
  await expect(page.getByRole("heading", { name: "TTS result saved" })).toBeVisible({ timeout: 60_000 });
  await expect(page.locator(".dma-legend-line-key", { hasText: "Raw" })).toBeVisible();
  await expect(page.locator(".dma-legend-line-key", { hasText: "Shifted" })).toBeVisible();
  await expect(page.locator(".dma-tts-saved-row").getByText("Ready for Prony Fit.", { exact: true })).toBeVisible();
  const calculationDetails = page.locator(".dma-tts-result-details");
  await calculationDetails.getByText("Calculation details", { exact: true }).click();
  const backendResults = page.getByRole("table").filter({ hasText: "Applied log10(aT)" });
  await expect(backendResults.locator("tbody > tr")).toHaveCount(6);
  await expect(backendResults.getByRole("cell", { name: "Validate", exact: true })).toBeVisible();
  await expect(page.locator(".curve-legend button")).toHaveCount(6);
  await expect(page.locator(".dma-legend-line-key", { hasText: "Raw" })).toBeVisible();
  await expect(page.locator(".dma-legend-line-key", { hasText: "Shifted" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: /^Show .* K on graph$/ })).toHaveCount(6);
  await expect(page.getByLabel("Show 273.15 K on graph")).toBeEnabled();
  expect(processCreateRequests).toHaveLength(1);
  await calculationDetails.getByText("Calculation details", { exact: true }).click();
  await captureIssue392ProcessState(page, "saved");

  const continueToFit = page.getByRole("button", { name: "Continue to Prony Fit", exact: true });
  await expect(continueToFit).toBeEnabled();
  await continueToFit.click();
  await expect(page).toHaveURL(/stage=fit/);
  await expect(page.getByRole("heading", { name: "Shifted DMA response" })).toBeVisible({ timeout: 30_000 });
  const dmaSession = await page.evaluate(() => JSON.parse(
    window.sessionStorage.getItem("cmp.modeling.recent-session.v4") ?? "null",
  )) as {
    material: { id: string; revisionId: string };
    materialState: { id: string; revisionId: string };
  };
  await approveSyntheticDmaFitSetup({
    request: page.request,
    webUrl,
    material: dmaSession.material,
    materialState: dmaSession.materialState,
    processingOutput: {
      id: created.master_curve_output.output_id,
      revisionId: created.master_curve_output.revision_id,
    },
  });
  await page.reload();
  await expect(page.getByRole("heading", { name: "Shifted DMA response" })).toBeVisible({ timeout: 30_000 });
  const decision = await calculateAndSelectAlternateModel(
    page,
    "Selected the adjacent Prony candidate after comparing the NIST DMA response and point differences.",
  );
  await page.getByRole("button", { name: "Save fit & continue", exact: true }).click();
  await expect(page).toHaveURL(/stage=export/, { timeout: 60_000 });
  const fitStage = page.locator(".modeling-stage-shell button").filter({
    has: page.locator("strong", { hasText: /^Fit$/ }),
  });
  await fitStage.click();
  await expect(page).toHaveURL(/stage=fit/);
  await expectDistinctFitDecision(page, decision);
  await page.screenshot({
    path: resolve(issue392EvidenceDir, "after/originals/modeling-fit-polymer-dma-selection-saved-1920x1080.png"),
    animations: "disabled",
    fullPage: false,
  });
  await page.reload();
  await expect(page).toHaveURL(/stage=fit/);
  await expect(page.getByRole("heading", { name: "Shifted DMA response" })).toBeVisible({ timeout: 30_000 });
  await expectDistinctFitDecision(page, decision);
  await expect.poll(() => pageErrors, { message: pageErrors.join("\n") }).toEqual([]);
  expect(processCreateRequests).toHaveLength(1);
});

test("a user calculates, compares, saves, and reloads an exact Polymer Fit at FHD", async ({
  page,
}) => {
  test.setTimeout(360_000);
  await page.setViewportSize({ width: 1920, height: 1080 });
  const accessToken = await installDemoUser(page);
  await openPolymerModeling(page, accessToken);
  await selectRelaxationInputAndOpenFit(page);

  await expect(page.getByRole("region", { name: "Calculate Prony models" })).toBeVisible();
  const inputReview = page.locator(".polymer-input-review-values");
  await expect(inputReview).not.toHaveAttribute("open");
  await expect(page.getByText("Approved", { exact: true })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Calculate Prony models" }),
  ).toBeEnabled({ timeout: 30_000 });
  await inputReview.getByText("Input details", { exact: true }).click();
  await expect(inputReview.getByText("Used to fit", { exact: true })).toBeVisible();
  await expect(inputReview.getByText("Used to verify", { exact: true })).toBeVisible();
  await expect(inputReview.getByText("Not used", { exact: true })).toBeVisible();
  await expect(inputReview.getByText("35 points", { exact: true })).toBeVisible();
  await expect(inputReview.getByText("5 points", { exact: true })).toBeVisible();
  await expect(inputReview.getByText("3 points", { exact: true })).toBeVisible();
  await expect(inputReview.getByText("Revision", { exact: true })).toHaveCount(0);
  await inputReview.getByText("Input details", { exact: true }).click();
  const normalSurface = await page
    .locator(".polymer-calibration-fit")
    .innerText();
  expect(normalSurface).not.toMatch(
    /\b(?:digest|sha-?256|candidate[_ ]?id|plan[_ ]?id|revision[_ ]?id)\b/i,
  );
  await expectInsideViewport(page.locator(".polymer-calibration-fit"));
  await expectInsideViewport(page.locator(".polymer-fit-command-ribbon"));
  await expectInsideViewport(page.locator(".polymer-fit-graph-region"));
  await expectInsideViewport(page.locator(".modeling-workspace-dock"));
  await expectUsableFitComposition(page);
  await capture(page, "modeling-fit-polymer-input-1920x1080.png");
  await capture(
    page,
    "modeling-fit-polymer-input-controls-1920x1080.png",
    page.locator(".modeling-workspace-dock"),
  );
  await capture(
    page,
    "modeling-fit-polymer-input-graph-1920x1080.png",
    page.locator(".polymer-fit-graph-region"),
  );

  const calculationSettings = page.getByRole("button", { name: "Calculation settings" });
  await calculationSettings.focus();
  await page.keyboard.press("Enter");
  const settingsDialog = page.getByRole("dialog", { name: "Calculation settings" });
  await expect(settingsDialog).toBeVisible();
  await expect(settingsDialog.getByRole("radio", { name: "Automatic" })).toBeChecked();
  await expect(settingsDialog).toContainText(
    "Fit will compare every feasible Prony term from 1 through 10.",
  );
  const manualSettings = settingsDialog.getByRole("radio", { name: "Manual" });
  await manualSettings.focus();
  await page.keyboard.press("Space");
  await expect(manualSettings).toBeChecked();
  await expect(settingsDialog.getByRole("checkbox", { name: /^10-term Prony/ })).toBeChecked();
  const modelSettings = settingsDialog.locator(".polymer-model-step");
  await modelSettings.evaluate((element) => {
    element.scrollIntoView({ block: "start" });
  });
  const parameterRanges = settingsDialog.locator(".polymer-bound-editor");
  await expect(parameterRanges.getByRole("row")).toHaveCount(22);
  await expectInsideViewport(parameterRanges);
  const finalManualParameter = parameterRanges.getByRole("rowheader", {
    name: "Relaxation time τ10",
  });
  await parameterRanges.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  await expectInsideViewport(finalManualParameter);
  await capture(page, "modeling-fit-polymer-calculation-settings-1920x1080.png");
  await settingsDialog.getByRole("button", { name: "Restore calculation defaults" }).click();
  await page.keyboard.press("Escape");
  await expect(settingsDialog).toHaveCount(0);
  await expect(calculationSettings).toBeFocused();

  const decision = await calculateAndSelectAlternateModel(
    page,
    "Selected the adjacent model after comparing fit and check differences.",
  );
  const candidates = page.getByRole("table", { name: "Calculated model comparison" });
  const recommended = candidates
    .locator("tbody > tr")
    .filter({ hasText: "Recommended" })
    .first();
  await expect(recommended.locator("td").nth(0)).not.toHaveText("—");
  await expect(recommended.locator("td").nth(1)).not.toHaveText("—");
  const promotionRoute = /\/api\/v1\/linear-viscoelastic-calibration-selections\/[^/]+\/linear-viscoelastic-model$/;
  let promotionAttempts = 0;
  await page.route(promotionRoute, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    promotionAttempts += 1;
    if (promotionAttempts === 1) {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Injected fitted-model save failure" }),
      });
      return;
    }
    await route.continue();
  });
  const save = page.getByRole("button", { name: "Save fit & continue" });
  await expect(save).toBeEnabled();
  await save.focus();
  await page.keyboard.press("Enter");
  const saveFailure = page.getByText("Model could not be saved", { exact: true });
  await expect(saveFailure).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("textbox", { name: "Reason for selection" })).toHaveValue(decision.reason);
  await expect(
    candidates.getByRole("radio", { name: `Select ${decision.selectedTerm}-term Prony` }),
  ).toBeChecked();
  await expect(page.getByRole("button", { name: "Continue to Export" })).toHaveCount(0);
  await capture(page, "modeling-fit-polymer-save-failed-1920x1080.png");
  const retry = page.getByRole("button", { name: "Retry save & continue", exact: true });
  await retry.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/stage=export/, { timeout: 60_000 });
  expect(promotionAttempts).toBe(2);
  await page.unroute(promotionRoute);
  await page.locator(".modeling-stage-shell button").filter({
    has: page.locator("strong", { hasText: /^Fit$/ }),
  }).click();
  await expect(page).toHaveURL(/stage=fit/);
  await expect(candidates).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Continue to Export" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Recalculate" })).toHaveCount(0);
  await expect(page.locator(".error-banner")).toHaveCount(0);
  await page.getByText("Measured and model values", { exact: true }).click();
  const exactValues = page.getByRole("table", {
    name: "Exact measured and model values shown in the graph",
  });
  await expect(exactValues.getByRole("columnheader", { name: "Recommended model" })).toBeVisible();
  await expect(exactValues.getByRole("columnheader", { name: "Selected model" })).toBeVisible();
  await expect(exactValues.locator("tbody > tr").first().locator("td").nth(3)).not.toHaveText("—");
  await expect(exactValues.locator("tbody > tr").first().locator("td").nth(4)).not.toHaveText("—");
  await page.getByText("Measured and model values", { exact: true }).click();
  await page.getByText("Model coefficients", { exact: true }).click();
  const coefficients = page.locator(".polymer-model-coefficients > div");
  await expect(
    page.getByRole("table", { name: `${decision.selectedTerm}-term Prony coefficients` }),
  ).toBeVisible();
  const finalCoefficient = page.getByRole("rowheader", { name: `Relaxation time τ${decision.selectedTerm}` });
  await expect(finalCoefficient).toHaveCount(1);
  const coefficientGeometry = await coefficients.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }));
  expect(coefficientGeometry.scrollHeight).toBeGreaterThan(
    coefficientGeometry.clientHeight,
  );
  await coefficients.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  await expect(finalCoefficient).toBeVisible();
  await page.getByText("Model coefficients", { exact: true }).click();
  await page.getByRole("button", { name: "Point differences" }).click();
  await expect(page.getByRole("img", { name: /^Differences on used points/i })).toBeVisible();
  await expect(page.getByRole("img", { name: /^Differences on check points/i })).toBeVisible();
  const resultsScroller = page.locator(".modeling-workspace-dock");
  await expectInsideViewport(resultsScroller);
  const candidateScrollGeometry = await page.locator(".modeling-fit-candidate-table-wrap").evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
    overflowY: getComputedStyle(element).overflowY,
  }));
  expect(candidateScrollGeometry.overflowY).toBe("auto");
  expect(candidateScrollGeometry.scrollHeight).toBeGreaterThanOrEqual(candidateScrollGeometry.clientHeight);
  await expectUsableFitComposition(page);
  await expect(page.locator(".error-banner")).toHaveCount(0);
  await capture(page, "modeling-fit-polymer-residual-1920x1080.png");
  await capture(
    page,
    "modeling-fit-polymer-saved-residual-1920x1080.png",
    page.locator(".polymer-fit-graph-region"),
  );
  await page.getByRole("button", { name: "Response curves" }).click();
  await expect(page.getByRole("img", { name: /Measured relaxation data with recommended and selected model responses/i })).toBeVisible();
  await capture(page, "modeling-fit-polymer-saved-1920x1080.png");
  await capture(
    page,
    "modeling-fit-polymer-saved-header-1920x1080.png",
    page.locator(".application-menu-bar"),
  );
  await capture(
    page,
    "modeling-fit-polymer-saved-decision-1920x1080.png",
    page.locator(".modeling-fit-decision-dock"),
  );
  await capture(
    page,
    "modeling-fit-polymer-saved-controls-1920x1080.png",
    page.locator(".modeling-workspace-dock"),
  );
  await capture(page, "modeling-fit-polymer-saved-graph-1920x1080.png", page.locator(".polymer-fit-graph-region"));

  await page.reload();
  await expect(page.locator(".polymer-calibration-fit")).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByRole("button", { name: "Continue to Export" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    page.getByRole("textbox", { name: "Reason for selection" }),
  ).toHaveValue(/Selected the adjacent model/);
  await expectDistinctFitDecision(page, decision);
  await expect(page.getByRole("button", { name: "Recalculate" })).toHaveCount(0);
  await persistModelingSession(page);
});

test("the saved Polymer Fit remains usable at every acceptance viewport", async ({
  page,
}) => {
  test.setTimeout(240_000);
  await installDemoUser(page);
  await restoreModelingSession(page);
  await page.goto("/modeling?stage=fit&family=polymer");
  await expect(page.locator(".polymer-calibration-fit")).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByRole("button", { name: "Continue to Export" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    page.getByRole("textbox", { name: "Reason for selection" }),
  ).toHaveValue(/Selected the adjacent model/);
  const persistedCandidates = page.getByRole("table", { name: "Calculated model comparison" });
  const persistedRecommendation = persistedCandidates.locator("tbody > tr").filter({ hasText: "Recommended" }).first();
  await expect(persistedRecommendation.getByRole("radio")).not.toBeChecked();
  await expect(persistedCandidates.locator('input[type="radio"]:checked')).toHaveCount(1);
  const persistedLegend = page.getByLabel("Response graph legend");
  await expect(persistedLegend.getByText("Recommended model", { exact: true })).toBeVisible();
  await expect(persistedLegend.getByText("Selected model", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Recalculate" })).toHaveCount(0);
  await captureAcceptanceViewports(page);
});

test("a changed Test Data input makes the saved model stale and restores its exact input", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1920, height: 1080 });
  const accessToken = await installDemoUser(page);
  await restoreModelingSession(page);
  const changedRevisionId = await createChangedUpstreamRevision(
    page,
    accessToken,
  );
  await page.goto("/modeling?stage=fit&family=polymer");
  await expect(page.getByRole("button", { name: "Continue to Export" })).toBeVisible({
    timeout: 30_000,
  });

  const stageButton = (name: "Data" | "Fit") =>
    page.locator(".modeling-stage-shell button").filter({
      has: page.locator("strong", { hasText: new RegExp(`^${name}$`) }),
    });
  await stageButton("Data").click();
  const changedInput = page.locator(
    `[data-document-key="CMP-DEMO-POLYMER-FIT-RELAXATION-CSV"][data-revision-id="${changedRevisionId}"]`,
  );
  await expect(changedInput).toHaveCount(1);
  await expect(
    page.getByRole("alert").filter({ hasText: /required channel/i }),
  ).toHaveCount(0);
  await changedInput.locator(".modeling-data-record-button").click();
  await expect(changedInput).toHaveClass(/active/, { timeout: 30_000 });

  await stageButton("Fit").click();
  const staleMessage = page.locator(".polymer-stale-message");
  await expect(staleMessage.getByText("Input changed", { exact: true })).toBeVisible({
    timeout: 30_000,
  });
  const staleInputs = staleMessage.getByRole("list", { name: "Saved and current Fit inputs" });
  await expect(staleInputs).toContainText("Saved result input");
  await expect(staleInputs).toContainText("Current input");
  const savedInputLabel = staleInputs.locator("dd").nth(0);
  const currentInputLabel = staleInputs.locator("dd").nth(1);
  await expect(savedInputLabel).toContainText(/version \d+$/);
  await expect(currentInputLabel).toContainText(/version \d+$/);
  expect(await savedInputLabel.innerText()).not.toBe(await currentInputLabel.innerText());
  await expect(staleMessage.locator("details")).toHaveCount(0);
  await expect(staleMessage).not.toContainText(/Revision/i);
  await expect(page.getByRole("table", { name: "Calculated model comparison" })).toHaveCount(0);
  await expect(
    page.getByRole("img", { name: /Measured relaxation data/i }),
  ).toBeVisible({ timeout: 30_000 });
  await capture(page, "modeling-fit-polymer-stale-1920x1080.png");

  const restoreSavedInput = staleMessage.getByRole("button", { name: "Restore saved input" });
  await restoreSavedInput.focus();
  await page.keyboard.press("Enter");
  await expect(staleMessage).toHaveCount(0, { timeout: 30_000 });
  await expect(
    page.getByRole("textbox", { name: "Reason for selection" }),
  ).toHaveValue(/Selected the adjacent model/, { timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Continue to Export" })).toBeVisible();
  await expect(
    page.getByRole("table", { name: "Calculated model comparison" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Recalculate" })).toHaveCount(0);
  await page.getByText("Model coefficients", { exact: true }).click();
  await expect(page.locator(".polymer-model-coefficients[open]")).toBeVisible();
  await capture(page, "modeling-fit-polymer-stale-restored-saved-input-1920x1080.png");
  await page.getByText("Model coefficients", { exact: true }).click();

  await stageButton("Data").click();
  await expect(changedInput).toHaveCount(1);
  await changedInput.locator(".modeling-data-record-button").click();
  await expect(changedInput).toHaveClass(/active/, { timeout: 30_000 });
  await stageButton("Fit").click();
  await expect(staleMessage.getByText("Input changed", { exact: true })).toBeVisible({
    timeout: 30_000,
  });
  const useCurrentInput = staleMessage.getByRole("button", { name: "Use current input" });
  await useCurrentInput.focus();
  await page.keyboard.press("Space");
  await expect(staleMessage).toHaveCount(0, { timeout: 30_000 });
  await expect(page.getByRole("region", { name: "Calculate Prony models" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Calculated model comparison" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Continue to Export" })).toHaveCount(0);
  await expect(page.getByText("Calculation settings need review", { exact: true })).toBeVisible({ timeout: 30_000 });
  await capture(page, "modeling-fit-polymer-stale-recovered-1920x1080.png");
});

test("the shared Modeling shell preserves the Metal Data to Export journey", async ({
  page,
}) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await installDemoUser(page, "administrator");
  await page.goto("/modeling?stage=data&family=metal");
  const source = page.locator(
    '[data-document-key="CMP-DEMO-DP780-TEST-JSON"]',
  );
  await expect(source).toHaveCount(1, { timeout: 30_000 });
  await source.locator(".modeling-data-record-button").click();
  await expect(source).toHaveClass(/active/, { timeout: 30_000 });

  const technical = page.locator("details.modeling-data-technical-details");
  if (!(await technical.getAttribute("open"))) {
    await technical.locator(":scope > summary").click();
  }
  const mapping = technical.getByRole("combobox", {
    name: "Saved Mapping Profile",
  });
  await expect.poll(async () => mapping.locator("option").count(), {
    timeout: 30_000,
  }).toBeGreaterThanOrEqual(2);
  await mapping.selectOption({ index: 1 });
  await expect(mapping).not.toHaveValue("");
  await technical.locator(":scope > summary").click();

  await page.getByRole("button", { name: "Continue to Process" }).click();
  await expect(page).toHaveURL(/stage=process/);
  await expect(page.locator(".modeling-work-title h1")).toHaveText(
    "Process Test Data",
    { timeout: 30_000 },
  );
  const previewProcess = page.getByRole("button", {
    name: "Preview changes",
    exact: true,
  });
  await expect(previewProcess).toBeEnabled({ timeout: 30_000 });
  await previewProcess.click();
  await expect(page.getByText("Preview ready", { exact: false })).toBeVisible({
    timeout: 60_000,
  });
  const processPanel = page.locator('[data-modeling-process-panel="ready"]');
  await processPanel
    .getByRole("textbox", { name: "Process result name" })
    .fill("Metal regression Process result");
  await processPanel
    .getByRole("textbox", { name: "Reason for saving Process result" })
    .fill("Verify the shared Modeling shell through Metal Fit and Export.");
  await processPanel.getByRole("button", { name: "Save Process result" }).click();
  await expect(
    page.getByText("Processed result saved and current", { exact: false }),
  ).toBeVisible({ timeout: 60_000 });

  const stageButton = (name: "Fit" | "Export") =>
    page.locator(".modeling-stage-shell button").filter({
      has: page.locator("strong", { hasText: new RegExp(`^${name}$`) }),
    });
  await stageButton("Fit").click();
  await expect(page).toHaveURL(/stage=fit/);
  await expect(page.locator(".modeling-work-title h1")).toHaveText(
    "Fit Material Model",
    { timeout: 30_000 },
  );
  const previewFit = page.getByRole("button", {
    name: "Calculate models",
    exact: true,
  });
  await expect(previewFit).toBeEnabled({ timeout: 30_000 });
  await previewFit.click();
  const candidateTable = page.getByRole("table", {
    name: "Calculated model comparison",
  });
  await expect(candidateTable).toBeVisible({ timeout: 60_000 });
  for (const viewport of acceptanceViewports) {
    const size = `${viewport.width}x${viewport.height}`;
    await page.setViewportSize(viewport);
    await expectInsideViewport(page.locator(".modeling-main-surface"));
    await expectInsideViewport(page.locator(".modeling-fit-decision-dock"));
    await expectInsideViewport(page.locator(".modeling-fit-candidate-table-wrap"));
    const legendTickOverlaps = await page.locator(".engineering-plot-frame").evaluate((frame) => {
      const legend = frame.querySelector<HTMLElement>(".curve-legend");
      if (!legend) return ["legend missing"];
      const legendRect = legend.getBoundingClientRect();
      return [...frame.querySelectorAll<SVGGraphicsElement>(".chart-tick")]
        .filter((tick) => {
          const rect = tick.getBoundingClientRect();
          return rect.right > legendRect.left
            && rect.left < legendRect.right
            && rect.bottom > legendRect.top
            && rect.top < legendRect.bottom;
        })
        .map((tick) => tick.textContent ?? "tick");
    });
    expect(legendTickOverlaps, `${size} legend overlaps axis ticks`).toEqual([]);
    await capture(page, `modeling-fit-metal-${size}.png`);
  }
  await page.setViewportSize({ width: 1920, height: 1080 });
  await candidateTable.getByRole("radio", { name: /^Select /i }).first().check();
  await page
    .getByRole("textbox", { name: "Candidate selection reason" })
    .fill("Preserve the reviewed Metal path while extending Polymer Fit.");
  const acknowledgement = page.getByRole("checkbox", {
    name: "Acknowledge selected candidate warning",
  });
  if (await acknowledgement.count()) await acknowledgement.check();
  const saveFit = page.getByRole("button", {
    name: "Save fit & continue",
    exact: true,
  });
  await expect(saveFit).toBeEnabled({ timeout: 30_000 });
  await saveFit.click();
  await expect(page.locator(".fit-surface-state")).toContainText("Saved current", {
    timeout: 60_000,
  });

  await stageButton("Export").click();
  await expect(page).toHaveURL(/stage=export/);
  await expect(
    page.locator(".modeling-target-preview, .modeling-export-blocked"),
  ).toBeVisible({ timeout: 60_000 });
  const session = await page.evaluate(() =>
    JSON.parse(window.sessionStorage.getItem("cmp.modeling.recent-session.v4") ?? "{}"),
  ) as { processingOutput?: { id?: string; revisionId?: string } };
  expect(session.processingOutput?.id).toBeTruthy();
  expect(session.processingOutput?.revisionId).toBeTruthy();
});
