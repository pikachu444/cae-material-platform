import { expect, test, type Page } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";

type SavedRecord = {
  record_id: string;
  table_id: string;
  current_revision: {
    id: string;
    revision_no: number;
    content: {
      table_revision_id: string;
      name: string;
      external_key: string | null;
      description: string | null;
      folder_id: string | null;
      folder_revision_id: string | null;
      values: Array<{
        data_type: string;
        value?: string;
      }>;
    };
  };
};

async function installAdministrator(page: Page): Promise<string> {
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
  return token;
}

async function expectExactSavedRoute(page: Page, saved: SavedRecord): Promise<void> {
  await expect
    .poll(() => {
      const url = new URL(page.url());
      return {
        pathname: url.pathname,
        tableId: url.searchParams.get("table_id"),
        tableRevisionId: url.searchParams.get("table_revision_id"),
        recordId: url.searchParams.get("record_id"),
        recordRevisionId: url.searchParams.get("record_revision_id"),
      };
    })
    .toEqual({
      pathname: "/administration/records",
      tableId: saved.table_id,
      tableRevisionId: saved.current_revision.content.table_revision_id,
      recordId: saved.record_id,
      recordRevisionId: saved.current_revision.id,
    });
}

async function expectRecordReadBack(
  page: Page,
  saved: SavedRecord,
  materialCode: string,
): Promise<void> {
  await expect(
    page.getByRole("heading", {
      name: saved.current_revision.content.name,
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText(`Draft · Revision ${saved.current_revision.revision_no}`, { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Name", exact: true })).toHaveValue(
    saved.current_revision.content.name,
  );
  await expect(page.getByRole("textbox", { name: "Record code", exact: true })).toHaveValue(
    saved.current_revision.content.external_key ?? "",
  );
  await expect(page.getByRole("textbox", { name: "Description", exact: true })).toHaveValue(
    saved.current_revision.content.description ?? "",
  );
  await expect(
    page.getByRole("group", { name: "Material code *", exact: true }).getByRole("textbox"),
  ).toHaveValue(materialCode);
}

test("Administration completes Database, exact Record, and Access read-back in one journey", async ({
  page,
}) => {
  test.setTimeout(90_000);
  const accessToken = await installAdministrator(page);

  const suffix = `${Date.now()}-${test.info().workerIndex}`;
  const recordName = `Issue 262 read-back ${suffix}`;
  const recordCode = `ISSUE262-${suffix}`;
  const materialCode = `CMP-ISSUE262-${suffix}`;
  const initialDescription = `Isolated FE-07B browser record ${suffix}`;
  const revisedDescription = `${initialDescription} revised`;

  await page.goto("/administration/database");
  await page.getByRole("combobox", { name: "Record type", exact: true }).selectOption({
    label: "Demo Material Records · Revision 1",
  });
  await page.getByRole("button", { name: "Layouts", exact: true }).click();
  const materialOverview = page
    .getByRole("region", { name: "Layouts list", exact: true })
    .getByRole("button", { name: /^Material overview\b/ });
  await materialOverview.click();
  await expect(page.getByRole("heading", { name: "Material overview", exact: true })).toBeVisible();
  const previewAction = page.getByRole("button", { name: "Preview", exact: true });
  await expect(previewAction).toBeEnabled();
  await previewAction.click();
  const preview = page.getByLabel("Datasheet preview");
  const seededRecordOption = preview.locator("option").filter({
    hasText: "DP780 synthetic reference steel",
  });
  const seededRecordId = (await seededRecordOption.getAttribute("value")) ?? "";
  expect(seededRecordId).not.toBe("");
  await preview.getByRole("combobox", { name: "Preview with", exact: true }).selectOption(
    seededRecordId,
  );
  const selectedRecordResponse = await page.request.get(
    `${webUrl}/api/v1/catalog/records/${encodeURIComponent(seededRecordId)}`,
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );
  expect(selectedRecordResponse.ok()).toBeTruthy();
  const selectedRecord = (await selectedRecordResponse.json()) as SavedRecord;
  await page.getByRole("button", { name: "Open in Records", exact: true }).click();
  await expect(page).toHaveURL(/\/administration\/records\?.*record_revision_id=.+/);
  const previewHandoffUrl = new URL(page.url());
  expect(previewHandoffUrl.searchParams.get("table_id")).toBe(selectedRecord.table_id);
  expect(previewHandoffUrl.searchParams.get("table_revision_id")).toBe(
    selectedRecord.current_revision.content.table_revision_id,
  );
  expect(previewHandoffUrl.searchParams.get("folder_id")).toBe(
    selectedRecord.current_revision.content.folder_id,
  );
  expect(previewHandoffUrl.searchParams.get("folder_revision_id")).toBe(
    selectedRecord.current_revision.content.folder_revision_id,
  );
  expect(previewHandoffUrl.searchParams.get("record_id")).toBe(selectedRecord.record_id);
  expect(previewHandoffUrl.searchParams.get("record_revision_id")).toBe(
    selectedRecord.current_revision.id,
  );
  await expect(page.getByRole("textbox", { name: "Record code", exact: true })).toHaveValue(
    "CMP-DEMO-DP780",
  );
  await page.reload();
  await expect(page.getByRole("textbox", { name: "Record code", exact: true })).toHaveValue(
    "CMP-DEMO-DP780",
  );
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await expect(page).toHaveURL(/\/administration\/records\?.*table_id=.+&table_revision_id=.+/);
  await expect(page.locator(".catalog-record-list .section-heading span")).toHaveText(/^\d+ records?$/);
  await page.getByRole("button", { name: "Create record", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Create record", exact: true })).toBeVisible();
  await expect(page.getByRole("group", { name: "Material code *", exact: true })).toBeVisible();

  await page.getByRole("textbox", { name: "Name", exact: true }).fill(recordName);
  await page.getByRole("textbox", { name: "Record code", exact: true }).fill(recordCode);
  await page.getByRole("textbox", { name: "Description", exact: true }).fill(initialDescription);
  await page
    .getByRole("group", { name: "Material code *", exact: true })
    .getByRole("textbox")
    .fill(materialCode);
  await expect(page.getByRole("button", { name: "Save new record", exact: true })).toBeEnabled();

  const createResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "POST"
      && /^\/api\/v1\/catalog\/tables\/[^/]+\/records$/.test(url.pathname)
    );
  });
  await page.getByRole("button", { name: "Save new record", exact: true }).click();
  const createResponse = await createResponsePromise;
  expect(createResponse.ok()).toBeTruthy();
  const created = (await createResponse.json()) as SavedRecord;
  expect(created.current_revision.revision_no).toBe(1);
  expect(created.current_revision.content.name).toBe(recordName);
  expect(created.current_revision.content.external_key).toBe(recordCode);
  expect(created.current_revision.content.description).toBe(initialDescription);
  expect(created.current_revision.content.values).toContainEqual(
    expect.objectContaining({ data_type: "text", value: materialCode }),
  );
  await expectExactSavedRoute(page, created);

  await page.reload();
  await expectExactSavedRoute(page, created);
  await expectRecordReadBack(page, created, materialCode);

  await page
    .getByRole("textbox", { name: "Description", exact: true })
    .fill(revisedDescription);
  const reviseResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "POST"
      && url.pathname === `/api/v1/catalog/records/${created.record_id}/revisions`
    );
  });
  await page.getByRole("button", { name: "Save new revision", exact: true }).click();
  const reviseResponse = await reviseResponsePromise;
  expect(reviseResponse.ok()).toBeTruthy();
  const revised = (await reviseResponse.json()) as SavedRecord;
  expect(revised.record_id).toBe(created.record_id);
  expect(revised.current_revision.id).not.toBe(created.current_revision.id);
  expect(revised.current_revision.revision_no).toBe(2);
  expect(revised.current_revision.content.description).toBe(revisedDescription);
  expect(revised.current_revision.content.values).toContainEqual(
    expect.objectContaining({ data_type: "text", value: materialCode }),
  );
  await expectExactSavedRoute(page, revised);

  await page.reload();
  await expectExactSavedRoute(page, revised);
  await expectRecordReadBack(page, revised, materialCode);

  await page.goto(
    `/catalog/records?table_id=${encodeURIComponent(revised.table_id)}&table_revision_id=${encodeURIComponent(revised.current_revision.content.table_revision_id)}&record_id=${encodeURIComponent(revised.record_id)}&revision_id=${encodeURIComponent(revised.current_revision.id)}`,
  );
  const primaryNavigation = page.getByRole("navigation", { name: "Primary navigation" });
  await expect(primaryNavigation.getByRole("button", { name: "Materials", exact: true })).toBeVisible();
  await expect(primaryNavigation.getByRole("button", { name: "Modeling", exact: true })).toBeVisible();
  await expect(primaryNavigation.getByRole("button", { name: "Activity", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Materials commands" })).toHaveCount(0);
  const legacyTasks = page.getByRole("navigation", { name: "Administration tasks" });
  await expect(legacyTasks.getByRole("button")).toHaveCount(4);
  await expect(legacyTasks.getByRole("button", { name: "Records", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect
    .poll(() => {
      const url = new URL(page.url());
      return {
        pathname: url.pathname,
        tableId: url.searchParams.get("table_id"),
        recordId: url.searchParams.get("record_id"),
        revisionId: url.searchParams.get("revision_id"),
      };
    })
    .toEqual({
      pathname: "/catalog/records",
      tableId: revised.table_id,
      recordId: revised.record_id,
      revisionId: revised.current_revision.id,
    });
  await expectRecordReadBack(page, revised, materialCode);

  await page.getByRole("navigation", { name: "Administration tasks" }).getByRole(
    "button",
    { name: "Database", exact: true },
  ).click();
  await expect(page.getByRole("region", { name: "Database design", exact: true })).toBeVisible();
  await page.getByRole("navigation", { name: "Administration tasks" }).getByRole(
    "button",
    { name: "Access", exact: true },
  ).click();
  await expect(page.getByRole("heading", { name: "Access", exact: true })).toBeVisible();
  for (const heading of ["Member", "Role", "Permissions", "Action"]) {
    await expect(page.getByRole("columnheader", { name: heading, exact: true })).toBeVisible();
  }

  const groupName = `issue262-demo-${suffix}`;
  await page.getByRole("button", { name: "Grant access", exact: true }).click();
  await page.getByRole("combobox", { name: "Role", exact: true }).selectOption("reviewer");
  await page.getByRole("textbox", { name: "Team name", exact: true }).fill(groupName);
  await page.getByRole("textbox", { name: "Reason", exact: true }).fill(
    `FE-07B demonstration grant ${suffix}`,
  );
  const grantResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "POST"
      && url.pathname === "/api/v1/product-access/assignments";
  });
  await page.getByRole("button", { name: "Grant access", exact: true }).click();
  expect((await grantResponsePromise).ok()).toBeTruthy();
  const assignmentRow = page.getByRole("row").filter({ hasText: groupName });
  await expect(assignmentRow).toContainText("Reviewer");
  await expect(assignmentRow).toContainText("Model approval");

  await assignmentRow.getByRole("button", { name: "Remove access", exact: true }).click();
  const revokePanel = page.locator(".access-revoke-panel");
  await revokePanel.getByRole("textbox", { name: "Reason", exact: true }).fill(
    `FE-07B demonstration cleanup ${suffix}`,
  );
  const revokeResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "POST"
      && /\/api\/v1\/product-access\/assignments\/[^/]+\/revoke$/.test(url.pathname);
  });
  await revokePanel.getByRole("button", { name: "Remove access", exact: true }).click();
  expect((await revokeResponsePromise).ok()).toBeTruthy();
  await expect(page.getByRole("row").filter({ hasText: groupName })).toHaveCount(0);
});
