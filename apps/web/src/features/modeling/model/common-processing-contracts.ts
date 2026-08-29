import type {
  DataClassification,
  RevisionMetadata,
} from "../../../shared/model/core-contracts";
import type {
  CurveDefinitionContract,
  CurveMetadataState,
  CurveSeriesPreviewContract,
} from "../../../shared/model/curve-contracts";
import type {
  CommonExactRevisionPin,
  CommonExportProvenance,
} from "./exact-revision-contracts";

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
  fit_candidates?: CommonHardeningCandidate[];
  /** Present on API 0.35.0 responses; optional here for cached 0.34 fixtures. */
  metadata_state?: CurveMetadataState;
  curve_definition_sha256?: string;
  curve_definition?: CurveDefinitionContract;
  curve_series?: CurveSeriesPreviewContract;
}

export interface CommonHardeningCandidate {
  family: string;
  response: number[];
  residual: number[];
  tangent: Array<number | null>;
  parameter_names: string[];
  parameter_units: string[];
  lower: number[];
  initial: number[];
  fitted: number[];
  upper: number[];
  rmse_pa: number;
  relative_rmse: number;
  objective: number;
  scipy_cost: number;
  convergence: boolean;
  nfev: number;
  active_bound: string[];
  jacobian_rank: number;
  jacobian_tolerance: number;
  jacobian_condition: number | null;
  identifiability: string;
  uncertainty: string;
  objective_history: number[];
  optimizer_status?: number;
  optimizer_message?: string;
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

export interface MetalFitRunAttemptResponse {
  id: string;
  run_id: string;
  ordinal: number;
  family: string;
  status: "executing" | "succeeded" | "failed" | "cancelled" | string;
  result: Record<string, unknown> | null;
  objective_history: number[];
  failure_code: string | null;
  failure_reason: string | null;
}

export interface MetalFitRunResponse {
  id: string;
  classification: DataClassification;
  source_processing_output: CommonExactRevisionPin;
  source_processing_output_sha256: string;
  source_document: CommonExactRevisionPin;
  mapping_profile: CommonExactRevisionPin;
  options: Record<string, unknown>;
  reproducibility_evidence: Record<string, unknown>;
  status: string;
  failure_code: string | null;
  failure_reason: string | null;
  attempts: MetalFitRunAttemptResponse[];
  preview: CommonProcessingPreview | null;
  created_by?: string | null;
  request_id?: string | null;
  trace_id?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
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
  source_processing_output?: CommonExactRevisionPin | null;
  source_processing_output_sha256?: string | null;
  workup_overrides: CommonProcessingWorkupOverride[];
  fit_decision: CommonProcessingFitDecision | null;
  export_provenance: CommonExportProvenance | null;
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
  /** Present on API 0.35.0 responses; optional here for cached 0.34 fixtures. */
  metadata_state?: CurveMetadataState;
  curve_definition_sha256?: string;
  curve_definition?: CurveDefinitionContract;
  curve_series?: CurveSeriesPreviewContract;
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
