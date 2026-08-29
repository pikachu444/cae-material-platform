import type {

  Applicability,

  DataClassification,

  ProvenanceSummary,

  RevisionMetadata,

} from "../../../shared/model/core-contracts";

import type {

  ExportTarget,

  MappingItem,

  MappingReport,

  MappingStatus,

} from "./export-contracts";

export interface ReferenceLinearElasticContent {
  model_family_id: string;
  model_schema_version: string;
  model_schema_digest: string;
  material_id: string;
  material_revision_id: string;
  material_state_id: string;
  material_state_revision_id: string;
  property_set_id: string;
  property_set_revision_id: string;
  density_kg_per_m3: number;
  youngs_modulus_pa: number;
  poisson_ratio: number;
  source_yield_stress_pa: number | null;
  applicable_temperature_min_k: number | null;
  applicable_temperature_max_k: number | null;
  applicable_strain_rate_min_per_s: number | null;
  applicable_strain_rate_max_per_s: number | null;
  applicability_note: string | null;
  reference_temperature_k: number;
  calibration_evidence: ReferenceCalibrationEvidence | null;
  non_production: true;
}

export interface ReferenceCalibrationEvidence {
  calibration_selection_id: string;
  calibration_selection_revision_id: string;
  calibration_run_id: string;
  calibration_candidate_id: string;
  calibration_candidate_sha256: string;
  diagnostics_artifact_id: string;
  diagnostics_sha256: string;
}

export interface MaterialModelProvenanceSummary extends ProvenanceSummary {
  source_property_set_revision_id: string;
  calibration_selection_revision_id: string | null;
}

export interface MaterialModelRevision extends RevisionMetadata {
  content: ReferenceLinearElasticContent;
  ir: Record<string, unknown>;
  provenance: MaterialModelProvenanceSummary;
}

export interface MaterialModelResponse {
  material_model_id: string;
  material_state_id: string;
  current_revision: MaterialModelRevision;
  links: {
    self: string;
    revisions: string;
    preflight: string;
    solver_cards: string;
  };
}

export interface MaterialModelList {
  items: MaterialModelResponse[];
}

export interface ReferenceModelCreateInput {
  property_set_revision_id: string;
  change_reason: string;
}

/**
 * FE-04G compatibility projections for root DTOs and the Solver Card
 * consumers that still import this module. Modeling owns the source shapes;
 * remove these projections in #263 with the remaining root DTO split.
 */

export interface SolverCardContent {
  material_model_id: string;
  material_model_revision_id: string;
  model_schema_digest: string;
  target: ExportTarget;
  solver_material_id: number;
  card_title: string;
  density_kg_per_m3: number;
  youngs_modulus_pa: number;
  poisson_ratio: number;
  source_yield_stress_pa: number | null;
  applicable_temperature_min_k: number | null;
  applicable_temperature_max_k: number | null;
  applicable_strain_rate_min_per_s: number | null;
  applicable_strain_rate_max_per_s: number | null;
  mapping_report_sha256: string;
  card_sha256: string;
  exporter_id: string;
  exporter_version: string;
  exporter_digest: string;
  non_production: true;
}

export interface SolverCardProvenanceSummary extends ProvenanceSummary {
  source_material_model_revision_id: string;
  mapping_report_sha256: string;
}

export interface SolverCardRevision extends RevisionMetadata {
  content: SolverCardContent;
  mapping_report: MappingReport;
  provenance: SolverCardProvenanceSummary;
}

export interface SolverCardResponse {
  solver_card_id: string;
  material_model_id: string;
  target: ExportTarget;
  solver_material_id: number;
  current_revision: SolverCardRevision;
  links: {
    self: string;
    revisions: string;
    preview: string;
    download: string;
  };
}

export interface SolverCardList {
  items: SolverCardResponse[];
}

export interface SolverCardCreateInput {
  material_model_revision_id: string;
  target: ExportTarget;
  expected_mapping_report_sha256: string;
  solver_material_id: number;
  card_title: string;
  change_reason: string;
}

export interface ReferenceValidationTemplateContent {
  template_label: string;
  template_kind: "reference_uniaxial_tensile_virtual_specimen";
  gauge_length_m: number;
  cross_section_area_m2: number;
  axial_element_count: number;
  axial_displacement_end_m: number;
  output_sample_count: number;
  result_extraction_profile_id: "urn:cmp:validation:reference-native-curve-extractor:1.0.0";
  metric_profile_id: "urn:cmp:validation:reference-relative-rmse:1.0.0";
  target_solver: "openradioss";
  target_version: "2025";
  target_unit_system: "kg_m_s";
  runner_command_id: "reference_inline_mock";
  non_production: true;
}

export interface ValidationTemplateRevision extends RevisionMetadata {
  content: ReferenceValidationTemplateContent;
}

export interface ValidationTemplateResponse {
  validation_template_id: string;
  current_revision: ValidationTemplateRevision;
  links: Record<string, string>;
}

export interface ReferenceValidationPlanContent {
  plan_label: string;
  plan_kind: "reference_uniaxial_tensile_validation";
  validation_template_id: string;
  validation_template_revision_id: string;
  material_model_id: string;
  material_model_revision_id: string;
  solver_card_id: string;
  solver_card_revision_id: string;
  experimental_selection_id: string;
  experimental_selection_revision_id: string;
  runner_id: "cmp.reference.inline-mock-runner";
  runner_version: "1.0.0";
  runner_digest: string;
  non_production: true;
}

export interface ValidationPlanRevision extends RevisionMetadata {
  content: ReferenceValidationPlanContent;
}

export interface ValidationPlanResponse {
  validation_plan_id: string;
  current_revision: ValidationPlanRevision;
  links: Record<string, string>;
}

export interface ValidationArtifactPointer {
  artifact_id: string;
  sha256: string;
}

export type ValidationExecutionMode = "reference_inline_mock" | "manual_attach";
export type ValidationRunStatus =
  | "queued"
  | "waiting_manual"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";
export type ReferenceRunnerOutcome =
  | "succeeded"
  | "license_unavailable"
  | "queue_timeout"
  | "solver_failed";

export interface ValidationResultManifestResponse {
  validation_result_manifest_id: string;
  validation_run_id: string;
  execution_mode: ValidationExecutionMode;
  solver_termination: "normal" | "abnormal" | "not_available";
  external_job_reference: string | null;
  deck: ValidationArtifactPointer;
  stdout: ValidationArtifactPointer;
  stderr: ValidationArtifactPointer;
  native_result: ValidationArtifactPointer | null;
  native_result_state: "available" | "not_available";
  manifest_artifact: ValidationArtifactPointer;
  manifest_sha256: string;
  created_at: string;
  created_by: string;
}

