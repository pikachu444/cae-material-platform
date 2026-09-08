import { useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  channelAxisLabel,
  curveDisplayModel,
  curveSegments,
  deviationMeaning,
  deviationSourceCount,
  displayCurveMagnitude,
  formatEngineeringNumber,
  originalUnitSummary,
  type CurveDefinitionContract,
  type CurveSeriesPreviewContract,
} from "../model/curve-contracts";
import styles from "./CurvePreview.module.css";

interface CurvePreviewProps {
  definition: CurveDefinitionContract;
  preview: CurveSeriesPreviewContract;
  compact?: boolean;
}

interface PlotSize { width: number; height: number; }
interface PlotGeometry extends PlotSize {
  left: number;
  right: number;
  top: number;
  bottom: number;
  fontSize: number;
}

const FALLBACK_SIZE: PlotSize = { width: 720, height: 320 };

function usePlotSize(frameRef: React.RefObject<HTMLDivElement | null>): PlotSize {
  const [size, setSize] = useState(FALLBACK_SIZE);
  useLayoutEffect(() => {
    const frame = frameRef.current;
    if (!frame) return undefined;
    const measure = () => {
      const rect = frame.getBoundingClientRect();
      const width = Math.max(360, Math.round(rect.width));
      const height = Math.max(220, Math.round(rect.height));
      setSize((current) => current.width === width && current.height === height ? current : { width, height });
    };
    measure();
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(measure);
      observer.observe(frame);
      return () => observer.disconnect();
    }
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [frameRef]);
  return size;
}

function geometryFor(size: PlotSize, compact: boolean): PlotGeometry {
  const fontSize = Math.max(11, Math.min(15, size.width / 105));
  const left = Math.max(68, Math.min(94, size.width * 0.095));
  const right = Math.max(20, Math.min(42, size.width * 0.032));
  const top = compact ? 18 : 24;
  const bottom = Math.max(50, Math.min(70, size.height * 0.19));
  return { ...size, left, right, top, bottom, fontSize };
}

function finiteValues(values: Array<number | null>): number[] {
  return values.filter((value): value is number => value !== null && Number.isFinite(value));
}

function domainFor(values: Array<number | null>, includeZero = true): [number, number] {
  const finite = finiteValues(values);
  if (!finite.length) return [0, 1];
  const observedMin = Math.min(...finite);
  const observedMax = Math.max(...finite);
  const min = includeZero && observedMin > 0 ? 0 : observedMin;
  const max = includeZero && observedMax < 0 ? 0 : observedMax;
  const range = Math.max(Math.abs(max - min), Math.max(Math.abs(min), Math.abs(max)) * 0.05, Number.EPSILON);
  const padding = range * 0.06;
  return [min === 0 ? 0 : min - padding, max === 0 ? 0 : max + padding];
}

function tickValues([min, max]: [number, number]): number[] {
  const span = max - min || 1;
  return Array.from({ length: 5 }, (_, index) => min + (span * index) / 4);
}

