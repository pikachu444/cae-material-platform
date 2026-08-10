import { expect, test, type Page } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const forbiddenNormalTechnicalLabels = /\b(?:draft|fixture|uuid|sha(?:256)?|hash|lifecycle[_\s-]?state)\b|\bissue\s*#\s*\d+\b|\bimplementation state\b/i;

async function expectMaterialsReady(page: Page): Promise<void> {
  await expect(page.locator(".materials-results")).toHaveAttribute("aria-busy", "false", { timeout: 15_000 });
  await expect(page.getByText("Checking…", { exact: true })).toHaveCount(0, { timeout: 15_000 });
}

async function expectLinkedResponseLabelsVisible(page: Page): Promise<void> {
  const geometry = await page.locator(".response-plot").evaluate((svg) => {
    const frame = svg.closest(".response-plot-frame")?.getBoundingClientRect();
    const status = document.querySelector(".application-status-bar")?.getBoundingClientRect();
    const rect = (element: Element | null) => {
      if (!element) return null;
      const bounds = element.getBoundingClientRect();
      return { left: bounds.left, right: bounds.right, top: bounds.top, bottom: bounds.bottom };
    };
    const xTickLabels = Array.from(svg.querySelectorAll(".linked-response-tick-label")).filter((label) => {
      const tick = label.parentElement?.querySelector(".linked-response-tick");
      return tick?.getAttribute("y1") !== tick?.getAttribute("y2");
    });
    return {
      frame: frame ? { left: frame.left, right: frame.right, top: frame.top, bottom: frame.bottom } : null,
      status: status ? { top: status.top } : null,
      xTicks: xTickLabels.map(rect),
      xTitle: rect(svg.querySelector(".linked-response-axis-title:not([transform])")),
    };
  });
  expect(geometry.frame).not.toBeNull();
  expect(geometry.status).not.toBeNull();
  expect(geometry.xTicks.length).toBeGreaterThan(0);
  expect(geometry.xTitle).not.toBeNull();
  const frame = geometry.frame!;
  const statusTop = geometry.status!.top;
  const insideFrameAndAboveStatus = (bounds: { left: number; right: number; top: number; bottom: number } | null) => {
    expect(bounds).not.toBeNull();
    expect(bounds!.left).toBeGreaterThanOrEqual(frame.left - 1);
    expect(bounds!.right).toBeLessThanOrEqual(frame.right + 1);
    expect(bounds!.top).toBeGreaterThanOrEqual(frame.top - 1);
    expect(bounds!.bottom).toBeLessThanOrEqual(frame.bottom + 1);
    expect(bounds!.bottom).toBeLessThanOrEqual(statusTop + 1);
  };
  geometry.xTicks.forEach(insideFrameAndAboveStatus);
  insideFrameAndAboveStatus(geometry.xTitle);
}