export type ValidationResponseExtractionStatus = "extracted" | "not_evaluated";
export type NumericalHealthStatus = "healthy" | "unhealthy" | "not_evaluated";
export type ValidationVerdict = "passed" | "failed" | "not_evaluated";
export type HoldoutIndependence =
  | "not_applicable_manual_ir"
  | "independent_selection"
  | "overlaps_calibration_selection";

export interface ValidationResponseExtractionResponse {
  response_extraction_id: string;
  validation_run_id: string;
  validation_result_manifest_id: string;
  source_native_result: ValidationArtifactPointer | null;
  status: ValidationResponseExtractionStatus;
  normalized_response: ValidationArtifactPointer | null;
  point_count: number | null;
  reason_code: string | null;
  created_at: string;
  created_by: string;
}

export interface NumericalHealthReportResponse {
  numerical_health_report_id: string;
  validation_run_id: string;
  validation_result_manifest_id: string;
  response_extraction_id: string;
  status: NumericalHealthStatus;
  solver_termination: "normal" | "abnormal" | "not_available";
  native_result_state: "available" | "not_available";
  expected_point_count: number;
  observed_point_count: number | null;
  output_complete: boolean;
  finite_values: boolean;
  strictly_increasing_strain: boolean;
  reason_code: string | null;
  report_artifact: ValidationArtifactPointer;
  report_sha256: string;
  created_at: string;
  created_by: string;
}

export interface ReferenceValidationResultResponse {
  validation_result_id: string;
  validation_run_id: string;
  validation_result_manifest_id: string;
  response_extraction: ValidationResponseExtractionResponse;
  numerical_health_report: NumericalHealthReportResponse;
  experimental_selection_id: string;
  experimental_selection_revision_id: string;
  metric_profile_id: "urn:cmp:validation:reference-relative-rmse:1.0.0";
  threshold_profile_id: "urn:cmp:validation:reference-relative-rmse-threshold:1.0.0";
  alignment_profile_id: "urn:cmp:validation:reference-linear-interpolation-observed-grid:1.0.0";
  relative_rmse_threshold: number;
  experimental_point_count: number;
  simulated_point_count: number | null;
  compared_point_count: number;
  root_mean_squared_error_pa: number | null;
  relative_root_mean_squared_error: number | null;
  normalization_stress_scale_pa: number | null;
  holdout_independence: HoldoutIndependence;
  verdict: ValidationVerdict;
  reason_code: string | null;
  result_artifact: ValidationArtifactPointer;
  result_sha256: string;
  created_at: string;
  created_by: string;
  links: Record<string, string>;
}

export interface ValidationResponseCurvePoint {
  engineering_strain: number;
  engineering_stress_pa: number;
}

export interface ValidationComparisonCurvePoint {
  engineering_strain: number;
  observed_engineering_stress_pa: number;
  simulated_engineering_stress_pa: number;
  residual_engineering_stress_pa: number;
}

export interface ValidationResultCurveResponse {
  validation_result_id: string;
  verdict: ValidationVerdict;
  response_point_count: number;
  returned_response_point_count: number;
  response_sampled: boolean;
  response_points: ValidationResponseCurvePoint[];
  comparison_point_count: number;
  returned_comparison_point_count: number;
  comparison_sampled: boolean;
  comparison_points: ValidationComparisonCurvePoint[];
}

export interface ValidationRunResponse {
  validation_run_id: string;
  classification: DataClassification;
  validation_plan_id: string;
  validation_plan_revision_id: string;
  validation_template_id: string;
  validation_template_revision_id: string;
  material_model_id: string;
  material_model_revision_id: string;
  solver_card_id: string;
  solver_card_revision_id: string;
  experimental_selection_id: string;
  experimental_selection_revision_id: string;
  execution_mode: ValidationExecutionMode;
  runner_id: "cmp.reference.inline-mock-runner";
  runner_version: "1.0.0";
  runner_digest: string;
  status: ValidationRunStatus;
  deck: ValidationArtifactPointer;
  external_job_reference: string | null;
  failure_code: string | null;
  submitted_at: string;
  started_at: string | null;
  ended_at: string | null;
  created_by: string;
  request_id: string;
  trace_id: string;
  change_reason: string;
  result_manifest: ValidationResultManifestResponse | null;
  validation_result: ReferenceValidationResultResponse | null;
  links: Record<string, string>;
}

export interface ShearRelaxationDatasetContent {
  material_state_id: string;
  material_state_revision_id: string;
  test_run_id: string;
  test_run_revision_id: string;
  raw_asset_id: string;
  raw_artifact_id: string;
  data_artifact_id: string;
  data_sha256: string;
  representation: "raw" | "normalized" | "processed";
  source_dataset_revision_id: string | null;
  processing_run_id: string | null;
  point_count: number;
  time_column: string;
  shear_modulus_column: string;
  time_original_unit: "s" | "ms" | "min" | "h";
  shear_modulus_original_unit: "Pa" | "kPa" | "MPa" | "GPa";
  normalized_time_unit: "s";
  normalized_shear_modulus_unit: "Pa";
  importer_id: string;
  importer_version: string;
}

export interface ShearRelaxationDatasetResponse {
  dataset_id: string;
  material_state_id: string;
  current_revision: RevisionMetadata & { content: ShearRelaxationDatasetContent };
  links: Record<string, string>;
}

export interface ShearRelaxationCurvePreview {
  dataset_id: string;
  dataset_revision_id: string;
  representation: "raw" | "normalized" | "processed";
  point_count: number;
  returned_point_count: number;
  time_unit: string;
  shear_modulus_unit: string;
  points: Array<{ time: number; shear_modulus: number }>;
}

export interface ShearRelaxationProcessingRecipeResponse {
  recipe_id: string;
  current_revision: RevisionMetadata;
  content: {
    recipe_kind: "reference_shear_relaxation_inclusive_time_crop";
    recipe_label: string;
    minimum_time_s: number;
    maximum_time_s: number;
    input_schema_ref: string;
    output_schema_ref: string;
    boundary_policy: "select_observed_points_inclusive_no_interpolation";
  };
  links: Record<string, string>;
}

export interface ShearRelaxationProcessingRunResponse {
  processing_run_id: string;
  classification: DataClassification;
  recipe_id: string;
  recipe_revision_id: string;
  input_dataset_id: string;
  input_dataset_revision_id: string;
  status: "executing" | "succeeded" | "failed";
  input_point_count: number;
  output_point_count: number | null;
  removed_point_count: number | null;
  result_artifact_id: string | null;
  result_sha256: string | null;
  output_dataset_id: string | null;
  output_dataset_revision_id: string | null;
  failure_code: string | null;
  started_at: string;
  ended_at: string | null;
  links: Record<string, string>;
}

