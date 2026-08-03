import { expect, test, type Page, type Route } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const tableId = "materials-reference-table";
const evidenceRoot = path.resolve("..", "..", ".cache/issue159-materials-evidence");

function metadata(id: string, revisionNo = 1): Record<string, unknown> {
  return {
    id,
    aggregate_id: id,
    revision_no: revisionNo,
    based_on_revision_id: null,
    schema_id: "urn:cmp:materials-reference:1",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-08-03T00:00:00Z",
    created_by: "00000000-0000-0000-0000-000000000001",
    change_reason: "materials hierarchy reference",
    organization_id: "00000000-0000-0000-0000-000000000002",
    project_id: "00000000-0000-0000-0000-000000000003",
    classification: "internal",
    lifecycle_state: "published",
  };
}

function tableResponse(): Record<string, unknown> {
  return {
    table_id: tableId,
    current_revision: {
      ...metadata(`${tableId}-revision`),
      content: {
        key: "demo_material_records",
         name: "Materials Reference Table",
         description: "Materials reference table",
      },
    },
  };
}

function folder(folderId: string, name: string, parentFolderId: string | null): Record<string, unknown> {
  return {
    folder_id: folderId,
    table_id: tableId,
    current_revision: metadata(`${folderId}-revision`),
    content: {
      table_revision_id: `${tableId}-revision`,
      name,
      description: null,
      parent_folder_id: parentFolderId,
      parent_folder_revision_id: parentFolderId ? `${parentFolderId}-revision` : null,
    },
  };
}

function record(recordId: string, row: number, name?: string): Record<string, unknown> {
  const names = [
    "DP780 dual-phase steel",
    "DP600 dual-phase steel",
    "HSLA structural steel",
    "AISI 304 stainless steel",
    "PA66 glass-filled polymer",
  ];
  const materialName = name ?? `${names[row % names.length]} — reference ${String(row).padStart(3, "0")}`;
  const materialClass = materialName.includes("PA66") ? "polymer" : "metal";
  return {
    record_id: recordId,
    table_id: tableId,
    domain_binding: {
      binding_id: `${recordId}-binding`,
      record_id: recordId,
      record_revision_id: `${recordId}-revision`,
      kind: "material",
      object_id: `${recordId}-material`,
      revision_id: `${recordId}-material-revision`,
      workbench_path: `/materials/${recordId}-material`,
    },
    current_revision: {
      ...metadata(`${recordId}-revision`),
      revision_no: 1,
      content: {
        table_revision_id: `${tableId}-revision`,
         name: materialName,
         external_key: `MAT-${String(row + 1).padStart(3, "0")}`,
         description: "Materials reference record with governed response data",
        folder_id: null,
        folder_revision_id: null,
        values: [
          { data_type: "discrete", attribute_definition_id: "material-class", attribute_definition_revision_id: "material-class-r1", value: materialClass },
           { data_type: "text", attribute_definition_id: "provider", attribute_definition_revision_id: "provider-r1", value: "Northstar Materials" },
           { data_type: "text", attribute_definition_id: "evidence-source", attribute_definition_revision_id: "evidence-source-r1", value: "Governed reference" },
        ],
      },
    },
  };
}

async function fulfillJson(route: Route, value: unknown): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(value),
  });
}

