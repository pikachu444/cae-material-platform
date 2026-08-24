import { expect, test, type Page } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const forbiddenNormalTechnicalLabels = /\b(?:draft|fixture|uuid|sha(?:256)?|hash|lifecycle[_\s-]?state)\b|\bissue\s*#\s*\d+\b|\bimplementation state\b/i;
const representativeDp780Tests = [
  "DP780 tensile · 23 °C · 0.0067 s⁻¹ · synthetic reference",
  "DP780 tensile · 80 °C · 0.0067 s⁻¹ · synthetic reference",
  "DP780 tensile · 23 °C · 0.0007 s⁻¹ · synthetic reference",
  "DP780 tensile · 23 °C · 0.067 s⁻¹ · synthetic reference",
  "DP780 FLD · Nakajima · synthetic reference",
  "DP780 FLD · Marciniak · synthetic reference",
] as const;
const dp780SolverCardRecord = "DP780 Abaqus native material card · synthetic reference";

async function expectMaterialsReady(page: Page): Promise<void> {
  const results = page.locator(".materials-results");
  await expect(results).toBeVisible({ timeout: 30_000 });
  await expect
    .poll(async () => (await results.getAttribute("aria-busy")) ?? "false", { timeout: 30_000 })
    .toBe("false");
  await expect(results.getByText("Loading…", { exact: true })).toHaveCount(0, { timeout: 30_000 });
}

async function openMaterialFilters(page: Page): Promise<void> {
  const search = page.getByRole("textbox", { name: "Search materials" });
  if ((await search.count()) === 0) {
    const filters = page.getByRole("button", { name: "Filters", exact: true });
    await expect(filters).toBeVisible({ timeout: 30_000 });
    await filters.click();
  }
  await expect(search).toBeVisible({ timeout: 15_000 });
  await expectMaterialsReady(page);
}

