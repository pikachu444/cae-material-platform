import { useId, useMemo } from "react";

import type { LinearViscoelasticCandidate, LinearViscoelasticWeights } from "../../../model/linear-viscoelastic-calibration-contracts";
import {
  formatPolymerAxisTick,
  formatPolymerDeviation,
  formatPolymerFitNumber,
  formatPolymerSignedDeviation,
  meanAbsoluteResidual,
} from "./polymer-linear-viscoelastic-format";
import { buildPolymerResidualSeries, type PolymerObservedSeries, type PolymerResidualSeries } from "./polymer-linear-viscoelastic-presentation";
import { usePolymerFitChartSize } from "./use-polymer-fit-chart-size";
import "./polymer-linear-viscoelastic-plot.css";
import "./polymer-linear-viscoelastic-residual-plot.css";

interface PolymerLinearViscoelasticResidualPlotProps {
  candidate?: LinearViscoelasticCandidate;
  observedSeries: PolymerObservedSeries[];
  weights?: Partial<LinearViscoelasticWeights>;
  isBestEvaluated: boolean;
  isSelected: boolean;
}

interface ResidualPanelProps {
  errorLabel: "Average difference";
  id: string;
  series: PolymerResidualSeries;
}

function ResidualPanel({ errorLabel, id, series }: ResidualPanelProps) {
  const { ref: chartRef, size } = usePolymerFitChartSize({
    fallbackWidth: 1000,
    fallbackHeight: 280,
    minWidth: 380,
    minHeight: 140,
  });
  const finite = series.points.filter((point) => Number.isFinite(point.x) && Number.isFinite(point.residual));
  if (!finite.length) {
    return (
      <section className="polymer-residual-panel polymer-residual-panel-empty" aria-labelledby={`${id}-heading`}>
        <div className="polymer-residual-panel-heading">
          <h3 id={`${id}-heading`}>{series.title}</h3>
        </div>
        <p>No points in this partition.</p>
      </section>
    );
  }

  const plot = { left: 72, right: size.width - 24, top: 24, bottom: size.height - 42 };
  const maxAbs = Math.max(...finite.map((point) => Math.abs(point.residual)), Number.EPSILON);
  const positiveX = finite.every((point) => point.x > 0);
  const rawXMin = Math.min(...finite.map((point) => point.x));
  const rawXMax = Math.max(...finite.map((point) => point.x));
  const useLogX = positiveX && rawXMax / rawXMin >= 100;
  const transformX = (value: number) => useLogX ? Math.log10(value) : value;
  const xMin = transformX(rawXMin);
  const xMax = transformX(rawXMax);
  const x = (value: number) => finite.length === 1 || xMin === xMax
    ? (plot.left + plot.right) / 2
    : plot.left + ((transformX(value) - xMin) / (xMax - xMin)) * (plot.right - plot.left);
  const y = (value: number) => (plot.top + plot.bottom) / 2
    - (value / maxAbs) * ((plot.bottom - plot.top) / 2);
  const ordered = [...finite].sort((left, right) => left.x - right.x);
  const path = ordered.map((point, index) => `${index ? "L" : "M"} ${x(point.x).toFixed(2)} ${y(point.residual).toFixed(2)}`).join(" ");
  const zeroY = y(0);

  return (
    <section className="polymer-residual-panel" aria-labelledby={`${id}-heading`}>
      <div className="polymer-residual-panel-heading">
        <h3 id={`${id}-heading`}>{series.title}</h3>
        <span>{errorLabel} {formatPolymerDeviation(meanAbsoluteResidual(finite.map((point) => point.residual)))}</span>
      </div>
      <div className="polymer-residual-chart" ref={chartRef}>
        <svg viewBox={`0 0 ${size.width} ${size.height}`} role="img" aria-labelledby={`${id}-svg-title ${id}-svg-description`}>
          <title id={`${id}-svg-title`}>{series.title}</title>
          <desc id={`${id}-svg-description`}>{finite.length} relative error values shown against {series.xLabel.toLowerCase()}.</desc>
          <line className="polymer-residual-grid" x1={plot.left} x2={plot.right} y1={plot.top} y2={plot.top} />
          <line className="polymer-residual-zero" x1={plot.left} x2={plot.right} y1={zeroY} y2={zeroY} />
          <line className="polymer-residual-grid" x1={plot.left} x2={plot.right} y1={plot.bottom} y2={plot.bottom} />
          <line className="polymer-residual-axis" x1={plot.left} x2={plot.left} y1={plot.top} y2={plot.bottom} />
          <line className="polymer-residual-axis" x1={plot.left} x2={plot.right} y1={plot.bottom} y2={plot.bottom} />
          <text className="polymer-residual-tick" x={plot.left - 10} y={plot.top + 4} textAnchor="end">{formatPolymerDeviation(maxAbs)}</text>
          <text className="polymer-residual-tick" x={plot.left - 10} y={zeroY + 4} textAnchor="end">0</text>
          <text className="polymer-residual-tick" x={plot.left - 10} y={plot.bottom + 4} textAnchor="end">−{formatPolymerDeviation(maxAbs)}</text>
          <text className="polymer-residual-tick" x={plot.left} y={plot.bottom + 18}>{formatPolymerAxisTick(rawXMin)}</text>
          <text className="polymer-residual-tick" x={plot.right} y={plot.bottom + 18} textAnchor="end">{formatPolymerAxisTick(rawXMax)}</text>
          <text className="polymer-residual-axis-label" x={(plot.left + plot.right) / 2} y={size.height - 6} textAnchor="middle">{series.xLabel} [{series.xUnit}]{useLogX ? " · log scale" : ""}</text>
          <text className="polymer-residual-axis-label" x="14" y={(plot.top + plot.bottom) / 2} textAnchor="middle" transform={`rotate(-90 14 ${(plot.top + plot.bottom) / 2})`}>Relative deviation</text>
          <path className="polymer-residual-line" d={path} />
          {finite.map((point) => (
            <circle className="polymer-residual-point" key={`${point.ordinal}:${point.x}`} cx={x(point.x)} cy={y(point.residual)} r="4"><title>Measured value {point.ordinal + 1}: relative deviation {formatPolymerSignedDeviation(point.residual)} at {formatPolymerFitNumber(point.x)} {series.xUnit}</title></circle>
          ))}
        </svg>
      </div>
    </section>
  );
}

