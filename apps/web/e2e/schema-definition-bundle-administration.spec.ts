import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page, type Route } from "@playwright/test";

const evidenceDirectory = process.env.CMP_SCHEMA_BUNDLE_EVIDENCE_DIR;
const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const bundleFixture = join(
  repositoryRoot,
  "contracts/examples/positive/schema-definition-bundle-many.json",
);
const artifactId = "20800000-0000-4000-8000-000000000001";
const applicationId = "20800000-0000-4000-8000-000000000002";
const bundleBytes = readFileSync(bundleFixture);
const sourceSha256 = createHash("sha256").update(bundleBytes).digest("hex");
const planFingerprint = "b".repeat(64);
const longKey = `representative_response_${"long_identity_".repeat(12)}end`;

const actionDefinitions = [
  ["database", "synthetic_engineering", "create"],
  ["profile", "synthetic_materials", "no-op"],
  ["table", "curves", "create"],
  ["attribute", "curve_id", "create"],
  ["attribute", "test_id", "create"],
  ["attribute", "stress_strain_curve", "create"],
  ["table", "materials", "update"],
  ["attribute", "material_code", "no-op"],
  ["attribute", "supplier", "update"],
  ["attribute", longKey, "update"],
  ["layout", "engineering_datasheet", "update"],
  ["table", "tensile_tests", "create"],
  ["link_type", "curve_tensile_test", "create"],
] as const;

const sourceArtifact = {
  artifact_id: artifactId,
  organization_id: "20400000-0000-4000-8000-000000000001",
  project_id: "20400000-0000-4000-8000-000000000002",
  classification: "internal",
  media_type: "application/vnd.cmp.catalog-schema-definition-bundle+json",
  size_bytes: bundleBytes.length,
  sha256: sourceSha256,
};

const plan = {
  $schema: "https://cmp.example/contracts/catalog/schema-definition-plan.schema.json",
  contract_version: "1.0.0",
  source_artifact: sourceArtifact,
  bundle: {
    bundle_key: "synthetic_dependency_chain",
    bundle_version: "1.0.0",
    scope: {
      organization_id: sourceArtifact.organization_id,
      project_id: sourceArtifact.project_id,
      classification: "internal",
    },
    database_key: "synthetic_engineering",
    profile_key: "synthetic_materials",
    record_schema_count: 3,
    dependency_order: ["curves", "materials", "tensile_tests"],
  },
  catalog_snapshot_fingerprint: "c".repeat(64),
  plan_fingerprint: planFingerprint,
  valid: true,
  action_counts: { create: 7, update: 4, "no-op": 2, conflict: 0, error: 0 },
  actions: actionDefinitions.map(([targetType, externalKey, disposition], index) => ({
    sequence: index + 1,
    disposition,
    target_type: targetType,
    external_key: externalKey,
    parent_external_key:
      targetType === "attribute" || targetType === "layout" ? "materials" : null,
    current:
      disposition === "create"
        ? null
        : {
            id: `20800000-0000-4000-8000-${String(index + 100).padStart(12, "0")}`,
            revision_id: `20800000-0000-4000-8000-${String(index + 200).padStart(12, "0")}`,
            content_hash: "d".repeat(64),
            published: true,
          },
    projected: { key: externalKey, name: externalKey.replaceAll("_", " ") },
    reason_codes: [
      disposition === "create"
        ? "target_absent"
        : disposition === "update"
          ? "content_changed"
          : "content_identical",
    ],
  })),
  diagnostics: [],
  mutations_applied: false,
  delete_missing: false,
  write_set: [],
};

const application = {
  $schema:
    "https://cmp.example/contracts/catalog/schema-definition-bundle-application.schema.json",
  contract_version: "1.0.0",
  application_id: applicationId,
  bundle_id: "20800000-0000-4000-8000-000000000003",
  bundle_key: "synthetic_dependency_chain",
  bundle_version: "1.0.0",
  classification: "internal",
  source_artifact: sourceArtifact,
  plan_fingerprint: planFingerprint,
  before_snapshot_fingerprint: "c".repeat(64),
  after_snapshot_fingerprint: "e".repeat(64),
  results: plan.actions
    .filter((action) => action.target_type !== "bundle")
    .map((action, index) => ({
      sequence: index + 1,
      disposition: action.disposition,
      target_type: action.target_type,
      external_key: action.external_key,
      parent_external_key: action.parent_external_key,
      aggregate_id: `20800000-0000-4000-8000-${String(index + 300).padStart(12, "0")}`,
      revision_id: `20800000-0000-4000-8000-${String(index + 400).padStart(12, "0")}`,
      content_hash: "f".repeat(64),
      published: true,
      source_schema_id: `urn:cmp:catalog-schema:${action.external_key}:1.0.0`,
      source_schema_version: "1.0.0",
      source_pointer: `/record_schemas/${Math.min(index, 2)}`,
    })),
  mutations_applied: true,
  delete_missing: false,
  applied_at: "2026-08-13T00:00:00Z",
  applied_by: "20800000-0000-4000-8000-000000000004",
  idempotency_key: "schema-bundle-playwright",
};

