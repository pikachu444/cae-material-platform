import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

import { expect, test, type Locator, type Page } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const evidenceDirectory = process.env.CMP_ISSUE262_EVIDENCE_DIR;
const viewports = [
  [1366, 768],
  [1440, 900],
  [1920, 1080],
  [2560, 1440],
  [3840, 2160],
] as const;

const rejectedLegacyAdministrationSelectors = [
  ".content-card",
  ".hero-actions",
  ".form-stack",
  ".form-grid",
  ".datasheet-field",
  ".page-stack",
  ".page-heading",
  ".eyebrow",
  ".status-badge",
  ".count-chip",
].join(",");

type RouteCapture = {
  id: "database" | "database-preview" | "records" | "access";
  workspace: string;
  primary: string;
  secondary: string;
};

const routeCaptures: Record<RouteCapture["id"], Omit<RouteCapture, "id">> = {
  database: {
    workspace: ".catalog-schema-editor",
    primary: ".schema-object-list",
    secondary: ".schema-property-editor",
  },
  "database-preview": {
    workspace: ".catalog-schema-editor",
    primary: ".schema-object-list",
    secondary: ".schema-record-preview",
  },
  records: {
    workspace: ".administration-record-workbench",
    primary: ".catalog-record-list",
    secondary: ".catalog-datasheet",
  },
  access: {
    workspace: ".administration-access-workbench",
    primary: ".access-assignments-table",
    secondary: ".assignment-table",
  },
};

async function installAdministrator(page: Page): Promise<void> {
  const response = await page.request.get(
    `${webUrl}/api/v1/demo-identity/token?persona=administrator`,
  );
  expect(response.ok()).toBeTruthy();
  const token = ((await response.json()) as { access_token: string }).access_token;
  await page.addInitScript(
    ({ accessToken }) => {
      window.localStorage.setItem(
        "cmp.material-platform.api-config",
        JSON.stringify({ baseUrl: "/api/v1", accessToken }),
      );
    },
    { accessToken: token },
  );
}

async function firstVisible(page: Page, selector: string): Promise<Locator> {
  const candidates = page.locator(selector);
  for (let index = 0; index < await candidates.count(); index += 1) {
    const candidate = candidates.nth(index);
    if (await candidate.isVisible()) return candidate;
  }
  return candidates.first();
}

