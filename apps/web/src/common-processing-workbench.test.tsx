import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  CommonProcessingWorkbench,
  fitSurfaceState,
  fitRailIdentity,
} from "./common-processing-workbench";
import {
  documentIsPolymerDma,
  documentMatchesDataTrack,
  manualModulusDisplayValue,
  manualModulusPascals,
} from "./features/modeling/model/processing-registry";

describe("Governed DMA/FLD Data boundaries", () => {
  const document = (semantics: string[]) => ({
    channels: semantics.map((quantity_semantics) => ({ quantity_semantics })),
    method: "bounded governed import",
  }) as never;

  it("shows source-v2 DMA semantics in Data without enabling the Prony Fit adapter", () => {
    const dma = document([
      "physics.temperature",
      "frequency.cyclic",
      "mechanics.modulus.storage",
      "mechanics.modulus.loss",
    ]);
    expect(documentMatchesDataTrack(dma, "polymer")).toBe(true);
    expect(documentIsPolymerDma(dma)).toBe(false);
  });

  it("keeps governed FLD as first-class Metal Data without treating it as tensile Fit input", () => {
    const fld = document(["mechanics.strain.minor", "mechanics.strain.major"]);
    expect(documentMatchesDataTrack(fld, "metal")).toBe(true);
    expect(documentMatchesDataTrack(fld, "polymer")).toBe(false);
  });
});

describe("Fit surface state mapping", () => {
  const base = {
    previewBusy: false,
    usablePreview: false,
    verifiedSavedFit: false,
    fitHistoryExists: false,
  };

  it("keeps calculating and saved-current precedence exact", () => {
    expect(fitSurfaceState({ ...base, previewBusy: true, usablePreview: true })).toBe("calculating");
    expect(fitSurfaceState({ ...base, usablePreview: true, verifiedSavedFit: true })).toBe("saved-current");
    expect(fitSurfaceState({ ...base, usablePreview: true, verifiedSavedFit: false })).toBe("preview-not-saved");
  });

  it("distinguishes stale history from an uncalculated source", () => {
    expect(fitSurfaceState({ ...base, fitHistoryExists: true })).toBe("saved-result-stale");
    expect(fitSurfaceState(base)).toBe("not-calculated");
  });
});

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json", ...headers }),
    json: async () => body,
  } as Response;
}

function isFitMethodInRequest(methodId: string | undefined): boolean {
  return Boolean(methodId && (methodId.includes("hardening_fit") || methodId.includes("prony_fit") || methodId.includes("fit_compare")));
}

function processRailIdentities(): string[] {
  return Array.from(document.querySelectorAll(".modeling-workspace-stage-process .curve-row-label"), (row) =>
    (row.textContent ?? "").replace(/\s+/g, " ").trim(),
  );
}

function processRailButton(identity: string): HTMLElement {
  const row = Array.from(document.querySelectorAll<HTMLElement>(".modeling-workspace-stage-process .curve-row-label"))
    .find((candidate) => (candidate.textContent ?? "").replace(/\s+/g, " ").trim() === identity);
  if (!row) throw new Error(`Process rail identity is missing: ${identity}`);
  return row;
}

function reverseJsonObjectKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(reverseJsonObjectKeys);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .reverse()
        .map(([key, nested]) => [key, reverseJsonObjectKeys(nested)]),
    );
  }
  return value;
}

const revision = {
  id: "53000000-0000-4000-8000-000000000001",
  aggregate_id: "53000000-0000-4000-8000-000000000002",
  revision_no: 1,
  based_on_revision_id: null,
  schema_id: "urn:cmp:test-data:1.0.0",
  schema_version: "1.0.0",
  content_hash: "a".repeat(64),
  created_at: "2026-07-18T00:00:00Z",
  created_by: "53000000-0000-4000-8000-000000000003",
  change_reason: "demo",
  organization_id: "53000000-0000-4000-8000-000000000004",
  project_id: "53000000-0000-4000-8000-000000000005",
  classification: "internal",
  lifecycle_state: "draft",
};

const ensembleCurveDefinition = {
  definition_version: "1.0.0",
  channels: [{
    key: "strain.engineering",
    label: "Engineering strain",
    quantity_semantics: "strain.engineering",
    axis_role: "independent",
    unit_contract: "common",
    dimension: "strain",
    original_units: [{ unit: "1", scale_to_normalized: "1", offset_to_normalized: "0" }],
    normalized_unit: "1",
    display_unit: "1",
    display_scale: "1",
    display_offset: "0",
    value_basis: "normalized",
  }, {
    key: "stress.engineering",
    label: "Engineering stress",
    quantity_semantics: "stress.engineering",
    axis_role: "dependent",
    unit_contract: "common",
    dimension: "force_per_area",
    original_units: [{ unit: "MPa", scale_to_normalized: "1000000", offset_to_normalized: "0" }],
    normalized_unit: "Pa",
    display_unit: "MPa",
    display_scale: "0.000001",
    display_offset: "0",
    value_basis: "normalized",
  }],
  deviations: (["lower", "upper"] as const).map((direction) => ({
    key: `stress.engineering.mean_ci_95_${direction}`,
    target_channel_key: "stress.engineering",
    scope: "pointwise",
    kind: "confidence_bound",
    method_id: "normal_approximation.mean_two_sided",
    method_version: "1.0.0",
    unit: "Pa",
    bound_direction: direction,
    band_group: "stress.engineering.mean_ci_95",
    scalar_value: null,
    series_key: `stress.engineering.mean_ci_95_${direction}.values`,
    source_count: 2,
    source_count_series_key: null,
    confidence_level: 0.95,
    coverage: "pointwise",
    ddof: 1,
    quantile_probability: null,
    quantile_method: null,
  })),
};

describe("manual Young's modulus unit conversion", () => {
  it("stores GPa input in canonical Pa", () => {
    expect(manualModulusPascals(205, "GPa")).toBe(205_000_000_000);
    expect(manualModulusDisplayValue(205_000_000_000, "GPa")).toBe(205);
  });

  it("stores MPa input in the same canonical Pa", () => {
    expect(manualModulusPascals(205_000, "MPa")).toBe(205_000_000_000);
    expect(manualModulusDisplayValue(205_000_000_000, "MPa")).toBe(205_000);
  });
});
const documentResource = {
  test_data_document_id: "53000000-0000-4000-8000-000000000002",
  current_revision: revision,
  document_key: "DP600-TENSILE-01",
  material_maker: "CMP Demo Metals",
  material_grade: "DP600",
  lot_batch: null,
  test_date: "2026-07-18",
  operator: "Tester",
  laboratory: "Lab",
  method: "tensile",
  specimen_id: "S-1",
  point_count: 3,
  canonical_artifact_id: "53000000-0000-4000-8000-000000000006",
  canonical_sha256: "b".repeat(64),
  normalized_artifact_id: "53000000-0000-4000-8000-000000000007",
  normalized_sha256: "c".repeat(64),
  channels: [
    {
      key: "engineering_strain",
      name: "Engineering strain",
      quantity_semantics: "mechanics.strain.engineering",
      axis_role: "independent",
      original_unit_string: "%",
      normalized_unit: "1",
      point_count: 3,
      missing_count: 0,
    },
    {
      key: "engineering_stress",
      name: "Engineering stress",
      quantity_semantics: "mechanics.stress.engineering",
      axis_role: "dependent",
      original_unit_string: "MPa",
      normalized_unit: "Pa",
      point_count: 3,
      missing_count: 0,
    },
  ],
  governed_source: {
    material: { aggregate_id: "material-a", revision_id: "material-a-r1" },
    material_state: { aggregate_id: "state-a", revision_id: "state-a-r1" },
    test_run: { aggregate_id: "run-a", revision_id: "run-a-r1" },
  },
};

const replicateResource = {
  ...documentResource,
  test_data_document_id: "53000000-0000-4000-8000-000000000012",
  current_revision: {
    ...revision,
    id: "53000000-0000-4000-8000-000000000011",
    aggregate_id: "53000000-0000-4000-8000-000000000012",
    content_hash: "f".repeat(64),
  },
  document_key: "DP600-TENSILE-02",
  specimen_id: "S-2",
  canonical_artifact_id: "53000000-0000-4000-8000-000000000016",
  canonical_sha256: "1".repeat(64),
  normalized_artifact_id: "53000000-0000-4000-8000-000000000017",
  normalized_sha256: "2".repeat(64),
};

const documentJson = {
  document_type: "cmp.test-data",
  schema_version: "1.0.0",
  document_id: "DP600-TENSILE-01",
};

const mappingProfileResource = {
  mapping_profile_id: "53000000-0000-4000-8000-000000000020",
  current_revision: {
    ...revision,
    id: "53000000-0000-4000-8000-000000000021",
    aggregate_id: "53000000-0000-4000-8000-000000000020",
    content_hash: "e".repeat(64),
  },
  content: {
    profile_key: "demo-metal-tensile",
    label: "Demo metal tensile mapping",
    independent_quantity: "strain.engineering",
    missing_data_policy: "drop_any",
    bindings: [
      {
        channel_key: "engineering_strain",
        target_quantity: "strain.engineering",
        accepted_normalized_units: ["1"],
        required: true,
        scale: 1,
        offset: 0,
      },
      {
        channel_key: "engineering_stress",
        target_quantity: "stress.engineering",
        accepted_normalized_units: ["Pa"],
        required: true,
        scale: 1,
        offset: 0,
      },
    ],
    attribute_bindings: [],
  },
};

function processPreviewFixture(scalarPa = 210e9) {
  return {
    execution_mode: "preview",
    promotable: false,
    source_document_sha256: "d".repeat(64),
    mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
    independent_quantity: "strain.engineering",
    stages: [
      {
        ordinal: 0,
        method_id: "mapping",
        method_version: "1.0.0",
        point_count: 3,
        series: [
          { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
          { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
        ],
        diagnostics: [],
        scalar_results: [],
      },
      {
        ordinal: 1,
        method_id: "metal.elastic_modulus",
        method_version: "1.0.0",
        point_count: 3,
        series: [
          { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
          { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
        ],
        diagnostics: [],
        scalar_results: [{ key: "youngs_modulus", quantity_semantics: "modulus.young", value: scalarPa, unit: "Pa" }],
      },
    ],
  };
}

function processOutputFixture(
  id: string,
  label: string,
  method: "robust_huber" | "chord" = "robust_huber",
): Record<string, unknown> {
  return {
    processing_output_id: id,
    current_revision: { ...revision, id: `${id}-revision`, aggregate_id: id },
    label,
    source_document: { aggregate_id: documentResource.test_data_document_id, revision_id: revision.id },
    source_document_sha256: "d".repeat(64),
    source_canonical_artifact_sha256: "e".repeat(64),
    mapping_profile: { aggregate_id: mappingProfileResource.mapping_profile_id, revision_id: mappingProfileResource.current_revision.id },
    mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
    steps: [{
      method_id: "metal.elastic_modulus",
      method_version: "1.0.0",
      options: { method, minimum_strain: method === "chord" ? 0.001 : 0.0002, maximum_strain: method === "chord" ? 0.003 : 0.002 },
    }],
    independent_quantity: "strain.engineering",
    stage_count: 1,
    final_point_count: 3,
    output_artifact_id: `${id}-artifact`,
    output_sha256: "f".repeat(64),
    workup_overrides: [],
    fit_decision: null,
    export_provenance: null,
  };
}

describe("Fit rail exact identities", () => {
  it("uses the pinned revision rather than the library current head", () => {
    expect(fitRailIdentity("Specimen 01", 7, 2)).toBe("Specimen 01 · r2");
    expect(fitRailIdentity("sample-03", 4, 1)).toBe("Specimen 03 · r1");
  });
});

function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function fitRestorePreview(marker: string): Record<string, unknown> {
  const methodId = marker === "A" ? "metal.proof_stress" : "metal.hardening_fit_extrapolate";
  const stage = (ordinal: number, method_id: string) => ({
    ordinal,
    method_id,
    method_version: "1.0.0",
    point_count: 2,
    series: [
      { quantity: "strain.engineering", unit: "1", values: [0, 0.001] },
      { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8] },
    ],
    diagnostics: [marker],
    scalar_results: [],
  });
  return {
    execution_mode: "preview",
    promotable: false,
    source_document_sha256: "d".repeat(64),
    mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
    independent_quantity: "strain.engineering",
    stages: [stage(0, "mapping"), stage(1, methodId)],
  };
}

function metalFitCalculationPreview(): Record<string, unknown> {
  const stage = (ordinal: number, method_id: string, scalar_results: Array<Record<string, unknown>> = []) => ({
    ordinal,
    method_id,
    method_version: "1.0.0",
    point_count: 2,
    series: [
      { quantity: "strain.engineering", unit: "1", values: [0, 0.001] },
      { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8] },
    ],
    diagnostics: [],
    scalar_results,
  });
  return {
    execution_mode: "preview",
    promotable: false,
    source_document_sha256: "d".repeat(64),
    mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
    independent_quantity: "strain.engineering",
    stages: [
      stage(0, "mapping"),
      stage(1, "rows.sort_unique"),
      stage(2, "metal.elastic_modulus"),
      stage(3, "metal.proof_stress"),
      stage(4, "metal.necking_candidate"),
      stage(5, "metal.engineering_to_true_plastic"),
      stage(6, "metal.hardening_fit_extrapolate", [
        { key: "swift.relative_rmse", quantity_semantics: "statistics.relative_rmse", value: 0.01, unit: "1" },
        { key: "swift.parameter.K", quantity_semantics: "model.parameter.K", value: 5e8, unit: "Pa" },
        { key: "swift.parameter.K.lower", quantity_semantics: "model.parameter.bound.lower.K", value: 1, unit: "Pa" },
        { key: "swift.parameter.K.upper", quantity_semantics: "model.parameter.bound.upper.K", value: 1e9, unit: "Pa" },
      ]),
    ],
  };
}

function fitRestoreFixtures(): {
  process: Record<string, unknown>;
  fit: Record<string, unknown>;
  session: Record<string, unknown>;
  material: Record<string, unknown>;
  materialState: Record<string, unknown>;
} {
  const process = processOutputFixture("restore-process-output", "Restored Process source");
  const processRevision = process.current_revision as Record<string, unknown>;
  const fit = {
    ...process,
    processing_output_id: "restore-fit-output",
    current_revision: {
      ...processRevision,
      id: "restore-fit-output-revision",
      aggregate_id: "restore-fit-output",
    },
    label: "Restored Fit output",
    steps: [
      ...(process.steps as Array<Record<string, unknown>>),
      { method_id: "metal.hardening_fit_extrapolate", method_version: "1.0.0", options: { law: "swift" } },
    ],
    stage_count: 2,
    output_artifact_id: "restore-fit-output-artifact",
    output_sha256: "9".repeat(64),
    source_processing_output: {
      aggregate_id: process.processing_output_id,
      revision_id: processRevision.id,
    },
    source_processing_output_sha256: process.output_sha256,
    fit_decision: null,
  };
  const sourceRef = {
    id: documentResource.test_data_document_id,
    revisionId: revision.id,
    label: documentResource.document_key,
    revisionNo: 1,
  };
  const profileRef = {
    id: mappingProfileResource.mapping_profile_id,
    revisionId: mappingProfileResource.current_revision.id,
    label: mappingProfileResource.content.label,
    revisionNo: 1,
  };
  const session = {
    version: 4,
    updatedAt: "2026-07-24T00:00:00Z",
    materialFamily: "metal",
    objective: "Restore exact Fit output",
    material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
    materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
    testData: sourceRef,
    mappingProfile: profileRef,
    processingOutput: {
      id: fit.processing_output_id,
      revisionId: (fit.current_revision as Record<string, unknown>).id,
      label: fit.label,
      revisionNo: 1,
    },
    workspace: {
      activeStage: "fit",
      selectedDocumentIds: [sourceRef.id],
      selectedTestDataRefs: [sourceRef],
      visibleTestDataKeys: [`${sourceRef.id}:${sourceRef.revisionId}`],
      selectedStepIndex: 0,
      selectedStageOrdinal: 1,
      plotView: "pipeline",
      settingsOpen: true,
    },
  };
  return {
    process,
    fit,
    session,
    material: { material_id: "material-a", current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } } },
    materialState: { material_state_id: "state-a", current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } } },
  };
}

function installFitRestoreParserMock(): void {
  vi.doMock("./modeling-fit-output", () => ({
    readVerifiedExactOutput: async (result: { data: { blob: Blob } }) => result.data.blob.text(),
    parseExactSavedFitOutput: (text: string) => ({ preview: fitRestorePreview(text), selection: null }),
  }));
}

function fitRestoreContentResponse(marker: string, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/vnd.cmp.processing-output+json" }),
    blob: async () => new Blob([marker], { type: "application/json" }),
    json: async () => ({ detail: marker }),
  } as Response;
}