function fulfillJson(route: Route, body: unknown, status = 200, headers: Record<string, string> = {}) {
  return route.fulfill({
    status,
    contentType: "application/json",
    headers: { "x-request-id": "issue-208-browser", ...headers },
    body: JSON.stringify(body),
  });
}

async function captureFiveViewports(page: Page): Promise<void> {
  if (!evidenceDirectory) return;
  await mkdir(evidenceDirectory, { recursive: true });
  for (const [width, height] of [
    [1366, 768],
    [1440, 900],
    [1920, 1080],
    [2560, 1440],
    [3840, 2160],
  ] as const) {
    await page.setViewportSize({ width, height });
    await expect(page.getByRole("heading", { name: "Change plan" })).toBeVisible();
    const name = `administration-schema-bundle-plan-${width}x${height}`;
    await page.screenshot({ path: join(evidenceDirectory, `${name}.png`) });
    await page.locator(".application-menu-bar").screenshot({
      path: join(evidenceDirectory, `${name}-header-crop.png`),
    });
    await page.locator(".administration-taskbar").screenshot({
      path: join(evidenceDirectory, `${name}-navigator-crop.png`),
    });
    await page.locator(".schema-bundle-plan").screenshot({
      path: join(evidenceDirectory, `${name}-table-crop.png`),
    });
    await page.locator(".schema-bundle-source").screenshot({
      path: join(evidenceDirectory, `${name}-form-crop.png`),
    });
    const measurement = await page.evaluate(() => {
      const rect = (selector: string) => {
        const value = document.querySelector(selector)?.getBoundingClientRect();
        return value
          ? { x: value.x, y: value.y, width: value.width, height: value.height }
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
        shell: rect(".application-shell"),
        administration: rect(".administration-workspace"),
        navigator: rect(".administration-taskbar"),
        source: rect(".schema-bundle-source"),
        plan: rect(".schema-bundle-plan"),
        detail: rect(".schema-bundle-detail"),
        table: rect(".schema-bundle-table"),
      };
    });
    expect(measurement.visualViewportScale).toBe(1);
    expect(measurement.document.scrollWidth).toBe(measurement.document.clientWidth);
    await writeFile(
      join(evidenceDirectory, `${name}.measurements.json`),
      `${JSON.stringify(measurement, null, 2)}\n`,
      "utf8",
    );
  }
}

