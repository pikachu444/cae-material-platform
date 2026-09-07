import type { CommonExportProvenance } from "../../modeling/contracts";

import type {

  DataClassification,

  RevisionMetadata,

} from "../../../shared/model/core-contracts";

import type {

  CurveDefinitionContract,

  CurveSeriesPreviewContract,

} from "../../../shared/model/curve-contracts";

export interface SpecimenContent {
  material_id: string;
  material_revision_id: string;
  material_state_id: string;
  material_state_revision_id: string;
  specimen_code: string;
  orientation: string | null;
  preparation_note: string | null;
}

export interface SpecimenRevision extends RevisionMetadata {
  content: SpecimenContent;
}

export interface SpecimenResponse {
  specimen_id: string;
  material_state_id: string;
  current_revision: SpecimenRevision;
  links: Record<string, string>;
}

export interface SpecimenSourceResponse {
  specimen_source_genealogy_id: string;
  specimen_id: string;
  current_revision: RevisionMetadata & {
    content: {
      specimen_id: string;
      specimen_revision_id: string;
      sources: Array<{
        material_lot_id: string;
        material_lot_revision_id: string;
        note: string | null;
      }>;
      note: string | null;
    };
  };
  links: Record<string, string>;
}

export interface TestMethodContent {
  method_code:
    | "reference_uniaxial_tensile"
    | "reference_planar_tension"
    | "reference_biaxial_tension"
    | "reference_shear_relaxation";
  display_name: "Reference uniaxial tensile CSV" | "Reference shear relaxation CSV";
  reference_only: true;
}

export interface TestMethodRevision extends RevisionMetadata {
  content: TestMethodContent;
}

export interface TestMethodResponse {
  test_method_id: string;
  current_revision: TestMethodRevision;
  links: Record<string, string>;
}

export interface TestRunContent {
  specimen_id: string;
  specimen_revision_id: string;
  test_method_id: string;
  test_method_revision_id: string;
  run_label: string;
  performed_at: string;
  test_temperature_k: number | null;
  crosshead_speed_mm_per_min: number | null;
  reference_only: true;
}

export interface TestRunRevision extends RevisionMetadata {
  content: TestRunContent;
}

export interface TestRunResponse {
  test_run_id: string;
  specimen_id: string;
  test_method_id: string;
  current_revision: TestRunRevision;
  links: Record<string, string>;
}

export type StandardConformance = "conformant" | "deviation_approved" | "not_claimed";
export type CalibrationResult = "passed" | "limited" | "failed";
export type LoadingRateUnit = "mm/min" | "1/s" | "N/s" | "Pa/s";

export interface TestContextResource<TContent = Record<string, unknown>> {
  resource_id: string;
  current_revision: RevisionMetadata & { content: TContent };
  links: Record<string, string>;
}

export interface TestCampaignContent {
  test_method_id: string;
  test_method_revision_id: string;
  campaign_code: string;
  name: string;
  objective: string;
  population_description: string;
  planned_specimen_count: number;
  standard_conformance: StandardConformance;
  standard_designation: string | null;
  standard_edition: string | null;
  standard_deviation_reason: string | null;
  reference_only: true;
}

export interface InstrumentContent {
  instrument_code: string;
  name: string;
  serial_number: string;
  manufacturer: string | null;
  model: string | null;
  location: string | null;
  description: string | null;
}

export interface InstrumentCalibrationContent {
  instrument_id: string;
  instrument_revision_id: string;
  calibration_code: string;
  certificate_reference: string;
  provider: string;
  calibrated_at: string;
  valid_from: string;
  valid_until: string;
  result: CalibrationResult;
  limitation_note: string | null;
}

export interface TestConditionContent {
  test_method_id: string;
  test_method_revision_id: string;
  captured_at: string;
  temperature_setpoint_k: string | null;
  temperature_observed_k: string | null;
  humidity_setpoint_pct: string | null;
  humidity_observed_pct: string | null;
  loading_rate_value: string | null;
  loading_rate_unit: LoadingRateUnit | null;
  orientation: string | null;
  medium: string | null;
  note: string | null;
}

export interface TestRunContextContent {
  test_run_id: string;
  test_run_revision_id: string;
  test_campaign_id: string;
  test_campaign_revision_id: string;
  test_condition_id: string;
  test_condition_revision_id: string;
  instrument_id: string;
  instrument_revision_id: string;
  calibration_id: string;
  calibration_revision_id: string;
  note: string | null;
}

