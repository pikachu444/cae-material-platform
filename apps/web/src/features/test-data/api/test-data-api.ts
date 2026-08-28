import type {
  CanonicalTestDataDocumentResponse,
  CanonicalTestDataPreviewResponse,
  CommonExportProvenance,
  CompletedUpload,
  CurvePreview,
  DataClassification,
  DatasetResponse,
  DatasetSelectionResponse,
  DistributionFamily,
  ExactUnitProfilePin,
  GovernedDatasetResponse,
  GovernedImportPreview,
  GovernedImportProfileContent,
  GovernedImportProfileResponse,
  GovernedImportRunResponse,
  GovernedTabularFileFormat,
  ImportDetectionReportResponse,
  ImportMappingResponse,
  ImportRunResponse,
  InstrumentCalibrationResponse,
  InstrumentContent,
  InstrumentResponse,
  LinearViscoelasticModelResponse,
  OutlierAssessmentResponse,
  OutlierDetectionPlanResponse,
  OutlierDetectionRunResponse,
  OutlierScopeComparisonResponse,
  ProcessingRecipeResponse,
  ProcessingRunResponse,
  PronyCalibrationDiagnosticsResponse,
  PronyCalibrationPlanResponse,
  PronyCalibrationRunResponse,
  PronyCandidateSelectionResponse,
  ReferenceCalibrationScopeResponse,
  ReferenceTensileMapping,
  ReplicateAlignmentBatchResponse,
  ReplicateOutlierAssessmentResponse,
  ReplicateOutlierDecision,
  ReplicateOutlierPlanResponse,
  ReplicateOutlierRunResponse,
  ReplicateStatisticalCurveResponse,
  ReplicateStatisticalPlanResponse,
  ReplicateStatisticalResultResponse,
  ReplicateStatisticalRunResponse,
  ScalarDistributionResultResponse,
  ScalarDistributionSelectionResponse,
  ShearRelaxationCurvePreview,
  ShearRelaxationDatasetResponse,
  ShearRelaxationProcessingRecipeResponse,
  ShearRelaxationProcessingRunResponse,
  SpecimenResponse,
  SpecimenSourceResponse,
  StatisticalCurvePreview,
  StatisticalPlanResponse,
  StatisticalResultResponse,
  StatisticalRunResponse,
  TensileReplicateSelectionResponse,
  TestCampaignContent,
  TestCampaignResponse,
  TestConditionContent,
  TestConditionResponse,
  TestMethodResponse,
  TestRunContextContent,
  TestRunContextResponse,
  TestRunResponse,
  UploadSession,
} from "../../../types";

import {
  ApiError,
  authenticatedHeaders,
  endpoint,
  request,
  throwResponseError,
} from "../../../shared/api/http";

import type { ApiConfig, ApiResult } from "../../../shared/api/http";

interface CanonicalTestDataDownload {
  blob: Blob;
  filename: string;
}

export function validateCanonicalTestData(
  config: ApiConfig,
  document: Record<string, unknown>,
): Promise<ApiResult<CanonicalTestDataPreviewResponse>> {
  return request(config, "/test-data:validate", {
    method: "POST",
    body: JSON.stringify(document),
  });
}