export interface ViscoelasticSelectionMember {
  ordinal: number;
  dataset_id: string;
  dataset_revision_id: string;
  test_run_id: string;
  test_run_revision_id: string;
  temperature_k: number;
  outlier_status: "not_assessed";
}

export interface ViscoelasticSelectionResponse {
  selection_id: string;
  current_revision: RevisionMetadata;
  content: {
    selection_label: string;
    material_state_id: string;
    material_state_revision_id: string;
    member_count: number;
    temperature_count: number;
    members: ViscoelasticSelectionMember[];
  };
  links: Record<string, string>;
}

export type ViscoelasticShiftMethod = "manual" | "wlf_fit" | "arrhenius_fit";

export interface ViscoelasticMasterPlanResponse {
  plan_id: string;
  current_revision: RevisionMetadata;
  content: {
    plan_label: string;
    selection_id: string;
    selection_revision_id: string;
    reference_temperature_k: number;
    grid_point_count: number;
    shift_method: ViscoelasticShiftMethod;
    manual_shift_factors: Array<{ temperature_k: number; log10_a_t: number }>;
    interpolation: "piecewise_linear_log_time";
    domain_policy: "common_intersection_no_extrapolation";
    reduced_time_convention: "time_divided_by_a_t";
  };
  links: Record<string, string>;
}

export interface ViscoelasticShiftFactor {
  temperature_k: number;
  log10_a_t: number;
  source: "reference" | "manual" | "wlf_fit" | "arrhenius_fit";
  observed_log10_a_t: number | null;
  residual_log10_a_t: number | null;
  alignment_rmse_pa: number | null;
}

export interface ViscoelasticMasterRunResponse {
  processing_run_id: string;
  classification: DataClassification;
  plan_id: string;
  plan_revision_id: string;
  selection_id: string;
  selection_revision_id: string;
  status: "executing" | "succeeded" | "failed";
  source_curve_count: number;
  temperature_count: number;
  aligned_row_count: number | null;
  statistics_row_count: number | null;
  master_row_count: number | null;
  aligned_dataset_id: string | null;
  aligned_dataset_revision_id: string | null;
  statistics_dataset_id: string | null;
  statistics_dataset_revision_id: string | null;
  master_dataset_id: string | null;
  master_dataset_revision_id: string | null;
  wlf_c1: number | null;
  wlf_c2_k: number | null;
  arrhenius_activation_energy_j_per_mol: number | null;
  shift_factors: ViscoelasticShiftFactor[];
  failure_code: string | null;
  started_at: string;
  ended_at: string | null;
  links: Record<string, string>;
}

export interface ViscoelasticMasterPreviewResponse {
  run: ViscoelasticMasterRunResponse;
  reference_temperature_k: number;
  aligned_curves: Array<{
    member_ordinal: number;
    dataset_revision_id: string;
    test_run_revision_id: string;
    temperature_k: number;
    outlier_status: "not_assessed";
    points: Array<{ time_s: number; shear_modulus_pa: number }>;
  }>;
  temperature_statistics: Array<{
    temperature_k: number;
    replicate_count: number;
    points: Array<{
      time_s: number;
      replicate_count: number;
      mean_shear_modulus_pa: number;
      sample_standard_deviation_pa: number | null;
      median_shear_modulus_pa: number;
      minimum_shear_modulus_pa: number;
      maximum_shear_modulus_pa: number;
    }>;
  }>;
  master_curve: Array<{
    reduced_time_s: number;
    contributing_curve_count: number;
    mean_shear_modulus_pa: number;
    sample_standard_deviation_pa: number | null;
    minimum_shear_modulus_pa: number;
    maximum_shear_modulus_pa: number;
  }>;
  policy: {
    interpolation: "piecewise_linear_log_time";
    domain: "common_intersection_no_extrapolation";
    reduced_time: "time_divided_by_a_t";
  };
}

export interface PronyParameterPlan {
  name: string;
  unit: string;
  lower: number;
  initial: number;
  upper: number;
  transform: "none" | "log";
}

export interface PronyCalibrationPlanResponse {
  prony_calibration_plan_id: string;
  current_revision: RevisionMetadata & {
    content: {
      plan_kind: "reference_two_term_shear_relaxation_prony";
      plan_label: string;
      input_dataset_id: string;
      input_dataset_revision_id: string;
      baseline_model_id: string;
      baseline_model_revision_id: string;
      total_g_ratio: PronyParameterPlan;
      fast_term_fraction: PronyParameterPlan;
      fast_relaxation_time_s: PronyParameterPlan;
      slow_relaxation_time_s: PronyParameterPlan;
      normalization_modulus_pa: number;
      multistart_count: number;
      random_seed: number;
      optimizer_adapter_id: string;
      non_production: true;
    };
  };
  links: Record<string, string>;
}

export interface PronyCalibrationCandidateResponse {
  prony_calibration_candidate_id: string;
  attempt_ordinal: number;
  status: "converged" | "nonconverged";
  candidate_sha256: string;
  total_g_ratio: number;
  fast_term_fraction: number;
  fast_g_ratio: number;
  slow_g_ratio: number;
  fast_relaxation_time_s: number;
  slow_relaxation_time_s: number;
  objective_total: number;
  residual_root_mean_square_pa: number;
  residual_mean_pa: number;
  convergence_reason: string;
  function_evaluations: number;
  optimality: number;
  parameter_at_bound: boolean;
  identifiability_status: "full_rank" | "rank_deficient";
  uncertainty_status: "not_assessed_reference";
  diagnostics_artifact_id: string;
  diagnostics_point_count: number;
  links: Record<string, string>;
}

export interface PronyCalibrationRunResponse {
  prony_calibration_run_id: string;
  status: "succeeded";
  plan_id: string;
  plan_revision_id: string;
  input_dataset_id: string;
  input_dataset_revision_id: string;
  baseline_model_id: string;
  baseline_model_revision_id: string;
  environment_digest: string;
  attempt_count: number;
  candidate_count: number;
  candidates: PronyCalibrationCandidateResponse[];
  links: Record<string, string>;
}

export interface PronyCalibrationDiagnosticsResponse {
  candidate_id: string;
  points: Array<{
    point_ordinal: number;
    time_s: number;
    observed_shear_modulus_pa: number;
    predicted_shear_modulus_pa: number;
    residual_pa: number;
  }>;
}

