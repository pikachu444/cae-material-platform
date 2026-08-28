import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Locator, type Page, type Route } from "@playwright/test";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const evidenceDirectory = process.env.CMP_ISSUE342_EVIDENCE_DIR;
const fixtureDirectory = join(repositoryRoot, "fixtures", "schema-record-data", "source-v2-task1b", "technical");
const fixturePaths = [
  join(fixtureDirectory, "cmp-246-technical-dp780.json"),
  join(fixtureDirectory, "elastomer.json"),
  join(fixtureDirectory, "polymer.json"),
];
const evidenceViewports = [
  [1366, 768],
  [1440, 900],
  [1920, 1080],
  [2560, 1440],
  [3840, 2160],
] as const;
type EvidenceState =
  | "normal"
  | "empty"
  | "loading"
  | "error"
  | "upload-error"
  | "invalid-preview"
  | "valid-preview"
  | "save-error"
  | "saved";

async function computedControlStyle(locator: Locator) {
  return locator.evaluate((element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return {
      tag: element.tagName.toLowerCase(),
      class_name: element.getAttribute("class") ?? "",
      disabled: element instanceof HTMLButtonElement || element instanceof HTMLInputElement
        ? element.disabled
        : null,
      width: rect.width,
      height: rect.height,
      display: style.display,
      visibility: style.visibility,
      font_family: style.fontFamily,
      font_size: style.fontSize,
      font_weight: style.fontWeight,
      line_height: style.lineHeight,
      padding_top: style.paddingTop,
      padding_right: style.paddingRight,
      padding_bottom: style.paddingBottom,
      padding_left: style.paddingLeft,
      text_align: style.textAlign,
      align_items: style.alignItems,
      opacity: style.opacity,
    };
  });
}

const tableId = "34200000-0000-4000-8000-000000000101";
const tableRevisionId = "34200000-0000-4000-8000-000000000102";
const formatId = "34200000-0000-4000-8000-000000000103";
const formatRevisionId = "34200000-0000-4000-8000-000000000104";
const applicationId = "34200000-0000-4000-8000-000000000105";
const sourceArtifactId = "34200000-0000-4000-8000-000000000106";
const packageArtifactId = "34200000-0000-4000-8000-000000000107";
const uploadId = "34200000-0000-4000-8000-000000000108";
const recordIds = [
  "34200000-0000-4000-8000-000000000201",
  "34200000-0000-4000-8000-000000000202",
  "34200000-0000-4000-8000-000000000203",
];

const technicalFixtures = fixturePaths.map((path, index) => ({
  path,
  name: basename(path),
  bytes: readFileSync(path),
  recordName: [
    "DP780 technical data",
    "Elastomer technical data",
    "Polymer technical data",
  ][index],
  externalKey: [
    "CMP-246-TECH-DP780",
    "CMP-246-TECH-ELASTOMER",
    "CMP-246-TECH-POLYMER",
  ][index],
  family: ["steel", "elastomer", "polymer"][index],
}));

function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function revision<T>(id: string, aggregateId: string, content: T) {
  return {
    id,
    aggregate_id: aggregateId,
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:issue-342-browser:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-08-28T00:00:00Z",
    created_by: "issue-342-browser",
    change_reason: "Issue #342 browser regression",
    organization_id: "34200000-0000-4000-8000-000000000001",
    project_id: "34200000-0000-4000-8000-000000000002",
    classification: "internal",
    lifecycle_state: "published",
    content,
  };
}

const table = {
  table_id: tableId,
  current_revision: revision(tableRevisionId, tableId, {
    key: "issue342_technical_data",
    name: "Technical source-v2",
    description: "Synthetic Task1B technical records",
    data_category: "technical_data",
  }),
};