export type TestCampaignResponse = TestContextResource<TestCampaignContent>;
export type InstrumentResponse = TestContextResource<InstrumentContent>;
export type InstrumentCalibrationResponse = TestContextResource<InstrumentCalibrationContent>;
export type TestConditionResponse = TestContextResource<TestConditionContent>;
export type TestRunContextResponse = TestContextResource<TestRunContextContent>;

export interface ReferenceTensileMapping {
  strain_column: string;
  stress_column: string;
  strain_unit: "1" | "%";
  stress_unit: "Pa" | "kPa" | "MPa" | "GPa";
}

export type ImportMappingSuggestionConfidence = "none" | "low";

export interface ImportMappingSuggestion {
  column: string | null;
  unit: string | null;
  confidence: ImportMappingSuggestionConfidence;
}

export interface ImportDetectionReportResponse {
  import_detection_report_id: string;
  classification: DataClassification;
  raw_asset_id: string;
  raw_artifact_id: string;
  raw_sha256: string;
  importer_id: "urn:cmp:testing:synthetic-csv-header-importer:1.0.0";
  importer_version: "1.0.0";
  status: "needs_input";
  header_columns: string[];
  strain_suggestion: ImportMappingSuggestion;
  stress_suggestion: ImportMappingSuggestion;
  report_sha256: string;
  reference_only: true;
  created_at: string;
  created_by: string;
  request_id: string;
  trace_id: string;
  links: Record<string, string>;
}

export interface ReferenceImportMappingContent {
  detection_report_id: string;
  raw_asset_id: string;
  raw_artifact_id: string;
  strain_column: string;
  stress_column: string;
  strain_unit: ReferenceTensileMapping["strain_unit"];
  stress_unit: ReferenceTensileMapping["stress_unit"];
  dataset_mapping_sha256: string;
  importer_id: "urn:cmp:testing:synthetic-csv-header-importer:1.0.0";
  importer_version: "1.0.0";
  approval_kind: "human_confirmed";
  reference_only: true;
}

export interface ImportMappingRevision extends RevisionMetadata {
  content: ReferenceImportMappingContent;
}

export interface ImportMappingResponse {
  import_mapping_id: string;
  mapping_label: string;
  current_revision: ImportMappingRevision;
  links: Record<string, string>;
}

export interface ImportRunResponse {
  import_run_id: string;
  classification: DataClassification;
  import_kind: "reference_uniaxial_tensile_csv";
  execution_mode: "reference_inline";
  reference_only: true;
  status: "executing" | "succeeded" | "failed";
  test_run_id: string;
  test_run_revision_id: string;
  raw_asset_id: string;
  raw_artifact_id: string;
  import_mapping_id: string;
  import_mapping_revision_id: string;
  mapping_sha256: string;
  importer_id: "urn:cmp:testing:synthetic-csv-header-importer:1.0.0";
  importer_version: "1.0.0";
  output_dataset_id: string | null;
  output_dataset_revision_id: string | null;
  failure_code: string | null;
  change_reason: string;
  started_at: string;
  ended_at: string | null;
  links: Record<string, string>;
}

export type DatasetRepresentation = "raw" | "normalized" | "processed";

export interface DatasetChannel {
  name: "engineering_strain" | "engineering_stress";
  quantity_kind: "engineering_strain" | "engineering_stress";
  original_column: string;
  original_unit: string;
  normalized_unit: "1" | "Pa";
  axis_role: "independent" | "dependent";
}

export interface DatasetContent {
  test_run_id: string;
  test_run_revision_id: string;
  raw_asset_id: string;
  raw_artifact_id: string;
  data_artifact_id: string;
  data_sha256: string;
  representation: DatasetRepresentation;
  source_dataset_revision_id: string | null;
  processing_run_id: string | null;
  point_count: number;
  mapping_sha256: string;
  importer_id: string;
  importer_version: string;
  reference_only: true;
  channels: DatasetChannel[];
}

export interface DatasetRevision extends RevisionMetadata {
  content: DatasetContent;
}

export interface DatasetResponse {
  dataset_id: string;
  test_run_id: string;
  current_revision: DatasetRevision;
  links: Record<string, string>;
}

export interface CurvePoint {
  engineering_strain: number;
  engineering_stress: number;
}

export interface CurvePreview {
  dataset_id: string;
  dataset_revision_id: string;
  representation: DatasetRepresentation;
  point_count: number;
  returned_point_count: number;
  sampled: boolean;
  strain_unit: "1" | "%";
  stress_unit: "Pa" | "kPa" | "MPa" | "GPa";
  points: CurvePoint[];
}

