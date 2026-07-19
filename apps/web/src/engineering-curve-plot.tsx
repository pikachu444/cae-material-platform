import {
  useEffect,
  useMemo,
  useState,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from "react";

import type { CommonCurveStage, CommonProcessingPreview } from "./types";

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

const PLOT_MARGIN = { left: 64, right: 24, top: 24, bottom: 52 } as const;
const CANDIDATE_COLORS = ["#64748b", "#0f766e", "#d97706", "#7c3aed", "#dc2626"];

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
): { xQuantity: string; xUnit: string; yQuantity: string; yUnit: string; series: PlotSeries[] } {
  const hardening = activeStage.method_id === "metal.hardening_fit_extrapolate";
  const prony = activeStage.method_id === "polymer.prony_fit_compare";
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
    const selected = activeStage.series.find((item) => item.quantity === "stress.hardening.selected");
    return {
      xQuantity,
      xUnit: activeX?.unit ?? "1",
      yQuantity: "stress.hardening",
      yUnit: selected?.unit ?? candidates[0]?.unit ?? "Pa",
      series: [
        ...candidates.map((item, index) => ({
          id: item.quantity,
          label: item.quantity.replace("stress.hardening.", ""),
          xValues: activeX?.values ?? [],
          yValues: item.values,
          color: CANDIDATE_COLORS[index % CANDIDATE_COLORS.length],
          className: "hardening-candidate",
        })),
        ...(selected ? [{
          id: selected.quantity,
          label: "Selected combination",
          xValues: activeX?.values ?? [],
          yValues: selected.values,
          color: "#111827",
          className: "hardening-selected",
        }] : []),
      ],
    };
  }

  if (prony) {
    const candidates = activeStage.series.filter((item) => item.quantity.startsWith("modulus.prony.candidate_"));
    const selected = activeStage.series.find((item) => item.quantity === "modulus.prony.selected");
    return {
      xQuantity,
      xUnit: activeX?.unit ?? "s",
      yQuantity: "modulus.shear.relaxation",
      yUnit: selected?.unit ?? candidates[0]?.unit ?? "Pa",
      series: [
        ...candidates.map((item, index) => ({
          id: item.quantity,
          label: item.quantity.replace("modulus.prony.candidate_", "").replaceAll("_", " "),
          xValues: activeX?.values ?? [],
          yValues: item.values,
          color: CANDIDATE_COLORS[index % CANDIDATE_COLORS.length],
          className: "hardening-candidate",
        })),
        ...(selected ? [{
          id: selected.quantity,
          label: "Selected Prony candidate",
          xValues: activeX?.values ?? [],
          yValues: selected.values,
          color: "#111827",
          className: "hardening-selected",
        }] : []),
      ],
    };
  }

  const baseDependent = baseStage.series.find((item) => item.quantity !== xQuantity);
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
    ],
  };
}

