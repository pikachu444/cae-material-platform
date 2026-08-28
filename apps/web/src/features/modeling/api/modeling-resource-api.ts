import type {
  CalibrationCandidateSelectionPromotionResponse,
  CalibrationCandidateSelectionResponse,
  CalibrationDiagnosticPreview,
  CalibrationPlanResponse,
  CalibrationRunResponse,
  DataClassification,
  ElastoplasticCardCreatedResponse,
  ElastoplasticCardResponse,
  ExportTarget,
  HardeningCurveResponse,
  HyperelasticDiagnosticsResponse,
  LinearViscoelasticCardResponse,
  LinearViscoelasticMappingReport,
  LinearViscoelasticModelResponse,
  LinearViscoelasticResponse,
  MappingReport,
  MaterialModelList,
  MaterialModelResponse,
  NeutralHyperelasticMappingReport,
  NeutralHyperelasticSolverCardResponse,
  NeutralMaterialResponse,
  OgdenCalibrationPlanResponse,
  OgdenCalibrationRole,
  OgdenCalibrationRunResponse,
  OgdenCandidateSelectionResponse,
  OgdenDiagnosticsResponse,
  OgdenPronyCardResponse,
  OgdenPronyMappingResponse,
  OgdenPronyModelResponse,
  OgdenPronyRevisionListResponse,
  OgdenTestMode,
  ReferenceModelCreateInput,
  ReferenceRunnerOutcome,
  ReferenceValidationResultResponse,
  ScientificProfileResponse,
  SolverCardCreateInput,
  SolverCardList,
  SolverCardResponse,
  TabulatedPlasticityModelResponse,
  ValidationExecutionMode,
  ValidationPlanResponse,
  ValidationResultCurveResponse,
  ValidationRunResponse,
  ValidationTemplateResponse,
  ViscoelasticMasterPlanResponse,
  ViscoelasticMasterPreviewResponse,
  ViscoelasticMasterRunResponse,
  ViscoelasticSelectionResponse,
  ViscoelasticShiftMethod,
  VoceCalibrationDiagnosticPreview,
  VoceCalibrationPlanResponse,
  VoceCalibrationRunResponse,
  VoceCandidateSelectionResponse,
  VoceHoldoutPlanResponse,
  VoceHoldoutResultResponse,
} from "../../../types";

import {
  authenticatedHeaders,
  endpoint,
  request,
  throwResponseError,
} from "../../../shared/api/http";

import type { ApiConfig, ApiResult } from "../../../shared/api/http";

function revisionPath(path: string, revisionId?: string): string {
  if (!revisionId) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}revision_id=${encodeURIComponent(revisionId)}`;
}

export function listMaterialModels(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<MaterialModelList>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/material-models`);
}

