import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./api";
import {
  SchemaDefinitionBundleAdmin,
  inspectSchemaDefinitionBundleFile,
  inspectSchemaDefinitionBundleFiles,
} from "./schema-definition-bundle-admin";
import type {
  SchemaDefinitionBundleApplication,
  SchemaDefinitionBundlePlan,
} from "./types";

const artifactId = "20800000-0000-4000-8000-000000000001";
const applicationId = "20800000-0000-4000-8000-000000000002";
const sha256 = "a".repeat(64);
const planFingerprint = "b".repeat(64);
const longKey = `long_schema_${"identity_".repeat(18)}end`;

const plan: SchemaDefinitionBundlePlan = {
  $schema: "https://cmp.example/contracts/catalog/schema-definition-plan.schema.json",
  contract_version: "1.0.0",
  source_artifact: {
    artifact_id: artifactId,
    organization_id: "20800000-0000-4000-8000-000000000003",
    project_id: "20800000-0000-4000-8000-000000000004",
    classification: "internal",
    media_type: "application/vnd.cmp.catalog-schema-definition-bundle+json",
    size_bytes: 512,
    sha256,
  },
  bundle: {
    bundle_key: "synthetic_dependency_chain",
    bundle_version: "1.0.0",
    scope: {
      organization_id: "20800000-0000-4000-8000-000000000003",
      project_id: "20800000-0000-4000-8000-000000000004",
      classification: "internal",
    },
    database_key: "synthetic_engineering",
    profile_key: "synthetic_materials",
    record_schema_count: 2,
    unit_profile_count: 0,
    dependency_order: ["materials", longKey],
  },
  catalog_snapshot_fingerprint: "c".repeat(64),
  plan_fingerprint: planFingerprint,
  valid: true,
  action_counts: { create: 1, update: 1, "no-op": 0, conflict: 0, error: 0 },
  actions: [
    {
      sequence: 1,
      disposition: "create",
      target_type: "table",
      external_key: "materials",
      parent_external_key: "synthetic_materials",
      current: null,
      projected: { key: "materials", name: "Synthetic materials" },
      reason_codes: ["target_absent"],
    },
    {
      sequence: 2,
      disposition: "update",
      target_type: "attribute",
      external_key: longKey,
      parent_external_key: "materials",
      current: {
        id: "20800000-0000-4000-8000-000000000005",
        revision_id: "20800000-0000-4000-8000-000000000006",
        content_hash: "d".repeat(64),
        published: true,
      },
      projected: { key: longKey, name: "Long synthetic field" },
      reason_codes: ["content_changed"],
    },
  ],
  diagnostics: [],
  mutations_applied: false,
  delete_missing: false,
  write_set: [],
};

const application: SchemaDefinitionBundleApplication = {
  $schema:
    "https://cmp.example/contracts/catalog/schema-definition-bundle-application.schema.json",
  contract_version: "1.0.0",
  application_id: applicationId,
  bundle_id: "20800000-0000-4000-8000-000000000007",
  bundle_key: "synthetic_dependency_chain",
  bundle_version: "1.0.0",
  classification: "internal",
  source_artifact: plan.source_artifact,
  plan_fingerprint: planFingerprint,
  before_snapshot_fingerprint: "c".repeat(64),
  after_snapshot_fingerprint: "e".repeat(64),
  results: [
    {
      sequence: 1,
      disposition: "create",
      target_type: "table",
      external_key: "materials",
      parent_external_key: "synthetic_materials",
      aggregate_id: "20800000-0000-4000-8000-000000000008",
      revision_id: "20800000-0000-4000-8000-000000000009",
      content_hash: "f".repeat(64),
      published: true,
      source_schema_id: "urn:cmp:catalog-schema:materials:1.0.0",
      source_schema_version: "1.0.0",
      source_pointer: "/record_schemas/0",
    },
  ],
  mutations_applied: true,
  delete_missing: false,
  applied_at: "2026-08-13T00:00:00Z",
  applied_by: "20800000-0000-4000-8000-000000000010",
  idempotency_key: "schema-bundle-test",
};

