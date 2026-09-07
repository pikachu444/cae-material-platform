import type { DataClassification } from "../../../shared/model/core-contracts";

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

export interface DmaTtsRecommendationRequest {
  test_data: DmaTtsExactTestDataPin;
  import_profile: DmaTtsExactImportProfilePin;
}

export interface DmaTtsRecommendationResponse {
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

export type DmaTtsPartition = "CALIBRATION" | "HOLDOUT" | "EXCLUDED";

export interface CreateDmaTtsRequest {
  classification: DataClassification;
  label: string;
  test_data: DmaTtsExactTestDataPin;
  import_profile: DmaTtsExactImportProfilePin;
  dispositions: Array<{
    source_ordinal: number;
    partition: DmaTtsPartition;
    exclusion_reason: string | null;
  }>;
  shift_law: {
    kind: "wlf";
    reference_temperature_k: number;
    c1: number;
    c2_k: number;
    value_origin: "generic_wlf_at_tg_starting_suggestion" | "engineer_edited";
  };
  confirmation: { confirmed: true; reason: string };
  recommendation_sha256: string | null;
  change_reason: string;
}

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
  loss_modulus_output: DmaTtsOutputPin | null;
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