const technicalFormat = {
  format_id: formatId,
  format_revision_id: formatRevisionId,
  format_key: "cmp-246-source-v2",
  application_id: applicationId,
  application_revision_id: applicationId,
  application_source: {
    artifact_id: sourceArtifactId,
    file: "catalog-schema-bundle.manifest.json",
    pointer: "/applications/cmp-246-source-v2",
    sha256: "b".repeat(64),
  },
  schema: {
    artifact_id: sourceArtifactId,
    file: "record-schemas/technical-data-v2.json",
    pointer: "/technical-data",
    sha256: "c".repeat(64),
  },
  table: {
    id: tableId,
    revision_id: tableRevisionId,
    key: "issue342_technical_data",
    source_file: "record-schemas/technical-data-v2.json",
    source_pointer: "/technical-data",
    source_sha256: "c".repeat(64),
  },
  wrapper: "technical-data",
  attribute_bindings: [
    {
      pointer: "/technical-data/Material Information/Family",
      attribute_id: "34200000-0000-4000-8000-000000000301",
      attribute_revision_id: "34200000-0000-4000-8000-000000000302",
      attribute_key: "family",
      data_type: "text",
      source_unit: null,
      quantity_semantics: null,
      curve: null,
      section: "Material Information",
    },
    {
      pointer: "/technical-data/Material Information/Grade",
      attribute_id: "34200000-0000-4000-8000-000000000303",
      attribute_revision_id: "34200000-0000-4000-8000-000000000304",
      attribute_key: "grade",
      data_type: "text",
      source_unit: null,
      quantity_semantics: null,
      curve: null,
      section: "Material Information",
    },
    {
      pointer: "/technical-data/Data Information/Technical Data Record Name",
      attribute_id: "34200000-0000-4000-8000-000000000305",
      attribute_revision_id: "34200000-0000-4000-8000-000000000306",
      attribute_key: "record_name",
      data_type: "text",
      source_unit: null,
      quantity_semantics: null,
      curve: null,
      section: "Data Information",
    },
  ],
  link_type_revision_ids: [],
  unit_profile_revision_ids: [],
};

const previewFiles = technicalFixtures.map((fixture, index) => ({
  filename: fixture.name,
  sha256: sha256(fixture.bytes),
  size_bytes: fixture.bytes.byteLength,
  valid: true,
  warnings: [],
  errors: [],
  external_key: fixture.externalKey,
  record_id: recordIds[index],
  record_revision_id: `${recordIds[index].slice(0, -3)}401`,
  lifecycle: "DRAFT",
  record_name: fixture.recordName,
  fields: [
    {
      section: "Material Information",
      label: "Family",
      pointer: "/technical-data/Material Information/Family",
      kind: "text",
      value: fixture.family,
      unit: null,
      summary: null,
    },
    {
      section: "Data Information",
      label: "Technical Data Record Name",
      pointer: "/technical-data/Data Information/Technical Data Record Name",
      kind: "text",
      value: fixture.recordName,
      unit: null,
      summary: null,
    },
  ],
}));

const previewResponse = {
  $schema: "https://cmp.example/contracts/catalog/json-record-registration.schema.json",
  contract_version: "1.0.0",
  preview_token: "issue-342-preview-token",
  expires_at: "2026-08-28T10:00:00Z",
  package: {
    media_type: "application/zip",
    sha256: "d".repeat(64),
    artifact_id: packageArtifactId,
  },
  format_revision_id: formatRevisionId,
  detected_record_type: "technical_data",
  format: technicalFormat,
  valid: true,
  files: previewFiles,
};

const invalidPreviewResponse = {
  ...previewResponse,
  preview_token: "issue-342-invalid-preview-token",
  valid: false,
  files: [{
    ...previewFiles[0],
    valid: false,
    fields: [],
    errors: [{
      filename: technicalFixtures[0].name,
      code: "invalid-field",
      message: "Family must be one of the installed source-v2 values.",
      recovery: "Correct the Family value and preview again.",
      json_pointer: "/technical-data/Material Information/Family",
      line: 4,
      column: 11,
      byte_offset: null,
      severity: "error" as const,
    }],
  }],
};

