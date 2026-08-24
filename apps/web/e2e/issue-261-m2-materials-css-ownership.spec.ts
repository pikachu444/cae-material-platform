import { expect, test, type Page, type Route } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";

/**
 * Issue #261 M2 keeps one deliberately small browser journey.  The fixture
 * uses the same exact-record and Neutral Solver Card shapes as
 * material-library-pinned and solver-card-delivery-ui; it is not a second
 * product fixture or an alternate route contract.
 */
const evidencePhase = process.env.CMP_ISSUE_261_EVIDENCE_PHASE === "before" ? "before" : "after";
const evidenceDirectory = process.env.CMP_ISSUE_261_EVIDENCE_DIR;
const tableId = "m2-materials-table";
const materialId = "m2-material";
const materialRevisionId = "m2-material-r1";
const recordId = "m2-record";
const recordRevisionId = "m2-record-r1";
const cardId = "m2-card";
const cardRevisionId = "m2-card-r1";
const noCardMaterialId = "m2-no-card-material";
const noCardMaterialRevisionId = "m2-no-card-r1";
const noCardRecordId = "m2-no-card-record";
const noCardRecordRevisionId = "m2-no-card-record-r1";

const viewports = [
  { width: 1366, height: 768 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
  { width: 2560, height: 1440 },
  { width: 3840, height: 2160 },
] as const;

function metadata(id: string, aggregateId: string, revisionNo = 1): Record<string, unknown> {
  return {
    id,
    aggregate_id: aggregateId,
    revision_no: revisionNo,
    based_on_revision_id: null,
    schema_id: "urn:cmp:issue-261-m2-browser:1",
    schema_version: "1.0.0",
    content_hash: `${id}-hash`,
    created_at: "2026-08-20T00:00:00Z",
    created_by: "issue-261-m2-browser",
    change_reason: "Issue #261 M2 deterministic Materials ownership fixture",
    organization_id: "issue-261-m2-org",
    project_id: "issue-261-m2-project",
    classification: "internal",
    lifecycle_state: "published",
  };
}

function materialRevision(id: string, aggregateId: string, name: string) {
  return {
    ...metadata(id, aggregateId),
    content: {
      name,
      material_code: "M2-STEEL",
      material_family: "steel",
      material_class: "metal",
      description: "Governed synthetic reference for Materials ownership evidence.",
    },
    provenance: {
      entity_type: "material.revision",
      reference_type: "issue-261-m2-browser",
      revision_id: id,
      content_sha256: `${id}-hash`,
      based_on_revision_id: null,
      recorded_at: "2026-08-20T00:00:00Z",
      recorded_by: "issue-261-m2-browser",
    },
  };
}

type FixtureRecord = {
  record_id: string;
  table_id: string;
  current_revision: Record<string, unknown>;
  domain_binding: Record<string, unknown>;
};

const material = materialRevision(materialRevisionId, materialId, "M2 Materials reference steel");
const noCardMaterial = materialRevision(noCardMaterialRevisionId, noCardMaterialId, "M2 Start Modeling reference steel");

function recordRevision(id: string, aggregateId: string, name: string) {
  return {
    ...metadata(id, aggregateId),
    content: {
      table_revision_id: `${tableId}-r1`,
      name,
      external_key: "M2-STEEL",
      description: "Exact record used by the Materials search journey.",
      folder_id: null,
      folder_revision_id: null,
      values: [
        { attribute_definition_id: "material-class", attribute_definition_revision_id: "material-class-r1", data_type: "discrete", value: "metal" },
        { attribute_definition_id: "provider", attribute_definition_revision_id: "provider-r1", data_type: "text", value: "CMP reference" },
        { attribute_definition_id: "evidence-source", attribute_definition_revision_id: "evidence-source-r1", data_type: "text", value: "M2 fixture" },
      ],
    },
  };
}

function recordResponse(
  id: string,
  revision: Record<string, unknown>,
  boundMaterialId: string,
  boundMaterialRevisionId: string,
): FixtureRecord {
  return {
    record_id: id,
    table_id: tableId,
    current_revision: revision,
    domain_binding: {
      binding_id: `${id}-binding`,
      record_id: id,
      record_revision_id: id,
      kind: "material",
      object_id: boundMaterialId,
      revision_id: boundMaterialRevisionId,
      workbench_path: `/materials/${boundMaterialId}`,
    },
  };
}

const record = recordResponse(
  recordId,
  recordRevision(recordRevisionId, recordId, "M2 Materials reference steel"),
  materialId,
  materialRevisionId,
);
const noCardRecord = recordResponse(
  noCardRecordId,
  recordRevision(noCardRecordRevisionId, noCardRecordId, "M2 Start Modeling reference steel"),
  noCardMaterialId,
  noCardMaterialRevisionId,
);

function tableResponse(): Record<string, unknown> {
  return {
    table_id: tableId,
    current_revision: {
      ...metadata(`${tableId}-r1`, tableId),
      content: { key: "demo_material_records", name: "Materials M2 evidence table", description: "Issue #261 M2 browser fixture" },
    },
  };
}

function graphFor(selectedMaterialId: string, selectedMaterialRevisionId: string, selectedRecordId: string, selectedRecordRevisionId: string, includeCard: boolean) {
  const root = {
    record_id: selectedRecordId,
    record_revision_id: selectedRecordRevisionId,
    revision_no: 1,
    table_id: tableId,
    name: selectedMaterialId === materialId ? "M2 Materials reference steel" : "M2 Start Modeling reference steel",
    external_key: "M2-STEEL",
    domain_binding: {
      binding_id: `${selectedRecordId}-binding`,
      record_id: selectedRecordId,
      record_revision_id: selectedRecordRevisionId,
      kind: "material",
      object_id: selectedMaterialId,
      revision_id: selectedMaterialRevisionId,
      workbench_path: `/materials/${selectedMaterialId}`,
    },
  };
  const card = {
    ...root,
    record_id: "m2-card-record",
    record_revision_id: "m2-card-record-r1",
    name: "M2 OpenRadioss native card",
    domain_binding: {
      binding_id: "m2-card-binding",
      record_id: "m2-card-record",
      record_revision_id: "m2-card-record-r1",
      kind: "neutral_solver_card",
      object_id: cardId,
      revision_id: cardRevisionId,
      workbench_path: "/exports",
    },
  };
  return { root, nodes: includeCard ? [root, card] : [root], links: [] };
}

async function fulfillJson(route: Route, value: unknown, status = 200): Promise<void> {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(value) });
}

