import { createHash } from "node:crypto";

export const FIXTURE_ID = "issue-189-synthetic-metal-v1";
export const SESSION_STORAGE_KEY = "cmp.modeling.recent-session.v4";

const IDS = Object.freeze({
  material: "18900000-0000-4000-8000-000000000001",
  materialRevision: "18900000-0000-4000-8000-000000000002",
  state: "18900000-0000-4000-8000-000000000003",
  stateRevision: "18900000-0000-4000-8000-000000000004",
  propertySet: "18900000-0000-4000-8000-000000000005",
  propertyRevision: "18900000-0000-4000-8000-000000000006",
  document: "18900000-0000-4000-8000-000000000007",
  documentRevision: "18900000-0000-4000-8000-000000000008",
  canonicalArtifact: "18900000-0000-4000-8000-000000000009",
  normalizedArtifact: "18900000-0000-4000-8000-000000000010",
  mapping: "18900000-0000-4000-8000-000000000011",
  mappingRevision: "18900000-0000-4000-8000-000000000012",
  processOutput: "18900000-0000-4000-8000-000000000013",
  processRevision: "18900000-0000-4000-8000-000000000014",
  processArtifact: "18900000-0000-4000-8000-000000000015",
  fitOutput: "18900000-0000-4000-8000-000000000016",
  fitRevision: "18900000-0000-4000-8000-000000000017",
  fitArtifact: "18900000-0000-4000-8000-000000000018",
  candidate: "18900000-0000-4000-8000-000000000019",
  ir: "18900000-0000-4000-8000-000000000020",
  irRevision: "18900000-0000-4000-8000-000000000021",
  neutral: "18900000-0000-4000-8000-000000000022",
  neutralRevision: "18900000-0000-4000-8000-000000000023",
});

const HASHES = Object.freeze({
  mapping: "abcdeffedcba0123456789abcdef0123456789abcdef0123456789abcdef0123",
  canonical: "c".repeat(64),
  normalized: "d".repeat(64),
});

const revision = (id, aggregateId, contentHash, classification = "internal") => ({
  id,
  aggregate_id: aggregateId,
  revision_no: 1,
  based_on_revision_id: null,
  schema_id: "urn:cmp:synthetic:1.0.0",
  schema_version: "1.0.0",
  content_hash: contentHash,
  created_at: "2026-08-08T00:00:00Z",
  created_by: "18900000-0000-4000-8000-000000000099",
  change_reason: "Issue 189 bounded synthetic fixture",
  organization_id: "18900000-0000-4000-8000-000000000090",
  project_id: "18900000-0000-4000-8000-000000000091",
  classification,
  lifecycle_state: "draft",
});

const materialRevision = revision(IDS.materialRevision, IDS.material, "a".repeat(64));
const stateRevision = revision(IDS.stateRevision, IDS.state, "b".repeat(64));
const propertyRevision = revision(IDS.propertyRevision, IDS.propertySet, "e".repeat(64));
const documentRevision = revision(IDS.documentRevision, IDS.document, HASHES.canonical);
const mappingRevision = revision(IDS.mappingRevision, IDS.mapping, HASHES.mapping);

export const material = {
  material_id: IDS.material,
  current_revision: {
    ...materialRevision,
    content: {
      name: "Issue 189 synthetic metal",
      material_code: "CMP-189-METAL",
      material_family: "metal",
      material_class: "metal",
      description: "Bounded non-production measurement fixture",
    },
  },
  links: { self: `/api/v1/materials/${IDS.material}`, revisions: "", states: "" },
};

export const materialState = {
  material_state_id: IDS.state,
  material_id: IDS.material,
  current_revision: {
    ...stateRevision,
    content: {
      material_id: IDS.material,
      material_revision_id: IDS.materialRevision,
      name: "As received",
      manufacturing_route: null,
      heat_treatment: null,
      lot_or_batch: "ISSUE-189",
      description: "Synthetic state",
    },
  },
  property_sets_url: `/api/v1/material-states/${IDS.state}/property-sets`,
};

