import { expect, test, type Page } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const preferenceKey = "cmp.material-platform.client-preferences.v1";

async function installSession(page: Page): Promise<void> {
  const response = await page.request.get(`${webUrl}/api/v1/demo-identity/token`);
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as { access_token: string };
  await page.addInitScript(
    ({ accessToken }) => {
      window.localStorage.setItem(
        "cmp.material-platform.api-config",
        JSON.stringify({ baseUrl: "/api/v1", accessToken }),
      );
      (window as typeof window & { __firstShellDensity?: string | null })
        .__firstShellDensity = null;
      const observer = new MutationObserver(() => {
        if (!document.querySelector(".application-shell")) return;
        const state = window as typeof window & {
          __firstShellDensity?: string | null;
        };
        if (state.__firstShellDensity === null) {
          state.__firstShellDensity =
            document.documentElement.getAttribute("data-display-density");
          observer.disconnect();
        }
      });
      observer.observe(document, { childList: true, subtree: true });
    },
    { accessToken: payload.access_token },
  );
}

async function waitForMaterials(page: Page): Promise<void> {
  const results = page.locator(".materials-results");
  await expect(results).toBeVisible({ timeout: 30_000 });
  await expect
    .poll(async () => (await results.getAttribute("aria-busy")) ?? "false", { timeout: 30_000 })
    .toBe("false");
  await expect(results.getByText("Loading…", { exact: true })).toHaveCount(0, { timeout: 30_000 });
}

async function openUtilityMenu(page: Page): Promise<void> {
  const menu = page.locator(".application-user-menu");
  if ((await menu.getAttribute("open")) === null) {
    await menu.locator("summary").click();
  }
  await expect(page.getByRole("group", { name: "Display density" })).toBeVisible();
}

async function chooseDensity(
  page: Page,
  label: "Compact" | "Standard" | "Large",
): Promise<void> {
  await openUtilityMenu(page);
  const option = page.getByRole("radio", { name: label });
  await option.focus();
  await option.press("Space");
  await expect(option).toBeChecked();
}

test("display density persists product-wide across routes and reload, then resets independently", async ({ page }) => {
  test.setTimeout(60_000);
  await installSession(page);
  await page.goto("/materials");
  await waitForMaterials(page);
  await openUtilityMenu(page);

  const large = page.getByRole("radio", { name: "Large" });
  await large.focus();
  await large.press("Space");
  await expect(large).toBeChecked();
  await expect(page.locator("html")).toHaveAttribute(
    "data-display-density",
    "large",
  );

  await page.getByRole("button", { name: "Modeling", exact: true }).click();
  await expect(page).toHaveURL(/\/modeling/);
  await expect(page.locator("html")).toHaveAttribute(
    "data-display-density",
    "large",
  );
  await page.getByRole("button", { name: "Activity", exact: true }).click();
  await expect(page).toHaveURL(/\/activity/);
  await expect(page.locator("html")).toHaveAttribute(
    "data-display-density",
    "large",
  );

  await page.reload();
  await expect(page.locator(".application-shell")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute(
    "data-display-density",
    "large",
  );
  expect(
    await page.evaluate(
      () =>
        (window as typeof window & { __firstShellDensity?: string | null })
          .__firstShellDensity,
    ),
  ).toBe("large");

  await page.evaluate(() =>
    window.localStorage.setItem("cmp.issue184.pane-sentinel", "preserve"),
  );
  await openUtilityMenu(page);
  await page
    .getByRole("button", { name: "Reset display density" })
    .click();
  await expect(page.getByRole("radio", { name: "Standard" })).toBeChecked();
  await expect(page.locator("html")).toHaveAttribute(
    "data-display-density",
    "standard",
  );
  expect(
    await page.evaluate(() =>
      window.localStorage.getItem("cmp.issue184.pane-sentinel"),
    ),
  ).toBe("preserve");
});

test("malformed and legacy density storage is repaired to Standard on reload", async ({ page }) => {
  await installSession(page);
  await page.goto("/materials");
  await waitForMaterials(page);
  await page.evaluate(
    ([key]) => window.localStorage.setItem(key, "legacy-large"),
    [preferenceKey],
  );

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute(
    "data-display-density",
    "standard",
  );
  const repaired = await page.evaluate(
    ([key]) => JSON.parse(window.localStorage.getItem(key) ?? "null"),
    [preferenceKey],
  );
  expect(repaired).toMatchObject({ version: 1 });
  expect(Object.values(repaired.displayDensityByScope)).toContain("standard");
});

test("P2 exposes the approved shared tokens and Large keeps the 1366 Activity queue locally overflow-free", async ({ page }) => {
  test.setTimeout(60_000);
  await installSession(page);
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/activity");
  await expect(page.locator(".activity-queue-scroll")).toBeVisible({ timeout: 30_000 });

  const contracts = [
    ["Compact", "compact", "13px", "36px", "264px", "5px"],
    ["Standard", "standard", "14px", "38px", "288px", "6px"],
    ["Large", "large", "16px", "40px", "312px", "7px"],
  ] as const;
  for (const [label, density, dataFont, control, navigator, splitter] of contracts) {
    await chooseDensity(page, label);
    await expect(page.locator("html")).toHaveAttribute("data-display-density", density);
    const tokens = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      const read = (name: string) => style.getPropertyValue(name).trim();
      return {
        dataFont: read("--ux-data-font-size"),
        control: read("--ux-control-min-block-size"),
        navigator: read("--ux-navigator-default-inline-size"),
        splitter: read("--ux-splitter-inline-size"),
      };
    });
    expect(tokens).toEqual({ dataFont, control, navigator, splitter });
  }

  const overflow = await page.locator(".activity-queue-scroll").evaluate((element) => ({
    local: element.scrollWidth - element.clientWidth,
    page: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  }));
  expect(overflow.local).toBeLessThanOrEqual(0);
  expect(overflow.page).toBeLessThanOrEqual(0);
});