const saveResponse = {
  batch_id: "34200000-0000-4000-8000-000000000401",
  replayed: false,
  package_sha256: previewResponse.package.sha256,
  lifecycle: "DRAFT",
  records: previewFiles.map((file, index) => ({
    record_id: recordIds[index],
    record_revision_id: file.record_revision_id,
    revision_no: 1,
    external_key: file.external_key,
  })),
  publication: { state: "DRAFT", allowed: false },
};

async function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: { "x-request-id": "issue-342-browser" },
    body: JSON.stringify(body),
  });
}

async function installAdministratorConfig(page: Page): Promise<void> {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "cmp.material-platform.api-config",
      JSON.stringify({ baseUrl: "/api/v1", accessToken: "issue-342-administrator-token" }),
    );
    window.sessionStorage.clear();
  });
}

async function assertDesktopGeometry(page: Page, capture: boolean): Promise<Array<Record<string, unknown>>> {
  const measurements: Array<Record<string, unknown>> = [];
  const originalDirectory = evidenceDirectory ? join(evidenceDirectory, "originals") : "";
  const cropDirectory = evidenceDirectory ? join(evidenceDirectory, "crops") : "";
  if (capture) {
    await mkdir(originalDirectory, { recursive: true });
    await mkdir(cropDirectory, { recursive: true });
  }
  for (const [width, height] of evidenceViewports) {
    await page.setViewportSize({ width, height });
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect(page.locator(".json-registration-steps")).toBeVisible();
    await expect(page.locator(".json-registration-files")).toBeVisible();
    await expect(page.locator(".json-registration-preview")).toBeVisible();
    const measurement = await page.evaluate(() => {
      const bounds = (selector: string) => {
        const element = document.querySelector(selector);
        const rect = element?.getBoundingClientRect();
        return rect
          ? { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
          : null;
      };
      return {
        viewport: { width: innerWidth, height: innerHeight },
        devicePixelRatio,
        visualViewportScale: visualViewport?.scale ?? null,
        document: {
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          clientHeight: document.documentElement.clientHeight,
          scrollHeight: document.documentElement.scrollHeight,
        },
        panes: {
          steps: bounds(".json-registration-steps"),
          files: bounds(".json-registration-files"),
          preview: bounds(".json-registration-preview"),
        },
        workspace: bounds(".json-registration-workspace"),
        previewFields: bounds(".json-registration-preview-fields"),
        saveRow: bounds(".json-registration-save-row"),
        addFiles: bounds(".json-registration-section-heading label[for='json-record-files']"),
        fileHeadingCells: Array.from(document.querySelectorAll(".json-registration-file-heading > span")).map((element) => {
          const rect = element.getBoundingClientRect();
          return { x: rect.x, width: rect.width };
        }),
        firstFileRowCells: Array.from(document.querySelectorAll(".json-registration-file-row:first-of-type > span")).map((element) => {
          const rect = element.getBoundingClientRect();
          return { x: rect.x, width: rect.width };
        }),
        surrounding: {
          recordTypeSelector: Boolean(document.querySelector("#catalog-record-type-selector")),
          searchPanel: bounds(".catalog-search-panel"),
          resultsPanel: bounds(".catalog-record-list"),
        },
      };
    });
    expect(measurement.devicePixelRatio).toBe(1);
    expect(measurement.visualViewportScale).toBe(1);
    expect(measurement.document.scrollWidth).toBe(measurement.document.clientWidth);
    expect(measurement.document.scrollHeight).toBe(measurement.document.clientHeight);
    expect(measurement.panes.steps?.width ?? 0).toBeLessThanOrEqual(416);
    if (width <= 1440) {
      expect(measurement.panes.files?.width ?? 0).toBeGreaterThanOrEqual(360);
      expect(measurement.panes.preview?.width ?? 0).toBeGreaterThanOrEqual(320);
      expect(measurement.addFiles?.height ?? 0).toBeLessThanOrEqual(44);
      for (const cells of [measurement.fileHeadingCells, measurement.firstFileRowCells]) {
        for (let index = 1; index < cells.length; index += 1) {
          const previous = cells[index - 1];
          const current = cells[index];
          expect(previous.x + previous.width).toBeLessThanOrEqual(current.x);
          expect(current.width).toBeGreaterThan(0);
        }
      }
    }
    if (width >= 1920) {
      expect(measurement.workspace?.width ?? 0).toBeGreaterThan(width - 128);
      expect(measurement.workspace?.height ?? 0).toBeGreaterThan(height * 0.5);
    }
    if (measurement.previewFields && measurement.saveRow) {
      expect(measurement.saveRow.y).toBeGreaterThanOrEqual(measurement.previewFields.y);
      expect(measurement.saveRow.y).toBeLessThanOrEqual(
        measurement.previewFields.y + measurement.previewFields.height + 160,
      );
    }
    measurements.push(measurement);
    if (capture) {
      const stem = `issue342-valid-preview-${width}x${height}`;
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: join(originalDirectory, `${stem}.png`), fullPage: false });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.locator(".application-menu-bar").screenshot({
        path: join(cropDirectory, `${stem}-header.png`),
      });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.locator(".json-registration-workspace").screenshot({
        path: join(cropDirectory, `${stem}-workspace.png`),
      });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.locator(".json-registration-files").screenshot({
        path: join(cropDirectory, `${stem}-controls.png`),
      });
    }
  }
  return measurements;
}

