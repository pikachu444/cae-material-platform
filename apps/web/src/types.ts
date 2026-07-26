export type DataClassification =
  | "internal"
  | "confidential"
  | "restricted"
  | "export_controlled";

export type ProductRole = "administrator" | "user";

export type FeatureGrant =
  | "schema_configuration"
  | "catalog_edit"
  | "processing_calibration"
  | "model_approval"
  | "solver_card_export";

export interface ProductAccessSummary {
  product_role: ProductRole;
  feature_grants: FeatureGrant[];
  legacy_compatible: boolean;
}

export interface ProductAccessAssignment {
  assignment_id: string;
  organization_id: string;
  project_id: string | null;
  subject_type: "principal" | "group";
  principal_id: string | null;
  group_issuer: string | null;
  group_name: string | null;
  product_role: ProductRole;
  feature_grants: FeatureGrant[];
  max_classification: Exclude<DataClassification, "export_controlled">;
  allow_export_controlled: boolean;
  valid_from: string;
  expires_at: string | null;
  revoked_at: string | null;
}

export interface GrantProductAccessInput {
  subject_type: "principal" | "group";
  principal_id: string | null;
  group_issuer: string | null;
  group_name: string | null;
  product_role: ProductRole;
  feature_grants: FeatureGrant[];
  max_classification: Exclude<DataClassification, "export_controlled">;
  allow_export_controlled: boolean;
  organization_wide: boolean;
  expires_at: string | null;
  grant_reason: string;
}

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

export type ProcessKind = "manufacturing" | "heat_treatment" | "conditioning" | "other";
export type LotKind = "lot" | "batch";

export interface ProcessDefinitionContent {
  process_code: string;
  name: string;
  kind: ProcessKind;
  description: string | null;
}

export interface ProcessDefinitionResponse {
  process_definition_id: string;
  current_revision: RevisionMetadata & {
    content: ProcessDefinitionContent;
    provenance: ProvenanceSummary;
  };
}

export interface MaterialLotContent {
  material_id: string;
  material_revision_id: string;
  lot_code: string;
  kind: LotKind;
  manufacturer: string | null;
  supplier: string | null;
  description: string | null;
}

export interface MaterialLotResponse {
  material_lot_id: string;
  material_id: string;
  current_revision: RevisionMetadata & {
    content: MaterialLotContent;
    provenance: ProvenanceSummary;
  };
}

export interface StateGenealogyContent {
  material_state_id: string;
  material_state_revision_id: string;
  manufacturing_process_id: string | null;
  manufacturing_process_revision_id: string | null;
  heat_treatment_process_id: string | null;
  heat_treatment_process_revision_id: string | null;
  material_lot_id: string | null;
  material_lot_revision_id: string | null;
  note: string | null;
}

export interface StateGenealogyResponse {
  state_genealogy_id: string;
  material_state_id: string;
  current_revision: RevisionMetadata & {
    content: StateGenealogyContent;
    provenance: ProvenanceSummary;
  };
}

export type BalanceBasis = "mass" | "volume" | "count" | "not_assessed";

export interface LotFlowContent {
  material_lot_id: string;
  material_lot_revision_id: string;
  original_quantity: string;
  original_unit: string;
  quantity_basis: Exclude<BalanceBasis, "not_assessed">;
  normalized_quantity: string;
  normalized_unit: string;
  normalization_factor: string;
}

export interface ProcessRunContent {
  process_definition_id: string;
  process_definition_revision_id: string;
  material_state_id: string;
  material_state_revision_id: string;
  run_code: string;
  started_at: string;
  ended_at: string | null;
  operator_name: string | null;
  equipment_reference: string | null;
  balance_basis: BalanceBasis;
  balance_tolerance_fraction: string | null;
  balance_not_assessed_reason: string | null;
  balance: {
    input_total: string;
    output_total: string;
    relative_difference: string;
    within_tolerance: boolean;
  } | null;
  inputs: LotFlowContent[];
  outputs: LotFlowContent[];
  note: string | null;
}