const mocks = vi.hoisted(() => ({
  getAccess: vi.fn(),
  upload: vi.fn(),
  plan: vi.fn(),
  apply: vi.fn(),
  readBack: vi.fn(),
  download: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return {
    ...original,
    getEffectiveProductAccess: mocks.getAccess,
    uploadSchemaDefinitionBundle: mocks.upload,
    planSchemaDefinitionBundle: mocks.plan,
    applySchemaDefinitionBundle: mocks.apply,
    getSchemaDefinitionBundleApplication: mocks.readBack,
    downloadSchemaDefinitionBundle: mocks.download,
  };
});

function validFile(): File {
  return new File(
    [
      JSON.stringify({
        $schema:
          "https://cmp.example/contracts/catalog/schema-definition-bundle.schema.json",
        contract_version: "1.0.0",
        bundle_key: "synthetic_dependency_chain",
        bundle_version: "1.0.0",
        scope: {
          organization_id: "20800000-0000-4000-8000-000000000003",
          project_id: "20800000-0000-4000-8000-000000000004",
          classification: "internal",
        },
        catalog: { database: { key: "db" }, profile: { key: "profile" } },
        record_schemas: [{ key: "materials" }, { key: "tests" }],
      }),
    ],
    "synthetic-definition-bundle.json",
    { type: "application/json" },
  );
}

describe("SchemaDefinitionBundleAdmin", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.sessionStorage.clear();
    mocks.getAccess.mockResolvedValue({
      data: {
        product_role: "administrator",
        feature_grants: ["schema_configuration", "catalog_edit"],
        legacy_compatible: false,
      },
      etag: null,
    });
    mocks.upload.mockResolvedValue({
      data: {
        upload: {
          upload_id: "20800000-0000-4000-8000-000000000011",
          organization_id: plan.source_artifact.organization_id,
          project_id: plan.source_artifact.project_id,
          classification: "internal",
          state: "completed",
          original_filename: "synthetic-definition-bundle.json",
          media_type: plan.source_artifact.media_type,
          expected_size_bytes: 512,
          expected_sha256: sha256,
          part_size_bytes: 512,
          expected_part_count: 1,
          test_run_revision_id: null,
          raw_asset_id: "20800000-0000-4000-8000-000000000012",
        },
        raw_asset: {
          raw_asset_id: "20800000-0000-4000-8000-000000000012",
          organization_id: plan.source_artifact.organization_id,
          project_id: plan.source_artifact.project_id,
          classification: "internal",
          sha256,
          size_bytes: 512,
          media_type: plan.source_artifact.media_type,
          original_filename: "synthetic-definition-bundle.json",
          storage_state: "staged_verified",
        },
        available_artifact_id: artifactId,
      },
      etag: null,
      requestId: "upload-request",
    });
    mocks.plan.mockResolvedValue({ data: plan, etag: null, requestId: "plan-request" });
    mocks.apply.mockResolvedValue({
      data: application,
      etag: null,
      requestId: "apply-request",
    });
    mocks.readBack.mockResolvedValue({
      data: application,
      etag: null,
      requestId: "read-request",
    });
    mocks.download.mockResolvedValue({
      blob: new Blob(["{}"], {
        type: "application/vnd.cmp.catalog-schema-definition-bundle+json",
      }),
      sha256: "9".repeat(64),
      filename: "synthetic_dependency_chain-1.0.0.json",
      media_type: "application/vnd.cmp.catalog-schema-definition-bundle+json",
      application_id: applicationId,
      source_artifact_id: artifactId,
      source_artifact_sha256: sha256,
      request_id: "export-request",
    });
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:bundle-export"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  });

  it("uploads, plans, keyboard-inspects, explicitly applies, reads back, and exports exact evidence", async () => {
    const user = userEvent.setup();
    render(
      <SchemaDefinitionBundleAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
      />,
    );

    const input = await screen.findByLabelText("Definition bundle");
    await user.upload(input, validFile());
    expect(await screen.findByText("2", { selector: "dd" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Upload and plan" }));

    expect(await screen.findByText("2 actions")).toBeTruthy();
    expect(mocks.plan).toHaveBeenCalledWith(expect.anything(), {
      artifact_id: artifactId,
      artifact_sha256: sha256,
    });
    const secondRow = screen.getByRole("button", { name: longKey });
    expect(secondRow.title).toBe(longKey);
    const firstRow = screen.getByRole("button", { name: "materials" });
    firstRow.focus();
    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(secondRow);
    expect(screen.getAllByText(longKey).length).toBeGreaterThan(1);

    await user.click(screen.getByRole("button", { name: "Review exact plan" }));
    expect(screen.getByText(planFingerprint)).toBeTruthy();
    const confirmation = screen.getByRole("checkbox", {
      name: "I reviewed this exact version, checksum, and plan fingerprint.",
    });
    await user.click(confirmation);
    await user.click(screen.getByRole("button", { name: "Apply exact plan" }));

    expect(await screen.findByText("Bundle applied and read back")).toBeTruthy();
    expect(mocks.apply).toHaveBeenCalledWith(expect.anything(), {
      artifact_id: artifactId,
      artifact_sha256: sha256,
      plan_fingerprint: planFingerprint,
    });
    expect(mocks.readBack).toHaveBeenCalledWith(expect.anything(), applicationId);

    await user.click(screen.getByRole("button", { name: "Export verified source" }));
    expect(await screen.findByText("synthetic_dependency_chain-1.0.0.json downloaded")).toBeTruthy();
    expect(mocks.download).toHaveBeenCalledWith(
      expect.anything(),
      "synthetic_dependency_chain",
      "1.0.0",
    );
    expect(URL.createObjectURL).toHaveBeenCalledOnce();
  });

  it("blocks confirmation when the server plan requires a current Record migration", async () => {
    const user = userEvent.setup();
    const migrationPlan: SchemaDefinitionBundlePlan = {
      ...plan,
      valid: false,
      action_counts: { create: 0, update: 0, "no-op": 0, conflict: 0, error: 1 },
      actions: [
        {
          ...plan.actions[0]!,
          disposition: "error",
          reason_codes: ["record_migration_required"],
        },
      ],
      diagnostics: [
        {
          severity: "error",
          code: "CMP-SCHEMA-BUNDLE-0014",
          location: "/catalog/table/materials",
          message: "Table 'materials' has current Records that pin its old revision.",
          remediation:
            "Migrate the affected current Records through an approved workflow, then request a fresh server plan.",
        },
      ],
    };
    mocks.plan.mockResolvedValue({
      data: migrationPlan,
      etag: null,
      requestId: "migration-plan-request",
    });
    render(
      <SchemaDefinitionBundleAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
      />,
    );

    await user.upload(await screen.findByLabelText("Definition bundle"), validFile());
    await user.click(screen.getByRole("button", { name: "Upload and plan" }));

    expect(await screen.findByText("CMP-SCHEMA-BUNDLE-0014")).toBeTruthy();
    expect(
      screen.getByText(
        "Apply is blocked because current Records require an approved migration before this schema change.",
      ),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Review exact plan" }),
    ).toMatchObject({ disabled: true });
    expect(screen.queryByText("Confirm the exact plan")).toBeNull();
    expect(mocks.apply).not.toHaveBeenCalled();
  });

  it("locks source replacement during planning and requires an explicit reset afterward", async () => {
    const user = userEvent.setup();
    let resolvePlan: (value: {
      data: SchemaDefinitionBundlePlan;
      etag: null;
      requestId: string;
    }) => void = () => undefined;
    mocks.plan.mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePlan = resolve;
      }),
    );
    render(
      <SchemaDefinitionBundleAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
      />,
    );

    const input = (await screen.findByLabelText("Definition bundle")) as HTMLInputElement;
    await user.upload(input, validFile());
    await user.click(screen.getByRole("button", { name: "Upload and plan" }));
    await waitFor(() => expect(mocks.plan).toHaveBeenCalledOnce());

    expect(input.disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "New bundle" })).toBeNull();

    resolvePlan({ data: plan, etag: null, requestId: "deferred-plan-request" });
    expect(await screen.findByText("2 actions")).toBeTruthy();
    expect(input.disabled).toBe(true);

    await user.click(screen.getByRole("button", { name: "New bundle" }));
    expect(input.disabled).toBe(false);
    expect(screen.queryByText("2 actions")).toBeNull();
    expect(screen.queryByRole("button", { name: "Review exact plan" })).toBeNull();
    expect(window.sessionStorage.getItem("cmp.schema-definition-bundle-administration.v1")).toBeNull();
  });

  it("blocks User and Reviewer roles before any bundle operation is exposed", async () => {
    mocks.getAccess.mockResolvedValue({
      data: { product_role: "reviewer", feature_grants: [], legacy_compatible: false },
      etag: null,
    });
    render(
      <SchemaDefinitionBundleAdmin
        config={{ baseUrl: "/api/v1", accessToken: "reviewer-token" }}
        onOpenConnection={() => undefined}
      />,
    );

    expect((await screen.findByRole("alert")).textContent).toContain(
      "Administrator access is required.",
    );
    expect(screen.queryByLabelText("Definition bundle")).toBeNull();
    expect(screen.queryByRole("button", { name: /Apply/ })).toBeNull();
    expect(mocks.plan).not.toHaveBeenCalled();
  });

  it("does not replay a stale Apply and offers a fresh server plan", async () => {
    const user = userEvent.setup();
    mocks.apply.mockRejectedValue(
      new ApiError(
        409,
        "The server Catalog changed after this plan.",
        "CMP-CATALOG-0207",
        "stale-correlation",
      ),
    );
    render(
      <SchemaDefinitionBundleAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
      />,
    );

    await user.upload(await screen.findByLabelText("Definition bundle"), validFile());
    await user.click(screen.getByRole("button", { name: "Upload and plan" }));
    await user.click(await screen.findByRole("button", { name: "Review exact plan" }));
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Apply exact plan" }));

    expect(await screen.findByText("The approved plan is stale.")).toBeTruthy();
    expect(screen.getByText("Current Catalog snapshot")).toBeTruthy();
    expect(screen.getByText("No client plan actions were applied.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Plan again" }));
    await waitFor(() => expect(mocks.plan).toHaveBeenCalledTimes(2));
    expect(mocks.apply).toHaveBeenCalledOnce();
    expect(
      (await screen.findByRole("button", { name: "Review exact plan" })) as HTMLButtonElement,
    ).toMatchObject({ disabled: false });
  });

  it("withholds success after an uncertain Apply and recovers only by application read-back", async () => {
    const user = userEvent.setup();
    mocks.readBack
      .mockRejectedValueOnce(
        new ApiError(503, "Application read-back is temporarily unavailable.", undefined, "read-failed"),
      )
      .mockResolvedValue({ data: application, etag: null, requestId: "read-recovered" });
    render(
      <SchemaDefinitionBundleAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
      />,
    );

    await user.upload(await screen.findByLabelText("Definition bundle"), validFile());
    await user.click(screen.getByRole("button", { name: "Upload and plan" }));
    await user.click(await screen.findByRole("button", { name: "Review exact plan" }));
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Apply exact plan" }));

    expect(await screen.findByText(/Application read-back is temporarily unavailable\./)).toBeTruthy();
    expect(
      screen.getByText(
        "Apply returned an application, but success is withheld until immutable read-back completes.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText("Bundle applied and read back")).toBeNull();
    expect(screen.queryByRole("button", { name: "Export verified source" })).toBeNull();
    expect(window.sessionStorage.getItem("cmp.schema-definition-bundle-administration.v1")).toContain(
      applicationId,
    );

    await user.click(screen.getByRole("button", { name: "Read applied result" }));
    expect(await screen.findByText("Bundle applied and read back")).toBeTruthy();
    expect(mocks.apply).toHaveBeenCalledOnce();
    expect(mocks.readBack).toHaveBeenCalledTimes(2);
  });

  it("restores an immutable application after refresh without storing source bytes", async () => {
    window.sessionStorage.setItem(
      "cmp.schema-definition-bundle-administration.v1",
      JSON.stringify({
        artifactId,
        artifactSha256: sha256,
        bundleKey: application.bundle_key,
        bundleVersion: application.bundle_version,
        applicationId,
      }),
    );
    render(
      <SchemaDefinitionBundleAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
      />,
    );

    expect(await screen.findByText("Bundle applied and read back")).toBeTruthy();
    expect(mocks.readBack).toHaveBeenCalledWith(expect.anything(), applicationId);
    expect(window.sessionStorage.getItem("cmp.schema-definition-bundle-administration.v1")).not.toContain(
      "record_schemas",
    );
    expect(mocks.apply).not.toHaveBeenCalled();
  });
});

