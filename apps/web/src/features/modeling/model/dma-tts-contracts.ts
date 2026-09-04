import type { DataClassification } from "../../../shared/model/core-contracts";

export type DmaTtsInputMode =
  | "fixed_frequency_temperature_sweep"
  | "multi_frequency_isotherms";

export type DmaTtsPartition = "CALIBRATION" | "HOLDOUT" | "EXCLUDED";

export interface DmaTtsExactTestDataPin {
  document_id: string;
  revision_id: string;
  content_sha256: string;
}

export interface DmaTtsExactImportProfilePin {
  profile_id: string;
  revision_id: string;
  content_sha256: string;
}

/** The exact lineage shape returned by the saved-output read-back endpoint. */
export interface DmaTtsExactLineagePin {
  document_id: string;
  revision_id: string;
  content_sha256: string;
}

export interface DmaTtsRecommendationRequest {
  test_data: DmaTtsExactTestDataPin;
  import_profile: DmaTtsExactImportProfilePin;
}

export interface DmaTtsMultiRecommendationRequest extends DmaTtsRecommendationRequest {
  reference_sweep_ordinal: number;
}

export interface DmaTtsRecommendationResponse {
  input_mode?: "fixed_frequency_temperature_sweep";
  source_evidence: Record<string, unknown>;
  reference_temperature_k: number;
  source_ordinal: number;
  c1: number;
  c2_k: number;
  value_origin: "generic_wlf_at_tg_starting_suggestion";
  material_specific: false;
  requires_confirmation: true;
  rule_id: "polymer.dma_wlf_starting_suggestion";
  rule_version: "1.0.0";
  recommendation_sha256: string;
}

export interface DmaTtsMultiSourceEvidence {
  test_data_document_id: string;
  test_data_revision_id: string;
  test_data_content_sha256: string;
  import_profile_id: string;
  import_profile_revision_id: string;
  import_profile_content_sha256: string;
  source_normalized_artifact_id: string;
  source_normalized_artifact_sha256: string;
}

export interface DmaTtsSweepSummary {
  source_sweep_ordinal: number;
  representative_temperature_k: number;
  point_count: number;
  source_frequency_min_hz: number;
  source_frequency_max_hz: number;
}

export interface DmaTtsSweepDisposition {
  source_sweep_ordinal: number;
  representative_temperature_k: number;
  partition: DmaTtsPartition;
  exclusion_reason: string | null;
}

export interface DmaTtsMultiWlfShiftLaw {
  kind: "wlf_fit";
  reference_temperature_k: number;
  initial_parameters: number[];
  lower_bounds: number[];
  upper_bounds: number[];
}

export interface DmaTtsMultiScoring {
  minimum_overlap_decades: number;
  scoring_point_count: number;
  storage_weight: number;
  loss_weight: number;
}

export interface DmaTtsAdjacentOptimizer {
  relative_shift_lower_bound_log10: number;
  relative_shift_upper_bound_log10: number;
  xatol: number;
  maxiter: number;
  seed: null;
}

export interface DmaTtsLawOptimizer {
  initial_parameters: number[];
  lower_bounds: number[];
  upper_bounds: number[];
  ftol: number;
  xtol: number;
  gtol: number;
  max_nfev: number;
  seed: null;
}

export interface DmaTtsMultiRecommendationResponse {
  input_mode: "multi_frequency_isotherms";
  source_evidence: DmaTtsMultiSourceEvidence;
  sweeps: DmaTtsSweepSummary[];
  reference_sweep_ordinal: number;
  reference_temperature_k: number;
  sweep_dispositions: DmaTtsSweepDisposition[];
  shift_law: DmaTtsMultiWlfShiftLaw;
  scoring: DmaTtsMultiScoring;
  adjacent_optimizer: DmaTtsAdjacentOptimizer;
  law_optimizer: DmaTtsLawOptimizer;
  profile_id: "cmp.dma_tts.multi_frequency_wlf_starting_profile";
  profile_version: "1.0.0";
  material_specific: false;
  production_readiness: "non_production";
  requires_confirmation: true;
  recommendation_sha256: string;
}

export interface DmaTtsFixedRowDisposition {
  source_ordinal: number;
  partition: DmaTtsPartition;
  exclusion_reason: string | null;
}

export type DmaTtsFixedShiftLaw =
  | {
      kind: "wlf";
      reference_temperature_k: number;
      c1: number;
      c2_k: number;
    }
  | {
      kind: "arrhenius";
      reference_temperature_k: number;
      activation_energy_j_per_mol: number;
    }
  | {
      kind: "manual_tabulated";
      reference_temperature_k: number;
      manual_table: Array<{ temperature_k: number; log10_a_t: number }>;
    };

interface CreateDmaTtsRequestCommon {
  classification: DataClassification;
  label: string;
  test_data: DmaTtsExactTestDataPin;
  import_profile: DmaTtsExactImportProfilePin;
  confirmation: { confirmed: true; reason: string };
  change_reason: string;
}

export interface CreateFixedDmaTtsRequest extends CreateDmaTtsRequestCommon {
  input_mode: "fixed_frequency_temperature_sweep";
  row_dispositions: DmaTtsFixedRowDisposition[];
  shift_law: DmaTtsFixedShiftLaw;
  recommendation_sha256: string | null;
}

export type DmaTtsMultiShiftLawRequest =
  | DmaTtsMultiWlfShiftLaw
  | {
      kind: "arrhenius_fit";
      reference_temperature_k: number;
      initial_parameters: number[];
      lower_bounds: number[];
      upper_bounds: number[];
    }
  | {
      kind: "manual_tabulated";
      reference_temperature_k: number;
      manual_table: Array<{ temperature_k: number; log10_a_t: number }>;
    };