export interface DatasetSelectionContent {
  selection_kind: "reference_curve_dataset_revision";
  member_count: 1;
  dataset_id: string;
  dataset_revision_id: string;
}

export interface DatasetSelectionRevision extends RevisionMetadata {
  content: DatasetSelectionContent;
}

export interface DatasetSelectionResponse {
  selection_id: string;
  selection_label: string;
  current_revision: DatasetSelectionRevision;
  links: Record<string, string>;
}

export interface TensileReplicateSelectionMember {
  ordinal: number;
  dataset_id: string;
  dataset_revision_id: string;
  test_run_id: string;
  test_run_revision_id: string;
}

export interface TensileReplicateSelectionRevision extends RevisionMetadata {
  content: {
    selection_kind: "reference_tensile_replicate_set";
    member_count: number;
    members: TensileReplicateSelectionMember[];
  };
}

export interface TensileReplicateSelectionResponse {
  selection_id: string;
  selection_label: string;
  current_revision: TensileReplicateSelectionRevision;
  links: Record<string, string>;
}

export interface ReferenceTensileCropRecipeContent {
  recipe_kind: "reference_tensile_inclusive_crop";
  step_count: 1;
  minimum_engineering_strain: number;
  maximum_engineering_strain: number;
  input_schema_ref: string;
  output_schema_ref: string;
  diagnostics_schema_ref: string;
  boundary_policy: "select_observed_points_inclusive_no_interpolation";
}

export interface ReferenceTensileAlignmentRecipeContent {
  recipe_kind: "reference_tensile_common_grid_linear";
  step_count: 1;
  grid_start_engineering_strain: number;
  grid_end_engineering_strain: number;
  grid_point_count: number;
  domain_policy: "intersection";
  interpolation_policy: "piecewise_linear";
  extrapolation_policy: "reject";
  input_schema_ref: string;
  output_schema_ref: string;
  diagnostics_schema_ref: string;
}

export interface ProcessingRecipeRevision extends RevisionMetadata {
  content: ReferenceTensileCropRecipeContent | ReferenceTensileAlignmentRecipeContent;
}

export interface ProcessingRecipeResponse {
  recipe_id: string;
  recipe_label: string;
  current_revision: ProcessingRecipeRevision;
  links: Record<string, string>;
}

export interface ProcessingRunResponse {
  processing_run_id: string;
  classification: DataClassification;
  execution_mode: "committed";
  status: "executing" | "succeeded" | "failed";
  selection_id: string;
  selection_revision_id: string;
  recipe_id: string;
  recipe_revision_id: string;
  input_dataset_id: string;
  input_dataset_revision_id: string;
  input_point_count: number;
  output_point_count: number | null;
  removed_point_count: number | null;
  result_artifact_id: string | null;
  result_sha256: string | null;
  output_dataset_id: string | null;
  output_dataset_revision_id: string | null;
  failure_code: string | null;
  change_reason: string;
  started_at: string;
  ended_at: string | null;
  run_kind: "reference_tensile_inclusive_crop" | "reference_tensile_common_grid_linear";
  batch_id: string | null;
  member_ordinal: number | null;
  links: Record<string, string>;
}

export interface ReplicateAlignmentBatchResponse {
  alignment_batch_id: string;
  selection_id: string;
  selection_revision_id: string;
  recipe_id: string;
  recipe_revision_id: string;
  common_domain_start: number;
  common_domain_end: number;
  member_count: number;
  runs: ProcessingRunResponse[];
}

export interface ReferenceTensileReplicatePlanContent {
  plan_kind: "reference_tensile_replicate_scalar_and_curve";
  selection_id: string;
  selection_revision_id: string;
  sample_count: number;
  required_input_representation: "processed";
  scalar_feature: "peak_engineering_stress_pa";
  curve_grid_policy: "exact_processed_grid_match_no_alignment";
  quantile_method: "linear_inclusive";
  confidence_interval_method: "student_t_95_two_sided";
  curve_output_schema_ref: string;
  scalar_distribution: ScalarDistributionAnalysisOptions | null;
}

export interface ExactUnitProfilePin {
  profile_id: string;
  revision_id: string;
  content_sha256: string;
}

export interface ScalarDistributionAnalysisOptions {
  seed: number;
  bootstrap_samples: 999;
  unit_profile: ExactUnitProfilePin | null;
}

