import { expect, test, type Page } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";

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

async function currentLayoutFieldOrder(page: Page): Promise<string[]> {
  return page.locator(".layout-drag-handle").evaluateAll((handles) =>
    handles.map((handle) => {
      const label = handle.getAttribute("aria-label") ?? "";
      return label.match(/^Reorder (.*), position \d+ of \d+$/)?.[1] ?? label;
    }),
  );
}

test("Database reviews, saves, reads back, previews, duplicates and deletes exact datasheet Layouts", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await installAdministrator(page);
  const suffix = `${Date.now()}-${test.info().workerIndex}`;
  const layoutName = `Issue 262 datasheet ${suffix}`;
  const copyName = `${layoutName} copy`;
  const createRequests: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST"
      && /\/api\/v1\/catalog\/tables\/[^/]+\/layouts$/.test(new URL(request.url()).pathname)
    ) {
      createRequests.push(request.url());
    }
  });

  await page.goto("/administration/database");
  await expect(page.getByRole("region", { name: "Database design", exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "Record type", exact: true }).selectOption({
    label: "Demo Material Records · Revision 1",
  });
  await expect(page.getByRole("button", { name: "Attributes", exact: true })).toContainText("14");
  await page.getByRole("button", { name: "Layouts", exact: true }).click();

  await page.getByRole("button", { name: "New layout", exact: true }).click();
  await expect(page.getByRole("heading", { name: "New layout", exact: true })).toBeVisible();
  expect(createRequests).toHaveLength(0);
  await page.getByRole("textbox", { name: "Layout name", exact: true }).fill(layoutName);
  await page.getByRole("textbox", { name: "Description (optional)", exact: true }).fill("Unsaved owner review order");
  const firstField = page.getByRole("checkbox").first();
  await expect(firstField).toBeChecked();
  const fieldsRegion = page.getByRole("region", { name: "Datasheet fields", exact: true });
  const initialGeometry = await fieldsRegion.evaluate((region) => {
    const footer = document.querySelector<HTMLElement>(".datasheet-layout-editor > footer");
    const bounds = region.getBoundingClientRect();
    const footerBounds = footer?.getBoundingClientRect();
    return {
      overflowY: getComputedStyle(region).overflowY,
      scrollHeight: region.scrollHeight,
      clientHeight: region.clientHeight,
      regionBottom: bounds.bottom,
      footerTop: footerBounds?.top ?? 0,
    };
  });
  expect(initialGeometry.overflowY).toBe("scroll");
  expect(initialGeometry.scrollHeight).toBeGreaterThan(initialGeometry.clientHeight);
  expect(initialGeometry.regionBottom).toBeLessThanOrEqual(initialGeometry.footerTop + 1);

  const manufacturerHandle = page.getByRole("button", { name: /^Reorder Manufacturer, position 5 of 14$/ });
  await manufacturerHandle.press("Alt+ArrowUp");
  await expect(page.getByRole("button", { name: /^Reorder Manufacturer, position 4 of 14$/ })).toBeVisible();
  await expect(page.getByText("Moved Manufacturer to position 4 of 14.", { exact: true })).toBeAttached();

  await fieldsRegion.evaluate((region) => { region.scrollTop = 0; });
  const conditionHandle = page.getByRole("button", { name: /^Reorder Condition, position 1 of 14$/ });
  const sourceBox = await conditionHandle.boundingBox();
  const targetBox = await fieldsRegion.boundingBox();
  expect(sourceBox).not.toBeNull();
  expect(targetBox).not.toBeNull();
  await page.mouse.move(sourceBox!.x + sourceBox!.width / 2, sourceBox!.y + sourceBox!.height / 2);
  await page.mouse.down();
  await page.mouse.move(targetBox!.x + targetBox!.width / 2, targetBox!.y + targetBox!.height - 6, { steps: 8 });
  await expect.poll(() => fieldsRegion.evaluate((region) => region.scrollTop)).toBeGreaterThan(0);
  await page.waitForTimeout(250);
  await page.mouse.up();
  const movedConditionLabel = await page
    .getByRole("button", { name: /^Reorder Condition, position \d+ of 14$/ })
    .getAttribute("aria-label");
  const movedConditionPosition = Number(movedConditionLabel?.match(/position (\d+) of/)?.[1] ?? "0");
  expect(movedConditionPosition).toBeGreaterThan(2);
  const unsavedFieldOrder = await currentLayoutFieldOrder(page);

  await page.getByRole("button", { name: "Preview", exact: true }).click();
  expect(createRequests).toHaveLength(0);
  const unsavedPreview = page.getByLabel("Datasheet preview");
  await expect(unsavedPreview).toBeVisible();
  await expect(unsavedPreview.getByRole("heading", { name: layoutName, exact: true })).toBeVisible();
  await expect(unsavedPreview.getByText("Unsaved owner review order", { exact: true })).toHaveCount(0);
  const unsavedDp780Option = unsavedPreview.locator("option").filter({
    hasText: "DP780 synthetic reference steel",
  });
  await unsavedPreview.getByRole("combobox", { name: "Preview with", exact: true }).selectOption(
    (await unsavedDp780Option.getAttribute("value")) ?? "",
  );
  await expect(unsavedPreview.getByText("CMP-DEMO-DP780", { exact: true })).toBeVisible();
  await expect(unsavedPreview.getByRole("heading", { name: "General", exact: true })).toBeVisible();
  await expect(unsavedPreview.locator(".schema-preview-fields dt")).toHaveText(unsavedFieldOrder);
  expect(createRequests).toHaveLength(0);
  await unsavedPreview.getByRole("button", { name: "Back to layout", exact: true }).click();

  const createResponsePromise = page.waitForResponse((response) =>
    response.request().method() === "POST"
    && /\/api\/v1\/catalog\/tables\/[^/]+\/layouts$/.test(new URL(response.url()).pathname),
  );
  await page.getByRole("button", { name: "Save", exact: true }).click();
  const createResponse = await createResponsePromise;
  expect(createResponse.status()).toBe(201);
  const created = (await createResponse.json()) as {
    layout_id: string;
    table_revision_id: string;
    revision: { id: string; revision_no: number };
    items: Array<{
      attribute_definition_id: string;
      attribute_definition_revision_id: string;
      ordinal: number;
    }>;
  };
  const createBody = createResponse.request().postDataJSON() as {
    table_revision_id: string;
    items: Array<{
      attribute_definition_id: string;
      attribute_definition_revision_id: string;
      ordinal: number;
    }>;
  };
  expect(createBody.table_revision_id).toBe(created.table_revision_id);
  expect(createBody.items).toEqual(created.items);
  expect(created.items).toHaveLength(14);
  expect(created.items.map((item) => item.ordinal)).toEqual(
    Array.from({ length: 14 }, (_, index) => index),
  );
  expect(created.items.every((item) => Boolean(item.attribute_definition_revision_id))).toBeTruthy();
  await expect(page).toHaveURL(new RegExp(
    `object_kind=layouts&object_id=${created.layout_id}&object_revision_id=${created.revision.id}`,
  ));
  await expect(page.getByRole("heading", { name: layoutName, exact: true })).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Layouts list", exact: true })
      .getByRole("button")
      .filter({ hasText: layoutName }),
  ).toContainText("Version 1");

  await page.reload();
  await expect(page.getByRole("heading", { name: layoutName, exact: true })).toBeVisible();
  expect(await currentLayoutFieldOrder(page)).toEqual(unsavedFieldOrder);
  await expect(page).toHaveURL(new RegExp(
    `object_id=${created.layout_id}&object_revision_id=${created.revision.id}`,
  ));

  await page.getByRole("button", { name: "Preview", exact: true }).click();
  const preview = page.getByLabel("Datasheet preview");
  await expect(preview).toBeVisible();
  const dp780Option = preview.locator("option").filter({
    hasText: "DP780 synthetic reference steel",
  });
  await preview.getByRole("combobox", { name: "Preview with", exact: true }).selectOption(
    (await dp780Option.getAttribute("value")) ?? "",
  );
  await expect(preview.getByRole("combobox", { name: "Preview with", exact: true })).toHaveValue(
    (await dp780Option.getAttribute("value")) ?? "",
  );
  await expect(preview.locator("option:checked")).toHaveText(
    "DP780 synthetic reference steel (Draft, revision 2)",
  );
  await expect(preview.getByText("CMP-DEMO-DP780", { exact: true })).toBeVisible();
  await expect(preview.getByText(/Record: Revision 2/)).toHaveCount(0);
  await expect(preview.getByText(/Status: Draft/)).toHaveCount(0);
  await page.getByRole("button", { name: "Back to layout", exact: true }).first().click();

  await page.getByLabel("More actions for " + layoutName).click();
  await page.getByRole("button", { name: "Duplicate layout", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Duplicate layout", exact: true })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Layout name", exact: true })).toHaveValue(copyName);
  expect(createRequests).toHaveLength(1);

  const copyResponsePromise = page.waitForResponse((response) =>
    response.request().method() === "POST"
    && /\/api\/v1\/catalog\/tables\/[^/]+\/layouts$/.test(new URL(response.url()).pathname),
  );
  await page.getByRole("button", { name: "Save", exact: true }).click();
  const copyResponse = await copyResponsePromise;
  expect(copyResponse.status()).toBe(201);
  const copied = (await copyResponse.json()) as {
    layout_id: string;
    revision: { id: string };
    items: Array<{ attribute_definition_revision_id: string }>;
  };
  expect(copied.layout_id).not.toBe(created.layout_id);
  expect(copied.items.map((item) => item.attribute_definition_revision_id)).toEqual(
    created.items.map((item) => item.attribute_definition_revision_id),
  );
  await expect(page.getByRole("heading", { name: copyName, exact: true })).toBeVisible();

  await page.getByLabel("More actions for " + copyName).click();
  await page.getByRole("button", { name: "Delete layout", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Delete unused draft?" })).toBeVisible();
  const deleteCopyPromise = page.waitForResponse((response) =>
    response.request().method() === "DELETE"
    && new URL(response.url()).pathname.endsWith(`/catalog/layouts/${copied.layout_id}`),
  );
  await page.getByRole("button", { name: "Delete unused draft permanently", exact: true }).click();
  expect((await deleteCopyPromise).status()).toBe(204);
  await expect(page.getByRole("region", { name: "Layouts list" }).getByText(copyName)).toHaveCount(0);

  const createdRow = page
    .getByRole("region", { name: "Layouts list", exact: true })
    .getByRole("button")
    .filter({ hasText: layoutName });
  await createdRow.click();
  await page.getByLabel("More actions for " + layoutName).click();
  await page.getByRole("button", { name: "Delete layout", exact: true }).click();
  const deleteCreatedPromise = page.waitForResponse((response) =>
    response.request().method() === "DELETE"
    && new URL(response.url()).pathname.endsWith(`/catalog/layouts/${created.layout_id}`),
  );
  await page.getByRole("button", { name: "Delete unused draft permanently", exact: true }).click();
  expect((await deleteCreatedPromise).status()).toBe(204);
  await expect(createdRow).toHaveCount(0);
});

