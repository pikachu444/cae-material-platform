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
  material_class: MaterialClass;
}

export type MaterialClass =
  | "unclassified"
  | "metal"
  | "polymer"
  | "elastomer"
  | "composite"
  | "ceramic"
  | "other";

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

export interface MaterialReviseInput {
  content: MaterialContent;
  change_reason: string;
}

export interface MaterialStateCreateInput {
  content: Omit<MaterialStateContent, "material_id">;
  change_reason: string;
}

export type MaterialStateReviseInput = MaterialStateCreateInput;

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
  method_code: "reference_uniaxial_tensile" | "reference_shear_relaxation";
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
  failure_code: string | null;
  qc_observations: QcObservation[];
  change_reason: string;
  started_at: string;
  ended_at: string | null;
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
  post_necking_extension_policy: "approved_constant_true_stress";
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

export interface LinearViscoelasticModelResponse {
  material_model_id: string;
  material_state_id: string;
  current_revision: RevisionMetadata & {
    content: {
      model_family_id: string;
      model_schema_version: "1.0.0" | "1.1.0";
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
