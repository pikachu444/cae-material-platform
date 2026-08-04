import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from "react";

import type {
  CommonCurveStage,
  CommonEnsemblePreview,
  CommonProcessingPreview,
  CommonProcessingStep,
  GraphSelectionCommand,
} from "./types";
import {
  fitDecisionIdentityLabel,
  type FitDecisionSelection,
} from "./modeling-fit-decision-contract";

export interface PlotBounds {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
}

interface PlotSeries {
  id: string;
  label: string;
  xValues: number[];
  yValues: number[];
  color: string;
  className: string;
}

export interface ObservedCurveInput {
  id: string;
  label: string;
  preview: CommonProcessingPreview;
  color?: string;
}

interface PlotBand {
  id: string;
  label: string;
  xValues: number[];
  lowerValues: number[];
  upperValues: number[];
}

interface PlotModel {
  xQuantity: string;
  xUnit: string;
  yQuantity: string;
  yUnit: string;
  series: PlotSeries[];
  band?: PlotBand;
  extrapolationStart?: number;
  xScale?: "linear" | "log10";
}

export type HardeningPlotMode = "response" | "residual" | "derivative";
export type PronyPlotMode = "response" | "residual";
export type PlotInteractionMode = "pan" | "range" | "point";
export interface PlotInteractionCommand {
  action: "set-mode" | "apply";
  mode?: PlotInteractionMode;
  requestId: number;
}
export interface PlotInteractionState {
  mode: PlotInteractionMode;
  hasSelection: boolean;
}

const PLOT_MARGIN = { left: 80, right: 24, top: 24, bottom: 52 } as const;
const CANDIDATE_COLORS = ["#64748b", "#0f766e", "#d97706", "#7c3aed", "#dc2626"];
const QUANTITY_LABELS: Record<string, string> = {
  "strain.engineering": "Engineering strain",
  "strain.true_plastic": "True plastic strain",
  "stress.hardening": "Hardening stress",
  "stress.true": "True stress",
  "stress.engineering": "Engineering stress",
  "modulus.shear.relaxation": "Shear relaxation modulus",
  "modulus.shear.dynamic": "Dynamic shear modulus",
  "predicted - measured": "Predicted minus measured",
  response: "Response",
};

function modelLabel(value: string): string {
  return {
    voce: "Voce",
    swift: "Swift",
    hockett_sherby: "Hockett–Sherby",
    ghosh: "Ghosh",
  }[value] ?? value.replaceAll("_", "-");
}

function quantityLabel(quantity: string): string {
  return QUANTITY_LABELS[quantity]
    ?? quantity.split(".").map((part) => part.replaceAll("_", " ")).join(" ");
}

export function linearInterpolate(
  xValues: number[],
  yValues: number[],
  target: number,
): number | null {
  if (xValues.length < 2 || xValues.length !== yValues.length) return null;
  if (target < xValues[0] || target > xValues[xValues.length - 1]) return null;
  const exact = xValues.indexOf(target);
  if (exact >= 0) return yValues[exact];
  let upper = 1;
  while (upper < xValues.length && xValues[upper] < target) upper += 1;
  if (upper >= xValues.length || xValues[upper] === xValues[upper - 1]) return null;
  const fraction = (target - xValues[upper - 1]) / (xValues[upper] - xValues[upper - 1]);
  return yValues[upper - 1] + fraction * (yValues[upper] - yValues[upper - 1]);
}

export function residualValues(
  observedX: number[],
  observedY: number[],
  predictedX: number[],
  predictedY: number[],
): { xValues: number[]; yValues: number[] } {
  const xValues: number[] = [];
  const yValues: number[] = [];
  observedX.forEach((x, index) => {
    const predicted = linearInterpolate(predictedX, predictedY, x);
    if (predicted !== null && Number.isFinite(observedY[index])) {
      xValues.push(x);
      yValues.push(predicted - observedY[index]);
    }
  });
  return { xValues, yValues };
}

export function derivativeValues(
  xValues: number[],
  yValues: number[],
): { xValues: number[]; yValues: number[] } {
  const x: number[] = [];
  const y: number[] = [];
  for (let index = 1; index < xValues.length; index += 1) {
    const deltaX = xValues[index] - xValues[index - 1];
    if (deltaX > 0 && Number.isFinite(deltaX)) {
      x.push((xValues[index] + xValues[index - 1]) / 2);
      y.push((yValues[index] - yValues[index - 1]) / deltaX);
    }
  }
  return { xValues: x, yValues: y };
}

export function plotPoints(
  x: number[],
  y: number[],
  width: number,
  height: number,
  bounds: PlotBounds,
  margins: { left: number; right: number; top: number; bottom: number } = PLOT_MARGIN,
): string {
  if (x.length < 2 || x.length !== y.length) return "";
  const xRange = bounds.xMax - bounds.xMin || 1;
  const yRange = bounds.yMax - bounds.yMin || 1;
  return x.map((value, index) => {
    const px = margins.left + ((value - bounds.xMin) / xRange) * (width - margins.left - margins.right);
    const py = height - margins.bottom - ((y[index] - bounds.yMin) / yRange) * (height - margins.top - margins.bottom);
    return `${px.toFixed(1)},${py.toFixed(1)}`;
  }).join(" ");
}

export function paddedPlotBounds(x: number[], y: number[]): PlotBounds {
  const finiteX = x.filter(Number.isFinite);
  const finiteY = y.filter(Number.isFinite);
  if (!finiteX.length || !finiteY.length) return { xMin: 0, xMax: 1, yMin: 0, yMax: 1 };
  const xMin = Math.min(...finiteX);
  const xMax = Math.max(...finiteX);
  const yMin = Math.min(...finiteY);
  const yMax = Math.max(...finiteY);
  const xPadding = Math.max((xMax - xMin) * 0.025, Math.abs(xMax || 1) * 0.0025);
  const yPadding = Math.max((yMax - yMin) * 0.06, Math.abs(yMax || 1) * 0.01);
  return {
    xMin: xMin - xPadding,
    xMax: xMax + xPadding,
    yMin: yMin - yPadding,
    yMax: yMax + yPadding,
  };
}

function axisTicks(minimum: number, maximum: number, count = 5): number[] {
  const interval = (maximum - minimum) / count;
  return Array.from({ length: count + 1 }, (_, index) => minimum + interval * index);
}

function displayScale(unit: string, values: number[]): { divisor: number; label: string } {
  if (unit !== "Pa") return { divisor: 1, label: unit };
  const maximum = Math.max(...values.map(Math.abs), 0);
  if (maximum >= 1e9) return { divisor: 1e9, label: "GPa" };
  if (maximum >= 1e6) return { divisor: 1e6, label: "MPa" };
  if (maximum >= 1e3) return { divisor: 1e3, label: "kPa" };
  return { divisor: 1, label: "Pa" };
}

function axisNumber(value: number): string {
  const absolute = Math.abs(value);
  if (absolute !== 0 && (absolute >= 10000 || absolute < 0.001)) return value.toExponential(2);
  return Number(value.toPrecision(4)).toString();
}

