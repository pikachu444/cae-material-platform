import { type FormEvent, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createReferenceOgdenCalibrationPlan,
  createReferenceOgdenCandidateSelection,
  executeReferenceOgdenCalibration,
  getHyperelasticFamilyCandidateDiagnostics,
  getReferenceOgdenCalibrationRun,
  getReferenceOgdenCandidateDiagnostics,
  listGovernedDatasetsForTestRun,
  listOgdenPronyModelRevisions,
  listScientificProfiles,
  listTestRunsForMaterialState,
  promoteReferenceOgdenCandidate,
} from "./api";
import type {
  GovernedDatasetResponse,
  MaterialStateResponse,
  OgdenCalibrationPlanResponse,
  OgdenCalibrationRole,
  OgdenCalibrationRunResponse,
  OgdenCandidateSelectionResponse,
  OgdenDiagnosticPoint,
  OgdenDiagnosticsResponse,
  HyperelasticDiagnosticsResponse,
  OgdenPronyModelResponse,
  OgdenTestMode,
  ScientificProfileResponse,
  TestRunResponse,
} from "./types";

const MODE_BY_SCHEMA: Partial<Record<GovernedDatasetResponse["data_schema"], OgdenTestMode>> = {
  monotonic_tension: "uniaxial_tension",
  planar_tension: "planar_tension",
  biaxial_tension: "biaxial_tension",
};
const COLORS = ["#55d6be", "#ffb347", "#7aa7ff", "#e77cff", "#ff6b6b"];

interface DatasetChoice {
  dataset: GovernedDatasetResponse;
  run: TestRunResponse;
  included: boolean;
  role: OgdenCalibrationRole;
  mode: OgdenTestMode;
  weight: string;
}