export interface PronyCandidateSelectionResponse {
  prony_candidate_selection_id: string;
  current_revision: RevisionMetadata & {
    content: {
      selection_label: string;
      prony_calibration_run_id: string;
      prony_calibration_candidate_id: string;
      candidate_sha256: string;
      baseline_model_id: string;
      baseline_model_revision_id: string;
      selection_reason: string;
      selection_decision: "accepted_for_linear_prony_ir_revision";
      non_production: true;
    };
  };
  links: Record<string, string>;
}

export interface ReferenceLinearElasticCalibrationPlanContent {
  plan_kind: "reference_uniaxial_linear_elasticity";
  plan_label: string;
  selection_id: string;
  selection_revision_id: string;
  material_model_id: string;
  material_model_revision_id: string;
  model_family_id: string;
  model_schema_version: string;
  model_schema_digest: string;
  test_mode: "reference_uniaxial_tension";
  evaluator_id: string;
  evaluator_version: string;
  evaluation_mode: "closed_form_curve";
  calibrator_id: string;
  calibrator_version: string;
  parameter_name: "youngs_modulus_pa";
  youngs_modulus_lower_bound_pa: number;
  youngs_modulus_initial_value_pa: number;
  youngs_modulus_upper_bound_pa: number;
  normalization_stress_scale_pa: number;
  point_weighting: "uniform_point_weight";
  objective_aggregation: "mean_normalized_squared_residual";
  x_domain_policy: "all_observed_points";
  missing_data_policy: "reject";
  multistart_count: number;
  random_seed: number;
  non_production: true;
}

export interface CalibrationPlanRevision extends RevisionMetadata {
  content: ReferenceLinearElasticCalibrationPlanContent;
}

export interface CalibrationPlanResponse {
  calibration_plan_id: string;
  current_revision: CalibrationPlanRevision;
  links: Record<string, string>;
}

export interface CalibrationAttemptResponse {
  calibration_attempt_id: string;
  calibration_run_id: string;
  attempt_ordinal: number;
  initial_youngs_modulus_pa: number;
  random_seed: number;
  status: "executing" | "succeeded" | "failed";
  candidate_id: string | null;
  failure_code: string | null;
  started_at: string;
  ended_at: string | null;
}

export interface CalibrationCandidateResponse {
  calibration_candidate_id: string;
  calibration_run_id: string;
  calibration_attempt_id: string;
  attempt_ordinal: number;
  status: "converged" | "nonconverged" | "failed";
  candidate_sha256: string;
  youngs_modulus_pa: number;
  objective_total: number;
  residual_root_mean_square_pa: number;
  residual_mean_pa: number;
  bound_sticking: boolean;
  convergence_reason: string;
  identifiability_status: string;
  uncertainty_status: string;
  diagnostics_artifact_id: string;
  diagnostics_sha256: string;
  diagnostics_point_count: number;
  created_at: string;
  created_by: string;
  links: Record<string, string>;
}

export interface CalibrationRunResponse {
  calibration_run_id: string;
  classification: DataClassification;
  calibration_plan_id: string;
  calibration_plan_revision_id: string;
  selection_id: string;
  selection_revision_id: string;
  dataset_id: string;
  dataset_revision_id: string;
  material_model_id: string;
  material_model_revision_id: string;
  execution_mode: "reference_inline";
  reproducibility_level: string;
  environment_digest: string;
  status: "executing" | "succeeded" | "failed";
  attempt_count: number;
  candidate_count: number;
  failure_code: string | null;
  change_reason: string;
  started_at: string;
  ended_at: string | null;
  created_by: string;
  request_id: string;
  trace_id: string;
  attempts: CalibrationAttemptResponse[];
  candidates: CalibrationCandidateResponse[];
  links: Record<string, string>;
}

export interface CalibrationDiagnosticPoint {
  engineering_strain: number;
  observed_engineering_stress_pa: number;
  predicted_engineering_stress_pa: number;
  residual_engineering_stress_pa: number;
  normalized_residual: number;
}

export interface CalibrationDiagnosticPreview {
  calibration_candidate_id: string;
  point_count: number;
  returned_point_count: number;
  sampled: boolean;
  points: CalibrationDiagnosticPoint[];
}

export interface VoceParameterResponse {
  name: "sigma_0_pa" | "q_pa" | "b";
  unit: "Pa" | "1";
  lower: number;
  initial: number;
  upper: number;
  scale: number;
  transform: "none";
}

export interface VoceCalibrationPlanResponse {
  voce_calibration_plan_id: string;
  current_revision: RevisionMetadata & {
    content: {
      plan_kind: "reference_multi_curve_voce_saturation";
      plan_label: string;
      calibration_input_scope_id: string;
      calibration_input_scope_revision_id: string;
      material_state_id: string;
      material_state_revision_id: string;
      property_set_id: string;
      property_set_revision_id: string;
      youngs_modulus_pa: number;
      parameters: VoceParameterResponse[];
      normalization_stress_scale_pa: number;
      multistart_count: number;
      random_seed: number;
      maximum_function_evaluations: number;
      ftol: number;
      xtol: number;
      gtol: number;
      model_family_id: string;
      test_mode_adapter_id: string;
      evaluator_id: string;
      objective_engine_id: string;
      optimizer_adapter_id: string;
      evaluation_mode: "closed_form_curve";
      residual_definition: string;
      specimen_weighting: "equal_specimen";
      point_weighting: "uniform_within_specimen";
      objective_aggregation: string;
      x_domain_policy: string;
      missing_data_policy: "reject";
      optimizer_method: "trf";
      rng_algorithm: "numpy.random.PCG64";
      non_production: true;
    };
  };
}

export interface VoceCalibrationCandidateResponse {
  voce_calibration_candidate_id: string;
  attempt_ordinal: number;
  status: "converged" | "nonconverged";
  candidate_sha256: string;
  sigma_0_pa: number;
  q_pa: number;
  b: number;
  objective_total: number;
  residual_root_mean_square_pa: number;
  residual_mean_pa: number;
  bound_sticking_parameters: string[];
  convergence_status_code: number;
  convergence_reason: string;
  function_evaluations: number;
  jacobian_evaluations: number | null;
  optimality: number;
  warnings: string[];
  identifiability_status: string;
  uncertainty_status: string;
  diagnostics_artifact_id: string;
  diagnostics_sha256: string;
  diagnostics_point_count: number;
  objective_terms: Array<{
    member_ordinal: number;
    dataset_id: string;
    dataset_revision_id: string;
    point_count: number;
    mean_normalized_squared_residual: number;
  }>;
}