describe("inspectSchemaDefinitionBundleFile", () => {
  it("rejects invalid MIME, malformed JSON, oversized files, and incomplete bundle shape", async () => {
    await expect(
      inspectSchemaDefinitionBundleFile(
        new File(["{}"], "bundle.json", { type: "text/plain" }),
      ),
    ).rejects.toThrow("JSON Schema Definition Bundle");
    await expect(
      inspectSchemaDefinitionBundleFile(
        new File(["{"], "bundle.json", { type: "application/json" }),
      ),
    ).rejects.toThrow("not valid JSON");
    await expect(
      inspectSchemaDefinitionBundleFile(
        new File(
          [new Uint8Array([0x7b, 0x22, 0x61, 0x22, 0x3a, 0xff, 0x7d])],
          "bundle.json",
          { type: "application/json" },
        ),
      ),
    ).rejects.toThrow("not valid UTF-8 JSON");
    const oversized = new File(["{}"], "bundle.json", { type: "application/json" });
    Object.defineProperty(oversized, "size", { value: 64 * 1024 * 1024 + 1 });
    await expect(inspectSchemaDefinitionBundleFile(oversized)).rejects.toThrow("larger than 64 MiB");
    await expect(
      inspectSchemaDefinitionBundleFile(
        new File(["{}"], "bundle.json", { type: "application/json" }),
      ),
    ).rejects.toThrow("not a version 1.0.0");
  });

  it("builds one deterministic source-set Artifact from a manifest and referenced files", async () => {
    const manifest = new File([JSON.stringify({
      document_type: "cmp.catalog-schema-bundle",
      bundle_id: "source-demo",
      bundle_version: "2026.08.0",
      unit_profiles: [
        { key: "source_si", name: "Source SI", units: { stress: "MPa" } },
        { key: "source_mm", name: "Source mm", units: { length: "mm" } },
      ],
      tables: [
        { key: "technical-data", record_schema_ref: "record-schemas/technical.json" },
        { key: "tensile-test", record_schema_ref: "record-schemas/tensile.json" },
      ],
    })], "catalog-schema-bundle.manifest.json", { type: "application/json" });
    const technical = new File(["{}"], "technical.json", { type: "application/json" });
    const tensile = new File(["{}"], "tensile.json", { type: "application/json" });

    const first = await inspectSchemaDefinitionBundleFiles([tensile, manifest, technical]);
    const second = await inspectSchemaDefinitionBundleFiles([technical, tensile, manifest]);

    expect(first.sourceFormat).toBe("source file set");
    expect(first.fileCount).toBe(3);
    expect(first.schemaCount).toBe(2);
    expect(first.unitProfileCount).toBe(2);
    expect(first.file.type).toBe("application/vnd.cmp.catalog-schema-source-set+json");
    expect(await first.file.text()).toBe(await second.file.text());

    const reopened = await inspectSchemaDefinitionBundleFiles([first.file]);
    expect(reopened.bundleKey).toBe("source-demo");
    expect(reopened.fileCount).toBe(3);
    expect(reopened.unitProfileCount).toBe(2);
    expect(await reopened.file.text()).toBe(await first.file.text());
  });
});