export function convertTabularToCanonicalTestData(
  config: ApiConfig,
  input: Record<string, unknown>,
): Promise<ApiResult<CanonicalTestDataPreviewResponse>> {
  return request(config, "/test-data:convert-tabular", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function importCanonicalTestData(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    document: Record<string, unknown>;
    change_reason: string;
    governed_source?: CommonExportProvenance;
  },
): Promise<ApiResult<CanonicalTestDataDocumentResponse>> {
  return request(config, "/test-data-documents", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listCanonicalTestDataDocuments(
  config: ApiConfig,
): Promise<ApiResult<{ items: CanonicalTestDataDocumentResponse[] }>> {
  return request(config, "/test-data-documents");
}

export function reviseCanonicalTestData(
  config: ApiConfig,
  documentId: string,
  etag: string,
  input: {
    document: Record<string, unknown>;
    change_reason: string;
    governed_source?: CommonExportProvenance;
  },
): Promise<ApiResult<CanonicalTestDataDocumentResponse>> {
  return request(config, `/test-data-documents/${encodeURIComponent(documentId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}

export async function downloadCanonicalTestDataDocument(
  config: ApiConfig,
  documentId: string,
  revisionId: string,
): Promise<ApiResult<CanonicalTestDataDownload>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "application/vnd.cmp.test-data+json");
  const response = await fetch(
    endpoint(
      config,
      `/test-data-documents/${encodeURIComponent(documentId)}/revisions/${encodeURIComponent(revisionId)}/content`,
    ),
    { ...init, headers },
  );
  if (!response.ok) return throwResponseError(response);
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return {
    data: {
      blob: await response.blob(),
      filename: match?.[1] ?? `test-data-${documentId}.json`,
    },
    etag: response.headers.get("etag"),
  };
}

export async function downloadCanonicalTestDataPackage(
  config: ApiConfig,
  revisions: Array<{ document_id: string; revision_id: string }>,
): Promise<ApiResult<CanonicalTestDataDownload>> {
  const init: RequestInit = {
    method: "POST",
    body: JSON.stringify({ revisions }),
  };
  const headers = authenticatedHeaders(config, init, "application/vnd.cmp.test-data-package+zip");
  const response = await fetch(endpoint(config, "/test-data-packages:download"), {
    ...init,
    headers,
  });
  if (!response.ok) return throwResponseError(response);
  return {
    data: { blob: await response.blob(), filename: "cmp-test-data-package.zip" },
    etag: response.headers.get("etag"),
  };
}

/**
 * Compatibility for the Activity section still composed in
 * material-library.tsx. The Modeling feature owns the primary client; remove
 * these two root calls when #262 extracts Activity from the registered
 * Materials hotspot and #263 retires root API compatibility.
 */

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

export function getSpecimenSource(
  config: ApiConfig,
  specimenId: string,
): Promise<ApiResult<SpecimenSourceResponse | null>> {
  return request(config, `/specimens/${encodeURIComponent(specimenId)}/source-genealogy`);
}

export function createSpecimenSource(
  config: ApiConfig,
  specimenId: string,
  input: {
    content: {
      specimen_revision_id: string;
      sources: Array<{
        material_lot_id: string;
        material_lot_revision_id: string;
        note: string | null;
      }>;
      note: string | null;
    };
    change_reason: string;
  },
): Promise<ApiResult<SpecimenSourceResponse>> {
  return request(config, `/specimens/${encodeURIComponent(specimenId)}/source-genealogy`, {
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

export function createReferenceShearRelaxationTestMethod(
  config: ApiConfig,
  input: { classification: DataClassification; change_reason: string },
): Promise<ApiResult<TestMethodResponse>> {
  return request(config, "/test-methods/reference-shear-relaxation", {
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

export function createReferenceShearRelaxationTestRun(
  config: ApiConfig,
  input: {
    specimen_id: string;
    specimen_revision_id: string;
    test_method_id: string;
    test_method_revision_id: string;
    run_label: string;
    performed_at: string;
    test_temperature_k: number | null;
    change_reason: string;
  },
): Promise<ApiResult<TestRunResponse>> {
  return request(config, "/test-runs/reference-shear-relaxation", {
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

export function listTestCampaigns(
  config: ApiConfig,
): Promise<ApiResult<{ items: TestCampaignResponse[] }>> {
  return request(config, "/test-campaigns");
}

export function createTestCampaign(
  config: ApiConfig,
  content: TestCampaignContent,
): Promise<ApiResult<TestCampaignResponse>> {
  return request(config, "/test-campaigns", {
    method: "POST",
    body: JSON.stringify({ content, change_reason: "Register governed Test Campaign" }),
  });
}

export function listInstruments(
  config: ApiConfig,
): Promise<ApiResult<{ items: InstrumentResponse[] }>> {
  return request(config, "/instruments");
}

export function createInstrument(
  config: ApiConfig,
  classification: DataClassification,
  content: InstrumentContent,
): Promise<ApiResult<InstrumentResponse>> {
  return request(config, "/instruments", {
    method: "POST",
    body: JSON.stringify({ classification, content, change_reason: "Register governed Instrument" }),
  });
}

export function listInstrumentCalibrations(
  config: ApiConfig,
  instrumentId: string,
): Promise<ApiResult<{ items: InstrumentCalibrationResponse[] }>> {
  return request(config, `/instruments/${encodeURIComponent(instrumentId)}/calibrations`);
}

export function createInstrumentCalibration(
  config: ApiConfig,
  instrumentId: string,
  content: Omit<InstrumentCalibrationResponse["current_revision"]["content"], "instrument_id">,
): Promise<ApiResult<InstrumentCalibrationResponse>> {
  return request(config, `/instruments/${encodeURIComponent(instrumentId)}/calibrations`, {
    method: "POST",
    body: JSON.stringify({ content, change_reason: "Record exact Instrument calibration" }),
  });
}

export function listTestConditions(
  config: ApiConfig,
): Promise<ApiResult<{ items: TestConditionResponse[] }>> {
  return request(config, "/test-conditions");
}

export function createTestCondition(
  config: ApiConfig,
  content: TestConditionContent,
): Promise<ApiResult<TestConditionResponse>> {
  return request(config, "/test-conditions", {
    method: "POST",
    body: JSON.stringify({ content, change_reason: "Capture typed Test conditions" }),
  });
}

export function getTestRunContext(
  config: ApiConfig,
  testRunId: string,
): Promise<ApiResult<TestRunContextResponse | null>> {
  return request(config, `/test-runs/${encodeURIComponent(testRunId)}/context`);
}

export function createTestRunContext(
  config: ApiConfig,
  testRunId: string,
  content: Omit<TestRunContextContent, "test_run_id">,
): Promise<ApiResult<TestRunContextResponse>> {
  return request(config, `/test-runs/${encodeURIComponent(testRunId)}/context`, {
    method: "POST",
    body: JSON.stringify({ content, change_reason: "Bind exact Test Run execution context" }),
  });
}

export function listDatasetsForMaterialState(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: DatasetResponse[] }>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/datasets`);
}

export function listShearRelaxationDatasetsForMaterialState(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: ShearRelaxationDatasetResponse[] }>> {
  return request(
    config,
    `/material-states/${encodeURIComponent(materialStateId)}/shear-relaxation-datasets`,
  );
}

export function importReferenceShearRelaxationDataset(
  config: ApiConfig,
  input: {
    test_run_id: string;
    test_run_revision_id: string;
    raw_asset_id: string;
    raw_artifact_id: string;
    mapping: {
      time_column: string;
      shear_modulus_column: string;
      time_unit: "s" | "ms" | "min" | "h";
      shear_modulus_unit: "Pa" | "kPa" | "MPa" | "GPa";
    };
    change_reason: string;
  },
): Promise<ApiResult<ShearRelaxationDatasetResponse>> {
  return request(config, "/shear-relaxation-datasets", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function previewShearRelaxationDataset(
  config: ApiConfig,
  datasetId: string,
  maximumPoints = 500,
): Promise<ApiResult<ShearRelaxationCurvePreview>> {
  return request(
    config,
    `/shear-relaxation-datasets/${encodeURIComponent(datasetId)}/preview?maximum_points=${maximumPoints}`,
  );
}

export function createReferenceShearRelaxationCropRecipe(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    recipe_label: string;
    minimum_time_s: number;
    maximum_time_s: number;
    change_reason: string;
  },
): Promise<ApiResult<ShearRelaxationProcessingRecipeResponse>> {
  return request(config, "/processing-recipes/reference-shear-relaxation-crop", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceShearRelaxationCrop(
  config: ApiConfig,
  input: {
    recipe_id: string;
    recipe_revision_id: string;
    input_dataset_id: string;
    input_dataset_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<ShearRelaxationProcessingRunResponse>> {
  return request(config, "/processing-runs/reference-shear-relaxation-crop", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferencePronyCalibrationPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    plan_label: string;
    input_dataset_id: string;
    input_dataset_revision_id: string;
    baseline_model_id: string;
    baseline_model_revision_id: string;
    total_g_ratio: { lower: number; initial: number; upper: number };
    fast_term_fraction: { lower: number; initial: number; upper: number };
    fast_relaxation_time_s: { lower: number; initial: number; upper: number };
    slow_relaxation_time_s: { lower: number; initial: number; upper: number };
    normalization_modulus_pa: number;
    multistart_count: number;
    random_seed: number;
    change_reason: string;
  },
): Promise<ApiResult<PronyCalibrationPlanResponse>> {
  return request(config, "/prony-calibration-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferencePronyCalibration(
  config: ApiConfig,
  planId: string,
  input: { plan_revision_id: string; change_reason: string },
): Promise<ApiResult<PronyCalibrationRunResponse>> {
  return request(config, `/prony-calibration-plans/${encodeURIComponent(planId)}/runs`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getReferencePronyCandidateDiagnostics(
  config: ApiConfig,
  candidateId: string,
): Promise<ApiResult<PronyCalibrationDiagnosticsResponse>> {
  return request(
    config,
    `/prony-calibration-candidates/${encodeURIComponent(candidateId)}/diagnostics`,
  );
}

export function createReferencePronyCandidateSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    calibration_run_id: string;
    calibration_candidate_id: string;
    selection_reason: string;
  },
): Promise<ApiResult<PronyCandidateSelectionResponse>> {
  return request(config, "/prony-candidate-selections", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function promoteReferencePronyCandidate(
  config: ApiConfig,
  selectionId: string,
  input: { selection_revision_id: string; change_reason: string },
): Promise<ApiResult<LinearViscoelasticModelResponse>> {
  return request(
    config,
    `/prony-candidate-selections/${encodeURIComponent(selectionId)}/promotions`,
    { method: "POST", body: JSON.stringify(input) },
  );
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

export function createReferenceTensileReplicateSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    dataset_revision_ids: string[];
    change_reason: string;
  },
): Promise<ApiResult<TensileReplicateSelectionResponse>> {
  return request(config, "/dataset-selections/reference-tensile-replicates", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseReferenceTensileReplicateSelection(
  config: ApiConfig,
  selectionId: string,
  input: {
    expected_current_revision_id: string;
    dataset_revision_ids: string[];
    change_reason: string;
  },
): Promise<ApiResult<TensileReplicateSelectionResponse>> {
  return request(
    config,
    `/dataset-selections/reference-tensile-replicates/${encodeURIComponent(selectionId)}/revisions`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function listReferenceTensileReplicateSelections(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: TensileReplicateSelectionResponse[] }>> {
  return request(
    config,
    `/dataset-selections/reference-tensile-replicates?material_state_id=${encodeURIComponent(materialStateId)}`,
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

export function createReferenceTensileAlignmentRecipe(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      recipe_label: string;
      grid_start_engineering_strain: number;
      grid_end_engineering_strain: number;
      grid_point_count: number;
      domain_policy: "intersection";
      interpolation_policy: "piecewise_linear";
      extrapolation_policy: "reject";
    };
    change_reason: string;
  },
): Promise<ApiResult<ProcessingRecipeResponse>> {
  return request(config, "/processing-recipes/reference-tensile-common-grid", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceTensileAlignment(
  config: ApiConfig,
  input: {
    selection_id: string;
    selection_revision_id: string;
    recipe_id: string;
    recipe_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<ReplicateAlignmentBatchResponse>> {
  return request(config, "/processing-runs/reference-tensile-common-grid", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listReferenceTensileReplicateStatisticalPlans(
  config: ApiConfig,
  selectionRevisionId: string,
): Promise<ApiResult<{ items: ReplicateStatisticalPlanResponse[] }>> {
  const query = new URLSearchParams({ selection_revision_id: selectionRevisionId, limit: "100" });
  return request(config, `/replicate-statistical-plans?${query.toString()}`);
}

export function createReferenceTensileReplicateStatisticalPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    plan_label: string;
    selection_id: string;
    selection_revision_id: string;
    sample_count: number;
    scalar_distribution?: {
      seed: number;
      bootstrap_samples: 999;
      unit_profile: ExactUnitProfilePin | null;
    } | null;
    change_reason: string;
  },
): Promise<ApiResult<ReplicateStatisticalPlanResponse>> {
  return request(config, "/replicate-statistical-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceTensileReplicateStatistics(
  config: ApiConfig,
  input: { plan_id: string; plan_revision_id: string; change_reason: string },
): Promise<ApiResult<ReplicateStatisticalRunResponse>> {
  return request(config, "/replicate-statistical-runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listReferenceTensileReplicateStatisticalRuns(
  config: ApiConfig,
  planRevisionId: string,
): Promise<ApiResult<{ items: ReplicateStatisticalRunResponse[] }>> {
  const query = new URLSearchParams({ plan_revision_id: planRevisionId, limit: "100" });
  return request(config, `/replicate-statistical-runs?${query.toString()}`);
}

export function getReferenceTensileReplicateStatisticalResult(
  config: ApiConfig,
  resultId: string,
): Promise<ApiResult<ReplicateStatisticalResultResponse>> {
  return request(config, `/replicate-statistical-results/${encodeURIComponent(resultId)}`);
}

export function previewReferenceTensileReplicateStatisticalResultCurve(
  config: ApiConfig,
  resultId: string,
  maximumPoints = 1_000,
): Promise<ApiResult<ReplicateStatisticalCurveResponse>> {
  const query = new URLSearchParams({ maximum_points: String(maximumPoints) });
  return request(
    config,
    `/replicate-statistical-results/${encodeURIComponent(resultId)}/curve?${query.toString()}`,
  );
}

export function getScalarDistributionResult(
  config: ApiConfig,
  resultId: string,
): Promise<ApiResult<ScalarDistributionResultResponse>> {
  return request(config, `/scalar-distribution-results/${encodeURIComponent(resultId)}`);
}

export function listScalarDistributionSelections(
  config: ApiConfig,
  resultId: string,
): Promise<ApiResult<{ items: ScalarDistributionSelectionResponse[] }>> {
  return request(
    config,
    `/scalar-distribution-results/${encodeURIComponent(resultId)}/selections`,
  );
}

export function createScalarDistributionSelection(
  config: ApiConfig,
  resultId: string,
  input: {
    classification: DataClassification;
    distribution_result_revision_id: string;
    selected_family: DistributionFamily;
    candidate_sha256: string;
    selection_reason: string;
  },
): Promise<ApiResult<ScalarDistributionSelectionResponse>> {
  return request(
    config,
    `/scalar-distribution-results/${encodeURIComponent(resultId)}/selections`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function reviseScalarDistributionSelection(
  config: ApiConfig,
  selectionId: string,
  input: {
    expected_current_revision_id: string;
    distribution_result_id: string;
    distribution_result_revision_id: string;
    selected_family: DistributionFamily;
    candidate_sha256: string;
    selection_reason: string;
  },
): Promise<ApiResult<ScalarDistributionSelectionResponse>> {
  return request(
    config,
    `/scalar-distribution-selections/${encodeURIComponent(selectionId)}`,
    { method: "PUT", body: JSON.stringify(input) },
  );
}

export function createReplicateOutlierDetectionPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    plan_label: string;
    statistical_result_id: string;
    statistical_result_revision_id: string;
    absolute_modified_z_threshold: number;
    change_reason: string;
  },
): Promise<ApiResult<ReplicateOutlierPlanResponse>> {
  return request(config, "/replicate-outlier-detection-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReplicateOutlierDetection(
  config: ApiConfig,
  input: { detection_plan_id: string; detection_plan_revision_id: string },
): Promise<ApiResult<ReplicateOutlierRunResponse>> {
  return request(config, "/replicate-outlier-detection-runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReplicateOutlierAssessment(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    candidate_id: string;
    detection_plan_id: string;
    detection_plan_revision_id: string;
    decision: ReplicateOutlierDecision;
    assessment_reason: string;
    change_reason: string;
  },
): Promise<ApiResult<ReplicateOutlierAssessmentResponse>> {
  return request(config, "/replicate-outlier-assessments", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferenceCalibrationInputScope(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    scope_label: string;
    detection_run_id: string;
    assessment_revision_ids: string[];
    change_reason: string;
  },
): Promise<ApiResult<ReferenceCalibrationScopeResponse>> {
  return request(config, "/reference-calibration-input-scopes", {
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

async function sha256Hex(file: Blob): Promise<string> {
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

export async function uploadGovernedTabularFile(
  config: ApiConfig,
  input: {
    file: File;
    file_format: GovernedTabularFileFormat;
    classification: DataClassification;
    test_run_revision_id?: string | null;
  },
): Promise<ApiResult<CompletedUpload>> {
  const filename = input.file.name.trim();
  if (!filename || filename.includes("/") || filename.includes("\\")) {
    throw new ApiError(422, "Choose a file with a safe, non-empty filename.");
  }
  if (input.file.size < 1 || input.file.size > 16 * 1024 * 1024) {
    throw new ApiError(422, "The governed source must be between 1 byte and 16 MiB.");
  }
  const mediaType = {
    csv: "text/csv",
    tsv: "text/tab-separated-values",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  }[input.file_format];
  const digest = await sha256Hex(input.file);
  const created = await request<{ upload: UploadSession; upload_capability: string }>(
    config,
    "/uploads",
    {
      method: "POST",
      headers: { "Idempotency-Key": browserIdempotencyKey() },
      body: JSON.stringify({
        classification: input.classification,
        original_filename: filename,
        media_type: mediaType,
        expected_size_bytes: input.file.size,
        expected_sha256: digest,
        test_run_revision_id: input.test_run_revision_id ?? null,
      }),
    },
  );
  const { upload, upload_capability: capability } = created.data;
  for (let partNumber = 1; partNumber <= upload.expected_part_count; partNumber += 1) {
    const start = (partNumber - 1) * upload.part_size_bytes;
    const part = input.file.slice(start, Math.min(input.file.size, start + upload.part_size_bytes));
    await request<UploadSession>(
      config,
      `/uploads/${encodeURIComponent(upload.upload_id)}/parts/${partNumber}`,
      {
        method: "PUT",
        headers: { "Content-Type": mediaType, "Upload-Capability": capability },
        body: part,
      },
    );
  }
  return request<CompletedUpload>(
    config,
    `/uploads/${encodeURIComponent(upload.upload_id)}:complete`,
    { method: "POST", headers: { "Upload-Capability": capability } },
  );
}

export function previewGovernedTabularImport(
  config: ApiConfig,
  input: {
    raw_asset_id: string;
    raw_artifact_id: string;
    file_format: GovernedTabularFileFormat;
    sheet_name: string | null;
    header_row: number;
    encoding: string;
    delimiter: string | null;
    decimal_separator: "." | ",";
  },
): Promise<ApiResult<GovernedImportPreview>> {
  return request(config, "/tabular-import-previews", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function listGovernedImportProfiles(
  config: ApiConfig,
): Promise<ApiResult<GovernedImportProfileResponse[]>> {
  const result = await request<{ items: GovernedImportProfileResponse[] }>(
    config,
    "/import-profiles",
  );
  return { data: result.data.items, etag: result.etag };
}

export function createGovernedImportProfile(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: GovernedImportProfileContent;
    change_reason: string;
  },
): Promise<ApiResult<GovernedImportProfileResponse>> {
  return request(config, "/import-profiles", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseGovernedImportProfile(
  config: ApiConfig,
  profileId: string,
  input: {
    expected_current_revision_id: string;
    content: GovernedImportProfileContent;
    change_reason: string;
  },
): Promise<ApiResult<GovernedImportProfileResponse>> {
  return request(config, `/import-profiles/${encodeURIComponent(profileId)}/revisions`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeGovernedTabularImport(
  config: ApiConfig,
  input: {
    test_run_id: string;
    test_run_revision_id: string;
    raw_asset_id: string;
    raw_artifact_id: string;
    import_profile_id: string;
    import_profile_revision_id: string;
    change_reason: string;
  },
  idempotencyKey: string = crypto.randomUUID(),
): Promise<ApiResult<GovernedImportRunResponse>> {
  return request(config, "/tabular-import-runs", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(input),
  });
}

export function listGovernedDatasetsForTestRun(
  config: ApiConfig,
  testRunId: string,
): Promise<ApiResult<{ items: GovernedDatasetResponse[] }>> {
  return request(
    config,
    `/governed-datasets?test_run_id=${encodeURIComponent(testRunId)}`,
  );
}
