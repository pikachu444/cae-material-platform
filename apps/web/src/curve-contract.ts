import type {
  CurveChannelContract,
  CurveDefinitionContract,
  CurveDeviationContract,
  CurveSeriesPreviewContract,
} from "./types";

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

export function displayCurveValue(
  channel: CurveChannelContract,
  value: number | null,
): number | null {
  if (value === null) return null;
  const scale = exactNumber(channel.display_scale);
  const offset = exactNumber(channel.display_offset);
  const displayed = value * scale + offset;
  return Number.isFinite(displayed) ? displayed : null;
}

export function displayCurveMagnitude(
  channel: CurveChannelContract,
  value: number | null,
): number | null {
  if (value === null) return null;
  const displayed = value * exactNumber(channel.display_scale);
  return Number.isFinite(displayed) ? displayed : null;
}

export function channelAxisLabel(channel: CurveChannelContract): string {
  return `${channel.label} [${channel.display_unit}]`;
}

export function channelForQuantity(
  definition: CurveDefinitionContract | null | undefined,
  quantitySemantics: string,
  preferredRole?: CurveChannelContract["axis_role"],
): CurveChannelContract | null {
  if (!definition) return null;
  return definition.channels.find((channel) => (
    channel.quantity_semantics === quantitySemantics
      && (!preferredRole || channel.axis_role === preferredRole)
  )) ?? null;
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
  if (deviation.quantile_probability !== null) {
    qualifiers.push(`q=${deviation.quantile_probability}`);
  }
  if (deviation.quantile_method !== null) qualifiers.push(deviation.quantile_method);
  return qualifiers.join(" · ");
}

export function deviationSourceCount(
  deviation: CurveDeviationContract,
  series: CurveSeriesPreviewContract,
  pointIndex: number,
): number | null {
  if (deviation.source_count !== null) return deviation.source_count;
  if (!deviation.source_count_series_key) return null;
  return series.source_counts.find((item) => item.key === deviation.source_count_series_key)
    ?.values[pointIndex] ?? null;
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
      return kind === "confidence_bound" ? 0
        : kind === "prediction_bound" ? 1
          : kind === "tolerance_bound" ? 2
            : kind === "quantile" ? 3 : 4;
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
    return {
      group,
      lower,
      upper,
      lowerValues: lowerSeries.values,
      upperValues: upperSeries.values,
      label: deviationMeaning(lower),
    };
  }
  return null;
}

export function curveDisplayModel(
  definition: CurveDefinitionContract | null | undefined,
  series: CurveSeriesPreviewContract | null | undefined,
): CurveDisplayModel | null {
  if (!definition || !series) return null;
  const independent = definition.channels.find((item) => item.axis_role === "independent");
  const dependent = definition.channels.find((item) => item.axis_role === "dependent");
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

export function originalUnitSummary(channel: CurveChannelContract): string {
  return [...new Set(channel.original_units.map((item) => item.unit))].join(", ") || "not recorded";
}