export interface ReplicateStatisticalPlanRevision extends RevisionMetadata {
  content: ReferenceTensileReplicatePlanContent;
}

export interface ReplicateStatisticalPlanResponse {
  statistical_plan_id: string;
  plan_label: string;
  current_revision: ReplicateStatisticalPlanRevision;
  links: Record<string, string>;
}

export interface ReplicateStatisticalRunMember {
  ordinal: number;
  dataset_id: string;
  dataset_revision_id: string;
  test_run_id: string;
  test_run_revision_id: string;
}

export interface ReplicateStatisticalRunResponse {
  statistical_run_id: string;
  classification: DataClassification;
  execution_mode: "committed";
  status: "executing" | "succeeded" | "failed";
  plan_id: string;
  plan_revision_id: string;
  selection_id: string;
  selection_revision_id: string;
  sample_count: number;
  members: ReplicateStatisticalRunMember[];
  result_id: string | null;
  result_revision_id: string | null;
  curve_artifact_id: string | null;
  curve_sha256: string | null;
  curve_point_count: number | null;
  scalar_distribution_result_id: string | null;
  scalar_distribution_result_revision_id: string | null;
  scalar_distribution_artifact_id: string | null;
  scalar_distribution_sha256: string | null;
  failure_code: string | null;
  qc_observations: QcObservation[];
  change_reason: string;
  started_at: string;
  ended_at: string | null;
  links: Record<string, string>;
}

export type DistributionFamily = "normal" | "lognormal" | "weibull";

export interface ScalarDistributionObservation {
  ordinal: number;
  dataset_id: string;
  dataset_revision_id: string;
  test_run_id: string;
  test_run_revision_id: string;
  value_pa: number | null;
  quality: "observed" | "missing" | "non_finite" | "censored";
  outlier_assessment: "not_assessed" | "flagged" | "not_flagged";
}

export interface ScalarDistributionCandidate {
  family: DistributionFamily;
  status: "succeeded" | "not_eligible" | "failed";
  support: "real" | "positive";
  estimator: string;
  parameter_count: 2;
  parameters: Array<{ name: "location" | "scale" | "shape"; estimate: number; unit_id: string | null }>;
  log_likelihood: number | null;
  aicc: number | null;
  bic: number | null;
  anderson_darling: number | null;
  bootstrap_p_value: number | null;
  bootstrap_success_count: number;
  bootstrap_failure_count: number;
  delta_aicc: number | null;
  recommended: boolean;
  reason_codes: string[];
  warnings: string[];
  candidate_sha256: string;
}

export interface ScalarDistributionResultResponse {
  scalar_distribution_result_id: string;
  current_revision: RevisionMetadata;
  statistical_run_id: string;
  statistical_result_id: string;
  statistical_result_revision_id: string;
  plan_id: string;
  plan_revision_id: string;
  selection_id: string;
  selection_revision_id: string;
  scalar_feature: "peak_engineering_stress_pa";
  sample_count: number;
  minimum_sample_count: 8;
  small_sample_warning_below: 20;
  observations: ScalarDistributionObservation[];
  candidates: ScalarDistributionCandidate[];
  recommended_families: DistributionFamily[];
  recommendation_method: "aicc_delta_le_2_at_least_two_successful_candidates_v1";
  artifact_id: string;
  artifact_sha256: string;
  seed: number;
  bootstrap_samples: 999;
  unit_profile: ExactUnitProfilePin | null;
  unit_applications: Array<{
    location: string;
    role: "input" | "display" | "solver_export";
    quantity_semantics: string;
    dimension: string;
    unit_id: string;
  }>;
  runtime_manifest: {
    algorithm_version: "scalar_distribution_fitting_v1";
    schema_ref: "urn:cmp:statistics:scalar-distribution-result:1.0.0";
    python_version: string;
    numpy_version: string;
    scipy_version: string;
    rng: "numpy.random.PCG64";
    source_sha256: string;
    lock_sha256: string;
    environment_sha256: string;
  };
  links: Record<string, string>;
}

export interface ScalarDistributionSelectionResponse {
  distribution_selection_id: string;
  current_revision: RevisionMetadata;
  content: {
    distribution_result_id: string;
    distribution_result_revision_id: string;
    selected_family: DistributionFamily;
    candidate_sha256: string;
    selection_reason: string;
  };
  links: Record<string, string>;
}