test("captures the current Database Layout workspace for owner review", async ({ page }) => {
  const screenshotPath = process.env.CMP_ISSUE262_DATABASE_FHD_PATH;
  test.skip(!screenshotPath, "Set CMP_ISSUE262_DATABASE_FHD_PATH for the bounded owner capture.");
  await page.setViewportSize({ width: 1920, height: 1080 });
  await installAdministrator(page);
  await page.goto("/administration/database");
  await page.getByRole("combobox", { name: "Record type", exact: true }).selectOption({
    label: "Demo Material Records · Revision 1",
  });
  await page.getByRole("button", { name: "Layouts", exact: true }).click();
  const layoutRow = page
    .getByRole("region", { name: "Layouts list", exact: true })
    .getByRole("button")
    .filter({ hasText: "Material overview" });
  await layoutRow.click();
  await expect(page.getByRole("heading", { name: "Material overview", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "New layout", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Preview", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save", exact: true })).toBeVisible();
  await expect(page.getByLabel("More actions for Material overview")).toBeVisible();
  await expect(page.locator(".layout-actions-menu")).not.toHaveAttribute("open", "");
  await expect(page.getByRole("button", { name: "Duplicate layout", exact: true })).toBeHidden();
  await expect(page.getByRole("button", { name: "Delete layout", exact: true })).toBeHidden();
  await expect(page.getByRole("button", { name: "Validate layout", exact: true })).toHaveCount(0);
  await expect(page.getByText(/Status: Draft/)).toHaveCount(0);
  await expect(page.getByText("Reload server state", { exact: true })).toHaveCount(0);
  const fieldsRegion = page.getByRole("region", { name: "Datasheet fields", exact: true });
  const geometry = await fieldsRegion.evaluate((region) => {
    const footer = document.querySelector<HTMLElement>(".datasheet-layout-editor > footer");
    const bounds = region.getBoundingClientRect();
    const footerBounds = footer?.getBoundingClientRect();
    return {
      overflowY: getComputedStyle(region).overflowY,
      scrollHeight: region.scrollHeight,
      clientHeight: region.clientHeight,
      regionBottom: bounds.bottom,
      footerTop: footerBounds?.top ?? 0,
    };
  });
  expect(geometry.overflowY).toBe("scroll");
  expect(geometry.scrollHeight).toBeGreaterThan(geometry.clientHeight);
  expect(geometry.regionBottom).toBeLessThanOrEqual(geometry.footerTop + 1);
  const hierarchy = await page.locator(".datasheet-layout-editor").evaluate((editor) => {
    const title = editor.querySelector<HTMLElement>(":scope > header h3");
    const more = editor.querySelector<HTMLElement>(".layout-actions-menu > summary");
    const preview = Array.from(editor.querySelectorAll<HTMLButtonElement>(":scope > footer button"))
      .find((button) => button.textContent?.trim() === "Preview");
    const sectionHeading = editor.querySelector<HTMLElement>(".layout-field-section > h4");
    const fieldLabel = editor.querySelector<HTMLElement>(".layout-field-scroll label span");
    const save = Array.from(editor.querySelectorAll<HTMLButtonElement>(":scope > footer button"))
      .find((button) => button.textContent?.trim() === "Save");
    if (!title || !more || !preview || !sectionHeading || !fieldLabel || !save) {
      throw new Error("Layout hierarchy controls are incomplete.");
    }
    const titleBounds = title.getBoundingClientRect();
    const moreBounds = more.getBoundingClientRect();
    return {
      titleCenter: titleBounds.top + titleBounds.height / 2,
      moreCenter: moreBounds.top + moreBounds.height / 2,
      titleFontSize: Number.parseFloat(getComputedStyle(title).fontSize),
      moreFontSize: Number.parseFloat(getComputedStyle(more).fontSize),
      previewFontSize: Number.parseFloat(getComputedStyle(preview).fontSize),
      moreFontWeight: Number.parseInt(getComputedStyle(more).fontWeight, 10),
      previewFontWeight: Number.parseInt(getComputedStyle(preview).fontWeight, 10),
      saveFontWeight: Number.parseInt(getComputedStyle(save).fontWeight, 10),
      sectionHeadingFontSize: Number.parseFloat(getComputedStyle(sectionHeading).fontSize),
      fieldFontSize: Number.parseFloat(getComputedStyle(fieldLabel).fontSize),
    };
  });
  expect(Math.abs(hierarchy.titleCenter - hierarchy.moreCenter)).toBeLessThanOrEqual(1);
  expect(hierarchy.titleFontSize).toBeGreaterThan(hierarchy.moreFontSize);
  expect(hierarchy.moreFontSize).toBe(hierarchy.previewFontSize);
  expect(hierarchy.fieldFontSize).toBe(hierarchy.sectionHeadingFontSize);
  expect(hierarchy.moreFontSize).toBe(hierarchy.fieldFontSize);
  expect(hierarchy.moreFontWeight).toBe(hierarchy.previewFontWeight);
  expect(hierarchy.saveFontWeight).toBeGreaterThan(hierarchy.moreFontWeight);
  await page.screenshot({ path: screenshotPath, fullPage: false, animations: "disabled" });
});
