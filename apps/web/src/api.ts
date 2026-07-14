import type {
  ExportTarget,
  CompletedUpload,
  CalibrationDiagnosticPreview,
  CalibrationCandidateSelectionPromotionResponse,
  CalibrationCandidateSelectionResponse,
  CalibrationPlanResponse,
  CalibrationRunResponse,
  CurvePreview,
  DatasetSelectionResponse,
  DatasetResponse,
  DataClassification,
  MaterialCreateInput,
  MaterialDetail,
  MaterialModelList,
  MaterialModelResponse,
  MaterialResponse,
  MaterialRevisionComparison,
  MaterialRevisionList,
  MaterialStateCreateInput,
  MaterialStateResponse,
  MappingReport,
  ImportDetectionReportResponse,
  ImportMappingResponse,
  ImportRunResponse,
  OutlierAssessmentResponse,
  OutlierDetectionPlanResponse,
  OutlierDetectionRunResponse,
  OutlierScopeComparisonResponse,
  PropertySetCreateInput,
  PropertySetResponse,
  ProcessingRecipeResponse,
  ProcessingRunResponse,
  StatisticalCurvePreview,
  StatisticalPlanResponse,
  StatisticalResultResponse,
  StatisticalRunResponse,
  ReferenceModelCreateInput,
  SolverCardCreateInput,
  SolverCardList,
  SolverCardResponse,
  ValidationExecutionMode,
  ReferenceValidationResultResponse,
  ValidationPlanResponse,
  ValidationResultCurveResponse,
  ValidationRunResponse,
  ValidationTemplateResponse,
  ReferenceRunnerOutcome,
  SpecimenResponse,
  TestMethodResponse,
  TestRunResponse,
  ReferenceTensileMapping,
  UploadSession,
} from "./types";

export interface ApiConfig {
  baseUrl: string;
  accessToken: string;
}

export interface ApiResult<T> {
  data: T;
  etag: string | null;
}

export interface LocalDemoAccessToken {
  access_token: string;
  token_type: "Bearer";
  expires_in_seconds: number;
  organization_id: string;
  project_id: string;
  group: string;
}

