import { quantityLabel } from "./engineering-labels";
/**
 * Display-only copy of the pure contract helpers from
 * apps/web/src/curve-contract.ts and its Curve*Contract types. The new app
 * intentionally does not import the legacy plot component, CSS, or
 * owning_revision metadata, while retaining the scientific unit and
 * deviation semantics required by the reader.
 */

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
  // Retained for the production contract, but not used for TestData/Card
  // identity or navigation in this reader.
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

export interface CurveDisplayBand {
  group: string;
  lower: CurveDeviationContract;
  upper: CurveDeviationContract;
  lowerValues: Array<number | null>;
  upperValues: Array<number | null>;
  label: string;
}

export interface CurveResolvedBand extends Omit<CurveDisplayBand, "lowerValues" | "upperValues"> {
  lowerValues: Array<number | null>;
  upperValues: Array<number | null>;
}

export interface CurveDisplayModel {
  definition: CurveDefinitionContract;
  series: CurveSeriesPreviewContract;
  independent: CurveChannelContract;
  dependent: CurveChannelContract;
  auxiliary: CurveChannelContract[];
  xValues: Array<number | null>;
  yValues: Array<number | null>;
  band: CurveDisplayBand | null;
}

export interface CurveChannelPair {
  independent: CurveChannelContract;
  dependent: CurveChannelContract;
  xValues: Array<number | null>;
  yValues: Array<number | null>;
}

const DEVIATION_LABELS: Record<CurveDeviationContract["kind"], string> = {
  standard_deviation: "standard deviation",
  standard_error: "standard error",
  confidence_bound: "confidence interval",
  prediction_bound: "prediction interval",
  tolerance_bound: "tolerance interval",
  quantile: "quantile",
  median_absolute_deviation: "median absolute deviation",
  interquartile_range: "interquartile range",
  range_bound: "range",
  coefficient_of_variation: "coefficient of variation",
};

