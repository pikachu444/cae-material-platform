export type CurveMetadataState = "declared" | "legacy_compatible" | "absent";
export type CurveAxisRole = "independent" | "dependent" | "auxiliary";
export type CurveDeviationScope = "channel_scalar" | "pointwise";
export type CurveDeviationKind =
  | "standard_deviation"
  | "standard_error"
  | "confidence_bound"
  | "prediction_bound"
  | "tolerance_bound"
  | "quantile"
  | "median_absolute_deviation"
  | "interquartile_range"
  | "range_bound"
  | "coefficient_of_variation";

export interface CurveOriginalUnitContract {
  unit: string;
  scale_to_normalized: string;
  offset_to_normalized: string;
}

export interface CurveChannelContract {
  key: string;
  label: string;
  quantity_semantics: string;
  axis_role: CurveAxisRole;
  unit_contract: "common" | "explicit_legacy";
  dimension: string | null;
  original_units: CurveOriginalUnitContract[];
  normalized_unit: string;
  display_unit: string;
  display_scale: string;
  display_offset: string;
  value_basis: "original" | "normalized" | "derived";
}

export interface CurveDeviationContract {
  key: string;
  target_channel_key: string;
  scope: CurveDeviationScope;
  kind: CurveDeviationKind;
  method_id: string;
  method_version: string;
  unit: string;
  bound_direction: "none" | "lower" | "upper";
  band_group: string | null;
  scalar_value: string | null;
  series_key: string | null;
  source_count: number | null;
  source_count_series_key: string | null;
  confidence_level: number | null;
  coverage: "pointwise" | "simultaneous" | null;
  ddof: number | null;
  quantile_probability: number | null;
  quantile_method: string | null;
}

export interface CurveDefinitionContract {
  definition_version: "1.0.0";
  channels: CurveChannelContract[];
  deviations: CurveDeviationContract[];
}

export interface CurveSeriesPreviewContract {
  point_count: number;
  returned_point_count: number;
  sampled: boolean;
  indices: number[];
  channels: Array<{ key: string; values: Array<number | null> }>;
  deviations: Array<{ key: string; values: Array<number | null> }>;
  source_counts: Array<{ key: string; values: number[] }>;
}

export interface CurveMetadataContract {
  contract_version: "1.0.0";
  metadata_state: CurveMetadataState;
  definition_sha256: string | null;
  definition: CurveDefinitionContract | null;
  owning_revision: { entity_type: string; entity_id: string; revision_id: string };
  artifact: { artifact_id: string; sha256: string; schema_ref: string | null; media_type: string };
  sources: Array<{
    entity_type: string;
    entity_id: string;
    revision_id: string;
    artifact_id: string | null;
    artifact_sha256: string | null;
  }>;
  provenance: Array<{
    kind: "input_usage" | "generation_activity" | "calculation_plan" | "calculation_run" | "calculation_result";
    entity_id: string;
    revision_id: string | null;
  }>;
}
