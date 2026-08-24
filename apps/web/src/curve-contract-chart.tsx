import {
  useId,
  useMemo,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";

import {
  channelAxisLabel,
  curveDisplayModel,
  deviationMeaning,
  deviationSourceCount,
  displayCurveValue,
  originalUnitSummary,
} from "./curve-contract";
import type { CatalogCurvePreviewResponse, CurveChannelContract } from "./types";
import "./features/materials/ui/curve-contract-chart.css";

const VIEW_WIDTH = 960;
const VIEW_HEIGHT = 430;
const MARGIN = { left: 78, right: 24, top: 24, bottom: 58 };

interface Bounds {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
}

function paddedBounds(values: Array<number | null>): [number, number] {
  const finite = values.filter((item): item is number => item !== null && Number.isFinite(item));
  if (!finite.length) return [0, 1];
  const minimum = Math.min(...finite);
  const maximum = Math.max(...finite);
  const span = maximum - minimum;
  const padding = Math.max(span * 0.06, Math.abs(maximum || 1) * 0.01);
  return span === 0 ? [minimum - padding, maximum + padding] : [minimum - padding, maximum + padding];
}

function ticks(minimum: number, maximum: number): number[] {
  return Array.from({ length: 6 }, (_, index) => minimum + ((maximum - minimum) * index) / 5);
}

function numberText(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "missing";
  if (value === 0) return "0";
  const absolute = Math.abs(value);
  return absolute >= 10000 || absolute < 0.001
    ? value.toExponential(4)
    : new Intl.NumberFormat(undefined, { maximumSignificantDigits: 6 }).format(value);
}

function point(
  x: number,
  y: number,
  bounds: Bounds,
): { x: number; y: number } {
  return {
    x: MARGIN.left + ((x - bounds.xMin) / (bounds.xMax - bounds.xMin || 1)) * (VIEW_WIDTH - MARGIN.left - MARGIN.right),
    y: VIEW_HEIGHT - MARGIN.bottom - ((y - bounds.yMin) / (bounds.yMax - bounds.yMin || 1)) * (VIEW_HEIGHT - MARGIN.top - MARGIN.bottom),
  };
}

function linePath(
  xValues: Array<number | null>,
  yValues: Array<number | null>,
  bounds: Bounds,
): string {
  let path = "";
  let continuing = false;
  xValues.forEach((x, index) => {
    const y = yValues[index];
    if (x === null || y === null || !Number.isFinite(x) || !Number.isFinite(y)) {
      continuing = false;
      return;
    }
    const plotted = point(x, y, bounds);
    path += `${continuing ? "L" : "M"}${plotted.x.toFixed(2)},${plotted.y.toFixed(2)} `;
    continuing = true;
  });
  return path.trim();
}

function bandPath(
  xValues: Array<number | null>,
  lowerValues: Array<number | null>,
  upperValues: Array<number | null>,
  bounds: Bounds,
): string {
  const complete = xValues.map((x, index) => ({ x, lower: lowerValues[index], upper: upperValues[index] }))
    .filter((item): item is { x: number; lower: number; upper: number } => (
      item.x !== null && item.lower !== null && item.upper !== null
      && Number.isFinite(item.x) && Number.isFinite(item.lower) && Number.isFinite(item.upper)
    ));
  if (complete.length < 2) return "";
  const upper = complete.map((item) => point(item.x, item.upper, bounds));
  const lower = complete.slice().reverse().map((item) => point(item.x, item.lower, bounds));
  return [...upper, ...lower]
    .map((item, index) => `${index === 0 ? "M" : "L"}${item.x.toFixed(2)},${item.y.toFixed(2)}`)
    .join(" ") + " Z";
}

function channelSummary(channel: CurveChannelContract): string {
  return `${channel.label}: original ${originalUnitSummary(channel)} · normalized ${channel.normalized_unit} · display ${channel.display_unit}`;
}

export function CurveContractChart({
  preview,
  title,
  onOpenModeling,
  modelingUnavailableReason,
}: {
  preview: CatalogCurvePreviewResponse;
  title: string;
  onOpenModeling?: (source: NonNullable<CatalogCurvePreviewResponse["modeling_source"]>) => void;
  modelingUnavailableReason?: string;
}) {
  const descriptionId = useId();
  const liveId = useId();
  const model = useMemo(
    () => curveDisplayModel(preview.curve_metadata.definition, preview.curve_series),
    [preview.curve_metadata.definition, preview.curve_series],
  );
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [showCurve, setShowCurve] = useState(true);
  const [showBand, setShowBand] = useState(true);

  if (preview.curve_metadata.metadata_state === "absent" || !model) {
    return <article className="contract-curve absent" aria-label={`${title} curve metadata unavailable`}>
      <div className="contract-curve-heading"><div><h3>{title}</h3></div></div>
      <div className="ux-empty compact" role="status"><strong>This revision has no recorded channel or deviation metadata.</strong><p>The stored curve remains available, but axes, units, bands, and Fit eligibility are not inferred.</p></div>
      <details className="ux-disclosure curve-evidence"><summary>Curve source and technical details</summary><dl><dt>Record revision</dt><dd><code>{preview.record_revision_id}</code></dd><dt>Artifact SHA-256</dt><dd><code>{preview.curve_metadata.artifact.sha256}</code></dd></dl></details>
    </article>;
  }

  const yBounds = paddedBounds([
    ...model.yValues,
    ...(model.band?.lowerValues ?? []),
    ...(model.band?.upperValues ?? []),
  ]);
  const xBounds = paddedBounds(model.xValues);
  const bounds: Bounds = { xMin: xBounds[0], xMax: xBounds[1], yMin: yBounds[0], yMax: yBounds[1] };
  const availableIndices = model.xValues
    .map((x, index) => ({ x, y: model.yValues[index], index }))
    .filter((item): item is { x: number; y: number; index: number } => item.x !== null && item.y !== null);
  const active = activeIndex === null ? null : availableIndices.find((item) => item.index === activeIndex) ?? null;
  const activePoint = active ? point(active.x, active.y, bounds) : null;
  const sourceCount = active && model.band
    ? deviationSourceCount(model.band.lower, model.series, active.index)
    : null;
  const bandLower = active && model.band ? model.band.lowerValues[active.index] ?? null : null;
  const bandUpper = active && model.band ? model.band.upperValues[active.index] ?? null : null;
  const auxiliaryValues = active ? model.auxiliary.map((channel) => {
    const values = model.series.channels.find((item) => item.key === channel.key)?.values;
    return { channel, value: displayCurveValue(channel, values?.[active.index] ?? null) };
  }) : [];

  const activateNearest = (targetX: number) => {
    if (!availableIndices.length) return;
    const nearest = availableIndices.reduce((best, item) => (
      Math.abs(item.x - targetX) < Math.abs(best.x - targetX) ? item : best
    ));
    setActiveIndex(nearest.index);
  };

  const handlePointer = (event: PointerEvent<SVGSVGElement>) => {
    const rectangle = event.currentTarget.getBoundingClientRect();
    const viewX = ((event.clientX - rectangle.left) / rectangle.width) * VIEW_WIDTH;
    const dataX = bounds.xMin + ((viewX - MARGIN.left) / (VIEW_WIDTH - MARGIN.left - MARGIN.right)) * (bounds.xMax - bounds.xMin);
    activateNearest(dataX);
  };

  const handleKeyboard = (event: KeyboardEvent<SVGSVGElement>) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End", "Escape"].includes(event.key)) return;
    event.preventDefault();
    if (event.key === "Escape") {
      setActiveIndex(null);
      return;
    }
    if (!availableIndices.length) return;
    const position = activeIndex === null
      ? (event.key === "ArrowLeft" || event.key === "End" ? availableIndices.length - 1 : 0)
      : Math.max(0, availableIndices.findIndex((item) => item.index === activeIndex));
    const next = event.key === "Home" ? 0
      : event.key === "End" ? availableIndices.length - 1
        : event.key === "ArrowLeft" ? Math.max(0, position - 1)
          : Math.min(availableIndices.length - 1, position + 1);
    setActiveIndex(availableIndices[next].index);
  };

  const liveText = active
    ? `${model.independent.label} ${numberText(active.x)} ${model.independent.display_unit}; ${model.dependent.label} ${numberText(active.y)} ${model.dependent.display_unit}${model.band ? `; ${model.band.label}, lower ${numberText(bandLower)}, upper ${numberText(bandUpper)}${sourceCount === null ? "" : `, n ${sourceCount}`}` : ""}.`
    : "Use Left and Right Arrow keys to inspect points. Escape clears the tooltip.";

  return <article className="contract-curve">
    <div className="contract-curve-heading"><div><h3>{title}</h3></div>{preview.modeling_use === "fit_input" ? <span>Fit input</span> : null}</div>
    <div className="contract-curve-frame">
      <svg
        className="contract-curve-svg"
        viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
        role="img"
        tabIndex={0}
        aria-label={`${title}: ${model.dependent.label} by ${model.independent.label}`}
        aria-describedby={liveId}
        onKeyDown={handleKeyboard}
        onPointerMove={handlePointer}
        onPointerLeave={() => setActiveIndex(null)}
      >
        {ticks(bounds.xMin, bounds.xMax).map((tick) => {
          const plotted = point(tick, bounds.yMin, bounds);
          return <g key={`x-${tick}`}><line className="chart-grid" x1={plotted.x} x2={plotted.x} y1={MARGIN.top} y2={VIEW_HEIGHT - MARGIN.bottom}/><text className="chart-tick" x={plotted.x} y={VIEW_HEIGHT - 32} textAnchor="middle">{numberText(tick)}</text></g>;
        })}
        {ticks(bounds.yMin, bounds.yMax).map((tick) => {
          const plotted = point(bounds.xMin, tick, bounds);
          return <g key={`y-${tick}`}><line className="chart-grid" x1={MARGIN.left} x2={VIEW_WIDTH - MARGIN.right} y1={plotted.y} y2={plotted.y}/><text className="chart-tick" x={MARGIN.left - 8} y={plotted.y + 4} textAnchor="end">{numberText(tick)}</text></g>;
        })}
        <line className="chart-axis" x1={MARGIN.left} x2={VIEW_WIDTH - MARGIN.right} y1={VIEW_HEIGHT - MARGIN.bottom} y2={VIEW_HEIGHT - MARGIN.bottom}/>
        <line className="chart-axis" x1={MARGIN.left} x2={MARGIN.left} y1={MARGIN.top} y2={VIEW_HEIGHT - MARGIN.bottom}/>
        {showBand && model.band ? <path className="ensemble-confidence-band" d={bandPath(model.xValues, model.band.lowerValues, model.band.upperValues, bounds)}/> : null}
        {showCurve ? <path className="contract-curve-line" d={linePath(model.xValues, model.yValues, bounds)}/> : null}
        {activePoint ? <g className="contract-curve-active"><line x1={activePoint.x} x2={activePoint.x} y1={MARGIN.top} y2={VIEW_HEIGHT - MARGIN.bottom}/><circle cx={activePoint.x} cy={activePoint.y} r="5"/></g> : null}
        <text className="chart-axis-label" x={(MARGIN.left + VIEW_WIDTH - MARGIN.right) / 2} y={VIEW_HEIGHT - 8} textAnchor="middle">{channelAxisLabel(model.independent)}</text>
        <text className="chart-axis-label" transform={`translate(17 ${(MARGIN.top + VIEW_HEIGHT - MARGIN.bottom) / 2}) rotate(-90)`} textAnchor="middle">{channelAxisLabel(model.dependent)}</text>
      </svg>
      {active && activePoint ? <div className="contract-curve-tooltip" style={{ left: `${Math.min(68, Math.max(4, (activePoint.x / VIEW_WIDTH) * 100))}%`, top: `${Math.max(22, (activePoint.y / VIEW_HEIGHT) * 100)}%` }} role="status">
        <strong>Point {preview.curve_series!.indices[active.index] + 1}</strong>
        <span>{model.independent.label}: {numberText(active.x)} {model.independent.display_unit}</span>
        <span>{model.dependent.label}: {numberText(active.y)} {model.dependent.display_unit}</span>
        {model.band ? <span>{model.band.label}<br/>lower {numberText(bandLower)} · upper {numberText(bandUpper)} {model.dependent.display_unit}{sourceCount === null ? "" : ` · n=${sourceCount}`}</span> : null}
        {auxiliaryValues.map((item) => <span key={item.channel.key}>{item.channel.label}: {numberText(item.value)} {item.channel.display_unit}</span>)}
      </div> : null}
    </div>
    <p id={liveId} className="visually-hidden" aria-live="polite">{liveText}</p>
    <div className="curve-legend interactive" aria-label="Curve visibility">
      <button type="button" aria-pressed={showCurve} className={showCurve ? "" : "hidden"} onClick={() => setShowCurve((current) => !current)}><i className="contract-line"/>{model.dependent.label}</button>
      {model.band ? <button type="button" aria-pressed={showBand} className={showBand ? "" : "hidden"} onClick={() => setShowBand((current) => !current)}><i className="confidence"/>{model.band.label}</button> : null}
    </div>
    {model.band ? <p className="curve-band-meaning">{deviationMeaning(model.band.lower)} · explicit lower/upper bounds</p> : null}
    {preview.modeling_use === "view_only" ? null : <div className="contract-curve-actions">
      {preview.modeling_use === "fit_input" && preview.modeling_source && onOpenModeling ? <button type="button" className="ux-button secondary" onClick={() => onOpenModeling(preview.modeling_source!)}>Open in Modeling</button> : <span>{modelingUnavailableReason ?? "No exact Fit source is available."}</span>}
    </div>}
    <details className="ux-disclosure curve-evidence"><summary>Curve source and technical details</summary><dl>
      <dt>Channel units</dt><dd className="curve-channel-summary" id={descriptionId}>
        <span>{channelSummary(model.independent)}</span>
        <span>{channelSummary(model.dependent)}</span>
        {model.auxiliary.map((channel) => <span key={channel.key}>{channelSummary(channel)}</span>)}
      </dd>
      <dt>Definition SHA-256</dt><dd><code>{preview.curve_metadata.definition_sha256}</code></dd>
      <dt>Owning revision</dt><dd><code>{preview.curve_metadata.owning_revision.entity_type}:{preview.curve_metadata.owning_revision.entity_id}@{preview.curve_metadata.owning_revision.revision_id}</code></dd>
      <dt>Artifact</dt><dd><code>{preview.curve_metadata.artifact.artifact_id}</code><br/><code>{preview.curve_metadata.artifact.sha256}</code></dd>
      <dt>Schema</dt><dd><code>{preview.curve_metadata.artifact.schema_ref ?? "not recorded"}</code></dd>
      <dt>Exact sources</dt><dd>{preview.curve_metadata.sources.length ? preview.curve_metadata.sources.map((source) => <code key={`${source.entity_type}:${source.revision_id}`}>{source.entity_type}:{source.entity_id}@{source.revision_id}{source.artifact_sha256 ? ` · ${source.artifact_sha256}` : ""}<br/></code>) : "None recorded"}</dd>
      <dt>Calculation provenance</dt><dd>{preview.curve_metadata.provenance.length ? preview.curve_metadata.provenance.map((item) => <code key={`${item.kind}:${item.entity_id}`}>{item.kind}:{item.entity_id}{item.revision_id ? `@${item.revision_id}` : ""}<br/></code>) : "None recorded"}</dd>
    </dl></details>
  </article>;
}