export const propertySet = {
  property_set_id: IDS.propertySet,
  material_state_id: IDS.state,
  current_revision: {
    ...propertyRevision,
    content: {
      material_state_id: IDS.state,
      material_state_revision_id: IDS.stateRevision,
      density_kg_per_m3: 7850,
      density_source: { kind: "fixture", reference: null },
      youngs_modulus_pa: 210000000000,
      youngs_modulus_source: { kind: "fixture", reference: null },
      poisson_ratio: 0.3,
      poisson_ratio_source: { kind: "fixture", reference: null },
      yield_stress_pa: 320000000,
      yield_stress_source: { kind: "fixture", reference: null },
      applicability: {
        temperature_min_k: null,
        temperature_max_k: null,
        strain_rate_min_per_s: null,
        strain_rate_max_per_s: null,
        note: "Synthetic only",
      },
    },
  },
};

const governedSource = {
  material: { aggregate_id: IDS.material, revision_id: IDS.materialRevision },
  material_state: { aggregate_id: IDS.state, revision_id: IDS.stateRevision },
  test_run: { aggregate_id: "18900000-0000-4000-8000-000000000024", revision_id: "18900000-0000-4000-8000-000000000025" },
};

export const testDataDocument = {
  test_data_document_id: IDS.document,
  current_revision: documentRevision,
  document_key: "ISSUE-189-SYNTHETIC-METAL",
  material_maker: "CMP synthetic",
  material_grade: "SYN-METAL-189",
  lot_batch: "ISSUE-189",
  test_date: "2026-08-08",
  operator: "CMP fixture",
  laboratory: "CMP fixture lab",
  method: "tensile",
  specimen_id: "SYN-189-01",
  point_count: 7,
  canonical_artifact_id: IDS.canonicalArtifact,
  canonical_sha256: HASHES.canonical,
  normalized_artifact_id: IDS.normalizedArtifact,
  normalized_sha256: HASHES.normalized,
  channels: [
    { key: "engineering_strain", name: "Engineering strain", quantity_semantics: "mechanics.strain.engineering", axis_role: "independent", original_unit_string: "1", normalized_unit: "1", point_count: 7, missing_count: 0 },
    { key: "engineering_stress", name: "Engineering stress", quantity_semantics: "mechanics.stress.engineering", axis_role: "dependent", original_unit_string: "MPa", normalized_unit: "Pa", point_count: 7, missing_count: 0 },
  ],
  governed_source: governedSource,
};

export const testDataContent = {
  document_type: "cmp.test-data",
  schema_version: "1.0.0",
  document_id: "ISSUE-189-SYNTHETIC-METAL",
  channels: {
    engineering_strain: [0, 0.01, 0.025, 0.04, 0.06, 0.08, 0.1],
    engineering_stress: [320000000, 360000000, 410000000, 450000000, 490000000, 520000000, 545000000],
  },
};

export const mappingProfile = {
  mapping_profile_id: IDS.mapping,
  current_revision: mappingRevision,
  content: {
    profile_key: "issue-189-synthetic-metal",
    label: "Issue 189 synthetic metal mapping",
    independent_quantity: "strain.engineering",
    missing_data_policy: "drop_any",
    bindings: [
      { channel_key: "engineering_strain", target_quantity: "strain.engineering", accepted_normalized_units: ["1"], required: true, scale: 1, offset: 0 },
      { channel_key: "engineering_stress", target_quantity: "stress.engineering", accepted_normalized_units: ["Pa"], required: true, scale: 1, offset: 0 },
    ],
    attribute_bindings: [],
  },
};

