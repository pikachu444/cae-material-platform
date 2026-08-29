import type { DataClassification } from "../../../shared/model/core-contracts";

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
  requested_by_display_name: string;
  requested_at: string;
  reason: string;
  lifecycle_state: LifecycleState;
  decision: ReviewDecisionResponse | null;
  links: Record<string, string>;
  evidence: ReviewSubjectEvidence | null;
}

export interface ReviewSubjectEvidence {
  subject_type: string;
  subject_id: string;
  subject_revision_id: string;
  label: string;
  classification: DataClassification;
  schema: { ref: string; version: string };
  server_manifest: { sha256: string };
  source_artifact: { state: "attached" | "unattached"; id: string | null; sha256: string | null };
  validation: { status: "valid" | "warning" | "blocked"; summary: string };
  created: { by: string; at: string };
  change_reason: string;
  exact_input_use: string[];
  affected_materials: { record_id: string | null; record_revision_id: string | null; path: string | null };
  affected_table_id: string | null;
  affected_table_revision_id: string | null;
  output_artifact_sha256: string | null;
  neutral: { material_id: string | null; material_revision_id: string | null; artifact_sha256: string | null };
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