function seriesForStage(
  preview: CommonProcessingPreview,
  activeStage: CommonCurveStage,
  baseStage: CommonCurveStage,
  activeStep?: CommonProcessingStep,
  hardeningMode: HardeningPlotMode = "response",
  pronyMode: PronyPlotMode = "response",
  fitSelection?: FitDecisionSelection | null,
): PlotModel {
  const hardening = activeStage.method_id === "metal.hardening_fit_extrapolate";
  const prony = activeStage.method_id === "polymer.prony_fit_compare"
    || activeStage.method_id === "polymer.dma_prony_fit_compare";
  const xQuantity = activeStage.series.some((item) => item.quantity === preview.independent_quantity)
    ? preview.independent_quantity
    : activeStage.series.find((item) => item.quantity.includes("strain"))?.quantity
      ?? preview.independent_quantity;
  const activeX = activeStage.series.find((item) => item.quantity === xQuantity);
  const baseX = baseStage.series.find((item) => item.quantity === xQuantity);
  const activeDependent = activeStage.series.find((item) => item.quantity !== xQuantity);

  if (hardening) {
    const candidates = activeStage.series.filter(
      (item) => item.quantity.startsWith("stress.hardening.") && item.quantity !== "stress.hardening.selected",
    );
    const previewBlend = activeStage.series.find((item) => item.quantity === "stress.hardening.selected");
    const fitMinimum = Number(activeStep?.options.fit_minimum_strain ?? 0);
    const fitMaximum = Number(activeStep?.options.fit_maximum_strain ?? activeX?.values.at(-1) ?? 0);
    const previousStage = preview.stages.find((item) => item.ordinal === activeStage.ordinal - 1);
    const observedXSeries = previousStage?.series.find((item) => item.quantity === xQuantity);
    const observedYSeries = previousStage?.series.find((item) => item.quantity === String(activeStep?.options.stress_quantity ?? "stress.true"));
    const observedX = observedXSeries?.values ?? [];
    const observedY = observedYSeries?.values ?? [];
    const candidateSeries: PlotSeries[] = candidates.map((item, index) => ({
      id: item.quantity,
      label: modelLabel(item.quantity.replace("stress.hardening.", "")),
      xValues: activeX?.values ?? [],
      yValues: item.values,
      color: CANDIDATE_COLORS[index % CANDIDATE_COLORS.length],
      className: "hardening-candidate",
    }));
    const explicitSingle = fitSelection?.mode === "single"
      ? candidates.find((item) => item.quantity === `stress.hardening.${fitSelection.primaryLaw}`)
      : null;
    const decisionSeries = explicitSingle ?? previewBlend;
    const decisionLabel = fitSelection
      ? `Selected · ${fitDecisionIdentityLabel(fitSelection)}`
      : `Preview ${modelLabel(String(activeStep?.options.primary_family ?? "primary"))}/${modelLabel(String(activeStep?.options.secondary_family ?? "secondary"))} blend`;
    const selectedSeries: PlotSeries | null = decisionSeries ? {
      id: `fit.decision.${fitSelection?.candidateKey ?? "preview"}`,
      label: decisionLabel,
      xValues: activeX?.values ?? [],
      yValues: decisionSeries.values,
      color: "#111827",
      className: "hardening-selected",
    } : null;
    const selectedBoundaryValue = selectedSeries
      ? linearInterpolate(selectedSeries.xValues, selectedSeries.yValues, fitMaximum)
      : null;
    const selectedObserved = selectedSeries ? {
      ...selectedSeries,
      id: `${selectedSeries.id}.observed`,
      label: `${decisionLabel} · fit`,
      xValues: [
        ...selectedSeries.xValues.filter((value) => value < fitMaximum),
        ...(selectedBoundaryValue !== null ? [fitMaximum] : []),
      ],
      yValues: [
        ...selectedSeries.yValues.filter((_, index) => selectedSeries.xValues[index] < fitMaximum),
        ...(selectedBoundaryValue !== null ? [selectedBoundaryValue] : []),
      ],
      className: "hardening-selected fitted-domain",
    } : null;
    const selectedExtrapolated = selectedSeries ? {
      ...selectedSeries,
      id: `${selectedSeries.id}.extrapolated`,
      label: `${decisionLabel} · extrapolated`,
      xValues: [
        ...(selectedBoundaryValue !== null ? [fitMaximum] : []),
        ...selectedSeries.xValues.filter((value) => value > fitMaximum),
      ],
      yValues: [
        ...(selectedBoundaryValue !== null ? [selectedBoundaryValue] : []),
        ...selectedSeries.yValues.filter((_, index) => selectedSeries.xValues[index] > fitMaximum),
      ],
      className: "hardening-selected extrapolated-domain",
    } : null;

    if (hardeningMode === "residual") {
      const inFitDomain = observedX.map((value, index) => ({ value, index }))
        .filter(({ value }) => value >= fitMinimum && value <= fitMaximum);
      const fitX = inFitDomain.map(({ value }) => value);
      const fitY = inFitDomain.map(({ index }) => observedY[index]);
      const comparison = [...candidateSeries, ...(selectedSeries ? [selectedSeries] : [])]
        .map((item) => {
          const residual = residualValues(fitX, fitY, item.xValues, item.yValues);
          return { ...item, ...residual, label: `${item.label} residual` };
        });
      return {
        xQuantity,
        xUnit: activeX?.unit ?? "1",
        yQuantity: "predicted - observed",
        yUnit: decisionSeries?.unit ?? candidates[0]?.unit ?? "Pa",
        series: comparison,
      };
    }

    if (hardeningMode === "derivative") {
      return {
        xQuantity,
        xUnit: activeX?.unit ?? "1",
        yQuantity: "d(stress) / d(plastic strain)",
        yUnit: decisionSeries?.unit ?? candidates[0]?.unit ?? "Pa",
        series: [...candidateSeries, ...(selectedSeries ? [selectedSeries] : [])].map((item) => ({
          ...item,
          ...derivativeValues(item.xValues, item.yValues),
          label: `${item.label} tangent`,
        })),
        extrapolationStart: fitMaximum,
      };
    }

    return {
      xQuantity,
      xUnit: activeX?.unit ?? "1",
      yQuantity: "stress.hardening",
      yUnit: decisionSeries?.unit ?? candidates[0]?.unit ?? "Pa",
      series: [
        ...(observedX.length === observedY.length ? [{
          id: "hardening-observed",
          label: "Observed plastic workup",
          xValues: observedX,
          yValues: observedY,
          color: "#e56734",
          className: "hardening-observed",
        }] : []),
        ...candidateSeries,
        ...(selectedObserved ? [selectedObserved] : []),
        ...(selectedExtrapolated ? [selectedExtrapolated] : []),
      ],
      extrapolationStart: fitMaximum,
    };
  }

  if (prony) {
    const dma = activeStage.method_id === "polymer.dma_prony_fit_compare";
    if (dma) {
      const previousStage = preview.stages.find((item) => item.ordinal === activeStage.ordinal - 1);
      const observedX = previousStage?.series.find((item) => item.quantity === xQuantity)?.values ?? [];
      const observedStorage = previousStage?.series.find((item) => item.quantity === String(activeStep?.options.storage_modulus_quantity ?? "modulus.shear.storage"));
      const observedLoss = previousStage?.series.find((item) => item.quantity === String(activeStep?.options.loss_modulus_quantity ?? "modulus.shear.loss"));
      const candidates = activeStage.series.filter((item) => item.quantity.includes(".prony.candidate_"));
      const selected = activeStage.series.filter((item) => item.quantity.endsWith(".prony.selected"));
      const candidateSeries: PlotSeries[] = candidates.map((item, index) => ({
        id: item.quantity,
        label: item.quantity.replace("modulus.", "").replace(".prony.candidate_", " · ").replaceAll("_", " "),
        xValues: activeX?.values ?? [],
        yValues: item.values,
        color: CANDIDATE_COLORS[index % CANDIDATE_COLORS.length],
        className: item.quantity.startsWith("modulus.loss") ? "prony-candidate dma-loss" : "prony-candidate dma-storage",
      }));
      const selectedSeries: PlotSeries[] = selected.map((item, index) => ({
        id: item.quantity,
        label: `${fitSelection ? `Selected · ${fitDecisionIdentityLabel(fitSelection)}` : "Server result preview"} · ${item.quantity.startsWith("modulus.storage") ? "storage modulus" : "loss modulus"}`,
        xValues: activeX?.values ?? [],
        yValues: item.values,
        color: index === 0 ? "#111827" : "#7c3aed",
        className: item.quantity.startsWith("modulus.storage") ? "prony-selected dma-storage" : "prony-selected dma-loss",
      }));
      if (pronyMode === "residual") {
        return {
          xQuantity,
          xUnit: activeX?.unit ?? "Hz",
          yQuantity: "predicted - measured",
          yUnit: "Pa",
          series: [...candidateSeries, ...selectedSeries].map((item) => ({
            ...item,
            ...residualValues(
              observedX,
              item.id.startsWith("modulus.storage") ? observedStorage?.values ?? [] : observedLoss?.values ?? [],
              item.xValues,
              item.yValues,
            ),
            label: `${item.label} residual`,
          })),
          xScale: "log10",
        };
      }
      return {
        xQuantity,
        xUnit: activeX?.unit ?? "Hz",
        yQuantity: "modulus.shear.dynamic",
        yUnit: "Pa",
        series: [
          ...(observedStorage ? [{ id: "dma-storage-observed", label: "Measured storage modulus", xValues: observedX, yValues: observedStorage.values, color: "#e56734", className: "prony-observed dma-storage" }] : []),
          ...(observedLoss ? [{ id: "dma-loss-observed", label: "Measured loss modulus", xValues: observedX, yValues: observedLoss.values, color: "#2f7f78", className: "prony-observed dma-loss" }] : []),
          ...candidateSeries,
          ...selectedSeries,
        ],
        xScale: "log10",
      };
    }
    const candidates = activeStage.series.filter((item) => item.quantity.startsWith("modulus.prony.candidate_"));
    const selected = activeStage.series.find((item) => item.quantity === "modulus.prony.selected");
    const previousStage = preview.stages.find((item) => item.ordinal === activeStage.ordinal - 1);
    const observedX = previousStage?.series.find((item) => item.quantity === xQuantity)?.values ?? [];
    const observedSeries = previousStage?.series.find(
      (item) => item.quantity === String(activeStep?.options.modulus_quantity ?? "modulus.shear.relaxation"),
    );
    const candidateSeries: PlotSeries[] = candidates.map((item, index) => ({
      id: item.quantity,
      label: item.quantity.replace("modulus.prony.candidate_", "").replaceAll("_", " "),
      xValues: activeX?.values ?? [],
      yValues: item.values,
      color: CANDIDATE_COLORS[index % CANDIDATE_COLORS.length],
      className: "prony-candidate",
    }));
    const selectedSeries: PlotSeries | null = selected ? {
      id: selected.quantity,
      label: fitSelection
        ? `Selected · ${fitDecisionIdentityLabel(fitSelection)}`
        : "Server result preview · Prony candidate",
      xValues: activeX?.values ?? [],
      yValues: selected.values,
      color: "#111827",
      className: "prony-selected",
    } : null;
    if (pronyMode === "residual") {
      const comparison = [...candidateSeries, ...(selectedSeries ? [selectedSeries] : [])].map((item) => ({
        ...item,
        ...residualValues(observedX, observedSeries?.values ?? [], item.xValues, item.yValues),
        label: `${item.label} residual`,
      }));
      return {
        xQuantity,
        xUnit: activeX?.unit ?? "s",
        yQuantity: "predicted - measured",
        yUnit: selected?.unit ?? candidates[0]?.unit ?? "Pa",
        series: comparison,
        xScale: "log10",
      };
    }
    return {
      xQuantity,
      xUnit: activeX?.unit ?? "s",
      yQuantity: "modulus.shear.relaxation",
      yUnit: selected?.unit ?? candidates[0]?.unit ?? "Pa",
      series: [
        ...(observedSeries && observedX.length === observedSeries.values.length ? [{
          id: "prony-observed",
          label: "Measured relaxation",
          xValues: observedX,
          yValues: observedSeries.values,
          color: "#e56734",
          className: "prony-observed",
        }] : []),
        ...candidateSeries,
        ...(selectedSeries ? [selectedSeries] : []),
      ],
      xScale: "log10",
    };
  }

  const baseDependent = baseStage.series.find((item) => item.quantity !== xQuantity);
  const engineeringOverlays: PlotSeries[] = [];
  if (activeStage.method_id === "metal.elastic_modulus") {
    const modulus = activeStage.scalar_results.find((item) => item.key === "youngs_modulus")?.value;
    const intercept = activeStage.scalar_results.find((item) => item.key === "elastic_intercept")?.value;
    const minimum = Number(activeStep?.options.minimum_strain ?? activeX?.values[0]);
    const maximum = Number(activeStep?.options.maximum_strain ?? activeX?.values.at(-1));
    if (Number.isFinite(modulus) && Number.isFinite(intercept) && Number.isFinite(minimum) && Number.isFinite(maximum)) {
      engineeringOverlays.push({
        id: "elastic-fit-line",
        label: "Elastic fit",
        xValues: [minimum, maximum],
        yValues: [modulus! * minimum + intercept!, modulus! * maximum + intercept!],
        color: "#2563eb",
        className: "engineering-fit",
      });
    }
  }
  if (activeStage.method_id === "metal.proof_stress") {
    const modulus = Number(activeStep?.options.youngs_modulus_pa);
    const offset = Number(activeStep?.options.offset_strain);
    const minimum = Number(activeStep?.options.search_start);
    const maximum = Number(activeStep?.options.search_end);
    if ([modulus, offset, minimum, maximum].every(Number.isFinite)) {
      engineeringOverlays.push({
        id: "proof-offset-line",
        label: `${(offset * 100).toPrecision(3)}% offset line`,
        xValues: [minimum, maximum],
        yValues: [modulus * (minimum - offset), modulus * (maximum - offset)],
        color: "#7c3aed",
        className: "proof-offset",
      });
    }
  }
  return {
    xQuantity,
    xUnit: activeX?.unit ?? baseX?.unit ?? "1",
    yQuantity: activeDependent?.quantity ?? baseDependent?.quantity ?? "response",
    yUnit: activeDependent?.unit ?? baseDependent?.unit ?? "1",
    series: [
      {
        id: "mapped-input",
        label: "Mapped input",
        xValues: baseX?.values ?? [],
        yValues: baseDependent?.values ?? [],
        color: "#8e9ca0",
        className: "source",
      },
      {
        id: "selected-stage",
        label: "Selected stage",
        xValues: activeX?.values ?? [],
        yValues: activeDependent?.values ?? [],
        color: "#e56734",
        className: "processed",
      },
      ...engineeringOverlays,
    ],
  };
}