export function EngineeringCurvePlot({
  preview,
  activeStage,
  baseStage,
  width,
  height,
}: {
  preview: CommonProcessingPreview;
  activeStage: CommonCurveStage;
  baseStage: CommonCurveStage;
  width: number;
  height: number;
}) {
  const [hiddenSeries, setHiddenSeries] = useState<string[]>([]);
  const [viewBounds, setViewBounds] = useState<PlotBounds | null>(null);
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);
  const [drag, setDrag] = useState<{ clientX: number; clientY: number; bounds: PlotBounds } | null>(null);
  const model = useMemo(
    () => seriesForStage(preview, activeStage, baseStage),
    [activeStage, baseStage, preview],
  );
  const validSeries = model.series.filter(
    (item) => item.xValues.length >= 2 && item.xValues.length === item.yValues.length,
  );
  const dataBounds = paddedPlotBounds(
    validSeries.flatMap((item) => item.xValues),
    validSeries.flatMap((item) => item.yValues),
  );
  const bounds = viewBounds ?? dataBounds;
  const yScale = displayScale(model.yUnit, validSeries.flatMap((item) => item.yValues));
  const xTicks = axisTicks(bounds.xMin, bounds.xMax);
  const yTicks = axisTicks(bounds.yMin, bounds.yMax);

  useEffect(() => {
    setHiddenSeries([]);
    setViewBounds(null);
    setCursor(null);
    setDrag(null);
  }, [activeStage.method_id, activeStage.ordinal]);

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
    const px = Math.min(width - PLOT_MARGIN.right, Math.max(PLOT_MARGIN.left, ((event.clientX - rectangle.left) / rectangle.width) * width));
    const py = Math.min(height - PLOT_MARGIN.bottom, Math.max(PLOT_MARGIN.top, ((event.clientY - rectangle.top) / rectangle.height) * height));
    return {
      x: bounds.xMin + ((px - PLOT_MARGIN.left) / (width - PLOT_MARGIN.left - PLOT_MARGIN.right)) * (bounds.xMax - bounds.xMin),
      y: bounds.yMax - ((py - PLOT_MARGIN.top) / (height - PLOT_MARGIN.top - PLOT_MARGIN.bottom)) * (bounds.yMax - bounds.yMin),
    };
  }

  function onPointerMove(event: ReactPointerEvent<SVGSVGElement>): void {
    setCursor(pointerCoordinates(event));
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
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setDrag(null);
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
        <span>{cursor ? `${axisNumber(cursor.x)} ${model.xUnit} · ${axisNumber(cursor.y / yScale.divisor)} ${yScale.label}` : "Wheel to zoom · drag to pan"}</span>
      </div>
      <svg
        className={`processing-curve interactive ${drag ? "is-panning" : ""}`}
        role="img"
        aria-label={activeStage.method_id === "metal.hardening_fit_extrapolate" ? "Hardening candidate and selected extrapolation curves" : activeStage.method_id === "polymer.prony_fit_compare" ? "Prony candidate and selected relaxation curves" : "Mapped and selected processing stage curve overlay"}
        viewBox={`0 0 ${width} ${height}`}
        onDoubleClick={() => setViewBounds(null)}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.currentTarget.setPointerCapture(event.pointerId);
          setDrag({ clientX: event.clientX, clientY: event.clientY, bounds });
        }}
        onPointerMove={onPointerMove}
        onPointerLeave={() => setCursor(null)}
        onPointerUp={endPointer}
        onPointerCancel={endPointer}
        onWheel={onWheel}
      >
        {xTicks.map((tick) => {
          const px = PLOT_MARGIN.left + ((tick - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (width - PLOT_MARGIN.left - PLOT_MARGIN.right);
          return <g key={`x-${tick}`}><line x1={px} y1={PLOT_MARGIN.top} x2={px} y2={height - PLOT_MARGIN.bottom} className="chart-grid"/><text x={px} y={height - 32} textAnchor="middle" className="chart-tick">{axisNumber(tick)}</text></g>;
        })}
        {yTicks.map((tick) => {
          const py = height - PLOT_MARGIN.bottom - ((tick - bounds.yMin) / (bounds.yMax - bounds.yMin || 1)) * (height - PLOT_MARGIN.top - PLOT_MARGIN.bottom);
          return <g key={`y-${tick}`}><line x1={PLOT_MARGIN.left} y1={py} x2={width - PLOT_MARGIN.right} y2={py} className="chart-grid"/><text x={PLOT_MARGIN.left - 8} y={py + 4} textAnchor="end" className="chart-tick">{axisNumber(tick / yScale.divisor)}</text></g>;
        })}
        <line x1={PLOT_MARGIN.left} y1={height - PLOT_MARGIN.bottom} x2={width - PLOT_MARGIN.right} y2={height - PLOT_MARGIN.bottom} className="chart-axis" />
        <line x1={PLOT_MARGIN.left} y1={PLOT_MARGIN.top} x2={PLOT_MARGIN.left} y2={height - PLOT_MARGIN.bottom} className="chart-axis" />
        {validSeries.map((series) => hiddenSeries.includes(series.id) ? null : <polyline key={series.id} points={plotPoints(series.xValues, series.yValues, width, height, bounds)} className={`curve-line ${series.className}`} style={{ stroke: series.color }} />)}
        {cursor ? <><line x1={PLOT_MARGIN.left + ((cursor.x - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (width - PLOT_MARGIN.left - PLOT_MARGIN.right)} y1={PLOT_MARGIN.top} x2={PLOT_MARGIN.left + ((cursor.x - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (width - PLOT_MARGIN.left - PLOT_MARGIN.right)} y2={height - PLOT_MARGIN.bottom} className="chart-crosshair"/><line x1={PLOT_MARGIN.left} y1={height - PLOT_MARGIN.bottom - ((cursor.y - bounds.yMin) / (bounds.yMax - bounds.yMin || 1)) * (height - PLOT_MARGIN.top - PLOT_MARGIN.bottom)} x2={width - PLOT_MARGIN.right} y2={height - PLOT_MARGIN.bottom - ((cursor.y - bounds.yMin) / (bounds.yMax - bounds.yMin || 1)) * (height - PLOT_MARGIN.top - PLOT_MARGIN.bottom)} className="chart-crosshair"/></> : null}
        <text x={(PLOT_MARGIN.left + width - PLOT_MARGIN.right) / 2} y={height - 8} textAnchor="middle" className="chart-axis-label">{model.xQuantity} [{model.xUnit}]</text>
        <text transform={`translate(15 ${(PLOT_MARGIN.top + height - PLOT_MARGIN.bottom) / 2}) rotate(-90)`} textAnchor="middle" className="chart-axis-label">{model.yQuantity} [{yScale.label}]</text>
      </svg>
      <div className="curve-legend interactive" aria-label="Curve visibility">
        {validSeries.map((series) => <button type="button" className={hiddenSeries.includes(series.id) ? "hidden" : ""} key={series.id} onClick={() => setHiddenSeries((current) => current.includes(series.id) ? current.filter((item) => item !== series.id) : [...current, series.id])} aria-pressed={!hiddenSeries.includes(series.id)}><i style={{ background: series.color }} />{series.label}</button>)}
      </div>
      <div className="stage-diagnostics">{activeStage.diagnostics.map((item) => <p key={item}>{item}</p>)}</div>
      {(activeStage.scalar_results ?? []).length ? <details className="model-diagnostics-details"><summary>Parameters and numerical evidence ({activeStage.scalar_results?.length})</summary><div className="metal-scalar-grid" aria-label="Processing scalar results">{(activeStage.scalar_results ?? []).map((item) => <article key={item.key}><span>{item.key.replaceAll("_", " ").replaceAll(".", " ")}</span><strong>{item.unit === "Pa" ? `${(item.value / 1e9).toPrecision(6)} GPa` : item.value.toPrecision(7)}</strong><small>{item.quantity_semantics} · {item.unit}</small></article>)}</div></details> : null}
      <p className="digest-line diagnostics-only"><span>Mapping SHA-256</span><code>{preview.mapping_profile_sha256}</code></p>
    </>
  );
}