async function installFixture(page: Page): Promise<void> {
  const folderNames = [
    "Cold-rolled steel reference archive for stamped body panels",
    "Automotive body sheet grades",
    "Structural plate and section data",
    "Heat-treated alloy specifications",
    "Stainless and corrosion-resistant grades",
    "Polymer compound reference data",
    "Supplier certificate imports",
    "Qualification and acceptance records",
    "Legacy design allowables",
    "Temperature-conditioned studies",
    "Welded joint material records",
    "Surface-treated coil references",
  ];
  const rootFolders = Array.from({ length: 90 }, (_, index) => folder(
    `folder-${index}`,
    `${folderNames[index % folderNames.length]} · ${String(index + 1).padStart(3, "0")}`,
    null,
  ));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const requestPath = url.pathname;
    if (requestPath.endsWith("/demo-identity/token")) {
      await fulfillJson(route, {
         access_token: "materials-scroll-token",
        token_type: "Bearer",
        expires_in_seconds: 900,
        organization_id: "00000000-0000-0000-0000-000000000002",
        project_id: "00000000-0000-0000-0000-000000000003",
         group: "materials-reference",
      });
      return;
    }
    if (requestPath.endsWith("/catalog/explorer/tables")) {
      await fulfillJson(route, { items: [tableResponse()] });
      return;
    }
    if (requestPath.endsWith(`/catalog/explorer/tables/${tableId}/children`)) {
      const parent = url.searchParams.get("parent_folder_id");
      if (parent?.startsWith("folder-deep-")) {
        const level = Number(parent.slice("folder-deep-".length));
        await fulfillJson(route, {
          table: tableResponse(),
             folders: level < 9
             ? [folder(`folder-deep-${level + 1}`, `Temperature conditioning run ${level + 1}`, parent)]
            : [],
          records: [],
        });
      } else {
        await fulfillJson(route, { table: tableResponse(), folders: rootFolders, records: [] });
      }
      return;
    }
    if (requestPath.endsWith(`/catalog/tables/${tableId}/subsets`)) {
      await fulfillJson(route, { items: [] });
      return;
    }
    if (requestPath.endsWith(`/catalog/tables/${tableId}/attributes`)) {
      await fulfillJson(route, {
        items: [
          { attribute_definition_id: "material-class", table_id: tableId, current_revision: { content: { key: "material_class" } } },
          { attribute_definition_id: "provider", table_id: tableId, current_revision: { content: { key: "provider" } } },
          { attribute_definition_id: "evidence-source", table_id: tableId, current_revision: { content: { key: "evidence_source" } } },
        ],
      });
      return;
    }
    if (requestPath.endsWith("/catalog/records:search")) {
      const payload = request.postDataJSON() as { text?: string | null } | null;
      const empty = payload?.text === "magnesium";
      const short = payload?.text === "steel";
      const shortNames = [
        "DP780 dual-phase steel",
        "DP600 dual-phase steel",
        "HSLA structural steel",
        "AISI 304 stainless steel",
        "IF mild steel",
        "TRIP advanced high-strength steel",
      ];
      await fulfillJson(route, {
        items: empty ? [] : Array.from(
          { length: short ? 6 : 50 },
          (_, index) => record(`record-${index}`, index, short ? shortNames[index] : undefined),
        ),
        total_count: empty ? 0 : short ? 6 : 120,
        offset: 0,
        limit: 50,
        facets: empty ? [] : [
           { attribute_definition_id: "material-class", value: "metal", count: short ? 6 : 120 },
           { attribute_definition_id: "provider", value: "Northstar Materials", count: short ? 6 : 120 },
           { attribute_definition_id: "evidence-source", value: "Governed reference", count: short ? 6 : 120 },
        ],
      });
      return;
    }
    await fulfillJson(route, {});
  });
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "cmp.material-platform.api-config",
       JSON.stringify({ baseUrl: "/api/v1", accessToken: "materials-scroll-token" }),
    );
  });
}

async function waitForFixture(page: Page, searchText = "reference"): Promise<void> {
  await page.goto("/materials");
  await expect(page.locator(".materials-results")).toHaveAttribute("aria-busy", "false");
  await expect(page.locator(".materials-result-table tbody tr").first()).toBeVisible();
  await expect(page.locator(".materials-tree-row").first()).toBeVisible();
  await page.getByRole("textbox", { name: "Search materials" }).fill(searchText);
  await page.getByLabel("Material query").getByRole("button", { name: "Find", exact: true }).click();
  await expect(page.locator(".materials-result-table tbody tr").first()).toBeVisible();
}

