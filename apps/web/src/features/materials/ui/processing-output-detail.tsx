import type {
  CommonCurveStage,
  CommonHardeningCandidate,
  CommonProcessingFitDecision,
} from "../../modeling";
import type { ExactProcessingOutput } from "../api/load-exact-processing-output";

interface NumericSeries {
  quantity: string;
  unit: string;
  values: number[];
}

interface CurveSelection {
  x: NumericSeries;
  y: NumericSeries;
  observedX: NumericSeries | null;
  observedY: NumericSeries | null;
}

const STAGE_LABELS: Record<string, string> = {
  mapping: "Mapped test data",
  "rows.sort_unique": "Ordered unique points",
  "metal.engineering_to_true_plastic": "True-plastic workup",
  "metal.hardening_fit_extrapolate": "Hardening fit and bounded extension",
};

const QUANTITY_LABELS: Record<string, string> = {
  "strain.engineering": "Engineering strain",
  "stress.engineering": "Engineering stress",
  "strain.true": "True strain",
  "strain.true_plastic": "True plastic strain",
  "stress.true": "True stress",
  "stress.hardening.selected": "Selected true stress",
};

const PARAMETER_LABELS: Record<string, string> = {
  k_pa: "K",
  epsilon_0: "ε₀",
  n: "n",
  sigma_0_pa: "σ₀",
  q_pa: "Q",
  b: "b",
  delta_p_minus_n: "p − n",
};

