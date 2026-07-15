import { type FormEvent, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createReferenceVoceCalibrationPlan,
  executeReferenceVoceCalibration,
  previewReferenceVoceCalibrationDiagnostics,
} from "./api";
import type {
  MaterialStateResponse,
  PropertySetResponse,
  ReferenceCalibrationScopeResponse,
  VoceCalibrationPlanResponse,
  VoceCalibrationDiagnosticPreview,
  VoceCalibrationRunResponse,
} from "./types";

const COLORS = ["#55d6be", "#ffb347", "#7aa7ff", "#e77cff", "#ff6b6b"];

function messageFor(error: unknown): string {
  if (error instanceof ApiError) return error.code ? `${error.message} (${error.code})` : error.message;
  return error instanceof Error ? error.message : "The Voce reference calibration failed.";
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function mpa(value: number): string {
  return `${(value / 1e6).toFixed(3)} MPa`;
}

function VoceFitPlot({ diagnostics }: { diagnostics: VoceCalibrationDiagnosticPreview }) {
  const points = diagnostics.points;
  if (!points.length) return null;
  const maxX = Math.max(...points.map((point) => point.true_plastic_strain)) || 1;
  const stresses = points.flatMap((point) => [
    point.observed_true_yield_stress_pa,
    point.predicted_true_yield_stress_pa,
  ]);
  const minY = Math.min(...stresses);
  const maxY = Math.max(...stresses);
  const ySpan = maxY - minY || 1;
  const x = (value: number) => 48 + (value / maxX) * 654;
  const y = (value: number) => 226 - ((value - minY) / ySpan) * 202;
  const members = [...new Set(points.map((point) => point.member_ordinal))];
  return (
    <section className="curve-panel" aria-label="Observed and fitted Voce curves">
      <div className="curve-heading">
        <div><p className="eyebrow">Candidate diagnostics</p><h5>Observed and fitted true stress</h5></div>
        <span className="reference-chip">{diagnostics.returned_point_count} points</span>
      </div>
      <svg className="curve-plot" viewBox="0 0 720 280" role="img" aria-label="Observed and fitted Voce stress plastic strain curves">
        <line x1="48" x2="702" y1="226" y2="226" />
        <line x1="48" x2="48" y1="24" y2="226" />
        {members.map((member) => {
          const curve = points.filter((point) => point.member_ordinal === member);
          const color = COLORS[member % COLORS.length];
          return (
            <g key={member}>
              <polyline
                className="fitted-curve"
                style={{ stroke: color }}
                points={curve.map((point) => `${x(point.true_plastic_strain).toFixed(2)},${y(point.predicted_true_yield_stress_pa).toFixed(2)}`).join(" ")}
              />
              {curve.map((point) => (
                <circle
                  key={point.point_ordinal}
                  cx={x(point.true_plastic_strain)}
                  cy={y(point.observed_true_yield_stress_pa)}
                  r="2.8"
                  fill={color}
                />
              ))}
            </g>
          );
        })}
        <text x="330" y="274">true plastic strain (1)</text>
        <text x="14" y="150" transform="rotate(-90 14 150)">true yield stress (Pa)</text>
      </svg>
      <p className="form-hint">Points: preserved specimen observations · lines: shared fitted Voce response.</p>
    </section>
  );
}

interface Props {
  config: ApiConfig;
  state: MaterialStateResponse;
  propertySet: PropertySetResponse;
  scope: ReferenceCalibrationScopeResponse;
}

export function ReferenceVoceCalibrationWorkbench({ config, state, propertySet, scope }: Props) {
  const properties = propertySet.current_revision.content;
  const yieldStress = properties.yield_stress_pa ?? 300e6;
  const [plan, setPlan] = useState<VoceCalibrationPlanResponse | null>(null);
  const [run, setRun] = useState<VoceCalibrationRunResponse | null>(null);
  const [diagnostics, setDiagnostics] = useState<VoceCalibrationDiagnosticPreview | null>(null);
  const [planLabel, setPlanLabel] = useState("Reviewed replicate Voce reference calibration");
  const [sigmaLowerMpa, setSigmaLowerMpa] = useState(String(yieldStress * 0.6 / 1e6));
  const [sigmaInitialMpa, setSigmaInitialMpa] = useState(String(yieldStress / 1e6));
  const [sigmaUpperMpa, setSigmaUpperMpa] = useState(String(yieldStress * 1.4 / 1e6));
  const [qLowerMpa, setQLowerMpa] = useState("20");
  const [qInitialMpa, setQInitialMpa] = useState("150");
  const [qUpperMpa, setQUpperMpa] = useState("600");
  const [bLower, setBLower] = useState("0.5");
  const [bInitial, setBInitial] = useState("10");
  const [bUpper, setBUpper] = useState("100");
  const [multistart, setMultistart] = useState("3");
  const [normalizationMpa, setNormalizationMpa] = useState("100");
  const [reason, setReason] = useState("Pin reviewed curves and explicit Voce/SciPy conventions");
  const [runReason, setRunReason] = useState("Execute deterministic multi-curve reference calibration");
  const [action, setAction] = useState<"plan" | "run" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const best = useMemo(
    () => run?.candidates.find((candidate) => candidate.status === "converged") ?? null,
    [run],
  );

  async function createPlan(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setAction("plan");
    setError(null);
    try {
      const result = await createReferenceVoceCalibrationPlan(config, {
        classification: state.current_revision.classification,
        plan_label: planLabel.trim(),
        calibration_input_scope_id: scope.scope_id,
        calibration_input_scope_revision_id: scope.current_revision.id,
        material_state_id: state.material_state_id,
        material_state_revision_id: state.current_revision.id,
        property_set_id: propertySet.property_set_id,
        property_set_revision_id: propertySet.current_revision.id,
        youngs_modulus_pa: properties.youngs_modulus_pa,
        sigma_0_pa: {
          lower: Number(sigmaLowerMpa) * 1e6,
          initial: Number(sigmaInitialMpa) * 1e6,
          upper: Number(sigmaUpperMpa) * 1e6,
          scale: Number(sigmaInitialMpa) * 1e6,
        },
        q_pa: {
          lower: Number(qLowerMpa) * 1e6,
          initial: Number(qInitialMpa) * 1e6,
          upper: Number(qUpperMpa) * 1e6,
          scale: Number(qInitialMpa) * 1e6,
        },
        b: {
          lower: Number(bLower),
          initial: Number(bInitial),
          upper: Number(bUpper),
          scale: Number(bInitial),
        },
        normalization_stress_scale_pa: Number(normalizationMpa) * 1e6,
        multistart_count: Number(multistart),
        random_seed: 20260715,
        maximum_function_evaluations: 2000,
        ftol: 1e-10,
        xtol: 1e-10,
        gtol: 1e-10,
        change_reason: reason.trim(),
      });
      setPlan(result.data);
      setRun(null);
      setDiagnostics(null);
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
      const result = await executeReferenceVoceCalibration(
        config,
        plan.voce_calibration_plan_id,
        { plan_revision_id: plan.current_revision.id, change_reason: runReason.trim() },
      );
      setRun(result.data);
      const candidate = result.data.candidates.find((item) => item.status === "converged");
      if (candidate) {
        const preview = await previewReferenceVoceCalibrationDiagnostics(
          config,
          candidate.voce_calibration_candidate_id,
        );
        setDiagnostics(preview.data);
      } else {
        setDiagnostics(null);
      }
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  return (
    <section className="reference-calibration-workbench voce-workbench" aria-label="Reference Voce calibration workbench">
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">P1 · Modeling</p>
          <h4>Multi-curve Voce reference calibration</h4>
        </div>
        <span className="reference-chip">non-production · solver-neutral</span>
      </div>
      <p className="form-hint">
        The reviewed Scope pins {scope.included_member_count} included curve revisions. Each
        specimen has equal objective weight; excluded source curves remain preserved.
      </p>
      <form className="form-stack" onSubmit={(event) => void createPlan(event)}>
        <label>Plan label<input value={planLabel} onChange={(event) => setPlanLabel(event.target.value)} required /></label>
        <div className="form-grid three-columns calibration-parameter-grid">
          <label>σ₀ lower (MPa)<input type="number" min="0.001" step="any" value={sigmaLowerMpa} onChange={(event) => setSigmaLowerMpa(event.target.value)} required /></label>
          <label>σ₀ initial (MPa)<input type="number" min="0.001" step="any" value={sigmaInitialMpa} onChange={(event) => setSigmaInitialMpa(event.target.value)} required /></label>
          <label>σ₀ upper (MPa)<input type="number" min="0.001" step="any" value={sigmaUpperMpa} onChange={(event) => setSigmaUpperMpa(event.target.value)} required /></label>
          <label>Q lower (MPa)<input type="number" min="0.001" step="any" value={qLowerMpa} onChange={(event) => setQLowerMpa(event.target.value)} required /></label>
          <label>Q initial (MPa)<input type="number" min="0.001" step="any" value={qInitialMpa} onChange={(event) => setQInitialMpa(event.target.value)} required /></label>
          <label>Q upper (MPa)<input type="number" min="0.001" step="any" value={qUpperMpa} onChange={(event) => setQUpperMpa(event.target.value)} required /></label>
          <label>b lower<input type="number" min="0.001" step="any" value={bLower} onChange={(event) => setBLower(event.target.value)} required /></label>
          <label>b initial<input type="number" min="0.001" step="any" value={bInitial} onChange={(event) => setBInitial(event.target.value)} required /></label>
          <label>b upper<input type="number" min="0.001" step="any" value={bUpper} onChange={(event) => setBUpper(event.target.value)} required /></label>
          <label>Normalization (MPa)<input type="number" min="0.001" step="any" value={normalizationMpa} onChange={(event) => setNormalizationMpa(event.target.value)} required /></label>
          <label>Deterministic starts<input type="number" min="1" max="16" step="1" value={multistart} onChange={(event) => setMultistart(event.target.value)} required /></label>
        </div>
        <label>Change reason<input value={reason} onChange={(event) => setReason(event.target.value)} required /></label>
        <button className="button primary" type="submit" disabled={action !== null}>
          {action === "plan" ? "Pinning calibration Plan…" : "Create immutable Voce Plan"}
        </button>
      </form>
      {plan ? (
        <div className="workflow-step calibration-plan-result">
          <strong>Plan {shortId(plan.voce_calibration_plan_id)} · r{plan.current_revision.revision_no}</strong>
          <p className="form-hint">SciPy least_squares · TRF · PCG64 seed 20260715 · missing data rejected.</p>
          <label>Run reason<input value={runReason} onChange={(event) => setRunReason(event.target.value)} required /></label>
          <button className="button primary" type="button" disabled={action !== null || !runReason.trim()} onClick={() => void execute()}>
            {action === "run" ? "Fitting all retained curves…" : "Execute multi-curve Calibration Run"}
          </button>
        </div>
      ) : null}
      {run ? (
        <section className="statistics-result" aria-live="polite">
          <div className="curve-heading">
            <div><p className="eyebrow">Durable calibration run</p><h5>{run.status} · {run.candidate_count} candidates</h5></div>
            <span className="reference-chip">{run.source_curve_count} curves · {run.attempt_count} starts</span>
          </div>
          {best ? (
            <>
              <div className="property-grid">
                <div><span>σ₀</span><strong>{mpa(best.sigma_0_pa)}</strong></div>
                <div><span>Q</span><strong>{mpa(best.q_pa)}</strong></div>
                <div><span>b</span><strong>{best.b.toPrecision(7)}</strong></div>
                <div><span>Objective</span><strong>{best.objective_total.toExponential(5)}</strong></div>
              </div>
              <p className="source-line">
                {best.convergence_reason} · {best.function_evaluations} evaluations · residual RMS {mpa(best.residual_root_mean_square_pa)}
              </p>
              <ul className="qc-list">
                {best.objective_terms.map((term) => (
                  <li key={term.dataset_revision_id}>
                    member {term.member_ordinal + 1} · {shortId(term.dataset_revision_id)} · {term.point_count} points · objective {term.mean_normalized_squared_residual.toExponential(5)}
                  </li>
                ))}
              </ul>
              <p className="form-hint">
                Identifiability: {best.identifiability_status} · uncertainty: {best.uncertainty_status} · diagnostics {shortId(best.diagnostics_sha256)}
              </p>
              {diagnostics ? <VoceFitPlot diagnostics={diagnostics} /> : null}
            </>
          ) : <p>No converged candidate is available. Review the persisted attempt diagnostics.</p>}
        </section>
      ) : null}
      {error ? <div className="error-banner" role="alert">{error}</div> : null}
    </section>
  );
}
