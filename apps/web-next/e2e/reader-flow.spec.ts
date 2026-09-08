import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

test.describe("P1 reader journey", () => {
  test("search, sort, open the associated card, download, return, acknowledge and recover", async ({ page }) => {
    await page.goto("/test-data?layout=A&scenario=dense");
    await expect(page.getByRole("heading", { name: "Results" })).toBeVisible();
    await expect(page.locator("tbody tr")).toHaveCount(50);

    await page.locator("thead th").filter({ hasText: "Test Data" }).getByRole("button").click();
    await expect.poll(() => new URL(page.url()).searchParams.get("direction")).toBe("asc");

    await page.getByLabel("Search Test Data").fill("td-00042");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page).toHaveURL(/q=td-00042/);
    await expect(page.locator("tbody tr")).toHaveCount(1);
    await page.getByRole("button", { name: /td-00042/ }).click();
    await expect(page.getByRole("heading", { name: /Reference tensile coupon/ })).toBeVisible();
    await expect(page.getByText(/1,000,000 source points.*1,000 point preview/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Curve preview" })).toBeVisible();

    await page.getByRole("button", { name: "B · curve focus" }).click();
    await expect(page).toHaveURL(/layout=B/);
    await expect(page.getByRole("button", { name: "Results" })).toBeVisible();
    await expect(page.locator("svg").first()).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { name: /Reference tensile coupon/ })).toBeVisible();
    await page.getByRole("button", { name: "Results" }).click();
    await expect(page).toHaveURL(/q=td-00042/);
    expect(new URL(page.url()).searchParams.get("selection")).toBe("td-00042");
    expect(new URL(page.url()).searchParams.get("view")).toBe("results");
    await expect(page.locator('tr[aria-selected="true"]')).toHaveCount(1);
    await page.getByRole("button", { name: /td-00042/ }).click();
    await expect(page.getByRole("heading", { name: /Reference tensile coupon/ })).toBeVisible();
    await page.getByRole("button", { name: /OpenRadioss linear elastic reference card/ }).click();
    await expect(page).toHaveURL(/\/cards\/card-00001/);
    expect(new URL(page.url()).searchParams.get("q")).toBeNull();
    await expect(page.getByRole("heading", { name: "OpenRadioss linear elastic reference card" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Native preview" })).toBeVisible();

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download native card" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("reference-linear-elasticity-kg-m-s.rad");
    const downloadedBytes = await readFile((await download.path()) ?? "");
    expect(downloadedBytes.byteLength).toBe(504);
    expect(createHash("sha256").update(downloadedBytes).digest("hex").toUpperCase()).toBe("FE8873B1F6978D5BF30D4936EADBEE9FB3B3BF5CD086E4C827BDF2E6105829A1");

    await page.getByRole("link", { name: "Solver Cards" }).click();
    await expect(page).toHaveURL(/\/cards(?:\?|$)/);
    await page.getByLabel("Search Solver Cards").fill("card-00002");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page.locator("tbody tr")).toHaveCount(1);
    await page.getByRole("button", { name: /card-00002/ }).click();
    await expect(page.getByRole("heading", { name: "Comparison card with acknowledged approximation" })).toBeVisible();
    await expect(page.getByRole("checkbox", { name: /acknowledge the approximation/i })).toBeVisible();
    await expect(page.getByRole("button", { name: "Download native card" })).toBeDisabled();
    await page.getByRole("checkbox", { name: /acknowledge the approximation/i }).check();
    await expect(page.getByRole("button", { name: "Download native card" })).toBeEnabled();

    await page.getByRole("button", { name: "Edit display metadata" }).click();
    const title = page.getByLabel("Title");
    await title.fill("Edited card title for this review");
    await page.keyboard.press("Escape");
    await expect(page.getByText("Unsaved draft")).toBeVisible();
    await page.getByRole("button", { name: "Discard draft" }).click();
    await expect(page.getByRole("heading", { name: "Comparison card with acknowledged approximation" })).toBeVisible();
    await page.getByRole("button", { name: "Edit display metadata" }).click();
    await page.getByLabel("Title").fill("Edited card title for this review");
    await page.getByRole("button", { name: "Apply example" }).click();
    await expect(page.getByRole("status")).toContainText("예시에 적용됨");
    await expect(page.getByRole("heading", { name: "Edited card title for this review" })).toBeVisible();
    await expect(page.getByRole("article").getByText("card-00002", { exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { name: "Comparison card with acknowledged approximation" })).toBeVisible();

    await page.getByRole("link", { name: "Solver Cards" }).click();
    await page.getByLabel("Search Solver Cards").fill("card-00003");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page.locator("tbody tr")).toHaveCount(1);
    await page.getByRole("button", { name: /card-00003/ }).click();
    await expect(page.getByRole("alert").filter({ hasText: "Download blocked" })).toContainText("Download blocked");
    await expect(page.getByRole("button", { name: "Download native card" })).toBeDisabled();
  });
});