export function PolymerLinearViscoelasticResidualPlot({
  candidate,
  observedSeries,
  weights,
  isBestEvaluated,
  isSelected,
}: PolymerLinearViscoelasticResidualPlotProps) {
  const id = useId().replaceAll(":", "");
  const residualSeries = useMemo(
    () => candidate ? buildPolymerResidualSeries(observedSeries, candidate, weights) : [],
    [candidate, observedSeries, weights],
  );
  return (
    <article className="polymer-residual-workspace" id="modeling-fit" aria-label="Polymer model calculation errors">
      <header className="polymer-residual-workspace-heading">
        <h2>Point differences</h2>
        {candidate ? (
          <dl className="polymer-residual-metrics">
            <div><dt>Model</dt><dd>{candidate.term_count}-term Prony{isSelected ? " · Selected" : isBestEvaluated ? " · Recommended" : ""}</dd></div>
          </dl>
        ) : null}
      </header>
      {candidate && residualSeries.length ? (
        <div className="polymer-residual-grid-layout">
          {residualSeries.map((series) => <ResidualPanel
            errorLabel="Average difference"
            id={`${id}-${series.key.replaceAll(":", "-")}`}
            key={series.key}
            series={series}
          />)}
        </div>
      ) : (
        <div className="polymer-residual-empty">
          <strong>{candidate ? "Error coordinates unavailable" : "No calculation result"}</strong>
          <span>{candidate ? "The returned error values do not match this input." : "Calculate Prony models to compare their errors."}</span>
        </div>
      )}
    </article>
  );
}
