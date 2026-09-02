import { useId, useMemo } from "react";

import type {
  LinearViscoelasticCandidate,
  LinearViscoelasticPointPartition,
  LinearViscoelasticResponseResidualEvidence,
  LinearViscoelasticWeights,
} from "../../../model/linear-viscoelastic-calibration-contracts";
import type { PolymerSourceCurveMode } from "../../../model/linear-viscoelastic-calibration-draft";
import {
  formatPolymerAxisTick,
  formatPolymerFitNumber,
  formatPolymerRangeCoordinate,
} from "./polymer-linear-viscoelastic-format";
import {
  buildPolymerCalculatedSeries,
  buildPolymerCandidateCalculatedSeries,
  polymerResponseDomain,
  type PolymerObservedSeries,
  type PolymerObservedPoint,
} from "./polymer-linear-viscoelastic-presentation";
import { usePolymerFitChartSize } from "./use-polymer-fit-chart-size";
import "./polymer-linear-viscoelastic-plot.css";
import "./polymer-linear-viscoelastic-response-plot.css";

interface PolymerLinearViscoelasticResponsePlotProps {
  mode: PolymerSourceCurveMode;
  shifted?: boolean;
  observedSeries: PolymerObservedSeries[];
  recommendation?: LinearViscoelasticCandidate;
  selection?: LinearViscoelasticCandidate;
  weights?: Partial<LinearViscoelasticWeights>;
  responseEvidence: LinearViscoelasticResponseResidualEvidence | null;
}

function partitionClass(
  partition: LinearViscoelasticPointPartition | null,
): string {
  return partition ? partition.toLowerCase() : "unassigned";
}

function pointUseLabel(
  partition: LinearViscoelasticPointPartition | null,
): string {
  if (partition === "CALIBRATION") return "Used to calculate the model";
  if (partition === "HOLDOUT") return "Held back to check the model";
  if (partition === "EXCLUDED") return "Not used";
  return "Not assigned";
}

function seriesPath(
  points: PolymerObservedPoint[],
  x: (value: number) => number,
  y: (value: number) => number,
): string {
  return [...points]
    .sort((left, right) => left.x - right.x)
    .map(
      (point, index) =>
        `${index ? "L" : "M"} ${x(point.x).toFixed(2)} ${y(point.y).toFixed(2)}`,
    )
    .join(" ");
}

function modulusAxisDisplay(
  unit: string,
  maximumMagnitude: number,
): {
  scale: number;
  unit: string;
} {
  if (unit !== "Pa") return { scale: 1, unit };
  if (maximumMagnitude >= 1_000_000_000)
    return { scale: 1_000_000_000, unit: "GPa" };
  if (maximumMagnitude >= 1_000_000) return { scale: 1_000_000, unit: "MPa" };
  if (maximumMagnitude >= 1_000) return { scale: 1_000, unit: "kPa" };
  return { scale: 1, unit };
}