export interface CreateMultiDmaTtsRequest extends CreateDmaTtsRequestCommon {
  input_mode: "multi_frequency_isotherms";
  sweep_dispositions: DmaTtsSweepDisposition[];
  reference_sweep_ordinal: number;
  shift_law: DmaTtsMultiShiftLawRequest;
  scoring: DmaTtsMultiScoring;
  adjacent_optimizer: DmaTtsAdjacentOptimizer;
  law_optimizer: DmaTtsLawOptimizer | null;
  recommendation_sha256: string | null;
}

export type CreateDmaTtsRequest = CreateFixedDmaTtsRequest | CreateMultiDmaTtsRequest;

export interface DmaTtsOutputPin {
  output_id: string;
  revision_id: string;
  content_sha256: string;
  metadata_artifact_id: string;
  metadata_sha256: string;
  result_artifact_id: string;
  result_sha256: string;
  result_schema_ref: string;
  result_media_type: "application/vnd.apache.parquet";
}

export interface CreateDmaTtsResponse {
  master_curve_output: DmaTtsOutputPin;
}

export interface DmaTemperatureSweepRow {
  ordinal: number;
  temperatureK: number;
  storageModulusPa: number;
  lossModulusPa: number;
}

export interface DmaTemperatureSweepSnapshot {
  frequencyHz: number;
  rows: DmaTemperatureSweepRow[];
}

export interface DmaFrequencySweepPoint {
  sourceOrdinal: number;
  temperatureK: number;
  frequencyHz: number;
  storageModulusPa: number;
  lossModulusPa: number;
}

export interface DmaFrequencySweepSnapshot {
  sourceSweepOrdinal: number;
  representativeTemperatureK: number;
  points: DmaFrequencySweepPoint[];
  sourceFrequencyMinHz: number;
  sourceFrequencyMaxHz: number;
}

export interface DmaTtsMultiSourceSnapshot {
  inputMode: "multi_frequency_isotherms";
  sweeps: DmaFrequencySweepSnapshot[];
}

export type DmaTtsSourceClassification =
  | { kind: "fixed"; source: DmaTemperatureSweepSnapshot; reason: null }
  | { kind: "multi"; source: DmaTtsMultiSourceSnapshot; reason: null }
  | { kind: "direct"; reason: null }
  | { kind: "blocked"; reason: string };

export interface DmaTtsIsotherm {
  input_mode: DmaTtsInputMode;
  source_sweep_ordinal: number | null;
  representative_temperature_k: number;
  partition: DmaTtsPartition;
  is_reference: boolean;
  exclusion_reason: string | null;
  holdout_evaluation_status: string | null;
  source_ordinals: number[];
  measured_temperature_k: number[];
  source_frequency_hz: number[];
  angular_frequency_rad_per_s: number[];
  storage_modulus_pa: number[];
  loss_modulus_pa: number[];
  source_tan_delta: Array<number | null>;
  loss_modulus_origin: string[];
  reduced_angular_frequency_rad_per_s: number[] | null;
  raw_angular_frequency_min_rad_per_s: number;
  raw_angular_frequency_max_rad_per_s: number;
  shifted_angular_frequency_min_rad_per_s: number | null;
  shifted_angular_frequency_max_rad_per_s: number | null;
  comparison_sweep_ordinal: number | null;
  observed_log10_a_t: number | null;
  applied_log10_a_t: number | null;
  shift_factor: number | null;
  shift_residual_log10_a_t: number | null;
  overlap_log10_reduced_angular_frequency_min: number | null;
  overlap_log10_reduced_angular_frequency_max: number | null;
  scoring_point_count: number | null;
  storage_mse: number | null;
  loss_mse: number | null;
  storage_rmse: number | null;
  loss_rmse: number | null;
  weighted_mse: number | null;
  adjacent_success: boolean | null;
  adjacent_status: number | null;
  adjacent_iterations: number | null;
  adjacent_evaluations: number | null;
  adjacent_objective: number | null;
}

export interface DmaTtsResultInterval {
  minimum: number;
  maximum: number;
}

export interface DmaTtsApplicationRange {
  basis: "at_least_two_shifted_calibration_isotherms";
  holdout_included: false;
  reduced_angular_frequency_intervals_rad_per_s: DmaTtsResultInterval[];
  calibration_temperature_interval_k: DmaTtsResultInterval;
}

export interface DmaTtsResultAssessment {
  adequacy: "not_assessed";
  uncertainty: "not_provided";
  identifiability: "not_assessed";
  production_readiness: "non_production";
}

export interface DmaTtsResultShiftLaw {
  kind: "wlf" | "wlf_fit" | "arrhenius" | "arrhenius_fit" | "manual_tabulated";
  reference_temperature_k: number;
}

export interface DmaTtsReadResponse {
  output: DmaTtsOutputPin;
  input_mode: DmaTtsInputMode;
  options: Record<string, unknown> & {
    input_mode?: DmaTtsInputMode;
    recommendation?: Record<string, unknown> | null;
    shift_law?: DmaTtsResultShiftLaw;
    application_range?: DmaTtsApplicationRange | null;
    assessment?: DmaTtsResultAssessment;
    warnings?: string[];
  };
  isotherms: DmaTtsIsotherm[];
  test_data: DmaTtsExactTestDataPin;
  import_profile: DmaTtsExactLineagePin;
}