const processSteps = [
  { method_id: "rows.sort_unique", method_version: "1.0.0", options: { duplicate_policy: "reject" } },
  { method_id: "metal.elastic_modulus", method_version: "1.0.0", options: { method: "robust_huber", minimum_strain: 0.0002, maximum_strain: 0.002, manual_modulus_pa: 210000000000 } },
  { method_id: "metal.proof_stress", method_version: "1.0.0", options: { offset_strain: 0.002, youngs_modulus_pa: 210000000000 } },
  { method_id: "metal.necking_candidate", method_version: "1.0.0", options: { method: "peak_engineering_stress" } },
  { method_id: "metal.engineering_to_true_plastic", method_version: "1.0.0", options: { necking_policy: "observed_full_domain", manual_necking_index: 6, youngs_modulus_pa: 210000000000 } },
];

const fitStep = {
  method_id: "metal.hardening_fit_extrapolate",
  method_version: "1.0.0",
  options: {
    equation_contract: "cmp.metal-hardening.altair-2025.v1",
    plastic_strain_quantity: "strain.true_plastic",
    stress_quantity: "stress.true",
    families: ["voce", "swift", "hockett_sherby", "ghosh"],
    fit_minimum_strain: 0,
    fit_maximum_strain: 0.1,
    extrapolation_maximum_strain: 1,
    output_point_count: 101,
    primary_family: "swift",
    secondary_family: "voce",
    primary_weight: 0.5,
    normalization_stress_pa: 100000000,
    maximum_function_evaluations: 5000,
  },
};

const sourceDocumentSha = "d".repeat(64);
const processOutputSha = "a1".repeat(32);

function stage(ordinal, methodId, pointCount, series, fitCandidates = []) {
  return { ordinal, method_id: methodId, method_version: "1.0.0", point_count: pointCount, series, diagnostics: [], scalar_results: [], fit_candidates: fitCandidates };
}

const observedStrain = [0, 0.01, 0.025, 0.04, 0.06, 0.08, 0.1];
const observedStress = [320000000, 360000000, 410000000, 450000000, 490000000, 520000000, 545000000];
const selectedStrain = Array.from({ length: 101 }, (_, index) => index / 100);
const selectedStress = Array.from({ length: 101 }, (_, index) => 320000000 + index * 2250000);
const genericStages = [
  stage(0, "mapping", 7, [{ quantity: "strain.engineering", unit: "1", values: observedStrain }, { quantity: "stress.engineering", unit: "Pa", values: observedStress }]),
  ...processSteps.map((step, index) => stage(index + 1, step.method_id, 7, [{ quantity: "strain.engineering", unit: "1", values: observedStrain }, { quantity: "stress.engineering", unit: "Pa", values: observedStress }])),
];
const processPreview = {
  execution_mode: "preview",
  promotable: false,
  source_document_sha256: sourceDocumentSha,
  mapping_profile_sha256: HASHES.mapping,
  independent_quantity: "strain.engineering",
  stages: genericStages,
};

function candidate(family) {
  const parameterNames = [family === "ghosh" ? "delta_p_minus_n" : "coefficient"];
  return {
    family,
    response: Array.from({ length: 101 }, () => 1),
    residual: [0.1, 0.1],
    tangent: Array.from({ length: 101 }, () => 1),
    parameter_names: parameterNames,
    parameter_units: parameterNames.map(() => "Pa"),
    lower: parameterNames.map(() => 0),
    initial: parameterNames.map(() => 0.5),
    fitted: parameterNames.map(() => 0.6),
    upper: parameterNames.map(() => 1),
    rmse_pa: 1,
    relative_rmse: 0.01,
    objective: 0.02,
    scipy_cost: 0.01,
    jacobian_tolerance: 1e-12,
    convergence: true,
    nfev: 2,
    active_bound: [],
    jacobian_rank: 1,
    jacobian_condition: null,
    identifiability: "identified",
    uncertainty: "not_provided",
    objective_history: [1, 0.1],
    optimizer_status: 1,
    optimizer_message: "converged",
  };
}