test("Administrator uploads, plans, confirms, applies, restores, and checksum-verifies one bundle", async ({
  page,
}) => {
  test.setTimeout(120_000);
  let productRole: "administrator" | "reviewer" = "administrator";
  let applyBody: Record<string, unknown> | null = null;
  let readBackCount = 0;
  const exportedBytes = Buffer.from(JSON.stringify({ bundle_key: "synthetic_dependency_chain" }));
  const exportDigest = createHash("sha256").update(exportedBytes).digest();
  const exportSha256 = exportDigest.toString("hex");

  await page.addInitScript(() => {
    window.localStorage.setItem(
      "cmp.material-platform.api-config",
      JSON.stringify({ baseUrl: "/api/v1", accessToken: "issue-208-browser-token" }),
    );
  });
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/product-access/me") {
      return fulfillJson(route, {
        product_role: productRole,
        feature_grants:
          productRole === "administrator" ? ["schema_configuration", "catalog_edit"] : [],
        legacy_compatible: false,
      });
    }
    if (path === "/api/v1/uploads" && request.method() === "POST") {
      return fulfillJson(
        route,
        {
          upload: {
            upload_id: "20800000-0000-4000-8000-000000000010",
            organization_id: sourceArtifact.organization_id,
            project_id: sourceArtifact.project_id,
            classification: "internal",
            state: "open",
            original_filename: "schema-definition-bundle-many.json",
            media_type: sourceArtifact.media_type,
            expected_size_bytes: Number(request.postDataJSON().expected_size_bytes),
            expected_sha256: request.postDataJSON().expected_sha256,
            part_size_bytes: Number(request.postDataJSON().expected_size_bytes),
            expected_part_count: 1,
            test_run_revision_id: null,
            raw_asset_id: null,
          },
          upload_capability: "x".repeat(32),
        },
        201,
      );
    }
    if (/\/api\/v1\/uploads\/[^/]+\/parts\/1$/.test(path)) {
      return fulfillJson(route, { state: "open" });
    }
    if (/\/api\/v1\/uploads\/[^/]+:complete$/.test(path)) {
      return fulfillJson(route, {
        upload: { state: "completed" },
        raw_asset: {
          raw_asset_id: "20800000-0000-4000-8000-000000000011",
          organization_id: sourceArtifact.organization_id,
          project_id: sourceArtifact.project_id,
          classification: "internal",
          sha256: sourceSha256,
          size_bytes: sourceArtifact.size_bytes,
          media_type: sourceArtifact.media_type,
          original_filename: "schema-definition-bundle-many.json",
          storage_state: "staged_verified",
        },
        available_artifact_id: artifactId,
      });
    }
    if (path === "/api/v1/catalog/schema-definition-bundles:plan") {
      expect(request.postDataJSON()).toEqual({
        artifact_id: artifactId,
        artifact_sha256: sourceSha256,
      });
      return fulfillJson(route, plan);
    }
    if (path === "/api/v1/catalog/schema-definition-bundles:apply") {
      applyBody = request.postDataJSON() as Record<string, unknown>;
      return fulfillJson(route, application, 201, {
        location: `/api/v1/catalog/schema-definition-bundle-applications/${applicationId}`,
      });
    }
    if (path.endsWith(`/schema-definition-bundle-applications/${applicationId}`)) {
      readBackCount += 1;
      return fulfillJson(route, application);
    }
    if (path.endsWith("/schema-definition-bundles/synthetic_dependency_chain:export")) {
      return route.fulfill({
        status: 200,
        headers: {
          "content-type": "application/vnd.cmp.catalog-schema-definition-bundle+json",
          etag: `"sha256:${exportSha256}"`,
          digest: `sha-256=${exportDigest.toString("base64")}`,
          "x-cmp-bundle-application-id": applicationId,
          "x-cmp-source-artifact-id": artifactId,
          "x-cmp-source-artifact-sha256": sourceSha256,
          "x-request-id": "issue-208-export",
        },
        body: exportedBytes,
      });
    }
    return fulfillJson(route, { detail: `Unhandled browser fixture route ${path}` }, 501);
  });

  await page.goto("/administration/schema-bundles");
  await expect(page.getByRole("list", { name: "Format definition workflow", exact: true })).toBeVisible();
  await page.getByLabel("Definition bundle").setInputFiles(bundleFixture);
  await expect(page.getByText("synthetic_dependency_chain", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Upload and plan" }).click();
  await expect(page.getByText("13 actions", { exact: true })).toBeVisible();

  const firstRow = page.getByRole("button", { name: "synthetic_engineering", exact: true });
  await firstRow.focus();
  await page.keyboard.press("End");
  await expect(page.getByRole("button", { name: "curve_tensile_test", exact: true })).toBeFocused();
  await expect(page.getByRole("button", { name: longKey, exact: true })).toHaveAttribute(
    "title",
    longKey,
  );

  await firstRow.scrollIntoViewIfNeeded();
  await firstRow.click();
  await page.locator(".schema-bundle-table-scroll").evaluate((element) => {
    element.scrollTop = 0;
    element.scrollLeft = 0;
  });

  await captureFiveViewports(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("button", { name: "Review exact plan" }).click();
  await expect(page.getByText(planFingerprint, { exact: true })).toBeVisible();
  if (evidenceDirectory) {
    await page.locator(".schema-bundle-detail").evaluate((element) => {
      element.scrollTop = element.scrollHeight;
    });
    await page.screenshot({
      path: join(evidenceDirectory, "administration-schema-bundle-confirmation-1440x900.png"),
    });
  }
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Apply exact plan" }).click();
  await expect(page.getByText("Exact application read back", { exact: true })).toBeVisible();
  expect(applyBody).toEqual({
    artifact_id: artifactId,
    artifact_sha256: sourceSha256,
    plan_fingerprint: planFingerprint,
    delete_missing: false,
  });
  expect(applyBody).not.toHaveProperty("actions");
  expect(readBackCount).toBe(1);

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export verified source" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("synthetic_dependency_chain-1.0.0.json");
  await expect(page.getByText(`synthetic_dependency_chain-1.0.0.json · ${exportSha256}`, { exact: true })).toBeVisible();
  if (evidenceDirectory) {
    await page.screenshot({
      path: join(evidenceDirectory, "administration-schema-bundle-applied-1440x900.png"),
    });
  }

  await page.reload();
  await expect(page.getByText("Exact application read back", { exact: true })).toBeVisible();
  expect(readBackCount).toBe(2);

  productRole = "reviewer";
  await page.reload();
  await expect(page.getByRole("alert")).toContainText("Administrator access is required.");
  await expect(page.getByLabel("Definition bundle")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Apply/ })).toHaveCount(0);
});