function pathForSegment(segment: Array<{ x: number; y: number }>, xDomain: [number, number], yDomain: [number, number], geometry: PlotGeometry): string {
  const xRange = xDomain[1] - xDomain[0] || 1;
  const yRange = yDomain[1] - yDomain[0] || 1;
  const plotWidth = geometry.width - geometry.left - geometry.right;
  const plotHeight = geometry.height - geometry.top - geometry.bottom;
  return segment.map((point, index) => {
    const x = geometry.left + ((point.x - xDomain[0]) / xRange) * plotWidth;
    const y = geometry.height - geometry.bottom - ((point.y - yDomain[0]) / yRange) * plotHeight;
    return `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(" ");
}

function bandPaths(model: NonNullable<ReturnType<typeof curveDisplayModel>>, xDomain: [number, number], yDomain: [number, number], geometry: PlotGeometry): string[] {
  if (!model.band) return [];
  const paths: string[] = [];
  let lower: Array<{ x: number; y: number }> = [];
  let upper: Array<{ x: number; y: number }> = [];
  const flush = () => {
    if (lower.length > 1 && upper.length > 1) {
      const lowerPath = pathForSegment(lower, xDomain, yDomain, geometry);
      const upperPath = pathForSegment([...upper].reverse(), xDomain, yDomain, geometry).replace(/^M/, "L");
      paths.push(`${lowerPath} ${upperPath} Z`);
    }
    lower = [];
    upper = [];
  };
  for (let index = 0; index < model.xValues.length; index += 1) {
    const x = model.xValues[index];
    const low = model.band.lowerValues[index];
    const high = model.band.upperValues[index];
    if (x === null || low === null || high === null || !Number.isFinite(x) || !Number.isFinite(low) || !Number.isFinite(high)) {
      flush();
      continue;
    }
    lower.push({ x, y: low });
    upper.push({ x, y: high });
  }
  flush();
  return paths;
}

function screenPoint(value: number, domain: [number, number], start: number, length: number): number {
  return start + ((value - domain[0]) / (domain[1] - domain[0] || 1)) * length;
}

export function CurvePreview({ definition, preview, compact = false }: CurvePreviewProps) {
  const model = useMemo(() => curveDisplayModel(definition, preview), [definition, preview]);
  const frameRef = useRef<HTMLDivElement>(null);
  const size = usePlotSize(frameRef);
  if (!model) {
    return <p className={styles.invalid} role="alert">Curve metadata is incomplete. Identity is retained; preview is blocked.</p>;
  }
  const geometry = geometryFor(size, compact);
  const allYValues = [...model.yValues, ...(model.band?.lowerValues ?? []), ...(model.band?.upperValues ?? [])];
  const xDomain = domainFor(model.xValues);
  const yDomain = domainFor(allYValues);
  const xTicks = tickValues(xDomain);
  const yTicks = tickValues(yDomain);
  const segments = curveSegments(model.xValues, model.yValues);
  const bands = bandPaths(model, xDomain, yDomain, geometry);
  const rows = model.xValues.slice(0, compact ? 6 : 12).map((x, index) => ({ x, y: model.yValues[index], index }));
  const deviation = definition.deviations.find((item) => item.bound_direction !== "none") ?? definition.deviations[0];
  const deviationSample = deviation ? displayCurveMagnitude(model.dependent, deviation.scalar_value === null ? null : Number(deviation.scalar_value)) : null;
  const plotWidth = geometry.width - geometry.left - geometry.right;
  const plotHeight = geometry.height - geometry.top - geometry.bottom;
  const titleId = `${definition.definition_version}-curve-title`;
  const descriptionId = `${definition.definition_version}-curve-description`;

  return (
    <section className={styles.wrapper} aria-labelledby={titleId}>
      <div className={styles.heading}>
        <div>
          <h3 id={titleId}>Curve preview</h3>
          <p>{channelAxisLabel(model.independent)} · {channelAxisLabel(model.dependent)}</p>
        </div>
        <span className={styles.pointCount}>{preview.returned_point_count.toLocaleString()} preview / {preview.point_count.toLocaleString()} source points</span>
      </div>
      <div ref={frameRef} className={`${styles.plotFrame} ${compact ? styles.compact : ""}`}>
        <svg data-testid="curve-plot" className={styles.plot} width={geometry.width} height={geometry.height} viewBox={`0 0 ${geometry.width} ${geometry.height}`} role="img" aria-labelledby={`${titleId} ${descriptionId}`}>
          <desc id={descriptionId}>Engineering curve with {channelAxisLabel(model.independent)} on the horizontal axis and {channelAxisLabel(model.dependent)} on the vertical axis. The shaded band is pointwise standard deviation and null source gaps remain disconnected.</desc>
          {yTicks.map((tick) => { const y = screenPoint(tick, yDomain, geometry.height - geometry.bottom - plotHeight, plotHeight); return <g key={`y-${tick}`}><line x1={geometry.left} x2={geometry.width - geometry.right} y1={y} y2={y} className={styles.grid} /><text x={geometry.left - 10} y={y + geometry.fontSize * 0.35} textAnchor="end" className={styles.axisLabel} style={{ fontSize: geometry.fontSize }}>{formatEngineeringNumber(tick)}</text></g>; })}
          {xTicks.map((tick) => { const x = screenPoint(tick, xDomain, geometry.left, plotWidth); return <g key={`x-${tick}`}><line x1={x} x2={x} y1={geometry.top} y2={geometry.height - geometry.bottom} className={styles.grid} /><text x={x} y={geometry.height - geometry.bottom + geometry.fontSize * 1.8} textAnchor="middle" className={styles.axisLabel} style={{ fontSize: geometry.fontSize }}>{formatEngineeringNumber(tick)}</text></g>; })}
          <line x1={geometry.left} x2={geometry.width - geometry.right} y1={geometry.height - geometry.bottom} y2={geometry.height - geometry.bottom} className={styles.axis} />
          <line x1={geometry.left} x2={geometry.left} y1={geometry.top} y2={geometry.height - geometry.bottom} className={styles.axis} />
          {bands.map((path, index) => <path key={`band-${index}`} d={path} className={styles.band} />)}
          {segments.map((segment, index) => <path key={`segment-${index}`} d={pathForSegment(segment, xDomain, yDomain, geometry)} className={styles.curve} />)}
          <text x={geometry.left + plotWidth / 2} y={geometry.height - 8} textAnchor="middle" className={styles.axisTitle} style={{ fontSize: geometry.fontSize }}>{model.independent.label} [{model.independent.display_unit}]</text>
          <text transform={`translate(16 ${geometry.top + plotHeight / 2}) rotate(-90)`} textAnchor="middle" className={styles.axisTitle} style={{ fontSize: geometry.fontSize }}>{model.dependent.label} [{model.dependent.display_unit}]</text>
        </svg>
      </div>
      <div className={styles.legend}>
        <span><i className={styles.lineSwatch} /> Mean response · n={deviation ? deviationSourceCount(deviation, preview, 0) ?? "—" : "—"}</span>
        {model.band ? <span><i className={styles.deviationSwatch} /> Band · standard deviation · pointwise</span> : null}
        {deviationSample !== null ? <span>Deviation sample {formatEngineeringNumber(deviationSample)} {model.dependent.display_unit}</span> : null}
      </div>
      <details className={styles.points}>
        <summary>Point data ({rows.length} shown)</summary>
        <table>
          <caption className="sr-only">Curve point data alternative</caption>
          <thead><tr><th scope="col">{model.independent.label} [{model.independent.display_unit}]</th><th scope="col">{model.dependent.label} [{model.dependent.display_unit}]</th></tr></thead>
          <tbody>{rows.map((point) => <tr key={`${definition.definition_version}-point-${point.index}`}><td>{point.x === null ? "—" : formatEngineeringNumber(point.x)}</td><td>{point.y === null ? "—" : formatEngineeringNumber(point.y)}</td></tr>)}</tbody>
        </table>
      </details>
      <details className={styles.contractDetails}>
        <summary>Curve contract</summary>
        <p>Display values preserve the declared conversion. Original units: {originalUnitSummary(model.independent)}, {originalUnitSummary(model.dependent)}. Deviation magnitudes use scale only; missing points remain disconnected.</p>
        {definition.deviations.length > 0 ? <p>{definition.deviations.map((item) => deviationMeaning(item)).join(" · ")}</p> : null}
      </details>
    </section>
  );
}