async function installFixture(page: Page): Promise<void> {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const requestPath = url.pathname;
    const selectedNoCard = requestPath.includes(noCardMaterialId) || requestPath.includes(noCardRecordId);
    const selectedMaterial = selectedNoCard ? noCardMaterial : material;
    const selectedRecord = selectedNoCard ? noCardRecord : record;
    const selectedMaterialId = selectedNoCard ? noCardMaterialId : materialId;
    const selectedMaterialRevisionId = selectedNoCard ? noCardMaterialRevisionId : materialRevisionId;
    const selectedRecordId = selectedNoCard ? noCardRecordId : recordId;
    const selectedRecordRevisionId = selectedNoCard ? noCardRecordRevisionId : recordRevisionId;

    if (requestPath.endsWith("/demo-identity/token")) {
      await fulfillJson(route, { access_token: "issue-261-m2-token", token_type: "Bearer", expires_in_seconds: 900 });
      return;
    }
    if (requestPath.endsWith("/catalog/explorer/tables")) {
      await fulfillJson(route, { items: [tableResponse()] });
      return;
    }
    if (requestPath.endsWith(`/catalog/explorer/tables/${tableId}/children`)) {
      await fulfillJson(route, { table: tableResponse(), folders: [], records: [record] });
      return;
    }
    if (requestPath.endsWith(`/catalog/tables/${tableId}/subsets`)) {
      await fulfillJson(route, { items: [] });
      return;
    }
    if (requestPath.endsWith(`/catalog/tables/${tableId}/attributes`)) {
      await fulfillJson(route, { items: [
        { attribute_definition_id: "material-class", table_id: tableId, current_revision: { content: { key: "material_class" } } },
        { attribute_definition_id: "provider", table_id: tableId, current_revision: { content: { key: "provider" } } },
        { attribute_definition_id: "evidence-source", table_id: tableId, current_revision: { content: { key: "evidence_source" } } },
      ] });
      return;
    }
    if (requestPath.endsWith(`/catalog/tables/${tableId}/layouts`)) {
      await fulfillJson(route, { items: [] });
      return;
    }
    if (requestPath.endsWith("/catalog/records:search")) {
      const payload = request.postDataJSON() as { text?: string | null } | null;
      await fulfillJson(route, payload?.text === "magnesium"
        ? { items: [], total_count: 0, offset: 0, limit: 50, facets: [] }
        : { items: [record], total_count: 1, offset: 0, limit: 50, facets: [
          { attribute_definition_id: "material-class", value: "metal", count: 1 },
          { attribute_definition_id: "provider", value: "CMP reference", count: 1 },
          { attribute_definition_id: "evidence-source", value: "M2 fixture", count: 1 },
        ] });
      return;
    }
    if (requestPath.endsWith(`/catalog/records/${selectedRecordId}/revisions`)) {
      await fulfillJson(route, { items: [selectedRecord.current_revision] });
      return;
    }
    if (requestPath.endsWith(`/catalog/records/${selectedRecordId}`)) {
      await fulfillJson(route, { ...selectedRecord, current_revision: selectedRecord.current_revision });
      return;
    }
    if (requestPath.includes(`/materials/${selectedMaterialId}/revisions`)) {
      await fulfillJson(route, { material_id: selectedMaterialId, revisions: [selectedMaterial] });
      return;
    }
    if (requestPath.endsWith(`/materials/${selectedMaterialId}`)) {
      await fulfillJson(route, { material: { material_id: selectedMaterialId, current_revision: selectedMaterial, links: { self: "", revisions: "", states: "" } }, states: [], property_sets: [] });
      return;
    }
    if (requestPath.includes("/catalog/workflow-explorer/")) {
      const includeCard = selectedMaterialId === materialId;
      await fulfillJson(route, graphFor(selectedMaterialId, selectedMaterialRevisionId, selectedRecordId, selectedRecordRevisionId, includeCard));
      return;
    }
    if (requestPath.includes("/catalog/domain-bindings:resolve")) {
      await fulfillJson(route, { binding_id: `${selectedMaterialId}-binding`, record_id: selectedRecordId, record_revision_id: selectedRecordRevisionId, kind: "material", object_id: selectedMaterialId, revision_id: selectedMaterialRevisionId, workbench_path: `/materials/${selectedMaterialId}` });
      return;
    }
    if (requestPath.startsWith("/api/v1/review-requests")) {
      await fulfillJson(route, { items: [] });
      return;
    }
    if (requestPath.includes(`/neutral-solver-cards/${cardId}/preview`)) {
      await route.fulfill({ status: 200, contentType: "text/plain", body: "/MAT/LAW36/1\nM2 exact card\n" });
      return;
    }
    if (requestPath.includes(`/neutral-solver-cards/${cardId}/mapping-report`)) {
      await fulfillJson(route, { exportable: true, report: { exportable: true, items: [] }, mapping_report_sha256: "m2-mapping-hash" });
      return;
    }
    if (requestPath.endsWith(`/neutral-solver-cards/${cardId}/download`)) {
      await route.fulfill({ status: 200, contentType: "text/plain", headers: { "Content-Disposition": 'attachment; filename="m2-exact-card.rad"' }, body: "/MAT/LAW36/1\nM2 exact card\n" });
      return;
    }
    if (requestPath.endsWith(`/neutral-solver-cards/${cardId}`)) {
      await fulfillJson(route, { solver_card_id: cardId, solver_material_id: 781, target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" }, current_revision: { ...metadata(cardRevisionId, cardId), content: { card_title: "M2 OpenRadioss native card", card_sha256: "m2-card-hash", mapping_report: { exportable: true, items: [] }, solver_material_id: 781, material_name: "M2 Materials reference steel", mapping_statuses: {} } } });
      return;
    }
    await fulfillJson(route, {});
  });
  await page.addInitScript(() => {
    window.localStorage.setItem("cmp.material-platform.api-config", JSON.stringify({ baseUrl: "/api/v1", accessToken: "issue-261-m2-token" }));
  });
}