export interface ReplicateScalarStatistics {
  sample_count: number;
  mean: number;
  sample_standard_deviation: number;
  median: number;
  median_absolute_deviation: number;
  interquartile_range: number;
  minimum: number;
  maximum: number;
  coefficient_of_variation: number | null;
  mean_confidence_interval_lower_95: number;
  mean_confidence_interval_upper_95: number;
}

export interface ReplicateStatisticalResultResponse {
  statistical_result_id: string;
  current_revision: RevisionMetadata;
  statistical_run_id: string;
  plan_id: string;
  plan_revision_id: string;
  selection_id: string;
  selection_revision_id: string;
  curve_artifact_id: string;
  curve_sha256: string;
  curve_point_count: number;
  peak_engineering_stress_pa: ReplicateScalarStatistics;
  methods: {
    grid: "exact_processed_grid_match_no_alignment";
    quantile: "linear_inclusive";
    confidence_interval: "student_t_95_two_sided";
  };
  links: Record<string, string>;
}

export interface ReplicateStatisticalCurvePoint {
  engineering_strain: number;
  statistics: ReplicateScalarStatistics;
}

export interface ReplicateStatisticalCurveResponse {
  result_id: string;
  grid_policy: "exact_processed_grid_match_no_alignment";
  points: ReplicateStatisticalCurvePoint[];
}

export interface ReplicateOutlierPlanResponse {
  detection_plan_id: string;
  plan_label: string;
  current_revision: RevisionMetadata;
  content: {
    statistical_result_id: string;
    statistical_result_revision_id: string;
    detector: "absolute_modified_z_score_peak_stress";
    feature: "peak_engineering_stress_pa";
    absolute_modified_z_threshold: number;
    automatic_exclusion: false;
  };
}

export interface ReplicateOutlierCandidateResponse {
  candidate_id: string;
  ordinal: number;
  dataset_id: string;
  dataset_revision_id: string;
  test_run_id: string;
  test_run_revision_id: string;
  peak_engineering_stress_pa: number;
  sample_median_peak_stress_pa: number;
  sample_mad_peak_stress_pa: number;
  absolute_modified_z_score: number | null;
  threshold: number;
  evidence_code: "modified_z_threshold_exceeded" | "mad_zero_nonmedian_review";
  review_status: "review_required";
}

export interface ReplicateOutlierRunResponse {
  detection_run_id: string;
  classification: DataClassification;
  detection_plan_id: string;
  detection_plan_revision_id: string;
  statistical_result_id: string;
  statistical_result_revision_id: string;
  selection_id: string;
  selection_revision_id: string;
  sample_count: number;
  sample_median_peak_stress_pa: number;
  sample_mad_peak_stress_pa: number;
  candidate_count: number;
  candidates: ReplicateOutlierCandidateResponse[];
  started_at: string;
  ended_at: string;
}

export type ReplicateOutlierDecision = "retained" | "excluded_from_calibration";

export interface ReplicateOutlierAssessmentResponse {
  assessment_id: string;
  current_revision: RevisionMetadata;
  candidate_id: string;
  detection_plan_id: string;
  detection_plan_revision_id: string;
  decision: ReplicateOutlierDecision;
  assessment_reason: string;
  automatic_exclusion: false;
}

export interface ReferenceCalibrationScopeResponse {
  scope_id: string;
  scope_label: string;
  current_revision: RevisionMetadata;
  source_selection_id: string;
  source_selection_revision_id: string;
  statistical_result_id: string;
  statistical_result_revision_id: string;
  detection_plan_id: string;
  detection_plan_revision_id: string;
  source_member_count: number;
  included_member_count: number;
  excluded_member_count: number;
  members: Array<{
    ordinal: number;
    dataset_id: string;
    dataset_revision_id: string;
    test_run_id: string;
    test_run_revision_id: string;
    disposition: "included" | "excluded";
    candidate_id: string | null;
    assessment_id: string | null;
    assessment_revision_id: string | null;
  }>;
}

export interface ReferenceTensilePairPlanContent {
  plan_kind: "reference_tensile_pair_scalar_and_curve";
  sample_count: 2;
  first_selection_id: string;
  first_selection_revision_id: string;
  second_selection_id: string;
  second_selection_revision_id: string;
  input_schema_ref: string;
  scalar_feature: "peak_engineering_stress_pa";
  curve_grid_policy: "exact_observed_grid_match_no_alignment";
  assumption_profile: "identical_observed_engineering_strain_grid";
  quantile_method: "linear_inclusive";
  confidence_interval_status: "not_provided_reference_pair";
  curve_output_schema_ref: string;
}

