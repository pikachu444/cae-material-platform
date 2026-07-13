export type DataClassification =
  | "internal"
  | "confidential"
  | "restricted"
  | "export_controlled";

export type PropertySourceKind =
  | "manual"
  | "supplier_datasheet"
  | "test_derived"
  | "literature"
  | "calibration";

export interface PropertySource {
  kind: PropertySourceKind;
  reference: string | null;
}

export interface Applicability {
  temperature_min_k: number | null;
  temperature_max_k: number | null;
  strain_rate_min_per_s: number | null;
  strain_rate_max_per_s: number | null;
  note: string | null;
}

export interface ProvenanceSummary {
  entity_type: string;
  reference_type: string;
  revision_id: string;
  content_sha256: string;
  based_on_revision_id: string | null;
  recorded_at: string;
  recorded_by: string;
}

export interface RevisionMetadata {
  id: string;
  aggregate_id: string;
  revision_no: number;
  based_on_revision_id: string | null;
  schema_id: string;
  schema_version: string;
  content_hash: string;
  created_at: string;
  created_by: string;
  change_reason: string;
  organization_id: string;
  project_id: string;
  classification: DataClassification;
  lifecycle_state: "draft";
}

export interface MaterialContent {
  name: string;
  material_code: string | null;
  material_family: string | null;
  description: string | null;
}

export interface MaterialRevision extends RevisionMetadata {
  content: MaterialContent;
  provenance: ProvenanceSummary;
}

export interface MaterialResponse {
  material_id: string;
  current_revision: MaterialRevision;
  links: {
    self: string;
    revisions: string;
    states: string;
  };
}

export interface MaterialStateContent {
  material_id: string;
  material_revision_id: string;
  name: string;
  manufacturing_route: string | null;
  heat_treatment: string | null;
  lot_or_batch: string | null;
  description: string | null;
}

export interface MaterialStateRevision extends RevisionMetadata {
  content: MaterialStateContent;
  provenance: ProvenanceSummary;
}

export interface MaterialStateResponse {
  material_state_id: string;
  material_id: string;
  current_revision: MaterialStateRevision;
  property_sets_url: string;
}

export interface PropertySetContent {
  material_state_id: string;
  material_state_revision_id: string;
  density_kg_per_m3: number;
  density_source: PropertySource;
  youngs_modulus_pa: number;
  youngs_modulus_source: PropertySource;
  poisson_ratio: number;
  poisson_ratio_source: PropertySource;
  yield_stress_pa: number | null;
  yield_stress_source: PropertySource | null;
  applicability: Applicability;
}

export interface PropertySetRevision extends RevisionMetadata {
  content: PropertySetContent;
  provenance: ProvenanceSummary;
}

export interface PropertySetResponse {
  property_set_id: string;
  material_state_id: string;
  current_revision: PropertySetRevision;
}

export interface MaterialDetail {
  material: MaterialResponse;
  states: MaterialStateResponse[];
  property_sets: PropertySetResponse[];
}

export interface MaterialRevisionList {
  material_id: string;
  revisions: MaterialRevision[];
}

export interface MaterialRevisionComparison {
  material_id: string;
  left: MaterialRevision;
  right: MaterialRevision;
  changed_fields: string[];
}

export interface MaterialCreateInput {
  classification: DataClassification;
  content: Omit<MaterialContent, "material_id">;
  change_reason: string;
}

export interface MaterialStateCreateInput {
  content: Omit<MaterialStateContent, "material_id">;
  change_reason: string;
}

export interface PropertySetCreateInput {
  content: Omit<PropertySetContent, "material_state_id">;
  change_reason: string;
}

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
  non_production: true;
}

export interface MaterialModelProvenanceSummary extends ProvenanceSummary {
  source_property_set_revision_id: string;
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

export interface ExportTarget {
  solver: string;
  version: string;
  unit_system: string;
}

export type MappingStatus =
  | "exact"
  | "transformed"
  | "approximated"
  | "ignored"
  | "unsupported"
  | "not_applicable";

export interface MappingItem {
  name: string;
  ir_path: string;
  target_representation: string | null;
  status: MappingStatus;
  detail: string;
}

export interface MappingReport {
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

export interface TestMethodContent {
  method_code: "reference_uniaxial_tensile";
  display_name: "Reference uniaxial tensile CSV";
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

export interface ReferenceTensileMapping {
  strain_column: string;
  stress_column: string;
  strain_unit: "1" | "%";
  stress_unit: "Pa" | "kPa" | "MPa" | "GPa";
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
  selection_kind: "reference_normalized_dataset_revision";
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

export interface ProcessingRecipeRevision extends RevisionMetadata {
  content: ReferenceTensileCropRecipeContent;
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
  links: Record<string, string>;
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

export interface CompletedUpload {
  upload: UploadSession;
  raw_asset: RawAsset;
  available_artifact_id: string | null;
}
