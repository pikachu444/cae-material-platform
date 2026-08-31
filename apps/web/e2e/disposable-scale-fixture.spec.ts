import { expect, test, type Page } from "@playwright/test";


const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const scaleQuery = "CMP-SCALE-";


async function waitForMaterials(page: Page): Promise<void> {
  await expect(page.locator(".materials-results")).toHaveAttribute("aria-busy", "false", {
    timeout: 30_000,
  });
}


async function findMaterials(page: Page, query: string): Promise<void> {
  await page.getByRole("textbox", { name: "Search materials" }).fill(query);
  await page.getByLabel("Material query").getByRole("button", { name: "Find", exact: true }).click();
  await waitForMaterials(page);
}


async function expectSearchParams(
  page: Page,
  expected: Record<string, string | null>,
): Promise<void> {
  await expect.poll(() => {
    const params = new URL(page.url()).searchParams;
    return Object.fromEntries(Object.keys(expected).map((key) => [key, params.get(key)]));
  }).toEqual(expected);
}


test("disposable 1,000-record fixture proves Materials scale without persistent demo pollution", async ({ page, request }) => {
  test.setTimeout(180_000);
  const pageErrors: Error[] = [];
  page.on("pageerror", (error) => pageErrors.push(error));

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

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/materials?q=${scaleQuery}`);
  await expect(page.getByRole("heading", { name: "Materials", level: 1 })).toBeVisible();
  await expect(page.getByRole("button", { name: "Browse" })).toHaveAttribute("aria-current", "page");
  const filters = page.getByRole("button", { name: "Filters" });
  await expect(filters).toBeVisible({ timeout: 30_000 });
  await filters.click();
  await waitForMaterials(page);
  const rows = page.locator(".materials-result-table tbody tr");
  await expect(page.locator(".materials-results-header .ux-meta").first()).toHaveText(
    "1–50 of 1,000 matches",
  );
  await expect(rows).toHaveCount(50);
  await expect(rows.first()).toContainText("CMP-SCALE-0000");
  await expect(rows.last()).toContainText("CMP-SCALE-0049");

  const results = page.locator(".materials-result-table-wrap");
  const scrollGeometry = await results.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }));
  expect(scrollGeometry.scrollHeight).toBeGreaterThan(scrollGeometry.clientHeight);
  await results.evaluate((element) => { element.scrollTop = element.scrollHeight; });
  await expect.poll(() => results.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
  await expect(page.locator(".materials-result-scroll-shell .materials-scroll-rail-y")).toBeVisible();

  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page.locator(".materials-results-header .ux-meta").first()).toHaveText(
    "51–100 of 1,000 matches",
  );
  await expect(rows).toHaveCount(50);
  await expect(rows.first()).toContainText("CMP-SCALE-0050");
  await expectSearchParams(page, { q: scaleQuery, mode: "filters", offset: "50" });

  await page.getByRole("button", { name: "Previous", exact: true }).click();
  const materialClass = page.getByRole("combobox", { name: "Material class" });
  await expect(page.getByRole("option", { name: "Metal (500)" })).toBeAttached();
  await expect(page.getByRole("option", { name: "Polymer (300)" })).toBeAttached();
  await expect(page.getByRole("option", { name: "Elastomer (200)" })).toBeAttached();
  await materialClass.selectOption("polymer");
  await expect(page.locator(".materials-results-header .ux-meta").first()).toHaveText(
    "1–50 of 300 matches",
  );
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page.locator(".materials-results-header .ux-meta").first()).toHaveText(
    "51–100 of 300 matches",
  );
  await expectSearchParams(page, {
    q: scaleQuery,
    family: "polymer",
    mode: "filters",
    offset: "50",
  });

  await page.reload();
  await waitForMaterials(page);
  await expect(page.getByRole("textbox", { name: "Search materials" })).toHaveValue(scaleQuery);
  await expect(page.getByRole("combobox", { name: "Material class" })).toHaveValue("polymer");
  await expect(page.locator(".materials-results-header .ux-meta").first()).toHaveText(
    "51–100 of 300 matches",
  );
  await expect(rows).toHaveCount(50);

  await page.getByRole("button", { name: "Previous", exact: true }).click();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.locator(".materials-results-header .ux-meta").first()).toHaveText(
    "1–50 of 1,000 matches",
  );

  // Source-v2 deliberately has no Provider/Evidence projections.  A stale
  // URL must fail closed, expose the recovery action, and preserve the query
  // and Filters route state while only clearing unsupported filters.
  await expect.poll(() => {
    const params = new URL(page.url()).searchParams;
    return [params.get("table"), params.get("selected")];
  }).toEqual([expect.any(String), expect.any(String)]);
  const preservedRoute = new URL(page.url());
  const preservedTable = preservedRoute.searchParams.get("table");
  const preservedSelected = preservedRoute.searchParams.get("selected");
  const unsupportedRoute = new URLSearchParams(preservedRoute.searchParams);
  unsupportedRoute.set("provider", "legacy");
  unsupportedRoute.set("source", "legacy");
  // Keep an explicit zero offset in the stale URL so recovery proves that the
  // controller removes it from the canonical path while retaining selection.
  unsupportedRoute.set("offset", "0");
  await page.goto(`/materials?${unsupportedRoute.toString()}`);
  await expect(page.getByRole("alert")).toContainText(
    "Unsupported legacy provider/source filters",
  );
  await expect(page.getByRole("button", { name: "Clear unsupported filters" })).toBeVisible();
  await page.getByRole("button", { name: "Clear unsupported filters" }).click();
  await waitForMaterials(page);
  await expectSearchParams(page, {
    q: scaleQuery,
    mode: "filters",
    table: preservedTable,
    selected: preservedSelected,
    provider: null,
    source: null,
    offset: null,
  });
  await expect(page.locator(".materials-results-header .ux-meta").first()).toHaveText(
    "1–50 of 1,000 matches",
  );

  await findMaterials(page, "CMP-SCALE-0731");
  await expect(page.locator(".materials-results-header .ux-meta").first()).toHaveText(
    "1–1 of 1 matches",
  );
  const exactRow = rows.filter({ hasText: "CMP-SCALE-0731" });
  await expect(exactRow).toHaveCount(1);
  await exactRow.getByRole("button").first().click();
  await expect(page).toHaveURL(
    /\/materials\/[0-9a-f-]+\?record_id=[0-9a-f-]+&record_revision_id=[0-9a-f-]+&material_revision_id=[0-9a-f-]+$/,
  );
  await expect(
    page.getByRole("heading", {
      name: "Disposable scale material 0731 · Plastic · Warm synthetic metadata",
      level: 1,
    }),
  ).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("No representative curve preview.", { exact: true })).toHaveCount(0);

  await page.goBack();
  await waitForMaterials(page);
  await expect(page.getByRole("textbox", { name: "Search materials" })).toHaveValue(
    "CMP-SCALE-0731",
  );
  await findMaterials(page, "CMP-SCALE-NOT-FOUND");
  await expect(page.getByText("No materials match this search.", { exact: true })).toBeVisible();
  await expect(rows).toHaveCount(0);
  await page.getByRole("button", { name: "Clear search", exact: true }).click();
  await waitForMaterials(page);
  await expect(page.getByRole("textbox", { name: "Search materials" })).toHaveValue("");
  await expect(rows).toHaveCount(50);
  await expect(page.getByText("No materials match this search.", { exact: true })).toHaveCount(0);
  expect(pageErrors).toEqual([]);
});