export interface VoceCalibrationRunResponse {
  voce_calibration_run_id: string;
  classification: DataClassification;
  plan_id: string;
  plan_revision_id: string;
  calibration_input_scope_id: string;
  calibration_input_scope_revision_id: string;
  property_set_id: string;
  property_set_revision_id: string;
  source_curve_count: number;
  execution_mode: "reference_inline_scipy";
  reproducibility_level: "R3";
  environment_digest: string;
  status: "executing" | "succeeded" | "failed";
  attempt_count: number;
  candidate_count: number;
  failure_code: string | null;
  change_reason: string;
  started_at: string;
  ended_at: string | null;
  attempts: Array<{
    voce_calibration_attempt_id: string;
    attempt_ordinal: number;
    initial_sigma_0_pa: number;
    initial_q_pa: number;
    initial_b: number;
    random_seed: number;
    status: "executing" | "succeeded" | "failed";
    candidate_id: string | null;
    failure_code: string | null;
    started_at: string;
    ended_at: string | null;
  }>;
  candidates: VoceCalibrationCandidateResponse[];
}

export interface VoceCalibrationDiagnosticPreview {
  calibration_candidate_id: string;
  point_count: number;
  returned_point_count: number;
  sampled: boolean;
  points: Array<{
    member_ordinal: number;
    dataset_revision_id: string;
    point_ordinal: number;
    true_plastic_strain: number;
    observed_true_yield_stress_pa: number;
    predicted_true_yield_stress_pa: number;
    residual_true_yield_stress_pa: number;
    normalized_residual: number;
    effective_weight: number;
  }>;
}

export interface VoceCandidateSelectionResponse {
  voce_candidate_selection_id: string;
  current_revision: RevisionMetadata & {
    content: {
      selection_label: string;
      voce_calibration_run_id: string;
      voce_calibration_candidate_id: string;
      candidate_sha256: string;
      selection_reason: string;
      selection_decision: "accepted_for_tabulated_ir_projection";
      non_production: true;
    };
  };
  links: Record<string, string>;
}

export interface VoceHoldoutPlanResponse {
  voce_holdout_plan_id: string;
  current_revision: RevisionMetadata & {
    content: {
      plan_label: string;
      material_model_id: string;
      material_model_revision_id: string;
      holdout_dataset_id: string;
      holdout_dataset_revision_id: string;
      metric_profile_id: string;
      threshold_profile_id: string;
      relative_rmse_threshold: 0.05;
      overlap_policy: "reject_any_calibration_scope_dataset_or_test_run_overlap";
      evaluation_mode: "closed_form_curve";
      solver_execution: "not_used";
      non_production: true;
    };
  };
  links: Record<string, string>;
}

export interface VoceHoldoutPoint {
  source_point_ordinal: number;
  true_plastic_strain: number;
  observed_true_yield_stress_pa: number;
  predicted_true_yield_stress_pa: number;
  residual_true_yield_stress_pa: number;
}

export interface VoceHoldoutResultResponse {
  voce_holdout_result_id: string;
  voce_holdout_run_id: string;
  plan_id: string;
  plan_revision_id: string;
  material_model_id: string;
  material_model_revision_id: string;
  calibration_input_scope_id: string;
  calibration_input_scope_revision_id: string;
  voce_calibration_run_id: string;
  voce_calibration_candidate_id: string;
  voce_candidate_selection_id: string;
  voce_candidate_selection_revision_id: string;
  holdout_dataset_id: string;
  holdout_dataset_revision_id: string;
  holdout_test_run_id: string;
  holdout_test_run_revision_id: string;
  holdout_independence: "disjoint_dataset_and_test_run";
  source_data_artifact_id: string;
  source_data_sha256: string;
  comparison_artifact_id: string;
  comparison_sha256: string;
  comparison_point_count: number;
  root_mean_squared_error_pa: number;
  relative_root_mean_squared_error: number;
  normalization_stress_scale_pa: number;
  characterized_max_true_plastic_strain: number;
  relative_rmse_threshold: 0.05;
  verdict: "passed" | "failed";
  evaluation_mode: "closed_form_curve";
  solver_execution: "not_used";
  non_production: true;
  created_at: string;
  created_by: string;
  points: VoceHoldoutPoint[];
  links: Record<string, string>;
}

export interface CalibrationCandidateSelectionContent {
  selection_label: string;
  calibration_run_id: string;
  calibration_candidate_id: string;
  candidate_sha256: string;
  selection_reason: string;
  selection_decision: "accepted_for_reference_ir_promotion";
  domain_acceptance_status: "accepted_by_human_for_reference_ir_promotion";
  non_production: true;
}

export interface CalibrationCandidateSelectionRevision extends RevisionMetadata {
  content: CalibrationCandidateSelectionContent;
}

export interface CalibrationCandidateSelectionResponse {
  calibration_candidate_selection_id: string;
  current_revision: CalibrationCandidateSelectionRevision;
  links: Record<string, string>;
}

export interface CalibrationCandidateSelectionPromotionResponse {
  calibration_candidate_selection_id: string;
  calibration_candidate_selection_revision_id: string;
  material_model: MaterialModelResponse;
}


export interface TabulatedPlasticityHardeningReference {
  artifact_id: string;
  sha256: string;
  schema_ref: string;
  point_count: number;
  independent_quantity: "true_plastic_strain";
  independent_unit: "1";
  dependent_quantity: "true_yield_stress";
  dependent_unit: "Pa";
}

export interface TabulatedPlasticityContent {
  model_family_id: string;
  model_schema_version: string;
  model_schema_digest: string;
  material_id: string;
  material_revision_id: string;
  material_state_id: string;
  material_state_revision_id: string;
  property_set_id: string;
  property_set_revision_id: string;
  source_dataset_id: string | null;
  source_dataset_revision_id: string | null;
  density_kg_per_m3: number;
  youngs_modulus_pa: number;
  poisson_ratio: number;
  initial_yield_stress_pa: number;
  hardening_curve: TabulatedPlasticityHardeningReference;
  source_point_count: number | null;
  pre_yield_excluded_point_count: number | null;
  post_necking_excluded_point_count: number | null;
  necking_source_point_index: number | null;
  transformation_profile_id: string;
  transformation_profile_version: string;
  transformation_profile_digest: string;
  necking_engineering_strain: number | null;
  characterized_max_true_plastic_strain: number;
  extension_max_true_plastic_strain: number;
  post_necking_extension_policy:
    | "approved_constant_true_stress"
    | "selected_fitted_bounded_extrapolation";
  post_necking_approximation_acknowledged: true;
  applicability: Applicability;
  reference_temperature_k: number;
  calibration_projection: {
    input_scope_id: string;
    input_scope_revision_id: string;
    plan_id: string;
    plan_revision_id: string;
    run_id: string;
    candidate_id: string;
    candidate_sha256: string;
    selection_id: string;
    selection_revision_id: string;
    sigma_0_pa: number;
    q_pa: number;
    b: number;
    sampling_point_count: number;
  } | null;
  processing_projection: {
    output_id: string;
    output_revision_id: string;
    output_sha256: string;
    source_test_data_id: string;
    source_test_data_revision_id: string;
    mapping_profile_id: string;
    mapping_profile_revision_id: string;
    candidate_families: string[];
    primary_family: string;
    secondary_family: string;
    primary_weight: number;
    fit_minimum_true_plastic_strain: number;
    recipe_batch?: {
      processing_recipe: { id: string; revision_id: string; sha256: string };
      processing_batch_id: string;
      batch_member_id: string;
      batch_attempt_id: string;
      batch_attempt_no: number;
    } | null;
  } | null;
  non_production: true;
}