test("Materials panes resize, collapse, and reset without coupling to density", async ({ page }) => {
  test.setTimeout(60_000);
  await installSession(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/materials");
  await waitForMaterials(page);

  const navigator = page.locator(".materials-workspace-panel.navigator-panel");
  const divider = page.getByRole("separator", { name: "Resize navigator" });
  const initialWidth = (await navigator.boundingBox())?.width ?? 0;
  await divider.focus();
  await divider.press("ArrowRight");
  await expect
    .poll(async () => (await navigator.boundingBox())?.width ?? 0)
    .toBeGreaterThan(initialWidth);

  await page.getByRole("button", { name: "Collapse navigator pane" }).click();
  await expect
    .poll(async () => (await navigator.boundingBox())?.width ?? 0)
    .toBeLessThan(1);
  await page.getByRole("button", { name: "Expand navigator pane" }).click();
  await divider.dblclick();
  await expect
    .poll(async () => Math.round((await navigator.boundingBox())?.width ?? 0))
    .toBe(288);
});

test("Modeling navigator resize, collapse, reset, and reload persistence remain reachable", async ({ page }) => {
  test.setTimeout(60_000);
  await installSession(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/modeling");
  const navigator = page.locator(".modeling-workspace-rail");
  await expect(navigator).toBeVisible({ timeout: 30_000 });
  const divider = page.getByRole("separator", {
    name: "Resize curve and process navigator",
  });
  const initialWidth = (await navigator.boundingBox())?.width ?? 0;
  await divider.focus();
  await divider.press("ArrowRight");
  await expect
    .poll(async () => (await navigator.boundingBox())?.width ?? 0)
    .toBeGreaterThan(initialWidth);
  const resizedWidth = (await navigator.boundingBox())?.width ?? 0;

  await page.reload();
  await expect(navigator).toBeVisible({ timeout: 30_000 });
  await expect
    .poll(async () => (await navigator.boundingBox())?.width ?? 0)
    .toBeGreaterThanOrEqual(resizedWidth - 2);
  await page
    .getByRole("button", { name: "Collapse curve and process navigator" })
    .click();
  await expect
    .poll(async () => (await navigator.boundingBox())?.width ?? 0)
    .toBeLessThan(1);
  await page
    .getByRole("button", { name: "Expand curve and process navigator" })
    .click();
  await divider.dblclick();
  await expect
    .poll(async () => Math.round((await navigator.boundingBox())?.width ?? 0))
    .toBe(288);
});

test("a zero-allocation Materials result opens its exact datasheet without a phantom context pane", async ({ page }) => {
  test.setTimeout(60_000);
  await installSession(page);
  await page.setViewportSize({ width: 960, height: 540 });
  await page.goto("/materials");
  await waitForMaterials(page);
  const firstRow = page.locator(".materials-result-table tbody tr").first();
  await expect(firstRow).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Expand details pane" })).toHaveCount(0);
  await firstRow.click();
  await expect(page).toHaveURL(/\/materials\/(?:records\/)?[0-9a-f-]+/);
  await expect(page.getByRole("heading", { name: "DP780 synthetic reference steel", level: 1 })).toBeVisible({ timeout: 30_000 });
});