async function captureEvidenceState(page: Page, state: Exclude<EvidenceState, "valid-preview">): Promise<Array<Record<string, unknown>>> {
  if (!evidenceDirectory) return [];
  const originalDirectory = join(evidenceDirectory, "originals");
  await mkdir(originalDirectory, { recursive: true });
  const measurements: Array<Record<string, unknown>> = [];
  for (const [width, height] of evidenceViewports) {
    await page.setViewportSize({ width, height });
    await page.evaluate(() => window.scrollTo(0, 0));
    const measurement = await page.evaluate((stateName) => {
      const bounds = (selector: string) => {
        const element = document.querySelector(selector);
        const rect = element?.getBoundingClientRect();
        return rect
          ? { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
          : null;
      };
      return {
        state: stateName,
        viewport: { width: innerWidth, height: innerHeight },
        devicePixelRatio,
        visualViewportScale: visualViewport?.scale ?? null,
        document: {
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          clientHeight: document.documentElement.clientHeight,
          scrollHeight: document.documentElement.scrollHeight,
        },
        importPanel: bounds('[aria-label="Record import"]'),
        workspace: bounds(".json-registration-workspace"),
        panes: {
          steps: bounds(".json-registration-steps"),
          files: bounds(".json-registration-files"),
          preview: bounds(".json-registration-preview"),
        },
      };
    }, state);
    expect(measurement.document.scrollWidth).toBe(measurement.document.clientWidth);
    if (state !== "normal") {
      expect(measurement.document.scrollHeight).toBe(measurement.document.clientHeight);
    }
    measurements.push(measurement);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: join(originalDirectory, `issue342-${state}-${width}x${height}.png`),
      fullPage: false,
    });
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  return measurements;
}