export interface TabulatedPlasticityProvenanceSummary {
  entity_type: "modeling.material_model.revision";
  reference_type: "modeling.material_model.revision";
  revision_id: string;
  content_sha256: string;
  based_on_revision_id: string | null;
  source_property_set_revision_id: string;
  source_dataset_revision_id: string | null;
  source_voce_selection_revision_id: string | null;
  source_processing_output_revision_id: string | null;
  hardening_curve_artifact_id: string;
  hardening_curve_sha256: string;
  transformation_profile_digest: string;
  recorded_at: string;
  recorded_by: string;
}

export interface TabulatedPlasticityRevision extends RevisionMetadata {
  content: TabulatedPlasticityContent;
  ir: Record<string, unknown>;
  provenance: TabulatedPlasticityProvenanceSummary;
}

export interface TabulatedPlasticityModelResponse {
  material_model_id: string;
  material_state_id: string;
  current_revision: TabulatedPlasticityRevision;
  links: Record<string, string>;
}

export type BulkRelaxationStatus = "characterized" | "not_characterized";

export interface LinearViscoelasticPronyTerm {
  ordinal: number;
  g_ratio: number;
  k_ratio: number;
  relaxation_time_s: number;
}

export interface LinearViscoelasticProcessingEvidence {
  processing_output: { id: string; revision_id: string; sha256: string };
  source_test_data: { id: string; revision_id: string };
  mapping_profile: { id: string; revision_id: string };
  selection_mode: "automatic_bic" | "manual";
  selected_term_count: number;
  normalized_rmse: number;
  bic: number;
  fitted_instantaneous_shear_modulus_pa: number;
  catalog_instantaneous_shear_modulus_pa: number;
  instantaneous_modulus_relative_mismatch: number;
  acknowledged_maximum_relative_mismatch: number;
  recipe_batch?: {
    processing_recipe: { id: string; revision_id: string; sha256: string };
    processing_batch_id: string;
    batch_member_id: string;
    batch_attempt_id: string;
    batch_attempt_no: number;
  } | null;
}

export interface LinearViscoelasticModelResponse {
  material_model_id: string;
  material_state_id: string;
  current_revision: RevisionMetadata & {
    content: {
      model_family_id: string;
      model_schema_version: "1.0.0" | "1.1.0" | "1.2.0" | "1.3.0";
      model_schema_digest: string;
      material_id: string;
      material_revision_id: string;
      material_state_id: string;
      material_state_revision_id: string;
      property_set_id: string;
      property_set_revision_id: string;
      density_kg_per_m3: number;
      youngs_modulus_pa: number;
      poisson_ratio: number;
      elastic_moduli_convention: "instantaneous";
      bulk_relaxation_status: BulkRelaxationStatus;
      terms: LinearViscoelasticPronyTerm[];
      reference_temperature_k: number;
      non_production: true;
      prony_promotion_evidence?: Record<string, unknown> | null;
      processing_promotion_evidence?: LinearViscoelasticProcessingEvidence | null;
    };
    ir: Record<string, unknown>;
  };
  links: Record<string, string>;
}

export interface LinearViscoelasticResponsePoint {
  time_s: number;
  shear_modulus_pa: number;
  bulk_modulus_pa: number;
}

export interface LinearViscoelasticResponse {
  material_model_id: string;
  material_model_revision_id: string;
  elastic_moduli_convention: "instantaneous";
  time_unit: "s";
  modulus_unit: "Pa";
  points: LinearViscoelasticResponsePoint[];
}

export interface LinearViscoelasticMappingReport {
  material_model_id: string;
  material_model_revision_id: string;
  model_schema_digest: string;
  target: ExportTarget;
  items: MappingItem[];
  exporter_id: string;
  exporter_version: string;
  exporter_digest: string;
  mapping_report_sha256: string;
  exportable: boolean;
  non_production: true;
}

export interface LinearViscoelasticCardResponse {
  solver_card_id: string;
  material_model_id: string;
  target: ExportTarget;
  solver_material_id: number;
  material_name: string;
  current_revision: RevisionMetadata & {
    content: {
      material_model_id: string;
      material_model_revision_id: string;
      bulk_relaxation_status: BulkRelaxationStatus;
      terms: LinearViscoelasticPronyTerm[];
      mapping_statuses: Record<string, MappingStatus>;
      card_sha256: string;
      non_production: true;
    };
  };
  links: { self: string; preview: string; download: string };
}

export interface OgdenPronyModelResponse {
  material_model_id: string;
  material_state_id: string;
  current_revision: RevisionMetadata & {
    content: {
      model_family_id: string;
      material_state_revision_id: string;
      property_set_revision_id: string;
      density_kg_per_m3: number;
      ogden_terms: Array<{ ordinal: number; mu_pa: number; alpha: number }>;
      prony_terms: Array<{
        ordinal: number;
        g_ratio: number;
        k_ratio: number;
        relaxation_time_s: number;
      }>;
      moduli_convention: "instantaneous";
      volumetric_response: "incompressible";
      promotion_evidence?: {
        selection_id: string;
        selection_revision_id: string;
        calibration_run_id: string;
        calibration_candidate_id: string;
        candidate_sha256: string;
        diagnostics_artifact_id: string;
        diagnostics_sha256: string;
        promoted_from_model_revision_id: string;
      };
      non_production: true;
    };
  };
  links: Record<string, string>;
}

export interface OgdenPronyRevisionListResponse {
  material_model_id: string;
  items: OgdenPronyModelResponse["current_revision"][];
}

export interface OgdenCandidateSelectionResponse {
  ogden_candidate_selection_id: string;
  current_revision: RevisionMetadata & {
    content: {
      selection_label: string;
      ogden_calibration_run_id: string;
      ogden_calibration_candidate_id: string;
      candidate_sha256: string;
      diagnostics_artifact_id: string;
      diagnostics_sha256: string;
      baseline_model_id: string;
      baseline_model_revision_id: string;
      selection_reason: string;
      selection_decision: "accepted_for_ogden_prony_ir_revision";
      non_production: true;
    };
  };
  links: Record<string, string>;
}