const fitCandidates = ["voce", "swift", "hockett_sherby", "ghosh"].map(candidate);
const fitDecision = {
  candidate_key: "voce",
  mode: "single",
  primary_law: "voce",
  secondary_law: null,
  primary_weight: null,
  parameter_sets: [{ law: "voce", parameters: [{ name: "coefficient", value: 0.6, unit: "Pa", lower: 0, upper: 1 }] }],
  fit_minimum: 0,
  fit_maximum: 0.1,
  extrapolation_maximum: 1,
  extrapolation_policy: "bounded",
  metric_definition: "relative_rmse",
  metric_value: 0.01,
  requested_term_policy: null,
  actual_term_count: null,
  selection_reason: "Synthetic issue 189 candidate",
  warning_acknowledged: true,
};
const fitStages = [
  ...genericStages,
  stage(6, fitStep.method_id, 101, [
    { quantity: "strain.true_plastic", unit: "1", values: selectedStrain },
    { quantity: "stress.true", unit: "Pa", values: selectedStress },
    { quantity: "stress.hardening.voce", unit: "Pa", values: selectedStress },
    { quantity: "stress.hardening.swift", unit: "Pa", values: selectedStress },
    { quantity: "stress.hardening.hockett_sherby", unit: "Pa", values: selectedStress },
    { quantity: "stress.hardening.ghosh", unit: "Pa", values: selectedStress },
    { quantity: "stress.hardening.selected", unit: "Pa", values: selectedStress },
  ], fitCandidates),
];

export const processOutput = {
  processing_output_id: IDS.processOutput,
  current_revision: revision(IDS.processRevision, IDS.processOutput, "f".repeat(64)),
  label: "Issue 189 Process output",
  source_document: { aggregate_id: IDS.document, revision_id: IDS.documentRevision },
  source_document_sha256: sourceDocumentSha,
  source_canonical_artifact_sha256: HASHES.canonical,
  mapping_profile: { aggregate_id: IDS.mapping, revision_id: IDS.mappingRevision },
  mapping_profile_sha256: HASHES.mapping,
  steps: processSteps,
  independent_quantity: "strain.engineering",
  stage_count: 6,
  final_point_count: 7,
  output_artifact_id: IDS.processArtifact,
  output_sha256: processOutputSha,
  source_processing_output: null,
  source_processing_output_sha256: null,
  workup_overrides: [],
  fit_decision: null,
  export_provenance: governedSource,
};

export const fitOutput = {
  processing_output_id: IDS.fitOutput,
  current_revision: revision(IDS.fitRevision, IDS.fitOutput, "f".repeat(64)),
  label: "Issue 189 Fit output",
  source_document: processOutput.source_document,
  source_document_sha256: sourceDocumentSha,
  source_canonical_artifact_sha256: HASHES.canonical,
  mapping_profile: processOutput.mapping_profile,
  mapping_profile_sha256: HASHES.mapping,
  steps: [...processSteps, fitStep],
  independent_quantity: "strain.engineering",
  stage_count: 7,
  final_point_count: 101,
  output_artifact_id: IDS.fitArtifact,
  output_sha256: "",
  source_processing_output: { aggregate_id: IDS.processOutput, revision_id: IDS.processRevision },
  source_processing_output_sha256: processOutputSha,
  workup_overrides: [],
  fit_decision: fitDecision,
  export_provenance: governedSource,
};

export const fitDocument = {
  document_type: "cmp.processing-output",
  document_version: "1.3.0",
  output_id: IDS.fitOutput,
  source_processing_output: fitOutput.source_processing_output,
  source_processing_output_sha256: processOutputSha,
  source_document: fitOutput.source_document,
  mapping_profile: fitOutput.mapping_profile,
  source_canonical_artifact_sha256: HASHES.canonical,
  steps: fitOutput.steps,
  fit_decision: fitDecision,
  result: {
    source_document_sha256: sourceDocumentSha,
    mapping_profile_sha256: HASHES.mapping,
    independent_quantity: "strain.engineering",
    stages: fitStages,
  },
};

const fitDocumentBytes = Buffer.from(JSON.stringify(fitDocument));
fitOutput.output_sha256 = createHash("sha256").update(fitDocumentBytes).digest("hex");