test("clean demo exposes Search-first material-family journeys and progressive bulk entry", async ({ page, request }) => {
  test.setTimeout(180_000);
  const tokenResponse = await request.get(`${webUrl}/api/v1/demo-identity/token`);
  expect(tokenResponse.ok()).toBeTruthy();
  const tokenPayload = (await tokenResponse.json()) as { access_token: string };

  await page.addInitScript(
    ({ accessToken }) => {
      window.localStorage.setItem(
        "cmp.material-platform.api-config",
        JSON.stringify({ baseUrl: "/api/v1", accessToken }),
      );
    },
    { accessToken: tokenPayload.access_token },
  );

  await page.goto("/");
  await expect(page).toHaveURL(/\/materials$/);
  await expect(page.getByRole("heading", { name: "Materials", level: 1 })).toBeVisible();
  await openMaterialFilters(page);
  await expectMaterialsReady(page);

  for (const materialCode of [
    "CMP-DEMO-DP780",
    "CMP-DEMO-POLYMER-PRONY",
    "CMP-DEMO-ELASTOMER-OGDEN",
  ] as const) {
    await page.getByRole("textbox", { name: "Search materials" }).fill(materialCode);
    await page.getByLabel("Material query").getByRole("button", { name: "Find", exact: true }).click();
    await expectMaterialsReady(page);
    const resultRow = page.getByRole("row").filter({ hasText: materialCode });
    await expect(resultRow).toBeVisible();
    const expectedReference = materialCode === "CMP-DEMO-DP780"
      ? /Synthetic reference/i
      : /synthetic T-60 reference/i;
    const expectedName = materialCode === "CMP-DEMO-DP780"
      ? "DP780 synthetic reference steel"
      : materialCode === "CMP-DEMO-POLYMER-PRONY"
        ? "Synthetic Polymer Prony"
        : "Synthetic Elastomer Ogden-Prony";
    const staleHumanNames = /synthetic demo steel|Demo Polymer Prony|Demo Elastomer Ogden-Prony/i;
    const normalResultsText = await page.locator(".materials-page").innerText();
    expect(normalResultsText).not.toMatch(/clean product demo|local demo|fixture/i);
    expect(normalResultsText).not.toMatch(staleHumanNames);
    expect(normalResultsText).toContain(expectedName);
    expect(normalResultsText).toMatch(expectedReference);
    expect(normalResultsText).not.toContain("not validated for engineering use");
    const normalResultsSurfaceText = await page.locator(".materials-results").innerText();
    expect(normalResultsSurfaceText).not.toMatch(forbiddenNormalTechnicalLabels);
    expect(normalResultsSurfaceText).toContain(expectedName);
    expect(normalResultsSurfaceText).toContain("Family");
    await expect(page.getByRole("columnheader", { name: "Status", exact: true })).toHaveCount(0);
    await resultRow.getByRole("button").click();
    await expect(page).toHaveURL(/\/materials\/[0-9a-f-]+\?record_id=[0-9a-f-]+&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$/);
    await expect(page.getByRole("complementary", { name: "Materials Browse Tree" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("tab", { name: "CAE Cards" })).toBeVisible();
    await expect(page.getByText(/^(Request review|Waiting for review|Approved|Changes requested)$/).first()).toBeVisible({ timeout: 15_000 });
    const normalDetailText = await page.locator(".material-detail-shell").innerText();
    expect(normalDetailText).not.toMatch(/clean product demo|local demo|fixture/i);
    expect(normalDetailText).not.toMatch(staleHumanNames);
    expect(normalDetailText).toContain(expectedName);
    const normalDetailHeaderText = await page.locator(".material-detail-header").innerText();
    const relatedContextText = await page.getByRole("region", { name: "Related data" }).innerText();
    const normalStatusBarText = await page.locator(".application-status-bar").innerText();
    expect(normalDetailHeaderText).not.toMatch(forbiddenNormalTechnicalLabels);
    expect(relatedContextText).not.toMatch(forbiddenNormalTechnicalLabels);
    expect(normalStatusBarText).not.toMatch(forbiddenNormalTechnicalLabels);
    expect(normalStatusBarText).toMatch(/\br\d+\b/);
    expect(normalDetailHeaderText).toMatch(/Request review|Waiting for review|Approved|Changes requested/);
    expect(relatedContextText).toContain("Revision");
    expect(relatedContextText).toContain("Related");
    await page.getByRole("tab", { name: "Source & history", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Linked records", exact: true })).toBeVisible();
    const linkedRecordsTable = page.locator(".evidence-overview table");
    if (await linkedRecordsTable.count()) {
      await expect(linkedRecordsTable.getByRole("columnheader", { name: "Relation", exact: true })).toBeVisible();
      await expect(linkedRecordsTable.getByRole("columnheader", { name: "Target record", exact: true })).toBeVisible();
      await expect(linkedRecordsTable.getByRole("columnheader", { name: "Type", exact: true })).toBeVisible();
      await expect(linkedRecordsTable.getByRole("columnheader", { name: "Exact revision", exact: true })).toBeVisible();
    } else {
      await expect(page.getByText("No related records are visible in the current view.", { exact: true })).toBeVisible();
    }
    await expect(page.getByText("Full lineage", { exact: true })).toBeVisible();
    await expect(page.locator("details.full-lineage")).not.toHaveAttribute("open", "");
    await expect(page.getByRole("heading", { name: "Workflow", exact: true })).toHaveCount(0);
    await expect(page.getByText("Follow related records and the exact material workflow; open technical identifiers only when needed.", { exact: true })).toHaveCount(0);
    await expect(page.locator(".material-tab-panel")).toContainText(expectedReference);
    await page.getByRole("tab", { name: "Overview", exact: true }).click();
    if (materialCode === "CMP-DEMO-DP780") {
      for (const representativeTest of representativeDp780Tests) {
        expect(relatedContextText).toContain(representativeTest);
      }
    }
    const treeFind = page.getByRole("textbox", { name: "Find in tree" });
    await treeFind.fill(expectedName);
    await treeFind.press("Enter");
    await expect(page.locator(".materials-left-pane")).toContainText(expectedName, { timeout: 15_000 });
    const normalTreeText = await page.locator(".materials-left-pane").innerText();
    expect(normalTreeText).not.toMatch(staleHumanNames);
    expect(normalTreeText).toContain(expectedName);
    if (materialCode === "CMP-DEMO-DP780") {
      const exactMaterialRevisionId = new URL(page.url()).searchParams.get("material_revision_id");
      expect(exactMaterialRevisionId).toBeTruthy();
      await page.getByRole("treeitem", { name: /Solver Cards/ }).click();
      await expect(page.locator(".materials-left-pane")).toContainText(dp780SolverCardRecord, {
        timeout: 15_000,
      });
      await page.getByRole("tab", { name: "CAE Cards" }).click();
      await expect(page.getByText("No native card is available.", { exact: true })).toBeVisible();
      const startModeling = page
        .getByRole("tabpanel")
        .getByRole("button", { name: "Start Modeling", exact: true });
      await expect(startModeling).toBeVisible();
      await startModeling.click();
      await expect(page).toHaveURL(/\/modeling\?stage=data&family=metal&material_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+&material_state_id=[0-9a-f-]+&material_state_revision_id=[0-9a-f-]+$/);
      await expect(page.getByRole("heading", { name: "Select Test Data" })).toBeVisible({ timeout: 30_000 });
      await expect(page.getByText("No Test Data selected", { exact: true })).toBeVisible();
      const exactSession = await page.evaluate(() =>
        JSON.parse(window.sessionStorage.getItem("cmp.modeling.recent-session.v4") ?? "null"),
      ) as {
        material?: { revisionId?: string };
        materialState?: { revisionId?: string };
        contextSelectionRequired?: boolean;
      } | null;
      expect(exactSession?.material?.revisionId).toBe(exactMaterialRevisionId);
      expect(exactSession?.materialState?.revisionId).toBeTruthy();
      expect(exactSession?.contextSelectionRequired).toBe(false);
    }
    await page.goto("/materials");
    await openMaterialFilters(page);
    await expectMaterialsReady(page);
  }

  await openMaterialFilters(page);
  await page.getByRole("textbox", { name: "Search materials" }).fill("CMP-DEMO-DP780");
  await page.getByLabel("Material query").getByRole("button", { name: "Find", exact: true }).click();
  await expectMaterialsReady(page);
  const dp780Row = page.getByRole("row").filter({ hasText: "CMP-DEMO-DP780" });
  await expect(dp780Row).toHaveCount(1);
  await dp780Row.press("Enter");
  await expect(page).toHaveURL(/\/materials\/[0-9a-f-]+\?record_id=[0-9a-f-]+&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$/);
  const relatedRecord = page.getByRole("region", { name: "Related data" }).getByRole("button").filter({ hasText: representativeDp780Tests[0] });
  await expect(relatedRecord).toBeVisible({ timeout: 15_000 });
  await expect(relatedRecord).toHaveCount(1);
  await expect(relatedRecord).toContainText("r1");
  await relatedRecord.click();
  await expect(page).toHaveURL(/\/materials\/records\/[0-9a-f-]+\/revisions\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: representativeDp780Tests[0], level: 1 })).toBeVisible({ timeout: 15_000 });
  await page.goBack();
  await expect(page).toHaveURL(/\/materials\/[0-9a-f-]+\?record_id=[0-9a-f-]+&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/materials\?q=CMP-DEMO-DP780/);
  await expect(page.getByRole("textbox", { name: "Search materials" })).toHaveValue("CMP-DEMO-DP780");
  await expectMaterialsReady(page);

  await page.goto("/activity");
  await expect(page.locator("main").getByRole("heading", { name: "Activity", exact: true, level: 1 })).toBeVisible();
  const selectedModelReview = page.getByRole("row").filter({ hasText: "Selected model review" }).first();
  await expect(selectedModelReview).toBeVisible();
  await expect(selectedModelReview).toContainText("Waiting for review");
  await page.getByRole("tab", { name: "Recent outcomes", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Recent outcomes", level: 2 })).toBeVisible();
  await expect(page.getByRole("table", { name: "Recent review outcomes" })).toBeVisible();
  await page.getByRole("tab", { name: "In progress", exact: true }).click();
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(selectedModelReview).toContainText("Waiting for review");
  const normalActivityText = await page.locator(".activity-content").innerText();
  expect(normalActivityText).not.toMatch(/\b(?:uuid|sha256|aggregate|revision_id|mapping profile|processing output|neutral json|provenance|checksum|recipe|batch)\b/i);
  expect(normalActivityText).not.toMatch(/\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b/i);
  await page.getByText("Advanced activity evidence", { exact: true }).click();
  await page.getByRole("button", { name: "Open export packages" }).click();
  await expect(page).toHaveURL(/\/exports$/);
});

test("Materials workspaces use the viewport and expose exact direct links across desktop widths", async ({ page, request }) => {
  test.setTimeout(180_000);
  const tokenResponse = await request.get(`${webUrl}/api/v1/demo-identity/token`);
  expect(tokenResponse.ok()).toBeTruthy();
  const tokenPayload = (await tokenResponse.json()) as { access_token: string };
  await page.addInitScript(
    ({ accessToken }) => {
      window.localStorage.setItem(
        "cmp.material-platform.api-config",
        JSON.stringify({ baseUrl: "/api/v1", accessToken }),
      );
    },
    { accessToken: tokenPayload.access_token },
  );

  const materialCode = "CMP-DEMO-DP780";
  const expectedName = "DP780 synthetic reference steel";
  const staleHumanNames = /synthetic demo steel|Demo Polymer Prony|Demo Elastomer Ogden-Prony/i;
  const staleStateRoutes = /Synthetic reference production route|Public synthetic reference route/i;
  for (const { width, height } of [
    { width: 1366, height: 768 },
    { width: 1440, height: 900 },
    { width: 1920, height: 1080 },
    { width: 2560, height: 1440 },
    { width: 3840, height: 2160 },
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto("/materials");
    await expect(page.getByRole("heading", { name: "Materials", level: 1 })).toBeVisible();
    await openMaterialFilters(page);
    await page.getByRole("textbox", { name: "Search materials" }).fill(materialCode);
    await page.getByLabel("Material query").getByRole("button", { name: "Find", exact: true }).click();
    await expectMaterialsReady(page);
    const resultRow = page.getByRole("row").filter({ hasText: materialCode });
    await expect(resultRow).toBeVisible();
    const resultsText = await page.locator(".materials-results").innerText();
    expect(resultsText).toContain(expectedName);
    expect(resultsText).not.toMatch(staleHumanNames);
    const searchGeometry = await page.locator(".materials-page").evaluate((element) => {
      const bounds = element.getBoundingClientRect();
      return { left: bounds.left, width: bounds.width };
    });
    expect(searchGeometry.left).toBeLessThanOrEqual(8);
    expect(searchGeometry.width).toBeGreaterThanOrEqual(width - 1);
    expect(searchGeometry.width).toBeLessThanOrEqual(width + 1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

    await resultRow.getByRole("button").click();
    const treeText = await page.locator(".materials-left-pane").innerText();
    expect(treeText).not.toMatch(staleHumanNames);
    await expect(page).toHaveURL(/\/materials\/[0-9a-f-]+\?record_id=[0-9a-f-]+&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$/);
    await expect(page.getByRole("heading", { name: expectedName, level: 1 })).toBeVisible({ timeout: 15_000 });
    const detailText = await page.locator(".material-detail-shell").innerText();
    expect(detailText).toContain(expectedName);
    expect(detailText).not.toMatch(staleHumanNames);
    expect(detailText).not.toMatch(staleStateRoutes);
    await expect(page.locator(".materials-left-pane")).toContainText(expectedName, { timeout: 15_000 });
    const detailGeometry = await page.locator(".materials-page").evaluate((element) => {
      const bounds = element.getBoundingClientRect();
      return { left: bounds.left, width: bounds.width };
    });
    expect(detailGeometry.left).toBeLessThanOrEqual(8);
    expect(detailGeometry.width).toBeGreaterThanOrEqual(width - 1);
    expect(detailGeometry.width).toBeLessThanOrEqual(width + 1);
    await expect(page.getByText("No representative curve preview.", { exact: true })).toHaveCount(0);
    const related = page.getByRole("region", { name: "Related data" });
    const fastTensile = related.getByRole("button").filter({ hasText: "DP780 tensile · 23 °C · 0.067 s⁻¹" });
    await expect(fastTensile).toHaveCount(1);
    await expect(fastTensile).toContainText("r1");
    const relatedBox = await related.evaluate((element) => {
      const bounds = element.getBoundingClientRect();
      return { left: bounds.left, right: bounds.right, width: bounds.width, height: bounds.height };
    });
    expect(relatedBox.left).toBeGreaterThanOrEqual(0);
    expect(relatedBox.right).toBeLessThanOrEqual(width + 1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
});

test("Activity queue has no horizontal overflow at required demo viewports", async ({ page, request }) => {
  const tokenResponse = await request.get(`${webUrl}/api/v1/demo-identity/token`);
  expect(tokenResponse.ok()).toBeTruthy();
  const tokenPayload = (await tokenResponse.json()) as { access_token: string };

  await page.addInitScript(
    ({ accessToken }) => {
      window.localStorage.setItem(
        "cmp.material-platform.api-config",
        JSON.stringify({ baseUrl: "/api/v1", accessToken }),
      );
    },
    { accessToken: tokenPayload.access_token },
  );

  for (const { width, height } of [
    { width: 1366, height: 768 },
    { width: 1440, height: 900 },
    { width: 1920, height: 1080 },
    { width: 2560, height: 1440 },
    { width: 3840, height: 2160 },
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto("/activity");
    await expect(page.locator("main").getByRole("heading", { name: "Activity", exact: true, level: 1 })).toBeVisible();
    await expect(page.getByText("Selected model review", { exact: true }).first()).toBeVisible();
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
      .toBe(true);
  }
});

test("canonical demo downloads exact Neutral cards and the governed ZIP", async ({ page, request }, testInfo) => {
  const tokenResponse = await request.get(`${webUrl}/api/v1/demo-identity/token`);
  expect(tokenResponse.ok()).toBeTruthy();
  const tokenPayload = (await tokenResponse.json()) as { access_token: string };
  const headers = { Authorization: `Bearer ${tokenPayload.access_token}` };

  const materialsResponse = await request.get(`${webUrl}/api/v1/materials?limit=100`, { headers });
  expect(materialsResponse.ok()).toBeTruthy();
  const materials = (await materialsResponse.json()) as {
    items: Array<{
      material_id: string;
      current_revision: { content: { material_code: string | null } };
    }>;
  };
  const metal = materials.items.find(
    (item) => item.current_revision.content.material_code === "CMP-DEMO-DP780",
  );
  expect(metal).toBeTruthy();

  const candidatesResponse = await request.get(
    `${webUrl}/api/v1/bulk-export-candidates?material_id=${metal!.material_id}`,
    { headers },
  );
  expect(candidatesResponse.ok()).toBeTruthy();
  const candidates = (await candidatesResponse.json()) as {
    items: Array<{
      source: { kind: string; neutral_solver_card_id?: string };
      source_sha256: string;
      default_archive_path: string;
    }>;
  };
  const canonicalNativeCards = candidates.items.filter(
    (item) => item.source.kind === "neutral_solver_card_native"
      && /\/CMP_DEMO_DP780_NEUTRAL\.(?:inp|rad)$/.test(item.default_archive_path),
  );
  expect(canonicalNativeCards).toHaveLength(2);
  const nativePaths = canonicalNativeCards.map((item) => item.default_archive_path);
  expect(nativePaths.some((path) => path.endsWith(".inp"))).toBeTruthy();
  expect(nativePaths.some((path) => path.endsWith(".rad"))).toBeTruthy();
  for (const card of canonicalNativeCards) {
    const response = await request.get(
      `${webUrl}/api/v1/neutral-solver-cards/${card.source.neutral_solver_card_id}/download`,
      { headers },
    );
    expect(response.ok()).toBeTruthy();
    const value = await response.body();
    expect(createHash("sha256").update(value).digest("hex")).toBe(
      card.source_sha256.replace("sha256:", ""),
    );
    expect(value.toString("utf8")).toMatch(/(\*MATERIAL|\/MAT\/LAW36|\*DENSITY|\*ELASTIC)/);
  }

  await page.addInitScript(
    ({ accessToken }) => {
      window.localStorage.setItem(
        "cmp.material-platform.api-config",
        JSON.stringify({ baseUrl: "/api/v1", accessToken }),
      );
    },
    { accessToken: tokenPayload.access_token },
  );
  await page.goto("/exports");
  await expect(page.getByRole("heading", { name: "Immutable bundles" })).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download ZIP" }).first().click();
  const download = await downloadPromise;
  const downloadPath = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(downloadPath);
  const archive = await readFile(downloadPath);
  expect(archive.subarray(0, 4).toString("hex")).toBe("504b0304");

  const bundlesResponse = await request.get(`${webUrl}/api/v1/export-bundles`, { headers });
  expect(bundlesResponse.ok()).toBeTruthy();
  const bundles = (await bundlesResponse.json()) as {
    items: Array<{ archive_sha256: string; component_count: number }>;
  };
  const downloadedSha256 = createHash("sha256").update(archive).digest("hex");
  const downloadedBundle = bundles.items.find(
    (item) => item.archive_sha256.replace("sha256:", "") === downloadedSha256,
  );
  expect(downloadedBundle).toBeTruthy();
  expect(downloadedBundle!.component_count).toBeGreaterThanOrEqual(6);
});

test("an exact approved Tensile revision opens its directly linked selected model", async ({ page, request }) => {
  test.setTimeout(90_000);
  const tokenResponse = await request.get(`${webUrl}/api/v1/demo-identity/token`);
  expect(tokenResponse.ok()).toBeTruthy();
  const tokenPayload = (await tokenResponse.json()) as { access_token: string };
  await page.addInitScript(
    ({ accessToken }) => {
      window.localStorage.setItem(
        "cmp.material-platform.api-config",
        JSON.stringify({ baseUrl: "/api/v1", accessToken }),
      );
    },
    { accessToken: tokenPayload.access_token },
  );

  await page.goto("/materials");
  await openMaterialFilters(page);
  await page.getByRole("textbox", { name: "Search materials" }).fill("CMP-DEMO-DP780");
  await page.getByLabel("Material query").getByRole("button", { name: "Find", exact: true }).click();
  await expectMaterialsReady(page);
  await page.getByRole("row").filter({ hasText: "CMP-DEMO-DP780" }).getByRole("button").click();
  await expect(page.getByRole("heading", { name: "DP780 synthetic reference steel", level: 1 })).toBeVisible({ timeout: 30_000 });

  const related = page.getByRole("region", { name: "Related data" });
  const fastTensile = related.getByRole("button").filter({ hasText: representativeDp780Tests[3] });
  await expect(fastTensile).toHaveCount(1);
  await expect(fastTensile).toContainText("r1");
  await fastTensile.click();
  await expect(page).toHaveURL(/\/materials\/records\/[0-9a-f-]+\/revisions\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: "Test Data", level: 1 })).toBeVisible({ timeout: 30_000 });

  const selectedModelName = "DP780 elastoplasticity · selected tabulated model · synthetic reference";
  const selectedModel = page.getByRole("region", { name: "Related data" }).getByRole("button").filter({ hasText: selectedModelName });
  await expect(selectedModel).toBeVisible({ timeout: 30_000 });
  await expect(selectedModel).toHaveCount(1);
  await expect(selectedModel).toContainText("r1");
  await selectedModel.click();
  await expect(page.getByRole("heading", { name: "Simulation Data", level: 1 })).toBeVisible({ timeout: 30_000 });
  const selectedModelDetail = page.locator(".exact-record-datasheet");
  await expect(selectedModelDetail.getByRole("heading", { name: "Selected Material Model details" })).toBeVisible();
  await expect(selectedModelDetail.getByText("Test setup", { exact: true })).toHaveCount(0);
  await expect(selectedModelDetail.getByText("Specimen", { exact: true })).toHaveCount(0);
  await expect(selectedModelDetail.getByText("Measured curve coverage", { exact: true })).toHaveCount(0);
});
