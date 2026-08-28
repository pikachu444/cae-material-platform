import { useEffect, useId, useMemo, useState } from "react";

import {
  type ApiConfig,
} from "../../../shared/api";
import {
  loadExactTestData,
  type ExactTestData,
  type ExactTestDataPoint,
} from "../api/load-exact-test-data";

interface Props {
  config: ApiConfig;
  documentId: string;
  revisionId: string;
}

interface PlotPoint {
  x: number;
  y: number;
}

function messageFor(cause: unknown): string {
  return cause instanceof Error
    ? cause.message
    : "Exact Test Data measurements could not be loaded.";
}

function downloadArtifact(data: ExactTestData): void {
  const url = URL.createObjectURL(data.artifact);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = data.filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function numericPoints(points: ExactTestDataPoint[]): PlotPoint[] {
  return points.flatMap((point) => {
    if (point.independent === null || point.dependent === null) return [];
    const x = Number(point.independent);
    const y = Number(point.dependent);
    return Number.isFinite(x) && Number.isFinite(y) ? [{ x, y }] : [];
  });
}

function paddedRange(values: number[]): { minimum: number; maximum: number } {
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum;
  const padding = span > 0 ? span * 0.05 : Math.max(Math.abs(maximum) * 0.05, 1);
  return { minimum: minimum - padding, maximum: maximum + padding };
}

function tickValues(minimum: number, maximum: number): number[] {
  return Array.from(
    { length: 6 },
    (_, index) => minimum + ((maximum - minimum) * index) / 5,
  );
}

function compactNumber(value: number): string {
  const magnitude = Math.abs(value);
  if (magnitude >= 1_000_000_000) return `${(value / 1_000_000_000).toPrecision(3)}G`;
  if (magnitude >= 1_000_000) return `${(value / 1_000_000).toPrecision(3)}M`;
  if (magnitude >= 1_000) return `${(value / 1_000).toPrecision(3)}k`;
  if (magnitude !== 0 && magnitude < 0.001) return value.toExponential(2);
  return Number(value.toPrecision(4)).toString();
}

function pointValue(value: string | null): string {
  if (value === null) return "—";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return value;
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 12 }).format(numeric);
}

function ExactTestDataPlot({ data }: { data: ExactTestData }) {
  const titleId = useId();
  const points = useMemo(() => numericPoints(data.points), [data.points]);
  const width = 760;
  const height = 326;
  const margin = { left: 76, right: 24, top: 22, bottom: 56 };
  const xRange = paddedRange(points.map((point) => point.x));
  const yRange = paddedRange(points.map((point) => point.y));
  const x = (value: number) =>
    margin.left +
    ((value - xRange.minimum) / (xRange.maximum - xRange.minimum || 1)) *
      (width - margin.left - margin.right);
  const y = (value: number) =>
    height -
    margin.bottom -
    ((value - yRange.minimum) / (yRange.maximum - yRange.minimum || 1)) *
      (height - margin.top - margin.bottom);
  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"}${x(point.x)} ${y(point.y)}`)
    .join(" ");
  return (
    <figure className="exact-test-data-plot">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-labelledby={titleId}
      >
        <title id={titleId}>
          {data.dependent.name} by {data.independent.name} exact Test Data curve
        </title>
        {tickValues(yRange.minimum, yRange.maximum).map((tick) => (
          <g key={`y-${tick}`}>
            <line
              className="exact-test-data-grid-line"
              x1={margin.left}
              x2={width - margin.right}
              y1={y(tick)}
              y2={y(tick)}
            />
            <text className="exact-test-data-tick" x={margin.left - 10} y={y(tick) + 4} textAnchor="end">
              {compactNumber(tick)}
            </text>
          </g>
        ))}
        {tickValues(xRange.minimum, xRange.maximum).map((tick) => (
          <g key={`x-${tick}`}>
            <line
              className="exact-test-data-grid-line"
              x1={x(tick)}
              x2={x(tick)}
              y1={margin.top}
              y2={height - margin.bottom}
            />
            <text className="exact-test-data-tick" x={x(tick)} y={height - margin.bottom + 22} textAnchor="middle">
              {compactNumber(tick)}
            </text>
          </g>
        ))}
        <path className="exact-test-data-curve" d={path} />
        {points.map((point, index) => (
          <circle
            className="exact-test-data-point"
            key={`${point.x}-${point.y}-${index}`}
            cx={x(point.x)}
            cy={y(point.y)}
            r="3.5"
          />
        ))}
        <text className="exact-test-data-axis-label" x={(margin.left + width - margin.right) / 2} y={height - 12} textAnchor="middle">
          {data.independent.name} ({data.independent.originalUnit})
        </text>
        <text
          className="exact-test-data-axis-label"
          x="18"
          y={(margin.top + height - margin.bottom) / 2}
          textAnchor="middle"
          transform={`rotate(-90 18 ${(margin.top + height - margin.bottom) / 2})`}
        >
          {data.dependent.name} ({data.dependent.originalUnit})
        </text>
      </svg>
    </figure>
  );
}

function ExactTestDataContent({ data }: { data: ExactTestData }) {
  return (
    <section className="exact-test-data-detail" aria-labelledby="exact-test-data-title">
      <div className="detail-section-heading">
        <h2 id="exact-test-data-title">Exact measurements</h2>
        <button
          className="ux-button tertiary"
          type="button"
          onClick={() => downloadArtifact(data)}
        >
          Download exact Test Data JSON
        </button>
      </div>
      <div className="exact-test-data-composition">
        <ExactTestDataPlot data={data} />
        <div className="exact-test-data-points-shell">
          <table className="ux-table exact-test-data-points" aria-label="Exact Test Data points">
            <thead>
              <tr>
                <th>Point</th>
                <th>
                  {data.independent.name} ({data.independent.originalUnit})
                </th>
                <th>
                  {data.dependent.name} ({data.dependent.originalUnit})
                </th>
              </tr>
            </thead>
            <tbody>
              {data.points.map((point) => (
                <tr key={point.ordinal}>
                  <td>{point.ordinal}</td>
                  <td>{pointValue(point.independent)}</td>
                  <td>{pointValue(point.dependent)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export function ExactTestDataDetail({ config, documentId, revisionId }: Props) {
  const [data, setData] = useState<ExactTestData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void loadExactTestData(config, documentId, revisionId)
      .then((value) => {
        if (!active) return;
        setData(value);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setData(null);
        setError(messageFor(cause));
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [attempt, config, documentId, revisionId]);

  if (loading) {
    return <p className="loading-state" role="status">Loading exact Test Data measurements…</p>;
  }
  if (error) {
    return (
      <div className="ux-notice error exact-test-data-error" role="alert">
        <span>{error}</span>
        <button
          className="ux-button tertiary"
          type="button"
          onClick={() => setAttempt((current) => current + 1)}
        >
          Retry exact Test Data
        </button>
      </div>
    );
  }
  return data ? <ExactTestDataContent data={data} /> : null;
}