async function captureRoute(
  page: Page,
  routeCapture: RouteCapture,
  width: number,
  height: number,
): Promise<void> {
  if (!evidenceDirectory) return;
  const originalDirectory = join(evidenceDirectory, "originals");
  const cropDirectory = join(evidenceDirectory, "crops");
  const measurementDirectory = join(evidenceDirectory, "measurements");
  await Promise.all([
    mkdir(originalDirectory, { recursive: true }),
    mkdir(cropDirectory, { recursive: true }),
    mkdir(measurementDirectory, { recursive: true }),
  ]);

  const stem = `administration-${routeCapture.id}-${width}x${height}`;
  const primary = await firstVisible(page, routeCapture.primary);
  const secondary = await firstVisible(page, routeCapture.secondary);
  await expect(page.locator(routeCapture.workspace)).toBeVisible();
  await expect(primary).toBeVisible();
  await expect(secondary).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  const primaryNavigation = page.getByRole("navigation", { name: "Primary navigation" });
  await expect(primaryNavigation.getByRole("button", { name: "Materials", exact: true })).toBeVisible();
  await expect(primaryNavigation.getByRole("button", { name: "Modeling", exact: true })).toBeVisible();
  await expect(primaryNavigation.getByRole("button", { name: "Activity", exact: true })).toBeVisible();
  const administrationTasks = page.getByRole("navigation", { name: "Administration tasks" });
  for (const task of ["Database", "Format definitions", "Records", "Access"]) {
    await expect(administrationTasks.getByRole("button", { name: task, exact: true })).toBeVisible();
  }
  await expect(page.locator(rejectedLegacyAdministrationSelectors)).toHaveCount(0);
  const measurements = await page.evaluate(
    ({ workspaceSelector, primarySelector, secondarySelector, state }) => {
      const rect = (selector: string) => {
        const element = Array.from(document.querySelectorAll<HTMLElement>(selector)).find(
          (candidate) => candidate.getClientRects().length > 0,
        );
        const value = element?.getBoundingClientRect();
        return value
          ? { x: value.x, y: value.y, width: value.width, height: value.height }
          : null;
      };
      return {
        state,
        url: location.href,
        viewport: { width: innerWidth, height: innerHeight },
        devicePixelRatio,
        visualViewportScale: visualViewport?.scale ?? null,
        document: {
          scrollY,
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          clientHeight: document.documentElement.clientHeight,
          scrollHeight: document.documentElement.scrollHeight,
        },
        shell: rect(".application-shell"),
        administration: rect(".administration-workspace"),
        taskbar: rect(".administration-taskbar"),
        workspace: rect(workspaceSelector),
        primary: rect(primarySelector),
        secondary: rect(secondarySelector),
      };
    },
    {
      workspaceSelector: routeCapture.workspace,
      primarySelector: routeCapture.primary,
      secondarySelector: routeCapture.secondary,
      state: routeCapture.id,
    },
  );
  await page.screenshot({ path: join(originalDirectory, `${stem}.png`) });
  await page.locator(".application-menu-bar").screenshot({
    path: join(cropDirectory, `${stem}-header.png`),
  });
  await page.locator(".administration-taskbar").screenshot({
    path: join(cropDirectory, `${stem}-taskbar.png`),
  });
  await primary.screenshot({ path: join(cropDirectory, `${stem}-primary.png`) });
  await secondary.screenshot({ path: join(cropDirectory, `${stem}-secondary.png`) });
  await page.evaluate(() => window.scrollTo(0, 0));
  expect(measurements.visualViewportScale).toBe(1);
  expect(measurements.devicePixelRatio).toBe(1);
  expect(measurements.document.scrollWidth).toBe(measurements.document.clientWidth);
  expect(measurements.taskbar?.y ?? -1).toBeGreaterThanOrEqual(0);
  expect(measurements.workspace).not.toBeNull();
  expect(measurements.primary?.width ?? 0).toBeGreaterThan(240);
  expect(measurements.secondary?.width ?? 0).toBeGreaterThan(280);
  await writeFile(
    join(measurementDirectory, `${stem}.json`),
    `${JSON.stringify(measurements, null, 2)}\n`,
    "utf8",
  );
}