export interface ProcessRunResponse {
  process_run_id: string;
  material_state_id: string;
  current_revision: RevisionMetadata & {
    content: ProcessRunContent;
    provenance: ProvenanceSummary;
  };
}

export interface ProcessDefinitionCreateInput {
  classification: DataClassification;
  content: ProcessDefinitionContent;
  change_reason: string;
}

export interface MaterialLotCreateInput {
  content: Omit<MaterialLotContent, "material_id">;
  change_reason: string;
}

export interface StateGenealogyCreateInput {
  content: Omit<StateGenealogyContent, "material_state_id">;
  change_reason: string;
}

export interface ProcessRunCreateInput {
  content: {
    process_definition_id: string;
    process_definition_revision_id: string;
    material_state_revision_id: string;
    run_code: string;
    started_at: string;
    ended_at: string | null;
    operator_name: string | null;
    equipment_reference: string | null;
    balance_basis: BalanceBasis;
    balance_tolerance_fraction: string | null;
    balance_not_assessed_reason: string | null;
    inputs: Array<{
      material_lot_id: string;
      material_lot_revision_id: string;
      original_quantity: string;
      original_unit: string;
    }>;
    outputs: Array<{
      material_lot_id: string;
      material_lot_revision_id: string;
      original_quantity: string;
      original_unit: string;
    }>;
    note: string | null;
  };
  change_reason: string;
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

/** UXC-06C1 ephemeral output; it is never an immutable Solver Card. */
export interface TargetPreviewResponse {
  preview_identity: string;
  filename: string;
  native_text: string;
  native_sha256: string;
  mapping_report_sha256: string;
  mapping: { items: MappingItem[]; [key: string]: unknown };
  source: {
    processing_output_id: string;
    processing_output_revision_id: string;
    processing_output_sha256: string;
    material_id: string;
    material_revision_id: string;
    material_state_id: string;
    material_state_revision_id: string;
    material_model_ir_revision_id: string;
    neutral_material_id: string;
    neutral_material_revision_id: string;
  };
  target: ExportTarget & { solver_material_id: number; material_name: string };
  acknowledgement_identity: string | null;
  non_production: true;
  delivery_status: "unavailable_pending_uxc_06c2";
}

/** UXC-06C2 immutable card plus transactional outbox receipt. */
export interface TargetDeliveryResponse {
  delivery_status: "delivered";
  receipt_id: string;
  delivery_identity: string;
  solver_card_id: string;
  solver_card_revision_id: string;
  filename: string;
  native_sha256: string;
  mapping_report_sha256: string;
  mapping_statuses: string[];
  source: TargetPreviewResponse["source"];
  target: TargetPreviewResponse["target"];
  occurred_at: string;
  recorded_by: string;
  links: Record<string, string>;
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

export type GovernedTabularFileFormat = "csv" | "tsv" | "xlsx";
export type GovernedTabularDataSchema =
  | "monotonic_tension"
  | "monotonic_compression"
  | "planar_tension"
  | "biaxial_tension"
  | "simple_shear"
  | "shear_relaxation";
export type GovernedQuantityKind =
  | "engineering_strain"
  | "engineering_stress"
  | "shear_strain"
  | "shear_stress"
  | "time"
  | "shear_modulus"
  | "displacement"
  | "force";

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

export type BulkExportMemberKind =
  | "raw_original"
  | "dataset_parquet"
  | "dataset_csv"
  | "model_ir_json"
  | "model_ir_schema"
  | "solver_mapping_report"
  | "solver_card_native"
  | "test_data_json"
  | "mapping_profile_json"
  | "processing_recipe_json"
  | "neutral_material_json"
  | "neutral_solver_mapping_report"
  | "neutral_solver_card_native";

export interface BulkExportSourceRef {
  kind: BulkExportMemberKind;
  raw_asset_id: string | null;
  artifact_id: string | null;
  dataset_id: string | null;
  dataset_revision_id: string | null;
  material_model_id: string | null;
  material_model_revision_id: string | null;
  solver_card_id: string | null;
  solver_card_revision_id: string | null;
  test_data_document_id?: string | null;
  test_data_document_revision_id?: string | null;
  mapping_profile_id?: string | null;
  mapping_profile_revision_id?: string | null;
  processing_recipe_id?: string | null;
  processing_recipe_revision_id?: string | null;
  neutral_material_id?: string | null;
  neutral_material_revision_id?: string | null;
  neutral_solver_card_id?: string | null;
  neutral_solver_card_revision_id?: string | null;
}

export interface BulkExportCandidate {
  source: BulkExportSourceRef;
  classification: DataClassification;
  source_sha256: string;
  source_size_bytes: number;
  media_type: string;
  default_archive_path: string;
  label: string;
}

export interface ExportSelectionResponse {
  export_selection_id: string;
  current_revision: RevisionMetadata & {
    content: {
      selection_label: string;
      classification: DataClassification;
      expected_size_bytes: number;
      selection_digest: string;
      members: Array<BulkExportCandidate & { ordinal: number; archive_path: string }>;
      omissions: Array<{
        ordinal: number;
        source: BulkExportSourceRef;
        reason_code: string;
        reason: string;
      }>;
    };
  };
  links: Record<string, string | null>;
}

export interface BulkExportJobResponse {
  export_job_id: string;
  classification: DataClassification;
  export_selection_id: string;
  export_selection_revision_id: string;
  state:
    | "queued"
    | "running"
    | "reconciliation_required"
    | "reconciling"
    | "succeeded"
    | "failed";
  attempt_count: number;
  bundle_id: string | null;
  failure_code: string | null;
  failure_detail: string | null;
  submitted_at: string;
  submitted_by: string;
  started_at: string | null;
  completed_at: string | null;
  lease_expires_at: string | null;
  heartbeat_at: string | null;
  committed_output: {
    output_commit_id: string;
    archive_artifact_id: string;
    archive_sha256: string;
    archive_size_bytes: number;
    manifest_sha256: string;
    committed_at: string;
    committed_by: string;
  } | null;
  links: Record<string, string | null>;
}

export interface BulkExportBundleResponse {
  export_bundle_id: string;
  classification: DataClassification;
  export_selection_id: string;
  export_selection_revision_id: string;
  archive_artifact_id: string;
  archive_sha256: string;
  archive_size_bytes: number;
  manifest_sha256: string;
  component_count: number;
  omission_count: number;
  created_at: string;
  created_by: string;
  links: Record<string, string | null>;
}

export interface OperationSeriesResponse {
  method: string;
  route: string;
  status_family: string;
  request_count: number;
  error_count: number;
  duration_sum_ms: number;
  p95_upper_bound_ms: number;
}

export interface OperationalSnapshotResponse {
  service: "cmp-api";
  version: string;
  started_at: string;
  observed_at: string;
  active_requests: number;
  request_count: number;
  error_count: number;
  series: OperationSeriesResponse[];
}

export type ConfigurableAttributeDataType =
  | "number"
  | "integer"
  | "text"
  | "boolean"
  | "date"
  | "discrete"
  | "file"
  | "curve"
  | "record_reference";

export interface ConfigurableTableContent {
  key: string;
  name: string;
  description: string | null;
}

export interface ConfigurableTableResponse {
  table_id: string;
  current_revision: RevisionMetadata & { content: ConfigurableTableContent };
}

export interface ConfigurableAttributeContent {
  table_revision_id: string;
  key: string;
  name: string;
  data_type: ConfigurableAttributeDataType;
  required: boolean;
  quantity_semantics: string | null;
  normalized_unit: string | null;
  minimum_number: number | null;
  maximum_number: number | null;
  minimum_length: number | null;
  maximum_length: number | null;
  pattern: string | null;
  allowed_values: string[];
  reference_table_id: string | null;
  help_text: string | null;
}

export interface ConfigurableAttributeResponse {
  attribute_definition_id: string;
  table_id: string;
  current_revision: RevisionMetadata & { content: ConfigurableAttributeContent };
}

export interface ConfigurableLayoutItem {
  attribute_definition_id: string;
  attribute_definition_revision_id: string;
  section: string;
  ordinal: number;
}

export interface ConfigurableLayoutResponse {
  layout_id: string;
  table_id: string;
  revision: RevisionMetadata;
  name: string;
  description: string | null;
  items: ConfigurableLayoutItem[];
}

export interface ConfigurableSubsetResponse {
  subset_id: string;
  table_id: string;
  revision: RevisionMetadata;
  name: string;
  description: string | null;
  filter_definition: Record<string, unknown> | null;
}

export interface ConfigurableCatalogFolderResponse {
  folder_id: string;
  table_id: string;
  current_revision: RevisionMetadata;
  content: {
    table_revision_id: string;
    name: string;
    description: string | null;
    parent_folder_id: string | null;
    parent_folder_revision_id: string | null;
  };
}

interface ConfigurableRecordValueBase {
  attribute_definition_id: string;
  attribute_definition_revision_id: string;
}

export type ConfigurableRecordValue =
  | (ConfigurableRecordValueBase & {
      data_type: "number";
      original_value: string;
      original_unit_string: string;
      normalized_value: string;
      normalized_unit: string;
      quantity_semantics: string;
    })
  | (ConfigurableRecordValueBase & { data_type: "integer"; value: number })
  | (ConfigurableRecordValueBase & { data_type: "text"; value: string })
  | (ConfigurableRecordValueBase & { data_type: "boolean"; value: boolean })
  | (ConfigurableRecordValueBase & { data_type: "date"; value: string })
  | (ConfigurableRecordValueBase & { data_type: "discrete"; value: string })
  | (ConfigurableRecordValueBase & {
      data_type: "file";
      artifact_id: string;
      artifact_sha256: string;
    })
  | (ConfigurableRecordValueBase & {
      data_type: "curve";
      artifact_id: string;
      artifact_sha256: string;
    })
  | (ConfigurableRecordValueBase & {
      data_type: "record_reference";
      target_record_id: string;
      target_record_revision_id: string;
    });

export interface ConfigurableCatalogRecordContent {
  table_revision_id: string;
  name: string;
  external_key: string | null;
  description: string | null;
  folder_id: string | null;
  folder_revision_id: string | null;
  values: ConfigurableRecordValue[];
}

export interface ConfigurableCatalogRecordResponse {
  record_id: string;
  table_id: string;
  current_revision: RevisionMetadata & { content: ConfigurableCatalogRecordContent };
}

export interface ConfigurableCatalogRecordSearchResponse {
  items: ConfigurableCatalogRecordResponse[];
  total_count: number;
  offset: number;
  limit: number;
  facets: Array<{
    attribute_definition_id: string;
    value: string;
    count: number;
  }>;
}

export interface ConfigurableCatalogRecordRevisionList {
  items: Array<RevisionMetadata & { content: ConfigurableCatalogRecordContent }>;
}

export interface ConfigurableCatalogRecordComparison {
  record_id: string;
  from_revision: RevisionMetadata & { content: ConfigurableCatalogRecordContent };
  to_revision: RevisionMetadata & { content: ConfigurableCatalogRecordContent };
  metadata_changed: boolean;
  value_differences: Array<{
    attribute_definition_id: string;
    status: "added" | "removed" | "changed" | "unchanged";
    before: ConfigurableRecordValue | null;
    after: ConfigurableRecordValue | null;
  }>;
}

export type ConfigurableLinkCardinality = "one" | "many";

export interface ConfigurableLinkTypeContent {
  key: string;
  name: string;
  source_table_id: string;
  source_table_revision_id: string;
  target_table_id: string;
  target_table_revision_id: string;
  forward_label: string;
  reverse_label: string;
  source_cardinality: ConfigurableLinkCardinality;
  target_cardinality: ConfigurableLinkCardinality;
  description: string | null;
}

export interface ConfigurableLinkTypeResponse {
  link_type_id: string;
  current_revision: RevisionMetadata & { content: ConfigurableLinkTypeContent };
}

export interface ConfigurableRecordLinkContent {
  link_type_id: string;
  link_type_revision_id: string;
  source_record_id: string;
  source_record_revision_id: string;
  target_record_id: string;
  target_record_revision_id: string;
  active: boolean;
  note: string | null;
}

export interface ConfigurableRecordLinkResponse {
  record_link_id: string;
  current_revision: RevisionMetadata & { content: ConfigurableRecordLinkContent };
}

export interface ConfigurableLinkEndpoint {
  record_id: string;
  record_revision_id: string;
  revision_no: number;
  table_id: string;
  name: string;
  external_key: string | null;
  domain_binding: DomainRevisionBinding | null;
}

export type DomainBindingKind =
  | "material"
  | "material_state"
  | "specimen"
  | "test_run"
  | "test_data"
  | "processing_output"
  | "material_model"
  | "neutral_material"
  | "solver_card"
  | "neutral_solver_card"
  | "release";

export interface DomainRevisionBinding {
  binding_id: string;
  record_id: string;
  record_revision_id: string;
  kind: DomainBindingKind;
  object_id: string;
  revision_id: string;
  workbench_path: string;
}

export interface ConfigurableRecordLinkView {
  record_link_id: string;
  current_revision: RevisionMetadata & { content: ConfigurableRecordLinkContent };
  link_type_revision: RevisionMetadata & { content: ConfigurableLinkTypeContent };
  source: ConfigurableLinkEndpoint;
  target: ConfigurableLinkEndpoint;
}

export interface CatalogExplorerChildrenResponse {
  table: ConfigurableTableResponse;
  folders: ConfigurableCatalogFolderResponse[];
  records: ConfigurableCatalogRecordResponse[];
}

export interface CatalogWorkflowGraphResponse {
  root: ConfigurableLinkEndpoint;
  nodes: ConfigurableLinkEndpoint[];
  links: ConfigurableRecordLinkView[];
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

export interface CommonChannelBinding {
  channel_key: string;
  target_quantity: string;
  accepted_normalized_units: string[];
  required: boolean;
  scale: number;
  offset: number;
}

export interface CommonAttributeBinding {
  attribute_definition_id: string;
  attribute_definition_revision_id: string;
  target_quantity: string;
  accepted_normalized_units: string[];
  required: boolean;
}

export interface CommonMappingProfileContent {
  profile_key: string;
  label: string;
  independent_quantity: string;
  missing_data_policy: "reject" | "drop_any";
  bindings: CommonChannelBinding[];
  attribute_bindings: CommonAttributeBinding[];
}

export interface CommonMappingProfileResponse {
  mapping_profile_id: string;
  current_revision: RevisionMetadata;
  content: CommonMappingProfileContent;
}

export interface CommonProcessingMethod {
  method_id: string;
  version: string;
  label: string;
  description: string;
  option_schema: Record<string, unknown>;
  deterministic: boolean;
  allows_extrapolation: boolean;
}

export interface CommonProcessingStep {
  method_id: string;
  method_version: string;
  options: Record<string, unknown>;
}

export interface CommonProcessingRecipeContent {
  recipe_key: string;
  label: string;
  description: string | null;
  mapping_profile_id: string;
  mapping_profile_revision_id: string;
  mapping_profile_sha256: string;
  steps: CommonProcessingStep[];
  lifecycle_state: "draft" | "published";
}

export interface CommonProcessingRecipeResponse {
  processing_recipe_id: string;
  current_revision: RevisionMetadata;
  content: CommonProcessingRecipeContent;
}

export interface CommonProcessingBatchSource {
  document_id: string;
  revision_id: string;
}

export interface CommonProcessingBatchPreflightMember {
  ordinal: number;
  source: CommonProcessingBatchSource;
  compatible: boolean;
  source_document_sha256: string | null;
  final_point_count: number | null;
  diagnostic: string | null;
}

export interface CommonProcessingBatchPreflight {
  recipe_id: string;
  recipe_revision_id: string;
  recipe_sha256: string;
  compatible: boolean;
  members: CommonProcessingBatchPreflightMember[];
}

export interface CommonProcessingBatchAttempt {
  attempt_id: string;
  member_id: string;
  attempt_no: number;
  status: "succeeded" | "failed";
  output_id: string | null;
  output_revision_id: string | null;
  error_code: string | null;
  error_detail: string | null;
  started_at: string;
  completed_at: string;
}

export interface CommonProcessingBatchResponse {
  batch_id: string;
  classification: DataClassification;
  label: string;
  recipe_id: string;
  recipe_revision_id: string;
  recipe_sha256: string;
  status: "planned" | "running" | "succeeded" | "partial" | "failed";
  members: Array<{
    member_id: string;
    ordinal: number;
    source: CommonProcessingBatchSource;
    source_document_sha256: string;
  }>;
  attempts: CommonProcessingBatchAttempt[];
  created_at: string;
  created_by: string;
}

export interface CommonCurveStage {
  ordinal: number;
  method_id: string;
  method_version: string;
  point_count: number;
  series: Array<{ quantity: string; unit: string; values: number[] }>;
  diagnostics: string[];
  scalar_results: Array<{
    key: string;
    quantity_semantics: string;
    value: number;
    unit: string;
  }>;
}

export type GraphSelectionCommand =
  | {
      kind: "range";
      x_quantity: string;
      x_unit: string;
      minimum: number;
      maximum: number;
    }
  | {
      kind: "point";
      x_quantity: string;
      x_unit: string;
      x: number;
      y_quantity: string;
      y_unit: string;
      y: number;
    };

export interface CommonProcessingPreview {
  execution_mode: "preview";
  promotable: false;
  source_document_sha256: string;
  mapping_profile_sha256: string;
  independent_quantity: string;
  stages: CommonCurveStage[];
}

export interface CommonExactRevisionPin {
  aggregate_id: string;
  revision_id: string;
}

export interface CommonProcessingOutputResponse {
  processing_output_id: string;
  current_revision: RevisionMetadata;
  label: string;
  source_document: CommonExactRevisionPin;
  source_document_sha256: string;
  source_canonical_artifact_sha256: string;
  mapping_profile: CommonExactRevisionPin;
  mapping_profile_sha256: string;
  steps: CommonProcessingStep[];
  independent_quantity: string;
  stage_count: number;
  final_point_count: number;
  output_artifact_id: string;
  output_sha256: string;
  workup_overrides: CommonProcessingWorkupOverride[];
  fit_decision: CommonProcessingFitDecision | null;
  export_provenance: CommonExportProvenance | null;
}

export interface CommonExportProvenance {
  material: CommonExactRevisionPin;
  material_state: CommonExactRevisionPin;
  test_run: CommonExactRevisionPin;
}

export interface CommonProcessingFitDecisionParameter {
  name: string;
  value: number;
  unit: string;
  lower: number | null;
  upper: number | null;
}

export interface CommonProcessingFitDecisionParameterSet {
  law: string;
  parameters: CommonProcessingFitDecisionParameter[];
}

export interface CommonProcessingFitDecision {
  candidate_key: string;
  mode: "single" | "blend";
  primary_law: string;
  secondary_law: string | null;
  primary_weight: number | null;
  parameter_sets: CommonProcessingFitDecisionParameterSet[];
  fit_minimum: number;
  fit_maximum: number;
  extrapolation_maximum: number | null;
  extrapolation_policy: string;
  metric_definition: string;
  metric_value: number;
  requested_term_policy: string | null;
  actual_term_count: number | null;
  selection_reason: string;
  warning_acknowledged: boolean;
}

export interface CommonProcessingWorkupOverride {
  kind: "youngs_modulus" | "necking_boundary";
  original_value: number;
  original_unit: string;
  canonical_value: number;
  canonical_unit: string;
  reason: string;
}

export interface CommonPointwiseStatistics {
  quantity: string;
  unit: string;
  mean: number[];
  median: number[];
  standard_deviation: number[];
  mad: number[];
  q1: number[];
  q3: number[];
  confidence_95_lower: number[];
  confidence_95_upper: number[];
}

export interface CommonEnsemblePreview {
  execution_mode: "preview";
  promotable: false;
  mapping_profile_sha256: string;
  independent_quantity: string;
  grid_unit: string;
  grid: number[];
  members: Array<{
    ordinal: number;
    source_document_sha256: string;
    stage: CommonCurveStage;
  }>;
  statistics: CommonPointwiseStatistics[];
  diagnostics: string[];
}