export interface StatisticalPlanRevision extends RevisionMetadata {
  content: ReferenceTensilePairPlanContent;
}

export interface StatisticalPlanResponse {
  statistical_plan_id: string;
  plan_label: string;
  current_revision: StatisticalPlanRevision;
  links: Record<string, string>;
}

export interface QcObservation {
  check_code:
    | "distinct_test_runs"
    | "identical_observed_engineering_strain_grid"
    | "input_artifact_readable";
  outcome: "passed" | "failed";
  detail: string;
  expected_point_count: number | null;
  observed_point_count: number | null;
  mismatch_index: number | null;
}

export interface StatisticalRunResponse {
  statistical_run_id: string;
  classification: DataClassification;
  execution_mode: "committed";
  status: "executing" | "succeeded" | "failed";
  plan_id: string;
  plan_revision_id: string;
  first_selection_id: string;
  first_selection_revision_id: string;
  first_dataset_id: string;
  first_dataset_revision_id: string;
  second_selection_id: string;
  second_selection_revision_id: string;
  second_dataset_id: string;
  second_dataset_revision_id: string;
  sample_count: 2;
  result_id: string | null;
  result_revision_id: string | null;
  curve_artifact_id: string | null;
  curve_sha256: string | null;
  curve_point_count: number | null;
  failure_code: string | null;
  qc_observations: QcObservation[];
  change_reason: string;
  started_at: string;
  ended_at: string | null;
  links: Record<string, string>;
}

export interface ReferenceTensilePairScalarStatistics {
  first_peak_engineering_stress_pa: number;
  second_peak_engineering_stress_pa: number;
  mean_engineering_stress_pa: number;
  sample_standard_deviation_engineering_stress_pa: number;
  median_engineering_stress_pa: number;
  median_absolute_deviation_engineering_stress_pa: number;
  interquartile_range_engineering_stress_pa: number;
  minimum_engineering_stress_pa: number;
  maximum_engineering_stress_pa: number;
  coefficient_of_variation: number | null;
  confidence_interval_status: "not_provided_reference_pair";
  quantile_method: "linear_inclusive";
}

export interface ReferenceTensilePairResultContent {
  result_kind: "reference_tensile_pair_scalar_and_curve";
  statistical_run_id: string;
  plan_id: string;
  plan_revision_id: string;
  first_selection_id: string;
  first_selection_revision_id: string;
  first_dataset_id: string;
  first_dataset_revision_id: string;
  second_selection_id: string;
  second_selection_revision_id: string;
  second_dataset_id: string;
  second_dataset_revision_id: string;
  sample_count: 2;
  scalar_feature: "peak_engineering_stress_pa";
  curve_artifact_id: string;
  curve_sha256: string;
  curve_point_count: number;
  scalar: ReferenceTensilePairScalarStatistics;
  assumption_profile: "identical_observed_engineering_strain_grid";
  curve_grid_policy: "exact_observed_grid_match_no_alignment";
}

export interface StatisticalResultRevision extends RevisionMetadata {
  content: ReferenceTensilePairResultContent;
}

export interface StatisticalResultResponse {
  statistical_result_id: string;
  current_revision: StatisticalResultRevision;
  links: Record<string, string>;
}

export interface StatisticalCurvePoint {
  engineering_strain: number;
  mean_engineering_stress_pa: number;
  sample_standard_deviation_engineering_stress_pa: number;
  median_engineering_stress_pa: number;
  minimum_engineering_stress_pa: number;
  maximum_engineering_stress_pa: number;
}

export interface StatisticalCurvePreview {
  statistical_result_id: string;
  point_count: number;
  returned_point_count: number;
  sampled: boolean;
  strain_unit: "1";
  stress_unit: "Pa";
  points: StatisticalCurvePoint[];
}

export interface ReferenceTensilePairOutlierDetectionPlanContent {
  plan_kind: "reference_tensile_pair_peak_difference_review";
  detector: "relative_peak_engineering_stress_difference";
  formula_version: "1.0.0";
  statistical_result_id: string;
  statistical_result_revision_id: string;
  feature: "peak_engineering_stress_pa";
  relative_peak_difference_threshold: number;
  candidate_policy: "flag_both_pair_members_for_human_review";
  automatic_exclusion: false;
  scope_kind: "reference_pair_analysis";
}