const methods = [
  ["rows.sort_unique", "Sort and de-duplicate rows"],
  ["metal.elastic_modulus", "Elastic modulus"],
  ["metal.proof_stress", "Proof stress"],
  ["metal.necking_candidate", "Necking candidate"],
  ["metal.engineering_to_true_plastic", "True plastic conversion"],
  ["metal.hardening_fit_extrapolate", "Hardening fit and extrapolation"],
].map(([method_id, label]) => ({ method_id, version: "1.0.0", label, description: "Synthetic fixture method", option_schema: {}, deterministic: true, allows_extrapolation: method_id.includes("fit") }));

export const elastoplasticCapabilities = {
  model_family_id: "cmp.reference-elastoplastic",
  model_schema_version: "1.3.0",
  model_schema_digest: "e".repeat(64),
  exporters: [{ exporter_id: "reference-elastoplastic", exporter_version: "2026.1", exporter_digest: "f".repeat(64), solver: "openradioss", version: "2025", unit_system: "kg_m_s", keywords: ["/MAT/LAW36"] }],
  mapping_statuses: ["exact", "transformed", "approximated", "unsupported"],
  non_production: true,
};

function ref(id, revisionId, label, revisionNo = 1) {
  return { id, revisionId, label, revisionNo };
}
const documentRef = ref(IDS.document, IDS.documentRevision, testDataDocument.document_key);
const mappingRef = ref(IDS.mapping, IDS.mappingRevision, mappingProfile.content.label);
const processRef = ref(IDS.processOutput, IDS.processRevision, processOutput.label);
const fitRef = ref(IDS.fitOutput, IDS.fitRevision, fitOutput.label);
const materialRef = ref(IDS.material, IDS.materialRevision, material.current_revision.content.name);
const stateRef = ref(IDS.state, IDS.stateRevision, materialState.current_revision.content.name);

export function modelingSession(routeId) {
  const fitOrExport = routeId !== "process";
  return {
    version: 4,
    updatedAt: "2026-08-08T00:00:00.000Z",
    materialFamily: "metal",
    objective: "Create a simulation-ready material card",
    contextSelectionRequired: false,
    material: materialRef,
    materialState: stateRef,
    testData: documentRef,
    mappingProfile: mappingRef,
    processingOutput: fitOrExport ? fitRef : processRef,
    ...(fitOrExport ? {
      fitCandidate: ref(IDS.candidate, IDS.fitRevision, "voce"),
      selection: fitRef,
      materialModelIr: ref(IDS.ir, IDS.irRevision, "Issue 189 IR"),
      neutralModel: ref(IDS.neutral, IDS.neutralRevision, "Issue 189 Neutral"),
    } : {}),
    workspace: {
      activeStage: routeId,
      selectedDocumentIds: [IDS.document],
      selectedTestDataRefs: [documentRef],
      visibleTestDataKeys: [`${IDS.document}:${IDS.documentRevision}`],
      selectedStepIndex: fitOrExport ? 5 : 0,
      selectedStageOrdinal: fitOrExport ? 5 : 0,
      plotView: "pipeline",
      settingsOpen: true,
    },
  };
}

