import type { RevisionMetadata } from "../../../shared/model/core-contracts";

export type LinearViscoelasticPointPartition = "CALIBRATION" | "HOLDOUT" | "EXCLUDED";
export type LinearViscoelasticAvailability = "PROVIDED" | "NOT_PROVIDED";
export type LinearViscoelasticInputMode = "relaxation" | "dma" | "dma_frequency_master_curve";
export type LinearViscoelasticCandidateScopeMode = "automatic" | "manual";

export interface LinearViscoelasticExactRevision {
  id: string;
  revision_id: string;
}

export interface LinearViscoelasticCatalogContext {
  material: { id: string; revisionId: string };
  materialState: { id: string; revisionId: string };
  propertySet: { id: string; revisionId: string };
}

export interface LinearViscoelasticExactRevisionEvidence extends LinearViscoelasticExactRevision {
  sha256?: string | null;
}

export interface LinearViscoelasticPointDisposition {
  ordinal: number;
  partition: LinearViscoelasticPointPartition;
  exclusion_reason: string | null;
}

export interface LinearViscoelasticParameterBound {
  name: string;
  lower: number;
  start: number;
  upper: number;
  unit: "Pa" | "s";
  transform: "ln";
}

export type SerializedLinearViscoelasticParameterBound = Omit<LinearViscoelasticParameterBound, "lower" | "start" | "upper"> & {
  lower: string;
  start: string;
  upper: string;
};

export interface LinearViscoelasticAvailabilityMap {
  ramp: LinearViscoelasticAvailability;
  sweep: LinearViscoelasticAvailability;
  preconditioning: LinearViscoelasticAvailability;
  linear_range: LinearViscoelasticAvailability;
}

export interface LinearViscoelasticWeights {
  relaxation_weight: string;
  dma_storage_weight: string;
  dma_loss_weight: string;
  relaxation_scale_pa: string;
  dma_storage_scale_pa: string;
  dma_loss_scale_pa: string;
  q_rule_version: "equal_per_point@1.0.0";
}

export interface LinearViscoelasticOptimizer {
  method: "trf";
  x_scale: "jac";
  transform: "ln";
  ftol: number;
  xtol: number;
  gtol: number;
  max_nfev: number;
}

export interface LinearViscoelasticPlanRequestBase {
  setup_name: string;
  material: LinearViscoelasticExactRevision;
  material_state: LinearViscoelasticExactRevision;
  input_mode: LinearViscoelasticInputMode;
  candidate_scope_mode?: LinearViscoelasticCandidateScopeMode;
  based_on_plan_id?: string;
  based_on_plan_revision_id?: string;
  override_reason?: string;
  availability: LinearViscoelasticAvailabilityMap;
  term_counts?: number[];
  parameter_bounds?: Record<string, LinearViscoelasticParameterBound[]>;
  start_vectors?: Record<string, number[][]>;
  weights: LinearViscoelasticWeights;
  optimizer: LinearViscoelasticOptimizer;
  recommendation_policy: "lowest_bic_then_term_count_then_attempt_ordinal@1.0.0";
  change_reason: string;
}

export interface DirectLinearViscoelasticPlanRequest extends LinearViscoelasticPlanRequestBase {
  test_data: LinearViscoelasticExactRevision;
  selected_temperature_k: number;
  point_dispositions: LinearViscoelasticPointDisposition[];
}

export interface ProcessedLinearViscoelasticPlanRequest extends LinearViscoelasticPlanRequestBase {
  processing_output: LinearViscoelasticExactRevision;
}

export interface ProcessedLinearViscoelasticFitInput {
  mode: "dma_frequency_master_curve";
  coordinate_quantity: "frequency.angular.reduced";
  coordinate_unit: "rad/s";
  response_channels: Array<{
    channel: "dma_storage" | "dma_loss";
    quantity: "mechanics.modulus.storage" | "mechanics.modulus.loss";
    unit: "Pa";
  }>;
  reference_temperature_k: string;
  rows: Array<{
    ordinal: number;
    coordinate: number | null;
    storage_modulus_pa: number;
    loss_modulus_pa: number;
    partition: LinearViscoelasticPointPartition;
    exclusion_reason: string | null;
  }>;
}

