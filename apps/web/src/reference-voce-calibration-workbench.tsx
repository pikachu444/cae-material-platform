import { type FormEvent, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createReferenceVoceCalibrationPlan,
  createReferenceVoceCandidateSelection,
  projectSelectedReferenceVoceCandidate,
  preflightElastoplasticMapping,
  createElastoplasticSolverCard,
  previewElastoplasticSolverCard,
  downloadElastoplasticSolverCard,
  executeReferenceVoceCalibration,
  createReferenceVoceHoldoutPlan,
  executeReferenceVoceHoldout,
  previewReferenceVoceCalibrationDiagnostics,
} from "./api";
import type {
  MaterialStateResponse,
  PropertySetResponse,
  ReferenceCalibrationScopeResponse,
  VoceCalibrationPlanResponse,
  VoceCalibrationDiagnosticPreview,
  VoceCalibrationRunResponse,
  VoceCandidateSelectionResponse,
  TabulatedPlasticityModelResponse,
  MappingReport,
  ElastoplasticCardResponse,
  DatasetResponse,
  VoceHoldoutPlanResponse,
  VoceHoldoutResultResponse,
} from "./types";
import "./features/modeling/ui/modeling-calibration-workbenches.css";

const COLORS = ["#55d6be", "#ffb347", "#7aa7ff", "#e77cff", "#ff6b6b"];

