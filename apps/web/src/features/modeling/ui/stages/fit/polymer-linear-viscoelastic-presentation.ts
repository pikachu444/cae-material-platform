import type {
  LinearViscoelasticCandidate,
  LinearViscoelasticPointPartition,
  LinearViscoelasticResponseResidualEvidence,
  LinearViscoelasticWeights,
  ProcessedLinearViscoelasticFitInput,
} from "../../../model/linear-viscoelastic-calibration-contracts";
import {
  polymerSnapshotChannel,
  type PolymerSourceSnapshot,
} from "../../../model/linear-viscoelastic-calibration-draft";

export interface PolymerObservedPoint {
  ordinal: number;
  x: number;
  y: number;
  partition: LinearViscoelasticPointPartition | null;
}

export interface PolymerObservedSeries {
  key: "relaxation" | "dma-storage" | "dma-loss";
  label: string;
  xLabel: string;
  xUnit: string;
  yLabel: string;
  yUnit: string;
  points: PolymerObservedPoint[];
}

export interface PolymerCalculatedPoint extends PolymerObservedPoint {
  observed: number;
  predicted: number;
  residual: number;
}

export interface PolymerCalculatedSeries extends Omit<PolymerObservedSeries, "label" | "points"> {
  label: string;
  role: "recommendation" | "selection";
  points: PolymerCalculatedPoint[];
}

export interface PolymerResidualPoint {
  ordinal: number;
  x: number;
  residual: number;
}

export interface PolymerResidualSeries {
  key: string;
  title: string;
  xLabel: string;
  xUnit: string;
  points: PolymerResidualPoint[];
}