function seriesForEnsemble(preview: CommonEnsemblePreview): PlotModel {
  const statistic = preview.statistics[0];
  if (!statistic) {
    return {
      xQuantity: preview.independent_quantity,
      xUnit: preview.grid_unit,
      yQuantity: "response",
      yUnit: "1",
      series: [],
    };
  }
  const memberSeries = preview.members.map((member, index) => {
    const response = member.stage.series.find((item) => item.quantity === statistic.quantity);
    return {
      id: `replicate-${member.ordinal}`,
      label: `Replicate ${member.ordinal}`,
      xValues: preview.grid,
      yValues: response?.values ?? [],
      color: CANDIDATE_COLORS[index % CANDIDATE_COLORS.length],
      className: "ensemble-member",
    };
  });
  return {
    xQuantity: preview.independent_quantity,
    xUnit: preview.grid_unit,
    yQuantity: statistic.quantity,
    yUnit: statistic.unit,
    series: [
      ...memberSeries,
      {
        id: "replicate-mean",
        label: "Pointwise mean",
        xValues: preview.grid,
        yValues: statistic.mean,
        color: "#111827",
        className: "ensemble-mean",
      },
    ],
    band: {
      id: "confidence-95",
      label: "95% mean confidence interval",
      xValues: preview.grid,
      lowerValues: statistic.confidence_95_lower,
      upperValues: statistic.confidence_95_upper,
    },
  };
}