export type ScientificProfileFamily =
  | "steel_voce"
  | "polymer_linear_prony"
  | "elastomer_ogden_prony";

export interface OgdenScientificParameters {
  mu_initial_pa: number;
  mu_lower_pa: number;
  mu_upper_pa: number;
  mu_scale_pa: number;
  alpha_initial: number;
  alpha_lower: number;
  alpha_upper: number;
  alpha_scale: number;
  uniaxial_weight: number;
  planar_weight: number;
  biaxial_weight: number;
}

export interface ScientificProfileResponse {
  scientific_profile_id: string;
  current_revision: RevisionMetadata & {
    content: {
      profile_label: string;
      family: ScientificProfileFamily;
      model_family_id: string;
      approval_status: "reference_unapproved" | "domain_approved";
      optimizer: "scipy_least_squares_trf";
      residual_definition: "normalized_weighted_least_squares";
      aggregation_order: "point_then_curve_then_mode";
      missing_data_policy: "reject";
      holdout_policy: "explicit_disjoint";
      uncertainty_policy: "jacobian_covariance_or_not_estimable";
      multistart_count: number;
      seed: number;
      status_note: string;
      parameters: Record<string, number | string>;
    };
  };
  links: Record<string, string>;
}

export type OgdenCalibrationRole = "calibration" | "holdout";
export type OgdenTestMode = "uniaxial_tension" | "planar_tension" | "biaxial_tension";

export interface OgdenCalibrationMember {
  ordinal: number;
  role: OgdenCalibrationRole;
  test_mode: OgdenTestMode;
  dataset_id: string;
  dataset_revision_id: string;
  weight: number;
}

export interface OgdenCalibrationPlanResponse {
  ogden_calibration_plan_id: string;
  current_revision: RevisionMetadata & {
    content: {
      plan_label: string;
      scientific_profile_id: string;
      scientific_profile_revision_id: string;
      material_state_id: string;
      material_state_revision_id: string;
      baseline_model_id: string;
      baseline_model_revision_id: string;
      members: OgdenCalibrationMember[];
      evaluator: "one_term_incompressible_ogden_nominal";
      objective: "normalized_weighted_least_squares";
      aggregation_order: "point_then_curve_then_mode";
      holdout_policy: "explicit_disjoint";
      maximum_function_evaluations: 5000;
      non_production: true;
    };
  };
  links: Record<string, string>;
}

export interface OgdenCalibrationCandidateResponse {
  ogden_calibration_candidate_id: string;
  attempt_ordinal: number;
  status: "converged" | "nonconverged";
  candidate_sha256: string;
  initial_mu_pa: number;
  initial_alpha: number;
  mu_pa: number;
  alpha: number;
  objective_total: number;
  objective_by_mode: Record<OgdenTestMode, number>;
  calibration_rmse_pa: number;
  calibration_normalized_rmse: number;
  holdout_rmse_pa: number | null;
  holdout_normalized_rmse: number | null;
  convergence_status_code: number;
  convergence_reason: string;
  function_evaluations: number;
  jacobian_evaluations: number | null;
  optimality: number;
  parameter_at_bound: boolean;
  jacobian_rank: number;
  jacobian_condition_number: number | null;
  identifiability_status: "full_rank" | "rank_deficient";
  uncertainty_status:
    | "estimated_jacobian_covariance"
    | "not_estimable_rank_deficient"
    | "not_estimable_insufficient_dof"
    | "not_estimable_nonfinite";
  mu_standard_error_pa: number | null;
  alpha_standard_error: number | null;
  mu_confidence_interval_pa: [number, number] | null;
  alpha_confidence_interval: [number, number] | null;
  warnings: string[];
  diagnostics_artifact_id: string;
  diagnostics_point_count: number;
  links: Record<string, string>;
}

export type HyperelasticFamily = "neo_hookean" | "mooney_rivlin" | "yeoh" | "ogden_1";

export interface HyperelasticFamilyCandidateResponse {
  hyperelastic_family_candidate_id: string;
  family: HyperelasticFamily;
  parameters: Array<{ name: string; value: number; unit: "Pa" | "1" }>;
  objective_total: number;
  objective_by_mode: Record<OgdenTestMode, number>;
  calibration_normalized_rmse: number;
  holdout_normalized_rmse: number | null;
  function_evaluations: number;
  convergence_reason: string;
  stability_status: "monotonic_on_fitted_domain" | "nonmonotonic";
  warnings: string[];
  candidate_sha256: string;
  diagnostics_artifact_id: string | null;
  diagnostics_point_count: number;
  links: Record<string, string>;
}

export interface OgdenCalibrationRunResponse {
  ogden_calibration_run_id: string;
  status: "succeeded";
  plan_id: string;
  plan_revision_id: string;
  scientific_profile_id: string;
  scientific_profile_revision_id: string;
  material_state_id: string;
  material_state_revision_id: string;
  baseline_model_id: string;
  baseline_model_revision_id: string;
  environment_digest: string;
  calibration_curve_count: number;
  holdout_curve_count: number;
  test_mode_count: number;
  attempt_count: number;
  candidate_count: number;
  candidates: OgdenCalibrationCandidateResponse[];
  family_candidate_count: number;
  family_candidates: HyperelasticFamilyCandidateResponse[];
  links: Record<string, string>;
}

export interface OgdenDiagnosticPoint {
  member_ordinal: number;
  role: OgdenCalibrationRole;
  test_mode: OgdenTestMode;
  dataset_id: string;
  dataset_revision_id: string;
  point_ordinal: number;
  engineering_strain: number;
  stretch: number;
  observed_nominal_stress_pa: number;
  predicted_nominal_stress_pa: number;
  residual_pa: number;
  normalized_residual: number;
  effective_weight: number;
}

export interface OgdenDiagnosticsResponse {
  candidate_id: string;
  points: OgdenDiagnosticPoint[];
}

export interface HyperelasticDiagnosticsResponse {
  candidate_id: string;
  points: Array<OgdenDiagnosticPoint & { family: HyperelasticFamily }>;
}

