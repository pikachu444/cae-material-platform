import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createReferenceTensileReplicateSelection,
  createReferenceTensileReplicateStatisticalPlan,
  executeReferenceTensileReplicateStatistics,
  getReferenceTensileReplicateStatisticalResult,
  previewReferenceTensileReplicateStatisticalResultCurve,
} from "./api";
import type {
  DataClassification,
  ReplicateStatisticalCurveResponse,
  ReplicateStatisticalPlanResponse,
  ReplicateStatisticalResultResponse,
  ReplicateStatisticalRunResponse,
  TensileReplicateSelectionResponse,
} from "./types";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    return error.code ? `${error.message} (${error.code})` : error.message;
  }
  return error instanceof Error ? error.message : "The replicate statistics workflow failed.";
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function scientific(value: number): string {
  return value.toExponential(5);
}

function StatisticsCurve({ curve }: { curve: ReplicateStatisticalCurveResponse }) {
  if (!curve.points.length) return null;
  const xs = curve.points.map((point) => point.engineering_strain);
  const ys = curve.points.flatMap((point) => [
    point.statistics.minimum,
    point.statistics.maximum,
  ]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xSpan = maxX - minX || 1;
  const ySpan = maxY - minY || 1;
  const x = (value: number) => 48 + ((value - minX) / xSpan) * 654;
  const y = (value: number) => 240 - ((value - minY) / ySpan) * 222;
  const line = (field: "mean" | "minimum" | "maximum") => curve.points
    .map((point) => `${x(point.engineering_strain).toFixed(2)},${y(point.statistics[field]).toFixed(2)}`)
    .join(" ");
  const confidenceBand = [
    ...curve.points.map((point) => (
      `${x(point.engineering_strain).toFixed(2)},${y(point.statistics.mean_confidence_interval_upper_95).toFixed(2)}`
    )),
    ...[...curve.points].reverse().map((point) => (
      `${x(point.engineering_strain).toFixed(2)},${y(point.statistics.mean_confidence_interval_lower_95).toFixed(2)}`
    )),
  ].join(" ");
  return (
    <section className="curve-panel" aria-label="Replicate statistical curve band">
      <div className="curve-heading">
        <div><p className="eyebrow">Pointwise statistics</p><h5>Mean, 95% CI, and observed range</h5></div>
        <span className="reference-chip">{curve.points.length} grid points</span>
      </div>
      <svg className="curve-plot replicate-statistics-plot" viewBox="0 0 720 280" role="img">
        <line x1="48" x2="702" y1="240" y2="240" />
        <line x1="48" x2="48" y1="18" y2="240" />
        <polygon className="confidence-band" points={confidenceBand} />
        <polyline className="observed-range" points={line("minimum")} />
        <polyline className="observed-range" points={line("maximum")} />
        <polyline className="statistical-mean" points={line("mean")} />
        <text x="340" y="278">engineering strain (1)</text>
        <text x="14" y="144" transform="rotate(-90 14 144)">engineering stress (Pa)</text>
      </svg>
      <p className="form-hint">Solid: mean · shaded: Student-t two-sided 95% CI · dashed: observed minimum/maximum.</p>
    </section>
  );
}

interface Props {
  config: ApiConfig;
  classification: DataClassification;
  alignedDatasetRevisionIds: string[];
  pinnedSelection?: TensileReplicateSelectionResponse;
}

export function ReferenceReplicateStatisticsWorkbench({
  config,
  classification,
  alignedDatasetRevisionIds,
  pinnedSelection,
}: Props) {
  const alignmentKey = useMemo(
    () => alignedDatasetRevisionIds.join(","),
    [alignedDatasetRevisionIds],
  );
  const [selection, setSelection] = useState<TensileReplicateSelectionResponse | null>(null);
  const [plan, setPlan] = useState<ReplicateStatisticalPlanResponse | null>(null);
  const [run, setRun] = useState<ReplicateStatisticalRunResponse | null>(null);
  const [result, setResult] = useState<ReplicateStatisticalResultResponse | null>(null);
  const [curve, setCurve] = useState<ReplicateStatisticalCurveResponse | null>(null);
  const [selectionLabel, setSelectionLabel] = useState("Aligned tensile replicate statistics input");
  const [selectionReason, setSelectionReason] = useState("Pin aligned processed revisions for statistics");
  const [planLabel, setPlanLabel] = useState("Reference multi-replicate tensile statistics");
  const [planReason, setPlanReason] = useState("Define exact-grid replicate statistics methods");
  const [runReason, setRunReason] = useState("Calculate persisted replicate statistics and QC");
  const [action, setAction] = useState<"selection" | "plan" | "run" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSelection(pinnedSelection ?? null);
    setPlan(null);
    setRun(null);
    setResult(null);
    setCurve(null);
  }, [alignmentKey, pinnedSelection]);

  async function pinAlignedOutputs(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setAction("selection");
    setError(null);
    try {
      const response = await createReferenceTensileReplicateSelection(config, {
        classification,
        selection_label: selectionLabel.trim(),
        dataset_revision_ids: alignedDatasetRevisionIds,
        change_reason: selectionReason.trim(),
      });
      setSelection(response.data);
      setPlan(null);
      setRun(null);
      setResult(null);
      setCurve(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function createPlan(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selection) return;
    setAction("plan");
    setError(null);
    try {
      const response = await createReferenceTensileReplicateStatisticalPlan(config, {
        classification,
        plan_label: planLabel.trim(),
        selection_id: selection.selection_id,
        selection_revision_id: selection.current_revision.id,
        sample_count: selection.current_revision.content.member_count,
        change_reason: planReason.trim(),
      });
      setPlan(response.data);
      setRun(null);
      setResult(null);
      setCurve(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function execute(): Promise<void> {
    if (!plan) return;
    setAction("run");
    setError(null);
    try {
      const runResponse = await executeReferenceTensileReplicateStatistics(config, {
        plan_id: plan.statistical_plan_id,
        plan_revision_id: plan.current_revision.id,
        change_reason: runReason.trim(),
      });
      setRun(runResponse.data);
      if (runResponse.data.status !== "succeeded" || !runResponse.data.result_id) return;
      const [resultResponse, curveResponse] = await Promise.all([
        getReferenceTensileReplicateStatisticalResult(config, runResponse.data.result_id),
        previewReferenceTensileReplicateStatisticalResultCurve(
          config,
          runResponse.data.result_id,
          1_000,
        ),
      ]);
      setResult(resultResponse.data);
      setCurve(curveResponse.data);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  const scalar = result?.peak_engineering_stress_pa;
  return (
    <div className="replicate-statistics-workbench">
      {pinnedSelection ? (
        <div className="form-stack">
          <strong>6C. Use the pinned processed Selection as the Statistics input</strong>
          <p className="form-hint">
            This existing immutable Selection already pins all {alignedDatasetRevisionIds.length}
            {" "}processed Dataset revisions. It is reused without alignment or duplication.
          </p>
          <div className="success-banner">
            Selection {shortId(pinnedSelection.selection_id)} revision {shortId(pinnedSelection.current_revision.id)}
            {" · "}n={pinnedSelection.current_revision.content.member_count}
          </div>
        </div>
      ) : (
        <form className="form-stack" onSubmit={(event) => void pinAlignedOutputs(event)}>
          <strong>6C. Pin aligned outputs as the immutable Statistics input</strong>
          <p className="form-hint">
            Statistics never follows the alignment batch implicitly. This explicit Selection pins all
            {" "}{alignedDatasetRevisionIds.length} processed Dataset revisions.
          </p>
          <label>Selection label<input value={selectionLabel} onChange={(event) => setSelectionLabel(event.target.value)} required /></label>
          <label>Change reason<input value={selectionReason} onChange={(event) => setSelectionReason(event.target.value)} required /></label>
          <button className="button secondary" type="submit" disabled={action !== null}>
            {action === "selection" ? "Pinning aligned outputs..." : "Pin aligned outputs"}
          </button>
          {selection ? (
            <div className="success-banner">
              Selection {shortId(selection.selection_id)} revision {shortId(selection.current_revision.id)}
              {" · "}n={selection.current_revision.content.member_count}
            </div>
          ) : null}
        </form>
      )}

      {selection ? (
        <form className="form-stack" onSubmit={(event) => void createPlan(event)}>
          <strong>6D. Persist the typed Statistical Plan</strong>
          <p className="form-hint">
            Exact observed grid, linear-inclusive quantiles, and Student-t two-sided 95% confidence
            intervals are explicit immutable methods. No hidden alignment is performed.
          </p>
          <label>Plan label<input value={planLabel} onChange={(event) => setPlanLabel(event.target.value)} required /></label>
          <label>Change reason<input value={planReason} onChange={(event) => setPlanReason(event.target.value)} required /></label>
          <button className="button secondary" type="submit" disabled={action !== null}>
            {action === "plan" ? "Creating Plan..." : "Create Statistical Plan"}
          </button>
          {plan ? (
            <div className="success-banner">
              Plan {shortId(plan.statistical_plan_id)} · n={plan.current_revision.content.sample_count}
            </div>
          ) : null}
        </form>
      ) : null}

      {plan ? (
        <div className="form-stack">
          <strong>6E. Commit Statistics/QC Run</strong>
          <label>Change reason<input value={runReason} onChange={(event) => setRunReason(event.target.value)} required /></label>
          <button className="button primary" type="button" onClick={() => void execute()} disabled={action !== null || !runReason.trim()}>
            {action === "run" ? "Calculating statistics..." : "Commit Statistics/QC Run"}
          </button>
        </div>
      ) : null}

      {error ? <div className="error-banner" role="alert">{error}</div> : null}
      {run ? (
        <section className="statistics-result" aria-live="polite">
          <div className="workflow-toolbar">
            <span>Run {shortId(run.statistical_run_id)} · {run.status} · n={run.sample_count}</span>
            <span className="reference-chip">{run.failure_code ?? "QC recorded"}</span>
          </div>
          <ul className="qc-list" aria-label="Multi-replicate quality-control observations">
            {run.qc_observations.map((observation) => (
              <li key={observation.check_code} className={observation.outcome}>
                <strong>{observation.check_code}</strong>: {observation.outcome} · {observation.detail}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {scalar ? (
        <section className="statistics-result">
          <div className="curve-heading">
            <div><p className="eyebrow">Peak engineering stress</p><h5>Replicate scalar statistics</h5></div>
            <span className="reference-chip">n={scalar.sample_count}</span>
          </div>
          <dl className="definition-list statistics-definition-list">
            <div><dt>Mean (Pa)</dt><dd>{scientific(scalar.mean)}</dd></div>
            <div><dt>Sample SD (Pa)</dt><dd>{scientific(scalar.sample_standard_deviation)}</dd></div>
            <div><dt>Median (Pa)</dt><dd>{scientific(scalar.median)}</dd></div>
            <div><dt>MAD (Pa)</dt><dd>{scientific(scalar.median_absolute_deviation)}</dd></div>
            <div><dt>IQR (Pa)</dt><dd>{scientific(scalar.interquartile_range)}</dd></div>
            <div><dt>Coefficient of variation</dt><dd>{scalar.coefficient_of_variation?.toPrecision(6) ?? "not applicable"}</dd></div>
            <div><dt>Mean 95% CI (Pa)</dt><dd>{scientific(scalar.mean_confidence_interval_lower_95)} – {scientific(scalar.mean_confidence_interval_upper_95)}</dd></div>
          </dl>
          <p className="source-line">
            Result {shortId(result.statistical_result_id)} · immutable curve Artifact {shortId(result.curve_artifact_id)}
          </p>
        </section>
      ) : null}
      {curve ? <StatisticsCurve curve={curve} /> : null}
    </div>
  );
}