function bandPolygon(band: PlotBand, width: number, height: number, bounds: PlotBounds): string {
  const upper = plotPoints(band.xValues, band.upperValues, width, height, bounds).split(" ");
  const lower = plotPoints(band.xValues, band.lowerValues, width, height, bounds).split(" ").reverse();
  return [...upper, ...lower].join(" ");
}

/**
 * Data-stage tensile plots keep the generic padded bounds contract while
 * anchoring a genuinely non-negative engineering axis at zero.  The helper
 * deliberately takes already-selected source values so residuals, fitted
 * curves, and other quantities continue to use paddedPlotBounds unchanged.
 */
export function dataObservedPlotBounds(
  x: number[],
  y: number[],
  xQuantity: string,
  yQuantity: string,
): PlotBounds {
  const bounds = paddedPlotBounds(x, y);
  if (xQuantity !== "strain.engineering" || yQuantity !== "stress.engineering") return bounds;
  const finiteX = x.filter(Number.isFinite);
  const finiteY = y.filter(Number.isFinite);
  return {
    ...bounds,
    xMin: finiteX.length && finiteX.every((value) => value >= 0) ? 0 : bounds.xMin,
    yMin: finiteY.length && finiteY.every((value) => value >= 0) ? 0 : bounds.yMin,
  };
}

/**
 * Keep the engineering plot frame mounted when a Modeling Data session has no
 * source yet.  This intentionally contains no series data: it is the same
 * axis/grid grammar as the responsive plot, with an actionable in-plot status.
 */
export function EngineeringCurvePlotEmpty({
  width,
  height,
  onChooseLocal,
}: {
  width: number;
  height: number;
  onChooseLocal?: () => void;
}) {
  const [renderedSize, setRenderedSize] = useState<{ width: number; height: number } | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  useEffect(() => {
    const target = svgRef.current;
    if (!target) return undefined;
    const update = (nextWidth: number, nextHeight: number) => {
      if (!Number.isFinite(nextWidth) || !Number.isFinite(nextHeight) || nextWidth <= 0 || nextHeight <= 0) return;
      setRenderedSize((current) => current && Math.abs(current.width - nextWidth) < 1 && Math.abs(current.height - nextHeight) < 1
        ? current
        : { width: nextWidth, height: nextHeight });
    };
    const rectangle = target.getBoundingClientRect();
    update(rectangle.width, rectangle.height);
    if (typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) update(entry.contentRect.width, entry.contentRect.height);
    });
    observer.observe(target);
    return () => observer.disconnect();
  }, []);
  const effectiveWidth = Math.max(320, renderedSize?.width ?? width);
  const effectiveHeight = Math.max(240, renderedSize?.height ?? height);
  const bounds = { xMin: 0, xMax: 0.25, yMin: 0, yMax: 1000 };
  const xTicks = [0, 0.05, 0.1, 0.15, 0.2, 0.25];
  const yTicks = [0, 250, 500, 750, 1000];
  const toX = (value: number) => PLOT_MARGIN.left
    + ((value - bounds.xMin) / (bounds.xMax - bounds.xMin))
      * (effectiveWidth - PLOT_MARGIN.left - PLOT_MARGIN.right);
  const toY = (value: number) => effectiveHeight - PLOT_MARGIN.bottom
    - ((value - bounds.yMin) / (bounds.yMax - bounds.yMin))
      * (effectiveHeight - PLOT_MARGIN.top - PLOT_MARGIN.bottom);

  return (
    <div className="engineering-curve-plot-empty-frame" data-plot-state="empty">
      <svg
        ref={svgRef}
        className="processing-curve engineering-curve-plot-empty-svg"
        role="img"
        aria-label="Empty engineering curve plot"
        viewBox={`0 0 ${effectiveWidth} ${effectiveHeight}`}
        preserveAspectRatio="xMidYMid meet"
      >
        <rect className="chart-surface" x="0" y="0" width={effectiveWidth} height={effectiveHeight} />
        {xTicks.map((tick) => <line key={`empty-x-grid-${tick}`} x1={toX(tick)} y1={PLOT_MARGIN.top} x2={toX(tick)} y2={effectiveHeight - PLOT_MARGIN.bottom} className="chart-grid" />)}
        {yTicks.map((tick) => <line key={`empty-y-grid-${tick}`} x1={PLOT_MARGIN.left} y1={toY(tick)} x2={effectiveWidth - PLOT_MARGIN.right} y2={toY(tick)} className="chart-grid" />)}
        <line x1={PLOT_MARGIN.left} y1={effectiveHeight - PLOT_MARGIN.bottom} x2={effectiveWidth - PLOT_MARGIN.right} y2={effectiveHeight - PLOT_MARGIN.bottom} className="chart-axis" />
        <line x1={PLOT_MARGIN.left} y1={PLOT_MARGIN.top} x2={PLOT_MARGIN.left} y2={effectiveHeight - PLOT_MARGIN.bottom} className="chart-axis" />
        {xTicks.map((tick) => <text key={`empty-x-tick-${tick}`} x={toX(tick)} y={effectiveHeight - 32} textAnchor="middle" className="chart-tick">{axisNumber(tick)}</text>)}
        {yTicks.map((tick) => <text key={`empty-y-tick-${tick}`} x={PLOT_MARGIN.left - 8} y={toY(tick) + 4} textAnchor="end" className="chart-tick">{axisNumber(tick)}</text>)}
        <text x={(PLOT_MARGIN.left + effectiveWidth - PLOT_MARGIN.right) / 2} y={effectiveHeight - 8} textAnchor="middle" className="chart-axis-label">Engineering strain [1]</text>
        <text transform={`translate(15 ${(PLOT_MARGIN.top + effectiveHeight - PLOT_MARGIN.bottom) / 2}) rotate(-90)`} textAnchor="middle" className="chart-axis-label">Engineering stress [MPa]</text>
      </svg>
      <div className="engineering-curve-plot-empty-overlay" role="status">
        <strong>No Test Data in this session</strong>
        <p>Choose an exact saved revision or inspect a Local file to prepare the first preview.</p>
        <button type="button" className="button primary" onClick={onChooseLocal}>Local file</button>
      </div>
    </div>
  );
}