export interface NeutralMaterialResponse {
  neutral_material_id: string;
  neutral_material_revision_id: string;
  revision_no: number;
  content_hash: string;
  document_artifact: { artifact_id: string; sha256: string };
  document: {
    document_type: "cmp.neutral-material";
    schema_version: "1.0.0";
    document_id: string;
    content_sha256: string;
    sources: {
      material?: { id: string; revision_id: string };
      material_state?: { id: string; revision_id: string };
      property_set?: { id: string; revision_id: string };
      calibration_plan?: { id: string; revision_id: string };
      scientific_profile?: { id: string; revision_id: string };
      datasets: Array<{
        dataset: { id: string; revision_id: string };
        role: OgdenCalibrationRole | "processing_input";
        test_mode: OgdenTestMode | "stress_relaxation";
        source_kind?: "governed_dataset" | "test_data_document" | "shear_relaxation_dataset";
      }>;
    };
    curve_stages: Array<{
      stage: "normalized" | "processed" | "fitted" | "extrapolated" | "residual";
      dataset_revision_id: string;
      test_mode: OgdenTestMode | "stress_relaxation";
      x: number[];
      y: number[];
    }>;
    candidate_selection: {
      calibration_run_id?: string;
      candidate_id?: string;
      candidate_sha256?: string;
      diagnostics_artifact_id?: string;
      diagnostics_sha256?: string;
      reason: string;
      objective_total?: number;
      calibration_normalized_rmse?: number;
      holdout_normalized_rmse?: number | null;
      stability_status?: string;
      warnings: string[];
      kind?: "processing_output_selection" | "prony_processing_output_selection";
      processing_output?: { id: string; revision_id: string };
    };
    material_model_ir: {
      model: { id: string; revision_id: string };
      schema_id: string;
      schema_version: string;
      model_family?: "hyperelastic" | "isotropic_tabulated_plasticity" | "generalized_maxwell";
      constitutive_model: {
        family: HyperelasticFamily | "isotropic_tabulated_plasticity" | "generalized_maxwell";
        parameters: Record<string, { value: number; unit: "Pa" | "1" }>;
      };
      maturity: "reference";
      non_production: true;
    };
    applicability:
      | { engineering_strain: { minimum: number; maximum: number; unit: "1" } }
      | { time: { minimum: number; maximum: number; unit: "s" } };
    validation: { status: string };
  };
  links: { self: string; download: string };
}

export interface NeutralHyperelasticMappingReport {
  mapping_report_sha256: string;
  exportable: boolean;
  report: {
    neutral_material_id: string;
    neutral_material_revision_id: string;
    neutral_material_sha256: string;
    model_family?: "hyperelastic" | "isotropic_tabulated_plasticity" | "generalized_maxwell";
    model_schema_digest: string;
    family: HyperelasticFamily | "isotropic_tabulated_plasticity" | "generalized_maxwell";
    target: ExportTarget;
    items: MappingItem[];
    exporter: {
      id: string;
      version: string;
      digest: string;
      documentation_url: string;
    };
    non_production: true;
  };
}

export interface NeutralHyperelasticSolverCardResponse {
  solver_card_id: string;
  neutral_material_id: string;
  target: ExportTarget;
  current_revision: RevisionMetadata & {
    content: {
      neutral_material_id: string;
      neutral_material_revision_id: string;
      neutral_material_sha256: string;
      model_family?: "hyperelastic" | "isotropic_tabulated_plasticity" | "generalized_maxwell";
      model_schema_digest: string;
      family: HyperelasticFamily | "isotropic_tabulated_plasticity" | "generalized_maxwell";
      target: ExportTarget;
      solver_material_id: number;
      material_name: string;
      density_kg_per_m3: number;
      constitutive_model: Record<string, unknown>;
      applicability:
        | { engineering_strain: { minimum: number; maximum: number; unit: "1" } }
        | { time: { minimum: number; maximum: number; unit: "s" } };
      mapping_statuses: Record<string, MappingStatus>;
      mapping_report_sha256: string;
      card_sha256: string;
      exporter: { id: string; version: string; digest: string };
      non_production: true;
    };
  };
  links: {
    self: string;
    mapping_report: string;
    preview: string;
    download: string;
  };
}

export interface OgdenPronyMappingResponse {
  mapping_report_sha256: string;
  exportable: boolean;
  report: {
    items: MappingItem[];
    exporter: { id: string; version: string; digest: string };
    target: ExportTarget;
    non_production: true;
  };
}

export interface OgdenPronyCardResponse {
  solver_card_id: string;
  material_model_id: string;
  target: ExportTarget;
  current_revision: RevisionMetadata & {
    content: {
      material_name: string;
      card_sha256: string;
      mapping_statuses: Record<string, MappingStatus>;
      non_production: true;
    };
  };
  links: { self: string; preview: string; download: string };
}

export interface HardeningCurvePoint {
  true_plastic_strain: number;
  true_yield_stress_pa: number;
  origin:
    | "catalog_yield_anchor"
    | "pre_necking_observation"
    | "calibrated_voce_sample"
    | "approved_constant_extension";
}

export interface HardeningCurveResponse {
  material_model_id: string;
  material_model_revision_id: string;
  artifact_id: string;
  artifact_sha256: string;
  points: HardeningCurvePoint[];
}

export interface ElastoplasticCardContent {
  material_model_id: string;
  material_model_revision_id: string;
  model_schema_digest: string;
  target: ExportTarget;
  solver_material_id: number;
  material_name: string;
  density_kg_per_m3: number;
  youngs_modulus_pa: number;
  poisson_ratio: number;
  initial_yield_stress_pa: number;
  hardening_curve_artifact_id: string;
  hardening_curve_sha256: string;
  hardening_curve_point_count: number;
  extension_max_true_plastic_strain: number;
  post_necking_extension_policy: "approved_constant_true_stress";
  applicability: Applicability;
  mapping_statuses: Record<string, MappingStatus>;
  mapping_report_sha256: string;
  card_sha256: string;
  exporter_id: string;
  exporter_version: string;
  exporter_digest: string;
  non_production: true;
}

export interface ElastoplasticCardProvenanceSummary {
  entity_type: "exporting.solver_card.revision";
  reference_type: "exporting.solver_card.revision";
  revision_id: string;
  content_sha256: string;
  based_on_revision_id: string | null;
  source_material_model_revision_id: string;
  source_hardening_curve_artifact_id: string;
  source_hardening_curve_sha256: string;
  mapping_report_sha256: string;
  recorded_at: string;
  recorded_by: string;
}

export interface ElastoplasticCardRevision extends RevisionMetadata {
  content: ElastoplasticCardContent;
  provenance: ElastoplasticCardProvenanceSummary;
}

export interface ElastoplasticCardResponse {
  solver_card_id: string;
  material_model_id: string;
  target: ExportTarget;
  solver_material_id: number;
  material_name: string;
  current_revision: ElastoplasticCardRevision;
  links: Record<string, string>;
}

export interface ElastoplasticCardCreatedResponse {
  card: ElastoplasticCardResponse;
  mapping_report: MappingReport;
}