function exactNumber(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

export function displayCurveValue(channel: CurveChannelContract, value: number | null): number | null {
  if (value === null) return null;
  const displayed = value * exactNumber(channel.display_scale) + exactNumber(channel.display_offset);
  return Number.isFinite(displayed) ? displayed : null;
}

export function displayCurveMagnitude(channel: CurveChannelContract, value: number | null): number | null {
  if (value === null) return null;
  const displayed = value * exactNumber(channel.display_scale);
  return Number.isFinite(displayed) ? displayed : null;
}

export function channelAxisLabel(channel: CurveChannelContract): string {
  return `${quantityLabel(channel.quantity_semantics)} [${channel.display_unit}]`;
}

export function channelForQuantity(
  definition: CurveDefinitionContract | null | undefined,
  quantitySemantics: string,
  preferredRole?: CurveChannelContract["axis_role"],
): CurveChannelContract | null {
  if (!definition) return null;
  return definition.channels.find((channel) => channel.quantity_semantics === quantitySemantics && (!preferredRole || channel.axis_role === preferredRole)) ?? null;
}

function percentage(level: number): string {
  const value = level * 100;
  return `${Number.isInteger(value) ? value.toFixed(0) : value.toPrecision(4)}%`;
}

export function deviationMeaning(deviation: CurveDeviationContract): string {
  const qualifiers: string[] = [];
  if (deviation.confidence_level !== null) qualifiers.push(percentage(deviation.confidence_level));
  if (deviation.coverage !== null) qualifiers.push(deviation.coverage);
  qualifiers.push(DEVIATION_LABELS[deviation.kind]);
  qualifiers.push(`${deviation.method_id} v${deviation.method_version}`);
  if (deviation.ddof !== null) qualifiers.push(`ddof ${deviation.ddof}`);
  if (deviation.quantile_probability !== null) qualifiers.push(`q=${deviation.quantile_probability}`);
  if (deviation.quantile_method !== null) qualifiers.push(deviation.quantile_method);
  return qualifiers.join(" · ");
}

export function deviationSourceCount(
  deviation: CurveDeviationContract,
  series: CurveSeriesPreviewContract,
  pointIndex = 0,
): number | null {
  if (deviation.source_count !== null) return deviation.source_count;
  if (!deviation.source_count_series_key) return null;
  return series.source_counts.find((item) => item.key === deviation.source_count_series_key)?.values[pointIndex] ?? null;
}

export function resolveDeviationBand(
  definition: CurveDefinitionContract,
  series: CurveSeriesPreviewContract,
  dependent: CurveChannelContract,
): CurveResolvedBand | null {
  const groups = new Map<string, CurveDeviationContract[]>();
  definition.deviations
    .filter((item) => item.target_channel_key === dependent.key && item.band_group)
    .forEach((item) => groups.set(item.band_group!, [...(groups.get(item.band_group!) ?? []), item]));
  const orderedGroups = [...groups.entries()].sort(([, left], [, right]) => {
    const priority = (items: CurveDeviationContract[]) => {
      const kind = items[0]?.kind;
      return kind === "confidence_bound" ? 0 : kind === "prediction_bound" ? 1 : kind === "tolerance_bound" ? 2 : kind === "quantile" ? 3 : 4;
    };
    return priority(left) - priority(right);
  });
  for (const [group, items] of orderedGroups) {
    const lower = items.find((item) => item.bound_direction === "lower" && item.series_key);
    const upper = items.find((item) => item.bound_direction === "upper" && item.series_key);
    if (!lower || !upper) continue;
    const lowerSeries = series.deviations.find((item) => item.key === lower.series_key);
    const upperSeries = series.deviations.find((item) => item.key === upper.series_key);
    if (!lowerSeries || !upperSeries) continue;
    return { group, lower, upper, lowerValues: lowerSeries.values, upperValues: upperSeries.values, label: deviationMeaning(lower) };
  }
  return null;
}

function isFiniteOrNull(value: unknown): value is number | null {
  return value === null || (typeof value === "number" && Number.isFinite(value));
}

function isCurveDefinitionShape(value: unknown): value is CurveDefinitionContract {
  if (!value || typeof value !== "object") return false;
  const definition = value as Partial<CurveDefinitionContract>;
  if (definition.definition_version !== "1.0.0" || !Array.isArray(definition.channels) || !Array.isArray(definition.deviations)) return false;
  const channelsValid = definition.channels.every((channel) => {
    if (!channel || typeof channel !== "object") return false;
    const item = channel as Partial<CurveChannelContract>;
    return typeof item.key === "string"
      && typeof item.label === "string"
      && typeof item.quantity_semantics === "string"
      && (item.axis_role === "independent" || item.axis_role === "dependent" || item.axis_role === "auxiliary")
      && (item.unit_contract === "common" || item.unit_contract === "explicit_legacy")
      && (item.dimension === null || typeof item.dimension === "string")
      && Array.isArray(item.original_units)
      && item.original_units.every((unit) => unit && typeof unit.unit === "string" && typeof unit.scale_to_normalized === "string" && typeof unit.offset_to_normalized === "string")
      && typeof item.normalized_unit === "string"
      && typeof item.display_unit === "string"
      && typeof item.display_scale === "string"
      && typeof item.display_offset === "string"
      && (item.value_basis === "original" || item.value_basis === "normalized" || item.value_basis === "derived");
  });
  const deviationsValid = definition.deviations.every((deviation) => {
    if (!deviation || typeof deviation !== "object") return false;
    const item = deviation as Partial<CurveDeviationContract>;
    return typeof item.key === "string"
      && typeof item.target_channel_key === "string"
      && typeof item.method_id === "string"
      && typeof item.method_version === "string"
      && typeof item.unit === "string"
      && (item.bound_direction === "none" || item.bound_direction === "lower" || item.bound_direction === "upper")
      && (item.scope === "channel_scalar" || item.scope === "pointwise")
      && typeof item.kind === "string"
      && item.kind in DEVIATION_LABELS
      && (item.band_group === null || typeof item.band_group === "string")
      && (item.scalar_value === null || typeof item.scalar_value === "string")
      && (item.series_key === null || typeof item.series_key === "string")
      && (item.source_count === null || typeof item.source_count === "number")
      && (item.source_count_series_key === null || typeof item.source_count_series_key === "string")
      && (item.confidence_level === null || typeof item.confidence_level === "number")
      && (item.coverage === null || item.coverage === "pointwise" || item.coverage === "simultaneous")
      && (item.ddof === null || typeof item.ddof === "number")
      && (item.quantile_probability === null || typeof item.quantile_probability === "number")
      && (item.quantile_method === null || typeof item.quantile_method === "string");
  });
  return channelsValid && deviationsValid;
}

function isCurveSeriesShape(value: unknown): value is CurveSeriesPreviewContract {
  if (!value || typeof value !== "object") return false;
  const series = value as Partial<CurveSeriesPreviewContract>;
  const pointCount = series.point_count;
  const returnedPointCount = series.returned_point_count;
  if (typeof pointCount !== "number" || typeof returnedPointCount !== "number" || !Number.isInteger(pointCount) || !Number.isInteger(returnedPointCount) || pointCount < 0 || returnedPointCount < 0 || typeof series.sampled !== "boolean") return false;
  if (!Array.isArray(series.indices) || !series.indices.every((index) => Number.isInteger(index))) return false;
  if (!Array.isArray(series.channels) || !series.channels.every((channel) => channel && typeof channel.key === "string" && Array.isArray(channel.values) && channel.values.every(isFiniteOrNull))) return false;
  if (!Array.isArray(series.deviations) || !series.deviations.every((deviation) => deviation && typeof deviation.key === "string" && Array.isArray(deviation.values) && deviation.values.every(isFiniteOrNull))) return false;
  return Array.isArray(series.source_counts) && series.source_counts.every((count) => count && typeof count.key === "string" && Array.isArray(count.values) && count.values.every((item) => Number.isFinite(item)));
}

export function curveDisplayModel(
  definition: CurveDefinitionContract | null | undefined,
  series: CurveSeriesPreviewContract | null | undefined,
  dependentKey?: string,
): CurveDisplayModel | null {
  if (!isCurveDefinitionShape(definition) || !isCurveSeriesShape(series)) return null;
  const independent = definition.channels.find((item) => item.axis_role === "independent");
  const dependents = definition.channels.filter((item) => item.axis_role === "dependent");
  const dependent = dependentKey
    ? dependents.find((item) => item.key === dependentKey)
    : dependents.length === 1 ? dependents[0] : dependents[0];
  if (!independent || !dependent) return null;
  const xSeries = series.channels.find((item) => item.key === independent.key);
  const ySeries = series.channels.find((item) => item.key === dependent.key);
  if (!xSeries || !ySeries || xSeries.values.length !== ySeries.values.length) return null;
  const resolvedBand = resolveDeviationBand(definition, series, dependent);
  return {
    definition,
    series,
    independent,
    dependent,
    auxiliary: definition.channels.filter((item) => item.axis_role === "auxiliary"),
    xValues: xSeries.values.map((value) => displayCurveValue(independent, value)),
    yValues: ySeries.values.map((value) => displayCurveValue(dependent, value)),
    band: resolvedBand ? {
      ...resolvedBand,
      lowerValues: resolvedBand.lowerValues.map((value) => displayCurveValue(dependent, value)),
      upperValues: resolvedBand.upperValues.map((value) => displayCurveValue(dependent, value)),
    } : null,
  };
}

/**
 * Resolve a declared x/y pair without guessing from returned array order.
 * When a definition exposes more than one dependent channel the caller must
 * pass the selected key so the product can make that choice visible.
 */
export function curveChannelPair(
  definition: CurveDefinitionContract | null | undefined,
  series: CurveSeriesPreviewContract | null | undefined,
  dependentKey?: string,
): CurveChannelPair | null {
  if (!isCurveDefinitionShape(definition) || !isCurveSeriesShape(series)) return null;
  const independent = definition.channels.find((item) => item.axis_role === "independent");
  const dependents = definition.channels.filter((item) => item.axis_role === "dependent");
  if (!independent || dependents.length === 0) return null;
  const dependent = dependentKey ? dependents.find((item) => item.key === dependentKey) : dependents.length === 1 ? dependents[0] : null;
  if (!dependent) return null;
  const xSeries = series.channels.find((item) => item.key === independent.key);
  const ySeries = series.channels.find((item) => item.key === dependent.key);
  if (!xSeries || !ySeries || xSeries.values.length !== ySeries.values.length || xSeries.values.length === 0) return null;
  return {
    independent,
    dependent,
    xValues: xSeries.values.map((value) => displayCurveValue(independent, value)),
    yValues: ySeries.values.map((value) => displayCurveValue(dependent, value)),
  };
}

export function originalUnitSummary(channel: CurveChannelContract): string {
  return [...new Set(channel.original_units.map((item) => item.unit))].join(", ") || "not recorded";
}

export function curveSegments(
  xValues: Array<number | null>,
  yValues: Array<number | null>,
): Array<Array<{ x: number; y: number }>> {
  const segments: Array<Array<{ x: number; y: number }>> = [];
  let current: Array<{ x: number; y: number }> = [];
  for (let index = 0; index < Math.min(xValues.length, yValues.length); index += 1) {
    const x = xValues[index];
    const y = yValues[index];
    if (x === null || y === null || !Number.isFinite(x) || !Number.isFinite(y)) {
      if (current.length) segments.push(current);
      current = [];
      continue;
    }
    current.push({ x, y });
  }
  if (current.length) segments.push(current);
  return segments;
}

export function formatEngineeringNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 4, useGrouping: true }).format(value);
}
