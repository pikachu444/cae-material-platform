import { mkdir } from "node:fs/promises";
import { join } from "node:path";

import { expect, test, type Locator, type Page } from "@playwright/test";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";
const evidenceDirectory = process.env.CMP_ADMIN_BUTTON_EVIDENCE_DIR;

async function captureState(page: Page, name: string): Promise<void> {
  if (!evidenceDirectory) {
    return;
  }
  await mkdir(evidenceDirectory, { recursive: true });
  await page.screenshot({ path: join(evidenceDirectory, `${name}-1440x900.png`) });
}

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

async function buttonStyle(button: Locator) {
  return button.evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      backgroundColor: style.backgroundColor,
      borderColor: style.borderColor,
      borderRadius: style.borderRadius,
      boxShadow: style.boxShadow,
      color: style.color,
      cursor: style.cursor,
      height: style.height,
      opacity: style.opacity,
      outlineStyle: style.outlineStyle,
      outlineWidth: style.outlineWidth,
    };
  });
}

async function expectSharedGeometry(
  button: Locator,
  heightToken = "--ux-interactive-min-block-size",
): Promise<void> {
  const style = await buttonStyle(button);
  const sharedHeight = await button.evaluate((_element, token) =>
    getComputedStyle(document.documentElement).getPropertyValue(token).trim(),
    heightToken,
  );
  expect(style.height).toBe(sharedHeight);
  expect(style.borderRadius).toBe("4px");
  expect(style.boxShadow).toBe("none");
}

test("Administration uses one shared semantic button hierarchy across its workspaces", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await installAdministrator(page);

  await page.goto("/administration/database");
  await expect(page.getByRole("region", { name: "Database design", exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "Record type", exact: true }).selectOption({
    label: "Demo Material Records · Revision 1",
  });
  await expect(page.getByText(/^\d+ shown$/)).toBeVisible();
  await expect(page.locator(".administration-workspace .button.primary")).toHaveCount(0);
  const addTable = page.getByRole("button", { name: "Create Record type", exact: true });
  await expect(addTable).toHaveClass("ux-button primary");
  await expectSharedGeometry(addTable);
  expect((await buttonStyle(addTable)).backgroundColor).toBe("rgb(36, 94, 168)");
  await addTable.hover();
  expect((await buttonStyle(addTable)).backgroundColor).toBe("rgb(24, 75, 139)");
  await captureState(page, "database-primary-hover");

  const editorFooter = page.locator(".schema-property-editor .property-sheet footer");
  const check = editorFooter.getByRole("button", { name: "Validate draft", exact: true });
  const saveDraft = editorFooter.getByRole("button", { name: "Save new Record type revision", exact: true });
  await expect(check).toHaveClass("ux-button");
  await expect(saveDraft).toHaveClass("ux-button primary");
  await expect(editorFooter.getByRole("button", { name: "Publish — Not configured" })).toHaveCount(0);
  await expect(editorFooter.locator(".ux-button.primary")).toHaveCount(1);
  await expectSharedGeometry(check, "--ux-control-min-block-size");
  await expectSharedGeometry(saveDraft, "--ux-control-min-block-size");
  await addTable.focus();
  expect(await addTable.evaluate((element) => element.matches(":focus-visible"))).toBe(true);
  const focusStyle = await buttonStyle(addTable);
  expect(focusStyle.outlineStyle).toBe("solid");
  expect(focusStyle.outlineWidth).toBe("3px");
  await captureState(page, "database-primary-focus");

  await page.goto("/administration/records");
  await page.getByRole("combobox", { name: "Record type", exact: true }).selectOption({
    label: "Demo Material Records (Revision 1)",
  });
  await expect(page.locator(".catalog-record-list .section-heading span")).toHaveText(/^\d+ records?$/);
  await page.getByRole("button", { name: "Import records", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Import multiple records", exact: true })).toBeVisible();
  const readColumns = page.getByRole("button", { name: "Read file columns", exact: true });
  const registerRows = page.getByRole("button", { name: "Import validated records", exact: true });
  await expect(readColumns).toHaveClass("ux-button");
  await expect(registerRows).toHaveClass("ux-button primary");
  await expect(registerRows).toBeDisabled();
  await expectSharedGeometry(readColumns, "--ux-control-min-block-size");
  await expectSharedGeometry(registerRows, "--ux-control-min-block-size");
  const disabledStyle = await buttonStyle(registerRows);
  expect(disabledStyle.backgroundColor).toBe("rgb(36, 94, 168)");
  expect(disabledStyle.cursor).toBe("not-allowed");
  expect(disabledStyle.opacity).toBe("0.5");
  await captureState(page, "records-primary-disabled");
  await expect(page.locator(".administration-workspace .button.primary")).toHaveCount(0);

  await page.goto("/administration/access");
  await expect(page.getByRole("heading", { name: "Access", exact: true })).toBeVisible();
  const revoke = page.getByRole("button", { name: "Remove access", exact: true }).first();
  await revoke.scrollIntoViewIfNeeded();
  await expect(revoke).toHaveClass("ux-button danger");
  await expectSharedGeometry(revoke, "--ux-control-min-block-size");
  const dangerStyle = await buttonStyle(revoke);
  expect(dangerStyle.backgroundColor).toBe("rgb(252, 232, 232)");
  expect(dangerStyle.color).toBe("rgb(166, 41, 41)");
  await revoke.hover();
  await captureState(page, "access-danger-hover");
  await page.getByRole("button", { name: "Grant access", exact: true }).click();
  await page.getByRole("combobox", { name: "Role", exact: true }).selectOption("reviewer");
  const createAssignment = page.getByRole("button", { name: "Grant access", exact: true });
  await createAssignment.scrollIntoViewIfNeeded();
  await expect(createAssignment).toHaveClass("ux-button primary");
  await expectSharedGeometry(createAssignment, "--ux-control-min-block-size");

  await page.route("**/api/v1/product-access/assignments", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 2_000));
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Synthetic loading-state evidence" }),
    });
  });
  await createAssignment.click();
  const saving = page.getByRole("button", { name: "Granting…", exact: true });
  await expect(saving).toBeDisabled();
  await expect(saving).toHaveAttribute("aria-busy", "true");
  const loadingStyle = await buttonStyle(saving);
  expect(loadingStyle.cursor).toBe("progress");
  expect(loadingStyle.opacity).toBe("0.72");
  await captureState(page, "access-primary-loading");
  await expect(page.getByRole("alert")).toContainText("Synthetic loading-state evidence");
  await expect(page.getByRole("button", { name: "Grant access", exact: true })).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await expect(page.locator(".administration-workspace .button.primary")).toHaveCount(0);
});