async function saveScreenshot(page: Page, state: string, width: number, height: number): Promise<void> {
  if (!evidenceDirectory) return;
  const directory = join(evidenceDirectory, evidencePhase);
  await mkdir(directory, { recursive: true });
  await page.screenshot({ path: join(directory, `${state}-${width}x${height}.png`), fullPage: false });
}

async function openSearch(page: Page): Promise<void> {
  await page.goto("/materials");
  await expect.poll(() => new URL(page.url()).searchParams.get("table")).toBe(tableId);
  await page.getByRole("button", { name: "Filters", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Search materials" })).toBeVisible();
  await page.getByRole("textbox", { name: "Search materials" }).fill("M2-STEEL");
  await page.getByLabel("Material query").getByRole("button", { name: "Find", exact: true }).click();
  await expect(page.locator(".materials-results")).toHaveAttribute("aria-busy", "false");
  await expect(page.getByRole("row").filter({ hasText: "M2-STEEL" })).toBeVisible();
}

test("Materials ownership keeps exact search, card delivery, handoff, reload and fail-closed recovery", async ({ page }) => {
  test.setTimeout(180_000);
  await installFixture(page);
  const observedRequests: string[] = [];
  page.on("request", (request) => observedRequests.push(request.url()));

  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    await openSearch(page);
    await saveScreenshot(page, "search", viewport.width, viewport.height);

    const resultRow = page.getByRole("row").filter({ hasText: "M2-STEEL" });
    await resultRow.getByRole("button").click();
    await expect(page).toHaveURL(new RegExp(`/materials/${materialId}\\?record_id=${recordId}&record_revision_id=${recordRevisionId}&material_revision_id=${materialRevisionId}$`));
    await expect(page.getByRole("heading", { name: "M2 Materials reference steel", level: 1 })).toBeVisible();
    await page.reload();
    await expect(page).toHaveURL(new RegExp(`/materials/${materialId}\\?record_id=${recordId}&record_revision_id=${recordRevisionId}&material_revision_id=${materialRevisionId}$`));
    await expect(page.getByRole("heading", { name: "M2 Materials reference steel", level: 1 })).toBeVisible();
    await saveScreenshot(page, "detail", viewport.width, viewport.height);

    await page.goBack();
    await expect(page).toHaveURL(/\/materials\?q=M2-STEEL/);
    await expect(page.getByRole("textbox", { name: "Search materials" })).toHaveValue("M2-STEEL");
    await expect(page.getByRole("row").filter({ hasText: "M2-STEEL" })).toBeVisible();
    await page.getByRole("row").filter({ hasText: "M2-STEEL" }).getByRole("button").click();
    await expect(page).toHaveURL(new RegExp(`/materials/${materialId}\\?record_id=${recordId}&record_revision_id=${recordRevisionId}&material_revision_id=${materialRevisionId}$`));

    await page.getByRole("tab", { name: "CAE Cards", exact: true }).click();
    await expect(page.getByRole("button", { name: "Preview", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Preview", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/materials/${materialId}/cards/${cardId}\\?record_id=${recordId}&record_revision_id=${recordRevisionId}&material_revision_id=${materialRevisionId}$`));
    await expect(page.getByRole("heading", { name: "M2 OpenRadioss native card", level: 1 })).toBeVisible();
    await saveScreenshot(page, "card-preview", viewport.width, viewport.height);

    if (viewport.width === 1440) {
      await page.goto(`/materials/${materialId}?record_id=${recordId}&record_revision_id=missing&material_revision_id=${materialRevisionId}`);
      await expect(page.getByRole("alert")).toContainText("revision");
      await saveScreenshot(page, "exception-revision-mismatch", viewport.width, viewport.height);
      await page.goto("/materials");
      await expect(page.getByRole("heading", { name: "Materials", level: 1 })).toBeVisible();
    }
  }

  await page.goto(`/materials/${noCardMaterialId}?record_id=${noCardRecordId}&record_revision_id=${noCardRecordRevisionId}&material_revision_id=${noCardMaterialRevisionId}`);
  await expect(page.getByRole("button", { name: "Start Modeling", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Start Modeling", exact: true }).click();
  await expect(page).toHaveURL(
    `/modeling?stage=data&family=metal&material_id=${noCardMaterialId}&material_revision_id=${noCardMaterialRevisionId}`,
  );

  const download = page.waitForEvent("download");
  await page.goto(`/materials/${materialId}/cards/${cardId}?record_id=${recordId}&record_revision_id=${recordRevisionId}&material_revision_id=${materialRevisionId}`);
  await expect(page.getByRole("button", { name: "Download .rad", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Download .rad", exact: true }).click();
  expect((await download).suggestedFilename()).toBe("m2-exact-card.rad");
  expect(observedRequests.some((url) => url.includes(`/neutral-solver-cards/${cardId}/preview?revision_id=${cardRevisionId}`))).toBe(true);
  expect(observedRequests.some((url) => url.includes(`/neutral-solver-cards/${cardId}/download?revision_id=${cardRevisionId}`))).toBe(true);
  expect(observedRequests.some((url) => url.includes("/neutral-solver-cards/") && !url.includes(`revision_id=${cardRevisionId}`))).toBe(false);
});