export interface LinearViscoelasticPlanContent extends Record<string, unknown> {
  plan_id?: string;
  plan_revision_id?: string;
  test_data?: LinearViscoelasticExactRevision & { sha256?: string };
  processing_output?: LinearViscoelasticExactRevision & { sha256?: string };
  input_semantics?: {
    mode?: string;
    deformation_mode?: string;
    channels?: Array<{
      key?: string;
      quantity_semantics?: string;
      axis_role?: string;
      original_unit_string?: string;
      normalized_unit?: string;
    }>;
    point_dispositions?: LinearViscoelasticPointDisposition[];
    selected_temperature_k?: string | number | null;
    temperature_source?: string;
    frequency_kind?: string;
    angular_frequency_conversion?: string;
    source_kind?: string;
    processing_method?: string | null;
  };
  recommendation_policy?: string;
  term_counts?: number[];
  parameter_bounds?: Record<string, Array<LinearViscoelasticParameterBound | SerializedLinearViscoelasticParameterBound>>;
  start_vectors?: Record<string, number[][] | string[][]>;
  weights?: Partial<LinearViscoelasticWeights>;
  optimizer?: Partial<LinearViscoelasticOptimizer>;
  statuses?: Partial<LinearViscoelasticAvailabilityMap>;
  setup_name?: string;
  material?: LinearViscoelasticExactRevisionEvidence;
  material_state?: LinearViscoelasticExactRevisionEvidence;
  input_mode?: LinearViscoelasticInputMode;
  based_on_plan_id?: string | null;
  based_on_plan_revision_id?: string | null;
  override_reason?: string | null;
  base_diff?: Record<string, unknown> | null;
  candidate_scope_mode?: LinearViscoelasticCandidateScopeMode;
}

export interface LinearViscoelasticPlanResponse {
  plan_id: string;
  current_revision: RevisionMetadata & { content: LinearViscoelasticPlanContent };
  links: Record<string, string>;
}

export type LinearViscoelasticPlanApprovalState = "active" | "superseded" | "withdrawn";

export interface LinearViscoelasticPlanApproval {
  plan_id: string;
  plan_revision_id: string;
  plan_sha256: string;
  setup_name: string;
  input_mode: LinearViscoelasticInputMode;
  material: LinearViscoelasticExactRevisionEvidence;
  material_state: LinearViscoelasticExactRevisionEvidence;
  test_data: LinearViscoelasticExactRevisionEvidence;
  processing_output: LinearViscoelasticExactRevisionEvidence | null;
  state: LinearViscoelasticPlanApprovalState;
  review_request_id: string;
  review_decision_id: string;
  evidence_sha256: string;
  approved_at: string;
  approved_by: string;
  superseded_by_plan_id: string | null;
  superseded_by_plan_revision_id: string | null;
}

export interface LinearViscoelasticPlanContextRequest {
  material: LinearViscoelasticExactRevision;
  material_state: LinearViscoelasticExactRevision;
  test_data: LinearViscoelasticExactRevision;
  processing_output?: LinearViscoelasticExactRevision;
  input_mode: LinearViscoelasticInputMode;
}

export interface LinearViscoelasticPlanContextMatch {
  plan_id: string;
  plan_revision_id: string;
  plan_sha256: string;
  setup_name: string;
  input_mode: LinearViscoelasticInputMode;
  material: LinearViscoelasticExactRevisionEvidence;
  material_state: LinearViscoelasticExactRevisionEvidence;
  test_data: LinearViscoelasticExactRevisionEvidence;
  processing_output: LinearViscoelasticExactRevisionEvidence | null;
  approval: LinearViscoelasticPlanApproval;
}

