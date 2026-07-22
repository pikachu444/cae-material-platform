import { expect, test, type Page } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";

async function expectMaterialsReady(page: Page): Promise<void> {
  await expect(page.locator(".materials-results")).toHaveAttribute("aria-busy", "false", { timeout: 15_000 });
  await expect(page.getByText("Checking…", { exact: true })).toHaveCount(0, { timeout: 15_000 });
}

test("clean demo exposes Search-first material-family journeys and progressive bulk entry", async ({ page, request }) => {
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
    await page.getByRole("search").getByRole("button", { name: "Find", exact: true }).click();
    await expectMaterialsReady(page);
    const resultRow = page.getByRole("row").filter({ hasText: materialCode });
    await expect(resultRow).toBeVisible();
    await resultRow.getByRole("button").click();
    await page.getByRole("button", { name: "Open material" }).click();
    await expect(page).toHaveURL(/\/materials\/[0-9a-f-]+$/);
    await expect(page.getByRole("complementary", { name: "Materials Browse Tree" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("tab", { name: "CAE Cards" })).toBeVisible();
    await page.goto("/materials");
  }

  await page.getByRole("textbox", { name: "Search materials" }).fill("CMP-DEMO-DP780");
  await page.getByRole("search").getByRole("button", { name: "Find", exact: true }).click();
  await expectMaterialsReady(page);
  const dp780Row = page.getByRole("row").filter({ hasText: "CMP-DEMO-DP780" });
  await expect(dp780Row).toHaveCount(1);
  await dp780Row.press("Enter");
  await expect(page).toHaveURL(/\/materials\/[0-9a-f-]+$/);
  const relatedRecord = page.locator(".material-related-context .related-record-list button").filter({ hasText: "DP780 reference Material State" });
  await expect(relatedRecord).toHaveCount(1);
  await relatedRecord.click();
  await expect(page).toHaveURL(/\/materials\/records\/[0-9a-f-]+\/revisions\/[0-9a-f-]+$/);
  await expect(page.getByRole("heading", { name: "DP780 reference Material State", level: 1 })).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/\/materials\/[0-9a-f-]+$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/materials\?q=CMP-DEMO-DP780/);
  await expect(page.getByRole("textbox", { name: "Search materials" })).toHaveValue("CMP-DEMO-DP780");
  await expectMaterialsReady(page);

  await page.goto("/activity");
  await expect(page.getByRole("heading", { name: "Current workspace activity" })).toBeVisible();
  await page.getByText("Advanced jobs and export packages", { exact: true }).click();
  await page.getByRole("button", { name: "Open export packages" }).click();
  await expect(page).toHaveURL(/\/exports$/);
});

test("clean demo downloads exact Neutral cards and the governed ZIP", async ({ page, request }, testInfo) => {
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
  const nativeCards = candidates.items.filter(
    (item) => item.source.kind === "neutral_solver_card_native",
  );
  expect(nativeCards).toHaveLength(2);
  const nativePaths = nativeCards.map((item) => item.default_archive_path);
  expect(nativePaths.some((path) => path.endsWith(".inp"))).toBeTruthy();
  expect(nativePaths.some((path) => path.endsWith(".rad"))).toBeTruthy();
  for (const card of nativeCards) {
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