function messageFor(cause: unknown): string {
  if (cause instanceof ApiError) {
    return cause.code ? `${cause.message} (${cause.code})` : cause.message;
  }
  return cause instanceof Error ? cause.message : "The Ogden calibration request failed.";
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function mpa(value: number | null): string {
  return value === null ? "not available" : `${(value / 1e6).toPrecision(5)} MPa`;
}

function OgdenDiagnosticsPlot({
  value,
  modelLabel = "Ogden",
}: {
  value: OgdenDiagnosticsResponse | HyperelasticDiagnosticsResponse;
  modelLabel?: string;
}) {
  const points = value.points;
  if (!points.length) return null;
  const maxStrain = Math.max(...points.map((point) => point.engineering_strain)) || 1;
  const stressValues = points.flatMap((point) => [
    point.observed_nominal_stress_pa,
    point.predicted_nominal_stress_pa,
  ]);
  const maxStress = Math.max(...stressValues, 1);
  const residualScale = Math.max(...points.map((point) => Math.abs(point.residual_pa)), 1);
  const x = (value: number) => 54 + (value / maxStrain) * 638;
  const stressY = (value: number) => 218 - (value / maxStress) * 184;
  const residualY = (value: number) => 316 - (value / residualScale) * 38;
  const members = [...new Set(points.map((point) => point.member_ordinal))];
  return (
    <section className="curve-panel ogden-diagnostics" aria-label={`Observed fitted and residual ${modelLabel} curves`}>
      <div className="curve-heading">
        <div>
          <p className="eyebrow">Candidate diagnostics Artifact</p>
          <h5>Observed, fitted, and residual nominal stress</h5>
        </div>
        <span className="reference-chip">{points.length} exact points</span>
      </div>
      <svg className="curve-plot" viewBox="0 0 720 360" role="img" aria-label={`Multi-test ${modelLabel} fit and residual plot`}>
        <line x1="54" x2="692" y1="218" y2="218" />
        <line x1="54" x2="54" y1="34" y2="218" />
        <line x1="54" x2="692" y1="316" y2="316" />
        {members.map((member) => {
          const curve = points.filter((point) => point.member_ordinal === member);
          const color = COLORS[member % COLORS.length];
          return (
            <g key={member}>
              <polyline
                className="fitted-curve"
                style={{ stroke: color }}
                points={curve.map((point) => `${x(point.engineering_strain)},${stressY(point.predicted_nominal_stress_pa)}`).join(" ")}
              />
              <polyline
                className="residual-curve"
                style={{ stroke: color }}
                points={curve.map((point) => `${x(point.engineering_strain)},${residualY(point.residual_pa)}`).join(" ")}
              />
              {curve.map((point) => (
                <circle
                  key={`${member}-${point.point_ordinal}`}
                  cx={x(point.engineering_strain)}
                  cy={stressY(point.observed_nominal_stress_pa)}
                  r="2.7"
                  fill={color}
                />
              ))}
            </g>
          );
        })}
        <text x="300" y="352">engineering strain (1)</text>
        <text x="14" y="155" transform="rotate(-90 14 155)">nominal stress (Pa)</text>
        <text x="14" y="330" transform="rotate(-90 14 330)">residual</text>
      </svg>
      <div className="diagnostic-legend">
        {members.map((member) => {
          const point = points.find((item) => item.member_ordinal === member) as OgdenDiagnosticPoint;
          return (
            <span key={member}>
              <i style={{ background: COLORS[member % COLORS.length] }} />
              {point.test_mode.replaceAll("_", " ")} · {point.role}
            </span>
          );
        })}
      </div>
    </section>
  );
}

export function ReferenceOgdenCalibrationWorkbench({
  config,
  state,
  model,
  onPromoted,
}: {
  config: ApiConfig;
  state: MaterialStateResponse;
  model: OgdenPronyModelResponse;
  onPromoted?: (value: OgdenPronyModelResponse) => void;
}) {
  const [profiles, setProfiles] = useState<ScientificProfileResponse[]>([]);
  const [choices, setChoices] = useState<DatasetChoice[]>([]);
  const [plan, setPlan] = useState<OgdenCalibrationPlanResponse | null>(null);
  const [run, setRun] = useState<OgdenCalibrationRunResponse | null>(null);
  const [runIdToLoad, setRunIdToLoad] = useState("");
  const [diagnostics, setDiagnostics] = useState<OgdenDiagnosticsResponse | null>(null);
  const [familyDiagnostics, setFamilyDiagnostics] = useState<HyperelasticDiagnosticsResponse | null>(null);
  const [selectedFamilyCandidateId, setSelectedFamilyCandidateId] = useState("");
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [selection, setSelection] = useState<OgdenCandidateSelectionResponse | null>(null);
  const [history, setHistory] = useState<OgdenPronyModelResponse["current_revision"][]>([]);
  const [selectionLabel, setSelectionLabel] = useState("Reviewed multi-test Ogden Candidate");
  const [selectionReason, setSelectionReason] = useState(
    "Reviewed fitted curves, residuals, convergence, bounds, and uncertainty evidence",
  );
  const [promotionReason, setPromotionReason] = useState(
    "Append the human-selected Ogden Candidate as a new immutable IR revision",
  );
  const [planLabel, setPlanLabel] = useState("Governed multi-test Ogden reference fit");
  const [reason, setReason] = useState("Pin exact governed curves and scientific profile revision");
  const [runReason, setRunReason] = useState("Execute deterministic multi-test Ogden reference fitting");
  const [busy, setBusy] = useState<"load" | "load-run" | "plan" | "run" | "diagnostics" | "selection" | "promotion" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadInputs(): Promise<void> {
    setBusy("load");
    setError(null);
    try {
      const [profileResult, runResult, revisionResult] = await Promise.all([
        listScientificProfiles(config, "elastomer_ogden_prony"),
        listTestRunsForMaterialState(config, state.material_state_id),
        listOgdenPronyModelRevisions(config, model.material_model_id),
      ]);
      setHistory(revisionResult.data.items);
      const datasets = await Promise.all(
        runResult.data.items.map(async (testRun) => ({
          testRun,
          result: await listGovernedDatasetsForTestRun(config, testRun.test_run_id),
        })),
      );
      setProfiles(profileResult.data);
      setChoices(
        datasets.flatMap(({ testRun, result }) =>
          result.data.items.flatMap((dataset) => {
            const mode = MODE_BY_SCHEMA[dataset.data_schema];
            if (dataset.representation !== "normalized" || !mode) return [];
            return [{ dataset, run: testRun, included: true, role: "calibration" as const, mode, weight: "1" }];
          }),
        ),
      );
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    setPlan(null);
    setRun(null);
    setSelection(null);
    setDiagnostics(null);
    setFamilyDiagnostics(null);
    setSelectedFamilyCandidateId("");
    setSelectedCandidateId("");
    void loadInputs();
  }, [config.baseUrl, config.accessToken, state.material_state_id, model.current_revision.id]);

  const selected = choices.filter((choice) => choice.included);
  const best = useMemo(
    () => run?.candidates.slice().sort((left, right) => left.objective_total - right.objective_total)[0] ?? null,
    [run],
  );

  async function createPlan(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const profile = profiles[0];
    if (!profile || !selected.length) return;
    setBusy("plan");
    setError(null);
    try {
      const result = await createReferenceOgdenCalibrationPlan(config, {
        classification: state.current_revision.classification,
        plan_label: planLabel.trim(),
        scientific_profile_id: profile.scientific_profile_id,
        scientific_profile_revision_id: profile.current_revision.id,
        material_state_id: state.material_state_id,
        material_state_revision_id: state.current_revision.id,
        baseline_model_id: model.material_model_id,
        baseline_model_revision_id: model.current_revision.id,
        members: selected.map((choice) => ({
          role: choice.role,
          test_mode: choice.mode,
          dataset_id: choice.dataset.dataset_id,
          dataset_revision_id: choice.dataset.current_revision.id,
          weight: Number(choice.weight),
        })),
        change_reason: reason.trim(),
      });
      setPlan(result.data);
      setRun(null);
      setDiagnostics(null);
      setFamilyDiagnostics(null);
      setSelectedFamilyCandidateId("");
      setSelectedCandidateId("");
      setSelection(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  async function showDiagnostics(candidateId: string): Promise<void> {
    setBusy("diagnostics");
    setSelectedCandidateId(candidateId);
    try {
      const result = await getReferenceOgdenCandidateDiagnostics(config, candidateId);
      setDiagnostics(result.data);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  async function showFamilyDiagnostics(candidateId: string): Promise<void> {
    setBusy("diagnostics");
    setSelectedFamilyCandidateId(candidateId);
    setError(null);
    try {
      const result = await getHyperelasticFamilyCandidateDiagnostics(config, candidateId);
      setFamilyDiagnostics(result.data);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  async function execute(): Promise<void> {
    if (!plan) return;
    setBusy("run");
    setError(null);
    try {
      const result = await executeReferenceOgdenCalibration(
        config,
        plan.ogden_calibration_plan_id,
        { plan_revision_id: plan.current_revision.id, change_reason: runReason.trim() },
      );
      setRun(result.data);
      setRunIdToLoad(result.data.ogden_calibration_run_id);
      const candidate = result.data.candidates.slice().sort(
        (left, right) => left.objective_total - right.objective_total,
      )[0];
      if (candidate) await showDiagnostics(candidate.ogden_calibration_candidate_id);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  async function loadExistingRun(): Promise<void> {
    if (!runIdToLoad.trim()) return;
    setBusy("load-run");
    setError(null);
    try {
      const result = await getReferenceOgdenCalibrationRun(config, runIdToLoad.trim());
      if (result.data.material_state_id !== state.material_state_id) {
        throw new Error("The requested Run belongs to a different Material State.");
      }
      setRun(result.data);
      setPlan(null);
      setSelection(null);
      setFamilyDiagnostics(null);
      setSelectedFamilyCandidateId("");
      const candidate = result.data.candidates.slice().sort(
        (left, right) => left.objective_total - right.objective_total,
      )[0];
      if (candidate) await showDiagnostics(candidate.ogden_calibration_candidate_id);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  async function createSelection(): Promise<void> {
    if (!run || !selectedCandidateId) return;
    setBusy("selection");
    setError(null);
    try {
      const result = await createReferenceOgdenCandidateSelection(config, {
        classification: state.current_revision.classification,
        selection_label: selectionLabel.trim(),
        calibration_run_id: run.ogden_calibration_run_id,
        calibration_candidate_id: selectedCandidateId,
        selection_reason: selectionReason.trim(),
      });
      setSelection(result.data);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  async function promoteSelection(): Promise<void> {
    if (!selection) return;
    setBusy("promotion");
    setError(null);
    try {
      const modelEtag = `"revision:${model.current_revision.revision_no}:sha256:${model.current_revision.content_hash}"`;
      const result = await promoteReferenceOgdenCandidate(
        config,
        selection.ogden_candidate_selection_id,
        modelEtag,
        {
          selection_revision_id: selection.current_revision.id,
          change_reason: promotionReason.trim(),
        },
      );
      const revisions = await listOgdenPronyModelRevisions(
        config,
        result.data.material_model_id,
      );
      setHistory(revisions.data.items);
      onPromoted?.(result.data);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="reference-calibration-workbench ogden-calibration-workbench" aria-label="Reference multi-test Ogden calibration workbench">
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">T-43 · governed scientific fitting</p>
          <h4>Multi-test Ogden calibration</h4>
          <p className="muted">
            Exact normalized Dataset revisions are fitted together. Calibration and holdout curves remain disjoint and immutable.
          </p>
        </div>
        <span className="reference-chip">reference · solver-neutral</span>
      </div>

      <div className="inline-action">
        <p className="form-hint">
          {profiles.length} scientific profile · {choices.length} supported normalized curves
        </p>
        <button className="text-button" type="button" disabled={busy !== null} onClick={() => void loadInputs()}>
          Refresh inputs
        </button>
      </div>

      <div className="workflow-step" aria-label="Open immutable hyperelastic calibration Run">
        <strong>Open a saved calibration Run</strong>
        <p className="form-hint">Paste an exact Run ID to restore its family comparison and diagnostics without re-running the fit.</p>
        <div className="inline-action">
          <label>Calibration Run ID<input value={runIdToLoad} onChange={(event) => setRunIdToLoad(event.target.value)} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" /></label>
          <button className="button secondary" type="button" disabled={busy !== null || !runIdToLoad.trim()} onClick={() => void loadExistingRun()}>
            {busy === "load-run" ? "Loading immutable Run…" : "Load saved Run"}
          </button>
        </div>
      </div>

      {!profiles.length ? (
        <p className="warning-notice">Create the explicit reference scientific profile above before fitting.</p>
      ) : null}
      {!choices.length ? (
        <p className="warning-notice">
          Import normalized monotonic, planar, or biaxial tension data for this Material State first.
        </p>
      ) : (
        <form className="form-stack" onSubmit={(event) => void createPlan(event)}>
          <label>Plan label<input value={planLabel} onChange={(event) => setPlanLabel(event.target.value)} required /></label>
          <div className="ogden-input-table" role="table" aria-label="Ogden calibration Dataset members">
            {choices.map((choice, index) => (
              <div className="ogden-input-row" role="row" key={choice.dataset.current_revision.id}>
                <input
                  aria-label={`Include ${choice.run.current_revision.content.run_label}`}
                  type="checkbox"
                  checked={choice.included}
                  onChange={(event) => setChoices((current) => current.map((item, ordinal) => ordinal === index ? { ...item, included: event.target.checked } : item))}
                />
                <div>
                  <strong>{choice.run.current_revision.content.run_label}</strong>
                  <small>{choice.dataset.data_schema.replaceAll("_", " ")} · {choice.dataset.row_count} points · r{choice.dataset.current_revision.revision_no}</small>
                </div>
                <select aria-label={`Role ${choice.run.current_revision.content.run_label}`} value={choice.role} onChange={(event) => setChoices((current) => current.map((item, ordinal) => ordinal === index ? { ...item, role: event.target.value as OgdenCalibrationRole } : item))}>
                  <option value="calibration">calibration</option>
                  <option value="holdout">holdout</option>
                </select>
                <select aria-label={`Mode ${choice.run.current_revision.content.run_label}`} value={choice.mode} onChange={(event) => setChoices((current) => current.map((item, ordinal) => ordinal === index ? { ...item, mode: event.target.value as OgdenTestMode } : item))}>
                  <option value="uniaxial_tension">uniaxial tension</option>
                  <option value="planar_tension">planar tension</option>
                  <option value="biaxial_tension">biaxial tension</option>
                </select>
                <input aria-label={`Weight ${choice.run.current_revision.content.run_label}`} type="number" min="0.000001" step="any" value={choice.weight} onChange={(event) => setChoices((current) => current.map((item, ordinal) => ordinal === index ? { ...item, weight: event.target.value } : item))} />
              </div>
            ))}
          </div>
          <label>Plan change reason<input value={reason} onChange={(event) => setReason(event.target.value)} required /></label>
          <button className="button primary" type="submit" disabled={busy !== null || !selected.some((choice) => choice.role === "calibration")}>
            {busy === "plan" ? "Pinning exact revisions…" : "Create immutable calibration Plan"}
          </button>
        </form>
      )}

      {plan ? (
        <div className="workflow-step">
          <strong>Plan {shortId(plan.ogden_calibration_plan_id)} · r{plan.current_revision.revision_no}</strong>
          <p className="form-hint">
            {plan.current_revision.content.members.length} exact curves · point → curve → mode aggregation · missing data rejected
          </p>
          <label>Run reason<input value={runReason} onChange={(event) => setRunReason(event.target.value)} required /></label>
          <button className="button primary" type="button" disabled={busy !== null || !runReason.trim()} onClick={() => void execute()}>
            {busy === "run" ? "Fitting deterministic starts…" : "Execute Ogden Calibration Run"}
          </button>
        </div>
      ) : null}

      {run ? (
        <section className="statistics-result" aria-live="polite">
          <div className="curve-heading">
            <div>
              <p className="eyebrow">T-55E · public hyperelastic families</p>
              <h5>{run.family_candidate_count} model families compared on the same revisions</h5>
            </div>
            <span className="reference-chip">normalized weighted fit</span>
          </div>
          <div className="candidate-table" role="table" aria-label="Hyperelastic family candidate comparison">
            {run.family_candidates.slice().sort((left, right) => left.objective_total - right.objective_total).map((candidate) => (
              <button
                className={`candidate-row ${selectedFamilyCandidateId === candidate.hyperelastic_family_candidate_id ? "selected" : ""}`}
                type="button"
                role="row"
                key={candidate.hyperelastic_family_candidate_id}
                disabled={!candidate.links.diagnostics || busy !== null}
                onClick={() => void showFamilyDiagnostics(candidate.hyperelastic_family_candidate_id)}
              >
                <strong>{candidate.family.replaceAll("_", " ")}</strong>
                <span>{candidate.parameters.map((parameter) => `${parameter.name}=${parameter.unit === "Pa" ? mpa(parameter.value) : parameter.value.toPrecision(5)}`).join(" · ")}</span>
                <span>NRMSE {candidate.calibration_normalized_rmse.toExponential(3)}</span>
                <span>{candidate.stability_status.replaceAll("_", " ")}</span>
                <span>{candidate.warnings.length ? candidate.warnings.join(", ").replaceAll("_", " ") : "no warning"}</span>
              </button>
            ))}
          </div>
          <div className="curve-heading">
            <div><p className="eyebrow">Immutable candidate comparison</p><h5>{run.candidate_count} candidates · {run.test_mode_count} modes</h5></div>
            <span className="reference-chip">{run.calibration_curve_count} fit · {run.holdout_curve_count} holdout</span>
          </div>
          <div className="candidate-table" role="table" aria-label="Ogden candidate comparison">
            {run.candidates.slice().sort((left, right) => left.objective_total - right.objective_total).map((candidate) => (
              <button
                className={`candidate-row ${selectedCandidateId === candidate.ogden_calibration_candidate_id ? "selected" : ""}`}
                type="button"
                role="row"
                key={candidate.ogden_calibration_candidate_id}
                onClick={() => void showDiagnostics(candidate.ogden_calibration_candidate_id)}
              >
                <span>start {candidate.attempt_ordinal + 1}</span>
                <strong>μ {mpa(candidate.mu_pa)}</strong>
                <strong>α {candidate.alpha.toPrecision(6)}</strong>
                <span>objective {candidate.objective_total.toExponential(3)}</span>
                <span>{candidate.status}</span>
              </button>
            ))}
          </div>
          {best ? (
            <>
              <div className="property-grid">
                <div><span>Calibration RMSE</span><strong>{mpa(best.calibration_rmse_pa)}</strong></div>
                <div><span>Holdout RMSE</span><strong>{mpa(best.holdout_rmse_pa)}</strong></div>
                <div><span>Jacobian rank</span><strong>{best.jacobian_rank}/2</strong></div>
                <div><span>Uncertainty</span><strong>{best.uncertainty_status.replaceAll("_", " ")}</strong></div>
              </div>
              <p className="source-line">{best.convergence_reason} · {best.function_evaluations} evaluations</p>
              <p className="form-hint">
                μ 95% CI {best.mu_confidence_interval_pa ? `${mpa(best.mu_confidence_interval_pa[0])} – ${mpa(best.mu_confidence_interval_pa[1])}` : "not estimable"} · α 95% CI {best.alpha_confidence_interval ? `${best.alpha_confidence_interval[0].toPrecision(5)} – ${best.alpha_confidence_interval[1].toPrecision(5)}` : "not estimable"}
              </p>
              {best.warnings.length ? <ul className="qc-list">{best.warnings.map((warning) => <li key={warning}>{warning.replaceAll("_", " ")}</li>)}</ul> : null}
            </>
          ) : null}
        </section>
      ) : null}
      {familyDiagnostics ? (
        <OgdenDiagnosticsPlot
          value={familyDiagnostics}
          modelLabel={familyDiagnostics.points[0]?.family.replaceAll("_", " ") ?? "hyperelastic family"}
        />
      ) : null}
      {diagnostics ? <OgdenDiagnosticsPlot value={diagnostics} /> : null}
      {run && selectedCandidateId ? (
        <section className="workflow-step ogden-promotion-panel" aria-label="Human Ogden Candidate selection and promotion">
          <div className="curve-heading">
            <div>
              <p className="eyebrow">T-44 · human decision gate</p>
              <h5>Select, explain, then append an IR revision</h5>
            </div>
            <span className="reference-chip">current r{model.current_revision.revision_no}</span>
          </div>
          <p className="form-hint">
            Candidate {shortId(selectedCandidateId)} is not promoted automatically. The exact current IR ETag is required.
          </p>
          <label>Selection label<input value={selectionLabel} onChange={(event) => setSelectionLabel(event.target.value)} required /></label>
          <label>Human selection reason<textarea value={selectionReason} onChange={(event) => setSelectionReason(event.target.value)} required /></label>
          <button className="button secondary" type="button" disabled={busy !== null || !selectionLabel.trim() || !selectionReason.trim()} onClick={() => void createSelection()}>
            {busy === "selection" ? "Recording immutable Selection…" : "Record immutable Candidate Selection"}
          </button>
          {selection ? (
            <div className="promotion-confirmation">
              <strong>Selection r{selection.current_revision.revision_no} recorded</strong>
              <small>{selection.current_revision.content.selection_decision.replaceAll("_", " ")}</small>
              <label>IR promotion reason<input value={promotionReason} onChange={(event) => setPromotionReason(event.target.value)} required /></label>
              <button className="button primary" type="button" disabled={busy !== null || !promotionReason.trim()} onClick={() => void promoteSelection()}>
                {busy === "promotion" ? "Appending immutable IR revision…" : `Promote into model r${model.current_revision.revision_no + 1}`}
              </button>
            </div>
          ) : null}
        </section>
      ) : null}
      {history.length ? (
        <section className="statistics-result ogden-revision-history" aria-label="Ogden IR revision and promotion evidence history">
          <div className="curve-heading">
            <div><p className="eyebrow">Same stable Material Model identity</p><h5>Append-only IR revision history</h5></div>
            <span className="reference-chip">{history.length} revisions</span>
          </div>
          <div className="candidate-table" role="table" aria-label="Ogden IR revisions">
            {history.map((revision) => {
              const term = revision.content.ogden_terms[0];
              const evidence = revision.content.promotion_evidence;
              return (
                <div className="candidate-row" role="row" key={revision.id}>
                  <strong>r{revision.revision_no}</strong>
                  <span>μ {mpa(term?.mu_pa ?? null)}</span>
                  <span>α {term?.alpha.toPrecision(6)}</span>
                  <span>{evidence ? `Candidate ${shortId(evidence.calibration_candidate_id)}` : "manual baseline"}</span>
                  <span>{evidence ? `from ${shortId(evidence.promoted_from_model_revision_id)}` : "initial revision"}</span>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}
      {error ? <p className="error-notice" role="alert">{error}</p> : null}
    </section>
  );
}
