export type DataClassification =
  | "internal"
  | "confidential"
  | "restricted"
  | "export_controlled";

export type LifecycleState = "draft" | "review" | "changes_requested" | "approved";

export type ReviewDecisionKind = "approved" | "changes_requested";

export interface ReviewDecisionResponse {
  review_decision_id: string;
  review_request_id: string;
  aggregate_type: string;
  aggregate_id: string;
  revision_id: string;
  manifest_sha256: string;
  decision: ReviewDecisionKind;
  decided_by: string;
  decided_at: string;
  reason: string;
}

export interface ReviewRequestResponse {
  review_request_id: string;
  classification: DataClassification;
  aggregate_type: string;
  aggregate_id: string;
  revision_id: string;
  manifest_sha256: string;
  required_role: "domain_reviewer";
  requested_by: string;
  requested_at: string;
  reason: string;
  lifecycle_state: LifecycleState;
  decision: ReviewDecisionResponse | null;
  links: Record<string, string>;
}

export interface ReviewRequestListResponse {
  items: ReviewRequestResponse[];
}

export interface ReleaseManifestResponse {
  release_manifest_id: string;
  release_id: string;
  manifest_sha256: string;
  package_sha256: string;
  package_size_bytes: number;
  package_media_type: "application/vnd.cmp.release-manifest+json";
  state: "released";
  material_id: string;
  material_revision_id: string;
  material_state_id: string;
  material_state_revision_id: string;
  property_set_id: string;
  property_set_revision_id: string;
  material_model_id: string;
  material_model_revision_id: string;
  material_model_content_sha256: string;
  solver_card_id: string;
  solver_card_revision_id: string;
  solver_card_content_sha256: string;
  mapping_report_sha256: string;
  card_sha256: string;
  validation_result_id: string;
  validation_result_sha256: string;
  review_request_id: string;
  review_manifest_sha256: string;
  provenance_snapshot_sha256: string;
  created_at: string;
  created_by: string;
  reason: string;
}

export interface ReleaseResponse {
  release_id: string;
  classification: DataClassification;
  release_code: string;
  title: string;
  channel: "reference";
  lifecycle_state: "released" | "superseded" | "withdrawn";
  created_at: string;
  created_by: string;
  manifest: ReleaseManifestResponse;
  links: Record<string, string>;
}

export interface ReleaseUsageResponse {
  usage_id: string;
  release_id: string;
  usage_kind: "download" | "consume";
  used_by: string;
  used_at: string;
  reason: string;
}

export interface ReleaseTransitionResponse {
  transition_id: string;
  release_id: string;
  kind: "supersede" | "withdraw";
  from_state: "released";
  to_state: "superseded" | "withdrawn";
  successor_release_id: string | null;
  reason: string;
  occurred_at: string;
  occurred_by: string;
}

export interface ReleaseImpactResponse {
  release: ReleaseResponse;
  predecessor_release_id: string | null;
  successor_release_id: string | null;
  usages: ReleaseUsageResponse[];
  transitions: ReleaseTransitionResponse[];
  warning: string | null;
}

export interface SupersedeReleaseInput {
  successor_release_id: string;
  reason: string;
}

export interface WithdrawReleaseInput {
  reason: string;
}

export interface RecordReleaseUsageInput {
  usage_kind: "consume";
  reason: string;
}

export interface ReleaseListResponse {
  items: ReleaseResponse[];
}

export interface ReleaseCreateInput {
  classification: DataClassification;
  release_code: string;
  title: string;
  material_id: string;
  material_revision_id: string;
  material_state_id: string;
  material_state_revision_id: string;
  property_set_id: string;
  property_set_revision_id: string;
  material_model_id: string;
  material_model_revision_id: string;
  material_model_content_sha256: string;
  solver_card_id: string;
  solver_card_revision_id: string;
  solver_card_content_sha256: string;
  mapping_report_sha256: string;
  card_sha256: string;
  validation_result_id: string;
  validation_result_sha256: string;
  review_request_id: string;
  review_manifest_sha256: string;
  provenance_snapshot_sha256: string;
  reason: string;
}

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
  source_dataset_id: string;
  source_dataset_revision_id: string;
  density_kg_per_m3: number;
  youngs_modulus_pa: number;
  poisson_ratio: number;
  initial_yield_stress_pa: number;
  hardening_curve: TabulatedPlasticityHardeningReference;
  source_point_count: number;
  pre_yield_excluded_point_count: number;
  post_necking_excluded_point_count: number;
  necking_source_point_index: number;
  transformation_profile_id: string;
  transformation_profile_version: string;
  transformation_profile_digest: string;
  necking_engineering_strain: number;
  characterized_max_true_plastic_strain: number;
  extension_max_true_plastic_strain: number;
  post_necking_extension_policy: "approved_constant_true_stress";
  post_necking_approximation_acknowledged: true;
  applicability: Applicability;
  reference_temperature_k: number;
  non_production: true;
}