export interface OutlierDetectionPlanRevision extends RevisionMetadata {
  content: ReferenceTensilePairOutlierDetectionPlanContent;
}

export interface OutlierDetectionPlanResponse {
  outlier_detection_plan_id: string;
  plan_label: string;
  current_revision: OutlierDetectionPlanRevision;
  links: Record<string, string>;
}

export interface OutlierCandidateResponse {
  outlier_candidate_id: string;
  detection_run_id: string;
  detection_plan_id: string;
  detection_plan_revision_id: string;
  statistical_result_id: string;
  statistical_result_revision_id: string;
  statistical_plan_id: string;
  statistical_plan_revision_id: string;
  selection_id: string;
  selection_revision_id: string;
  dataset_id: string;
  dataset_revision_id: string;
  pair_position: "first" | "second";
  feature: "peak_engineering_stress_pa";
  peak_engineering_stress_pa: number;
  peer_peak_engineering_stress_pa: number;
  relative_peak_difference: number;
  relative_peak_difference_threshold: number;
  status: "review_required";
  automatic_exclusion: false;
  links: Record<string, string>;
}

export interface OutlierDetectionRunResponse {
  outlier_detection_run_id: string;
  classification: DataClassification;
  execution_mode: "committed";
  status: "executing" | "succeeded" | "failed";
  detection_plan_id: string;
  detection_plan_revision_id: string;
  statistical_result_id: string;
  statistical_result_revision_id: string;
  candidate_count: 0 | 2;
  failure_code: string | null;
  candidates: OutlierCandidateResponse[];
  change_reason: string;
  started_at: string;
  ended_at: string | null;
  links: Record<string, string>;
}

export interface ReferenceTensilePairOutlierAssessmentContent {
  candidate_id: string;
  scope_kind: "reference_pair_analysis";
  statistical_plan_id: string;
  statistical_plan_revision_id: string;
  decision: "retained" | "excluded_from_reference_analysis";
  assessment_reason: string;
}

export interface OutlierAssessmentRevision extends RevisionMetadata {
  content: ReferenceTensilePairOutlierAssessmentContent;
}

export interface OutlierAssessmentResponse {
  outlier_assessment_id: string;
  current_revision: OutlierAssessmentRevision;
  links: Record<string, string>;
}

export interface OutlierScopeComparisonEntry {
  candidate: OutlierCandidateResponse;
  assessment_history: OutlierAssessmentResponse[];
  latest_assessment: OutlierAssessmentResponse | null;
}

export interface OutlierScopeComparisonResponse {
  detection_plan: OutlierDetectionPlanResponse;
  statistical_result: StatisticalResultResponse;
  scope_kind: "reference_pair_analysis";
  entries: OutlierScopeComparisonEntry[];
  source_mutation: false;
  derived_selection_created: false;
}

export interface UploadSession {
  upload_id: string;
  organization_id: string;
  project_id: string;
  classification: DataClassification;
  state: "open" | "completing" | "completed" | "failed" | "cancelled";
  original_filename: string;
  media_type: string;
  expected_size_bytes: number;
  expected_sha256: string;
  part_size_bytes: number;
  expected_part_count: number;
  test_run_revision_id: string | null;
  raw_asset_id: string | null;
}

export interface RawAsset {
  raw_asset_id: string;
  organization_id: string;
  project_id: string;
  classification: DataClassification;
  sha256: string;
  size_bytes: number;
  media_type: string;
  original_filename: string;
  storage_state: "staged_verified";
}

export type GovernedTabularFileFormat = "csv" | "tsv" | "xlsx";
export type GovernedTabularDataSchema =
  | "monotonic_tension"
  | "monotonic_compression"
  | "planar_tension"
  | "biaxial_tension"
  | "simple_shear"
  | "shear_relaxation"
  | "dma_frequency_temperature_sweep"
  | "forming_limit_diagram";
export type GovernedQuantityKind =
  | "engineering_strain"
  | "engineering_stress"
  | "shear_strain"
  | "shear_stress"
  | "time"
  | "shear_modulus"
  | "displacement"
  | "force"
  | "temperature"
  | "frequency"
  | "storage_modulus"
  | "loss_modulus"
  | "tan_delta"
  | "minor_strain"
  | "major_strain";

export interface GovernedChannelMapping {
  ordinal: number;
  source_column: string;
  source_quantity: GovernedQuantityKind;
  original_unit: string;
  normalized_quantity?: GovernedQuantityKind;
  normalized_unit?: string;
  axis_role: "independent" | "dependent";
}