function stubFitRestoreFetch(outputs: Array<Record<string, unknown>> | (() => Array<Record<string, unknown>>)): {
  contentGets: () => number;
  fitRunPosts: () => number;
  pendingContent: Array<ReturnType<typeof deferred<Response>>>;
} {
  let contentGetCount = 0;
  let fitRunPostCount = 0;
  const pendingContent: Array<ReturnType<typeof deferred<Response>>> = [];
  const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource] });
    if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
    if (url.endsWith("/processing-methods")) return jsonResponse({ items: [
      ...processMethodFixtures(),
      { method_id: "metal.hardening_fit_extrapolate", version: "1.0.0", label: "Hardening fit", description: "Hardening fit", option_schema: {}, deterministic: true, allows_extrapolation: true },
    ] });
    if (url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
    if (url.includes("/processing-outputs/") && url.endsWith("/content")) {
      contentGetCount += 1;
      const next = deferred<Response>();
      pendingContent.push(next);
      return next.promise;
    }
    if (url.endsWith("/processing-outputs")) {
      const currentOutputs = typeof outputs === "function" ? outputs() : outputs;
      return jsonResponse({ items: currentOutputs.map((item) => JSON.parse(JSON.stringify(item))) });
    }
    if (url.endsWith("/metal-fit-runs") && init?.method === "POST") {
      fitRunPostCount += 1;
      return jsonResponse({
        id: "unexpected-auto-fit-run",
        status: "succeeded",
        preview: fitRestorePreview("auto-preview"),
        failure_code: null,
        failure_reason: null,
      });
    }
    if (url.includes("/test-data-documents/") && url.endsWith("/content")) return fitRestoreContentResponse(JSON.stringify(documentJson));
    throw new Error(`unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return {
    contentGets: () => contentGetCount,
    fitRunPosts: () => fitRunPostCount,
    pendingContent,
  };
}

function processMethodFixtures() {
  return [
    ["rows.sort_unique", "Sort and resolve duplicate x values"],
    ["metal.elastic_modulus", "Young's modulus"],
    ["metal.proof_stress", "Proof stress"],
    ["metal.necking_candidate", "Necking candidate"],
    ["metal.engineering_to_true_plastic", "True/plastic conversion"],
  ].map(([method_id, label]) => ({ method_id, version: "1.0.0", label, description: label, option_schema: {}, deterministic: true, allows_extrapolation: false }));
}

describe("Common Processing Workbench", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("keeps Data Mapping Profile identity and JSON synchronized when selecting a saved revision", async () => {
    const session = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Edit a mapping profile",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: undefined,
      mappingProfile: {
        id: mappingProfileResource.mapping_profile_id,
        revisionId: mappingProfileResource.current_revision.id,
        label: mappingProfileResource.content.label,
        revisionNo: 1,
      },
      workspace: {
        activeStage: "data",
        selectedDocumentIds: [],
        selectedTestDataRefs: [],
        visibleTestDataKeys: [],
        selectedStepIndex: 0,
        selectedStageOrdinal: 0,
        plotView: "pipeline",
        settingsOpen: true,
      },
    };
    const material = { material_id: "material-a", current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } } };
    const materialState = { material_state_id: "state-a", current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } } };
    const onSessionEvent = vi.fn();
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: processMethodFixtures() });
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.includes("/material-states/") && url.endsWith("/test-runs")) return jsonResponse({ items: [] });
      if (url.endsWith("/import-profiles")) return jsonResponse({ items: [] });
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const view = render(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={session as never}
        material={material as never}
        materialState={materialState as never}
        locationSearch="?stage=data&family=metal"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
        onSessionEvent={onSessionEvent}
      />,
    );
    try {
      const savedProfile = await screen.findByLabelText("Saved Mapping Profile");
      await waitFor(() => expect((savedProfile as HTMLSelectElement).value).toBe(mappingProfileResource.mapping_profile_id));
      fireEvent.click(screen.getByText("Advanced source settings"));
      const profileJson = screen.getByLabelText("Mapping Profile JSON") as HTMLTextAreaElement;
      expect(JSON.parse(profileJson.value)).toMatchObject({ profile_key: mappingProfileResource.content.profile_key });
      fireEvent.change(savedProfile, { target: { value: "" } });
      expect(onSessionEvent).toHaveBeenLastCalledWith({ type: "CHANGE_MAPPING" });
      fireEvent.change(savedProfile, { target: { value: mappingProfileResource.mapping_profile_id } });
      await waitFor(() => expect(JSON.parse(profileJson.value)).toMatchObject({ profile_key: mappingProfileResource.content.profile_key }));
      expect(onSessionEvent).toHaveBeenLastCalledWith({
        type: "CHANGE_MAPPING",
        mappingProfile: {
          id: mappingProfileResource.mapping_profile_id,
          revisionId: mappingProfileResource.current_revision.id,
          label: mappingProfileResource.content.label,
          revisionNo: 1,
        },
      });
      await screen.findByLabelText("Test Data revision");
      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(9));
    } finally {
      view.unmount();
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  });

  it("preserves the valid Process preview and save fields across a failed output POST, then retries once", async () => {
    const sourceRef = { id: documentResource.test_data_document_id, revisionId: revision.id, label: documentResource.document_key, revisionNo: 1 };
    const session = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Retry a failed Process save",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: sourceRef,
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      workspace: {
        activeStage: "process",
        selectedDocumentIds: [sourceRef.id],
        selectedTestDataRefs: [sourceRef],
        visibleTestDataKeys: [`${sourceRef.id}:${sourceRef.revisionId}`],
        selectedStepIndex: 1,
        selectedStageOrdinal: 1,
        plotView: "pipeline",
        settingsOpen: true,
      },
    };
    const material = { material_id: "material-a", current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } } };
    const materialState = { material_state_id: "state-a", current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } } };
    let failOutputPost = true;
    let outputPosts = 0;
    const committed: Record<string, unknown>[] = [];
    const onSessionChange = vi.fn();
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: processMethodFixtures() });
      if (url.endsWith("/processing-outputs") && init?.method === "POST") {
        outputPosts += 1;
        if (failOutputPost) return jsonResponse({ detail: "forced Process output failure" }, 503);
        const body = JSON.parse(String(init.body ?? "{}")) as Record<string, unknown>;
        const saved = processOutputFixture("process-retry-output", String(body.label ?? "Processed result"));
        committed.push(saved);
        return jsonResponse(saved, 201);
      }
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: committed });
      if (url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.includes("/test-data-documents/") && url.endsWith("/content")) return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
      } as Response;
      if (url.endsWith("/processing:preview") && init?.method === "POST") return jsonResponse(processPreviewFixture());
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={session as never}
        material={material as never}
        materialState={materialState as never}
        locationSearch="?stage=process&family=metal"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
      />,
    );
    // The Process panel is a lazy chunk; the full parallel Vitest suite can
    // take longer than Testing Library's 1 s default even though the settled
    // panel and mocked requests are correct.
    await screen.findByRole(
      "button",
      { name: "Save processed curves" },
      { timeout: 5_000 },
    );
    await waitFor(() => expect(screen.getByText("Preview ready.", { exact: false })).toBeTruthy());
    const label = screen.getByRole("textbox", { name: "Processed curve label" }) as HTMLInputElement;
    const reason = screen.getByRole("textbox", { name: "Save reason" }) as HTMLInputElement;
    fireEvent.change(label, { target: { value: "Retry-preserved label" } });
    fireEvent.change(reason, { target: { value: "Retry-preserved reason" } });
    const save = screen.getByRole("button", { name: "Save processed curves" }) as HTMLButtonElement;
    fireEvent.click(save);
    await screen.findByText("forced Process output failure");
    expect(label.value).toBe("Retry-preserved label");
    expect(reason.value).toBe("Retry-preserved reason");
    expect(save.disabled).toBe(false);
    expect(screen.getByText("210.0 GPa")).toBeTruthy();
    expect(committed).toHaveLength(0);
    expect(onSessionChange.mock.calls.some(([patch]) => (patch as Record<string, unknown>).processingOutput !== undefined)).toBe(false);
    failOutputPost = false;
    fireEvent.click(save);
    await waitFor(() => expect(committed).toHaveLength(1));
    expect(outputPosts).toBe(2);
    expect(screen.getByText("Processed result saved and current", { exact: false })).toBeTruthy();
    expect(onSessionChange.mock.calls.filter(([patch]) => (patch as Record<string, unknown>).processingOutput !== undefined)).toHaveLength(1);
  });

  it("adds toe compensation explicitly, preserves last-valid evidence, and gates warning save", async () => {
    const sourceRef = { id: documentResource.test_data_document_id, revisionId: revision.id, label: documentResource.document_key, revisionNo: 1 };
    const session = {
      version: 4,
      updatedAt: "2026-08-13T00:00:00Z",
      materialFamily: "metal",
      objective: "Review explicit toe compensation",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: sourceRef,
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      workspace: {
        activeStage: "process",
        selectedDocumentIds: [sourceRef.id],
        selectedTestDataRefs: [sourceRef],
        visibleTestDataKeys: [`${sourceRef.id}:${sourceRef.revisionId}`],
        selectedStepIndex: 1,
        selectedStageOrdinal: 1,
        plotView: "pipeline",
        settingsOpen: true,
      },
    };
    const material = { material_id: "material-a", current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } } };
    const materialState = { material_state_id: "state-a", current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } } };
    let committedBody: Record<string, unknown> | null = null;
    let committedOutput: Record<string, unknown> | null = null;
    const previewBodies: Array<{ steps: Array<{ method_id: string; options: Record<string, unknown> }> }> = [];
    const curveStage = (ordinal: number, method_id: string) => ({
      ordinal,
      method_id,
      method_version: "1.0.0",
      point_count: 6,
      series: [
        { quantity: "strain.engineering", unit: "1", values: [-0.0003, 0.0001, 0.0005, 0.0009, 0.0013, 0.0017] },
        { quantity: "stress.engineering", unit: "Pa", values: [0, 30e6, 170e6, 115e6, 390e6, 300e6] },
      ],
      diagnostics: method_id === "tensile.toe_zero_intercept" ? [
        "toe.method=tensile.toe_zero_intercept@1.0.0",
        "toe.domain=[0.0002,0.0022];points=6;equipment_compliance=not_provided",
        "toe.fit=slope_pa=180000000000;intercept_pa=-54000000;offset_strain=0.0003;r_squared=0.91",
        "toe.warning.low_linearity:r_squared=0.91;threshold=0.995",
      ] : [],
      scalar_results: method_id === "tensile.toe_zero_intercept" ? [
        { key: "toe_estimated_slope", quantity_semantics: "modulus.young", value: 180e9, unit: "Pa" },
        { key: "toe_intercept", quantity_semantics: "stress.intercept", value: -54e6, unit: "Pa" },
        { key: "toe_strain_offset", quantity_semantics: "strain.offset", value: 0.0003, unit: "1" },
        { key: "toe_r_squared", quantity_semantics: "statistics.r_squared", value: 0.91, unit: "1" },
        { key: "toe_estimation_point_count", quantity_semantics: "count.points", value: 6, unit: "1" },
      ] : method_id === "metal.elastic_modulus" ? [
        { key: "youngs_modulus", quantity_semantics: "modulus.young", value: 210e9, unit: "Pa" },
      ] : [],
    });
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: [
        ...processMethodFixtures(),
        { method_id: "tensile.toe_zero_intercept", version: "1.0.0", label: "Tensile toe compensation", description: "Explicit OLS zero intercept", option_schema: {}, deterministic: true, allows_extrapolation: false },
      ] });
      if (url.endsWith("/processing-outputs") && init?.method === "POST") {
        committedBody = JSON.parse(String(init.body ?? "{}")) as Record<string, unknown>;
        committedOutput = {
          ...processOutputFixture("toe-output", "Toe-corrected Process"),
          steps: committedBody.steps,
        };
        return jsonResponse(committedOutput, 201);
      }
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: committedOutput ? [committedOutput] : [] });
      if (url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.includes("/test-data-documents/") && url.endsWith("/content")) return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
      } as Response;
      if (url.endsWith("/processing:preview") && init?.method === "POST") {
        const body = JSON.parse(String(init.body ?? "{}")) as { steps: Array<{ method_id: string; options: Record<string, unknown> }> };
        previewBodies.push(body);
        return jsonResponse({
          execution_mode: "preview",
          promotable: false,
          source_document_sha256: "d".repeat(64),
          mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
          independent_quantity: "strain.engineering",
          stages: [curveStage(0, "mapping"), ...body.steps.map((step, index) => curveStage(index + 1, step.method_id))],
        });
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={session as never}
        material={material as never}
        materialState={materialState as never}
        locationSearch="?stage=process&family=metal"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
      />,
    );

    const toeButton = await screen.findByRole("button", { name: "Add tensile toe compensation" }, { timeout: 5_000 }) as HTMLButtonElement;
    await waitFor(() => expect(toeButton.disabled).toBe(false));
    expect((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value).not.toContain("tensile.toe_zero_intercept");
    fireEvent.click(toeButton);
    await waitFor(() => expect((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value).toContain("tensile.toe_zero_intercept"));
    let steps = JSON.parse((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value) as Array<{ method_id: string; options: Record<string, unknown> }>;
    expect(steps.map((step) => step.method_id).slice(0, 3)).toEqual([
      "rows.sort_unique",
      "tensile.toe_zero_intercept",
      "metal.elastic_modulus",
    ]);
    expect(steps[1].options).toMatchObject({ equipment_compliance: "not_provided", warning_acknowledged: false });

    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await screen.findByText("OLS zero intercept · v1.0.0");
    expect(screen.getByText("1 quality warning · acknowledgement required")).toBeTruthy();
    expect(screen.getByText("Warning reviewed")).toBeTruthy();
    expect(screen.getByText("180.00 GPa")).toBeTruthy();
    expect(screen.getByText("0.910000")).toBeTruthy();
    const save = screen.getByRole("button", { name: "Save processed curves" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    expect(screen.getByText(/Review and acknowledge the toe quality warning/)).toBeTruthy();
    expect(screen.getByRole("img", { name: /mapped and selected processing stage curve overlay/i })).toBeTruthy();

    fireEvent.click(screen.getByRole("checkbox", { name: "Acknowledge toe quality warning" }));
    steps = JSON.parse((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value) as Array<{ method_id: string; options: Record<string, unknown> }>;
    expect(steps[1].options.warning_acknowledged).toBe(true);
    expect(save.disabled).toBe(true);
    expect(screen.getByText("Result retained; preview again to save changes.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(save.disabled).toBe(false));

    fireEvent.change(screen.getByLabelText("Toe estimation range start"), { target: { value: "0.00025" } });
    steps = JSON.parse((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value) as Array<{ method_id: string; options: Record<string, unknown> }>;
    expect(steps[1].options.warning_acknowledged).toBe(false);
    expect(save.disabled).toBe(true);

    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:undo" } }));
    steps = JSON.parse((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value) as Array<{ method_id: string; options: Record<string, unknown> }>;
    expect(steps[1].options.minimum_strain).toBe(0);
    expect(steps[1].options.warning_acknowledged).toBe(false);
    const previewCountBeforeUndoPreview = previewBodies.length;
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(previewBodies).toHaveLength(previewCountBeforeUndoPreview + 1));
    expect(save.disabled).toBe(true);
    fireEvent.click(screen.getByRole("checkbox", { name: "Acknowledge toe quality warning" }));
    expect(save.disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(save.disabled).toBe(false));

    steps = JSON.parse((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value) as Array<{ method_id: string; options: Record<string, unknown> }>;
    steps[1].options.minimum_strain = 0.0003;
    steps[1].options.warning_acknowledged = true;
    fireEvent.change(screen.getByLabelText("Ordered processing steps"), {
      target: { value: JSON.stringify(steps, null, 2) },
    });
    steps = JSON.parse((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value) as Array<{ method_id: string; options: Record<string, unknown> }>;
    expect(steps[1].options.warning_acknowledged).toBe(false);
    expect(save.disabled).toBe(true);
    fireEvent.click(screen.getByRole("checkbox", { name: "Acknowledge toe quality warning" }));
    expect(save.disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(save.disabled).toBe(false));
    fireEvent.click(save);
    await waitFor(() => expect(committedBody).not.toBeNull());
    const committedSteps = (committedBody as unknown as Record<string, unknown>).steps as Array<{ method_id: string; options: Record<string, unknown> }>;
    expect(committedSteps[1]).toMatchObject({
      method_id: "tensile.toe_zero_intercept",
      options: { minimum_strain: 0.0003, warning_acknowledged: true, equipment_compliance: "not_provided" },
    });
    expect(previewBodies.at(-1)?.steps[1].options.warning_acknowledged).toBe(true);

    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:fit" } }));
    const fitEvidence = await screen.findByRole("button", { name: "Candidate parameters" });
    fireEvent.click(fitEvidence);
    expect(await screen.findByTitle("Toe-corrected Process · r1")).toBeTruthy();
    expect(screen.getByText("OLS zero intercept · v1.0.0", { selector: ".fit-source-evidence strong" }).closest("dd")?.textContent).toBe(
      "OLS zero intercept · v1.0.0 · exact saved Process step",
    );
  });

  it("restores history settings as a draft while preserving the saved Process current across rerender and reload", async () => {
    const sourceRef = { id: documentResource.test_data_document_id, revisionId: revision.id, label: documentResource.document_key, revisionNo: 1 };
    const initialSession = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Restore history settings without replacing Process current",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: sourceRef,
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      workspace: {
        activeStage: "process",
        selectedDocumentIds: [sourceRef.id],
        selectedTestDataRefs: [sourceRef],
        visibleTestDataKeys: [`${sourceRef.id}:${sourceRef.revisionId}`],
        selectedStepIndex: 1,
        selectedStageOrdinal: 1,
        plotView: "pipeline",
        settingsOpen: true,
      },
    };
    const material = { material_id: "material-a", current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } } };
    const materialState = { material_state_id: "state-a", current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } } };
    const serverOutputs = [
      processOutputFixture("process-history-robust", "Robust history"),
      processOutputFixture("process-history-chord", "Chord history", "chord"),
    ];
    let outputPosts = 0;
    let previewPosts = 0;
    let observedPreviewPosts = 0;
    let restoredSession: Record<string, unknown> = initialSession;
    const onSessionChange = vi.fn();
    const onSessionEvent = vi.fn();
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: processMethodFixtures() });
      if (url.endsWith("/processing-outputs") && init?.method === "POST") {
        outputPosts += 1;
        const body = JSON.parse(String(init.body ?? "{}")) as Record<string, unknown>;
        const saved = processOutputFixture(`process-saved-${outputPosts}`, String(body.label ?? "New Process"));
        serverOutputs.push(saved);
        return jsonResponse(saved, 201);
      }
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: serverOutputs });
      if (url.includes("/processing-outputs/") && url.endsWith("/content")) {
        const outputId = decodeURIComponent(url.split("/processing-outputs/")[1].split("/content")[0]);
        const saved = serverOutputs.find((item) => item.processing_output_id === outputId);
        const method = (saved?.steps as Array<{ options?: { method?: string } }> | undefined)?.[0]?.options?.method;
        const artifact = {
          document_type: "cmp.processing-output",
          output_id: outputId,
          source_document: saved?.source_document,
          mapping_profile: saved?.mapping_profile,
          steps: saved?.steps,
          result: { stages: [{ scalar_results: [{ key: "youngs_modulus", value: method === "chord" ? 120e9 : 210e9, unit: "Pa" }] }] },
        };
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/vnd.cmp.processing-output+json" }),
          blob: async () => new Blob([JSON.stringify(artifact)], { type: "application/json" }),
        } as Response;
      }
      if (url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.includes("/test-data-documents/") && url.endsWith("/content")) return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
      } as Response;
      if (url.endsWith("/processing:preview") && init?.method === "POST") {
        const body = JSON.parse(String(init.body ?? "{}")) as { steps?: Array<{ options?: { method?: string } }> };
        if (body.steps?.length) previewPosts += 1;
        else observedPreviewPosts += 1;
        const scalarPa = body.steps?.find((step) => step.options?.method === "chord") ? 120e9 : 210e9;
        return jsonResponse(processPreviewFixture(scalarPa));
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const renderWorkbench = (session: Record<string, unknown>) => render(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={session as never}
        material={material as never}
        materialState={materialState as never}
        locationSearch="?stage=process&family=metal"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
        onSessionEvent={onSessionEvent as never}
      />,
    );

    let view = renderWorkbench(restoredSession);
    await screen.findByRole("button", { name: "Save processed curves" });
    await waitFor(() => expect(screen.getByText("Preview ready.", { exact: false })).toBeTruthy());
    fireEvent.change(screen.getByRole("textbox", { name: "Processed curve label" }), { target: { value: "New Process" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Save reason" }), { target: { value: "Persist a current Process result" } });
    fireEvent.click(screen.getByRole("button", { name: "Save processed curves" }));
    await waitFor(() => expect(serverOutputs).toHaveLength(3));
    const saved = serverOutputs[2] as Record<string, unknown>;
    const savedRevision = saved.current_revision as Record<string, unknown>;
    const savedRef = { id: saved.processing_output_id as string, revisionId: savedRevision.id as string, label: saved.label as string, revisionNo: 1 };
    expect(onSessionChange).toHaveBeenCalledWith({ processingOutput: savedRef });

    view.unmount();
    restoredSession = { ...initialSession, processingOutput: savedRef };
    view = renderWorkbench(restoredSession);
    await screen.findByRole("button", { name: "Save processed curves" });
    await waitFor(() => expect(screen.getByText("Preview ready.", { exact: false })).toBeTruthy());
    const details = document.querySelector("details.process-saved-results") as HTMLDetailsElement;
    fireEvent.click(details.querySelector(":scope > summary")!);
    await waitFor(() => expect(details.querySelectorAll(".process-comparison-row")).toHaveLength(3));
    await waitFor(() => expect(details.querySelectorAll(".process-comparison-row .text-button")).toHaveLength(3));
    let rows = Array.from(details.querySelectorAll(".process-comparison-row"), (row) => row.textContent ?? "");
    expect(rows.filter((text) => text.includes("current"))).toHaveLength(1);
    expect(rows.find((text) => text.includes("New Process"))).toContain("current");

    const currentRow = Array.from(details.querySelectorAll<HTMLElement>(".process-comparison-row"))
      .find((row) => row.textContent?.includes("New Process"));
    if (!currentRow) throw new Error("restored current Process row is missing");
    const chordRow = Array.from(details.querySelectorAll<HTMLElement>(".process-comparison-row"))
      .find((row) => row.textContent?.includes("Chord history"));
    if (!chordRow) throw new Error("historical Chord Process row is missing");
    const changeProcessEventsBeforeUse = onSessionEvent.mock.calls.filter(
      ([event]) => (event as { type?: string }).type === "CHANGE_PROCESS",
    ).length;
    const previewPostsBeforeUse = previewPosts;
    fireEvent.click(within(chordRow).getByRole("button", { name: "Use settings" }));
    await screen.findByText(/Saved Process settings restored as a new draft/);
    await new Promise((resolve) => window.setTimeout(resolve, 350));
    expect(previewPosts).toBe(previewPostsBeforeUse);
    expect(document.querySelector('[data-modeling-process-panel="ready"] .process-band-result')?.textContent).toContain("210.0 GPa");
    expect(onSessionEvent.mock.calls.filter(
      ([event]) => (event as { type?: string }).type === "CHANGE_PROCESS",
    )).toHaveLength(changeProcessEventsBeforeUse);
    expect(restoredSession.processingOutput).toEqual(savedRef);
    expect((screen.getByRole("combobox", { name: "Evaluation method" }) as HTMLSelectElement).value).toBe("chord");
    expect((screen.getByRole("spinbutton", { name: "Elastic range start" }) as HTMLInputElement).value).toBe("0.001");
    expect((screen.getByRole("spinbutton", { name: "Elastic range end" }) as HTMLInputElement).value).toBe("0.003");
    expect((screen.getByRole("button", { name: "Save processed curves" }) as HTMLButtonElement).disabled).toBe(true);
    rows = Array.from(details.querySelectorAll(".process-comparison-row"), (row) => row.textContent ?? "");
    expect(rows.filter((text) => text.includes("current"))).toHaveLength(1);
    expect(rows.find((text) => text.includes("New Process"))).toContain("current");
    const previewPostsBeforeStageRoundTrip = previewPosts;
    for (const stage of ["data", "fit", "export", "process"] as const) {
      fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: `modeling:${stage}` } }));
      const heading = stage === "data"
        ? "Select Test Data"
        : stage === "fit"
          ? "Fit material response"
          : stage === "export"
            ? "Review & deliver solver card"
            : "Prepare observed curves";
      await screen.findByRole("heading", { name: heading });
    }
    await new Promise((resolve) => window.setTimeout(resolve, 350));
    expect(previewPosts).toBe(previewPostsBeforeStageRoundTrip);
    expect(observedPreviewPosts).toBeGreaterThan(0);
    expect((screen.getByRole("combobox", { name: "Evaluation method" }) as HTMLSelectElement).value).toBe("chord");
    expect((screen.getByRole("spinbutton", { name: "Elastic range start" }) as HTMLInputElement).value).toBe("0.001");
    expect((screen.getByRole("spinbutton", { name: "Elastic range end" }) as HTMLInputElement).value).toBe("0.003");
    expect((screen.getByRole("button", { name: "Save processed curves" }) as HTMLButtonElement).disabled).toBe(true);
    expect(document.querySelector('[data-modeling-process-panel="ready"] .process-band-result')?.textContent).toContain("210.0 GPa");
    const roundTripDetails = document.querySelector("details.process-saved-results") as HTMLDetailsElement;
    rows = Array.from(roundTripDetails.querySelectorAll(".process-comparison-row"), (row) => row.textContent ?? "");
    expect(rows.filter((text) => text.includes("current"))).toHaveLength(1);
    expect(rows.find((text) => text.includes("New Process"))).toContain("current");
    view.rerender(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={restoredSession as never}
        material={material as never}
        materialState={materialState as never}
        locationSearch="?stage=process&family=metal"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
        onSessionEvent={onSessionEvent as never}
      />,
    );
    await waitFor(() => {
      rows = Array.from(document.querySelectorAll(".process-comparison-row"), (row) => row.textContent ?? "");
      expect(rows).toHaveLength(3);
      expect(rows.filter((text) => text.includes("current"))).toHaveLength(1);
      expect(rows.find((text) => text.includes("New Process"))).toContain("current");
    });
    view.unmount();
    view = renderWorkbench(restoredSession);
    await screen.findByRole("button", { name: "Save processed curves" });
    await waitFor(() => expect(screen.getByText("Preview ready.", { exact: false })).toBeTruthy());
    const reloadedDetails = document.querySelector("details.process-saved-results") as HTMLDetailsElement;
    fireEvent.click(reloadedDetails.querySelector(":scope > summary")!);
    await waitFor(() => expect(reloadedDetails.querySelectorAll(".process-comparison-row")).toHaveLength(3));
    await waitFor(() => {
      const reloadedRows = Array.from(reloadedDetails.querySelectorAll(".process-comparison-row"), (row) => row.textContent ?? "");
      expect(reloadedRows.filter((text) => text.includes("current"))).toHaveLength(1);
      expect(reloadedRows.find((text) => text.includes("New Process"))).toContain("current");
    });
    expect(outputPosts).toBe(1);
  });

  it("characterizes exact Data, Process, Fit, and Export continuity with explicit recovery", async () => {
    const committedOutputs: Array<Record<string, unknown>> = [];
    const seededFitOutput: Record<string, unknown> = {
      processing_output_id: "53000000-0000-4000-8000-000000000029",
      current_revision: {
        ...revision,
        id: "53000000-0000-4000-8000-000000000028",
        aggregate_id: "53000000-0000-4000-8000-000000000029",
      },
      label: "DP600 · seeded fit baseline",
      source_document: {
        aggregate_id: replicateResource.test_data_document_id,
        revision_id: replicateResource.current_revision.id,
      },
      source_document_sha256: "0".repeat(64),
      source_canonical_artifact_sha256: "1".repeat(64),
      mapping_profile: {
        aggregate_id: mappingProfileResource.mapping_profile_id,
        revision_id: mappingProfileResource.current_revision.id,
      },
      mapping_profile_sha256: "2".repeat(64),
      steps: [{
        method_id: "metal.hardening_fit_extrapolate",
        method_version: "1.0.0",
        options: { primary_family: "swift" },
      }],
      independent_quantity: "strain.engineering",
      stage_count: 1,
      final_point_count: 3,
      output_artifact_id: "53000000-0000-4000-8000-000000000027",
      output_sha256: "3".repeat(64),
      workup_overrides: [],
      fit_decision: null,
      export_provenance: null,
    };
    const seededProcessOutput: Record<string, unknown> = {
      processing_output_id: "53000000-0000-4000-8000-000000000026",
      current_revision: {
        ...revision,
        id: "53000000-0000-4000-8000-000000000025",
        aggregate_id: "53000000-0000-4000-8000-000000000026",
      },
      label: "DP600 · seeded Process source",
      source_document: {
        aggregate_id: documentResource.test_data_document_id,
        revision_id: revision.id,
      },
      source_document_sha256: "d".repeat(64),
      source_canonical_artifact_sha256: "e".repeat(64),
      mapping_profile: {
        aggregate_id: mappingProfileResource.mapping_profile_id,
        revision_id: mappingProfileResource.current_revision.id,
      },
      mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
      steps: [{
        method_id: "rows.sort_unique",
        method_version: "1.0.0",
        options: {},
      }],
      independent_quantity: "strain.engineering",
      stage_count: 2,
      final_point_count: 3,
      output_artifact_id: "53000000-0000-4000-8000-000000000024",
      output_sha256: "4".repeat(64),
      source_processing_output: null,
      source_processing_output_sha256: null,
      workup_overrides: [],
      fit_decision: null,
      export_provenance: null,
    };
    seededFitOutput.source_processing_output = {
      aggregate_id: seededProcessOutput.processing_output_id,
      revision_id: (seededProcessOutput.current_revision as { id: string }).id,
    };
    seededFitOutput.source_processing_output_sha256 = seededProcessOutput.output_sha256;
    let failNextPreview = false;
    let invalidArtifactId: string | null = null;
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource, replicateResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-outputs") && init?.method === "POST") {
        const body = JSON.parse(String(init.body ?? "{}")) as {
          label?: string;
          source_document?: unknown;
          mapping_profile?: unknown;
          steps?: unknown;
        };
        const outputNumber = 30 + committedOutputs.length;
        const outputId = `53000000-0000-4000-8000-${String(outputNumber).padStart(12, "0")}`;
        const output = {
          processing_output_id: outputId,
          current_revision: {
            ...revision,
            id: `53000000-0000-4000-8000-${String(outputNumber + 1).padStart(12, "0")}`,
            aggregate_id: outputId,
          },
          label: committedOutputs.length === 0 ? "DP600 · swift selected fit" : body.label ?? "Processed result",
          source_document: body.source_document ?? {
            aggregate_id: documentResource.test_data_document_id,
            revision_id: revision.id,
          },
          mapping_profile: body.mapping_profile ?? {
            aggregate_id: mappingProfileResource.mapping_profile_id,
            revision_id: mappingProfileResource.current_revision.id,
          },
          steps: body.steps ?? [],
          output_sha256: String(outputNumber).repeat(64),
          final_point_count: 3,
          stage_count: 6,
        };
        committedOutputs.push(output);
        return jsonResponse(output, 201);
      }
      if (url.includes("/processing-outputs/") && url.endsWith("/content")) {
        const outputId = decodeURIComponent(url.split("/processing-outputs/")[1].split("/content")[0]);
        const output = [seededFitOutput, ...committedOutputs].find((item) => item.processing_output_id === outputId);
        const modulusStep = (output?.steps as Array<{ method_id?: string; options?: { method?: string } }> | undefined)
          ?.find((step) => step.method_id === "metal.elastic_modulus");
        const scalarPa = modulusStep?.options?.method === "chord" ? 120e9 : 210e9;
        const artifact = {
          document_type: "cmp.processing-output",
          output_id: invalidArtifactId === outputId ? "wrong-output" : outputId,
          source_document: output?.source_document,
          mapping_profile: output?.mapping_profile,
          // The released artifact is canonically key-sorted, while the list
          // response preserves request insertion order.  Keep the same
          // structure and array order to exercise order-independent validation.
          steps: reverseJsonObjectKeys(output?.steps),
          result: { stages: [{ scalar_results: [{ key: "youngs_modulus", value: scalarPa, unit: "Pa" }] }] },
        };
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/vnd.cmp.processing-output+json" }),
          blob: async () => new Blob([JSON.stringify(artifact)], { type: "application/json" }),
        } as Response;
      }
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: [seededProcessOutput, seededFitOutput, ...committedOutputs] });
      if (url.endsWith("/common-processing-recipes")) return jsonResponse({ items: [] });
      if (url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-ensemble-methods")) {
        return jsonResponse({
          items: [
            {
              method_id: "curves.align_linear_intersection",
              version: "1.0.0",
              label: "Align curves on observed intersection",
              description: "Linear interpolation without extrapolation",
              option_schema: {},
              deterministic: true,
              allows_extrapolation: false,
            },
            {
              method_id: "curves.pointwise_statistics",
              version: "1.0.0",
              label: "Pointwise replicate statistics",
              description: "Mean, median, sample SD, MAD, IQR, and 95% mean CI",
              option_schema: {},
              deterministic: true,
              allows_extrapolation: false,
            },
          ],
        });
      }
      if (url.endsWith("/processing-methods")) {
        return jsonResponse({
          items: [
            {
              method_id: "rows.sort_unique",
              version: "1.0.0",
              label: "Sort and resolve duplicate x values",
              description: "Explicit duplicate policy",
              option_schema: {},
              deterministic: true,
              allows_extrapolation: false,
            },
          ],
        });
      }
      if (url.includes("/content")) {
        return {
          ok: true,
          status: 200,
          headers: new Headers({
            "content-type": "application/vnd.cmp.test-data+json",
            "content-disposition": 'attachment; filename="demo.json"',
          }),
          blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
        } as Response;
      }
      if ((url.endsWith("/processing:preview") || url.endsWith("/processing:preview-from-output") || url.endsWith("/metal-fit-runs")) && init?.method === "POST") {
        if (failNextPreview) {
          failNextPreview = false;
          throw new Error("preview failed");
        }
        const body = JSON.parse(String(init.body ?? "{}")) as {
          steps?: Array<{ method_id?: string; options?: { method?: string } }>;
        };
        const modulusPa = body.steps?.find((step) => step.method_id === "metal.elastic_modulus")?.options?.method === "chord"
          ? 120e9
          : 210e9;
        const fitPreview = {
          execution_mode: "preview",
          promotable: false,
          source_document_sha256: "d".repeat(64),
          mapping_profile_sha256: "e".repeat(64),
          independent_quantity: "strain.engineering",
          stages: [
            {
              ordinal: 0,
              method_id: "mapping",
              method_version: "1.0.0",
              point_count: 3,
              series: [
                { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
              ],
              diagnostics: ["canonical normalized values mapped"],
              scalar_results: [],
            },
            {
              ordinal: 1,
              method_id: "rows.sort_unique",
              method_version: "1.0.0",
              point_count: 3,
              series: [
                { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
              ],
              diagnostics: ["input rows sorted by independent quantity"],
              scalar_results: [
                {
                  key: "youngs_modulus",
                  quantity_semantics: "modulus.young",
                  value: modulusPa,
                  unit: "Pa",
                },
              ],
            },
            {
              ordinal: 2,
              method_id: "metal.elastic_modulus",
              method_version: "1.0.0",
              point_count: 3,
              series: [
                { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
              ],
              diagnostics: ["robust elastic fit calculated"],
              scalar_results: [],
            },
            {
              ordinal: 3,
              method_id: "metal.proof_stress",
              method_version: "1.0.0",
              point_count: 3,
              series: [
                { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
              ],
              diagnostics: [],
              scalar_results: [],
            },
            {
              ordinal: 4,
              method_id: "metal.necking_candidate",
              method_version: "1.0.0",
              point_count: 3,
              series: [
                { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
              ],
              diagnostics: [],
              scalar_results: [],
            },
            {
              ordinal: 5,
              method_id: "metal.engineering_to_true_plastic",
              method_version: "1.0.0",
              point_count: 3,
              series: [
                { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
              ],
              diagnostics: [],
              scalar_results: [],
            },
            {
              ordinal: 6,
              method_id: "metal.hardening_fit_extrapolate",
              method_version: "1.0.0",
              point_count: 3,
              series: [
                { quantity: "strain.true_plastic", unit: "1", values: [0, 0.25, 0.5] },
                { quantity: "stress.hardening.voce", unit: "Pa", values: [3e8, 5e8, 5.5e8] },
                { quantity: "stress.hardening.swift", unit: "Pa", values: [3.1e8, 5.2e8, 6e8] },
                { quantity: "stress.hardening.selected", unit: "Pa", values: [3.05e8, 5.1e8, 5.75e8] },
              ],
              diagnostics: ["extrapolated domain (0.1, 0.5] is not observed"],
              scalar_results: [
                {
                  key: "voce.relative_rmse",
                  quantity_semantics: "statistics.relative_rmse",
                  value: 0.012,
                  unit: "1",
                },
                { key: "swift.relative_rmse", quantity_semantics: "statistics.relative_rmse", value: 0.01, unit: "1" },
                { key: "swift.parameter.K", quantity_semantics: "model.parameter.K", value: 5e8, unit: "Pa" },
                { key: "swift.parameter.K.lower", quantity_semantics: "model.parameter.bound.lower.K", value: 1, unit: "Pa" },
                { key: "swift.parameter.K.upper", quantity_semantics: "model.parameter.bound.upper.K", value: 1e9, unit: "Pa" },
              ],
            },
          ],
        };
        if (url.endsWith("/metal-fit-runs")) {
          return jsonResponse({
            id: "53000000-0000-4000-8000-000000000099",
            status: "succeeded",
            preview: fitPreview,
            failure_code: null,
            failure_reason: null,
          });
        }
        return jsonResponse(fitPreview);
      }
      if (url.endsWith("/processing:preview-ensemble") && init?.method === "POST") {
        return jsonResponse({
          execution_mode: "preview",
          promotable: false,
          mapping_profile_sha256: "e".repeat(64),
          independent_quantity: "strain.engineering",
          grid_unit: "1",
          grid: [0, 0.001, 0.002],
          members: [
            {
              ordinal: 0,
              source_document_sha256: "d".repeat(64),
              stage: {
                ordinal: 1,
                method_id: "curves.align_linear_intersection",
                method_version: "1.0.0",
                point_count: 3,
                series: [
                  { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                  { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
                ],
                diagnostics: [],
              },
            },
            {
              ordinal: 1,
              source_document_sha256: "3".repeat(64),
              stage: {
                ordinal: 1,
                method_id: "curves.align_linear_intersection",
                method_version: "1.0.0",
                point_count: 3,
                series: [
                  { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                  { quantity: "stress.engineering", unit: "Pa", values: [0, 2.2e8, 3.2e8] },
                ],
                diagnostics: [],
              },
            },
          ],
          statistics: [
            {
              quantity: "stress.engineering",
              unit: "Pa",
              mean: [0, 2.1e8, 3.1e8],
              median: [0, 2.1e8, 3.1e8],
              standard_deviation: [0, 1.414e7, 1.414e7],
              mad: [0, 1e7, 1e7],
              q1: [0, 2.05e8, 3.05e8],
              q3: [0, 2.15e8, 3.15e8],
              confidence_95_lower: [0, 1.904e8, 2.904e8],
              confidence_95_upper: [0, 2.296e8, 3.296e8],
              metadata_state: "declared",
              curve_definition_sha256: "9".repeat(64),
              curve_definition: ensembleCurveDefinition,
              curve_series: {
                point_count: 3,
                returned_point_count: 3,
                sampled: false,
                indices: [0, 1, 2],
                channels: [
                  { key: "strain.engineering", values: [0, 0.001, 0.002] },
                  { key: "stress.engineering", values: [0, 2.1e8, 3.1e8] },
                ],
                deviations: [
                  {
                    key: "stress.engineering.mean_ci_95_lower.values",
                    values: [0, 1.904e8, 2.904e8],
                  },
                  {
                    key: "stress.engineering.mean_ci_95_upper.values",
                    values: [0, 2.296e8, 3.296e8],
                  },
                ],
                source_counts: [],
              },
            },
          ],
          diagnostics: ["2 member curves retained", "sample standard deviation uses n - 1"],
        });
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const onSessionChange = vi.fn();
    const onSessionEvent = vi.fn();
    const onNewSession = vi.fn();
    const onNavigate = vi.fn();
    const materialA = {
      material_id: "material-a",
      current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } },
    };
    const stateA = {
      material_state_id: "state-a",
      current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } },
    };
    const sessionA = {
      version: 3,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Create a card",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: { id: documentResource.test_data_document_id, revisionId: revision.id, label: documentResource.document_key, revisionNo: 1 },
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      processingOutput: {
        id: seededProcessOutput.processing_output_id,
        revisionId: (seededProcessOutput.current_revision as { id: string }).id,
        label: seededProcessOutput.label,
        revisionNo: 1,
      },
      workspace: { activeStage: "data", selectedDocumentIds: [], selectedStepIndex: 0, selectedStageOrdinal: 0, plotView: "pipeline", settingsOpen: true },
    };
    const view = render(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        onNavigate={onNavigate}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
        onSessionEvent={onSessionEvent}
        onNewSession={onNewSession}
        initialSession={sessionA as never}
        material={materialA as never}
        materialState={stateA as never}
        familyWorkbench={<div>Exact Neutral and solver delivery fixture</div>}
      />,
    );

    expect(await screen.findByRole("banner", { name: "Modeling context" })).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Material Modeling steps" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Card" })).toBeNull();
    expect(screen.getByRole("tablist", { name: "Material modeling family" })).toBeTruthy();
    expect(await screen.findByRole(
      "img",
      { name: "Hardening candidate and selected extrapolation curves" },
      { timeout: 5000 },
    )).toBeTruthy();
    expect(screen.queryByText("Test data")).toBeNull();
    const settingsControl = screen.getByRole("button", { name: /current-stage settings/ });
    expect(settingsControl).toBeTruthy();
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:data" } }));
    expect(await screen.findByRole("tablist", { name: "Test data source" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Library" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Local file" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Test Data JSON" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Select Test Data" })).toBeTruthy();
    expect(screen.queryByText("Metal hardening candidates")).toBeNull();
    let dataIdentityRow: HTMLElement | undefined;
    await waitFor(() => {
      dataIdentityRow = Array.from(document.querySelectorAll<HTMLElement>(".modeling-data-curve-tree .curve-row-label"))
        .find((row) => row.querySelector("strong")?.textContent === "Specimen 01");
      expect(dataIdentityRow).toBeTruthy();
    });
    if (!dataIdentityRow) throw new Error("Data identity row is missing");
    expect(dataIdentityRow.querySelector("strong")?.textContent).toBe("Specimen 01");
    expect(dataIdentityRow.querySelector("small.curve-secondary-identity")?.textContent).toBe("Session revision r1");
    expect(dataIdentityRow.querySelectorAll("small")).toHaveLength(1);
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:validate" } }));
    expect(await screen.findByRole("heading", { name: "Validation, review and release" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Submit · Not configured" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Release · Not configured" }).hasAttribute("disabled")).toBe(true);
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:data" } }));
    fireEvent.click(screen.getByRole("tab", { name: /Polymer/ }));
    expect((screen.getByLabelText("Mapping Profile JSON") as HTMLTextAreaElement).value).toContain(
      '"profile_key": "polymer-shear-relaxation"',
    );
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:fit" } }));
    expect((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value).toContain(
      '"method_id": "polymer.prony_fit_compare"',
    );
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:data" } }));
    fireEvent.click(screen.getByRole("tab", { name: /Metal/ }));
    fireEvent.change(screen.getByLabelText("Test Data revision"), {
      target: { value: documentResource.test_data_document_id },
    });
    fireEvent.click(screen.getByRole("button", { name: "Load exact JSON" }));
    await waitFor(() => expect((screen.getByLabelText("Test Data revision") as HTMLSelectElement).value).toBe(documentResource.test_data_document_id));
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:fit" } }));
    expect(await screen.findByRole(
      "img",
      { name: "Hardening candidate and selected extrapolation curves" },
      { timeout: 5000 },
    )).toBeTruthy();
    expect((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value).toContain(
      '"method_id": "metal.hardening_fit_extrapolate"',
    );
    expect(document.querySelector(".modeling-context-actions > .modeling-advanced-menu > summary")?.className)
      .toContain("button secondary");
    if (settingsControl.getAttribute("aria-expanded") === "false") fireEvent.click(settingsControl);
    fireEvent.click(screen.getByText("Advanced · Recipe and Batch"));
    fireEvent.click(screen.getByRole("button", { name: /Recipe/ }));
    expect(screen.getByLabelText("Saved Processing Recipe")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Batch/ }));
    expect(screen.getByLabelText("Processing Batch label")).toBeTruthy();
    expect((await screen.findAllByText("DP600-TENSILE-01 · r1")).length).toBeGreaterThanOrEqual(1);
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    expect(await screen.findByRole(
      "img",
      { name: "Hardening candidate and selected extrapolation curves" },
      { timeout: 5000 },
    )).toBeTruthy();
    expect(await screen.findByText("Preview Swift/Voce blend")).toBeTruthy();
    const fitRail = document.querySelector(".configured-step-list");
    expect(fitRail?.querySelector(".rail-title")?.textContent).toContain("Process");
    expect(fitRail?.querySelectorAll("button")).toHaveLength(4);
    expect(screen.getByRole("button", { name: /Sort duplicate x/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /True\/plastic conversion/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Necking boundary/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Hardening fit/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /Step 4 · Hardening fit and extrapolation/ })).toBeTruthy();
    expect(screen.getByText("Candidate equations")).toBeTruthy();
    expect(screen.getByText("Fit domain")).toBeTruthy();
    expect(screen.getByText("Selected blend")).toBeTruthy();
    expect(screen.getByText("Primary contribution")).toBeTruthy();
    expect(screen.getByText("Extrapolation")).toBeTruthy();
    expect(screen.getByText("Graph interaction")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Apply" })).toBeNull();
    expect(screen.getByLabelText("Output points").closest("fieldset")).toBeTruthy();
    expect(screen.getByLabelText("Secondary hardening law").closest("fieldset")?.className).toContain("selected-blend-group");
    const fitPlotHeading = screen.getByRole("heading", { name: "Hardening response", level: 2 });
    expect(fitPlotHeading).toBeTruthy();
    expect(screen.queryAllByText("Hardening response", { exact: true })
      .filter((node) => node.tagName.toLowerCase() !== "h2")).toHaveLength(0);
    expect(screen.queryByRole("button", { name: "Select range" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Select fit range" }));
    expect(screen.getByRole("button", { name: "Select fit range" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("Candidate parameters")).toBeTruthy();
    fireEvent.click(screen.getByText("Candidate parameters"));
    const sourceEvidence = screen.getByLabelText("Source evidence");
    expect(within(sourceEvidence).getByText("Source digest")).toBeTruthy();
    expect(within(sourceEvidence).getByText("Fit method")).toBeTruthy();
    expect(screen.getByText("voce relative rmse")).toBeTruthy();
    expect(await screen.findByRole("columnheader", { name: "Recommendation" })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Save fit & continue" })).toHaveLength(1);
    expect((screen.getByRole("button", { name: "Save fit & continue" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByText("Reference hardening projection")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Select swift candidate/i }));
    expect(screen.getAllByText("Selected · swift").length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText("Candidate selection reason"), {
      target: { value: "Select Swift after comparing response, residual and tangent stability." },
    });
    expect((screen.getByRole("button", { name: "Save fit & continue" }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole("checkbox", { name: "Include Specimen 01 in processing and fit" }));
    expect((screen.getByRole("button", { name: "Save fit & continue" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByLabelText("Candidate selection reason")).toBeNull();
    fireEvent.click(screen.getByRole("checkbox", { name: "Include Specimen 01 in processing and fit" }));
    fireEvent.click(screen.getByRole("button", { name: /Select swift candidate/i }));
    fireEvent.change(screen.getByLabelText("Candidate selection reason"), {
      target: { value: "Re-select Swift after changing input scope." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => {
      expect((screen.getByRole("button", { name: "Save fit & continue" }) as HTMLButtonElement).disabled).toBe(true);
      expect(screen.queryByLabelText("Candidate selection reason")).toBeNull();
    });
    fireEvent.click(screen.getByRole("button", { name: /Select swift candidate/i }));
    fireEvent.change(screen.getByLabelText("Candidate selection reason"), {
      target: { value: "Re-select Swift after the successful candidate recomputation." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save fit & continue" }));
    expect(await screen.findByRole("heading", { name: "Fit material response" })).toBeTruthy();
    expect(screen.getByText(/New immutable Fit Output saved and current/i)).toBeTruthy();
    expect(screen.getByText(/Modeling Export is separate and has not started/i)).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Review & deliver solver card" })).toBeNull();
    expect(onNavigate.mock.calls.some(([path]) => String(path).includes("export"))).toBe(false);
    expect(onSessionChange).toHaveBeenCalledWith({
      processingOutput: {
        id: "53000000-0000-4000-8000-000000000030",
        revisionId: "53000000-0000-4000-8000-000000000031",
        label: "DP600 · swift selected fit",
        revisionNo: 1,
      },
    });
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:process" } }));
    // Process is lazy-loaded; when this test runs after another Process test the
    // module may already be warm, so the loading fallback is intentionally
    // optional while the panel remains the same contract.
    expect(await screen.findByRole("heading", { name: "Prepare observed curves" })).toBeTruthy();
    expect(await screen.findByRole("button", { name: "Save processed curves" })).toBeTruthy();
    expect(screen.queryByRole("status", { name: "Loading Process controls" })).toBeNull();
    fireEvent.click(processRailButton("Specimen 01 · r1"));
    await waitFor(() => expect(document.querySelector(".persistent-modeling-plot > .modeling-plot-empty")).toBeTruthy());
    expect(screen.queryByText("Choose a saved Test Data revision. The graph compares real curves without changing saved data.")).toBeNull();
    expect(document.querySelector('[data-modeling-process-panel="ready"]')).toBeTruthy();
    const processSave = screen.getByRole("button", { name: "Save processed curves" }) as HTMLButtonElement;
    fireEvent.click(processRailButton("Specimen 02 · r1"));
    expect(onSessionEvent).toHaveBeenCalledWith({
      type: "PIN_TEST_DATA",
      testData: {
        id: replicateResource.test_data_document_id,
        revisionId: replicateResource.current_revision.id,
        label: replicateResource.document_key,
        revisionNo: replicateResource.current_revision.revision_no,
      },
    });
    await waitFor(() => expect(onSessionEvent).toHaveBeenLastCalledWith({ type: "CHANGE_SELECTION" }));
    onSessionEvent.mockClear();
    fireEvent.click(screen.getByRole("checkbox", { name: "Include Specimen 02 in processing and fit" }));
    expect(onSessionEvent).toHaveBeenNthCalledWith(1, {
      type: "PIN_TEST_DATA",
      testData: {
        id: documentResource.test_data_document_id,
        revisionId: documentResource.current_revision.id,
        label: documentResource.document_key,
        revisionNo: documentResource.current_revision.revision_no,
      },
    });
    expect(onSessionEvent).toHaveBeenNthCalledWith(2, {
      type: "SET_TEST_DATA_SELECTION",
      selectedTestDataRefs: [{
        id: documentResource.test_data_document_id,
        revisionId: documentResource.current_revision.id,
        label: documentResource.document_key,
        revisionNo: documentResource.current_revision.revision_no,
      }],
    });
    onSessionEvent.mockClear();
    fireEvent.click(screen.getByRole("checkbox", { name: "Include Specimen 01 in processing and fit" }));
    expect(onSessionEvent).toHaveBeenNthCalledWith(1, { type: "PIN_TEST_DATA" });
    expect(onSessionEvent).toHaveBeenNthCalledWith(2, { type: "SET_TEST_DATA_SELECTION", selectedTestDataRefs: [] });
    expect(screen.getByRole("img", { name: "Blocked engineering curve plot" })).toBeTruthy();
    const blockedPlot = document.querySelector('.engineering-curve-plot-empty-frame[data-plot-state="blocked"]');
    expect(blockedPlot?.querySelectorAll(".chart-axis").length).toBeGreaterThanOrEqual(2);
    expect(blockedPlot?.querySelectorAll(".chart-grid").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole("button", { name: "Back to Data" })).toBeTruthy();
    expect((screen.getByRole("button", { name: "Preview changes" }) as HTMLButtonElement).disabled).toBe(true);
    expect(processSave.disabled).toBe(true);
    expect(document.querySelector('.method-library > summary[aria-disabled="true"]')).toBeTruthy();
    const blockedMethodButtons = Array.from(document.querySelectorAll<HTMLButtonElement>(".method-library .method-pill"));
    const blockedRailButtons = Array.from(document.querySelectorAll<HTMLButtonElement>(".configured-step-list button"));
    const blockedRangeInputs = Array.from(document.querySelectorAll<HTMLInputElement>(".process-band-controls input"));
    expect(blockedMethodButtons.length).toBeGreaterThan(0);
    expect(blockedRailButtons.length).toBeGreaterThan(0);
    expect(blockedRangeInputs.length).toBeGreaterThan(0);
    expect(blockedMethodButtons.every((button) => button.disabled)).toBe(true);
    expect(blockedRailButtons.every((button) => button.disabled)).toBe(true);
    expect(blockedRangeInputs.every((input) => input.matches(":disabled"))).toBe(true);
    fireEvent.click(screen.getByRole("checkbox", { name: "Include Specimen 01 in processing and fit" }));
    fireEvent.click(processRailButton("Specimen 01 · r1"));
    fireEvent.click(screen.getByRole("checkbox", { name: "Include Specimen 02 in processing and fit" }));
    fireEvent.click(processRailButton("Specimen 02 · r1"));
    await waitFor(() => expect((screen.getByRole("button", { name: "Preview changes" }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole("button", { name: /\+ Sort and resolve duplicate/ }));
    expect(processSave.disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(screen.getByText(/Preview ready/)).toBeTruthy());
    const processPreviewRequest = fetchMock.mock.calls
      .filter(([input, init]) => String(input).endsWith("/processing:preview") && init?.method === "POST")
      .at(-1);
    const processPreviewBody = JSON.parse(String(processPreviewRequest?.[1]?.body ?? "{}")) as {
      steps?: Array<{ method_id?: string; options?: Record<string, unknown> }>;
    };
    expect(processPreviewBody.steps?.map((step) => step.method_id)).toEqual([
      "rows.sort_unique",
      "metal.elastic_modulus",
      "metal.proof_stress",
      "metal.necking_candidate",
      "metal.engineering_to_true_plastic",
      "rows.sort_unique",
    ]);
    expect(processPreviewBody.steps?.some((step) => isFitMethodInRequest(step.method_id))).toBe(false);
    expect(screen.getByRole("img", { name: /(?:mapped and selected processing stage curve overlay|candidate and selected .*curves)/i })).toBeTruthy();
    const processPanel = () => document.querySelector('[data-modeling-process-panel="ready"]') as HTMLElement;
    await waitFor(() => expect(screen.getByText("Step 2 · Process · Young's modulus", { exact: true })).toBeTruthy());
    expect(screen.getByRole("combobox", { name: "Evaluation method" })).toBeTruthy();
    expect((screen.getByRole("combobox", { name: "Evaluation method" }) as HTMLSelectElement).value).toBe("robust_huber");
    expect(screen.getByLabelText("Elastic range start")).toBeTruthy();
    expect(screen.getByLabelText("Elastic range end")).toBeTruthy();
    expect(screen.queryByText("Candidate equations")).toBeNull();
    expect(screen.queryByText("Fit domain")).toBeNull();
    expect(screen.queryByText("Selected blend")).toBeNull();
    const robustResult = processPanel().querySelector(".process-band-result");
    expect(robustResult?.textContent ?? "").toMatch(/210\.0 GPa/);
    expect(screen.getByText("Curve response", { exact: true })).toBeTruthy();
    expect(screen.queryByText("Preview — not saved", { exact: true })).toBeNull();
    expect(screen.getByRole("heading", { name: "Result" })).toBeTruthy();
    const processMethodOptions = screen.getByRole("combobox", { name: "Evaluation method" }) as HTMLSelectElement;
    expect(Array.from(processMethodOptions.options, (option) => option.text)).toEqual([
      "Auto robust",
      "Linear regression",
      "Chord",
      "Secant",
      "Manual slope",
    ]);
    for (const value of ["robust_huber", "linear_regression", "chord", "secant", "manual"]) {
      fireEvent.change(processMethodOptions, { target: { value } });
      expect(processMethodOptions.value).toBe(value);
    }
    fireEvent.change(processMethodOptions, { target: { value: "robust_huber" } });
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(screen.getByText("Preview ready.", { exact: false })).toBeTruthy());
    expect(processPanel().querySelector(".guided-step-options")?.textContent ?? "").not.toMatch(/Auto\/calculated value preview/);
    expect((screen.getByRole("button", { name: "Save processed curves" }) as HTMLButtonElement).disabled).toBe(false);
    failNextPreview = true;
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(screen.getByText("The Processing Workbench operation failed.")).toBeTruthy());
    expect(screen.getByRole("img", { name: /(?:mapped and selected processing stage curve overlay|candidate and selected .*curves)/i })).toBeTruthy();
    const processLabel = screen.getByRole("textbox", { name: "Processed curve label" });
    const processReason = screen.getByRole("textbox", { name: "Save reason" });
    fireEvent.change(processLabel, { target: { value: "Robust elastic" } });
    fireEvent.change(processReason, { target: { value: "Capture deterministic saved-result sibling one" } });
    fireEvent.click(processSave);
    await waitFor(() => expect(committedOutputs).toHaveLength(2));
    const firstProcessOutput = String(committedOutputs[1].processing_output_id);
    const firstCommitBody = JSON.parse(String(fetchMock.mock.calls.filter(([input, init]) => String(input).endsWith("/processing-outputs") && init?.method === "POST").at(-1)?.[1]?.body ?? "{}")) as {
      source_document?: { aggregate_id?: string; revision_id?: string };
      mapping_profile?: { aggregate_id?: string; revision_id?: string };
      steps?: Array<{ method_id?: string; options?: Record<string, unknown> }>;
    };
    expect(firstCommitBody.source_document).toEqual({ aggregate_id: replicateResource.test_data_document_id, revision_id: replicateResource.current_revision.id });
    expect(firstCommitBody.mapping_profile).toEqual({ aggregate_id: mappingProfileResource.mapping_profile_id, revision_id: mappingProfileResource.current_revision.id });
    expect(firstCommitBody.steps?.map((step) => step.method_id)).toEqual([
      "rows.sort_unique",
      "metal.elastic_modulus",
      "metal.proof_stress",
      "metal.necking_candidate",
      "metal.engineering_to_true_plastic",
      "rows.sort_unique",
    ]);
    expect(firstCommitBody.steps?.some((step) => isFitMethodInRequest(step.method_id))).toBe(false);
    expect(firstCommitBody.steps?.find((step) => step.method_id === "metal.elastic_modulus")?.options).toMatchObject({ method: "robust_huber", minimum_strain: 0.0002, maximum_strain: 0.002 });
    fireEvent.change(screen.getByRole("combobox", { name: "Evaluation method" }), { target: { value: "chord" } });
    fireEvent.change(screen.getByLabelText("Elastic range start"), { target: { value: "0.001" } });
    fireEvent.change(screen.getByLabelText("Elastic range end"), { target: { value: "0.003" } });
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(screen.getByText(/Preview ready/)).toBeTruthy());
    const chordResult = processPanel().querySelector(".process-band-result");
    expect(chordResult?.textContent ?? "").toMatch(/120\.0 GPa/);
    expect(processPanel().querySelector(".guided-step-options")?.textContent ?? "").not.toMatch(/Auto\/calculated value preview/);
    fireEvent.change(processLabel, { target: { value: "Chord elastic" } });
    fireEvent.change(processReason, { target: { value: "Capture deterministic saved-result sibling two" } });
    fireEvent.click(processSave);
    await waitFor(() => expect(committedOutputs).toHaveLength(3));
    const secondProcessOutput = String(committedOutputs[2].processing_output_id);
    expect(firstProcessOutput).not.toBe(secondProcessOutput);
    const savedDetails = document.querySelector("details.process-saved-results") as HTMLDetailsElement;
    expect(screen.getAllByText("DP600-TENSILE-02 · r1").length).toBeGreaterThan(0);
    await waitFor(() => expect(savedDetails.querySelector("summary")?.textContent).toContain("Saved results (2)"));
    fireEvent.click(savedDetails.querySelector(":scope > summary")!);
    await waitFor(() => expect(savedDetails.querySelectorAll(".process-comparison-row")).toHaveLength(2));
    await waitFor(() => expect(Array.from(savedDetails.querySelectorAll(".process-comparison-row"), (row) => row.textContent ?? "").join(" ")).toContain("210.0 GPa"));
    const savedRowText = Array.from(savedDetails.querySelectorAll(".process-comparison-row"), (row) => row.textContent ?? "");
    expect(savedRowText.some((text) => text.includes("seeded fit baseline"))).toBe(false);
    expect(savedRowText).toEqual(expect.arrayContaining([
      expect.stringContaining("Robust elastic"),
      expect.stringContaining("Chord elastic"),
    ]));
    expect(savedRowText.every((text) => !text.includes("Specimen 02 · r1"))).toBe(true);
    expect(savedRowText.every((text) => text.includes("r1"))).toBe(true);
    expect(savedRowText.find((text) => text.includes("Robust elastic"))).toContain("210.0 GPa");
    expect(savedRowText.find((text) => text.includes("Robust elastic"))).toContain("history");
    expect(savedRowText.find((text) => text.includes("Chord elastic"))).toContain("120.0 GPa");
    expect(savedRowText.find((text) => text.includes("Chord elastic"))).toContain("current");
    const firstRow = savedDetails.querySelectorAll(".process-comparison-row")[0] as HTMLElement;
    expect(within(firstRow).getByRole("button", { name: "Use settings" })).toBeTruthy();
    invalidArtifactId = firstProcessOutput;
    fireEvent.click(savedDetails.querySelector(":scope > summary")!);
    fireEvent.click(savedDetails.querySelector(":scope > summary")!);
    await waitFor(() => expect(savedDetails.querySelectorAll(".process-comparison-row")[0]?.textContent).toContain("Saved result unavailable"));
    const invalidRow = savedDetails.querySelectorAll(".process-comparison-row")[0] as HTMLElement;
    fireEvent.click(within(invalidRow).getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(invalidRow.textContent).toContain("Saved result unavailable"));
    invalidArtifactId = null;
    fireEvent.click(within(invalidRow).getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(invalidRow.textContent).toContain("210.0 GPa"));
    fireEvent.click(within(invalidRow).getByRole("button", { name: "Use settings" }));
    expect(await screen.findByText(/Saved Process settings restored as a new draft/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Save processed curves" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(screen.getByText(/Preview ready/)).toBeTruthy());
    expect(screen.getByText("Curves")).toBeTruthy();
    expect(screen.getByText("2 curves · 2 included")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Tensile tests" })).toBeTruthy();
    const curveGroup = document.querySelector(".curve-tree-group > details");
    expect(curveGroup?.hasAttribute("open")).toBe(true);
    const groupSummary = curveGroup?.querySelector("summary");
    expect(groupSummary?.textContent).toContain("Tensile tests");
    fireEvent.click(groupSummary!);
    expect(curveGroup?.hasAttribute("open")).toBe(false);
    fireEvent.click(groupSummary!);
    expect(curveGroup?.hasAttribute("open")).toBe(true);
    expect(document.querySelector(".curve-group-row > span")).toBeNull();
    const curveKey = document.querySelector(".dataset-curve-swatch");
    expect(curveKey).toBeTruthy();
    expect(curveKey?.className).toBe("dataset-curve-swatch");
    expect(curveKey?.getAttribute("role")).toBe("img");
    expect(curveKey?.getAttribute("aria-label")).toBe("Plot color for Specimen 01");
    expect(curveKey?.previousElementSibling?.className).toBe("curve-include-toggle");
    expect(curveKey?.nextElementSibling?.className).toBe("curve-row-label");
    expect(Array.from(curveKey?.parentElement?.children ?? []).map((child) => child.className)).toEqual([
      "curve-include-toggle",
      "dataset-curve-swatch",
      "curve-row-label",
      "curve-visibility-toggle",
    ]);
    const curveRow = processRailButton("Specimen 01 · r1");
    expect(curveRow.textContent).toBe("Specimen 01 · r1");
    const includeSpecimen = screen.getByRole("checkbox", { name: "Include Specimen 01 in processing and fit" });
    const plotVisibility = screen.getByRole("button", { name: "Hide Specimen 01 on plot" });
    expect(plotVisibility.getAttribute("aria-pressed")).toBe("true");
    expect(screen.queryByText(/^Hide$/)).toBeNull();
    fireEvent.click(plotVisibility);
    expect(screen.getByRole("button", { name: "Show Specimen 01 on plot" }).getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(includeSpecimen);
    expect((includeSpecimen as HTMLInputElement).checked).toBe(false);
    expect(onSessionEvent).toHaveBeenCalledWith({ type: "CHANGE_SELECTION" });
    fireEvent.click(includeSpecimen);
    expect((includeSpecimen as HTMLInputElement).checked).toBe(true);
    expect(screen.queryByText("Fit evidence")).toBeNull();
    fireEvent.click(screen.getByRole("button", {
      name: /1Sort and resolve duplicate x values1\.0\.0/,
    }));
    expect(screen.getByRole("img", { name: /(?:mapped and selected processing stage curve overlay|candidate and selected .*curves)/i })).toBeTruthy();
    expect(screen.getByText("input rows sorted by independent quantity")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /2Young's modulus1\.0\.0/ }));
    const evaluationMethod = screen.getByRole("combobox", { name: "Evaluation method" }) as HTMLSelectElement;
    expect(evaluationMethod.value).toBe("robust_huber");
    fireEvent.change(evaluationMethod, { target: { value: "manual" } });
    fireEvent.change(screen.getByLabelText("Manual Young's modulus"), { target: { value: "205" } });
    expect(screen.getByLabelText("Manual Young's modulus unit")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Manual Young's modulus reason"), { target: { value: "Reconcile the measured elastic range." } });
    expect(onSessionEvent).toHaveBeenCalledWith({ type: "CHANGE_PROCESS" });
    const guidedSteps = JSON.parse((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value) as Array<{ method_id: string; options: Record<string, unknown> }>;
    expect(guidedSteps[1].options.method).toBe("manual");
    expect(guidedSteps[1].options.manual_modulus_pa).toBe(205_000_000_000);
    await screen.findByRole("img", { name: /(?:mapped and selected processing stage curve overlay|candidate and selected .*curves)/i });
    fireEvent.click(screen.getByRole("button", { name: /2Young's modulus1\.0\.0/ }));
    const elasticPlot = screen.getByRole("img", { name: /(?:mapped and selected processing stage curve overlay|candidate and selected .*curves)/i });
    Object.defineProperty(elasticPlot, "getBoundingClientRect", {
      value: () => ({ left: 0, top: 0, right: 760, bottom: 420, width: 760, height: 420, x: 0, y: 0, toJSON: () => ({}) }),
      configurable: true,
    });
    fireEvent.click(screen.getByRole("button", { name: "Select range" }));
    fireEvent.pointerDown(elasticPlot, { button: 0, pointerId: 2, clientX: 100, clientY: 200 });
    fireEvent.pointerMove(elasticPlot, { pointerId: 2, clientX: 160, clientY: 200 });
    fireEvent.pointerUp(elasticPlot, { pointerId: 2, clientX: 160, clientY: 200 });
    fireEvent.click(screen.getByRole("button", { name: "Apply selection" }));
    const appliedSteps = JSON.parse((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value) as Array<{ method_id: string; options: Record<string, number> }>;
    expect(appliedSteps[1].method_id).toBe("metal.elastic_modulus");
    expect(appliedSteps[1].options.minimum_strain).not.toBe(0.0002);
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await screen.findByText(/Preview ready/);
    await screen.findByRole("img", { name: /(?:mapped and selected processing stage curve overlay|candidate and selected .*curves)/i });
    fireEvent.click(screen.getByRole("button", { name: /4Necking candidate1\.0\.0/ }));
    await waitFor(() => expect(screen.getByText("Step 4 · Process · Necking candidate", { exact: true })).toBeTruthy());
    const neckingPlot = screen.getByRole("img", { name: /(?:mapped and selected processing stage curve overlay|candidate and selected .*curves)/i });
    Object.defineProperty(neckingPlot, "getBoundingClientRect", {
      value: () => ({ left: 0, top: 0, right: 760, bottom: 420, width: 760, height: 420, x: 0, y: 0, toJSON: () => ({}) }),
      configurable: true,
    });
    fireEvent.click(screen.getByRole("button", { name: "Pick point" }));
    fireEvent.pointerDown(neckingPlot, { button: 0, pointerId: 3, clientX: 620, clientY: 180 });
    fireEvent.pointerUp(neckingPlot, { pointerId: 3, clientX: 620, clientY: 180 });
    fireEvent.click(screen.getByRole("button", { name: "Apply selection" }));
    const neckingSteps = JSON.parse((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value) as Array<{ method_id: string; options: Record<string, unknown> }>;
    expect(neckingSteps[4].method_id).toBe("metal.engineering_to_true_plastic");
    expect(neckingSteps[4].options.necking_policy).toBe("manual_index");
    expect(Number(neckingSteps[4].options.manual_necking_index)).toBeGreaterThanOrEqual(1);

    fireEvent.click(screen.getByRole("button", { name: "Align and calculate" }));
    expect(await screen.findByRole("img", { name: "Aligned replicate curves with declared pointwise statistics" })).toBeTruthy();
    expect(document.querySelector("polygon.ensemble-confidence-band")).toBeTruthy();
    expect(screen.getAllByText("95% · pointwise · confidence interval · normal_approximation.mean_two_sided v1.0.0 · ddof 1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Engineering stress").length).toBeGreaterThan(0);
    expect(screen.getAllByText("MPa").length).toBeGreaterThan(0);
    expect(screen.getByText("Members (2)")).toBeTruthy();
    expect(screen.getByText("sample standard deviation uses n - 1")).toBeTruthy();
    const ensembleRequest = fetchMock.mock.calls.find(([input]) => String(input).endsWith("/processing:preview-ensemble"));
    const ensembleBody = JSON.parse(String(ensembleRequest?.[1]?.body)) as { preprocessing_steps: Array<{ method_id: string }> };
    expect(ensembleBody.preprocessing_steps.map((step) => step.method_id)).toEqual(["rows.sort_unique", "rows.sort_unique"]);
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:export" } }));
    expect(await screen.findByRole("heading", { name: "Review & deliver solver card" })).toBeTruthy();
    await waitFor(() => expect(onSessionChange).toHaveBeenCalledWith({
      workspace: expect.objectContaining({ activeStage: "export" }),
    }));
    expect(screen.getByRole("heading", { name: "Exact target preview is gated" })).toBeTruthy();
    expect(screen.queryByText("Test data")).toBeNull();
    expect(screen.queryByLabelText("Resize curve and process navigator")).toBeNull();
    expect(screen.queryByRole("button", { name: "Mean & band" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Replicate statistics" })).toBeNull();
    expect(document.querySelector(".persistent-modeling-plot")).toBeNull();
    expect(screen.queryByRole("img", { name: "Test data and selected model response" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Generate preview" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Stress response" })).toBeNull();
    expect(screen.queryByText("Calculation notes")).toBeNull();
    expect(screen.queryByText("Exact Neutral and solver delivery fixture")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Back to Fit" }));
    expect(screen.queryByRole("img", { name: "Aligned replicate curves with declared pointwise statistics" })).toBeNull();
    onSessionChange.mockClear();
    view.rerender(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        onNavigate={onNavigate}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
        onNewSession={onNewSession}
        initialSession={{
          ...sessionA,
          material: { id: "material-b", revisionId: "material-b-r1", label: "DP600 B", revisionNo: 1 },
          materialState: { id: "state-b", revisionId: "state-b-r1", label: "Aged", revisionNo: 1 },
          testData: undefined,
          mappingProfile: undefined,
          recipe: undefined,
          processingOutput: undefined,
        } as never}
        material={{ ...materialA, material_id: "material-b", current_revision: { ...materialA.current_revision, id: "material-b-r1", content: { name: "DP600 B" } } } as never}
        materialState={{ ...stateA, material_state_id: "state-b", current_revision: { ...stateA.current_revision, id: "state-b-r1", content: { name: "Aged" } } } as never}
        familyWorkbench={<div>Exact Neutral and solver delivery fixture</div>}
      />,
    );
    await waitFor(() => {
      const repinned = onSessionChange.mock.calls.filter(([patch]) => {
        const candidate = patch as Record<string, unknown>;
        return candidate.testData !== undefined
          || candidate.mappingProfile !== undefined
          || candidate.recipe !== undefined
          || candidate.processingOutput !== undefined;
      });
      expect(repinned).toEqual([]);
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:new" } }));
    expect(onNewSession).toHaveBeenCalledWith("metal");
    expect(onNavigate).toHaveBeenLastCalledWith("/modeling?stage=data&family=metal");
  }, 20_000);

  it("keeps restored exact Data refs while documents resolve before Material context", async () => {
    const thirdResource = {
      ...replicateResource,
      test_data_document_id: "53000000-0000-4000-8000-000000000022",
      current_revision: {
        ...replicateResource.current_revision,
        id: "53000000-0000-4000-8000-000000000023",
        aggregate_id: "53000000-0000-4000-8000-000000000022",
      },
      document_key: "DP600-TENSILE-03",
      specimen_id: "S-3",
    };
    const documents = [documentResource, replicateResource, thirdResource];
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: documents });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-methods") || url.endsWith("/processing-outputs")
        || url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes")
        || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.includes("/content")) {
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
        } as Response;
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const refs = documents.map((item) => ({
      id: item.test_data_document_id,
      revisionId: item.current_revision.id,
      label: item.document_key,
      revisionNo: item.current_revision.revision_no,
    }));
    const initialSession = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Keep exact Data sources",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: refs[0],
      workspace: {
        activeStage: "data",
        selectedDocumentIds: refs.map((ref) => ref.id),
        selectedTestDataRefs: refs,
        visibleTestDataKeys: refs.map((ref) => `${ref.id}:${ref.revisionId}`),
        selectedStepIndex: 0,
        selectedStageOrdinal: 0,
        plotView: "pipeline",
        settingsOpen: true,
      },
    };
    const onSessionChange = vi.fn();
    const material = {
      material_id: "material-a",
      current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } },
    };
    const materialState = {
      material_state_id: "state-a",
      current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } },
    };
    const view = render(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={initialSession as never}
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
      />,
    );
    await waitFor(() => expect(
      fetchMock.mock.calls.some(([input]) => String(input).endsWith("/test-data-documents")),
    ).toBe(true));
    await new Promise((resolve) => window.setTimeout(resolve, 0));

    view.rerender(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={initialSession as never}
        material={material as never}
        materialState={materialState as never}
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
      />,
    );
    await waitFor(() => expect(document.querySelectorAll(".data-library-row")).toHaveLength(3));
    await waitFor(() => {
      const workspacePatches = onSessionChange.mock.calls
        .map(([patch]) => (patch as Record<string, unknown>).workspace)
        .filter((workspace): workspace is Record<string, unknown> => Boolean(workspace));
      const latest = workspacePatches.at(-1);
      expect(latest?.selectedTestDataRefs).toHaveLength(3);
      expect(latest?.selectedDocumentIds).toHaveLength(3);
      expect(latest?.visibleTestDataKeys).toHaveLength(3);
    });
  });

  it("defers Process reconciliation until Material context resolves without empty workspace patches", async () => {
    const thirdResource = {
      ...replicateResource,
      test_data_document_id: "53000000-0000-4000-8000-000000000022",
      current_revision: {
        ...replicateResource.current_revision,
        id: "53000000-0000-4000-8000-000000000023",
        aggregate_id: "53000000-0000-4000-8000-000000000022",
      },
      document_key: "DP600-TENSILE-03",
      specimen_id: "S-3",
    };
    const documents = [documentResource, replicateResource, thirdResource];
    // The persisted workspace order is not the restored source focus. This
    // mirrors the live reload where refs arrive as 03, 02, base while
    // session.testData remains pinned to base.
    const refs = [thirdResource, replicateResource, documentResource].map((item) => ({
      id: item.test_data_document_id,
      revisionId: item.current_revision.id,
      label: item.document_key,
      revisionNo: item.current_revision.revision_no,
    }));
    const baseRef = refs[2];
    const replicateRef = refs[1];
    const robustOutput = {
      processing_output_id: "53000000-0000-4000-8000-000000000030",
      current_revision: { ...revision, id: "53000000-0000-4000-8000-000000000031", aggregate_id: "53000000-0000-4000-8000-000000000030" },
      label: "Robust 210",
      source_document: { aggregate_id: baseRef.id, revision_id: baseRef.revisionId },
      mapping_profile: { aggregate_id: mappingProfileResource.mapping_profile_id, revision_id: mappingProfileResource.current_revision.id },
      steps: [{ method_id: "metal.elastic_modulus", method_version: "1.0.0", options: { method: "robust_huber", minimum_strain: 0.0002, maximum_strain: 0.002 } }],
      output_sha256: "3".repeat(64),
      final_point_count: 3,
      stage_count: 2,
    };
    const chordOutput = {
      ...robustOutput,
      processing_output_id: "53000000-0000-4000-8000-000000000032",
      current_revision: { ...revision, id: "53000000-0000-4000-8000-000000000033", aggregate_id: "53000000-0000-4000-8000-000000000032" },
      label: "Chord 120",
      steps: [{ method_id: "metal.elastic_modulus", method_version: "1.0.0", options: { method: "chord", minimum_strain: 0.001, maximum_strain: 0.003 } }],
      output_sha256: "4".repeat(64),
    };
    const outputItems = [robustOutput, chordOutput];
    const workspacePatches = (onSessionChange: ReturnType<typeof vi.fn>) => onSessionChange.mock.calls
      .map(([patch]) => (patch as Record<string, unknown>).workspace)
      .filter((workspace): workspace is Record<string, unknown> => Boolean(workspace));
    let resolveDocuments: ((response: Response) => void) | undefined;
    const documentsResponse = new Promise<Response>((resolve) => { resolveDocuments = resolve; });
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return documentsResponse;
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-outputs") && init?.method !== "POST") return jsonResponse({ items: outputItems });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: [
        "rows.sort_unique", "metal.elastic_modulus", "metal.proof_stress", "metal.necking_candidate", "metal.engineering_to_true_plastic",
      ].map((methodId) => ({ method_id: methodId, version: "1.0.0", label: methodId, description: methodId, option_schema: {}, deterministic: true, allows_extrapolation: false })) });
      if (url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.includes("/processing-outputs/") && url.endsWith("/content")) {
        const outputId = decodeURIComponent(url.split("/processing-outputs/")[1].split("/content")[0]);
        const output = outputItems.find((item) => item.processing_output_id === outputId);
        const scalarPa = outputId === chordOutput.processing_output_id ? 120e9 : 210e9;
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/vnd.cmp.processing-output+json" }),
          blob: async () => new Blob([JSON.stringify({
            document_type: "cmp.processing-output",
            output_id: outputId,
            source_document: output?.source_document,
            mapping_profile: output?.mapping_profile,
            steps: output?.steps,
            result: { stages: [{ scalar_results: [{ key: "youngs_modulus", value: scalarPa, unit: "Pa" }] }] },
          })], { type: "application/json" }),
        } as Response;
      }
      if (url.includes("/content")) return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
      } as Response;
      if (url.endsWith("/processing:preview") && init?.method === "POST") {
        const body = JSON.parse(String(init.body ?? "{}")) as { steps?: Array<{ method_id?: string; options?: { method?: string } }> };
        const scalarPa = body.steps?.find((step) => step.method_id === "metal.elastic_modulus")?.options?.method === "chord" ? 120e9 : 210e9;
        return jsonResponse({
          execution_mode: "preview",
          promotable: false,
          source_document_sha256: "d".repeat(64),
          mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
          independent_quantity: "strain.engineering",
          stages: [
            { ordinal: 0, method_id: "mapping", method_version: "1.0.0", point_count: 3, series: [{ quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] }, { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] }], diagnostics: [], scalar_results: [] },
            { ordinal: 1, method_id: "rows.sort_unique", method_version: "1.0.0", point_count: 3, series: [{ quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] }, { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] }], diagnostics: [], scalar_results: [] },
            { ordinal: 2, method_id: "metal.elastic_modulus", method_version: "1.0.0", point_count: 3, series: [{ quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] }, { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] }], diagnostics: [], scalar_results: [{ key: "youngs_modulus", quantity_semantics: "modulus.young", value: scalarPa, unit: "Pa" }] },
          ],
        });
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const initialSession = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Restore Process exact revisions",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: baseRef,
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      processingOutput: { id: chordOutput.processing_output_id, revisionId: chordOutput.current_revision.id, label: chordOutput.label, revisionNo: 1 },
      workspace: {
        activeStage: "process",
        selectedDocumentIds: [baseRef.id, replicateRef.id],
        selectedTestDataRefs: refs,
        visibleTestDataKeys: refs.map((ref) => `${ref.id}:${ref.revisionId}`),
        selectedStepIndex: 1,
        selectedStageOrdinal: 2,
        plotView: "pipeline",
        settingsOpen: true,
      },
    };
    const material = { material_id: "material-a", current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } } };
    const materialState = { material_state_id: "state-a", current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } } };
    const onSessionChange = vi.fn();
    const view = render(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={initialSession as never}
        locationSearch="?stage=process&family=metal"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
      />,
    );
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/test-data-documents"))).toBe(true));
    resolveDocuments?.(jsonResponse({ items: documents }));
    await waitFor(() => expect(document.querySelector(".method-library summary")?.textContent).toContain("5"));
    expect(workspacePatches(onSessionChange).length).toBeGreaterThan(0);
    const expectedRefKeys = refs.map((ref) => `${ref.id}:${ref.revisionId}`).join("|");
    const expectedIncludedIds = [baseRef.id, replicateRef.id].join("|");
    const assertRestoredWorkspace = () => expect(workspacePatches(onSessionChange).every((workspace) => {
      const refsInPatch = workspace.selectedTestDataRefs as Array<{ id: string; revisionId: string }> | undefined;
      const includedIds = workspace.selectedDocumentIds as string[] | undefined;
      return refsInPatch?.length === 3
        && refsInPatch.map((ref) => `${ref.id}:${ref.revisionId}`).join("|") === expectedRefKeys
        && includedIds?.length === 2
        && includedIds.join("|") === expectedIncludedIds;
    })).toBe(true);
    assertRestoredWorkspace();
    expect(onSessionChange.mock.calls.map(([patch]) => (patch as Record<string, unknown>).testData).filter(Boolean)).toEqual([]);

    view.rerender(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={initialSession as never}
        material={material as never}
        materialState={materialState as never}
        locationSearch="?stage=process&family=metal"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
      />,
    );
    await waitFor(() => expect(document.querySelectorAll(".curve-row-label")).toHaveLength(3));
    await screen.findByRole("button", { name: "Save processed curves" });
    assertRestoredWorkspace();
    expect(onSessionChange.mock.calls.map(([patch]) => (patch as Record<string, unknown>).testData).filter(Boolean)).toEqual([]);
    expect(await screen.findByText("No Process preview is active. Choose Use settings for a saved result, then select Preview changes to preview the draft.")).toBeTruthy();
    expect(screen.queryByText("Choose a saved Test Data revision. The graph compares real curves without changing saved data.")).toBeNull();
    expect(document.querySelector(".persistent-modeling-plot > .modeling-plot-toolbar")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(screen.getByText(/Preview ready\./)).toBeTruthy(), { timeout: 5000 });
    expect(processRailIdentities()).toEqual(expect.arrayContaining(["Specimen 01 · r1", "Specimen 02 · r1", "Specimen 03 · r1"]));
    expect(processRailIdentities().every((text) => /^Specimen \d{2} · r[1-9]\d*$/.test(text))).toBe(true);
    expect(Array.from(document.querySelectorAll(".modeling-workspace-stage-process .curve-row-label small"))).toHaveLength(0);
    expect(document.querySelector(".process-band-source")?.textContent).toBe("Specimen 01 · r1");
    expect(document.querySelector(".process-band-result")?.textContent).toContain("210.0 GPa");
    const savedDetails = document.querySelector("details.process-saved-results") as HTMLDetailsElement;
    expect(savedDetails.querySelector("summary")?.textContent).toContain("Saved results (2)");
    fireEvent.click(savedDetails.querySelector(":scope > summary")!);
    await waitFor(() => expect(savedDetails.querySelectorAll(".process-comparison-row")).toHaveLength(2));
    await waitFor(() => {
      const rows = Array.from(savedDetails.querySelectorAll(".process-comparison-row"), (row) => row.textContent ?? "");
      expect(rows.find((text) => text.includes("Robust 210"))).toContain("210.0 GPa");
      expect(rows.find((text) => text.includes("Chord 120"))).toContain("120.0 GPa");
      expect(rows.every((text) => !text.includes("Specimen 01 · r1"))).toBe(true);
      expect(rows.every((text) => text.includes("r1"))).toBe(true);
    });
    expect(Array.from(savedDetails.querySelectorAll(".process-comparison-row"), (row) => row.textContent ?? "").find((text) => text.includes("Chord 120"))).toContain("current");
    expect(fetchMock.mock.calls.filter(([input, init]) => String(input).endsWith("/processing-outputs") && init?.method !== "POST").length).toBeLessThanOrEqual(2);
    expect(screen.queryByText(/ERR_INSUFFICIENT_RESOURCES|Maximum update depth exceeded/)).toBeNull();
  });

  it("preserves older exact refs, membership, visibility and focus when Data enters Process", async () => {
    const currentRevision = {
      ...revision,
      id: "53000000-0000-4000-8000-000000000101",
      aggregate_id: documentResource.test_data_document_id,
      revision_no: 2,
    };
    const historicalDocuments = [
      { ...documentResource, current_revision: currentRevision },
      {
        ...replicateResource,
        current_revision: {
          ...currentRevision,
          id: "53000000-0000-4000-8000-000000000102",
          aggregate_id: replicateResource.test_data_document_id,
        },
      },
      {
        ...replicateResource,
        test_data_document_id: "53000000-0000-4000-8000-000000000022",
        current_revision: {
          ...currentRevision,
          id: "53000000-0000-4000-8000-000000000103",
          aggregate_id: "53000000-0000-4000-8000-000000000022",
        },
        document_key: "DP600-TENSILE-03",
        specimen_id: "S-3",
      },
    ];
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: historicalDocuments });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-outputs") || url.endsWith("/processing-ensemble-methods")
        || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: [
        "rows.sort_unique", "metal.elastic_modulus", "metal.proof_stress", "metal.necking_candidate",
        "metal.engineering_to_true_plastic", "metal.hardening_fit_extrapolate",
      ].map((methodId) => ({ method_id: methodId, version: "1.0.0", label: methodId, description: methodId, option_schema: {}, deterministic: true, allows_extrapolation: false })) });
      if (url.endsWith("/processing:preview") && init?.method === "POST") return jsonResponse({
        execution_mode: "preview",
        promotable: false,
        source_document_sha256: "d".repeat(64),
        mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
        independent_quantity: "strain.engineering",
        stages: [{
          ordinal: 0,
          method_id: "mapping",
          method_version: "1.0.0",
          point_count: 2,
          series: [
            { quantity: "strain.engineering", unit: "1", values: [0, 0.001] },
            { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8] },
          ],
          diagnostics: [],
          scalar_results: [],
        }],
      });
      if (url.includes("/content")) return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
      } as Response;
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const historicalRevisionIds = [revision.id, replicateResource.current_revision.id, "53000000-0000-4000-8000-000000000023"];
    const refs = historicalDocuments.map((item, index) => ({
      id: item.test_data_document_id,
      revisionId: historicalRevisionIds[index],
      label: item.document_key,
      revisionNo: 1,
    }));
    const initialSession = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Process exact older revisions",
      material: { id: "material-a", revisionId: "material-a-r2", label: "DP600", revisionNo: 2 },
      materialState: { id: "state-a", revisionId: "state-a-r2", label: "As received", revisionNo: 2 },
      testData: refs[0],
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      workspace: {
        activeStage: "data",
        selectedDocumentIds: refs.slice(0, 2).map((ref) => ref.id),
        selectedTestDataRefs: refs,
        visibleTestDataKeys: refs.map((ref) => `${ref.id}:${ref.revisionId}`),
        selectedStepIndex: 0,
        selectedStageOrdinal: 0,
        plotView: "pipeline",
        settingsOpen: true,
      },
    };
    const material = {
      material_id: "material-a",
      current_revision: { id: "material-a-r2", revision_no: 2, content: { name: "DP600" } },
    };
    const materialState = {
      material_state_id: "state-a",
      current_revision: { id: "state-a-r2", revision_no: 2, content: { name: "As received" } },
    };
    render(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={initialSession as never}
        material={material as never}
        materialState={materialState as never}
        locationSearch="?stage=data&family=metal"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
      />,
    );
    await waitFor(() => expect(document.querySelectorAll(".curve-row-label")).toHaveLength(3));
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:process" } }));
    await screen.findByRole("button", { name: "Save processed curves" });
    await waitFor(() => expect(document.querySelectorAll(".curve-row-label")).toHaveLength(3));
    expect(document.querySelector(".process-band-source")?.textContent).toContain("r1");
    expect(screen.getByText("3 curves · 2 included")).toBeTruthy();
    expect(screen.getAllByRole("checkbox", { name: /Include .* in processing and fit/ }).filter((input) => (input as HTMLInputElement).checked)).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /Show .* on plot|Hide .* on plot/ }).filter((button) => button.getAttribute("aria-pressed") === "true")).toHaveLength(3);
    expect(document.querySelectorAll(".modeling-dataset-list article.active")).toHaveLength(1);
    expect((screen.getByRole("button", { name: "Preview changes" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("settles one failed exact read, exposes explicit retry, and never falls back to stale bytes", async () => {
    const sourceId = documentResource.test_data_document_id;
    const missingId = replicateResource.test_data_document_id;
    const sourceRef = { id: sourceId, revisionId: revision.id, label: documentResource.document_key, revisionNo: 1 };
    const missingRef = { id: missingId, revisionId: replicateResource.current_revision.id, label: replicateResource.document_key, revisionNo: 1 };
    const session = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Exact read recovery",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: sourceRef,
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      workspace: {
        activeStage: "process",
        selectedDocumentIds: [sourceId],
        selectedTestDataRefs: [sourceRef, missingRef],
        visibleTestDataKeys: [`${sourceId}:${revision.id}`, `${missingId}:${replicateResource.current_revision.id}`],
        selectedStepIndex: 1,
        selectedStageOrdinal: 0,
        plotView: "pipeline",
        settingsOpen: true,
      },
    };
    let failedRead = true;
    let contentGets = 0;
    let previewPosts = 0;
    let outputPosts = 0;
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource, replicateResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-outputs") && init?.method === "POST") {
        outputPosts += 1;
        return jsonResponse({}, 201);
      }
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: [] });
      if (url.includes("/test-data-documents/") && url.endsWith("/content")) {
        contentGets += 1;
        const requestedId = decodeURIComponent(url.split("/test-data-documents/")[1].split("/")[0]);
        if (requestedId === missingId && failedRead) return jsonResponse({ detail: "missing exact source" }, 404);
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
        } as Response;
      }
      if (url.endsWith("/processing:preview") && init?.method === "POST") {
        previewPosts += 1;
        return jsonResponse({
          execution_mode: "preview",
          promotable: false,
          source_document_sha256: "d".repeat(64),
          mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
          independent_quantity: "strain.engineering",
          stages: [{
            ordinal: 0,
            method_id: "mapping",
            method_version: "1.0.0",
            point_count: 2,
            series: [
              { quantity: "strain.engineering", unit: "1", values: [0, 0.001] },
              { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8] },
            ],
            diagnostics: [],
            scalar_results: [{ key: "youngs_modulus", quantity_semantics: "modulus.young", value: 210e9, unit: "Pa" }],
          }],
        });
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const material = { material_id: "material-a", current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } } };
    const materialState = { material_state_id: "state-a", current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } } };
    const view = render(<CommonProcessingWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} initialSession={session as never} material={material as never} materialState={materialState as never} locationSearch="?stage=process&family=metal" onNavigate={() => undefined} onOpenConnection={() => undefined} />);
    await screen.findByRole("button", { name: "Save processed curves" });
    await waitFor(() => expect(contentGets).toBe(1));
    await waitFor(() => expect(processRailIdentities()).toContain("Specimen 02 · r1"));
    const previewPostsBeforeFailure = previewPosts;
    fireEvent.click(processRailButton("Specimen 02 · r1"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Retry exact source" })).toBeTruthy());
    expect(contentGets).toBe(2);
    expect(screen.getByText("Exact source unavailable · r1")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Preview changes" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Save processed curves" }) as HTMLButtonElement).disabled).toBe(true);
    const blockedProcessPanel = document.querySelector('[data-modeling-process-panel="ready"]');
    expect(blockedProcessPanel?.textContent ?? "").not.toMatch(/(?:210|120)\.0 GPa/);
    expect(screen.getByRole("img", { name: "Blocked engineering curve plot" })).toBeTruthy();
    expect(previewPosts).toBe(previewPostsBeforeFailure);
    view.rerender(<CommonProcessingWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} initialSession={session as never} material={material as never} materialState={materialState as never} locationSearch="?stage=process&family=metal" onNavigate={() => undefined} onOpenConnection={() => undefined} />);
    await new Promise((resolve) => setTimeout(resolve, 350));
    expect(contentGets).toBe(2);
    failedRead = false;
    fireEvent.click(screen.getByRole("button", { name: "Retry exact source" }));
    await waitFor(() => expect(processRailIdentities()).toContain("Specimen 02 · r1"));
    expect((screen.getByRole("button", { name: "Preview changes" }) as HTMLButtonElement).disabled).toBe(false);
    expect(outputPosts).toBe(0);
  });

  it.each(["success", "failure"] as const)("re-reads A after an explicit A→B→A selection when B %s", async (outcome) => {
    const sourceId = documentResource.test_data_document_id;
    const nextId = replicateResource.test_data_document_id;
    const sourceRef = { id: sourceId, revisionId: revision.id, label: documentResource.document_key, revisionNo: 1 };
    const nextRef = { id: nextId, revisionId: replicateResource.current_revision.id, label: replicateResource.document_key, revisionNo: 1 };
    const contentRequests: string[] = [];
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource, replicateResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: [] });
      if (url.includes("/test-data-documents/") && url.endsWith("/content")) {
        const requestedId = decodeURIComponent(url.split("/test-data-documents/")[1].split("/")[0]);
        contentRequests.push(requestedId);
        if (requestedId === nextId && outcome === "failure") return jsonResponse({ detail: "B unavailable" }, 404);
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
        } as Response;
      }
      if (url.endsWith("/processing:preview") && init?.method === "POST") return jsonResponse({
        execution_mode: "preview",
        promotable: false,
        source_document_sha256: "d".repeat(64),
        mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
        independent_quantity: "strain.engineering",
        stages: [{ ordinal: 0, method_id: "mapping", method_version: "1.0.0", point_count: 2, series: [], diagnostics: [], scalar_results: [] }],
      });
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const session = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Exact A B A selection",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: sourceRef,
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      workspace: { activeStage: "process", selectedDocumentIds: [sourceId], selectedTestDataRefs: [sourceRef, nextRef], visibleTestDataKeys: [`${sourceId}:${revision.id}`, `${nextId}:${replicateResource.current_revision.id}`], selectedStepIndex: 0, selectedStageOrdinal: 0, plotView: "pipeline", settingsOpen: true },
    };
    const material = { material_id: "material-a", current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } } };
    const materialState = { material_state_id: "state-a", current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } } };
    render(<CommonProcessingWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} initialSession={session as never} material={material as never} materialState={materialState as never} locationSearch="?stage=process&family=metal" onNavigate={() => undefined} onOpenConnection={() => undefined} />);
    await waitFor(() => expect(contentRequests).toEqual([sourceId]));
    await waitFor(() => expect(processRailIdentities()).toContain("Specimen 01 · r1"));
    fireEvent.click(processRailButton("Specimen 02 · r1"));
    await waitFor(() => expect(contentRequests).toEqual([sourceId, nextId]));
    if (outcome === "success") await waitFor(() => expect(processRailIdentities()).toContain("Specimen 02 · r1"));
    else await screen.findByRole("button", { name: "Retry exact source" });
    fireEvent.click(processRailButton("Specimen 01 · r1"));
    await waitFor(() => expect(contentRequests).toEqual([sourceId, nextId, sourceId]));
    await waitFor(() => expect(processRailIdentities()).toContain("Specimen 01 · r1"));
    expect(screen.queryByText("Exact source unavailable · r1")).toBeNull();
  });

  it.each(["success", "failure"] as const)("keeps the newest exact request authoritative when A is pending and B %s", async (outcome) => {
    const sourceId = documentResource.test_data_document_id;
    const nextId = replicateResource.test_data_document_id;
    const sourceRef = { id: sourceId, revisionId: revision.id, label: documentResource.document_key, revisionNo: 1 };
    const nextRef = { id: nextId, revisionId: replicateResource.current_revision.id, label: replicateResource.document_key, revisionNo: 1 };
    let contentGets = 0;
    let resolveA: ((response: Response) => void) | undefined;
    let rejectA: ((reason?: unknown) => void) | undefined;
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource, replicateResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: [] });
      if (url.includes("/test-data-documents/") && url.endsWith("/content")) {
        contentGets += 1;
        const requestedId = decodeURIComponent(url.split("/test-data-documents/")[1].split("/")[0]);
        if (requestedId === sourceId) {
          return new Promise<Response>((resolve, reject) => { resolveA = resolve; rejectA = reject; });
        }
        if (outcome === "failure") return jsonResponse({ detail: "B unavailable" }, 404);
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
        } as Response;
      }
      if (url.endsWith("/processing:preview") && init?.method === "POST") return jsonResponse({
        execution_mode: "preview",
        promotable: false,
        source_document_sha256: "d".repeat(64),
        mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
        independent_quantity: "strain.engineering",
        stages: [{ ordinal: 0, method_id: "mapping", method_version: "1.0.0", point_count: 2, series: [], diagnostics: [], scalar_results: [] }],
      });
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const session = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Exact request race",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: sourceRef,
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      workspace: { activeStage: "process", selectedDocumentIds: [sourceId], selectedTestDataRefs: [sourceRef, nextRef], visibleTestDataKeys: [`${sourceId}:${revision.id}`, `${nextId}:${replicateResource.current_revision.id}`], selectedStepIndex: 0, selectedStageOrdinal: 0, plotView: "pipeline", settingsOpen: true },
    };
    const material = { material_id: "material-a", current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } } };
    const materialState = { material_state_id: "state-a", current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } } };
    render(<CommonProcessingWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} initialSession={session as never} material={material as never} materialState={materialState as never} locationSearch="?stage=process&family=metal" onNavigate={() => undefined} onOpenConnection={() => undefined} />);
    await waitFor(() => expect(contentGets).toBe(1));
    fireEvent.click(processRailButton("Specimen 02 · r1"));
    await waitFor(() => expect(contentGets).toBe(2));
    if (outcome === "success") await waitFor(() => expect(processRailIdentities()).toContain("Specimen 02 · r1"));
    else await waitFor(() => expect(screen.getByRole("button", { name: "Retry exact source" })).toBeTruthy());
    resolveA?.({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
    } as Response);
    await new Promise((resolve) => setTimeout(resolve, 250));
    expect(contentGets).toBe(2);
    if (outcome === "success") {
      expect(processRailIdentities()).toContain("Specimen 02 · r1");
      expect(document.querySelector(".process-band-source")?.textContent).toBe("Specimen 02 · r1");
    } else {
      expect(screen.getByText("Exact source unavailable · r1")).toBeTruthy();
      expect(screen.getByRole("button", { name: "Retry exact source" })).toBeTruthy();
    }
    rejectA?.(new Error("late A failure"));
  });

  it("coalesces StrictMode exact Fit restore, applies once, and settles the identity", async () => {
    installFitRestoreParserMock();
    const fixtures = fitRestoreFixtures();
    const fetchState = stubFitRestoreFetch([fixtures.fit, fixtures.process]);
    let view: ReturnType<typeof render> | undefined;
    try {
      view = render(
        <StrictMode>
          <CommonProcessingWorkbench
            config={{ baseUrl: "/api/v1", accessToken: "token" }}
            initialSession={fixtures.session as never}
            material={fixtures.material as never}
            materialState={fixtures.materialState as never}
            locationSearch="?stage=fit&family=metal"
            onNavigate={() => undefined}
            onOpenConnection={() => undefined}
          />
        </StrictMode>,
      );
      await waitFor(() => expect(fetchState.contentGets()).toBe(1));
      expect(fetchState.pendingContent).toHaveLength(1);
      fetchState.pendingContent[0].resolve(fitRestoreContentResponse("B"));
      await screen.findByText("Saved immutable Fit Output restored with its exact Process source and decision.");
      expect(screen.getAllByText("Saved immutable Fit Output restored with its exact Process source and decision.")).toHaveLength(1);
      await screen.findByText("Saved current", { exact: true });
      await new Promise((resolve) => setTimeout(resolve, 400));
      expect(fetchState.contentGets()).toBe(1);
      expect(fetchState.fitRunPosts()).toBe(0);
      expect(screen.getByText("Saved current", { exact: true })).toBeTruthy();
    } finally {
      view?.unmount();
      vi.doUnmock("./modeling-fit-output");
    }
  });

  it("keeps a mounted Fit save notice through exact restore and restores the notice after remount", async () => {
    installFitRestoreParserMock();
    const fixtures = fitRestoreFixtures();
    const processRevision = fixtures.process.current_revision as Record<string, unknown>;
    const processRef = {
      id: fixtures.process.processing_output_id,
      revisionId: processRevision.id,
      label: fixtures.process.label,
      revisionNo: processRevision.revision_no,
    };
    const fixtureWorkspace = fixtures.session.workspace as Record<string, unknown>;
    const initialSession = {
      ...fixtures.session,
      processingOutput: processRef,
      workspace: { ...fixtureWorkspace, selectedStageOrdinal: 0 },
    };
    const committed: Array<Record<string, unknown>> = [];
    const fitPreview = metalFitCalculationPreview();
    let contentGets = 0;
    const onSessionChange = vi.fn();
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: [
        ...processMethodFixtures(),
        { method_id: "metal.hardening_fit_extrapolate", version: "1.0.0", label: "Hardening fit", description: "Hardening fit", option_schema: {}, deterministic: true, allows_extrapolation: true },
      ] });
      if (url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.endsWith("/metal-fit-runs") && init?.method === "POST") return jsonResponse({
        id: "fit-run-save-restore",
        status: "succeeded",
        preview: fitPreview,
        failure_code: null,
        failure_reason: null,
      });
      if (url.endsWith("/processing-outputs") && init?.method === "POST") {
        const body = JSON.parse(String(init.body ?? "{}")) as Record<string, unknown>;
        const saved = {
          ...fixtures.process,
          processing_output_id: "saved-fit-output",
          current_revision: { ...processRevision, id: "saved-fit-output-revision", aggregate_id: "saved-fit-output" },
          label: String(body.label ?? "Saved Fit output"),
          source_document: body.source_document,
          mapping_profile: body.mapping_profile,
          steps: body.steps,
          source_processing_output: body.source_processing_output,
          source_processing_output_sha256: fixtures.process.output_sha256,
          output_sha256: "8".repeat(64),
          stage_count: 7,
          fit_decision: body.fit_decision ?? null,
        };
        committed.push(saved);
        return jsonResponse(saved, 201);
      }
      if (url.includes("/processing-outputs/") && url.endsWith("/content")) {
        contentGets += 1;
        return fitRestoreContentResponse("B");
      }
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: [fixtures.process, ...committed] });
      if (url.includes("/test-data-documents/") && url.endsWith("/content")) return fitRestoreContentResponse(JSON.stringify(documentJson));
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const renderWorkbench = (session: Record<string, unknown>) => (
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={session as never}
        material={fixtures.material as never}
        materialState={fixtures.materialState as never}
        locationSearch="?stage=fit&family=metal"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
      />
    );
    let view: ReturnType<typeof render> | undefined;
    const restoredNotice = "Saved immutable Fit Output restored with its exact Process source and decision.";
    try {
      view = render(renderWorkbench(initialSession));
      await waitFor(() => expect(screen.getByText("Preview ready.", { exact: false })).toBeTruthy(), { timeout: 5000 });
      expect(document.querySelector(".modeling-workspace-stage-fit")).toBeTruthy();
      fireEvent.click(screen.getByText("Candidate parameters"));
      await screen.findByText("Fit evidence");
      fireEvent.click(await screen.findByRole("button", { name: /Select swift candidate/i }));
      fireEvent.change(screen.getByLabelText("Candidate selection reason"), { target: { value: "Select Swift for the deterministic save/restore regression." } });
      fireEvent.click(screen.getByRole("button", { name: "Save fit & continue" }));
      await screen.findByText(/New immutable Fit Output saved and current/i);
      expect(committed).toHaveLength(1);

      const saved = committed[0];
      const savedRevision = saved.current_revision as Record<string, unknown>;
      const savedSession = {
        ...initialSession,
        processingOutput: {
          id: saved.processing_output_id,
          revisionId: savedRevision.id,
          label: saved.label,
          revisionNo: savedRevision.revision_no,
        },
        workspace: { ...(initialSession.workspace as Record<string, unknown>), selectedStageOrdinal: 6 },
      };
      view.rerender(renderWorkbench(savedSession));
      await waitFor(() => expect(contentGets).toBe(1));
      await waitFor(() => expect(screen.getByText(/New immutable Fit Output saved and current/i)).toBeTruthy());
      expect(screen.queryByText(restoredNotice)).toBeNull();
      expect(document.querySelector(".persistent-modeling-plot h2")?.textContent ?? "").toContain("Hardening response");

      view.unmount();
      view = render(renderWorkbench(savedSession));
      await screen.findByText(restoredNotice);
      expect(contentGets).toBe(2);
      expect(document.querySelector(".persistent-modeling-plot h2")?.textContent ?? "").toContain("Hardening response");
    } finally {
      view?.unmount();
      vi.doUnmock("./modeling-fit-output");
    }
  });

  it("gives a changed restore identity a distinct request and ignores the stale response", async () => {
    installFitRestoreParserMock();
    const fixtures = fitRestoreFixtures();
    const fetchState = stubFitRestoreFetch([fixtures.fit, fixtures.process]);
    let view: ReturnType<typeof render> | undefined;
    try {
      const renderRestore = (accessToken: string) => (
        <StrictMode>
          <CommonProcessingWorkbench
            config={{ baseUrl: "/api/v1", accessToken }}
            initialSession={fixtures.session as never}
            material={fixtures.material as never}
            materialState={fixtures.materialState as never}
            locationSearch="?stage=fit&family=metal"
            onNavigate={() => undefined}
            onOpenConnection={() => undefined}
          />
        </StrictMode>
      );
      view = render(renderRestore("token-a"));
      await waitFor(() => expect(fetchState.contentGets()).toBe(1));
      view.rerender(renderRestore("token-b"));
      await waitFor(() => expect(fetchState.contentGets()).toBe(2));
      fetchState.pendingContent[0].resolve(fitRestoreContentResponse("A"));
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(document.querySelector(".persistent-modeling-plot h2")?.textContent ?? "").not.toContain("Proof stress");
      fetchState.pendingContent[1].resolve(fitRestoreContentResponse("B"));
      await waitFor(() => expect(document.querySelector(".persistent-modeling-plot h2")?.textContent ?? "").toContain("Hardening response"));
    } finally {
      view?.unmount();
      vi.doUnmock("./modeling-fit-output");
    }
  });

  it("settles a failed restore without a loop and retries exactly once", async () => {
    installFitRestoreParserMock();
    const fixtures = fitRestoreFixtures();
    const fetchState = stubFitRestoreFetch([fixtures.fit, fixtures.process]);
    let view: ReturnType<typeof render> | undefined;
    try {
      view = render(
        <StrictMode>
          <CommonProcessingWorkbench
            config={{ baseUrl: "/api/v1", accessToken: "token" }}
            initialSession={fixtures.session as never}
            material={fixtures.material as never}
            materialState={fixtures.materialState as never}
            locationSearch="?stage=fit&family=metal"
            onNavigate={() => undefined}
            onOpenConnection={() => undefined}
          />
        </StrictMode>,
      );
      await waitFor(() => expect(fetchState.contentGets()).toBe(1));
      fetchState.pendingContent[0].resolve(fitRestoreContentResponse("forced restore failure", 503));
      const retry = await screen.findByRole("button", { name: "Retry exact saved Fit" });
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(fetchState.contentGets()).toBe(1);
      fireEvent.click(retry);
      await waitFor(() => expect(fetchState.contentGets()).toBe(2));
      expect(fetchState.pendingContent).toHaveLength(2);
      fetchState.pendingContent[1].resolve(fitRestoreContentResponse("B"));
      await screen.findByText("Saved immutable Fit Output restored with its exact Process source and decision.");
      expect(fetchState.contentGets()).toBe(2);
    } finally {
      view?.unmount();
      vi.doUnmock("./modeling-fit-output");
    }
  });

  it("keeps an unmounted Fit restore response inert", async () => {
    installFitRestoreParserMock();
    const fixtures = fitRestoreFixtures();
    const fetchState = stubFitRestoreFetch([fixtures.fit, fixtures.process]);
    let view: ReturnType<typeof render> | undefined;
    try {
      view = render(
        <StrictMode>
          <CommonProcessingWorkbench
            config={{ baseUrl: "/api/v1", accessToken: "token" }}
            initialSession={fixtures.session as never}
            material={fixtures.material as never}
            materialState={fixtures.materialState as never}
            locationSearch="?stage=fit&family=metal"
            onNavigate={() => undefined}
            onOpenConnection={() => undefined}
          />
        </StrictMode>,
      );
      await waitFor(() => expect(fetchState.contentGets()).toBe(1));
      view.unmount();
      fetchState.pendingContent[0].resolve(fitRestoreContentResponse("B"));
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(screen.queryByText("Saved immutable Fit Output restored with its exact Process source and decision.")).toBeNull();
    } finally {
      view?.unmount();
      vi.doUnmock("./modeling-fit-output");
    }
  });

  it("treats every pinned Fit/Process identity determinant as a distinct restore request", async () => {
    installFitRestoreParserMock();
    type RestoreMutation = {
      label: string;
      apply: (fit: Record<string, unknown>, process: Record<string, unknown>, session: Record<string, unknown>) => string;
    };
    const mutations: RestoreMutation[] = [
      { label: "base URL", apply: () => "/api/v2" },
      {
        label: "Fit aggregate",
        apply: (fit, _process, session) => {
          fit.processing_output_id = "restore-fit-output-next";
          (fit.current_revision as Record<string, unknown>).aggregate_id = fit.processing_output_id;
          (session.processingOutput as Record<string, unknown>).id = fit.processing_output_id;
          return "/api/v1";
        },
      },
      {
        label: "Fit revision id",
        apply: (fit, _process, session) => {
          const nextRevisionId = "restore-fit-revision-next";
          (fit.current_revision as Record<string, unknown>).id = nextRevisionId;
          (session.processingOutput as Record<string, unknown>).revisionId = nextRevisionId;
          return "/api/v1";
        },
      },
      {
        label: "Fit revision number",
        apply: (fit) => {
          (fit.current_revision as Record<string, unknown>).revision_no = 2;
          return "/api/v1";
        },
      },
      {
        label: "Fit revision hash",
        apply: (fit) => {
          (fit.current_revision as Record<string, unknown>).content_hash = "b".repeat(64);
          return "/api/v1";
        },
      },
      {
        label: "Fit output digest",
        apply: (fit) => {
          fit.output_sha256 = "8".repeat(64);
          return "/api/v1";
        },
      },
      {
        label: "Process aggregate",
        apply: (fit, process) => {
          process.processing_output_id = "restore-process-output-next";
          (process.current_revision as Record<string, unknown>).aggregate_id = process.processing_output_id;
          (fit.source_processing_output as Record<string, unknown>).aggregate_id = process.processing_output_id;
          return "/api/v1";
        },
      },
      {
        label: "Process revision id",
        apply: (fit, process) => {
          const nextRevisionId = "restore-process-revision-next";
          (process.current_revision as Record<string, unknown>).id = nextRevisionId;
          (fit.source_processing_output as Record<string, unknown>).revision_id = nextRevisionId;
          return "/api/v1";
        },
      },
      {
        label: "Process revision number",
        apply: (_fit, process) => {
          (process.current_revision as Record<string, unknown>).revision_no = 2;
          return "/api/v1";
        },
      },
      {
        label: "Process revision hash",
        apply: (_fit, process) => {
          (process.current_revision as Record<string, unknown>).content_hash = "c".repeat(64);
          return "/api/v1";
        },
      },
      {
        label: "Process output digest",
        apply: (_fit, process) => {
          process.output_sha256 = "7".repeat(64);
          return "/api/v1";
        },
      },
      {
        label: "Test Data pin",
        apply: (_fit, process) => {
          (process.source_document as Record<string, unknown>).revision_id = "test-data-revision-next";
          return "/api/v1";
        },
      },
      {
        label: "Test Data digest",
        apply: (_fit, process) => {
          process.source_document_sha256 = "6".repeat(64);
          return "/api/v1";
        },
      },
      {
        label: "Profile pin",
        apply: (_fit, process) => {
          (process.mapping_profile as Record<string, unknown>).revision_id = "profile-revision-next";
          return "/api/v1";
        },
      },
      {
        label: "Profile digest",
        apply: (_fit, process) => {
          process.mapping_profile_sha256 = "5".repeat(64);
          return "/api/v1";
        },
      },
      {
        label: "canonical digest",
        apply: (_fit, process) => {
          process.source_canonical_artifact_sha256 = "4".repeat(64);
          return "/api/v1";
        },
      },
      {
        label: "ordered steps",
        apply: (_fit, process) => {
          process.steps = [{ method_id: "rows.sort_unique", method_version: "1.0.0", options: {} }, ...(process.steps as Array<Record<string, unknown>>)];
          return "/api/v1";
        },
      },
      {
        label: "stage count",
        apply: (_fit, process) => {
          process.stage_count = Number(process.stage_count) + 1;
          return "/api/v1";
        },
      },
      {
        label: "independent quantity",
        apply: (_fit, process) => {
          process.independent_quantity = "time";
          return "/api/v1";
        },
      },
    ];
    let currentFit: Record<string, unknown>;
    let currentProcess: Record<string, unknown>;
    const first = fitRestoreFixtures();
    currentFit = first.fit;
    currentProcess = first.process;
    const fetchState = stubFitRestoreFetch(() => [currentFit, currentProcess]);
    let view: ReturnType<typeof render> | undefined;
    try {
      const renderRestore = (session: Record<string, unknown>, baseUrl: string) => (
        <StrictMode>
          <CommonProcessingWorkbench
            config={{ baseUrl, accessToken: "token" }}
            initialSession={session as never}
            material={first.material as never}
            materialState={first.materialState as never}
            locationSearch="?stage=fit&family=metal"
            onNavigate={() => undefined}
            onOpenConnection={() => undefined}
          />
        </StrictMode>
      );
      view = render(renderRestore(first.session, "/api/v1"));
      await waitFor(() => expect(fetchState.contentGets()).toBe(1));
      fetchState.pendingContent[0].resolve(fitRestoreContentResponse("B"));
      await screen.findByText("Saved immutable Fit Output restored with its exact Process source and decision.");
      for (const [index, mutation] of mutations.entries()) {
        const next = fitRestoreFixtures();
        const nextBaseUrl = mutation.apply(next.fit, next.process, next.session);
        currentFit = next.fit;
        currentProcess = next.process;
        view.rerender(renderRestore(next.session, nextBaseUrl));
        await waitFor(() => expect(fetchState.contentGets()).toBe(index + 2), { timeout: 3000 });
        fetchState.pendingContent[index + 1].resolve(fitRestoreContentResponse("B"));
        await new Promise((resolve) => setTimeout(resolve, 20));
      }
      expect(fetchState.contentGets()).toBe(mutations.length + 1);
    } finally {
      view?.unmount();
      vi.doUnmock("./modeling-fit-output");
    }
  });
});