function messageFor(error: unknown): string {
  if (error instanceof ApiError) return error.message;
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

function VoceHoldoutPlot({ result }: { result: VoceHoldoutResultResponse }) {
  if (!result.points.length) return null;
  const maxX = Math.max(...result.points.map((point) => point.true_plastic_strain)) || 1;
  const values = result.points.flatMap((point) => [
    point.observed_true_yield_stress_pa,
    point.predicted_true_yield_stress_pa,
  ]);
  const minY = Math.min(...values);
  const maxY = Math.max(...values);
  const span = maxY - minY || 1;
  const x = (value: number) => 48 + (value / maxX) * 654;
  const y = (value: number) => 226 - ((value - minY) / span) * 202;
  return (
    <section className="curve-panel" aria-label="Voce holdout observed and predicted curve">
      <div className="curve-heading">
        <div><p className="eyebrow">V3 holdout evidence</p><h5>Independent observed vs predicted true stress</h5></div>
        <span className={`reference-chip ${result.verdict === "passed" ? "success" : "warning"}`}>
          {result.verdict} · {(result.relative_root_mean_squared_error * 100).toFixed(2)}%
        </span>
      </div>
      <svg className="curve-plot" viewBox="0 0 720 280" role="img">
        <line x1="48" x2="702" y1="226" y2="226" />
        <line x1="48" x2="48" y1="24" y2="226" />
        <polyline
          className="fitted-curve"
          points={result.points.map((point) => `${x(point.true_plastic_strain).toFixed(2)},${y(point.predicted_true_yield_stress_pa).toFixed(2)}`).join(" ")}
        />
        {result.points.map((point) => (
          <circle
            key={point.source_point_ordinal}
            cx={x(point.true_plastic_strain)}
            cy={y(point.observed_true_yield_stress_pa)}
            r="3"
          />
        ))}
        <text x="330" y="274">true plastic strain (1)</text>
        <text x="14" y="150" transform="rotate(-90 14 150)">true yield stress (Pa)</text>
      </svg>
      <p className="form-hint">
        Closed-form material response only · no solver/card execution · residual is predicted minus observed.
      </p>
    </section>
  );
}

interface Props {
  config: ApiConfig;
  state: MaterialStateResponse;
  propertySet: PropertySetResponse;
  scope: ReferenceCalibrationScopeResponse;
  datasets: DatasetResponse[];
}

export function ReferenceVoceCalibrationWorkbench({ config, state, propertySet, scope, datasets }: Props) {
  const properties = propertySet.current_revision.content;
  const yieldStress = properties.yield_stress_pa ?? 300e6;
  const [plan, setPlan] = useState<VoceCalibrationPlanResponse | null>(null);
  const [run, setRun] = useState<VoceCalibrationRunResponse | null>(null);
  const [diagnostics, setDiagnostics] = useState<VoceCalibrationDiagnosticPreview | null>(null);
  const [selection, setSelection] = useState<VoceCandidateSelectionResponse | null>(null);
  const [model, setModel] = useState<TabulatedPlasticityModelResponse | null>(null);
  const [mapping, setMapping] = useState<MappingReport | null>(null);
  const [card, setCard] = useState<ElastoplasticCardResponse | null>(null);
  const [cardPreview, setCardPreview] = useState<string | null>(null);
  const [holdoutPlan, setHoldoutPlan] = useState<VoceHoldoutPlanResponse | null>(null);
  const [holdoutResult, setHoldoutResult] = useState<VoceHoldoutResultResponse | null>(null);
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
  const [selectionReason, setSelectionReason] = useState("Accept the best converged candidate after reviewing fitted curves and residuals");
  const [extension, setExtension] = useState("0.5");
  const [extensionAcknowledged, setExtensionAcknowledged] = useState(false);
  const [targetSolver, setTargetSolver] = useState<"openradioss" | "abaqus">("openradioss");
  const [materialName, setMaterialName] = useState("CALIBRATED_MATERIAL");
  const [solverMaterialId, setSolverMaterialId] = useState("101");
  const holdoutCandidates = useMemo(() => datasets.filter((dataset) => {
    const revision = dataset.current_revision;
    return (revision.content.representation === "normalized" || revision.content.representation === "processed")
      && !scope.members.some((member) => (
        member.dataset_revision_id === revision.id
        || member.test_run_revision_id === revision.content.test_run_revision_id
      ));
  }), [datasets, scope.members]);
  const [holdoutDatasetRevisionId, setHoldoutDatasetRevisionId] = useState("");
  const selectedHoldout = holdoutCandidates.find(
    (dataset) => dataset.current_revision.id === holdoutDatasetRevisionId,
  ) ?? holdoutCandidates[0] ?? null;
  const [holdoutReason, setHoldoutReason] = useState("Validate the accepted Voce IR against an independent Test Run");
  const [action, setAction] = useState<"plan" | "run" | "select" | "project" | "preflight" | "card" | "download" | "holdout-plan" | "holdout-run" | null>(null);
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
      setSelection(null);
      setModel(null);
      setMapping(null);
      setCard(null);
      setHoldoutPlan(null);
      setHoldoutResult(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function acceptCandidate(): Promise<void> {
    if (!run || !best) return;
    setAction("select");
    setError(null);
    try {
      const result = await createReferenceVoceCandidateSelection(config, {
        classification: run.classification,
        selection_label: `${planLabel.trim()} accepted candidate`,
        voce_calibration_run_id: run.voce_calibration_run_id,
        voce_calibration_candidate_id: best.voce_calibration_candidate_id,
        selection_reason: selectionReason.trim(),
      });
      setSelection(result.data);
      setModel(null);
      setMapping(null);
      setCard(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function projectCandidate(): Promise<void> {
    if (!selection) return;
    setAction("project");
    setError(null);
    try {
      const result = await projectSelectedReferenceVoceCandidate(
        config,
        selection.voce_candidate_selection_id,
        {
          selection_revision_id: selection.current_revision.id,
          sampling_point_count: 51,
          extension_max_true_plastic_strain: Number(extension),
          acknowledge_constant_extension: extensionAcknowledged,
          change_reason: "Project accepted Voce Candidate on the fixed 51-point solver-neutral grid",
        },
      );
      setModel(result.data);
      setMapping(null);
      setCard(null);
      setCardPreview(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  const target = {
    solver: targetSolver,
    version: "2025" as const,
    unit_system: "kg_m_s" as const,
  };

  async function preflight(): Promise<void> {
    if (!model) return;
    setAction("preflight");
    setError(null);
    try {
      const result = await preflightElastoplasticMapping(
        config,
        model.material_model_id,
        model.current_revision.id,
        target,
      );
      setMapping(result.data);
      setCard(null);
      setCardPreview(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function generateCard(): Promise<void> {
    if (!model || !mapping) return;
    setAction("card");
    setError(null);
    try {
      const result = await createElastoplasticSolverCard(config, model.material_model_id, {
        material_model_revision_id: model.current_revision.id,
        target,
        expected_mapping_report_sha256: mapping.mapping_report_sha256,
        solver_material_id: Number(solverMaterialId),
        material_name: materialName.trim(),
        change_reason: `Generate ${targetSolver} card from accepted calibrated IR`,
      });
      setCard(result.data.card);
      const preview = await previewElastoplasticSolverCard(config, result.data.card.solver_card_id);
      setCardPreview(preview.data);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function downloadCard(): Promise<void> {
    if (!card) return;
    setAction("download");
    try {
      const result = await downloadElastoplasticSolverCard(config, card.solver_card_id);
      const url = URL.createObjectURL(result.data.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.data.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function createHoldoutPlan(): Promise<void> {
    if (!model || !selectedHoldout) return;
    setAction("holdout-plan");
    setError(null);
    try {
      const created = await createReferenceVoceHoldoutPlan(config, {
        classification: state.current_revision.classification,
        content: {
          plan_label: `${planLabel.trim()} independent holdout`,
          material_model_id: model.material_model_id,
          material_model_revision_id: model.current_revision.id,
          holdout_dataset_id: selectedHoldout.dataset_id,
          holdout_dataset_revision_id: selectedHoldout.current_revision.id,
        },
        change_reason: holdoutReason.trim(),
      });
      setHoldoutPlan(created.data);
      setHoldoutResult(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function executeHoldout(): Promise<void> {
    if (!holdoutPlan) return;
    setAction("holdout-run");
    setError(null);
    try {
      const result = await executeReferenceVoceHoldout(
        config,
        holdoutPlan.voce_holdout_plan_id,
        {
          plan_revision_id: holdoutPlan.current_revision.id,
          change_reason: holdoutReason.trim(),
        },
      );
      setHoldoutResult(result.data);
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
      {best ? (
        <section className="workflow-stack calibrated-card-workflow" aria-label="Accepted Voce candidate to solver card">
          <div className="section-heading compact-heading">
            <div><p className="eyebrow">P1 · Candidate promotion</p><h5>Accepted Candidate → IR 1.1 → Solver Card</h5></div>
            <span className="reference-chip">OpenRadioss + Abaqus</span>
          </div>
          {!selection ? (
            <div className="workflow-step">
              <label>Human selection reason<input value={selectionReason} onChange={(event) => setSelectionReason(event.target.value)} required /></label>
              <button className="button primary" type="button" disabled={action !== null || !selectionReason.trim()} onClick={() => void acceptCandidate()}>
                {action === "select" ? "Recording immutable selection…" : "Accept this converged Candidate"}
              </button>
            </div>
          ) : (
            <div className="workflow-step">
              <strong>Accepted Selection {shortId(selection.voce_candidate_selection_id)}</strong>
              <p className="form-hint">The Candidate digest and human reason are pinned in an immutable revision.</p>
              <div className="form-grid three-columns">
                <label>Fixed-grid points<input type="number" value="51" disabled /></label>
                <label>Constant extension max εp<input type="number" min="0.001" step="any" value={extension} onChange={(event) => setExtension(event.target.value)} /></label>
                <label className="checkbox-line"><input type="checkbox" checked={extensionAcknowledged} onChange={(event) => setExtensionAcknowledged(event.target.checked)} /> Acknowledge constant extension approximation</label>
              </div>
              <button className="button primary" type="button" disabled={action !== null || !extensionAcknowledged} onClick={() => void projectCandidate()}>
                {action === "project" ? "Projecting calibrated IR…" : "Create solver-neutral calibrated IR"}
              </button>
            </div>
          )}
          {model ? (
            <div className="workflow-step">
              <strong>IR {shortId(model.material_model_id)} · {model.current_revision.content.model_family_id}</strong>
              <p className="form-hint">51 exact Voce samples plus one explicitly acknowledged constant extension point. No solver keyword is stored in the IR.</p>
              <div className="form-grid three-columns">
                <label>Target solver<select value={targetSolver} onChange={(event) => { setTargetSolver(event.target.value as "openradioss" | "abaqus"); setMapping(null); setCard(null); setCardPreview(null); }}><option value="openradioss">OpenRadioss 2025 · LAW36</option><option value="abaqus">Abaqus 2025 · isotropic *PLASTIC</option></select></label>
                <label>Material name<input value={materialName} onChange={(event) => setMaterialName(event.target.value)} /></label>
                <label>Solver material ID<input type="number" min="1" value={solverMaterialId} onChange={(event) => setSolverMaterialId(event.target.value)} /></label>
              </div>
              <button className="button secondary" type="button" disabled={action !== null} onClick={() => void preflight()}>{action === "preflight" ? "Checking mapping…" : "Run mapping preflight"}</button>
              {mapping ? (
                <>
                  <ul className="qc-list">{mapping.items.map((item) => <li key={item.name}><strong>{item.status}</strong> · {item.name} · {item.detail}</li>)}</ul>
                  <button className="button primary" type="button" disabled={action !== null || !mapping.exportable} onClick={() => void generateCard()}>{action === "card" ? "Generating card…" : `Generate ${targetSolver === "abaqus" ? "Abaqus .inp" : "OpenRadioss .rad"}`}</button>
                </>
              ) : null}
            </div>
          ) : null}
          {card ? (
            <div className="workflow-step">
              <strong>Immutable card {shortId(card.solver_card_id)}</strong>
              <button className="button secondary" type="button" disabled={action !== null} onClick={() => void downloadCard()}>{action === "download" ? "Preparing download…" : "Download solver card"}</button>
              {cardPreview ? <pre className="card-preview"><code>{cardPreview}</code></pre> : null}
            </div>
          ) : null}
        </section>
      ) : null}
      {model ? (
        <section className="workflow-stack voce-holdout-workflow" aria-label="Solver-independent Voce holdout validation">
          <div className="section-heading compact-heading">
            <div><p className="eyebrow">P1 · V3 Validation</p><h5>Independent tensile holdout</h5></div>
            <span className="reference-chip">closed-form · no solver</span>
          </div>
          <p className="form-hint">
            Dataset revision and Test Run revision must both be absent from the complete calibration review Scope.
            A 5% relative-RMSE threshold is reference evidence only, not production approval.
          </p>
          {holdoutCandidates.length ? (
            <div className="workflow-step">
              <label>
                Independent holdout Dataset
                <select
                  aria-label="Independent holdout Dataset"
                  value={selectedHoldout?.current_revision.id ?? ""}
                  onChange={(event) => {
                    setHoldoutDatasetRevisionId(event.target.value);
                    setHoldoutPlan(null);
                    setHoldoutResult(null);
                  }}
                >
                  {holdoutCandidates.map((dataset) => (
                    <option key={dataset.current_revision.id} value={dataset.current_revision.id}>
                      {dataset.current_revision.content.representation} · {shortId(dataset.current_revision.id)} · Test Run {shortId(dataset.current_revision.content.test_run_revision_id)}
                    </option>
                  ))}
                </select>
              </label>
              <label>Validation reason<input value={holdoutReason} onChange={(event) => setHoldoutReason(event.target.value)} required /></label>
              {!holdoutPlan ? (
                <button className="button secondary" type="button" disabled={action !== null || !holdoutReason.trim()} onClick={() => void createHoldoutPlan()}>
                  {action === "holdout-plan" ? "Pinning independent inputs…" : "Create immutable holdout Plan"}
                </button>
              ) : (
                <button className="button primary" type="button" disabled={action !== null} onClick={() => void executeHoldout()}>
                  {action === "holdout-run" ? "Evaluating holdout…" : "Evaluate closed-form holdout"}
                </button>
              )}
            </div>
          ) : (
            <div className="warning-banner">
              No independent Dataset is available. Upload a tensile Test Run that is not part of the calibration review Scope.
            </div>
          )}
          {holdoutResult ? (
            <>
              <div className="property-grid">
                <div><span>Holdout independence</span><strong>Dataset + Test Run disjoint</strong></div>
                <div><span>RMSE</span><strong>{mpa(holdoutResult.root_mean_squared_error_pa)}</strong></div>
                <div><span>Relative RMSE</span><strong>{(holdoutResult.relative_root_mean_squared_error * 100).toFixed(3)}%</strong></div>
                <div><span>Reference verdict</span><strong>{holdoutResult.verdict}</strong></div>
              </div>
              <p className="source-line">
                Result {shortId(holdoutResult.voce_holdout_result_id)} · comparison Artifact {shortId(holdoutResult.comparison_artifact_id)} · {holdoutResult.comparison_point_count} points
              </p>
              <VoceHoldoutPlot result={holdoutResult} />
            </>
          ) : null}
        </section>
      ) : null}
      {error ? <div className="error-banner" role="alert">{error}</div> : null}
    </section>
  );
}