export interface LinearViscoelasticPlanContextResponse {
  summary: string;
  selection_required: boolean;
  matches: LinearViscoelasticPlanContextMatch[];
}

export interface LinearViscoelasticRunAcceptedResponse {
  run_id: string;
  job_id: string;
  run_url: string;
  job_url: string;
  status: "queued" | string;
}

export interface LinearViscoelasticCandidate {
  candidate_id: string;
  candidate_sha256: string;
  attempt_ordinal: number;
  term_count: number;
  physical_parameters: number[];
  transformed_parameters: number[];
  rss: number;
  bic: number;
  calibration_residuals: number[];
  holdout_residuals: number[];
  rank: {
    singular_values?: number[];
    sigma_max?: number;
    threshold?: number;
    rank?: number;
    status?: string;
    warning_code?: string | null;
  };
  warnings: string[];
  uncertainty_status: "NOT_PROVIDED" | string;
}

export interface LinearViscoelasticAttempt {
  ordinal: number;
  term_count: number;
  start_vector?: number[];
  transformed_start_vector?: number[];
  status?: number;
  message?: string;
  nfev?: number;
  cost?: number;
  optimality?: number;
  active_mask?: number[];
  physical_parameters?: number[];
  transformed_parameters?: number[];
  rss?: number;
  rank?: LinearViscoelasticCandidate["rank"];
  warnings?: string[];
  converged?: boolean;
  physical?: boolean;
}

export interface LinearViscoelasticRecommendation {
  recommendation_id: string;
  candidate_id: string;
  candidate_digest: string;
  rule_version: string;
}

export interface LinearViscoelasticRunResponse {
  run_id: string;
  plan_revision_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "retrying" | string;
  attempts: LinearViscoelasticAttempt[];
  candidates: LinearViscoelasticCandidate[];
  recommendation: LinearViscoelasticRecommendation | null;
  failure_code: string | null;
  failure_detail: string | null;
  recovery_hint: string | null;
  execution_ledger_sha256: string;
  approval_request_id?: string | null;
  approval_decision_id?: string | null;
  approval_evidence_sha256?: string | null;
  approval_state?: LinearViscoelasticPlanApprovalState | null;
  approval_approved_at?: string | null;
  approval_approved_by?: string | null;
  execution_context?: Record<string, unknown> | null;
}

export type LinearViscoelasticResponseChannel = "relaxation" | "dma_storage" | "dma_loss";

export interface LinearViscoelasticResponseResidualEvidence {
  run_id: string;
  plan_revision_id: string;
  recommendation: {
    recommendation_id: string;
    candidate_id: string;
    candidate_sha256: string;
    rule_version: "linear_viscoelastic_bic@1.0.0";
  };
  artifact: {
    artifact_id: string;
    sha256: string;
    artifact_role: "response-residuals";
    schema_ref: "urn:cmp:modeling:linear-viscoelastic-calibration-response-residuals:1.0.0";
    media_type: "application/vnd.apache.parquet";
    size_bytes: number;
  };
  rows: Array<{
    ordinal: number;
    channel: LinearViscoelasticResponseChannel;
    observed: number;
    predicted: number;
    residual: number;
    partition: LinearViscoelasticPointPartition;
  }>;
}

export interface LinearViscoelasticSelectionRequest {
  plan_revision_id: string;
  run_id: string;
  candidate_id: string;
  candidate_sha256: string;
  reason: string;
  warning_acknowledgements: Array<Record<string, unknown>>;
  change_reason: string;
}

export interface LinearViscoelasticSelectionResponse {
  selection_id: string;
  selection_revision_id: string;
  plan_revision_id: string;
  run_id: string;
  candidate_id: string;
  candidate_sha256: string;
  reason: string;
  warning_acknowledgements: Array<Record<string, unknown>>;
  actor: string;
  created_at: string;
}