export interface TabulatedPlasticityProvenanceSummary {
  entity_type: "modeling.material_model.revision";
  reference_type: "modeling.material_model.revision";
  revision_id: string;
  content_sha256: string;
  based_on_revision_id: string | null;
  source_property_set_revision_id: string;
  source_dataset_revision_id: string;
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

export interface HardeningCurvePoint {
  true_plastic_strain: number;
  true_yield_stress_pa: number;
  origin: "catalog_yield_anchor" | "pre_necking_observation" | "approved_constant_extension";
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

export type ProvenanceEntityReferenceKind = "raw_asset" | "artifact" | "revision";

export type ProvenanceCompletenessState = "complete" | "incomplete";

export interface ProvenanceEntityReference {
  kind: ProvenanceEntityReferenceKind;
  type: string;
  id: string;
  sha256: string;
}

export interface ProvenanceCompletenessSummary {
  state: ProvenanceCompletenessState;
  issues: string[];
}

export interface ProvenanceEntityResponse {
  entity_id: string;
  organization_id: string;
  project_id: string;
  classification: DataClassification;
  entity_type: string;
  reference: ProvenanceEntityReference;
  generation_requirement: "none" | "primary";
  generation_activity_id: string | null;
  created_at: string;
  recorded_at: string;
  recorded_by: string;
  completeness: ProvenanceCompletenessSummary;
  links: {
    self: string;
    lineage: string;
    impact: string;
    completeness: string;
  };
}

export type ProvenanceLineageDirection = "upstream" | "downstream";

export interface ProvenanceLineageNode {
  entity_id: string;
  entity_type: string;
  reference: ProvenanceEntityReference;
  generation_activity_id: string | null;
  completeness: ProvenanceCompletenessSummary;
  depth: number;
  path: string[];
  via_relation: "usage_generation" | "derivation" | "revision" | null;
}

export interface ProvenanceLineagePage {
  root_entity_id: string;
  direction: ProvenanceLineageDirection;
  max_depth: number;
  limit: number;
  target_entity_type: string | null;
  nodes: ProvenanceLineageNode[];
  next_cursor: string | null;
  graph_truncated: boolean;
  total_discovered: number;
}

export type ProvenanceCompletenessReportState = "complete" | "incomplete" | "indeterminate";

export interface ProvenanceCompletenessIssue {
  code: string;
  entity_id: string | null;
  activity_id: string | null;
}

export interface ProvenanceCompletenessReport {
  root_entity_id: string;
  state: ProvenanceCompletenessReportState;
  eligible: boolean;
  nodes_evaluated: number;
  edges_evaluated: number;
  max_depth_reached: number;
  issues: ProvenanceCompletenessIssue[];
}

export type AuditOutcome = "success" | "failure" | "denied";

export interface AuditEvent {
  event_id: string;
  sequence_no: number;
  occurred_at: string;
  recorded_at: string;
  actor: { type: "user" | "service"; id: string };
  organization_id: string;
  project_id: string;
  action: string;
  target: { type: string; id: string | null };
  outcome: AuditOutcome;
  request_id: string;
  trace_id: string;
  ip_or_client: "policy-redacted";
  reason: string;
  previous_hash: string;
  event_hash: string;
}

export interface AuditEventPage {
  events: AuditEvent[];
  next_after_sequence: number | null;
}

export type AuditIntegrityState = "valid" | "invalid";

export interface AuditIntegrityIssue {
  code: string;
  event_sequence_no: number | null;
  segment_no: number | null;
}

export interface AuditIntegrityReport {
  state: AuditIntegrityState;
  event_count: number;
  last_sequence_no: number;
  segment_count: number;
  sealed_through_sequence_no: number;
  unsealed_event_count: number;
  issues: AuditIntegrityIssue[];
}