export const ROUTES = [
  { id: "process", path: "/modeling?stage=process&family=metal", window: "cold_route_plus_required_action", readinessSelectors: [".processing-workbench-page.stage-process .modeling-workspace-stage-process", "svg.processing-curve[aria-label=\"Mapped and selected processing stage curve overlay\"] polyline.curve-line", "text=Preview ready."], actions: ["auto preview from the pinned Process session"], requiredChunks: ["common-processing-workbench", "modeling-process-panel"] },
  { id: "fit", path: "/modeling?stage=fit&family=metal", window: "cold_route_plus_required_action", readinessSelectors: [".processing-workbench-page.stage-fit .modeling-workspace-stage-fit", ".fit-surface-state-saved-current", "svg.processing-curve polyline.curve-line", "#fit-evidence-dock .fit-evidence-body[aria-label=\"Candidate parameters evidence\"]", ".hardening-candidate-evidence[aria-label=\"Hardening candidate numerical comparison\"]"], actions: ["click button.fit-evidence-trigger once"], requiredChunks: ["common-processing-workbench", "fit-hardening-options", "modeling-fit-decision"] },
  { id: "export", path: "/modeling?stage=export&family=metal", window: "cold_route_plus_required_action", readinessSelectors: [".processing-workbench-page.stage-export", ".modeling-target-preview", "select[aria-label=\"Solver target\"]:enabled", "svg.fit-source-graph[aria-label=\"True plastic strain and true stress response\"]"], actions: ["restore exact saved Fit and inspect the Solver target capability"], requiredChunks: ["common-processing-workbench", "modeling-target-preview"] },
];

function jsonResponse(data) {
  return { status: 200, contentType: "application/json", body: JSON.stringify(data) };
}

