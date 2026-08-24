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

test("Database design previews a real Record, preserves a blocked selection, and deletes only an unused r1 draft", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await installAdministrator(page);
  await page.goto("/administration/database");

  await expect(page.getByRole("heading", { name: "Database design", exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "Table", exact: true }).selectOption({
    label: "Demo Material Records · r1",
  });
  await expect(page.getByRole("button", { name: "Attributes", exact: true })).toContainText("14");
  await expect(page.getByRole("button", { name: "Layouts", exact: true })).toContainText("1");
  await page.getByRole("button", { name: "Layouts", exact: true }).click();
  await page.getByRole("region", { name: "Layouts list", exact: true }).getByRole("button").first().click();

  await page.getByRole("button", { name: "Preview record", exact: true }).click();
  const preview = page.getByLabel("Adjacent datasheet preview");
  await expect(preview).toBeVisible();
  const dp780Option = preview.locator("option").filter({ hasText: "DP780 synthetic reference steel" });
  await preview.getByRole("combobox", { name: "Record", exact: true }).selectOption(
    (await dp780Option.getAttribute("value")) ?? "",
  );
  await expect(preview.getByText("DP780 synthetic reference steel", { exact: true })).toBeVisible();
  await expect(preview.getByText("CMP-DEMO-DP780", { exact: true })).toBeVisible();
  await expect(preview.getByText("Layout r1 · 14 exact Attribute revision pins", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/table_id=.+&table_revision_id=.+&object_kind=layouts&object_id=.+&object_revision_id=.+&record_id=.+&record_revision_id=.+/);
  await page.reload();
  await expect(page.getByLabel("Adjacent datasheet preview")).toBeVisible();
  await expect(page.getByLabel("Adjacent datasheet preview").getByText("DP780 synthetic reference steel", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Adjacent datasheet preview").getByText("CMP-DEMO-DP780", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Close preview", exact: true }).first().click();

  await page.getByRole("button", { name: "Table", exact: true }).click();
  const seededTable = page.getByRole("button", { name: /Demo Material Records.*r1/ });
  await seededTable.click();
  await expect(seededTable).toHaveClass(/active/);
  await page.getByRole("button", { name: "Delete draft", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Delete unpublished draft?" })).toBeVisible();
  await expect(page.getByText(/Records, Links, references or dependencies/)).toBeVisible();
  await page.getByRole("button", { name: "Delete draft permanently", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(/referenced|Records|dependencies/i);
  await expect(seededTable).toHaveClass(/active/);

  const suffix = Date.now().toString().slice(-8);
  const duplicateName = `Issue 289 unused draft ${suffix}`;
  await page.getByRole("button", { name: "Duplicate", exact: true }).click();
  await expect(page.getByRole("heading", { name: "New table", exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "Display name", exact: true }).fill(duplicateName);
  await page.getByRole("textbox", { name: "Reference key", exact: true }).fill(`issue289_${suffix}`);
  await page.getByRole("button", { name: "Save new Table", exact: true }).click();
  await expect(page.locator(".success-banner")).toContainText(
    `${duplicateName} Table revision 1 created.`,
  );
  const duplicateRow = page.getByRole("button", { name: new RegExp(`${duplicateName}.*r1`) });
  await expect(duplicateRow).toHaveClass(/active/);

  await page.getByRole("button", { name: "Delete draft", exact: true }).click();
  await page.getByRole("button", { name: "Delete draft permanently", exact: true }).click();
  await expect(page.locator(".success-banner")).toContainText(
    `${duplicateName} unpublished draft was permanently deleted.`,
  );
  await expect(duplicateRow).toHaveCount(0);
  await expect(page.getByText("3 shown", { exact: true })).toBeVisible();
});