export function EngineeringCurvePlot({
  preview,
  activeStage,
  baseStage,
  width: fallbackWidth,
  height: fallbackHeight,
  onApplySelection,
  ensemblePreview,
  activeStep,
  fitSelection,
  selectedModelOnly = false,
  interactionCommand,
  onInteractionStateChange,
  observedCurves,
}: {
  preview: CommonProcessingPreview;
  activeStage: CommonCurveStage;
  baseStage: CommonCurveStage;
  width: number;
  height: number;
  onApplySelection?: (selection: GraphSelectionCommand) => void;
  ensemblePreview?: CommonEnsemblePreview | null;
  activeStep?: CommonProcessingStep;
  fitSelection?: FitDecisionSelection | null;
  selectedModelOnly?: boolean;
  interactionCommand?: PlotInteractionCommand | null;
  onInteractionStateChange?: (state: PlotInteractionState) => void;
  /** Data-stage only: real server previews for each visible exact Test Data revision. */
  observedCurves?: ObservedCurveInput[];
}) {
  const [hiddenSeries, setHiddenSeries] = useState<string[]>([]);
  const [viewBounds, setViewBounds] = useState<PlotBounds | null>(null);
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);
  const [drag, setDrag] = useState<{ clientX: number; clientY: number; bounds: PlotBounds } | null>(null);
  const [interactionMode, setInteractionMode] = useState<PlotInteractionMode>("pan");
  const [selectionStart, setSelectionStart] = useState<{ x: number; y: number } | null>(null);
  const [selection, setSelection] = useState<GraphSelectionCommand | null>(null);
  const [hardeningMode, setHardeningMode] = useState<HardeningPlotMode>("response");
  const [pronyMode, setPronyMode] = useState<PronyPlotMode>("response");
  const [renderedSize, setRenderedSize] = useState<{ width: number; height: number } | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const isHardening = !ensemblePreview && activeStage.method_id === "metal.hardening_fit_extrapolate";
  const hideInteractionControls = isHardening;
  const isProny = !ensemblePreview && (activeStage.method_id === "polymer.prony_fit_compare"
    || activeStage.method_id === "polymer.dma_prony_fit_compare");
  const isDmaProny = activeStage.method_id === "polymer.dma_prony_fit_compare";
  const model = useMemo(() => {
    const baseModel = ensemblePreview
      ? seriesForEnsemble(ensemblePreview)
      : seriesForStage(preview, activeStage, baseStage, activeStep, hardeningMode, pronyMode, fitSelection);
    if (ensemblePreview || selectedModelOnly) return baseModel;
    if (!observedCurves?.length) return baseModel;
    const observedSeries: PlotSeries[] = observedCurves.flatMap((curve, index) => {
      const stage = curve.preview.stages[0];
      if (!stage) return [];
      const x = stage.series.find((item) => item.quantity === curve.preview.independent_quantity);
      const y = stage.series.find((item) => item.quantity !== curve.preview.independent_quantity);
      if (!x || !y || x.values.length < 2 || x.values.length !== y.values.length) return [];
      return [{
        id: `observed.${curve.id}`,
        label: curve.label,
        xValues: x.values,
        yValues: y.values,
        color: curve.color ?? CANDIDATE_COLORS[index % CANDIDATE_COLORS.length],
        className: "data-observed",
      }];
    });
    // Data-stage observed previews are the measured source curves.  They
    // replace the mapped/base series here so each exact source contributes one
    // line and legend entry instead of a duplicate synthetic-looking line.
    return { ...baseModel, series: observedSeries, band: undefined };
  }, [activeStage, activeStep, baseStage, ensemblePreview, fitSelection, hardeningMode, observedCurves, pronyMode, preview, selectedModelOnly]);
  const visibleModelSeries = selectedModelOnly
    ? model.series.filter((item) => !item.className.includes("candidate"))
    : model.series;
  const hardeningResponseSeries = isHardening && hardeningMode === "response"
    ? visibleModelSeries.filter((item) => !item.className.includes("candidate") || /^(Voce|Hockett–Sherby)$/.test(item.label))
    : visibleModelSeries;
  const validSeries = visibleModelSeries.filter(
    (item) => item.xValues.length >= 2 && item.xValues.length === item.yValues.length
      && (model.xScale !== "log10" || item.xValues.every((value) => value > 0)),
  );
  const toPlotX = (value: number) => model.xScale === "log10" ? Math.log10(value) : value;
  const fromPlotX = (value: number) => model.xScale === "log10" ? 10 ** value : value;
  const plottedSeries = validSeries.map((item) => ({
    ...item,
    xValues: item.xValues.map(toPlotX),
  }));
  const plottedBand = model.band && (model.xScale !== "log10" || model.band.xValues.every((value) => value > 0)) ? {
    ...model.band,
    xValues: model.band.xValues.map(toPlotX),
  } : undefined;
  const paddedDataBounds = paddedPlotBounds(
    plottedSeries.flatMap((item) => item.xValues),
    [
      ...validSeries.flatMap((item) => item.yValues),
      ...(model.band?.lowerValues ?? []),
      ...(model.band?.upperValues ?? []),
    ],
  );
  const observedEngineeringX = plottedSeries.flatMap((item) => item.xValues);
  const observedEngineeringY = validSeries.flatMap((item) => item.yValues);
  const isDataObservedEngineering = !ensemblePreview
    && !selectedModelOnly
    && Boolean(observedCurves?.length)
    && model.xQuantity === "strain.engineering"
    && model.yQuantity === "stress.engineering";
  const dataBounds = isDmaProny && pronyMode === "response"
    ? { ...paddedDataBounds, yMin: Math.max(0, paddedDataBounds.yMin) }
    : isDataObservedEngineering
      ? dataObservedPlotBounds(observedEngineeringX, observedEngineeringY, model.xQuantity, model.yQuantity)
      : paddedDataBounds;
  const bounds = viewBounds ?? dataBounds;
  const effectiveWidth = renderedSize?.width ?? fallbackWidth;
  const effectiveHeight = renderedSize?.height ?? fallbackHeight;
  // Keep every geometric calculation on the same responsive coordinate system as the SVG viewBox.
  const width = effectiveWidth;
  const height = effectiveHeight;
  const yScale = displayScale(model.yUnit, validSeries.flatMap((item) => item.yValues));
  const xTicks = model.xScale === "log10"
    ? Array.from(
        { length: Math.max(0, Math.floor(bounds.xMax) - Math.ceil(bounds.xMin) + 1) },
        (_, index) => Math.ceil(bounds.xMin) + index,
      ).filter((value) => value >= bounds.xMin && value <= bounds.xMax)
    : axisTicks(bounds.xMin, bounds.xMax);
  const yTicks = axisTicks(bounds.yMin, bounds.yMax);
  const extrapolationPlotStart = model.extrapolationStart === undefined
    ? undefined
    : toPlotX(model.extrapolationStart);
  const marker = useMemo(() => {
    if (ensemblePreview) return null;
    const keys = activeStage.method_id === "metal.proof_stress"
      ? { x: "proof_strain", y: "proof_stress", label: "Proof point" }
      : activeStage.method_id === "metal.necking_candidate"
        ? { x: "necking_candidate_engineering_strain", y: "necking_candidate_engineering_stress", label: "Automatic necking candidate" }
        : activeStage.method_id === "metal.engineering_to_true_plastic"
          ? { x: "necking_engineering_strain", y: "necking_engineering_stress", label: "Applied necking boundary" }
          : null;
    if (!keys) return null;
    const x = activeStage.scalar_results.find((item) => item.key === keys.x)?.value;
    const y = activeStage.scalar_results.find((item) => item.key === keys.y)?.value;
    return Number.isFinite(x) && Number.isFinite(y) ? { x: x!, y: y!, label: keys.label } : null;
  }, [activeStage, ensemblePreview]);

  useEffect(() => {
    setHiddenSeries([]);
    setViewBounds(null);
    setCursor(null);
    setDrag(null);
    setSelectionStart(null);
    setSelection(null);
    setHardeningMode("response");
    setPronyMode("response");
    if (ensemblePreview) setInteractionMode("pan");
  }, [activeStage.method_id, activeStage.ordinal, ensemblePreview]);

  useEffect(() => {
    const target = svgRef.current;
    if (!target) return undefined;
    const update = (nextWidth: number, nextHeight: number) => {
      if (!Number.isFinite(nextWidth) || !Number.isFinite(nextHeight) || nextWidth <= 0 || nextHeight <= 0) return;
      setRenderedSize((current) => current && Math.abs(current.width - nextWidth) < 1 && Math.abs(current.height - nextHeight) < 1
        ? current
        : { width: nextWidth, height: nextHeight });
    };
    const rectangle = target.getBoundingClientRect();
    update(rectangle.width, rectangle.height);
    if (typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) update(entry.contentRect.width, entry.contentRect.height);
    });
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    onInteractionStateChange?.({ mode: interactionMode, hasSelection: Boolean(selection) });
  }, [interactionMode, onInteractionStateChange, selection]);

  function applySelection(): void {
    if (!selection || !onApplySelection) return;
    onApplySelection(selection);
    setSelection(null);
    setSelectionStart(null);
    setInteractionMode("pan");
  }

  useEffect(() => {
    if (!hideInteractionControls || !interactionCommand) return;
    if (interactionCommand.action === "set-mode" && interactionCommand.mode) {
      setInteractionMode(interactionCommand.mode);
      if (interactionCommand.mode === "pan") {
        setSelection(null);
        setSelectionStart(null);
      }
    }
    if (interactionCommand.action === "apply") applySelection();
  }, [hideInteractionControls, interactionCommand]);

  function zoom(factor: number, center = cursor): void {
    const centerX = center?.x ?? (bounds.xMin + bounds.xMax) / 2;
    const centerY = center?.y ?? (bounds.yMin + bounds.yMax) / 2;
    setViewBounds({
      xMin: centerX - (centerX - bounds.xMin) * factor,
      xMax: centerX + (bounds.xMax - centerX) * factor,
      yMin: centerY - (centerY - bounds.yMin) * factor,
      yMax: centerY + (bounds.yMax - centerY) * factor,
    });
  }

  function pointerCoordinates(event: ReactPointerEvent<SVGSVGElement>): { x: number; y: number } {
    const rectangle = event.currentTarget.getBoundingClientRect();
    const px = Math.min(effectiveWidth - PLOT_MARGIN.right, Math.max(PLOT_MARGIN.left, ((event.clientX - rectangle.left) / rectangle.width) * effectiveWidth));
    const py = Math.min(effectiveHeight - PLOT_MARGIN.bottom, Math.max(PLOT_MARGIN.top, ((event.clientY - rectangle.top) / rectangle.height) * effectiveHeight));
    return {
      x: bounds.xMin + ((px - PLOT_MARGIN.left) / (effectiveWidth - PLOT_MARGIN.left - PLOT_MARGIN.right)) * (bounds.xMax - bounds.xMin),
      y: bounds.yMax - ((py - PLOT_MARGIN.top) / (effectiveHeight - PLOT_MARGIN.top - PLOT_MARGIN.bottom)) * (bounds.yMax - bounds.yMin),
    };
  }

  function onPointerMove(event: ReactPointerEvent<SVGSVGElement>): void {
    const coordinates = pointerCoordinates(event);
    setCursor(coordinates);
    if (interactionMode === "range" && selectionStart) {
      setSelection({
        kind: "range",
        x_quantity: model.xQuantity,
        x_unit: model.xUnit,
        minimum: fromPlotX(Math.min(selectionStart.x, coordinates.x)),
        maximum: fromPlotX(Math.max(selectionStart.x, coordinates.x)),
      });
      return;
    }
    if (!drag) return;
    const rectangle = event.currentTarget.getBoundingClientRect();
    const deltaX = ((event.clientX - drag.clientX) / rectangle.width) * (drag.bounds.xMax - drag.bounds.xMin);
    const deltaY = ((event.clientY - drag.clientY) / rectangle.height) * (drag.bounds.yMax - drag.bounds.yMin);
    setViewBounds({
      xMin: drag.bounds.xMin - deltaX,
      xMax: drag.bounds.xMax - deltaX,
      yMin: drag.bounds.yMin + deltaY,
      yMax: drag.bounds.yMax + deltaY,
    });
  }

  function endPointer(event: ReactPointerEvent<SVGSVGElement>): void {
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture?.(event.pointerId);
    }
    setDrag(null);
    setSelectionStart(null);
  }

  function onWheel(event: ReactWheelEvent<SVGSVGElement>): void {
    event.preventDefault();
    zoom(event.deltaY > 0 ? 1.18 : 0.82, pointerCoordinates(event as unknown as ReactPointerEvent<SVGSVGElement>));
  }

  if (!validSeries.length) {
    return <div className="modeling-plot-empty" role="status"><strong>No compatible curve can be plotted.</strong><p>The selected stage did not return paired finite x/y arrays. Review the stage diagnostics and channel mapping.</p></div>;
  }

  return (
    <>
      <div className="modeling-plot-toolbar" aria-label="Curve plot controls">
        <div>
          <button type="button" aria-label="Zoom out" onClick={() => zoom(1.25)}>−</button>
          <button type="button" aria-label="Zoom in" onClick={() => zoom(0.8)}>+</button>
          <button type="button" onClick={() => setViewBounds(null)}>Reset view</button>
        </div>
        {!hideInteractionControls ? <div className="plot-interaction-modes" role="group" aria-label="Graph selection mode">
          <button type="button" className={interactionMode === "pan" ? "active" : ""} aria-pressed={interactionMode === "pan"} onClick={() => setInteractionMode("pan")}>Pan</button>
          <button type="button" disabled={!onApplySelection} className={interactionMode === "range" ? "active" : ""} aria-pressed={interactionMode === "range"} onClick={() => setInteractionMode("range")}>Select range</button>
          <button type="button" disabled={!onApplySelection} className={interactionMode === "point" ? "active" : ""} aria-pressed={interactionMode === "point"} onClick={() => setInteractionMode("point")}>Pick point</button>
          <button type="button" disabled={!selection || !onApplySelection} onClick={applySelection}>Apply selection</button>
          {selection ? <button type="button" onClick={() => setSelection(null)}>Clear</button> : null}
        </div> : null}
        {!isHardening ? <span>{selection?.kind === "range" ? `Selected ${axisNumber(selection.minimum)} – ${axisNumber(selection.maximum)} ${selection.x_unit}` : selection?.kind === "point" ? `Selected ${axisNumber(selection.x)} ${selection.x_unit} · ${axisNumber(selection.y / yScale.divisor)} ${yScale.label}` : cursor ? `${axisNumber(fromPlotX(cursor.x))} ${model.xUnit} · ${axisNumber(cursor.y / yScale.divisor)} ${yScale.label}` : interactionMode === "pan" ? "Wheel to zoom · drag to pan" : interactionMode === "range" ? "Drag across the x-domain, then apply" : "Click one engineering point, then apply"}</span> : null}
      </div>
      {isHardening && !selectedModelOnly ? <div className="hardening-analysis-tabs" role="tablist" aria-label="Hardening comparison view">
        {(["response", "residual", "derivative"] as HardeningPlotMode[]).map((mode) => <button type="button" role="tab" aria-selected={hardeningMode === mode} className={hardeningMode === mode ? "active" : ""} key={mode} onClick={() => setHardeningMode(mode)}>{mode === "response" ? "Response" : mode === "residual" ? "Residual" : "Tangent modulus"}</button>)}
      </div> : null}
      {isProny && !selectedModelOnly ? <div className="hardening-analysis-tabs prony-analysis-tabs" role="tablist" aria-label="Prony comparison view">
        {(["response", "residual"] as PronyPlotMode[]).map((mode) => <button type="button" role="tab" aria-selected={pronyMode === mode} className={pronyMode === mode ? "active" : ""} key={mode} onClick={() => setPronyMode(mode)}>{mode === "response" ? isDmaProny ? "Storage & loss" : "Relaxation response" : "Residual"}</button>)}
        <span>{pronyMode === "response" ? isDmaProny ? `Measured storage/loss + ${fitSelection ? "explicit engineer selection" : "server result preview"}` : `Measured modulus + every fitted term count + ${fitSelection ? "explicit engineer selection" : "server result preview"}` : isDmaProny ? "Joint storage/loss residual on the observed log-frequency grid" : "Predicted minus measured modulus on the observed log-time grid"}</span>
      </div> : null}
      <svg
        ref={svgRef}
        className={`processing-curve interactive interaction-${interactionMode} ${drag ? "is-panning" : ""}`}
        role="img"
        aria-label={selectedModelOnly ? "Test data and selected model response" : ensemblePreview ? "Aligned replicate curves with pointwise mean and confidence interval" : activeStage.method_id === "metal.hardening_fit_extrapolate" ? "Hardening candidate and selected extrapolation curves" : activeStage.method_id === "polymer.dma_prony_fit_compare" ? "DMA storage and loss Prony candidate curves" : activeStage.method_id === "polymer.prony_fit_compare" ? "Prony candidate and selected relaxation curves" : "Mapped and selected processing stage curve overlay"}
        viewBox={`0 0 ${effectiveWidth} ${effectiveHeight}`}
        onDoubleClick={() => setViewBounds(null)}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          const coordinates = pointerCoordinates(event);
          event.currentTarget.setPointerCapture?.(event.pointerId);
          if (interactionMode === "range") {
            setSelectionStart(coordinates);
            setSelection({ kind: "range", x_quantity: model.xQuantity, x_unit: model.xUnit, minimum: fromPlotX(coordinates.x), maximum: fromPlotX(coordinates.x) });
          } else if (interactionMode === "point") {
            setSelection({ kind: "point", x_quantity: model.xQuantity, x_unit: model.xUnit, x: fromPlotX(coordinates.x), y_quantity: model.yQuantity, y_unit: model.yUnit, y: coordinates.y });
          } else {
            setDrag({ clientX: event.clientX, clientY: event.clientY, bounds });
          }
        }}
        onPointerMove={onPointerMove}
        onPointerLeave={() => setCursor(null)}
        onPointerUp={endPointer}
        onPointerCancel={endPointer}
        onWheel={onWheel}
      >
        {xTicks.map((tick) => {
          const px = PLOT_MARGIN.left + ((tick - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (effectiveWidth - PLOT_MARGIN.left - PLOT_MARGIN.right);
          return <g key={`x-${tick}`}><line x1={px} y1={PLOT_MARGIN.top} x2={px} y2={effectiveHeight - PLOT_MARGIN.bottom} className="chart-grid"/><text x={px} y={effectiveHeight - 32} textAnchor="middle" className="chart-tick">{axisNumber(fromPlotX(tick))}</text></g>;
        })}
        {yTicks.map((tick) => {
          const py = effectiveHeight - PLOT_MARGIN.bottom - ((tick - bounds.yMin) / (bounds.yMax - bounds.yMin || 1)) * (effectiveHeight - PLOT_MARGIN.top - PLOT_MARGIN.bottom);
          return <g key={`y-${tick}`}><line x1={PLOT_MARGIN.left} y1={py} x2={effectiveWidth - PLOT_MARGIN.right} y2={py} className="chart-grid"/><text x={PLOT_MARGIN.left - 8} y={py + 4} textAnchor="end" className="chart-tick">{axisNumber(tick / yScale.divisor)}</text></g>;
        })}
        {extrapolationPlotStart !== undefined && extrapolationPlotStart < bounds.xMax ? <g className="extrapolation-region"><rect x={PLOT_MARGIN.left + ((Math.max(extrapolationPlotStart, bounds.xMin) - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (effectiveWidth - PLOT_MARGIN.left - PLOT_MARGIN.right)} y={PLOT_MARGIN.top} width={Math.max(0, ((bounds.xMax - Math.max(extrapolationPlotStart, bounds.xMin)) / (bounds.xMax - bounds.xMin || 1)) * (effectiveWidth - PLOT_MARGIN.left - PLOT_MARGIN.right))} height={effectiveHeight - PLOT_MARGIN.top - PLOT_MARGIN.bottom}/><line x1={PLOT_MARGIN.left + ((extrapolationPlotStart - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (effectiveWidth - PLOT_MARGIN.left - PLOT_MARGIN.right)} y1={PLOT_MARGIN.top} x2={PLOT_MARGIN.left + ((extrapolationPlotStart - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (effectiveWidth - PLOT_MARGIN.left - PLOT_MARGIN.right)} y2={effectiveHeight - PLOT_MARGIN.bottom}/><text x={PLOT_MARGIN.left + ((extrapolationPlotStart - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (effectiveWidth - PLOT_MARGIN.left - PLOT_MARGIN.right) + 7} y={PLOT_MARGIN.top + 14}>EXTRAPOLATED · UNOBSERVED</text></g> : null}
        <line x1={PLOT_MARGIN.left} y1={effectiveHeight - PLOT_MARGIN.bottom} x2={effectiveWidth - PLOT_MARGIN.right} y2={effectiveHeight - PLOT_MARGIN.bottom} className="chart-axis" />
        <line x1={PLOT_MARGIN.left} y1={PLOT_MARGIN.top} x2={PLOT_MARGIN.left} y2={effectiveHeight - PLOT_MARGIN.bottom} className="chart-axis" />
        {plottedBand && plottedBand.xValues.length >= 2 ? <polygon points={bandPolygon(plottedBand, effectiveWidth, effectiveHeight, bounds)} className="ensemble-confidence-band" /> : null}
        {plottedSeries.filter((series) => hardeningResponseSeries.some((item) => item.id === series.id)).map((series) => hiddenSeries.includes(series.id) ? null : <polyline key={series.id} points={plotPoints(series.xValues, series.yValues, effectiveWidth, effectiveHeight, bounds)} className={`curve-line ${series.className}`} style={{ stroke: series.color }} />)}
        {marker ? <g className="engineering-result-marker"><line x1={PLOT_MARGIN.left + ((toPlotX(marker.x) - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (width - PLOT_MARGIN.left - PLOT_MARGIN.right)} y1={PLOT_MARGIN.top} x2={PLOT_MARGIN.left + ((toPlotX(marker.x) - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (width - PLOT_MARGIN.left - PLOT_MARGIN.right)} y2={height - PLOT_MARGIN.bottom}/><circle cx={PLOT_MARGIN.left + ((toPlotX(marker.x) - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (width - PLOT_MARGIN.left - PLOT_MARGIN.right)} cy={height - PLOT_MARGIN.bottom - ((marker.y - bounds.yMin) / (bounds.yMax - bounds.yMin || 1)) * (height - PLOT_MARGIN.top - PLOT_MARGIN.bottom)} r="5"/><text x={PLOT_MARGIN.left + ((toPlotX(marker.x) - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (width - PLOT_MARGIN.left - PLOT_MARGIN.right) + 8} y={Math.max(PLOT_MARGIN.top + 12, height - PLOT_MARGIN.bottom - ((marker.y - bounds.yMin) / (bounds.yMax - bounds.yMin || 1)) * (height - PLOT_MARGIN.top - PLOT_MARGIN.bottom) - 8)}>{marker.label}</text></g> : null}
        {selection?.kind === "range" ? <rect className="graph-range-selection" x={PLOT_MARGIN.left + ((toPlotX(selection.minimum) - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (width - PLOT_MARGIN.left - PLOT_MARGIN.right)} y={PLOT_MARGIN.top} width={Math.max(1, ((toPlotX(selection.maximum) - toPlotX(selection.minimum)) / (bounds.xMax - bounds.xMin || 1)) * (width - PLOT_MARGIN.left - PLOT_MARGIN.right))} height={height - PLOT_MARGIN.top - PLOT_MARGIN.bottom} /> : null}
        {selection?.kind === "point" ? <><line className="graph-point-selection" x1={PLOT_MARGIN.left + ((toPlotX(selection.x) - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (width - PLOT_MARGIN.left - PLOT_MARGIN.right)} y1={PLOT_MARGIN.top} x2={PLOT_MARGIN.left + ((toPlotX(selection.x) - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (width - PLOT_MARGIN.left - PLOT_MARGIN.right)} y2={height - PLOT_MARGIN.bottom} /><circle className="graph-point-marker" cx={PLOT_MARGIN.left + ((toPlotX(selection.x) - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (width - PLOT_MARGIN.left - PLOT_MARGIN.right)} cy={height - PLOT_MARGIN.bottom - ((selection.y - bounds.yMin) / (bounds.yMax - bounds.yMin || 1)) * (height - PLOT_MARGIN.top - PLOT_MARGIN.bottom)} r="5" /></> : null}
        {cursor ? <><line x1={PLOT_MARGIN.left + ((cursor.x - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (width - PLOT_MARGIN.left - PLOT_MARGIN.right)} y1={PLOT_MARGIN.top} x2={PLOT_MARGIN.left + ((cursor.x - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (width - PLOT_MARGIN.left - PLOT_MARGIN.right)} y2={height - PLOT_MARGIN.bottom} className="chart-crosshair"/><line x1={PLOT_MARGIN.left} y1={height - PLOT_MARGIN.bottom - ((cursor.y - bounds.yMin) / (bounds.yMax - bounds.yMin || 1)) * (height - PLOT_MARGIN.top - PLOT_MARGIN.bottom)} x2={width - PLOT_MARGIN.right} y2={height - PLOT_MARGIN.bottom - ((cursor.y - bounds.yMin) / (bounds.yMax - bounds.yMin || 1)) * (height - PLOT_MARGIN.top - PLOT_MARGIN.bottom)} className="chart-crosshair"/></> : null}
        <text x={(PLOT_MARGIN.left + width - PLOT_MARGIN.right) / 2} y={height - 8} textAnchor="middle" className="chart-axis-label">{quantityLabel(model.xQuantity)} [{model.xUnit}]{model.xScale === "log10" ? " · logarithmic" : ""}</text>
        <text transform={`translate(15 ${(PLOT_MARGIN.top + height - PLOT_MARGIN.bottom) / 2}) rotate(-90)`} textAnchor="middle" className="chart-axis-label">{quantityLabel(model.yQuantity)} [{yScale.label}]</text>
      </svg>
      <div className="curve-legend interactive" aria-label="Curve visibility">
        {validSeries.filter((series, index, all) => hardeningResponseSeries.some((item) => item.id === series.id) && (!isHardening || !series.className.includes("extrapolated-domain")) && (!isHardening || index === all.findIndex((item) => item.id.split(".observed")[0] === series.id.split(".observed")[0]))).map((series) => <button type="button" className={hiddenSeries.includes(series.id) ? "hidden" : ""} key={series.id} onClick={() => setHiddenSeries((current) => current.includes(series.id) ? current.filter((item) => item !== series.id) : [...current, series.id])} aria-pressed={!hiddenSeries.includes(series.id)}><i style={{ background: series.color }} />{isHardening && series.className.includes("fitted-domain") ? series.label.replace(" · fit", "") : series.label}</button>)}
        {isHardening && hardeningMode === "response" ? <span className="curve-band-legend">Shaded: extrapolated/unobserved</span> : null}
        {model.band ? <span className="curve-band-legend"><i />{model.band.label}</span> : null}
      </div>
      {!selectedModelOnly && (ensemblePreview?.diagnostics ?? activeStage.diagnostics).length ? <details className="stage-diagnostics"><summary>{ensemblePreview ? "Alignment and statistics notes" : "Calculation notes"} <span>{(ensemblePreview?.diagnostics ?? activeStage.diagnostics).length}</span></summary>{(ensemblePreview?.diagnostics ?? activeStage.diagnostics).map((item) => <p key={item}>{item}</p>)}</details> : null}
      {!selectedModelOnly && !ensemblePreview && (activeStage.scalar_results ?? []).length ? <details className="model-diagnostics-details"><summary>Parameters and numerical evidence ({activeStage.scalar_results?.length})</summary><div className="metal-scalar-grid" aria-label="Processing scalar results">{(activeStage.scalar_results ?? []).map((item) => <article key={item.key}><span>{item.key.replaceAll("_", " ").replaceAll(".", " ")}</span><strong>{item.unit === "Pa" ? `${(item.value / 1e9).toPrecision(6)} GPa` : item.value.toPrecision(7)}</strong><small>{item.quantity_semantics} · {item.unit}</small></article>)}</div></details> : null}
      <p className="digest-line diagnostics-only"><span>Mapping SHA-256</span><code>{preview.mapping_profile_sha256}</code></p>
    </>
  );
}