test("clean demo exposes Search-first material-family journeys and progressive bulk entry", async ({ page, request }) => {
  test.setTimeout(60_000);
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
    expect(normalResultsText).toContain("not validated for engineering use");
    const normalResultsSurfaceText = await page.locator(".materials-results").innerText();
    expect(normalResultsSurfaceText).not.toMatch(forbiddenNormalTechnicalLabels);
    expect(normalResultsSurfaceText).toContain(expectedName);
    expect(normalResultsSurfaceText).toContain("Family");
    await expect(page.getByRole("columnheader", { name: "Status", exact: true })).toHaveCount(0);
    await resultRow.getByRole("button").click();
    const normalContextText = await page.locator(".materials-selection").innerText();
    expect(normalContextText).not.toMatch(/clean product demo|local demo|fixture/i);
    expect(normalContextText).not.toMatch(staleHumanNames);
    expect(normalContextText).toContain(expectedName);
    expect(normalContextText).toMatch(expectedReference);
    expect(normalContextText).toContain("not validated for engineering use");
    expect(normalContextText).not.toMatch(forbiddenNormalTechnicalLabels);
    expect(normalContextText).toContain("Family");
    expect(normalContextText).toContain("Open datasheet");
    const normalSearchStatusBarText = await page.locator(".application-status-bar").innerText();
    expect(normalSearchStatusBarText).not.toMatch(forbiddenNormalTechnicalLabels);
    expect(normalSearchStatusBarText).toMatch(/\br\d+\b/);
    await page.getByRole("button", { name: "Open datasheet" }).click();
    await expect(page).toHaveURL(/\/materials\/[0-9a-f-]+\?record_id=[0-9a-f-]+&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$/);
    await expect(page.getByRole("complementary", { name: "Materials Browse Tree" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("tab", { name: "CAE Cards" })).toBeVisible();
    await expect(page.getByText(/^(Request review|Waiting for review|Approved|Changes requested)$/).first()).toBeVisible({ timeout: 15_000 });
    const normalDetailText = await page.locator(".material-detail-shell").innerText();
    expect(normalDetailText).not.toMatch(/clean product demo|local demo|fixture/i);
    expect(normalDetailText).not.toMatch(staleHumanNames);
    expect(normalDetailText).toContain(expectedName);
    expect(normalDetailText).toMatch(expectedReference);
    const normalDetailHeaderText = await page.locator(".material-detail-header").innerText();
    const relatedContextText = await page.getByRole("complementary", { name: "Related exact records" }).innerText();
    const normalStatusBarText = await page.locator(".application-status-bar").innerText();
    expect(normalDetailHeaderText).not.toMatch(forbiddenNormalTechnicalLabels);
    expect(relatedContextText).not.toMatch(forbiddenNormalTechnicalLabels);
    expect(normalStatusBarText).not.toMatch(forbiddenNormalTechnicalLabels);
    expect(normalStatusBarText).toMatch(/\br\d+\b/);
    expect(normalDetailHeaderText).toMatch(/Request review|Waiting for review|Approved|Changes requested/);
    expect(relatedContextText).toContain("Revision");
    expect(relatedContextText).toContain("Related");
    const treeFind = page.getByRole("textbox", { name: "Find in tree" });
    await treeFind.fill(expectedName);
    await treeFind.press("Enter");
    await expect(page.locator(".materials-left-pane")).toContainText(expectedName, { timeout: 15_000 });
    const normalTreeText = await page.locator(".materials-left-pane").innerText();
    expect(normalTreeText).not.toMatch(staleHumanNames);
    expect(normalTreeText).toContain(expectedName);
    if (materialCode === "CMP-DEMO-DP780") {
      await page.getByRole("tab", { name: "CAE Cards" }).click();
      const abaqusRow = page.getByRole("row").filter({ hasText: "Abaqus" }).filter({ hasText: ".inp" });
      await expect(abaqusRow).toHaveCount(1);
      const previewButton = abaqusRow.getByRole("button", { name: "Preview card", exact: true });
      await expect(previewButton).toBeVisible({ timeout: 15_000 });
      await previewButton.click();
      await expect(page).toHaveURL(/\/materials\/[0-9a-f-]+\/cards\/[0-9a-f-]+\?record_id=[0-9a-f-]+&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$/);

      const acknowledgement = page.getByRole("checkbox", { name: "I reviewed the delivery notes before downloading this card." });
      const downloadButton = page.getByRole("button", { name: "Download .inp", exact: true });
      await expect(page.getByRole("heading", { name: "Delivery check", exact: true })).toBeVisible({ timeout: 15_000 });
      await expect(acknowledgement).toBeVisible({ timeout: 15_000 });
      await expect(downloadButton).toBeVisible({ timeout: 15_000 });
      const nativePreview = page.getByLabel("Native solver card preview");
      const scrollRail = page.locator(".preview-scroll-rail");
      await expect(nativePreview).toHaveAttribute("tabindex", "0");
      const normalCardText = await page.locator(".card-preview-shell").innerText();
      expect(normalCardText).not.toMatch(/\b(?:uuid|sha256|hash|aggregate|revision_id|mapping profile|recipe|batch|processing output|neutral|neutral json|ir|exporter|provenance|checksum)\b/i);
      expect(normalCardText).not.toMatch(/\b(?:approximated|ignored|unsupported|not_applicable)\b/i);
      for (const { width, height } of [
        { width: 1366, height: 768 },
        { width: 1440, height: 900 },
        { width: 1920, height: 1080 },
        { width: 2560, height: 1440 },
        { width: 3840, height: 2160 },
      ]) {
        await page.setViewportSize({ width, height });
        const shellGeometry = await page.locator(".card-preview-shell").evaluate((element) => {
          const bounds = element.getBoundingClientRect();
          return { left: bounds.left, right: bounds.right, width: bounds.width };
        });
        expect(shellGeometry.left).toBeGreaterThanOrEqual(7);
        expect(shellGeometry.left).toBeLessThanOrEqual(9);
        expect(shellGeometry.width).toBeGreaterThanOrEqual(width - 17);
        expect(shellGeometry.width).toBeLessThanOrEqual(width - 15);
        expect(shellGeometry.right).toBeGreaterThanOrEqual(width - 9);
        expect(shellGeometry.right).toBeLessThanOrEqual(width - 7);
        const deliverySheetGeometry = await page.locator(".card-preview-actions").evaluate((element) => element.getBoundingClientRect().width);
        expect(deliverySheetGeometry).toBeGreaterThanOrEqual(311);
        expect(deliverySheetGeometry).toBeLessThanOrEqual(313);
        await acknowledgement.scrollIntoViewIfNeeded();
        await expect(acknowledgement).toBeVisible();
        await expect(downloadButton).toBeVisible();
        await expect(downloadButton).toBeDisabled();
        await nativePreview.focus();
        await expect(nativePreview).toBeFocused();
        const scrollState = await nativePreview.evaluate((element) => ({
          clientHeight: element.clientHeight,
          scrollHeight: element.scrollHeight,
          scrollTop: element.scrollTop,
        }));
        if (scrollState.scrollHeight > scrollState.clientHeight + 1) {
          await expect(scrollRail).toHaveAttribute("data-scrollable", "true");
          await nativePreview.press("End");
          await expect.poll(() => nativePreview.evaluate((element) => element.scrollTop)).toBeGreaterThan(scrollState.scrollTop);
          await nativePreview.press("Home");
        }
        const linkedResponse = page.getByRole("img", { name: "Linked response chart showing true stress in MPa versus true plastic strain" });
        if (width >= 1800) {
          await expect(linkedResponse).toBeVisible();
          await expect(linkedResponse).toHaveAttribute("data-x-label", "True plastic strain [1]");
          await expect(linkedResponse).toHaveAttribute("data-y-label", "True stress (MPa)");
          const yDomain = await linkedResponse.getAttribute("data-y-domain");
          expect(yDomain?.split(",").map(Number).every((value) => Number.isFinite(value) && value >= 0 && value < 10_000)).toBe(true);
          const nativeGeometry = await nativePreview.boundingBox();
          const responseGeometry = await page.locator(".response-plot-band").boundingBox();
          expect(nativeGeometry?.height ?? 0).toBeLessThanOrEqual(322);
          expect(responseGeometry?.height ?? 0).toBeGreaterThanOrEqual(320);
          expect(responseGeometry?.height ?? 0).toBeLessThanOrEqual(562);
          await expectLinkedResponseLabelsVisible(page);
        } else {
          await expect(linkedResponse).toBeHidden();
        }
        await expect
          .poll(() => acknowledgement.evaluate((element) => {
            const bounds = element.getBoundingClientRect();
            return bounds.top >= 0
              && bounds.left >= 0
              && bounds.bottom <= window.innerHeight
              && bounds.right <= window.innerWidth;
          }))
          .toBe(true);
        await expect
          .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
          .toBe(true);
      }

      await acknowledgement.check();
      await expect(downloadButton).toBeEnabled();
      const downloadPromise = page.waitForEvent("download");
      await downloadButton.click();
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toMatch(/\.inp$/);
    }
    await page.goto("/materials");
  }

  await page.getByRole("textbox", { name: "Search materials" }).fill("CMP-DEMO-DP780");
  await page.getByLabel("Material query").getByRole("button", { name: "Find", exact: true }).click();
  await expectMaterialsReady(page);
  const dp780Row = page.getByRole("row").filter({ hasText: "CMP-DEMO-DP780" });
  await expect(dp780Row).toHaveCount(1);
  await dp780Row.press("Enter");
  await expect(page).toHaveURL(/\/materials\/[0-9a-f-]+\?record_id=[0-9a-f-]+&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$/);
  const relatedRecord = page.locator(".material-related-context .related-record-list button").filter({ hasText: "DP780 reference Material State" });
  await expect(relatedRecord).toBeVisible({ timeout: 15_000 });
  await expect(relatedRecord).toHaveCount(1);
  await relatedRecord.click();
  await expect(page).toHaveURL(/\/materials\/records\/[0-9a-f-]+\/revisions\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: "DP780 reference Material State", level: 1 })).toBeVisible({ timeout: 15_000 });
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
  await expect(page.getByText(/Downloaded solver card/).first()).toBeVisible();
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

test("Materials workspaces use the viewport and expose the shared response plot across desktop widths", async ({ page, request }) => {
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
    await page.goto(`/materials?q=${materialCode}`);
    await expect(page.getByRole("heading", { name: "Materials", level: 1 })).toBeVisible();
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
    const contextText = await page.locator(".materials-selection").innerText();
    expect(treeText).not.toMatch(staleHumanNames);
    expect(contextText).toContain(expectedName);
    expect(contextText).not.toMatch(staleHumanNames);
    expect(contextText).not.toMatch(staleStateRoutes);
    if (width <= 1390) {
      await resultRow.press("Enter");
    } else {
      await page.getByRole("button", { name: "Open datasheet" }).click();
    }
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
    const graph = page.locator(".material-curve-preview [data-x-label='True plastic strain [1]']");
    await expect(graph).toBeVisible({ timeout: 15_000 });
    await expect(graph).toHaveAttribute("data-y-label", "True stress (MPa)");
    const graphBox = await graph.evaluate((element) => {
      const bounds = element.getBoundingClientRect();
      return { left: bounds.left, right: bounds.right, width: bounds.width, height: bounds.height };
    });
    expect(graphBox.left).toBeGreaterThanOrEqual(0);
    expect(graphBox.right).toBeLessThanOrEqual(width + 1);
    const pointsTable = page.getByRole("table", { name: "Representative response points" });
    if (width >= 1800) {
      await expect(pointsTable).toBeVisible();
      const responseRegion = page.getByRole("region", { name: "Scrollable representative response points" });
      await expect(responseRegion).toBeVisible();
      await expect(responseRegion).toHaveAttribute("tabindex", "0");
      await expect(responseRegion.locator("thead th").first()).toHaveCSS("position", "sticky");
      const responseShell = page.locator(".material-response-points-scroll-shell");
      await expect(responseShell).toHaveAttribute("data-scroll-y", "true");
      await expect(responseShell).toHaveAttribute("data-scroll-x", "false");
      const verticalRail = responseShell.locator(".materials-scroll-rail-y");
      await expect(verticalRail).toBeVisible();
      await expect(responseShell.locator(".materials-scroll-rail-x")).toHaveCount(0);
      const initialPageAndTree = await page.evaluate(() => ({
        pageY: window.scrollY,
        treeY: document.querySelector<HTMLElement>(".materials-tree-scroll")?.scrollTop ?? 0,
      }));
      const initialResponseScroll = await responseRegion.evaluate((element) => ({
        clientHeight: element.clientHeight,
        scrollHeight: element.scrollHeight,
        scrollTop: element.scrollTop,
      }));
      expect(initialResponseScroll.scrollHeight).toBeGreaterThan(initialResponseScroll.clientHeight);
      await responseRegion.hover();
      await page.mouse.wheel(0, 160);
      await expect.poll(() => responseRegion.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
      expect(await page.evaluate(() => window.scrollY)).toBe(initialPageAndTree.pageY);
      expect(await page.locator(".materials-tree-scroll").evaluate((element) => element.scrollTop)).toBe(initialPageAndTree.treeY);
      await responseRegion.focus();
      await responseRegion.press("Home");
      await responseRegion.press("PageDown");
      await expect.poll(() => responseRegion.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
      const railBox = await verticalRail.boundingBox();
      expect(railBox).not.toBeNull();
      await responseRegion.press("Home");
      const beforeTrackClick = await responseRegion.evaluate((element) => element.scrollTop);
      await page.mouse.click(railBox!.x + railBox!.width / 2, railBox!.y + railBox!.height * 0.75);
      await expect.poll(() => responseRegion.evaluate((element) => element.scrollTop)).not.toBe(beforeTrackClick);
      const thumb = verticalRail.locator(".materials-scroll-thumb");
      const thumbBox = await thumb.boundingBox();
      expect(thumbBox).not.toBeNull();
      const beforeThumbDrag = await responseRegion.evaluate((element) => element.scrollTop);
      await page.mouse.move(thumbBox!.x + thumbBox!.width / 2, thumbBox!.y + thumbBox!.height / 2);
      await page.mouse.down();
      await page.mouse.move(thumbBox!.x + thumbBox!.width / 2, railBox!.y + thumbBox!.height / 2);
      await page.mouse.up();
      await expect.poll(() => responseRegion.evaluate((element) => element.scrollTop)).not.toBe(beforeThumbDrag);
      expect(await page.evaluate(() => window.scrollY)).toBe(initialPageAndTree.pageY);
      expect(await page.locator(".materials-tree-scroll").evaluate((element) => element.scrollTop)).toBe(initialPageAndTree.treeY);
      const tableBox = await pointsTable.evaluate((element) => {
        const bounds = element.getBoundingClientRect();
        return { left: bounds.left, right: bounds.right, width: bounds.width, height: bounds.height };
      });
      expect(tableBox.right).toBeLessThanOrEqual(width + 1);
      expect(tableBox.left).toBeGreaterThanOrEqual(0);
      const responseRows = pointsTable.locator("tbody tr");
      const responseRowCount = await responseRows.count();
      expect(responseRowCount).toBeGreaterThanOrEqual(2);
      expect(responseRowCount).toBe(Number(await graph.getAttribute("data-series-rows")));
      expect(await pointsTable.evaluate((element) => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
      const endpointValues = await responseRows.evaluateAll((rows) => {
        const endpoints = [rows[0], rows[rows.length - 1]];
        return endpoints.map((row) => ({
          x: Number(row.getAttribute("data-x-value")),
          y: Number(row.getAttribute("data-y-value")),
        }));
      });
      expect(endpointValues.every(({ x, y }) => Number.isFinite(x) && Number.isFinite(y))).toBe(true);
    } else {
      await expect(pointsTable).toBeHidden();
    }
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

test("an exact Test JSON revision navigates back through the governed workflow graph", async ({ page, request }) => {
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

  await page.goto("/datasets/test-json");
  const related = page.getByLabel("CMP-DEMO-DP780-TEST-JSON r1 related governed data");
  await expect(related.getByRole("link", { name: "Open Workflow Explorer" })).toBeVisible();
  await related.getByRole("link", { name: "Open Workflow Explorer" }).click();
  await expect(page).toHaveURL(/\/catalog\/explorer\/records\/[0-9a-f-]+\/revisions\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: "DP780 canonical tensile Test JSON" })).toBeVisible();
  const workflowNodes = page.locator(".workflow-node-list");
  await expect(workflowNodes.getByText("DP780 canonical Neutral Material JSON", { exact: true })).toBeVisible();
  await expect(workflowNodes.getByText("DP780 Abaqus native material card", { exact: true })).toBeVisible();
  await expect(workflowNodes.getByText("DP780 OpenRadioss native material card", { exact: true })).toBeVisible();
});
