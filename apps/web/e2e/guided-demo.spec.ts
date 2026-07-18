import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

const webUrl = process.env.CMP_DEMO_WEB_URL ?? "http://127.0.0.1:5173";

test("clean demo exposes three material-family journeys and bulk entry", async ({ page, request }) => {
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
  await expect(
    page.getByRole("heading", { name: "Choose a material family and follow the evidence." }),
  ).toBeVisible();
  await expect(page.getByText("CMP-DEMO-DP780", { exact: true })).toBeVisible();
  await expect(page.getByText("CMP-DEMO-POLYMER-PRONY", { exact: true })).toBeVisible();
  await expect(page.getByText("CMP-DEMO-ELASTOMER-OGDEN", { exact: true })).toBeVisible();

  for (const [action, materialCode] of [
    ["Open metal journey", "CMP-DEMO-DP780"],
    ["Open polymer journey", "CMP-DEMO-POLYMER-PRONY"],
    ["Open elastomer journey", "CMP-DEMO-ELASTOMER-OGDEN"],
  ] as const) {
    await expect(page.getByText(materialCode, { exact: true })).toBeVisible();
    await page.getByRole("button", { name: action }).click();
    await expect(page).toHaveURL(/\/materials\/[0-9a-f-]+\/models$/);
    await page.goto("/");
  }

  await page.getByRole("button", { name: "Open bulk downloads" }).click();
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
  expect(bundles.items).toHaveLength(1);
  expect(bundles.items[0].component_count).toBeGreaterThanOrEqual(6);
  expect(createHash("sha256").update(archive).digest("hex")).toBe(
    bundles.items[0].archive_sha256.replace("sha256:", ""),
  );
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