export function PolymerLinearViscoelasticResponsePlot({
  mode,
  shifted = false,
  observedSeries,
  recommendation,
  selection,
  weights,
  responseEvidence,
}: PolymerLinearViscoelasticResponsePlotProps) {
  const id = useId().replaceAll(":", "");
  const { ref: chartRef, size } = usePolymerFitChartSize({
    fallbackWidth: 1000,
    fallbackHeight: 520,
    minWidth: 560,
    minHeight: 180,
  });
  const recommendedSeries = useMemo(
    () => buildPolymerCalculatedSeries(observedSeries, responseEvidence),
    [observedSeries, responseEvidence],
  );
  const selectedSeries = useMemo(
    () =>
      selection && selection.candidate_id !== recommendation?.candidate_id
        ? buildPolymerCandidateCalculatedSeries(
            observedSeries,
            selection,
            weights,
          )
        : [],
    [observedSeries, recommendation?.candidate_id, selection, weights],
  );
  const calculatedSeries = [...recommendedSeries, ...selectedSeries];
  const selectionMatchesRecommendation = Boolean(
    selection && selection.candidate_id === recommendation?.candidate_id,
  );
  const showRecommendedValues = Boolean(
    recommendedSeries.length && !selectionMatchesRecommendation,
  );
  const domain = polymerResponseDomain(observedSeries, calculatedSeries);
  const observedPoints = observedSeries.flatMap((item) => item.points);
  const calculatedPoints = calculatedSeries.flatMap((item) => item.points);
  const partitionsByOrdinal = new Map<
    number,
    LinearViscoelasticPointPartition | null
  >();
  for (const point of observedPoints)
    partitionsByOrdinal.set(point.ordinal, point.partition);
  const exactPartitions = [...partitionsByOrdinal.values()];
  const holdoutCount = exactPartitions.filter(
    (partition) => partition === "HOLDOUT",
  ).length;
  const excludedCount = exactPartitions.filter(
    (partition) => partition === "EXCLUDED",
  ).length;
  const evidenceMismatch = Boolean(
    responseEvidence &&
    !recommendedSeries.flatMap((item) => item.points).length,
  );
  const selectionMismatch = Boolean(
    selection &&
    selection.candidate_id !== recommendation?.candidate_id &&
    !selectedSeries.flatMap((item) => item.points).length,
  );
  const positiveX =
    observedPoints.length > 0 && observedPoints.every((point) => point.x > 0);
  const useLogX = Boolean(
    domain && positiveX && domain.xMax / domain.xMin >= 100,
  );
  const transformedX = (value: number) => (useLogX ? Math.log10(value) : value);
  const xMin = domain ? transformedX(domain.xMin) : 0;
  const xMax = domain ? transformedX(domain.xMax) : 1;
  const rawYSpan = domain ? domain.yMax - domain.yMin : 1;
  const yPadding =
    rawYSpan > 0
      ? rawYSpan * 0.08
      : Math.max(Math.abs(domain?.yMax ?? 1) * 0.08, 1);
  const yMin = (domain?.yMin ?? 0) - yPadding;
  const yMax = (domain?.yMax ?? 1) + yPadding;
  const primarySeries = observedSeries[0];
  const yAxis = modulusAxisDisplay(
    primarySeries?.yUnit ?? "",
    Math.max(Math.abs(yMin), Math.abs(yMax)),
  );
  const plot = {
    left: size.width >= 900 ? 82 : 70,
    right: size.width - 28,
    top: 26,
    bottom: size.height - 52,
  };
  const x = (value: number) =>
    plot.left +
    ((transformedX(value) - xMin) / Math.max(xMax - xMin, Number.EPSILON)) *
      (plot.right - plot.left);
  const y = (value: number) =>
    plot.bottom -
    ((value - yMin) / Math.max(yMax - yMin, Number.EPSILON)) *
      (plot.bottom - plot.top);

  return (
    <article
      className="polymer-response-workspace"
      id="modeling-fit"
      aria-label="Measured polymer response and calculated model response"
    >
      <header className="polymer-response-heading">
        <h2>{mode === "dma" ? (shifted ? "Shifted DMA response" : "DMA response") : "Relaxation response"}</h2>
      </header>
      {domain && primarySeries ? (
        <>
          <div className="polymer-response-chart" ref={chartRef}>
            <svg
              viewBox={`0 0 ${size.width} ${size.height}`}
              role="img"
              aria-labelledby={`${id}-title ${id}-description`}
            >
              <title id={`${id}-title`}>
                {mode === "dma"
                  ? `${shifted ? "Shifted" : "Measured"} DMA data with recommended and selected model responses`
                  : "Measured relaxation data with recommended and selected model responses"}
              </title>
              <desc id={`${id}-description`}>
                {observedPoints.length} measured response values
                {calculatedPoints.length
                  ? ` with calculated recommendation${selection ? " and engineer selection" : ""}`
                  : " before calculation"}
                . Marker appearance distinguishes values used to calculate the
                model, values held back to check it, and values not used.
              </desc>
              {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                const lineY = plot.top + ratio * (plot.bottom - plot.top);
                const value = yMax - ratio * (yMax - yMin);
                return (
                  <g key={`y:${ratio}`}>
                    <line
                      className="polymer-response-grid"
                      x1={plot.left}
                      x2={plot.right}
                      y1={lineY}
                      y2={lineY}
                    />
                    <text
                      className="polymer-response-tick"
                      x={plot.left - 10}
                      y={lineY + 4}
                      textAnchor="end"
                    >
                      {formatPolymerAxisTick(value / yAxis.scale)}
                    </text>
                  </g>
                );
              })}
              {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                const lineX = plot.left + ratio * (plot.right - plot.left);
                const transformedValue = xMin + ratio * (xMax - xMin);
                const value = useLogX
                  ? 10 ** transformedValue
                  : transformedValue;
                return (
                  <g key={`x:${ratio}`}>
                    <line
                      className="polymer-response-grid vertical"
                      x1={lineX}
                      x2={lineX}
                      y1={plot.top}
                      y2={plot.bottom}
                    />
                    <text
                      className="polymer-response-tick"
                      x={lineX}
                      y={plot.bottom + 20}
                      textAnchor={
                        ratio === 0 ? "start" : ratio === 1 ? "end" : "middle"
                      }
                    >
                      {useLogX ? formatPolymerRangeCoordinate(value) : formatPolymerAxisTick(value)}
                    </text>
                  </g>
                );
              })}
              <line
                className="polymer-response-axis"
                x1={plot.left}
                x2={plot.left}
                y1={plot.top}
                y2={plot.bottom}
              />
              <line
                className="polymer-response-axis"
                x1={plot.left}
                x2={plot.right}
                y1={plot.bottom}
                y2={plot.bottom}
              />
              <text
                className="polymer-response-axis-label"
                x={(plot.left + plot.right) / 2}
                y={size.height - 8}
                textAnchor="middle"
              >
                {primarySeries.xLabel} [{primarySeries.xUnit}]
                {useLogX ? " · log scale" : ""}
              </text>
              <text
                className="polymer-response-axis-label"
                x="15"
                y={(plot.top + plot.bottom) / 2}
                textAnchor="middle"
                transform={`rotate(-90 15 ${(plot.top + plot.bottom) / 2})`}
              >
                {primarySeries.yLabel} [{yAxis.unit}]
              </text>
              {calculatedSeries.map((item) => (
                <path
                  className={`polymer-response-fit ${item.role === "recommendation" && selectionMatchesRecommendation ? "selection" : item.role} ${item.key}`}
                  d={seriesPath(item.points, x, y)}
                  key={`fit:${item.role}:${item.key}`}
                />
              ))}
              {observedSeries.map((item) => (
                <g
                  className={`polymer-response-series ${item.key}`}
                  key={item.key}
                >
                  {item.points.map((point) => (
                    <circle
                      className={`partition-${partitionClass(point.partition)}`}
                      key={`${item.key}:${point.ordinal}`}
                      cx={x(point.x)}
                      cy={y(point.y)}
                      r="4"
                    >
                      <title>
                        {item.label}, measured value {point.ordinal + 1}:{" "}
                        {formatPolymerFitNumber(point.y)} {item.yUnit} at{" "}
                        {formatPolymerFitNumber(point.x)} {item.xUnit};{" "}
                        {pointUseLabel(point.partition)}
                      </title>
                    </circle>
                  ))}
                </g>
              ))}
            </svg>
            <div
              className="polymer-response-legend"
              aria-label="Response graph legend"
            >
              {mode === "dma" ? observedSeries.map((item) => (
                <span className={`observed ${item.key}`} key={`response:${item.key}`}><i />{item.key === "dma-loss" ? "Loss modulus" : "Storage modulus"}</span>
              )) : null}
              <span className="observed calibration"><i />Used to calculate model</span>
              {holdoutCount ? (
                <span>
                  <i className="holdout" />
                  Held back for check
                </span>
              ) : null}
              {excludedCount ? (
                <span>
                  <i className="excluded" />
                  Excluded
                </span>
              ) : null}
              {recommendedSeries.length ? (
                <span className={`calculated ${selectionMatchesRecommendation ? "selection" : "recommendation"}`}><i />{selectionMatchesRecommendation ? "Selected model" : "Recommended model"}</span>
              ) : null}
              {selectedSeries.length ? <span className="calculated selection"><i />Selected model</span> : null}
            </div>
          </div>
          {evidenceMismatch ? (
            <p className="polymer-response-evidence-mismatch" role="status">
              The recommended curve is hidden because its values do not match
              this input.
            </p>
          ) : null}
          {selectionMismatch ? (
            <p className="polymer-response-evidence-mismatch" role="status">
              The selected curve is hidden because its result does not match
              this input.
            </p>
          ) : null}
          <details className="polymer-response-table">
            <summary>
              {calculatedPoints.length
                ? "Measured and model values"
                : "Measured values"}
            </summary>
            <div>
              <table>
                <caption>
                  Exact measured and model values shown in the graph
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Response</th>
                    <th scope="col">Value</th>
                    <th scope="col">Coordinate</th>
                    <th scope="col">Measured</th>
                    {showRecommendedValues ? (
                      <th scope="col">Recommended model</th>
                    ) : null}
                    {selection ? <th scope="col">Selected model</th> : null}
                    <th scope="col">Role</th>
                  </tr>
                </thead>
                <tbody>
                  {observedSeries.flatMap((item) =>
                    item.points.map((point) => {
                      const recommended = recommendedSeries
                        .find((series) => series.key === item.key)
                        ?.points.find(
                          (value) => value.ordinal === point.ordinal,
                        );
                      const selected =
                        selection?.candidate_id === recommendation?.candidate_id
                          ? recommended
                          : selectedSeries
                              .find((series) => series.key === item.key)
                              ?.points.find(
                                (value) => value.ordinal === point.ordinal,
                              );
                      return (
                        <tr key={`${item.key}:${point.ordinal}`}>
                          <td>{item.label}</td>
                          <th scope="row">{point.ordinal + 1}</th>
                          <td>
                            {formatPolymerFitNumber(point.x)} {item.xUnit}
                          </td>
                          <td>
                            {formatPolymerFitNumber(point.y)} {item.yUnit}
                          </td>
                          {showRecommendedValues ? (
                            <td>
                              {recommended
                                ? `${formatPolymerFitNumber(recommended.predicted)} ${item.yUnit}`
                                : "—"}
                            </td>
                          ) : null}
                          {selection ? (
                            <td>
                              {selected
                                ? `${formatPolymerFitNumber(selected.predicted)} ${item.yUnit}`
                                : "—"}
                            </td>
                          ) : null}
                          <td>
                            {pointUseLabel(
                              recommended?.partition ??
                                selected?.partition ??
                                point.partition,
                            )}
                          </td>
                        </tr>
                      );
                    }),
                  )}
                </tbody>
              </table>
            </div>
          </details>
        </>
      ) : (
        <div className="polymer-response-empty">
          <strong>No Test Data selected</strong>
        </div>
      )}
    </article>
  );
}