test("Materials table and Browse tree keep independent native local scroll at required viewports", async ({ page }) => {
  test.setTimeout(120_000);
  await mkdir(evidenceRoot, { recursive: true });
  await installFixture(page);

  for (const viewport of [
    { width: 1366, height: 768 },
    { width: 1440, height: 900 },
    { width: 1920, height: 1080 },
  ]) {
    await page.setViewportSize(viewport);
    await waitForFixture(page);
    const pa66Row = page.locator(".materials-result-table tbody tr").filter({ hasText: "PA66 glass-filled polymer" }).first();
    await expect(pa66Row).toContainText("Polymer");
    const results = page.locator(".materials-result-table-wrap");
    const tree = page.locator(".materials-tree-scroll");
    const resultRailY = page.locator(".materials-result-scroll-shell .materials-scroll-rail-y");
    const treeRailY = page.locator(".materials-tree-scroll-shell .materials-scroll-rail-y");
    const treeRailX = page.locator(".materials-tree-scroll-shell .materials-scroll-rail-x");
    const title = page.getByRole("heading", { name: "Materials", level: 2 });
    const beforeTitle = await title.boundingBox();
    const geometry = await Promise.all([results, tree].map(async (locator) => locator.evaluate((element) => ({
      clientWidth: element.clientWidth,
      clientHeight: element.clientHeight,
      scrollWidth: element.scrollWidth,
      scrollHeight: element.scrollHeight,
    }))));
    expect(geometry[0].scrollHeight).toBeGreaterThan(geometry[0].clientHeight);
    expect(geometry[1].scrollHeight).toBeGreaterThan(geometry[1].clientHeight);
    expect(geometry[1].scrollWidth).toBeGreaterThan(geometry[1].clientWidth);
    await expect(resultRailY).toBeVisible();
    await expect(treeRailY).toBeVisible();
    await expect(treeRailX).toBeVisible();
    for (const rail of [resultRailY, treeRailY, treeRailX]) {
      await expect(rail).toHaveCSS("background-color", "rgb(220, 231, 236)");
      await expect(rail.locator(".materials-scroll-thumb")).toBeVisible();
      const railGeometry = await rail.evaluate((element) => {
        const thumb = element.firstElementChild as HTMLElement;
        const railBox = element.getBoundingClientRect();
        const thumbBox = thumb.getBoundingClientRect();
        return {
          railLength: element.classList.contains("materials-scroll-rail-x") ? railBox.width : railBox.height,
          thumbLength: element.classList.contains("materials-scroll-rail-x") ? thumbBox.width : thumbBox.height,
        };
      });
      expect(railGeometry.thumbLength).toBeGreaterThanOrEqual(36);
      expect(railGeometry.thumbLength).toBeLessThan(railGeometry.railLength);
    }

    await results.hover();
    await page.mouse.wheel(0, 700);
    await expect.poll(() => results.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
    const tableScrollTop = await results.evaluate((element) => element.scrollTop);
    await tree.hover();
    await page.mouse.wheel(0, 700);
    await expect.poll(() => tree.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
    await page.mouse.wheel(700, 0);
    await expect.poll(() => tree.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
    expect(await results.evaluate((element) => element.scrollTop)).toBe(tableScrollTop);
    await results.evaluate((element) => { element.scrollTop = 0; });
    await expect.poll(() => results.evaluate((element) => element.scrollTop)).toBe(0);
    const resultRailBox = await resultRailY.boundingBox();
    expect(resultRailBox).not.toBeNull();
    await page.mouse.click(resultRailBox!.x + resultRailBox!.width / 2, resultRailBox!.y + resultRailBox!.height - 2);
    await expect.poll(() => results.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);

    await tree.evaluate((element) => { element.scrollTop = 0; element.scrollLeft = 0; });
    await expect.poll(() => tree.evaluate((element) => element.scrollTop)).toBe(0);
    const treeThumbBox = await treeRailY.locator(".materials-scroll-thumb").boundingBox();
    const treeRailBox = await treeRailY.boundingBox();
    expect(treeThumbBox).not.toBeNull();
    expect(treeRailBox).not.toBeNull();
    await page.mouse.move(treeThumbBox!.x + treeThumbBox!.width / 2, treeThumbBox!.y + treeThumbBox!.height / 2);
    await page.mouse.down();
    await page.mouse.move(treeRailBox!.x + treeRailBox!.width / 2, treeRailBox!.y + treeRailBox!.height - treeThumbBox!.height / 2);
    await page.mouse.up();
    await expect.poll(() => tree.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);

    await treeRailX.focus();
    await treeRailX.press("End");
    await expect.poll(() => tree.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
    await tree.focus();
    await tree.press("End");
    await expect.poll(() => tree.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
    await tree.evaluate((element) => { element.scrollLeft = 0; });
    await expect.poll(() => tree.evaluate((element) => element.scrollLeft)).toBe(0);
    await results.focus();
    await results.press("PageDown");
    await expect.poll(() => results.evaluate((element) => element.scrollTop)).toBeGreaterThan(tableScrollTop);
    const afterTitle = await title.boundingBox();
    expect(afterTitle?.top).toBe(beforeTitle?.top);
    expect(afterTitle?.left).toBe(beforeTitle?.left);
    await page.screenshot({ path: path.join(evidenceRoot, `long-${viewport.width}x${viewport.height}.png`), fullPage: false });
    await tree.hover();
    await page.waitForTimeout(200);
    await page.screenshot({ path: path.join(evidenceRoot, `long-${viewport.width}x${viewport.height}-tree-hover.png`), fullPage: false });
    await results.hover();
    await page.waitForTimeout(200);
    await page.screenshot({ path: path.join(evidenceRoot, `long-${viewport.width}x${viewport.height}-results-hover.png`), fullPage: false });
  }

  await page.setViewportSize({ width: 1440, height: 900 });
  await waitForFixture(page);
  await page.getByRole("textbox", { name: "Search materials" }).fill("steel");
  await page.getByLabel("Material query").getByRole("button", { name: "Find", exact: true }).click();
  await expect(page.locator(".materials-result-table-wrap")).toHaveJSProperty("scrollHeight", await page.locator(".materials-result-table-wrap").evaluate((element) => element.clientHeight));
  await expect(page.locator(".materials-result-scroll-shell .materials-scroll-rail-y")).toHaveCount(0);
  await page.screenshot({ path: path.join(evidenceRoot, "short-1440x900.png"), fullPage: false });

  await page.getByRole("textbox", { name: "Search materials" }).fill("magnesium");
  await page.getByLabel("Material query").getByRole("button", { name: "Find", exact: true }).click();
  await expect(page.locator(".ux-empty").first()).toBeVisible();
  const emptyGeometry = await page.locator(".materials-result-table-wrap").evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }));
  expect(emptyGeometry.scrollHeight).toBeLessThanOrEqual(emptyGeometry.clientHeight + 1);
  await expect(page.locator(".materials-result-scroll-shell .materials-scroll-rail-y")).toHaveCount(0);
  await expect(page.locator(".materials-result-scroll-shell .materials-scroll-rail-x")).toHaveCount(0);
  await page.screenshot({ path: path.join(evidenceRoot, "empty-1440x900.png"), fullPage: false });
});