export function createModelingFixture() {
  const state = {
    requests: [],
    requestCounts: {},
    pending: 0,
    pendingRequests: 0,
    previewPosts: 0,
    totalPreviewPosts: 0,
    persistentWrites: 0,
    unexpectedRequests: 0,
  };
  const fixtureRoutes = ROUTES.map((route) => ({ id: route.id, requests: [], allowedPreviewPosts: route.id === "process" ? 1 : 0, persistentWrites: 0, unexpectedRequests: 0 }));
  let activeRoute = "process";

  function record(method, path, route = activeRoute) {
    state.requests.push({ method, path });
    const key = `${method} ${path}`;
    state.requestCounts[key] = (state.requestCounts[key] ?? 0) + 1;
    fixtureRoutes.find((item) => item.id === route)?.requests.push({ method, path, count: 1 });
  }
  function fail(route, message = "fixture request rejected") {
    state.unexpectedRequests += 1;
    const item = fixtureRoutes.find((candidate) => candidate.id === route);
    if (item) item.unexpectedRequests += 1;
    return { status: 404, contentType: "application/json", body: JSON.stringify({ detail: message }) };
  }
  function setRoute(routeId) {
    activeRoute = routeId;
    state.previewPosts = 0;
  }
  function routeSummary() {
    const aggregate = (items) => {
      const counts = new Map();
      for (const item of items) {
        const key = `${item.method}\u0000${item.path}`;
        counts.set(key, (counts.get(key) ?? 0) + 1);
      }
      return [...counts.entries()].map(([key, count]) => {
        const [method, path] = key.split("\u0000");
        return { method, path, count };
      }).sort((left, right) => left.method < right.method ? -1 : left.method > right.method ? 1 : left.path < right.path ? -1 : left.path > right.path ? 1 : 0);
    };
    return { fixtureId: FIXTURE_ID, fixtureSha256: null, nonProduction: true, materialFamily: "metal", sessionStorageKey: SESSION_STORAGE_KEY, routes: fixtureRoutes.map((item) => ({ id: item.id, requests: aggregate(item.requests), allowedPreviewPosts: item.allowedPreviewPosts, persistentWrites: item.persistentWrites, unexpectedRequests: item.unexpectedRequests })) };
  }

  async function handle({ method, path, body = null, route = activeRoute }) {
    record(method, path, route);
    const normalized = path.split("?")[0];
    if (method === "GET") {
      if (normalized === "/api/v1/demo-identity/token") return jsonResponse({ access_token: "issue-189-demo-token", token_type: "bearer", expires_in_seconds: 3600, organization_id: "18900000-0000-4000-8000-000000000090", project_id: "18900000-0000-4000-8000-000000000091", user_id: "18900000-0000-0000-0000-000000000099", group: "cmp-demo-material-team" });
      if (normalized === "/api/v1/processing-methods") return jsonResponse({ items: methods });
      if (normalized === "/api/v1/processing-ensemble-methods") return jsonResponse({ items: [] });
      if (normalized === "/api/v1/common-processing-recipes") return jsonResponse({ items: [] });
      if (normalized === "/api/v1/common-processing-batches") return jsonResponse({ items: [] });
      if (normalized === "/api/v1/mapping-profiles") return jsonResponse({ items: [mappingProfile] });
      if (normalized === "/api/v1/processing-outputs") return jsonResponse({ items: [processOutput, fitOutput] });
      if (normalized === "/api/v1/materials" || normalized === "/api/v1/materials/") return jsonResponse({ items: [material], total_count: 1 });
      if (normalized === `/api/v1/materials/${IDS.material}`) return jsonResponse({ material, states: [materialState], property_sets: [] });
      if (normalized === "/api/v1/test-data-documents") return jsonResponse({ items: [testDataDocument] });
      if (normalized === `/api/v1/test-data-documents/${IDS.document}/revisions/${IDS.documentRevision}/content`) return { status: 200, contentType: "application/vnd.cmp.test-data+json", headers: { "content-disposition": 'attachment; filename="issue-189.json"' }, body: JSON.stringify(testDataContent) };
      if (normalized === `/api/v1/material-states/${IDS.state}/datasets`) return jsonResponse({ items: [] });
      if (normalized === `/api/v1/material-states/${IDS.state}/material-models`) return jsonResponse({ items: [] });
      if (normalized === `/api/v1/processing-outputs/${IDS.fitOutput}/content`) return { status: 200, contentType: "application/vnd.cmp.processing-output+json", body: fitDocumentBytes };
      if (normalized === `/api/v1/processing-outputs/${IDS.processOutput}/content`) return { status: 200, contentType: "application/vnd.cmp.processing-output+json", body: Buffer.from(JSON.stringify({ ...testDataContent, document_type: "cmp.processing-output" })) };
      if (normalized === "/api/v1/exporters/reference-elastoplastic/capabilities") return jsonResponse(elastoplasticCapabilities);
      if (normalized === "/api/v1/bulk-export-candidates") return jsonResponse({ items: [] });
      if (normalized === "/api/v1/catalog/domain-bindings:resolve") return jsonResponse({});
      return fail(route, `unknown GET ${path}`);
    }
    if (method === "POST" && normalized === "/api/v1/processing:preview") {
      state.previewPosts += 1;
      state.totalPreviewPosts += 1;
      if (state.previewPosts !== 1 || activeRoute !== "process") return fail(route, "only one Process preview is allowed");
      let parsed;
      try { parsed = typeof body === "string" ? JSON.parse(body) : body; } catch { return fail(route, "invalid preview JSON"); }
      const documentMatches = Boolean(parsed && JSON.stringify(parsed.document) === JSON.stringify(testDataContent));
      const profileMatches = Boolean(parsed && JSON.stringify(parsed.mapping_profile) === JSON.stringify(mappingProfile.content));
      const stepsMatch = Boolean(
        parsed
        && Array.isArray(parsed.steps)
        && parsed.steps.length === processSteps.length
        && parsed.steps.every((step, index) => {
          const expected = processSteps[index];
          return step
            && step.method_id === expected.method_id
            && step.method_version === expected.method_version
            && step.options
            && typeof step.options === "object"
            && !Array.isArray(step.options);
        }),
      );
      if (!parsed || !documentMatches || !profileMatches || !stepsMatch || parsed.steps.some((step) => String(step.method_id).includes("hardening_fit"))) return fail(route, `preview payload is not the pinned process-only fixture (document=${documentMatches},profile=${profileMatches},steps=${stepsMatch},length=${parsed?.steps?.length ?? "none"})`);
      return jsonResponse(processPreview);
    }
    // Every other mutation is intentionally rejected and never counted as a durable write.
    return fail(route, `mutation not allowed: ${method} ${path}`);
  }
  return { state, setRoute, handle, routeSummary, processPreview, processSteps, fitStep, fixtureRoutes };
}

export { IDS, processSteps, fitStep, processPreview, fitDocumentBytes };