export interface GovernedImportProfileContent {
  profile_label: string;
  data_schema: GovernedTabularDataSchema;
  file_format: GovernedTabularFileFormat;
  sheet_name: string | null;
  header_row: number;
  encoding: string;
  delimiter: string | null;
  decimal_separator: "." | ",";
  channels: GovernedChannelMapping[];
  initial_gauge_length_m: number | null;
  initial_cross_section_area_m2: number | null;
  approval_kind: "human_confirmed";
  profile_sha256?: string;
}

export interface GovernedImportProfileResponse {
  import_profile_id: string;
  current_revision: RevisionMetadata;
  content: GovernedImportProfileContent & { profile_sha256: string };
}

export interface GovernedImportPreview {
  preview_report_id: string;
  classification: DataClassification;
  raw_asset_id: string;
  raw_artifact_id: string;
  raw_sha256: string;
  file_format: GovernedTabularFileFormat;
  sheet_names: string[];
  selected_sheet_name: string | null;
  header_row: number;
  encoding: string;
  delimiter: string | null;
  decimal_separator: "." | ",";
  header_columns: string[];
  sample_rows: string[][];
  status: "needs_input";
  report_sha256: string;
}

export interface GovernedImportRunResponse {
  import_run_id: string;
  classification: DataClassification;
  test_run_id: string;
  test_run_revision_id: string;
  raw_asset_id: string;
  raw_artifact_id: string;
  import_profile_id: string;
  import_profile_revision_id: string;
  profile_sha256: string;
  idempotency_key: string;
  request_sha256: string;
  status: "executing" | "succeeded" | "failed";
  started_at: string;
  finished_at: string | null;
  raw_dataset_id: string | null;
  raw_dataset_revision_id: string | null;
  normalized_dataset_id: string | null;
  normalized_dataset_revision_id: string | null;
  row_count: number | null;
  failure_code: string | null;
  failure_detail: string | null;
  diagnostics: Array<{
    ordinal: number;
    row_number: number | null;
    column_name: string | null;
    channel_key: string | null;
    error_code: string;
    error_detail: string;
    recovery_hint: string;
  }>;
}

export interface GovernedDatasetResponse {
  dataset_id: string;
  current_revision: RevisionMetadata;
  representation: "raw" | "normalized";
  data_schema: GovernedTabularDataSchema;
  test_run_id: string;
  test_run_revision_id: string;
  raw_asset_id: string;
  raw_artifact_id: string;
  data_artifact_id: string;
  data_sha256: string;
  import_profile_id: string;
  import_profile_revision_id: string;
  source_dataset_revision_id: string | null;
  row_count: number;
  channels: GovernedChannelMapping[];
}

export interface CompletedUpload {
  upload: UploadSession;
  raw_asset: RawAsset;
  available_artifact_id: string | null;
}

export interface CanonicalTestDataChannelPreview {
  key: string;
  name: string;
  quantity_semantics: string;
  axis_role: "independent" | "dependent" | "auxiliary";
  original_unit_string: string;
  normalized_unit: string;
  point_count: number;
  missing_count: number;
}

export interface CanonicalTestDataPreviewResponse {
  status: "valid";
  document_sha256: string;
  canonical_size_bytes: number;
  point_count: number;
  condition_count: number;
  material_maker: string;
  material_grade: string;
  test_date: string;
  operator: string;
  laboratory: string;
  method: string;
  specimen_id: string;
  channels: CanonicalTestDataChannelPreview[];
  canonical_document: Record<string, unknown>;
  curve_definition_sha256: string;
  curve_definition: CurveDefinitionContract;
  curve_series: CurveSeriesPreviewContract;
}

export interface CanonicalTestDataDocumentResponse {
  test_data_document_id: string;
  current_revision: RevisionMetadata;
  document_key: string;
  material_maker: string;
  material_grade: string;
  lot_batch: string | null;
  test_date: string;
  operator: string;
  laboratory: string;
  method: string;
  specimen_id: string;
  point_count: number;
  canonical_artifact_id: string;
  canonical_sha256: string;
  normalized_artifact_id: string;
  normalized_sha256: string;
  channels: CanonicalTestDataChannelPreview[];
  governed_source: CommonExportProvenance | null;
}

/**
 * Activity compatibility for the consumer still composed in
 * material-library.tsx. Modeling owns the matching batch contract; remove
 * these root shapes with the #262 Activity extraction and #263 DTO split.
 */