function finite(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function pointsFromChannels(
  xValues: Array<number | null>,
  yValues: Array<number | null>,
  partitions: Array<LinearViscoelasticPointPartition | null>,
  include: (ordinal: number) => boolean = () => true,
): PolymerObservedPoint[] {
  const length = Math.min(xValues.length, yValues.length);
  return Array.from({ length }, (_, ordinal) => {
    const x = xValues[ordinal];
    const y = yValues[ordinal];
    return finite(x) && finite(y) && include(ordinal)
      ? { ordinal, x, y, partition: partitions[ordinal] ?? null }
      : null;
  }).filter((point): point is PolymerObservedPoint => point !== null);
}

export function buildPolymerObservedSeries(
  snapshot: PolymerSourceSnapshot,
  selectedTemperature: string,
  partitions: Array<LinearViscoelasticPointPartition | null>,
): PolymerObservedSeries[] {
  if (snapshot.mode === "relaxation") {
    const time = polymerSnapshotChannel(snapshot, "time.elapsed");
    const modulus = polymerSnapshotChannel(snapshot, "modulus.shear.relaxation");
    if (!time || !modulus) return [];
    return [{
      key: "relaxation",
      label: "Measured relaxation modulus",
      xLabel: "Elapsed time",
      xUnit: time.unit,
      yLabel: "Shear relaxation modulus",
      yUnit: modulus.unit,
      points: pointsFromChannels(time.values, modulus.values, partitions),
    }];
  }
  if (snapshot.mode !== "dma") return [];
  const frequency = polymerSnapshotChannel(snapshot, "frequency.cyclic");
  const temperature = polymerSnapshotChannel(snapshot, "physics.temperature");
  const storage = snapshot.channels.find((channel) => channel.quantity.includes("modulus.shear.storage") || channel.quantity.includes("modulus.storage"));
  const loss = snapshot.channels.find((channel) => channel.quantity.includes("modulus.shear.loss") || channel.quantity.includes("modulus.loss"));
  if (!frequency || !storage || !loss) return [];
  const selected = Number(selectedTemperature);
  const include = temperature && Number.isFinite(selected)
    ? (ordinal: number) => temperature.values[ordinal] === selected
    : () => true;
  return [
    {
      key: "dma-storage",
      label: "Measured storage modulus",
      xLabel: "Frequency",
      xUnit: frequency.unit,
      yLabel: "Shear modulus",
      yUnit: storage.unit,
      points: pointsFromChannels(frequency.values, storage.values, partitions, include),
    },
    {
      key: "dma-loss",
      label: "Measured loss modulus",
      xLabel: "Frequency",
      xUnit: frequency.unit,
      yLabel: "Shear modulus",
      yUnit: loss.unit,
      points: pointsFromChannels(frequency.values, loss.values, partitions, include),
    },
  ];
}

export function buildProcessedPolymerObservedSeries(
  input: ProcessedLinearViscoelasticFitInput | null,
): PolymerObservedSeries[] {
  if (!input) return [];
  const points = (
    response: (row: ProcessedLinearViscoelasticFitInput["rows"][number]) => number
  ): PolymerObservedPoint[] => input.rows.flatMap((row) => (
    finite(row.coordinate) && finite(response(row))
      ? [{ ordinal: row.ordinal, x: row.coordinate, y: response(row), partition: row.partition }]
      : []
  ));
  return [
    {
      key: "dma-storage",
      label: "Measured storage modulus",
      xLabel: "Reduced angular frequency",
      xUnit: input.coordinate_unit,
      yLabel: "Shear modulus",
      yUnit: "Pa",
      points: points((row) => row.storage_modulus_pa),
    },
    {
      key: "dma-loss",
      label: "Measured loss modulus",
      xLabel: "Reduced angular frequency",
      xUnit: input.coordinate_unit,
      yLabel: "Shear modulus",
      yUnit: "Pa",
      points: points((row) => row.loss_modulus_pa),
    },
  ];
}

const EVIDENCE_CHANNEL_BY_SERIES: Record<PolymerObservedSeries["key"], LinearViscoelasticResponseResidualEvidence["rows"][number]["channel"]> = {
  relaxation: "relaxation",
  "dma-storage": "dma_storage",
  "dma-loss": "dma_loss",
};

export function buildPolymerCalculatedSeries(
  observedSeries: PolymerObservedSeries[],
  evidence: LinearViscoelasticResponseResidualEvidence | null,
): PolymerCalculatedSeries[] {
  if (!evidence) return [];
  const expected = observedSeries.flatMap((series) => series.points
    .map((point) => ({ series, point, channel: EVIDENCE_CHANNEL_BY_SERIES[series.key] })));
  const rows = new Map<string, LinearViscoelasticResponseResidualEvidence["rows"][number]>();
  for (const row of evidence.rows) {
    const key = `${row.channel}:${row.ordinal}`;
    if (rows.has(key)) return [];
    rows.set(key, row);
  }
  if (rows.size !== expected.length || expected.some(({ point, channel }) => {
    const row = rows.get(`${channel}:${point.ordinal}`);
    return !row || row.observed !== point.y || row.partition !== point.partition;
  })) return [];
  return observedSeries.map((series) => {
    const channel = EVIDENCE_CHANNEL_BY_SERIES[series.key];
    return {
      ...series,
      label: series.key === "relaxation"
        ? "Recommended model"
        : series.key === "dma-storage"
          ? "Recommended storage response"
          : "Recommended loss response",
      role: "recommendation" as const,
      points: series.points.flatMap((point) => {
        const row = rows.get(`${channel}:${point.ordinal}`);
        return row ? [{
          ordinal: point.ordinal,
          x: point.x,
          y: row.predicted,
          observed: row.observed,
          predicted: row.predicted,
          residual: row.residual,
          partition: row.partition,
        }] : [];
      }),
    };
  }).filter((series) => series.points.length > 0);
}

function candidateSeriesLabel(
  key: PolymerObservedSeries["key"],
  role: PolymerCalculatedSeries["role"],
): string {
  if (role === "selection") {
    return key === "relaxation"
      ? "Engineer selection"
      : key === "dma-storage"
        ? "Selected storage response"
        : "Selected loss response";
  }
  return key === "relaxation"
    ? "Recommended model"
    : key === "dma-storage"
      ? "Recommended storage response"
      : "Recommended loss response";
}

function positiveWeight(value: string | undefined): number | null {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : null;
}

export function buildPolymerCandidateCalculatedSeries(
  observedSeries: PolymerObservedSeries[],
  candidate: LinearViscoelasticCandidate | undefined,
  weights: Partial<LinearViscoelasticWeights> | undefined,
  role: PolymerCalculatedSeries["role"] = "selection",
): PolymerCalculatedSeries[] {
  if (!candidate || !weights) return [];
  const scales = {
    relaxation: positiveWeight(weights.relaxation_scale_pa),
    "dma-storage": positiveWeight(weights.dma_storage_scale_pa),
    "dma-loss": positiveWeight(weights.dma_loss_scale_pa),
  };
  const objectiveWeights = {
    relaxation: positiveWeight(weights.relaxation_weight),
    "dma-storage": positiveWeight(weights.dma_storage_weight),
    "dma-loss": positiveWeight(weights.dma_loss_weight),
  };
  if (Object.values(scales).some((value) => value === null)
    || Object.values(objectiveWeights).some((value) => value === null)) return [];
  let calibrationCursor = 0;
  let holdoutCursor = 0;
  const series = observedSeries.map((observed): PolymerCalculatedSeries | null => {
    const calibrationCount = observed.points.filter((point) => point.partition === "CALIBRATION").length;
    const scale = scales[observed.key]!;
    const objectiveWeight = objectiveWeights[observed.key]!;
    const calibrationFactor = calibrationCount > 0
      ? scale / Math.sqrt(objectiveWeight / calibrationCount)
      : null;
    const points = observed.points.flatMap((point): PolymerCalculatedPoint[] => {
      let normalizedResidual: number | undefined;
      let factor: number | null = null;
      if (point.partition === "CALIBRATION") {
        normalizedResidual = candidate.calibration_residuals[calibrationCursor++];
        factor = calibrationFactor;
      } else if (point.partition === "HOLDOUT") {
        normalizedResidual = candidate.holdout_residuals[holdoutCursor++];
        factor = scale;
      } else {
        return [];
      }
      if (factor === null || !Number.isFinite(normalizedResidual)) return [];
      const residual = normalizedResidual! * factor;
      const predicted = point.y + residual;
      return Number.isFinite(predicted) ? [{
        ...point,
        y: predicted,
        observed: point.y,
        predicted,
        residual,
      }] : [];
    });
    return points.length ? {
      ...observed,
      label: candidateSeriesLabel(observed.key, role),
      role,
      points,
    } : null;
  }).filter((item): item is PolymerCalculatedSeries => item !== null);
  const expected = observedSeries.reduce((count, observed) => count
    + observed.points.filter((point) => point.partition === "CALIBRATION" || point.partition === "HOLDOUT").length, 0);
  return calibrationCursor === candidate.calibration_residuals.length
    && holdoutCursor === candidate.holdout_residuals.length
    && series.reduce((count, item) => count + item.points.length, 0) === expected
    ? series
    : [];
}

export function buildPolymerResidualSeries(
  observedSeries: PolymerObservedSeries[],
  candidate: LinearViscoelasticCandidate,
  weights: Partial<LinearViscoelasticWeights> | undefined,
): PolymerResidualSeries[] {
  const calculated = buildPolymerCandidateCalculatedSeries(observedSeries, candidate, weights);
  return calculated.flatMap((series) => (["CALIBRATION", "HOLDOUT"] as const).flatMap((partition) => {
    const observedLabel = observedSeries.find((observed) => observed.key === series.key)?.label ?? series.key;
    const points = series.points
      .filter((point) => point.partition === partition && point.observed !== 0)
      .map((point) => ({
        ordinal: point.ordinal,
        x: point.x,
        residual: point.residual / point.observed,
      }));
    return points.length ? [{
      key: `${partition.toLowerCase()}:${series.key}`,
      title: `${partition === "CALIBRATION" ? "Differences on used points" : "Differences on check points"} · ${observedLabel.replace("Measured ", "")}`,
      xLabel: series.xLabel,
      xUnit: series.xUnit,
      points,
    }] : [];
  }));
}

export function meanAbsolutePolymerRelativeDeviation(
  observedSeries: PolymerObservedSeries[],
  candidate: LinearViscoelasticCandidate,
  weights: Partial<LinearViscoelasticWeights> | undefined,
  partition: "CALIBRATION" | "HOLDOUT",
): number | null {
  const values = buildPolymerResidualSeries(observedSeries, candidate, weights)
    .filter((series) => series.key.startsWith(`${partition.toLowerCase()}:`))
    .flatMap((series) => series.points.map((point) => point.residual))
    .filter(Number.isFinite);
  return values.length
    ? values.reduce((sum, value) => sum + Math.abs(value), 0) / values.length
    : null;
}

export function exactPolymerResponsePartitions(
  draftPartitions: Array<LinearViscoelasticPointPartition | null>,
  evidence: LinearViscoelasticResponseResidualEvidence | null,
): Array<LinearViscoelasticPointPartition | null> {
  if (!evidence) return draftPartitions;
  const exact = [...draftPartitions];
  for (const row of evidence.rows) exact[row.ordinal] = row.partition;
  return exact;
}

export function polymerResponseDomain(
  observedSeries: PolymerObservedSeries[],
  calculatedSeries: PolymerCalculatedSeries[] = [],
) {
  const observedPoints = observedSeries.flatMap((item) => item.points);
  const calculatedPoints = calculatedSeries.flatMap((item) => item.points);
  if (!observedPoints.length) return null;
  const yValues = [
    ...observedPoints.map((point) => point.y),
    ...calculatedPoints.map((point) => point.predicted),
  ];
  return {
    xMin: Math.min(...observedPoints.map((point) => point.x)),
    xMax: Math.max(...observedPoints.map((point) => point.x)),
    yMin: Math.min(...yValues),
    yMax: Math.max(...yValues),
  };
}

export const polymerObservedDomain = polymerResponseDomain;