async function openExactDatabaseLayout(page: Page): Promise<void> {
  await page.goto("/administration/database");
  await expect(page.getByRole("region", { name: "Database design", exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "Record type", exact: true }).selectOption({
    label: "Demo Material Records · Revision 1",
  });
  await page.getByRole("button", { name: "Layouts", exact: true }).click();
  await page
    .getByRole("region", { name: "Layouts list", exact: true })
    .getByRole("button", { name: /^Material overview\b/ })
    .click();
  const version = page
    .getByRole("region", { name: "Layouts list", exact: true })
    .getByText("Version 1", { exact: true });
  await expect(version).toBeVisible();
  expect(
    await version.evaluate((element) => {
      const list = element.closest(".schema-object-list");
      if (!list) return false;
      return element.getBoundingClientRect().right <= list.getBoundingClientRect().right;
    }),
  ).toBeTruthy();
  await expect(page.locator(".schema-property-editor .property-sheet")).toBeVisible();
  await expect(page).toHaveURL(/table_revision_id=.+&object_kind=layouts&object_id=.+&object_revision_id=.+/);
}

async function openExactDatabaseRecord(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  const preview = page.getByLabel("Datasheet preview");
  const option = preview.locator("option").filter({ hasText: "DP780 synthetic reference steel" });
  const recordId = (await option.getAttribute("value")) ?? "";
  const previewWith = preview.getByRole("combobox", { name: "Preview with", exact: true });
  await previewWith.selectOption(recordId);
  await expect(previewWith).toHaveValue(recordId);
  await expect(option).toHaveText(/DP780 synthetic reference steel \(Draft, revision 2\)/);
  await expect(preview.getByText("CMP-DEMO-DP780", { exact: true })).toBeVisible();
  await expect(preview.getByText("0.30", { exact: true })).toBeVisible();
  await expect(preview.getByText("0.30 1", { exact: true })).toHaveCount(0);
  await expect(page).toHaveURL(/table_revision_id=.+&object_kind=layouts&object_id=.+&object_revision_id=.+&record_id=.+&record_revision_id=.+/);
}

for (const [width, height] of viewports) {
  test(`FE-07B Administration exact journey remains usable at ${width}x${height}`, async ({ page }) => {
    test.skip(!evidenceDirectory, "Set CMP_ISSUE262_EVIDENCE_DIR for the bounded visual acceptance run.");
    test.setTimeout(60_000);
    await installAdministrator(page);
    await page.route("**/api/v1/product-access/assignments", async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      const body = (await response.json()) as {
        items: Array<{ group_name?: string | null; revoked_at?: string | null }>;
      };
      await route.fulfill({
        response,
        json: {
          ...body,
          items: body.items.filter(
            (item) => item.revoked_at === null && item.group_name?.startsWith("cmp-demo-"),
          ),
        },
      });
    });

    await page.setViewportSize({ width, height });
    await openExactDatabaseLayout(page);
    await captureRoute(page, { id: "database", ...routeCaptures.database }, width, height);
    await openExactDatabaseRecord(page);
    const previewScroll = page.locator(".schema-preview-fields");
    const previewOverflow = await previewScroll.evaluate((element) => ({
      clientHeight: element.clientHeight,
      overflowY: getComputedStyle(element).overflowY,
      scrollHeight: element.scrollHeight,
    }));
    expect(previewOverflow.overflowY).toBe("auto");
    if (previewOverflow.scrollHeight > previewOverflow.clientHeight) {
      await previewScroll.evaluate((element) => { element.scrollTop = element.scrollHeight; });
      expect(await previewScroll.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
      await previewScroll.evaluate((element) => { element.scrollTop = 0; });
    }
    await captureRoute(page, { id: "database-preview", ...routeCaptures["database-preview"] }, width, height);

    await page.getByRole("button", { name: "Open in Records", exact: true }).click();
    await expect(page).toHaveURL(/\/administration\/records\?.*table_revision_id=.+&record_revision_id=.+/);
    const recordEditor = page.getByRole("region", { name: "Edit DP780 synthetic reference steel", exact: true });
    await expect(recordEditor.getByRole("heading", { name: "DP780 synthetic reference steel", exact: true })).toBeVisible();
    await expect(recordEditor.getByText("Draft · Revision 2", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Record code", { exact: true })).toHaveValue("CMP-DEMO-DP780");
    await page.reload();
    await expect(recordEditor.getByRole("heading", { name: "DP780 synthetic reference steel", exact: true })).toBeVisible();
    await expect(recordEditor.getByText("Draft · Revision 2", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Record code", { exact: true })).toHaveValue("CMP-DEMO-DP780");
    await page
      .getByRole("textbox", { name: "Search", exact: true })
      .fill("CMP-DEMO-DP780");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page.locator(".catalog-record-list .section-heading span")).toHaveText("1 record");
    await expect(page.getByRole("button", { name: "Import records", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create record", exact: true })).toBeVisible();
    await expect(page.locator(".catalog-record-list")).toBeVisible();
    await expect(page.locator(".catalog-datasheet")).toBeVisible();
    await expect(page.locator(".ux-button.primary:visible")).toHaveText("Create record");
    await expect(page.getByRole("button", { name: "Save new revision", exact: true })).not.toHaveClass(/primary/);
    const recordEditorOverflow = await page.locator(".catalog-datasheet").evaluate((element) => ({
      clientHeight: element.clientHeight,
      overflowY: getComputedStyle(element).overflowY,
      scrollHeight: element.scrollHeight,
    }));
    expect(recordEditorOverflow.overflowY).toBe("auto");
    if (recordEditorOverflow.scrollHeight > recordEditorOverflow.clientHeight) {
      await page.locator(".catalog-datasheet").evaluate((element) => { element.scrollTop = element.scrollHeight; });
      expect(await page.locator(".catalog-datasheet").evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
      await page.locator(".catalog-datasheet").evaluate((element) => { element.scrollTop = 0; });
    }
    await captureRoute(page, { id: "records", ...routeCaptures.records }, width, height);

    await page.goto("/administration/access");
    await expect(page.getByRole("heading", { name: "Access", exact: true })).toBeVisible();
    await captureRoute(page, { id: "access", ...routeCaptures.access }, width, height);
  });
}