test("registers three Task1B Technical JSON records through the live Administration flow", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await installAdministratorConfig(page);

  const uploadRequests: Array<Record<string, unknown>> = [];
  const previewRequests: Array<Record<string, unknown>> = [];
  const saveRequests: Array<Record<string, unknown>> = [];
  const unexpectedRequests: string[] = [];
  let uploadMode: "success" | "pending" | "error" = "success";
  let releasePendingUpload: (() => void) | null = null;
  let previewMode: "valid" | "invalid" = "valid";
  let saveMode: "success" | "error" = "success";
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path === "/api/v1/catalog/tables" && method === "GET") {
      return fulfillJson(route, { items: [table] });
    }
    if (path === "/api/v1/materials" && method === "GET") {
      return fulfillJson(route, {
        items: [],
        total_count: 0,
        offset: 0,
        limit: 100,
        facets: { material_classes: [], providers: [], evidence_sources: [] },
      });
    }
    if (path === `/api/v1/catalog/tables/${tableId}/attributes` && method === "GET") {
      return fulfillJson(route, { items: [] });
    }
    if (path === `/api/v1/catalog/tables/${tableId}/layouts` && method === "GET") {
      return fulfillJson(route, { items: [] });
    }
    if (path === `/api/v1/catalog/tables/${tableId}/folders` && method === "GET") {
      return fulfillJson(route, { items: [] });
    }
    if (path === `/api/v1/catalog/tables/${tableId}/subsets` && method === "GET") {
      return fulfillJson(route, { items: [] });
    }
    if (path === "/api/v1/catalog/records:search" && method === "POST") {
      return fulfillJson(route, {
        items: [],
        total_count: 0,
        offset: 0,
        limit: 50,
        facets: [],
      });
    }
    if (path === "/api/v1/uploads" && method === "POST") {
      uploadRequests.push(request.postDataJSON() as Record<string, unknown>);
      if (uploadMode === "pending") {
        await new Promise<void>((resolve) => {
          releasePendingUpload = resolve;
        });
      }
      if (uploadMode === "error") {
        return fulfillJson(route, { detail: "Artifact upload failed. Retry the upload." }, 500);
      }
      return fulfillJson(route, {
        upload: { upload_id: uploadId, expected_part_count: 1, part_size_bytes: 1024 * 1024 },
        upload_capability: "issue-342-upload-capability",
      });
    }
    if (path === `/api/v1/uploads/${uploadId}/parts/1` && method === "PUT") {
      return fulfillJson(route, {
        upload_id: uploadId,
        expected_part_count: 1,
        part_size_bytes: 1024 * 1024,
      });
    }
    if (path === `/api/v1/uploads/${uploadId}:complete` && method === "POST") {
      return fulfillJson(route, { available_artifact_id: packageArtifactId });
    }
    if (path === "/api/v1/catalog/json-record-registrations:preview" && method === "POST") {
      previewRequests.push(request.postDataJSON() as Record<string, unknown>);
      if (previewMode === "invalid") return fulfillJson(route, invalidPreviewResponse);
      return fulfillJson(route, previewResponse);
    }
    if (path === `/api/v1/catalog/json-record-registrations/${previewResponse.preview_token}:save` && method === "POST") {
      saveRequests.push(request.postDataJSON() as Record<string, unknown>);
      if (saveMode === "error") {
        return fulfillJson(route, { detail: "Save failed. Retry Save." }, 500);
      }
      return fulfillJson(route, saveResponse);
    }

    unexpectedRequests.push(`${method} ${path}${url.search}`);
    return fulfillJson(route, { detail: `Unhandled issue #342 route ${path}` }, 501);
  });

  const evidenceInventory: Array<{ state: EvidenceState; viewports: Array<Record<string, unknown>> }> = [];
  const recordEvidence = (state: EvidenceState, viewports: Array<Record<string, unknown>>) => {
    if (evidenceDirectory) evidenceInventory.push({ state, viewports });
  };
  const pickerFile = (fixture: (typeof technicalFixtures)[number]) => ({
    name: fixture.name,
    mimeType: "application/json",
    buffer: fixture.bytes,
  });
  const openImport = async () => {
    const command = page.getByRole("button", { name: "Import records", exact: true });
    await expect(command).toHaveCount(1);
    await expect(command).toBeEnabled();
    await command.click();
    const panel = page.getByRole("region", { name: "Record import", exact: true });
    await expect(panel.getByRole("heading", { name: "Import records", exact: true })).toBeVisible();
    await expect(panel.getByRole("combobox", { name: "Record type", exact: true })).toHaveCount(0);
    await expect(panel.locator("select")).toHaveCount(0);
    await expect(panel.getByText(/Format revision|Classification|Technical details/i)).toHaveCount(0);
    await expect(page.locator("#catalog-record-type-selector")).toHaveCount(0);
    await expect(page.locator(".catalog-search-panel")).toHaveCount(0);
    await expect(page.locator(".catalog-record-list")).toHaveCount(0);
    await expect(page.locator(".catalog-datasheet")).toHaveCount(0);
    return panel;
  };
  const closeImport = async (panel: ReturnType<typeof page.getByRole>) => {
    await panel.getByRole("button", { name: "Close", exact: true }).click();
    await expect(page.locator("#catalog-record-type-selector")).toBeVisible();
    await expect(page.locator(".catalog-search-panel")).toBeVisible();
    await expect(page.locator(".catalog-record-list")).toBeVisible();
  };

  await page.goto("/administration/records");
  await expect(page.locator("#catalog-record-type-selector")).toBeVisible();
  await expect(page.locator(".catalog-search-panel")).toBeVisible();
  await expect(page.locator(".catalog-record-list")).toBeVisible();
  recordEvidence("normal", await captureEvidenceState(page, "normal"));

  let registration = await openImport();
  const picker = registration.getByLabel("Add files");
  await expect(picker).toHaveAttribute("accept", /json/);
  await expect(picker).not.toHaveAttribute("accept", /zip/i);
  await expect(registration.getByRole("row")).toHaveCount(0);
  recordEvidence("empty", await captureEvidenceState(page, "empty"));
  await closeImport(registration);

  registration = await openImport();
  uploadMode = "pending";
  await registration.getByLabel("Add files").setInputFiles(pickerFile(technicalFixtures[0]));
  await expect(registration.getByText(technicalFixtures[0].name, { exact: true })).toBeVisible();
  await expect(registration.getByText("Uploading…", { exact: true })).toBeVisible();
  await expect.poll(() => releasePendingUpload !== null).toBe(true);
  recordEvidence("loading", await captureEvidenceState(page, "loading"));
  uploadMode = "success";
  releasePendingUpload?.();
  releasePendingUpload = null;
  await expect(registration.getByRole("button", { name: "Preview", exact: true })).toBeEnabled();
  await closeImport(registration);

  registration = await openImport();
  await registration.getByLabel("Add files").setInputFiles([
    pickerFile(technicalFixtures[0]),
    { name: "records.csv", mimeType: "text/csv", buffer: Buffer.from("Family,Grade\nsteel,DP780\n") },
  ]);
  await expect(
    registration.getByText("Keep the selected files. Use one source family per import.", { exact: true }),
  ).toBeVisible();
  recordEvidence("error", await captureEvidenceState(page, "error"));
  await closeImport(registration);

  registration = await openImport();
  uploadMode = "error";
  const uploadErrorCount = uploadRequests.length;
  await registration.getByLabel("Add files").setInputFiles(pickerFile(technicalFixtures[0]));
  await expect.poll(() => uploadRequests.length).toBe(uploadErrorCount + 1);
  await expect(registration.getByText("Artifact upload failed. Retry the upload.", { exact: true })).toBeVisible();
  const uploadRetry = registration.getByRole("button", { name: "Retry", exact: true });
  await expect(uploadRetry).toBeEnabled();
  recordEvidence("upload-error", await captureEvidenceState(page, "upload-error"));
  uploadMode = "success";
  await uploadRetry.click();
  await expect.poll(() => uploadRequests.length).toBe(uploadErrorCount + 2);
  await expect(registration.getByRole("button", { name: "Preview", exact: true })).toBeEnabled();
  await closeImport(registration);

  registration = await openImport();
  previewMode = "invalid";
  await registration.getByLabel("Add files").setInputFiles(pickerFile(technicalFixtures[0]));
  await expect(registration.getByRole("button", { name: "Preview", exact: true })).toBeEnabled();
  const invalidPreviewCount = previewRequests.length;
  await registration.getByRole("button", { name: "Preview", exact: true }).click();
  await expect.poll(() => previewRequests.length).toBe(invalidPreviewCount + 1);
  await expect(registration.getByText("invalid-field", { exact: true })).toBeVisible();
  await expect(
    registration.getByText(
      /cmp-246-technical-dp780\.json.*\/technical-data\/Material Information\/Family.*Cause: Family must be one of the installed source-v2 values\..*Recovery: Correct the Family value and preview again\./,
    ),
  ).toBeVisible();
  recordEvidence("invalid-preview", await captureEvidenceState(page, "invalid-preview"));
  previewMode = "valid";
  await registration.getByRole("button", { name: "Retry", exact: true }).click();
  await expect.poll(() => previewRequests.length).toBe(invalidPreviewCount + 2);
  await expect(registration.getByText("Technical data", { exact: true })).toBeVisible();
  await closeImport(registration);

  registration = await openImport();
  previewMode = "valid";
  const validUploadCount = uploadRequests.length;
  await registration.getByLabel("Add files").setInputFiles(technicalFixtures.map(pickerFile));
  for (const fixture of technicalFixtures) {
    await expect(registration.getByText(fixture.name, { exact: true })).toBeVisible();
  }
  await expect.poll(() => uploadRequests.length).toBe(validUploadCount + 1);
  const validUploadRequest = uploadRequests[uploadRequests.length - 1];
  expect(validUploadRequest).toMatchObject({
    media_type: "application/zip",
    original_filename: "json-record-registration.zip",
  });

  const surroundingSurface = await page.evaluate(() => {
    const rendered = (selector: string) => {
      const element = document.querySelector(selector);
      if (!element) return false;
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    };
    return {
      recordTypeSelectorVisible: rendered("#catalog-record-type-selector"),
      searchPanelVisible: rendered(".catalog-search-panel"),
      resultsPanelVisible: rendered(".catalog-record-list"),
    };
  });
  expect(surroundingSurface).toEqual({
    recordTypeSelectorVisible: false,
    searchPanelVisible: false,
    resultsPanelVisible: false,
  });
  console.info(`[issue342] JSON panel surrounding surfaces: ${JSON.stringify(surroundingSurface)}`);

  const previewCommand = registration.getByRole("button", { name: "Preview", exact: true });
  await expect(previewCommand).toBeEnabled();
  const previewControlStyle = await computedControlStyle(previewCommand);
  const validPreviewCount = previewRequests.length;
  await previewCommand.click();
  await expect.poll(() => previewRequests.length).toBe(validPreviewCount + 1);
  const validPreviewRequest = previewRequests[previewRequests.length - 1];
  expect(validPreviewRequest).toMatchObject({ classification: "internal" });
  expect((validPreviewRequest.files as unknown[]).length).toBe(1);
  await expect(registration.getByText("3 selected · 3 valid", { exact: true })).toBeVisible();
  await expect(registration.getByRole("button", { name: "Preview", exact: true })).toHaveCount(0);
  await expect(registration.getByText("Detected content", { exact: true })).toHaveCount(1);
  await expect(registration.getByText("Technical data", { exact: true })).toHaveCount(1);
  await expect(registration.getByRole("row", { name: /cmp-246-technical-dp780\.json, DP780 technical data/ })).toBeVisible();
  await expect(
    registration.getByLabel("Record preview").getByText("DP780 technical data", { exact: true }),
  ).toBeVisible();

  const reason = registration.getByLabel("Reason for change");
  await expect(reason).toHaveAttribute("required", "");
  const save = registration.getByRole("button", { name: "Save", exact: true });
  await expect(save).toBeDisabled();

  const componentStyleInventory = {
    route: "/administration/records",
    workspace: "Import records valid preview",
    viewport: { width: 1440, height: 900 },
    browser_zoom: "100%",
    device_pixel_ratio: 1,
    controls: {
      add_files_trigger: await computedControlStyle(
        registration.locator(".json-registration-section-heading label.ux-button"),
      ),
      native_file_input: await computedControlStyle(registration.getByLabel("Add files")),
      preview_secondary: previewControlStyle,
      close_tertiary: await computedControlStyle(
        registration.locator(".json-registration-steps-header button.ux-button"),
      ),
      reason_input: await computedControlStyle(reason),
      save_disabled_primary: await computedControlStyle(save),
    },
    visible_select: null,
    notes: [
      "The native file input is visually hidden; Add files is the visible shared button trigger.",
      "The import workspace has no visible select control because file bytes drive JSON versus tabular routing and the server resolves the installed exact format.",
    ],
  };

  const measurements = await assertDesktopGeometry(page, Boolean(evidenceDirectory));
  recordEvidence("valid-preview", measurements);
  await page.setViewportSize({ width: 1440, height: 900 });
  if (evidenceDirectory) {
    await writeFile(
      join(evidenceDirectory, "valid-preview-measurements.json"),
      `${JSON.stringify({ surroundingSurface, viewports: measurements }, null, 2)}\n`,
      "utf8",
    );
  }

  await reason.fill("Approved Task1B technical source registration");
  await expect(save).toBeEnabled();
  if (evidenceDirectory) {
    await writeFile(
      join(evidenceDirectory, "component-style-inventory.json"),
      `${JSON.stringify({
        ...componentStyleInventory,
        controls: {
          ...componentStyleInventory.controls,
          save_enabled_primary: await computedControlStyle(save),
        },
      }, null, 2)}\n`,
      "utf8",
    );
  }
  saveMode = "error";
  const saveErrorCount = saveRequests.length;
  await save.click();
  await expect.poll(() => saveRequests.length).toBe(saveErrorCount + 1);
  await expect(registration.getByText("Save failed. Retry Save.", { exact: true })).toBeVisible();
  await expect(registration.getByRole("row", { name: /cmp-246-technical-dp780\.json, DP780 technical data/ })).toBeVisible();
  await expect(
    registration.getByLabel("Record preview").getByText("DP780 technical data", { exact: true }),
  ).toBeVisible();
  await expect(save).toBeEnabled();
  recordEvidence("save-error", await captureEvidenceState(page, "save-error"));

  saveMode = "success";
  await save.click();
  await expect.poll(() => saveRequests.length).toBe(saveErrorCount + 2);
  await expect(registration.getByText("Draft records saved.", { exact: true })).toBeVisible();
  await expect(registration.getByRole("link", { name: "JSON", exact: true })).toHaveCount(0);
  await expect(registration.getByRole("link", { name: "CSV", exact: true })).toHaveCount(0);
  recordEvidence("saved", await captureEvidenceState(page, "saved"));

  if (evidenceDirectory) {
    const capturedOriginalCount = evidenceInventory.reduce((count, item) => count + item.viewports.length, 0);
    expect(evidenceInventory.map((item) => item.state)).toEqual([
      "normal",
      "empty",
      "loading",
      "error",
      "upload-error",
      "invalid-preview",
      "valid-preview",
      "save-error",
      "saved",
    ]);
    expect(capturedOriginalCount).toBe(45);
    await writeFile(
      join(evidenceDirectory, "state-inventory.json"),
      `${JSON.stringify({
        states: evidenceInventory,
        viewports: evidenceViewports.map(([width, height]) => ({ width, height })),
        original_count: capturedOriginalCount,
      }, null, 2)}\n`,
      "utf8",
    );
  }

  await registration.getByRole("button", { name: "Open records", exact: true }).click();
  await expect(page).toHaveURL(/\/administration\/records\?table_id=[^&]+&table_revision_id=[^&]+$/);
  const savedRoute = new URL(page.url());
  expect(savedRoute.pathname).toBe("/administration/records");
  expect(savedRoute.searchParams.get("table_id")).toBe(tableId);
  expect(savedRoute.searchParams.get("table_revision_id")).toBe(tableRevisionId);
  expect(savedRoute.searchParams.has("record_id")).toBe(false);
  expect(savedRoute.searchParams.has("record_revision_id")).toBe(false);
  expect(savedRoute.searchParams.has("revision_id")).toBe(false);

  await page.reload();
  await expect(page).toHaveURL(savedRoute.toString());
  await expect(page.getByRole("button", { name: "Import records", exact: true })).toBeVisible();
  await expect(page.locator(".catalog-datasheet")).toHaveCount(0);
  await expect(page.locator(".catalog-record-list")).toContainText("Technical source-v2");
  expect(unexpectedRequests).toEqual([]);
});