function words(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function sentence(value: string): string {
  const normalized = value.replaceAll("_", " ").replaceAll("-", " ");
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function familyLabel(value: string): string {
  if (value === "hockett_sherby") return "Hockett–Sherby";
  return words(value);
}

function decisionLabel(decision: CommonProcessingFitDecision): string {
  if (decision.actual_term_count !== null) {
    return `${decision.actual_term_count}-term Generalized Maxwell`;
  }
  if (decision.mode === "blend") {
    const primaryPercent = Math.round((decision.primary_weight ?? 0) * 100);
    return `${familyLabel(decision.primary_law)} + ${familyLabel(decision.secondary_law ?? "")} ${primaryPercent}/${100 - primaryPercent}`;
  }
  return familyLabel(decision.primary_law);
}

function formatNumber(value: number, significantDigits = 4): string {
  return value.toLocaleString("en-US", {
    maximumSignificantDigits: significantDigits,
  });
}

function engineeringValue(value: number, unit: string): { value: string; unit: string } {
  if (unit === "Pa") {
    return { value: formatNumber(value / 1_000_000), unit: "MPa" };
  }
  return { value: formatNumber(value), unit };
}

function engineeringNumber(value: number, unit: string): number {
  return unit === "Pa" ? value / 1_000_000 : value;
}

function quantityLabel(value: string): string {
  if (QUANTITY_LABELS[value]) return QUANTITY_LABELS[value];
  return words(value.split(".").at(-1) ?? value);
}

function finalStage(data: ExactProcessingOutput): CommonCurveStage {
  return data.document.result.stages[data.document.result.stages.length - 1];
}

function findSeries(stage: CommonCurveStage, quantity: string): NumericSeries | null {
  return stage.series.find((item) => item.quantity === quantity) ?? null;
}

function selectCurve(data: ExactProcessingOutput): CurveSelection | null {
  const resultStage = finalStage(data);
  const selected = findSeries(resultStage, "stress.hardening.selected");
  const truePlastic = findSeries(resultStage, "strain.true_plastic");
  const x = truePlastic ?? resultStage.series[0] ?? null;
  const y = selected ?? resultStage.series.find(
    (item) => item !== x && item.values.length === x?.values.length,
  ) ?? null;
  if (!x || !y || x.values.length !== y.values.length) return null;

  const observedStage = [...data.document.result.stages].reverse().find(
    (stage) => findSeries(stage, x.quantity) && findSeries(stage, "stress.true"),
  );
  const observedX = observedStage ? findSeries(observedStage, x.quantity) : null;
  const observedY = observedStage ? findSeries(observedStage, "stress.true") : null;
  return {
    x,
    y,
    observedX: observedX?.values.length === observedY?.values.length ? observedX : null,
    observedY: observedX?.values.length === observedY?.values.length ? observedY : null,
  };
}

function selectedCandidate(data: ExactProcessingOutput): CommonHardeningCandidate | null {
  const decision = data.document.fit_decision;
  if (!decision) return null;
  return finalStage(data).fit_candidates?.find(
    (candidate) => candidate.family === decision.candidate_key,
  ) ?? null;
}

function curveTitle(curve: CurveSelection): string {
  if (
    curve.x.quantity === "strain.true_plastic"
    && curve.y.quantity === "stress.hardening.selected"
  ) return "True stress–plastic strain result";
  return `${quantityLabel(curve.y.quantity)} by ${quantityLabel(curve.x.quantity)}`;
}

function CurvePlot({ curve }: { curve: CurveSelection }) {
  const width = 980;
  const height = 430;
  const bounds = { left: 82, right: 28, top: 24, bottom: 62 };
  const plotWidth = width - bounds.left - bounds.right;
  const plotHeight = height - bounds.top - bounds.bottom;
  const allX = [
    ...curve.x.values,
    ...(curve.observedX?.values ?? []),
  ];
  const yDisplay = curve.y.values.map((value) => engineeringNumber(value, curve.y.unit));
  const observedYDisplay = (curve.observedY?.values ?? []).map(
    (value) => engineeringNumber(value, curve.observedY?.unit ?? curve.y.unit),
  );
  const xMinimum = Math.min(...allX);
  const xMaximum = Math.max(...allX);
  const yMinimum = 0;
  const yMaximum = Math.max(...yDisplay, ...observedYDisplay) * 1.08;
  const xScale = (value: number) => bounds.left
    + ((value - xMinimum) / Math.max(xMaximum - xMinimum, Number.EPSILON)) * plotWidth;
  const yScale = (value: number) => bounds.top
    + plotHeight
    - ((value - yMinimum) / Math.max(yMaximum - yMinimum, Number.EPSILON)) * plotHeight;
  const line = curve.x.values.map(
    (value, index) => `${index === 0 ? "M" : "L"} ${xScale(value)} ${yScale(yDisplay[index])}`,
  ).join(" ");
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const displayYUnit = engineeringValue(1, curve.y.unit).unit;

  return (
    <svg
      className="processing-output-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`${quantityLabel(curve.y.quantity)} in ${displayYUnit} by ${quantityLabel(curve.x.quantity)} in ${curve.x.unit}`}
    >
      {ticks.map((tick) => {
        const x = bounds.left + tick * plotWidth;
        const y = bounds.top + (1 - tick) * plotHeight;
        return (
          <g key={tick}>
            <line className="processing-output-gridline" x1={bounds.left} x2={width - bounds.right} y1={y} y2={y} />
            <line className="processing-output-gridline" x1={x} x2={x} y1={bounds.top} y2={height - bounds.bottom} />
            <text className="processing-output-tick" x={bounds.left - 12} y={y + 5} textAnchor="end">
              {formatNumber(yMinimum + tick * (yMaximum - yMinimum), 3)}
            </text>
            <text className="processing-output-tick" x={x} y={height - bounds.bottom + 24} textAnchor="middle">
              {formatNumber(xMinimum + tick * (xMaximum - xMinimum), 3)}
            </text>
          </g>
        );
      })}
      <line className="processing-output-axis" x1={bounds.left} x2={width - bounds.right} y1={height - bounds.bottom} y2={height - bounds.bottom} />
      <line className="processing-output-axis" x1={bounds.left} x2={bounds.left} y1={bounds.top} y2={height - bounds.bottom} />
      <path className="processing-output-fit-line" d={line} />
      {curve.observedX && curve.observedY
        ? curve.observedX.values.map((xValue, index) => (
            <circle
              className="processing-output-observed-point"
              key={`${xValue}:${index}`}
              cx={xScale(xValue)}
              cy={yScale(observedYDisplay[index])}
              r="4.5"
            />
          ))
        : null}
      <text className="processing-output-axis-title" x={bounds.left + plotWidth / 2} y={height - 12} textAnchor="middle">
        {quantityLabel(curve.x.quantity)} [{curve.x.unit}]
      </text>
      <text className="processing-output-axis-title" transform={`translate(20 ${bounds.top + plotHeight / 2}) rotate(-90)`} textAnchor="middle">
        {quantityLabel(curve.y.quantity)} [{displayYUnit}]
      </text>
    </svg>
  );
}

function FitSummary({ data }: { data: ExactProcessingOutput }) {
  const decision = data.document.fit_decision;
  const candidate = selectedCandidate(data);
  if (!decision) {
    return (
      <section className="processing-output-summary" aria-labelledby="processing-result-summary-title">
        <h2 id="processing-result-summary-title">Key results</h2>
        <dl className="processing-output-key-values">
          <div><dt>Stages</dt><dd>{data.summary.stage_count}</dd></div>
          <div><dt>Result points</dt><dd>{data.summary.final_point_count}</dd></div>
        </dl>
      </section>
    );
  }
  return (
    <section className="processing-output-summary" aria-labelledby="selected-model-title">
      <h2 id="selected-model-title">Selected model</h2>
      <dl className="processing-output-key-values">
        <div><dt>Decision</dt><dd>{decisionLabel(decision)}</dd></div>
        <div><dt>Fit range</dt><dd>{formatNumber(decision.fit_minimum)}–{formatNumber(decision.fit_maximum)} strain</dd></div>
        <div><dt>Extension</dt><dd>{decision.extrapolation_policy === "bounded" ? "Bounded" : words(decision.extrapolation_policy)}{decision.extrapolation_maximum === null ? "" : ` to ${formatNumber(decision.extrapolation_maximum)} strain`}</dd></div>
        <div><dt>Fit metric</dt><dd>{sentence(decision.metric_definition)} {formatNumber(decision.metric_value * 100)} %</dd></div>
        <div><dt>Convergence</dt><dd>{candidate ? (candidate.convergence ? "Converged" : "Not converged") : "Not recorded"}</dd></div>
        <div><dt>Identifiability</dt><dd>{candidate ? sentence(candidate.identifiability) : "Not recorded"}</dd></div>
      </dl>
      <h3>Fitted parameters</h3>
      <table className="ux-table processing-output-parameters">
        <thead><tr><th>Model</th><th>Parameter</th><th>Fit</th><th>Bounds</th></tr></thead>
        <tbody>
          {decision.parameter_sets.flatMap((set) => set.parameters.map((parameter) => {
            const fitted = engineeringValue(parameter.value, parameter.unit);
            const lower = parameter.lower === null ? null : engineeringValue(parameter.lower, parameter.unit);
            const upper = parameter.upper === null ? null : engineeringValue(parameter.upper, parameter.unit);
            return (
              <tr key={`${set.law}:${parameter.name}`}>
                <td>{familyLabel(set.law)}</td>
                <td>{PARAMETER_LABELS[parameter.name] ?? parameter.name}</td>
                <td>{fitted.value} {fitted.unit === "1" ? "" : fitted.unit}</td>
                <td>{lower && upper ? `${lower.value}–${upper.value} ${lower.unit === "1" ? "" : lower.unit}` : "—"}</td>
              </tr>
            );
          }))}
        </tbody>
      </table>
    </section>
  );
}

function KeyResults({ data }: { data: ExactProcessingOutput }) {
  const scalars = data.document.result.stages.flatMap((stage) => stage.scalar_results);
  const scalar = (key: string) => scalars.find((item) => item.key === key);
  const neckingStrain = scalar("necking_engineering_strain");
  const neckingStress = scalar("necking_engineering_stress");
  const observedMaximum = scalar("fit.observed_maximum_strain");
  const workup = data.document.workup_overrides[0];
  const values = [
    { label: "Result points", value: String(data.summary.final_point_count) },
    observedMaximum ? { label: "Observed fit limit", value: `${formatNumber(observedMaximum.value)} strain` } : null,
    neckingStrain ? { label: "Necking strain", value: `${formatNumber(neckingStrain.value)} ${neckingStrain.unit}` } : null,
    neckingStress ? (() => {
      const display = engineeringValue(neckingStress.value, neckingStress.unit);
      return { label: "Necking stress", value: `${display.value} ${display.unit}` };
    })() : null,
    workup ? {
      label: "Workup decision",
      value: workup.kind === "necking_boundary"
        ? `Manual necking boundary · point ${formatNumber(workup.original_value)}`
        : `Manual Young’s modulus · ${engineeringValue(workup.original_value, workup.original_unit).value} ${engineeringValue(workup.original_value, workup.original_unit).unit}`,
    } : null,
  ].filter((item): item is { label: string; value: string } => Boolean(item));
  return (
    <section className="processing-output-key-results" aria-labelledby="processing-key-results-title">
      <h2 id="processing-key-results-title">Key results</h2>
      <dl className="processing-output-key-values compact">
        {values.map((item) => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}
      </dl>
    </section>
  );
}

export function ProcessingOutputDetail({ data }: { data: ExactProcessingOutput }) {
  const curve = selectCurve(data);
  return (
    <div className="processing-output-detail">
      <div className="processing-output-primary">
        <section className="processing-output-curve" aria-labelledby="processing-output-curve-title">
          <div className="detail-section-heading">
            <h2 id="processing-output-curve-title">{curve ? curveTitle(curve) : "Result curve"}</h2>
            {curve ? (
              <div className="processing-output-legend" aria-label="Curve legend">
                <span><i className="fit" />Selected result</span>
                {curve.observedX ? <span><i className="observed" />Processed source points</span> : null}
              </div>
            ) : null}
          </div>
          {curve ? <CurvePlot curve={curve} /> : <div className="ux-empty"><strong>No plottable result series.</strong></div>}
        </section>
        <FitSummary data={data} />
      </div>
      <KeyResults data={data} />
    </div>
  );
}

export function ProcessingOutputEvidence({ data }: { data: ExactProcessingOutput }) {
  const candidates = finalStage(data).fit_candidates ?? [];
  return (
    <>
      <h3>Processing stages</h3>
      <ol className="processing-output-technical-stages">
        {data.document.result.stages.map((stage) => (
          <li key={`${stage.ordinal}:${stage.method_id}`}>{STAGE_LABELS[stage.method_id] ?? words(stage.method_id)}</li>
        ))}
      </ol>
      <h3>Processing Output evidence</h3>
      <dl className="evidence-grid">
        <dt>Processing Output ID</dt><dd>{data.summary.processing_output_id}</dd>
        <dt>Exact output revision</dt><dd>{data.summary.current_revision.id}</dd>
        <dt>Artifact digest</dt><dd>{data.summary.output_sha256}</dd>
        <dt>Source Test Data revision</dt><dd>{data.document.source_document.revision_id}</dd>
        <dt>Source canonical digest</dt><dd>{data.document.source_canonical_artifact_sha256}</dd>
        <dt>Mapping Profile revision</dt><dd>{data.document.mapping_profile.revision_id}</dd>
        <dt>Mapping Profile digest</dt><dd>{data.summary.mapping_profile_sha256}</dd>
        <dt>Document contract</dt><dd>{data.document.document_type} · {data.document.document_version}</dd>
      </dl>
      {candidates.length ? (
        <>
          <h3>Fit diagnostics</h3>
          <table className="ux-table processing-output-diagnostics">
            <thead><tr><th>Candidate</th><th>Convergence</th><th>Relative RMSE</th><th>Identifiability</th><th>Evaluations</th><th>Active bounds</th></tr></thead>
            <tbody>
              {candidates.map((candidate) => (
                <tr key={candidate.family}>
                  <td>{familyLabel(candidate.family)}</td>
                  <td>{candidate.convergence ? "Converged" : "Not converged"}</td>
                  <td>{formatNumber(candidate.relative_rmse * 100)} %</td>
                  <td>{sentence(candidate.identifiability)}</td>
                  <td>{candidate.nfev}</td>
                  <td>{candidate.active_bound.length ? candidate.active_bound.map((item) => PARAMETER_LABELS[item] ?? item).join(", ") : "None"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
      {data.document.workup_overrides.length ? (
        <>
          <h3>Workup decisions</h3>
          <table className="ux-table processing-output-workup">
            <thead><tr><th>Decision</th><th>Recorded value</th><th>Canonical value</th><th>Reason</th></tr></thead>
            <tbody>
              {data.document.workup_overrides.map((item) => (
                <tr key={item.kind}>
                  <td>{words(item.kind)}</td>
                  <td>{formatNumber(item.original_value)} {item.original_unit}</td>
                  <td>{formatNumber(item.canonical_value)} {item.canonical_unit}</td>
                  <td>{item.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}
    </>
  );
}