export function getMaterialModel(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<MaterialModelResponse>> {
  return request(config, `/material-models/${encodeURIComponent(materialModelId)}`);
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

export interface VoceParameterInput {
  lower: number;
  initial: number;
  upper: number;
  scale: number;
}

export function createReferenceVoceCalibrationPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    plan_label: string;
    calibration_input_scope_id: string;
    calibration_input_scope_revision_id: string;
    material_state_id: string;
    material_state_revision_id: string;
    property_set_id: string;
    property_set_revision_id: string;
    youngs_modulus_pa: number;
    sigma_0_pa: VoceParameterInput;
    q_pa: VoceParameterInput;
    b: VoceParameterInput;
    normalization_stress_scale_pa: number;
    multistart_count: number;
    random_seed: number;
    maximum_function_evaluations: number;
    ftol: number;
    xtol: number;
    gtol: number;
    change_reason: string;
  },
): Promise<ApiResult<VoceCalibrationPlanResponse>> {
  return request(config, "/voce-calibration-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceVoceCalibration(
  config: ApiConfig,
  planId: string,
  input: { plan_revision_id: string; change_reason: string },
): Promise<ApiResult<VoceCalibrationRunResponse>> {
  return request(
    config,
    `/voce-calibration-plans/${encodeURIComponent(planId)}/runs`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function previewReferenceVoceCalibrationDiagnostics(
  config: ApiConfig,
  candidateId: string,
  maximumPoints = 1000,
): Promise<ApiResult<VoceCalibrationDiagnosticPreview>> {
  return request(
    config,
    `/voce-calibration-candidates/${encodeURIComponent(candidateId)}/diagnostics-preview?maximum_points=${maximumPoints}`,
  );
}

export function createReferenceVoceCandidateSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    voce_calibration_run_id: string;
    voce_calibration_candidate_id: string;
    selection_reason: string;
  },
): Promise<ApiResult<VoceCandidateSelectionResponse>> {
  return request(config, "/voce-candidate-selections", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function projectSelectedReferenceVoceCandidate(
  config: ApiConfig,
  selectionId: string,
  input: {
    selection_revision_id: string;
    sampling_point_count: number;
    extension_max_true_plastic_strain: number;
    acknowledge_constant_extension: boolean;
    change_reason: string;
  },
): Promise<ApiResult<TabulatedPlasticityModelResponse>> {
  return request(
    config,
    `/voce-candidate-selections/${encodeURIComponent(selectionId)}/tabulated-plasticity-models`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function createReferenceVoceHoldoutPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      plan_label: string;
      material_model_id: string;
      material_model_revision_id: string;
      holdout_dataset_id: string;
      holdout_dataset_revision_id: string;
    };
    change_reason: string;
  },
): Promise<ApiResult<VoceHoldoutPlanResponse>> {
  return request(config, "/voce-holdout-validation-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceVoceHoldout(
  config: ApiConfig,
  planId: string,
  input: { plan_revision_id: string; change_reason: string },
): Promise<ApiResult<VoceHoldoutResultResponse>> {
  return request(
    config,
    `/voce-holdout-validation-plans/${encodeURIComponent(planId)}/runs`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function listReferenceVoceHoldoutResults(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<{ items: VoceHoldoutResultResponse[] }>> {
  return request(
    config,
    `/tabulated-plasticity-models/${encodeURIComponent(materialModelId)}/voce-holdout-results`,
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

export function getSolverCard(
  config: ApiConfig,
  solverCardId: string,
  revisionId?: string,
): Promise<ApiResult<SolverCardResponse>> {
  return request(
    config,
    revisionPath(`/solver-cards/${encodeURIComponent(solverCardId)}`, revisionId),
  );
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
  revisionId?: string,
): Promise<ApiResult<string>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(
      config,
      revisionPath(`/solver-cards/${encodeURIComponent(solverCardId)}/preview`, revisionId),
    ),
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
  revisionId?: string,
): Promise<ApiResult<SolverCardDownload>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(
      config,
      revisionPath(`/solver-cards/${encodeURIComponent(solverCardId)}/download`, revisionId),
    ),
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

export function listTabulatedPlasticityModels(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: TabulatedPlasticityModelResponse[] }>> {
  return request(
    config,
    `/material-states/${encodeURIComponent(materialStateId)}/tabulated-plasticity-models`,
  );
}

export function listLinearViscoelasticModels(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: LinearViscoelasticModelResponse[] }>> {
  return request(
    config,
    `/material-states/${encodeURIComponent(materialStateId)}/linear-viscoelastic-models`,
  );
}

export function createLinearViscoelasticModel(
  config: ApiConfig,
  materialStateId: string,
  input: {
    property_set_revision_id: string;
    bulk_relaxation_status: "characterized" | "not_characterized";
    terms: Array<{ g_ratio: number; k_ratio: number; relaxation_time_s: number }>;
    change_reason: string;
  },
): Promise<ApiResult<LinearViscoelasticModelResponse>> {
  return request(
    config,
    `/material-states/${encodeURIComponent(materialStateId)}/linear-viscoelastic-models`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function promotePronyProcessingOutput(
  config: ApiConfig,
  processingOutputId: string,
  input: {
    material_state_id: string;
    property_set_revision_id: string;
    processing_output_revision_id: string;
    acknowledged_maximum_relative_mismatch: number;
    review_acknowledged: boolean;
    change_reason: string;
  },
): Promise<ApiResult<LinearViscoelasticModelResponse>> {
  return request(
    config,
    `/processing-outputs/${encodeURIComponent(processingOutputId)}/linear-viscoelastic-models`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function previewLinearViscoelasticResponse(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<LinearViscoelasticResponse>> {
  return request(
    config,
    `/linear-viscoelastic-models/${encodeURIComponent(materialModelId)}/response`,
  );
}

export function preflightLinearViscoelasticMapping(
  config: ApiConfig,
  materialModelId: string,
  materialModelRevisionId: string,
): Promise<ApiResult<LinearViscoelasticMappingReport>> {
  return request(
    config,
    `/linear-viscoelastic-models/${encodeURIComponent(materialModelId)}/mapping-preflight`,
    {
      method: "POST",
      body: JSON.stringify({
        material_model_revision_id: materialModelRevisionId,
        target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s" },
      }),
    },
  );
}

export function listLinearViscoelasticSolverCards(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<{ items: LinearViscoelasticCardResponse[] }>> {
  return request(
    config,
    `/linear-viscoelastic-models/${encodeURIComponent(materialModelId)}/solver-cards`,
  );
}

export function createLinearViscoelasticSolverCard(
  config: ApiConfig,
  materialModelId: string,
  input: {
    material_model_revision_id: string;
    expected_mapping_report_sha256: string;
    solver_material_id: number;
    material_name: string;
    change_reason: string;
  },
): Promise<ApiResult<{ card: LinearViscoelasticCardResponse; mapping_report: LinearViscoelasticMappingReport }>> {
  return request(
    config,
    `/linear-viscoelastic-models/${encodeURIComponent(materialModelId)}/solver-cards`,
    {
      method: "POST",
      body: JSON.stringify({
        ...input,
        target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s" },
      }),
    },
  );
}

export async function previewLinearViscoelasticSolverCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<string>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/linear-viscoelastic-solver-cards/${encodeURIComponent(solverCardId)}/preview`),
    { ...init, headers },
  );
  if (!response.ok) return throwResponseError(response);
  return { data: await response.text(), etag: response.headers.get("etag") };
}

export async function downloadLinearViscoelasticSolverCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<{ blob: Blob; filename: string }>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/linear-viscoelastic-solver-cards/${encodeURIComponent(solverCardId)}/download`),
    { ...init, headers },
  );
  if (!response.ok) return throwResponseError(response);
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "material.inp";
  return { data: { blob: await response.blob(), filename }, etag: response.headers.get("etag") };
}

export function listOgdenPronyModels(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: OgdenPronyModelResponse[] }>> {
  return request(
    config,
    `/material-states/${encodeURIComponent(materialStateId)}/ogden-prony-models`,
  );
}

export function createOgdenPronyModel(
  config: ApiConfig,
  materialStateId: string,
  input: {
    property_set_revision_id: string;
    ogden_mu_pa: number;
    ogden_alpha: number;
    prony_terms: Array<{ g_ratio: number; relaxation_time_s: number }>;
    change_reason: string;
  },
): Promise<ApiResult<OgdenPronyModelResponse>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/ogden-prony-models`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function listScientificProfiles(
  config: ApiConfig,
  family: "steel_voce" | "polymer_linear_prony" | "elastomer_ogden_prony",
): Promise<ApiResult<ScientificProfileResponse[]>> {
  const result = await request<{ items: ScientificProfileResponse[] }>(
    config,
    `/scientific-profiles?family=${encodeURIComponent(family)}`,
  );
  return { data: result.data.items, etag: result.etag };
}

export function createOgdenScientificProfile(
  config: ApiConfig,
): Promise<ApiResult<ScientificProfileResponse>> {
  return request(config, "/scientific-profiles", {
    method: "POST",
    body: JSON.stringify({
      classification: "internal",
      content: {
        profile_label: "Reference elastomer multi-test Ogden",
        family: "elastomer_ogden_prony",
        approval_status: "reference_unapproved",
        multistart_count: 8,
        seed: 20260716,
        status_note: "Synthetic/public reference bounds; domain sign-off is not recorded.",
        ogden: {
          mu_initial_pa: 1200000,
          mu_lower_pa: 1000,
          mu_upper_pa: 100000000,
          mu_scale_pa: 1000000,
          alpha_initial: 2.4,
          alpha_lower: 0.1,
          alpha_upper: 20,
          alpha_scale: 2,
          uniaxial_weight: 1,
          planar_weight: 1,
          biaxial_weight: 1,
        },
      },
      change_reason: "Create explicit reference Ogden scientific profile",
    }),
  });
}

export function createReferenceOgdenCalibrationPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    plan_label: string;
    scientific_profile_id: string;
    scientific_profile_revision_id: string;
    material_state_id: string;
    material_state_revision_id: string;
    baseline_model_id: string;
    baseline_model_revision_id: string;
    members: Array<{
      role: OgdenCalibrationRole;
      test_mode: OgdenTestMode;
      dataset_id: string;
      dataset_revision_id: string;
      weight: number;
    }>;
    change_reason: string;
  },
): Promise<ApiResult<OgdenCalibrationPlanResponse>> {
  return request(config, "/ogden-calibration-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listReferenceOgdenCalibrationPlans(
  config: ApiConfig,
  limit = 100,
): Promise<ApiResult<{ items: OgdenCalibrationPlanResponse[] }>> {
  return request(config, `/ogden-calibration-plans?limit=${encodeURIComponent(String(limit))}`);
}

export function getReferenceOgdenCalibrationPlan(
  config: ApiConfig,
  planId: string,
): Promise<ApiResult<OgdenCalibrationPlanResponse>> {
  return request(config, `/ogden-calibration-plans/${encodeURIComponent(planId)}`);
}

export function reviseReferenceOgdenCalibrationPlan(
  config: ApiConfig,
  planId: string,
  input: {
    expected_current_revision_id: string;
    plan_label: string;
    scientific_profile_id: string;
    scientific_profile_revision_id: string;
    material_state_id: string;
    material_state_revision_id: string;
    baseline_model_id: string;
    baseline_model_revision_id: string;
    members: Array<{
      role: OgdenCalibrationRole;
      test_mode: OgdenTestMode;
      dataset_id: string;
      dataset_revision_id: string;
      weight: number;
    }>;
    change_reason: string;
  },
): Promise<ApiResult<OgdenCalibrationPlanResponse>> {
  return request(
    config,
    `/ogden-calibration-plans/${encodeURIComponent(planId)}/revisions`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function executeReferenceOgdenCalibration(
  config: ApiConfig,
  planId: string,
  input: { plan_revision_id: string; change_reason: string },
): Promise<ApiResult<OgdenCalibrationRunResponse>> {
  return request(config, `/ogden-calibration-plans/${encodeURIComponent(planId)}/runs`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getReferenceOgdenCandidateDiagnostics(
  config: ApiConfig,
  candidateId: string,
): Promise<ApiResult<OgdenDiagnosticsResponse>> {
  return request(
    config,
    `/ogden-calibration-candidates/${encodeURIComponent(candidateId)}/diagnostics`,
  );
}

export function getReferenceOgdenCalibrationRun(
  config: ApiConfig,
  runId: string,
): Promise<ApiResult<OgdenCalibrationRunResponse>> {
  return request(config, `/ogden-calibration-runs/${encodeURIComponent(runId)}`);
}

export function getHyperelasticFamilyCandidateDiagnostics(
  config: ApiConfig,
  candidateId: string,
): Promise<ApiResult<HyperelasticDiagnosticsResponse>> {
  return request(
    config,
    `/hyperelastic-family-candidates/${encodeURIComponent(candidateId)}/diagnostics`,
  );
}

export function promoteHyperelasticCandidateToNeutralMaterial(
  config: ApiConfig,
  input: {
    candidate_id: string;
    selection_reason: string;
    change_reason: string;
  },
): Promise<ApiResult<NeutralMaterialResponse>> {
  return request(config, "/neutral-materials:promote", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function promoteModelToNeutralMaterial(
  config: ApiConfig,
  family: "metal" | "linear-viscoelastic",
  input: {
    material_model_id: string;
    material_model_revision_id: string;
    selection_reason: string;
    change_reason: string;
  },
): Promise<ApiResult<NeutralMaterialResponse>> {
  return request(config, `/neutral-materials:promote-${family}`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getNeutralMaterial(
  config: ApiConfig,
  neutralMaterialId: string,
): Promise<ApiResult<NeutralMaterialResponse>> {
  return request(
    config,
    `/neutral-materials/${encodeURIComponent(neutralMaterialId)}`,
  );
}

export function importNeutralMaterial(
  config: ApiConfig,
  input: { document: Record<string, unknown>; change_reason: string },
): Promise<ApiResult<NeutralMaterialResponse>> {
  return request(config, "/neutral-materials:import", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function downloadNeutralMaterial(
  config: ApiConfig,
  neutralMaterialId: string,
): Promise<ApiResult<{ blob: Blob; filename: string }>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "application/json");
  const response = await fetch(
    endpoint(
      config,
      `/neutral-materials/${encodeURIComponent(neutralMaterialId)}/download`,
    ),
    { ...init, headers },
  );
  if (!response.ok) {
    return throwResponseError(response);
  }
  return {
    data: {
      blob: await response.blob(),
      filename: `neutral-material-${neutralMaterialId}.json`,
    },
    etag: response.headers.get("etag"),
  };
}

export function preflightNeutralHyperelasticSolverCard(
  config: ApiConfig,
  neutralMaterialId: string,
  input: { neutral_material_revision_id: string; target: ExportTarget },
): Promise<ApiResult<NeutralHyperelasticMappingReport>> {
  return request(
    config,
    `/neutral-materials/${encodeURIComponent(neutralMaterialId)}/solver-card-preflight`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function createNeutralHyperelasticSolverCard(
  config: ApiConfig,
  neutralMaterialId: string,
  input: {
    neutral_material_revision_id: string;
    target: ExportTarget;
    expected_mapping_report_sha256: string;
    solver_material_id: number;
    material_name: string;
    change_reason: string;
  },
): Promise<ApiResult<NeutralHyperelasticSolverCardResponse>> {
  return request(
    config,
    `/neutral-materials/${encodeURIComponent(neutralMaterialId)}/solver-cards`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function getNeutralSolverCard(
  config: ApiConfig,
  solverCardId: string,
  revisionId?: string,
): Promise<ApiResult<NeutralHyperelasticSolverCardResponse>> {
  return request(
    config,
    revisionPath(`/neutral-solver-cards/${encodeURIComponent(solverCardId)}`, revisionId),
  );
}

export function getNeutralSolverMappingReport(
  config: ApiConfig,
  solverCardId: string,
  revisionId?: string,
): Promise<ApiResult<NeutralHyperelasticMappingReport>> {
  return request(
    config,
    revisionPath(
      `/neutral-solver-cards/${encodeURIComponent(solverCardId)}/mapping-report`,
      revisionId,
    ),
  );
}

export async function previewNeutralHyperelasticSolverCard(
  config: ApiConfig,
  solverCardId: string,
  revisionId?: string,
): Promise<ApiResult<string>> {
  const headers = authenticatedHeaders(config, {}, "text/plain");
  const response = await fetch(
    endpoint(
      config,
      revisionPath(
        `/neutral-solver-cards/${encodeURIComponent(solverCardId)}/preview`,
        revisionId,
      ),
    ),
    { headers },
  );
  if (!response.ok) return throwResponseError(response);
  return { data: await response.text(), etag: response.headers.get("etag") };
}

export async function downloadNeutralHyperelasticSolverCard(
  config: ApiConfig,
  solverCardId: string,
  revisionId?: string,
): Promise<ApiResult<SolverCardDownload>> {
  const headers = authenticatedHeaders(config, {}, "text/plain");
  const response = await fetch(
    endpoint(
      config,
      revisionPath(
        `/neutral-solver-cards/${encodeURIComponent(solverCardId)}/download`,
        revisionId,
      ),
    ),
    { headers },
  );
  if (!response.ok) return throwResponseError(response);
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? `solver-card-${solverCardId}.txt`;
  return {
    data: { blob: await response.blob(), filename },
    etag: response.headers.get("etag"),
  };
}

export async function downloadNeutralHyperelasticMappingReport(
  config: ApiConfig,
  solverCardId: string,
  revisionId?: string,
): Promise<ApiResult<{ blob: Blob; filename: string }>> {
  const result = await request<NeutralHyperelasticMappingReport>(
    config,
    revisionPath(
      `/neutral-solver-cards/${encodeURIComponent(solverCardId)}/mapping-report`,
      revisionId,
    ),
  );
  return {
    data: {
      blob: new Blob([JSON.stringify(result.data, null, 2)], { type: "application/json" }),
      filename: `mapping-report-${solverCardId}.json`,
    },
    etag: result.etag,
  };
}

export function createReferenceOgdenCandidateSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    calibration_run_id: string;
    calibration_candidate_id: string;
    selection_reason: string;
  },
): Promise<ApiResult<OgdenCandidateSelectionResponse>> {
  return request(config, "/ogden-candidate-selections", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function promoteReferenceOgdenCandidate(
  config: ApiConfig,
  selectionId: string,
  modelEtag: string,
  input: { selection_revision_id: string; change_reason: string },
): Promise<ApiResult<OgdenPronyModelResponse>> {
  return request(
    config,
    `/ogden-candidate-selections/${encodeURIComponent(selectionId)}/promotions`,
    {
      method: "POST",
      headers: { "If-Match": modelEtag },
      body: JSON.stringify(input),
    },
  );
}

export function listOgdenPronyModelRevisions(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<OgdenPronyRevisionListResponse>> {
  return request(
    config,
    `/ogden-prony-models/${encodeURIComponent(materialModelId)}/revisions`,
  );
}

export function preflightOgdenPronyCard(
  config: ApiConfig,
  materialModelId: string,
  materialModelRevisionId: string,
  solver: "abaqus" | "openradioss",
): Promise<ApiResult<OgdenPronyMappingResponse>> {
  return request(
    config,
    `/ogden-prony-models/${encodeURIComponent(materialModelId)}/solver-card-preflight`,
    {
      method: "POST",
      body: JSON.stringify({
        material_model_revision_id: materialModelRevisionId,
        target: { solver, version: "2025", unit_system: "kg_m_s" },
      }),
    },
  );
}

export function listOgdenPronyCards(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<{ items: OgdenPronyCardResponse[] }>> {
  return request(config, `/ogden-prony-models/${encodeURIComponent(materialModelId)}/solver-cards`);
}

export function createOgdenPronyCard(
  config: ApiConfig,
  materialModelId: string,
  input: {
    material_model_revision_id: string;
    solver: "abaqus" | "openradioss";
    expected_mapping_report_sha256: string;
    solver_material_id: number;
    material_name: string;
    change_reason: string;
  },
): Promise<ApiResult<OgdenPronyCardResponse>> {
  return request(config, `/ogden-prony-models/${encodeURIComponent(materialModelId)}/solver-cards`, {
    method: "POST",
    body: JSON.stringify({
      material_model_revision_id: input.material_model_revision_id,
      target: { solver: input.solver, version: "2025", unit_system: "kg_m_s" },
      expected_mapping_report_sha256: input.expected_mapping_report_sha256,
      solver_material_id: input.solver_material_id,
      material_name: input.material_name,
      change_reason: input.change_reason,
    }),
  });
}

export async function previewOgdenPronyCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<string>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/ogden-prony-solver-cards/${encodeURIComponent(solverCardId)}/preview`),
    { ...init, headers },
  );
  if (!response.ok) return throwResponseError(response);
  return { data: await response.text(), etag: response.headers.get("etag") };
}

export async function downloadOgdenPronyCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<{ blob: Blob; filename: string }>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/ogden-prony-solver-cards/${encodeURIComponent(solverCardId)}/download`),
    { ...init, headers },
  );
  if (!response.ok) return throwResponseError(response);
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "elastomer-card.txt";
  return { data: { blob: await response.blob(), filename }, etag: response.headers.get("etag") };
}

export function createTabulatedPlasticityModel(
  config: ApiConfig,
  materialStateId: string,
  input: {
    property_set_revision_id: string;
    dataset_revision_id: string;
    extension_max_true_plastic_strain: number;
    acknowledge_post_necking_approximation: boolean;
    change_reason: string;
  },
): Promise<ApiResult<TabulatedPlasticityModelResponse>> {
  return request(
    config,
    `/material-states/${encodeURIComponent(materialStateId)}/tabulated-plasticity-models`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function promoteProcessingOutputToTabulatedPlasticity(
  config: ApiConfig,
  processingOutputId: string,
  input: {
    material_state_id: string;
    property_set_revision_id: string;
    processing_output_revision_id: string;
    acknowledge_bounded_extrapolation: boolean;
    change_reason: string;
  },
): Promise<ApiResult<TabulatedPlasticityModelResponse>> {
  return request(
    config,
    `/processing-outputs/${encodeURIComponent(processingOutputId)}/tabulated-plasticity-models`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function getTabulatedPlasticityHardeningCurve(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<HardeningCurveResponse>> {
  return request(
    config,
    `/tabulated-plasticity-models/${encodeURIComponent(materialModelId)}/hardening-curve`,
  );
}

export function preflightElastoplasticMapping(
  config: ApiConfig,
  materialModelId: string,
  materialModelRevisionId: string,
  target: ExportTarget,
): Promise<ApiResult<MappingReport>> {
  return request(
    config,
    `/tabulated-plasticity-models/${encodeURIComponent(materialModelId)}/mapping-preflight`,
    {
      method: "POST",
      body: JSON.stringify({ material_model_revision_id: materialModelRevisionId, target }),
    },
  );
}

export function listElastoplasticSolverCards(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<{ items: ElastoplasticCardResponse[] }>> {
  return request(
    config,
    `/tabulated-plasticity-models/${encodeURIComponent(materialModelId)}/solver-cards`,
  );
}

export function createElastoplasticSolverCard(
  config: ApiConfig,
  materialModelId: string,
  input: {
    material_model_revision_id: string;
    target: ExportTarget;
    expected_mapping_report_sha256: string;
    solver_material_id: number;
    material_name: string;
    change_reason: string;
  },
): Promise<ApiResult<ElastoplasticCardCreatedResponse>> {
  return request(
    config,
    `/tabulated-plasticity-models/${encodeURIComponent(materialModelId)}/solver-cards`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export async function previewElastoplasticSolverCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<string>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/elastoplastic-solver-cards/${encodeURIComponent(solverCardId)}/preview`),
    { ...init, headers },
  );
  if (!response.ok) {
    return throwResponseError(response);
  }
  return { data: await response.text(), etag: response.headers.get("etag") };
}

export async function downloadElastoplasticSolverCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<SolverCardDownload>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/elastoplastic-solver-cards/${encodeURIComponent(solverCardId)}/download`),
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
      filename: match?.[1] ?? `elastoplastic-card-${solverCardId}.txt`,
    },
    etag: response.headers.get("etag"),
  };
}

export function createViscoelasticSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    members: Array<{ dataset_id: string; dataset_revision_id: string }>;
    change_reason: string;
  },
): Promise<ApiResult<ViscoelasticSelectionResponse>> {
  return request(config, "/viscoelastic-selections", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createViscoelasticMasterPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    plan_label: string;
    selection_id: string;
    selection_revision_id: string;
    reference_temperature_k: number;
    grid_point_count: number;
    shift_method: ViscoelasticShiftMethod;
    manual_shift_factors: Array<{ temperature_k: number; log10_a_t: number }>;
    change_reason: string;
  },
): Promise<ApiResult<ViscoelasticMasterPlanResponse>> {
  return request(config, "/processing-plans/viscoelastic-master-curve", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeViscoelasticMasterPlan(
  config: ApiConfig,
  input: { plan_id: string; plan_revision_id: string; change_reason: string },
): Promise<ApiResult<ViscoelasticMasterRunResponse>> {
  return request(config, "/processing-runs/viscoelastic-master-curve", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function previewViscoelasticMasterRun(
  config: ApiConfig,
  runId: string,
): Promise<ApiResult<ViscoelasticMasterPreviewResponse>> {
  return request(
    config,
    `/processing-runs/viscoelastic-master-curve/${encodeURIComponent(runId)}/preview`,
  );
}