interface ProblemDocument {
  detail?: string;
  title?: string;
  code?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export const defaultApiConfig: ApiConfig = {
  baseUrl: (import.meta.env.VITE_CMP_API_BASE_URL ?? "/api/v1").replace(/\/$/, ""),
  accessToken: "",
};

const storageKey = "cmp.material-platform.api-config";

export function loadApiConfig(): ApiConfig {
  const raw = window.localStorage.getItem(storageKey);
  if (!raw) {
    return defaultApiConfig;
  }
  try {
    const value: unknown = JSON.parse(raw);
    if (
      typeof value === "object" &&
      value !== null &&
      "baseUrl" in value &&
      "accessToken" in value &&
      typeof value.baseUrl === "string" &&
      typeof value.accessToken === "string"
    ) {
      return {
        baseUrl: value.baseUrl.replace(/\/$/, "") || defaultApiConfig.baseUrl,
        accessToken: value.accessToken,
      };
    }
  } catch {
    // A malformed local preference must not make the catalog inaccessible.
  }
  return defaultApiConfig;
}

export function saveApiConfig(config: ApiConfig): void {
  window.localStorage.setItem(storageKey, JSON.stringify(config));
}

function endpoint(config: ApiConfig, path: string): string {
  return `${config.baseUrl.replace(/\/$/, "")}${path}`;
}

function authenticatedHeaders(config: ApiConfig, init: RequestInit, accept: string): Headers {
  const token = config.accessToken.trim();
  if (!token) {
    throw new ApiError(401, "Add a bearer access token in Connection before using the catalog.");
  }

  const headers = new Headers(init.headers);
  headers.set("Accept", accept);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

async function throwResponseError(response: Response): Promise<never> {
  const isJson = response.headers.get("content-type")?.includes("json");
  let problem: ProblemDocument = {};
  if (isJson) {
    try {
      problem = (await response.json()) as ProblemDocument;
    } catch {
      // Preserve a useful HTTP failure if a proxy sends an invalid problem body.
    }
  }
  throw new ApiError(
    response.status,
    problem.detail ?? problem.title ?? `Catalog request failed (${response.status}).`,
    problem.code,
  );
}

async function request<T>(
  config: ApiConfig,
  path: string,
  init: RequestInit = {},
): Promise<ApiResult<T>> {
  const headers = authenticatedHeaders(config, init, "application/json");
  const response = await fetch(endpoint(config, path), { ...init, headers });
  const isJson = response.headers.get("content-type")?.includes("json");
  const body: unknown = isJson ? await response.json() : undefined;

  if (!response.ok) {
    const problem = (body ?? {}) as ProblemDocument;
    throw new ApiError(response.status, problem.detail ?? problem.title ?? `Catalog request failed (${response.status}).`, problem.code);
  }

  return { data: body as T, etag: response.headers.get("etag") };
}

/**
 * Request the explicitly enabled local-demo token without attaching a bearer
 * credential.  A normal deployment has no such route, so this never becomes
 * an authentication fallback for the workbench.
 */
export async function requestLocalDemoAccessToken(
  config: Pick<ApiConfig, "baseUrl">,
): Promise<ApiResult<LocalDemoAccessToken>> {
  const baseUrl = config.baseUrl.trim().replace(/\/$/, "") || "/api/v1";
  const response = await fetch(`${baseUrl}/demo-identity/token`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    return throwResponseError(response);
  }
  return {
    data: (await response.json()) as LocalDemoAccessToken,
    etag: response.headers.get("etag"),
  };
}

export function listMaterials(
  config: ApiConfig,
  query: string,
): Promise<ApiResult<{ items: MaterialResponse[] }>> {
  const search = new URLSearchParams({ limit: "50" });
  if (query.trim()) {
    search.set("q", query.trim());
  }
  return request(config, `/materials?${search.toString()}`);
}

export function getMaterialDetail(
  config: ApiConfig,
  materialId: string,
): Promise<ApiResult<MaterialDetail>> {
  return request(config, `/materials/${encodeURIComponent(materialId)}`);
}

export function getMaterialRevisions(
  config: ApiConfig,
  materialId: string,
): Promise<ApiResult<MaterialRevisionList>> {
  return request(config, `/materials/${encodeURIComponent(materialId)}/revisions`);
}

export function compareMaterialRevisions(
  config: ApiConfig,
  materialId: string,
  leftRevisionId: string,
  rightRevisionId: string,
): Promise<ApiResult<MaterialRevisionComparison>> {
  const search = new URLSearchParams({
    left_revision_id: leftRevisionId,
    right_revision_id: rightRevisionId,
  });
  return request(
    config,
    `/materials/${encodeURIComponent(materialId)}/revisions:compare?${search.toString()}`,
  );
}

export function createMaterial(
  config: ApiConfig,
  input: MaterialCreateInput,
): Promise<ApiResult<MaterialResponse>> {
  return request(config, "/materials", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createMaterialState(
  config: ApiConfig,
  materialId: string,
  input: MaterialStateCreateInput,
): Promise<ApiResult<MaterialStateResponse>> {
  return request(config, `/materials/${encodeURIComponent(materialId)}/states`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getPropertySet(
  config: ApiConfig,
  propertySetId: string,
): Promise<ApiResult<PropertySetResponse>> {
  return request(config, `/property-sets/${encodeURIComponent(propertySetId)}`);
}

export function createPropertySet(
  config: ApiConfig,
  materialStateId: string,
  input: PropertySetCreateInput,
): Promise<ApiResult<PropertySetResponse>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/property-sets`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function revisePropertySet(
  config: ApiConfig,
  propertySetId: string,
  etag: string,
  input: PropertySetCreateInput,
): Promise<ApiResult<PropertySetResponse>> {
  return request(config, `/property-sets/${encodeURIComponent(propertySetId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}

export function listMaterialModels(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<MaterialModelList>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/material-models`);
}

export function createReferenceMaterialModel(
  config: ApiConfig,
  materialStateId: string,
  input: ReferenceModelCreateInput,
): Promise<ApiResult<MaterialModelResponse>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/material-models`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferenceLinearElasticCalibrationPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    plan_label: string;
    selection_id: string;
    selection_revision_id: string;
    material_model_id: string;
    material_model_revision_id: string;
    youngs_modulus_lower_bound_pa: number;
    youngs_modulus_initial_value_pa: number;
    youngs_modulus_upper_bound_pa: number;
    normalization_stress_scale_pa: number;
    multistart_count: number;
    random_seed: number;
    change_reason: string;
  },
): Promise<ApiResult<CalibrationPlanResponse>> {
  return request(config, "/calibration-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceLinearElasticCalibration(
  config: ApiConfig,
  input: {
    plan_id: string;
    plan_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<CalibrationRunResponse>> {
  return request(config, "/calibration-runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function previewCalibrationCandidateDiagnostics(
  config: ApiConfig,
  candidateId: string,
  maximumPoints = 500,
): Promise<ApiResult<CalibrationDiagnosticPreview>> {
  return request(
    config,
    `/calibration-candidates/${encodeURIComponent(candidateId)}/diagnostics-preview?maximum_points=${maximumPoints}`,
  );
}

export function createReferenceCalibrationCandidateSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    calibration_run_id: string;
    calibration_candidate_id: string;
    selection_reason: string;
  },
): Promise<ApiResult<CalibrationCandidateSelectionResponse>> {
  return request(config, "/calibration-candidate-selections", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function promoteSelectedReferenceCalibrationCandidate(
  config: ApiConfig,
  selectionId: string,
  input: {
    selection_revision_id: string;
    expected_material_model_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<CalibrationCandidateSelectionPromotionResponse>> {
  return request(
    config,
    `/calibration-candidate-selections/${encodeURIComponent(selectionId)}/promote-material-model`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function listValidationTemplates(
  config: ApiConfig,
): Promise<ApiResult<{ items: ValidationTemplateResponse[] }>> {
  return request(config, "/validation-templates?limit=100");
}

export function createReferenceValidationTemplate(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      template_label: string;
      gauge_length_m: number;
      cross_section_area_m2: number;
      axial_element_count: number;
      axial_displacement_end_m: number;
      output_sample_count: number;
    };
    change_reason: string;
  },
): Promise<ApiResult<ValidationTemplateResponse>> {
  return request(config, "/validation-templates", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listValidationPlans(
  config: ApiConfig,
): Promise<ApiResult<{ items: ValidationPlanResponse[] }>> {
  return request(config, "/validation-plans?limit=100");
}

export function createReferenceValidationPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      plan_label: string;
      validation_template_id: string;
      validation_template_revision_id: string;
      material_model_id: string;
      material_model_revision_id: string;
      solver_card_id: string;
      solver_card_revision_id: string;
      experimental_selection_id: string;
      experimental_selection_revision_id: string;
    };
    change_reason: string;
  },
): Promise<ApiResult<ValidationPlanResponse>> {
  return request(config, "/validation-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function submitReferenceValidationRun(
  config: ApiConfig,
  input: {
    validation_plan_id: string;
    validation_plan_revision_id: string;
    execution_mode: ValidationExecutionMode;
    external_job_reference?: string;
    change_reason: string;
  },
): Promise<ApiResult<ValidationRunResponse>> {
  return request(config, "/validation-runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function pollReferenceValidationRun(
  config: ApiConfig,
  runId: string,
  input: { change_reason: string; outcome: ReferenceRunnerOutcome },
): Promise<ApiResult<ValidationRunResponse>> {
  return request(config, `/validation-runs/${encodeURIComponent(runId)}:poll`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function cancelValidationRun(
  config: ApiConfig,
  runId: string,
  input: { change_reason: string },
): Promise<ApiResult<ValidationRunResponse>> {
  return request(config, `/validation-runs/${encodeURIComponent(runId)}:cancel`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function attachManualValidationResult(
  config: ApiConfig,
  runId: string,
  input: {
    stdout_text: string;
    stderr_text: string;
    native_result_text: string;
    change_reason: string;
  },
): Promise<ApiResult<ValidationRunResponse>> {
  return request(config, `/validation-runs/${encodeURIComponent(runId)}:attach-result`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function evaluateReferenceValidationRun(
  config: ApiConfig,
  runId: string,
  input: { change_reason: string },
): Promise<ApiResult<ValidationRunResponse>> {
  return request(config, `/validation-runs/${encodeURIComponent(runId)}:evaluate`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getReferenceValidationResult(
  config: ApiConfig,
  validationResultId: string,
): Promise<ApiResult<ReferenceValidationResultResponse>> {
  return request(config, `/validation-results/${encodeURIComponent(validationResultId)}`);
}

export function previewReferenceValidationResultCurve(
  config: ApiConfig,
  validationResultId: string,
  maximumPoints = 1_000,
): Promise<ApiResult<ValidationResultCurveResponse>> {
  const query = new URLSearchParams({ maximum_points: String(maximumPoints) });
  return request(
    config,
    `/validation-results/${encodeURIComponent(validationResultId)}/curve?${query.toString()}`,
  );
}

export function preflightSolverCardMapping(
  config: ApiConfig,
  materialModelId: string,
  target: ExportTarget,
): Promise<ApiResult<MappingReport>> {
  return request(config, `/material-models/${encodeURIComponent(materialModelId)}/mapping-preflight`, {
    method: "POST",
    body: JSON.stringify({ target }),
  });
}

export function listSolverCards(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<SolverCardList>> {
  return request(config, `/material-models/${encodeURIComponent(materialModelId)}/solver-cards`);
}

export function createSolverCard(
  config: ApiConfig,
  materialModelId: string,
  input: SolverCardCreateInput,
): Promise<ApiResult<SolverCardResponse>> {
  return request(config, `/material-models/${encodeURIComponent(materialModelId)}/solver-cards`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function previewSolverCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<string>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/solver-cards/${encodeURIComponent(solverCardId)}/preview`),
    { ...init, headers },
  );
  if (!response.ok) {
    return throwResponseError(response);
  }
  return { data: await response.text(), etag: response.headers.get("etag") };
}

export interface SolverCardDownload {
  blob: Blob;
  filename: string;
}

export async function downloadSolverCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<SolverCardDownload>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/solver-cards/${encodeURIComponent(solverCardId)}/download`),
    { ...init, headers },
  );
  if (!response.ok) {
    return throwResponseError(response);
  }
  const header = response.headers.get("content-disposition") ?? "";
  const match = header.match(/filename="?([^";]+)"?/i);
  return {
    data: {
      blob: await response.blob(),
      filename: match?.[1] ?? `solver-card-${solverCardId}.rad`,
    },
    etag: response.headers.get("etag"),
  };
}

export function listSpecimensForMaterialState(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: SpecimenResponse[] }>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/specimens`);
}

export function createSpecimen(
  config: ApiConfig,
  materialStateId: string,
  input: {
    material_state_revision_id: string;
    specimen_code: string;
    orientation: string | null;
    preparation_note: string | null;
    change_reason: string;
  },
): Promise<ApiResult<SpecimenResponse>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/specimens`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listTestMethods(
  config: ApiConfig,
): Promise<ApiResult<{ items: TestMethodResponse[] }>> {
  return request(config, "/test-methods");
}

export function createReferenceTensileTestMethod(
  config: ApiConfig,
  input: { classification: DataClassification; change_reason: string },
): Promise<ApiResult<TestMethodResponse>> {
  return request(config, "/test-methods/reference-uniaxial-tensile", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferenceTensileTestRun(
  config: ApiConfig,
  input: {
    specimen_id: string;
    specimen_revision_id: string;
    test_method_id: string;
    test_method_revision_id: string;
    run_label: string;
    performed_at: string;
    test_temperature_k: number | null;
    crosshead_speed_mm_per_min: number | null;
    change_reason: string;
  },
): Promise<ApiResult<TestRunResponse>> {
  return request(config, "/test-runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listTestRunsForMaterialState(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: TestRunResponse[] }>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/test-runs`);
}

export function listDatasetsForMaterialState(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: DatasetResponse[] }>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/datasets`);
}

export function listDatasetRevisions(
  config: ApiConfig,
  datasetId: string,
): Promise<ApiResult<{ dataset_id: string; revisions: DatasetResponse["current_revision"][] }>> {
  return request(config, `/datasets/${encodeURIComponent(datasetId)}/revisions`);
}

export function createReferenceDatasetSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    dataset_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<DatasetSelectionResponse>> {
  return request(config, "/dataset-selections", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listDatasetRevisionSelections(
  config: ApiConfig,
  datasetRevisionId: string,
): Promise<ApiResult<{ items: DatasetSelectionResponse[] }>> {
  return request(
    config,
    `/dataset-revisions/${encodeURIComponent(datasetRevisionId)}/selections`,
  );
}

export function listProcessingRecipes(
  config: ApiConfig,
): Promise<ApiResult<{ items: ProcessingRecipeResponse[] }>> {
  return request(config, "/processing-recipes");
}

export function createReferenceTensileCropRecipe(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      recipe_label: string;
      minimum_engineering_strain: number;
      maximum_engineering_strain: number;
    };
    change_reason: string;
  },
): Promise<ApiResult<ProcessingRecipeResponse>> {
  return request(config, "/processing-recipes/reference-tensile-crop", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceTensileCrop(
  config: ApiConfig,
  input: {
    selection_id: string;
    selection_revision_id: string;
    recipe_id: string;
    recipe_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<ProcessingRunResponse>> {
  return request(config, "/processing-runs/reference-tensile-crop", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listStatisticalPlans(
  config: ApiConfig,
): Promise<ApiResult<{ items: StatisticalPlanResponse[] }>> {
  return request(config, "/statistical-plans?limit=100");
}

export function createReferenceTensilePairStatisticalPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      plan_label: string;
      first_selection_id: string;
      first_selection_revision_id: string;
      second_selection_id: string;
      second_selection_revision_id: string;
    };
    change_reason: string;
  },
): Promise<ApiResult<StatisticalPlanResponse>> {
  return request(config, "/statistical-plans/reference-tensile-pair", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceTensilePairStatistics(
  config: ApiConfig,
  input: {
    plan_id: string;
    plan_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<StatisticalRunResponse>> {
  return request(config, "/statistical-runs/reference-tensile-pair", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getStatisticalResult(
  config: ApiConfig,
  resultId: string,
): Promise<ApiResult<StatisticalResultResponse>> {
  return request(config, `/statistical-results/${encodeURIComponent(resultId)}`);
}

export function previewStatisticalResultCurve(
  config: ApiConfig,
  resultId: string,
  maximumPoints = 1_000,
): Promise<ApiResult<StatisticalCurvePreview>> {
  const query = new URLSearchParams({ maximum_points: String(maximumPoints) });
  return request(
    config,
    `/statistical-results/${encodeURIComponent(resultId)}/curve?${query.toString()}`,
  );
}

export function listOutlierDetectionPlans(
  config: ApiConfig,
): Promise<ApiResult<{ items: OutlierDetectionPlanResponse[] }>> {
  return request(config, "/outlier-detection-plans?limit=100");
}

export function createReferenceTensilePairOutlierDetectionPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      plan_label: string;
      statistical_result_id: string;
      statistical_result_revision_id: string;
      relative_peak_difference_threshold: number;
    };
    change_reason: string;
  },
): Promise<ApiResult<OutlierDetectionPlanResponse>> {
  return request(config, "/outlier-detection-plans/reference-tensile-pair", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceTensilePairOutlierDetection(
  config: ApiConfig,
  input: {
    detection_plan_id: string;
    detection_plan_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<OutlierDetectionRunResponse>> {
  return request(config, "/outlier-detection-runs/reference-tensile-pair", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferenceTensilePairOutlierAssessment(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      candidate_id: string;
      statistical_plan_id: string;
      statistical_plan_revision_id: string;
      decision: "retained" | "excluded_from_reference_analysis";
      assessment_reason: string;
    };
    change_reason: string;
  },
): Promise<ApiResult<OutlierAssessmentResponse>> {
  return request(config, "/outlier-assessments/reference-tensile-pair", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getReferenceTensilePairOutlierScopeComparison(
  config: ApiConfig,
  input: {
    detection_plan_id: string;
    detection_plan_revision_id: string;
  },
): Promise<ApiResult<OutlierScopeComparisonResponse>> {
  const query = new URLSearchParams({
    detection_plan_id: input.detection_plan_id,
    detection_plan_revision_id: input.detection_plan_revision_id,
  });
  return request(
    config,
    `/outlier-scope-comparisons/reference-tensile-pair?${query.toString()}`,
  );
}

export function importReferenceTensileDataset(
  config: ApiConfig,
  input: {
    test_run_id: string;
    test_run_revision_id: string;
    raw_asset_id: string;
    raw_artifact_id: string;
    mapping: ReferenceTensileMapping;
    change_reason: string;
  },
): Promise<ApiResult<DatasetResponse>> {
  return request(config, "/datasets/reference-uniaxial-tensile:import", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function detectReferenceImport(
  config: ApiConfig,
  input: { raw_asset_id: string; raw_artifact_id: string },
): Promise<ApiResult<ImportDetectionReportResponse>> {
  return request(config, "/imports:detect", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferenceImportMapping(
  config: ApiConfig,
  input: {
    detection_report_id: string;
    mapping_label: string;
    strain_column: string;
    stress_column: string;
    strain_unit: ReferenceTensileMapping["strain_unit"];
    stress_unit: ReferenceTensileMapping["stress_unit"];
    change_reason: string;
  },
): Promise<ApiResult<ImportMappingResponse>> {
  return request(config, "/import-mappings", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceImport(
  config: ApiConfig,
  input: {
    test_run_id: string;
    test_run_revision_id: string;
    raw_asset_id: string;
    raw_artifact_id: string;
    import_mapping_id: string;
    import_mapping_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<ImportRunResponse>> {
  return request(config, "/imports", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function previewDatasetCurve(
  config: ApiConfig,
  datasetRevisionId: string,
  maximumPoints = 1_000,
): Promise<ApiResult<CurvePreview>> {
  const query = new URLSearchParams({ maximum_points: String(maximumPoints) });
  return request(
    config,
    `/dataset-revisions/${encodeURIComponent(datasetRevisionId)}/curve?${query.toString()}`,
  );
}

function browserIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `browser-upload-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

async function sha256Hex(file: File): Promise<string> {
  if (typeof crypto === "undefined" || !crypto.subtle) {
    throw new ApiError(503, "This browser cannot calculate the required SHA-256 upload digest.");
  }
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function uploadReferenceTensileCsv(
  config: ApiConfig,
  input: {
    file: File;
    classification: DataClassification;
    test_run_revision_id: string;
  },
): Promise<ApiResult<CompletedUpload>> {
  const filename = input.file.name.trim();
  if (!filename || filename.includes("/") || filename.includes("\\")) {
    throw new ApiError(422, "Choose a CSV file with a safe, non-empty filename.");
  }
  if (input.file.size < 1 || input.file.size > 16 * 1024 * 1024) {
    throw new ApiError(422, "The reference CSV must be between 1 byte and 16 MiB.");
  }
  const digest = await sha256Hex(input.file);
  const created = await request<{ upload: UploadSession; upload_capability: string }>(config, "/uploads", {
    method: "POST",
    headers: { "Idempotency-Key": browserIdempotencyKey() },
    body: JSON.stringify({
      classification: input.classification,
      original_filename: filename,
      media_type: "text/csv",
      expected_size_bytes: input.file.size,
      expected_sha256: digest,
      test_run_revision_id: input.test_run_revision_id,
    }),
  });
  const { upload, upload_capability: capability } = created.data;
  for (let partNumber = 1; partNumber <= upload.expected_part_count; partNumber += 1) {
    const start = (partNumber - 1) * upload.part_size_bytes;
    const part = input.file.slice(start, Math.min(input.file.size, start + upload.part_size_bytes));
    await request<UploadSession>(
      config,
      `/uploads/${encodeURIComponent(upload.upload_id)}/parts/${partNumber}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "text/csv",
          "Upload-Capability": capability,
        },
        body: part,
      },
    );
  }
  return request<CompletedUpload>(
    config,
    `/uploads/${encodeURIComponent(upload.upload_id)}:complete`,
    {
      method: "POST",
      headers: { "Upload-Capability": capability },
    },
  );
}
