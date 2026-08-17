import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../../../api";
import {
  commitCommonProcessingOutput,
  createCommonMappingProfile,
  createCommonProcessingRecipe,
  createExactTargetPreview,
  deliverExactTargetPreview,
  downloadCommonProcessingOutput,
  downloadSelectedModelNeutralMaterial,
  executeCommonProcessingBatch,
  executeMetalFitRun,
  getReferenceElastoplasticExportCapabilities,
  listCommonMappingProfiles,
  listCommonProcessingBatches,
  listCommonProcessingEnsembleMethods,
  listCommonProcessingMethods,
  listCommonProcessingOutputs,
  listCommonProcessingRecipes,
  preflightCommonProcessingBatch,
  previewCommonProcessing,
  previewCommonProcessingEnsemble,
  previewCommonProcessingFromOutput,
  retryFailedCommonProcessingBatch,
  reviseCommonMappingProfile,
  reviseCommonProcessingRecipe,
} from "./modeling-api";

const config = { baseUrl: "/api/v1/", accessToken: " modeling-token " };

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({
      "content-type": "application/json",
      etag: '"modeling-r7"',
      "x-request-id": "request-modeling-7",
    }),
    json: async () => body,
  } as Response;
}

describe("Modeling API ownership contract", () => {
  it("preserves all JSON endpoint paths, methods, bodies, concurrency headers, and transport metadata", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ accepted: true }));
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    const profileInput = {
      classification: "internal",
      content: { profile_key: "profile", bindings: [] },
      change_reason: "Create exact profile",
    };
    const profileRevision = {
      content: { profile_key: "profile-r2", bindings: [] },
      change_reason: "Revise exact profile",
    };
    const recipeInput = {
      classification: "internal",
      content: { recipe_key: "recipe", steps: [] },
      change_reason: "Create exact recipe",
    };
    const recipeRevision = {
      content: { recipe_key: "recipe-r2", steps: [] },
      change_reason: "Revise exact recipe",
    };
    const preflightInput = {
      classification: "internal",
      recipe_id: "recipe",
      recipe_revision_id: "recipe-r1",
      sources: [{ document_id: "document", revision_id: "document-r3" }],
    };
    const batchInput = {
      ...preflightInput,
      label: "Exact batch",
      change_reason: "Run exact batch",
    };
    const previewInput = {
      document: { document_id: "document" },
      mapping_profile: { profile_key: "profile" },
      steps: [{ method_id: "rows.sort_unique", method_version: "1.0.0", options: {} }],
    };
    const fitPreviewInput = {
      source_processing_output: { aggregate_id: "output", revision_id: "output-r4" },
      fit_step: { method_id: "metal.hardening_fit_extrapolate", method_version: "1.0.0", options: {} },
    };
    const fitRunInput = {
      classification: "internal",
      ...fitPreviewInput,
      change_reason: "Run selected exact fit",
    };
    const ensembleInput = {
      documents: [{ document_id: "document-a" }, { document_id: "document-b" }],
      mapping_profile: { profile_key: "profile" },
      preprocessing_steps: [{ method_id: "rows.sort_unique", method_version: "1.0.0", options: {} }],
      alignment: { point_count: 101, domain_policy: "intersection", extrapolation: "reject" },
    };
    const outputInput = {
      classification: "internal",
      label: "Selected Process result",
      source_document: { aggregate_id: "document", revision_id: "document-r3" },
      mapping_profile: { aggregate_id: "profile", revision_id: "profile-r2" },
      steps: previewInput.steps,
      change_reason: "Save exact result",
      source_processing_output: null,
      fit_decision: null,
    };
    const targetPreviewInput = {
      processing_output_id: "output",
      processing_output_revision_id: "output-r4",
      neutral_material_id: "neutral",
      neutral_material_revision_id: "neutral-r2",
      target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s" },
      solver_material_id: 7,
      material_name: "REFERENCE",
      expected_mapping_report_sha256: "a".repeat(64),
    };
    const targetDeliveryInput = {
      ...targetPreviewInput,
      preview_identity: "b".repeat(64),
      expected_mapping_report_sha256: "c".repeat(64),
      acknowledgement_identity: "d".repeat(64),
    };

    const cases: Array<{
      name: string;
      path: string;
      method?: string;
      body?: unknown;
      ifMatch?: string;
      signal?: AbortSignal;
      invoke: () => Promise<unknown>;
    }> = [
      { name: "list methods", path: "/processing-methods", invoke: () => listCommonProcessingMethods(config) },
      { name: "list ensemble methods", path: "/processing-ensemble-methods", invoke: () => listCommonProcessingEnsembleMethods(config) },
      { name: "list profiles", path: "/mapping-profiles", invoke: () => listCommonMappingProfiles(config) },
      { name: "create profile", path: "/mapping-profiles", method: "POST", body: profileInput, invoke: () => createCommonMappingProfile(config, profileInput as never) },
      { name: "revise profile", path: "/mapping-profiles/profile%2Fid/revisions", method: "POST", body: profileRevision, ifMatch: '"profile-r1"', invoke: () => reviseCommonMappingProfile(config, "profile/id", '"profile-r1"', profileRevision as never) },
      { name: "list recipes", path: "/common-processing-recipes", invoke: () => listCommonProcessingRecipes(config) },
      { name: "create recipe", path: "/common-processing-recipes", method: "POST", body: recipeInput, invoke: () => createCommonProcessingRecipe(config, recipeInput as never) },
      { name: "revise recipe", path: "/common-processing-recipes/recipe%2Fid/revisions", method: "POST", body: recipeRevision, ifMatch: '"recipe-r1"', invoke: () => reviseCommonProcessingRecipe(config, "recipe/id", '"recipe-r1"', recipeRevision as never) },
      { name: "preflight batch", path: "/common-processing-batches:preflight", method: "POST", body: preflightInput, invoke: () => preflightCommonProcessingBatch(config, preflightInput as never) },
      { name: "execute batch", path: "/common-processing-batches", method: "POST", body: batchInput, invoke: () => executeCommonProcessingBatch(config, batchInput as never) },
      { name: "list batches", path: "/common-processing-batches", invoke: () => listCommonProcessingBatches(config) },
      { name: "retry failed batch", path: "/common-processing-batches/batch%2Fid:retry-failed", method: "POST", invoke: () => retryFailedCommonProcessingBatch(config, "batch/id") },
      { name: "preview process", path: "/processing:preview", method: "POST", body: previewInput, signal: controller.signal, invoke: () => previewCommonProcessing(config, previewInput as never, controller.signal) },
      { name: "preview Fit from exact output", path: "/processing:preview-from-output", method: "POST", body: fitPreviewInput, signal: controller.signal, invoke: () => previewCommonProcessingFromOutput(config, fitPreviewInput as never, controller.signal) },
      { name: "execute exact Fit", path: "/metal-fit-runs", method: "POST", body: fitRunInput, signal: controller.signal, invoke: () => executeMetalFitRun(config, fitRunInput as never, controller.signal) },
      { name: "preview ensemble", path: "/processing:preview-ensemble", method: "POST", body: ensembleInput, invoke: () => previewCommonProcessingEnsemble(config, ensembleInput as never) },
      { name: "list outputs", path: "/processing-outputs", invoke: () => listCommonProcessingOutputs(config) },
      { name: "commit output", path: "/processing-outputs", method: "POST", body: outputInput, invoke: () => commitCommonProcessingOutput(config, outputInput as never) },
      { name: "create exact target preview", path: "/exporting/target-previews", method: "POST", body: targetPreviewInput, invoke: () => createExactTargetPreview(config, targetPreviewInput) },
      { name: "read Export capabilities", path: "/exporters/reference-elastoplastic/capabilities", invoke: () => getReferenceElastoplasticExportCapabilities(config) },
      { name: "deliver exact target", path: "/exporting/target-deliveries", method: "POST", body: targetDeliveryInput, invoke: () => deliverExactTargetPreview(config, targetDeliveryInput) },
    ];

    for (const [index, testCase] of cases.entries()) {
      const result = await testCase.invoke() as { etag: string | null; requestId?: string | null };
      const [url, init = {}] = fetchMock.mock.calls[index];
      const headers = new Headers(init.headers);
      expect(url, testCase.name).toBe(`/api/v1${testCase.path}`);
      expect(init.method ?? "GET", testCase.name).toBe(testCase.method ?? "GET");
      expect(headers.get("authorization"), testCase.name).toBe("Bearer modeling-token");
      expect(headers.get("accept"), testCase.name).toBe("application/json");
      expect(headers.get("if-match"), testCase.name).toBe(testCase.ifMatch ?? null);
      expect(headers.get("content-type"), testCase.name).toBe(testCase.body === undefined ? null : "application/json");
      expect(init.body === undefined ? undefined : JSON.parse(String(init.body)), testCase.name).toEqual(testCase.body);
      expect(init.signal, testCase.name).toBe(testCase.signal);
      expect(result.etag, testCase.name).toBe('"modeling-r7"');
      expect(result.requestId, testCase.name).toBe("request-modeling-7");
    }
    expect(fetchMock).toHaveBeenCalledTimes(cases.length);
  });

  it("preserves exact download paths, Accept headers, filenames, and ETags", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({
          "content-disposition": 'attachment; filename="process-output-r4.json"',
          etag: '"process-sha"',
        }),
        blob: async () => new Blob(["process"]),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({
          "content-disposition": 'attachment; filename="selected-model-r2.cmp-neutral.json"',
          etag: '"neutral-sha"',
        }),
        blob: async () => new Blob(["neutral"]),
      } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const process = await downloadCommonProcessingOutput(config, "output/id");
    const neutral = await downloadSelectedModelNeutralMaterial(config, "neutral/id", "revision/id");

    expect(process.data.filename).toBe("process-output-r4.json");
    expect(process.etag).toBe('"process-sha"');
    expect(neutral.data.filename).toBe("selected-model-r2.cmp-neutral.json");
    expect(neutral.etag).toBe('"neutral-sha"');
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/processing-outputs/output%2Fid/content",
      "/api/v1/neutral-materials/neutral%2Fid/revisions/revision%2Fid/download",
    ]);
    const processHeaders = new Headers(fetchMock.mock.calls[0][1]?.headers);
    const neutralHeaders = new Headers(fetchMock.mock.calls[1][1]?.headers);
    expect(processHeaders.get("accept")).toBe("application/vnd.cmp.processing-output+json");
    expect(neutralHeaders.get("accept")).toBe("application/json");
    expect(processHeaders.get("authorization")).toBe("Bearer modeling-token");
    expect(neutralHeaders.get("authorization")).toBe("Bearer modeling-token");
  });

  it("preserves structured API failure meaning for JSON and download responses", async () => {
    const problem = {
      detail: "The exact revision no longer matches.",
      code: "revision_conflict",
      trace_id: "trace-modeling-7",
    };
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse(problem, 409))
      .mockResolvedValueOnce(jsonResponse(problem, 409));
    vi.stubGlobal("fetch", fetchMock);

    const requestFailure = await listCommonProcessingOutputs(config).catch((error: unknown) => error);
    expect(requestFailure).toBeInstanceOf(ApiError);
    expect(requestFailure).toMatchObject({
      status: 409,
      code: problem.code,
      traceId: problem.trace_id,
    } satisfies Partial<ApiError>);
    expect((requestFailure as ApiError).message).toBe(
      `${problem.detail} Support reference: ${problem.code} · ${problem.trace_id}.`,
    );
    const downloadFailure = await downloadCommonProcessingOutput(config, "stale-output").catch((error: unknown) => error);
    expect(downloadFailure).toBeInstanceOf(ApiError);
    expect(downloadFailure).toMatchObject({
      status: 409,
      code: problem.code,
      traceId: problem.trace_id,
    } satisfies Partial<ApiError>);
    expect((downloadFailure as ApiError).message).toBe(
      `${problem.detail} Support reference: ${problem.code} · ${problem.trace_id}.`,
    );
  });
});
