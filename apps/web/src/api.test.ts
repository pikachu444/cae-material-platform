import { describe, expect, it, vi } from "vitest";
import {
  ApiError,
  createReferenceImportMapping,
  detectReferenceImport,
  downloadNeutralHyperelasticMappingReport,
  downloadSelectedModelNeutralMaterial,
  executeReferenceImport,
  getReferenceOgdenCalibrationRun,
  importReferenceTensileDataset,
  previewDatasetCurve,
  preflightSolverCardMapping,
  previewSolverCard,
  getSolverCard,
  getNeutralSolverMappingReport,
  requestLocalDemoAccessToken,
  listMaterials,
  searchMaterialCatalogRecords,
  previewCommonProcessingFromOutput,
  applySchemaDefinitionBundle,
  downloadSchemaDefinitionBundle,
  getSchemaDefinitionBundleApplication,
  planSchemaDefinitionBundle,
  uploadSchemaDefinitionBundle,
} from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json", etag: "\"revision\"" }),
    json: async () => body,
  } as Response;
}

describe("Catalog API client", () => {
  it("downloads the exact selected-model Neutral revision and preserves server headers", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({
        "content-disposition": 'attachment; filename="selected-model-r4.cmp-neutral.json"',
        etag: '"neutral-digest"',
      }),
      blob: async () => new Blob(["{}"], { type: "application/json" }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const result = await downloadSelectedModelNeutralMaterial(
      { baseUrl: "/api/v1", accessToken: "short-lived-token" },
      "neutral-id",
      "neutral-revision",
    );

    expect(result.data.filename).toBe("selected-model-r4.cmp-neutral.json");
    expect(result.etag).toBe('"neutral-digest"');
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/v1/neutral-materials/neutral-id/revisions/neutral-revision/download",
    );
  });

  it("pins Fit preview requests to one exact Process Output revision", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ execution_mode: "preview", promotable: false, source_document_sha256: "a".repeat(64), mapping_profile_sha256: "b".repeat(64), independent_quantity: "strain.engineering", stages: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await previewCommonProcessingFromOutput(
      { baseUrl: "/api/v1", accessToken: "short-lived-token" },
      {
        source_processing_output: {
          aggregate_id: "00000000-0000-4000-8000-000000000101",
          revision_id: "00000000-0000-4000-8000-000000000102",
        },
        fit_step: {
          method_id: "metal.hardening_fit_extrapolate",
          method_version: "1.0.0",
          options: { equation_contract: "altair-material-modeler-2025-v1", families: ["voce"] },
        },
      },
    );

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/processing:preview-from-output");
    expect(JSON.parse(String(init?.body))).toMatchObject({
      source_processing_output: {
        aggregate_id: "00000000-0000-4000-8000-000000000101",
        revision_id: "00000000-0000-4000-8000-000000000102",
      },
      fit_step: { method_id: "metal.hardening_fit_extrapolate" },
    });
  });

  it("sends the tenant-scoped bearer token to the configured Material endpoint", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await listMaterials(
      { baseUrl: "http://localhost:8000/api/v1", accessToken: "short-lived-token" },
      "DP780 steel",
    );

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/materials?limit=50&offset=0&q=DP780+steel");
    expect(new Headers(init?.headers).get("authorization")).toBe("Bearer short-lived-token");
    expect(new Headers(init?.headers).get("accept")).toBe("application/json");
  });

  it("does not make a catalog request without an explicit bearer token", async () => {
    try {
      await listMaterials({ baseUrl: "/api/v1", accessToken: "" }, "");
      throw new Error("Expected a missing-token request to fail");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(401);
    }
  });

  it("uses one governed Catalog search for Materials rows, facets, sort and binding scope", async () => {
    const tableId = "00000000-0000-0000-0000-000000000010";
    const tableRevisionId = "00000000-0000-0000-0000-000000000011";
    const classAttributeId = "00000000-0000-0000-0000-000000000012";
    const classAttributeRevisionId = "00000000-0000-0000-0000-000000000013";
    const materialId = "00000000-0000-0000-0000-000000000014";
    const recordId = "00000000-0000-0000-0000-000000000015";
    const recordRevisionId = "00000000-0000-0000-0000-000000000016";
    const metadata = (id: string) => ({
      id,
      aggregate_id: id,
      revision_no: 1,
      based_on_revision_id: null,
      schema_id: "urn:cmp:catalog:record:1.0.0",
      schema_version: "1.0.0",
      content_hash: "a".repeat(64),
      created_at: "2026-07-20T00:00:00Z",
      created_by: "00000000-0000-0000-0000-000000000003",
      change_reason: "fixture",
      organization_id: "00000000-0000-0000-0000-000000000004",
      project_id: "00000000-0000-0000-0000-000000000005",
      classification: "internal",
      lifecycle_state: "draft",
    });
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({
        items: [{
          attribute_definition_id: classAttributeId,
          table_id: tableId,
          current_revision: {
            ...metadata(classAttributeRevisionId),
            content: {
              table_revision_id: tableRevisionId,
              key: "material_class",
              name: "Material class",
              data_type: "discrete",
              required: false,
              quantity_semantics: null,
              normalized_unit: null,
              minimum_number: null,
              maximum_number: null,
              minimum_length: null,
              maximum_length: null,
              pattern: null,
              allowed_values: ["metal", "polymer", "elastomer"],
              reference_table_id: null,
              help_text: null,
            },
          },
        }],
      }))
      .mockResolvedValueOnce(jsonResponse({
        items: [{
          record_id: recordId,
          table_id: tableId,
          domain_binding: {
            binding_id: "00000000-0000-0000-0000-000000000017",
            record_id: recordId,
            record_revision_id: recordRevisionId,
            kind: "material",
            object_id: materialId,
            revision_id: "00000000-0000-0000-0000-000000000018",
            workbench_path: `/materials/${materialId}`,
          },
          current_revision: {
            ...metadata(recordRevisionId),
            content: {
              table_revision_id: tableRevisionId,
              name: "Demo DP780",
              external_key: "DP780",
              description: "Synthetic metal reference",
              folder_id: null,
              folder_revision_id: null,
              values: [{
                data_type: "discrete",
                attribute_definition_id: classAttributeId,
                attribute_definition_revision_id: classAttributeRevisionId,
                value: "metal",
              }],
            },
          },
        }],
        total_count: 1,
        offset: 50,
        limit: 50,
        facets: [{ attribute_definition_id: classAttributeId, value: "metal", count: 1 }],
      }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await searchMaterialCatalogRecords(
      { baseUrl: "/api/v1", accessToken: "short-lived-token" },
      { tableId, query: "DP780", materialClass: "metal", offset: 50, limit: 50, sortBy: "material_class", sortDirection: "descending" },
    );

    expect(result.data.items[0]?.material_id).toBe(materialId);
    expect(result.data.items[0]?.material_revision_id).toBe("00000000-0000-0000-0000-000000000018");
    expect(result.data.items[0]?.record_id).toBe(recordId);
    expect(result.data.items[0]?.record_revision_id).toBe(recordRevisionId);
    expect(result.data.items[0]?.record_revision_id).not.toBe(result.data.items[0]?.material_revision_id);
    expect(result.data.items[0]?.record_revision_no).toBe(1);
    expect(result.data.items[0]?.material_class).toBe("metal");
    expect(result.data.total_count).toBe(1);
    expect(result.data.facets.material_classes).toEqual([{ material_class: "metal", count: 1 }]);
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe("/api/v1/catalog/records:search");
    expect(JSON.parse(String(init?.body))).toMatchObject({
      table_id: tableId,
      text: "DP780",
      domain_binding_kind: "material",
      include_descendants: false,
      sort_by: "attribute",
      sort_attribute_id: classAttributeId,
      sort_direction: "descending",
      offset: 50,
      limit: 50,
    });
  });

  it("preserves the problem code and trace ID in every user-visible API error", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse(
        {
          detail: "The selected revision is no longer current; reload and retry.",
          code: "CMP-REVISION-409",
          trace_id: "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
        },
        409,
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      listMaterials({ baseUrl: "/api/v1", accessToken: "short-lived-token" }, "DP780"),
    ).rejects.toMatchObject({
      status: 409,
      code: "CMP-REVISION-409",
      traceId: "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
      supportReference:
        "CMP-REVISION-409 · 00-0123456789abcdef0123456789abcdef-0123456789abcdef-01",
      message:
        "The selected revision is no longer current; reload and retry. Support reference: CMP-REVISION-409 · 00-0123456789abcdef0123456789abcdef-0123456789abcdef-01.",
    });
  });

  it("requests a local demo token without attaching a bearer credential", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({
      access_token: "local-demo-token",
      token_type: "Bearer",
      expires_in_seconds: 900,
      organization_id: "d0000000-0000-4000-8000-000000000001",
      project_id: "d0000000-0000-4000-8000-000000000002",
      group: "cmp-demo-material-team",
    }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await requestLocalDemoAccessToken({ baseUrl: "/api/v1" });

    expect(result.data.access_token).toBe("local-demo-token");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/demo-identity/token");
    expect(new Headers(init?.headers).get("authorization")).toBeNull();
  });

  it("acknowledges an explicit solver target before any Solver Card is created", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        material_model_id: "00000000-0000-0000-0000-000000000001",
        material_model_revision_id: "00000000-0000-0000-0000-000000000002",
        model_schema_digest: "a".repeat(64),
        target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
        items: [],
        exporter_id: "cmp.reference.openradioss-elast",
        exporter_version: "1.0.0",
        exporter_digest: "b".repeat(64),
        mapping_report_sha256: "c".repeat(64),
        exportable: true,
        non_production: true,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await preflightSolverCardMapping(
      { baseUrl: "http://localhost:8000/api/v1", accessToken: "short-lived-token" },
      "00000000-0000-0000-0000-000000000001",
      { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
    );

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(
      "http://localhost:8000/api/v1/material-models/00000000-0000-0000-0000-000000000001/mapping-preflight",
    );
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({
      target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
    });
  });

  it("requests the immutable card preview as authenticated plain text", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "text/plain" }),
      text: async () => "/MAT/ELAST/17/1\n",
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const result = await previewSolverCard(
      { baseUrl: "/api/v1", accessToken: "short-lived-token" },
      "00000000-0000-0000-0000-000000000001",
    );

    expect(result.data).toBe("/MAT/ELAST/17/1\n");
    const [, init] = fetchMock.mock.calls[0];
    expect(new Headers(init?.headers).get("accept")).toBe("text/plain");
    expect(new Headers(init?.headers).get("authorization")).toBe("Bearer short-lived-token");
  });

  it("pins Solver Card reads, previews, and mapping downloads to one revision", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({}))
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "text/plain" }),
        text: async () => "exact-card",
      } as Response)
      .mockResolvedValueOnce(jsonResponse({}))
      .mockResolvedValueOnce(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);
    const config = { baseUrl: "/api/v1", accessToken: "short-lived-token" };
    const cardId = "00000000-0000-0000-0000-000000000101";
    const revisionId = "00000000-0000-0000-0000-000000000102";

    await getSolverCard(config, cardId, revisionId);
    await previewSolverCard(config, cardId, revisionId);
    await getNeutralSolverMappingReport(config, cardId, revisionId);
    await downloadNeutralHyperelasticMappingReport(config, cardId, revisionId);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      `/api/v1/solver-cards/${cardId}?revision_id=${revisionId}`,
      `/api/v1/solver-cards/${cardId}/preview?revision_id=${revisionId}`,
      `/api/v1/neutral-solver-cards/${cardId}/mapping-report?revision_id=${revisionId}`,
      `/api/v1/neutral-solver-cards/${cardId}/mapping-report?revision_id=${revisionId}`,
    ]);
  });

  it("keeps the current-head Solver Card URL unpinned when no revision is selected", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);
    await getSolverCard(
      { baseUrl: "/api/v1", accessToken: "short-lived-token" },
      "00000000-0000-0000-0000-000000000101",
    );
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/solver-cards/00000000-0000-0000-0000-000000000101");
  });

  it("imports a Dataset only with pinned Test Run and Raw Artifact identities", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({
      dataset_id: "00000000-0000-0000-0000-000000000010",
      test_run_id: "00000000-0000-0000-0000-000000000011",
      current_revision: {},
      links: {},
    }, 201));
    vi.stubGlobal("fetch", fetchMock);

    await importReferenceTensileDataset(
      { baseUrl: "http://localhost:8000/api/v1", accessToken: "short-lived-token" },
      {
        test_run_id: "00000000-0000-0000-0000-000000000011",
        test_run_revision_id: "00000000-0000-0000-0000-000000000012",
        raw_asset_id: "00000000-0000-0000-0000-000000000013",
        raw_artifact_id: "00000000-0000-0000-0000-000000000014",
        mapping: {
          strain_column: "engineering_strain",
          stress_column: "engineering_stress",
          strain_unit: "1",
          stress_unit: "MPa",
        },
        change_reason: "Import reference curve",
      },
    );

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/datasets/reference-uniaxial-tensile:import");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toMatchObject({
      test_run_revision_id: "00000000-0000-0000-0000-000000000012",
      raw_artifact_id: "00000000-0000-0000-0000-000000000014",
    });
  });

  it("keeps reference importer detection, mapping approval, and execution as separate API calls", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);
    const config = { baseUrl: "http://localhost:8000/api/v1", accessToken: "short-lived-token" };

    await detectReferenceImport(config, {
      raw_asset_id: "00000000-0000-0000-0000-000000000020",
      raw_artifact_id: "00000000-0000-0000-0000-000000000021",
    });
    await createReferenceImportMapping(config, {
      detection_report_id: "00000000-0000-0000-0000-000000000022",
      mapping_label: "Reference tensile columns",
      strain_column: "engineering_strain",
      stress_column: "engineering_stress",
      strain_unit: "1",
      stress_unit: "MPa",
      change_reason: "Human mapping approval",
    });
    await executeReferenceImport(config, {
      test_run_id: "00000000-0000-0000-0000-000000000023",
      test_run_revision_id: "00000000-0000-0000-0000-000000000024",
      raw_asset_id: "00000000-0000-0000-0000-000000000020",
      raw_artifact_id: "00000000-0000-0000-0000-000000000021",
      import_mapping_id: "00000000-0000-0000-0000-000000000025",
      import_mapping_revision_id: "00000000-0000-0000-0000-000000000026",
      change_reason: "Create immutable Dataset revisions",
    });

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "http://localhost:8000/api/v1/imports:detect",
      "http://localhost:8000/api/v1/import-mappings",
      "http://localhost:8000/api/v1/imports",
    ]);
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toMatchObject({
      detection_report_id: "00000000-0000-0000-0000-000000000022",
      strain_column: "engineering_strain",
      stress_unit: "MPa",
    });
    expect(JSON.parse(String(fetchMock.mock.calls[2][1]?.body))).toMatchObject({
      import_mapping_revision_id: "00000000-0000-0000-0000-000000000026",
      raw_artifact_id: "00000000-0000-0000-0000-000000000021",
    });
  });

  it("requests a bounded curve preview for one concrete Dataset revision", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ points: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await previewDatasetCurve(
      { baseUrl: "/api/v1", accessToken: "short-lived-token" },
      "00000000-0000-0000-0000-000000000015",
      500,
    );

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/dataset-revisions/00000000-0000-0000-0000-000000000015/curve?maximum_points=500");
    expect(new Headers(init?.headers).get("authorization")).toBe("Bearer short-lived-token");
  });

  it("reloads one immutable hyperelastic calibration Run by exact identity", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({
      ogden_calibration_run_id: "00000000-0000-4000-8000-000000000060",
      status: "succeeded",
      family_candidate_count: 4,
      family_candidates: [],
    }));
    vi.stubGlobal("fetch", fetchMock);

    await getReferenceOgdenCalibrationRun(
      { baseUrl: "/api/v1", accessToken: "short-lived-token" },
      "00000000-0000-4000-8000-000000000060",
    );

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/ogden-calibration-runs/00000000-0000-4000-8000-000000000060");
    expect(new Headers(init?.headers).get("authorization")).toBe("Bearer short-lived-token");
  });

  it("keeps bundle plan, exact apply, and immutable read-back as separate requests", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce({
        ...jsonResponse({ plan_fingerprint: "b".repeat(64) }),
        headers: new Headers({
          "content-type": "application/json",
          "x-request-id": "plan-request",
        }),
      } as Response)
      .mockResolvedValueOnce({
        ...jsonResponse({ application_id: "application-id" }, 201),
        headers: new Headers({
          "content-type": "application/json",
          "x-request-id": "apply-request",
        }),
      } as Response)
      .mockResolvedValueOnce(jsonResponse({ application_id: "application-id" }));
    vi.stubGlobal("fetch", fetchMock);
    const config = { baseUrl: "/api/v1", accessToken: "administrator-token" };
    const evidence = {
      artifact_id: "20800000-0000-4000-8000-000000000001",
      artifact_sha256: "a".repeat(64),
    };

    const planned = await planSchemaDefinitionBundle(config, evidence);
    const applied = await applySchemaDefinitionBundle(config, {
      ...evidence,
      plan_fingerprint: "b".repeat(64),
    });
    await getSchemaDefinitionBundleApplication(config, "application-id");

    expect(planned.requestId).toBe("plan-request");
    expect(applied.requestId).toBe("apply-request");
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/catalog/schema-definition-bundles:plan",
      "/api/v1/catalog/schema-definition-bundles:apply",
      "/api/v1/catalog/schema-definition-bundle-applications/application-id",
    ]);
    const applyInit = fetchMock.mock.calls[1]?.[1];
    expect(JSON.parse(String(applyInit?.body))).toEqual({
      ...evidence,
      plan_fingerprint: "b".repeat(64),
      delete_missing: false,
    });
    expect(JSON.parse(String(applyInit?.body))).not.toHaveProperty("actions");
    expect(new Headers(applyInit?.headers).get("idempotency-key")).toMatch(
      /^schema-bundle-/,
    );
  });

  it("uploads a JSON bundle with its exact digest and vendor media type", async () => {
    const file = new File(["{}"], "bundle.json", { type: "application/json" });
    const digestBuffer = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
    const digest = Array.from(new Uint8Array(digestBuffer), (byte) =>
      byte.toString(16).padStart(2, "0"),
    ).join("");
    const upload = {
      upload_id: "20800000-0000-4000-8000-000000000011",
      organization_id: "20800000-0000-4000-8000-000000000003",
      project_id: "20800000-0000-4000-8000-000000000004",
      classification: "internal",
      state: "open",
      original_filename: "bundle.json",
      media_type: "application/vnd.cmp.catalog-schema-definition-bundle+json",
      expected_size_bytes: file.size,
      expected_sha256: digest,
      part_size_bytes: file.size,
      expected_part_count: 1,
      test_run_revision_id: null,
      raw_asset_id: null,
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ upload, upload_capability: "x".repeat(32) }, 201))
      .mockResolvedValueOnce(jsonResponse({ ...upload, state: "open" }))
      .mockResolvedValueOnce(
        jsonResponse({
          upload: { ...upload, state: "completed" },
          raw_asset: {
            raw_asset_id: "20800000-0000-4000-8000-000000000012",
            organization_id: upload.organization_id,
            project_id: upload.project_id,
            classification: "internal",
            sha256: digest,
            size_bytes: file.size,
            media_type: upload.media_type,
            original_filename: file.name,
            storage_state: "staged_verified",
          },
          available_artifact_id: "20800000-0000-4000-8000-000000000001",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const result = await uploadSchemaDefinitionBundle(
      { baseUrl: "/api/v1", accessToken: "administrator-token" },
      { file, classification: "internal" },
    );

    expect(result.data.available_artifact_id).toBe(
      "20800000-0000-4000-8000-000000000001",
    );
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toMatchObject({
      media_type: "application/vnd.cmp.catalog-schema-definition-bundle+json",
      expected_sha256: digest,
      expected_size_bytes: file.size,
    });
    expect(new Headers(fetchMock.mock.calls[1]?.[1]?.headers).get("content-type")).toBe(
      "application/vnd.cmp.catalog-schema-definition-bundle+json",
    );
  });

  it("downloads only when both export checksum headers and immutable source evidence match", async () => {
    const blob = new Blob(["{}"], {
      type: "application/vnd.cmp.catalog-schema-definition-bundle+json",
    });
    const digestBuffer = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
    const digestBytes = new Uint8Array(digestBuffer);
    const digest = Array.from(digestBytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
    const digestBase64 = btoa(String.fromCharCode(...digestBytes));
    const response = (etag: string) =>
      ({
        ok: true,
        status: 200,
        headers: new Headers({
          "content-type": "application/vnd.cmp.catalog-schema-definition-bundle+json",
          etag,
          digest: `sha-256=${digestBase64}`,
          "x-cmp-bundle-application-id": "20800000-0000-4000-8000-000000000002",
          "x-cmp-source-artifact-id": "20800000-0000-4000-8000-000000000001",
          "x-cmp-source-artifact-sha256": "a".repeat(64),
          "x-request-id": "export-request",
        }),
        blob: async () => blob,
      }) as Response;
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(response(`"sha256:${digest}"`))
      .mockResolvedValueOnce(response(`"sha256:${"0".repeat(64)}"`));
    vi.stubGlobal("fetch", fetchMock);
    const config = { baseUrl: "/api/v1", accessToken: "administrator-token" };

    const exported = await downloadSchemaDefinitionBundle(
      config,
      "synthetic_dependency_chain",
      "1.0.0",
    );
    expect(exported).toMatchObject({
      sha256: digest,
      filename: "synthetic_dependency_chain-1.0.0.json",
      application_id: "20800000-0000-4000-8000-000000000002",
      request_id: "export-request",
    });
    await expect(
      downloadSchemaDefinitionBundle(config, "synthetic_dependency_chain", "1.0.0"),
    ).rejects.toThrow("checksum does not match");
  });
});
