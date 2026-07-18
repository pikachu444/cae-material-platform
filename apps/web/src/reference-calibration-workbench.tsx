import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  type ApiConfig,
  createReferenceCalibrationCandidateSelection,
  createReferenceLinearElasticCalibrationPlan,
  executeReferenceLinearElasticCalibration,
  listDatasetRevisionSelections,
  listDatasetsForMaterialState,
  listMaterialModels,
  promoteSelectedReferenceCalibrationCandidate,
  previewCalibrationCandidateDiagnostics,
} from "./api";
import type {
  CalibrationCandidateSelectionResponse,
  CalibrationDiagnosticPreview,
  CalibrationPlanResponse,
  CalibrationRunResponse,
  DatasetSelectionResponse,
  MaterialModelResponse,
  MaterialStateResponse,
} from "./types";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "The reference calibration workbench could not reach the protected API. Try again.";
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function plotPoints(
  preview: CalibrationDiagnosticPreview,
  value: (point: CalibrationDiagnosticPreview["points"][number]) => number,
): string {
  const width = 720;
  const height = 280;
  const left = 48;
  const right = 18;
  const top = 18;
  const bottom = 40;
  const xs = preview.points.map((point) => point.engineering_strain);
  const ys = preview.points.flatMap((point) => [
    point.observed_engineering_stress_pa,
    point.predicted_engineering_stress_pa,
  ]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xSpan = maxX - minX || 1;
  const ySpan = maxY - minY || 1;
  return preview.points
    .map((point) => {
      const x = left + ((point.engineering_strain - minX) / xSpan) * (width - left - right);
      const y = height - bottom - ((value(point) - minY) / ySpan) * (height - top - bottom);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function CalibrationCurvePanel({ preview }: { preview: CalibrationDiagnosticPreview }) {
  const xValues = preview.points.map((point) => point.engineering_strain);
  const yValues = preview.points.flatMap((point) => [
    point.observed_engineering_stress_pa,
    point.predicted_engineering_stress_pa,
  ]);
  const minX = Math.min(...xValues);
  const maxX = Math.max(...xValues);
  const minY = Math.min(...yValues);
  const maxY = Math.max(...yValues);
  return (
    <section className="calibration-curve-panel" aria-label="Reference calibration fitted curve">
      <div className="curve-heading">
        <div>
          <p className="eyebrow">Candidate diagnostics</p>
          <h5>Observed and fitted engineering-stress curve</h5>
        </div>
        <span className="reference-chip">SI units</span>
      </div>
      <p className="curve-summary">
        {preview.returned_point_count.toLocaleString()} of {preview.point_count.toLocaleString()} points;
        observed is solid and the closed-form fit is dashed
        {preview.sampled ? "; preview points were deterministically sampled" : ""}.
      </p>
      <svg className="calibration-curve-plot" viewBox="0 0 720 280" role="img" aria-label="Observed and fitted stress strain curves">
        <line x1="48" x2="702" y1="240" y2="240" />
        <line x1="48" x2="48" y1="18" y2="240" />
        <polyline className="observed" points={plotPoints(preview, (point) => point.observed_engineering_stress_pa)} />
        <polyline className="predicted" points={plotPoints(preview, (point) => point.predicted_engineering_stress_pa)} />
        <text x="48" y="264">{minX.toPrecision(4)}</text>
        <text x="642" y="264">{maxX.toPrecision(4)}</text>
        <text x="4" y="236">{minY.toPrecision(4)}</text>
        <text x="4" y="26">{maxY.toPrecision(4)}</text>
        <text x="340" y="278">engineering strain (1)</text>
        <text x="14" y="144" transform="rotate(-90 14 144)">engineering stress (Pa)</text>
      </svg>
      <dl className="calibration-residual-summary">
        <div>
          <dt>Maximum residual (Pa)</dt>
          <dd>{Math.max(...preview.points.map((point) => Math.abs(point.residual_engineering_stress_pa))).toPrecision(6)}</dd>
        </div>
        <div>
          <dt>Maximum normalized residual</dt>
          <dd>{Math.max(...preview.points.map((point) => Math.abs(point.normalized_residual))).toPrecision(6)}</dd>
        </div>
      </dl>
    </section>
  );
}

interface ReferenceCalibrationWorkbenchProps {
  config: ApiConfig;
  state: MaterialStateResponse;
}

export function ReferenceCalibrationWorkbench({
  config,
  state,
}: ReferenceCalibrationWorkbenchProps) {
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState<MaterialModelResponse[]>([]);
  const [selections, setSelections] = useState<DatasetSelectionResponse[]>([]);
  const [selectedModelId, setSelectedModelId] = useState("");
  const [selectedSelectionId, setSelectedSelectionId] = useState("");
  const [plan, setPlan] = useState<CalibrationPlanResponse | null>(null);
  const [run, setRun] = useState<CalibrationRunResponse | null>(null);
  const [candidateSelection, setCandidateSelection] = useState<CalibrationCandidateSelectionResponse | null>(null);
  const [promotedModel, setPromotedModel] = useState<MaterialModelResponse | null>(null);
  const [diagnostics, setDiagnostics] = useState<CalibrationDiagnosticPreview | null>(null);
  const [planLabel, setPlanLabel] = useState("Reference linear elastic calibration");
  const [lowerBound, setLowerBound] = useState("1000000000");
  const [initialValue, setInitialValue] = useState("210000000000");
  const [upperBound, setUpperBound] = useState("500000000000");
  const [normalizationScale, setNormalizationScale] = useState("1000000");
  const [multistartCount, setMultistartCount] = useState("3");
  const [randomSeed, setRandomSeed] = useState("20260719");
  const [planReason, setPlanReason] = useState("Pin reference tensile curve and model revisions for calibration");
  const [runReason, setRunReason] = useState("Execute deterministic reference linear elastic calibration");
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [candidateSelectionLabel, setCandidateSelectionLabel] = useState("Accepted reference elastic candidate");
  const [candidateSelectionReason, setCandidateSelectionReason] = useState("Human review accepts this converged candidate for a non-production reference IR");
  const [promotionReason, setPromotionReason] = useState("Promote the accepted reference calibration candidate into a new immutable IR revision");
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [modelResult, datasetResult] = await Promise.all([
        listMaterialModels(config, state.material_state_id),
        listDatasetsForMaterialState(config, state.material_state_id),
      ]);
      const selectionResults = await Promise.all(
        datasetResult.data.items.map((dataset) => (
          listDatasetRevisionSelections(config, dataset.current_revision.id)
        )),
      );
      const scopedSelections = new Map<string, DatasetSelectionResponse>();
      for (const result of selectionResults) {
        for (const selection of result.data.items) {
          if (selection.current_revision.classification === state.current_revision.classification) {
            scopedSelections.set(selection.selection_id, selection);
          }
        }
      }
      setModels(modelResult.data.items);
      setSelections([...scopedSelections.values()]);
      setSelectedModelId((current) => (
        modelResult.data.items.some((model) => model.material_model_id === current)
          ? current
          : modelResult.data.items[0]?.material_model_id ?? ""
      ));
      setSelectedSelectionId((current) => (
        scopedSelections.has(current) ? current : [...scopedSelections.keys()][0] ?? ""
      ));
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setLoading(false);
    }
  }, [config, state.material_state_id, state.current_revision.classification]);

  useEffect(() => {
    if (open) {
      void refresh();
    }
  }, [open, refresh]);

  const selectedModel = useMemo(
    () => models.find((model) => model.material_model_id === selectedModelId) ?? null,
    [models, selectedModelId],
  );
  const selectedSelection = useMemo(
    () => selections.find((selection) => selection.selection_id === selectedSelectionId) ?? null,
    [selections, selectedSelectionId],
  );
  const convergedCandidates = useMemo(
    () => run?.candidates.filter((candidate) => candidate.status === "converged") ?? [],
    [run],
  );
  const selectedCandidate = useMemo(
    () => convergedCandidates.find((candidate) => candidate.calibration_candidate_id === selectedCandidateId) ?? null,
    [convergedCandidates, selectedCandidateId],
  );

  async function submitPlan(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedModel || !selectedSelection) {
      return;
    }
    const lower = Number(lowerBound);
    const initial = Number(initialValue);
    const upper = Number(upperBound);
    const scale = Number(normalizationScale);
    const multistart = Number(multistartCount);
    const seed = Number(randomSeed);
    if (
      !Number.isFinite(lower)
      || !Number.isFinite(initial)
      || !Number.isFinite(upper)
      || !Number.isFinite(scale)
      || lower <= 0
      || lower >= upper
      || initial < lower
      || initial > upper
      || scale <= 0
      || !Number.isInteger(multistart)
      || multistart < 1
      || multistart > 16
      || !Number.isSafeInteger(seed)
    ) {
      setError("Use finite, ordered SI Young's modulus bounds, a positive normalization scale, 1–16 starts, and an integer seed.");
      return;
    }
    setAction("plan");
    setError(null);
    try {
      const result = await createReferenceLinearElasticCalibrationPlan(config, {
        classification: state.current_revision.classification,
        plan_label: planLabel.trim(),
        selection_id: selectedSelection.selection_id,
        selection_revision_id: selectedSelection.current_revision.id,
        material_model_id: selectedModel.material_model_id,
        material_model_revision_id: selectedModel.current_revision.id,
        youngs_modulus_lower_bound_pa: lower,
        youngs_modulus_initial_value_pa: initial,
        youngs_modulus_upper_bound_pa: upper,
        normalization_stress_scale_pa: scale,
        multistart_count: multistart,
        random_seed: seed,
        change_reason: planReason.trim(),
      });
      setPlan(result.data);
      setRun(null);
      setDiagnostics(null);
      setCandidateSelection(null);
      setPromotedModel(null);
      setSelectedCandidateId("");
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function executePlan(): Promise<void> {
    if (!plan) {
      return;
    }
    setAction("run");
    setError(null);
    try {
      const result = await executeReferenceLinearElasticCalibration(config, {
        plan_id: plan.calibration_plan_id,
        plan_revision_id: plan.current_revision.id,
        change_reason: runReason.trim(),
      });
      setRun(result.data);
      setCandidateSelection(null);
      setPromotedModel(null);
      const candidate = result.data.candidates.find((item) => item.status === "converged");
      setSelectedCandidateId(candidate?.calibration_candidate_id ?? "");
      if (candidate) {
        const preview = await previewCalibrationCandidateDiagnostics(
          config,
          candidate.calibration_candidate_id,
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

  async function recordCandidateSelection(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!run || !selectedCandidate) {
      setError("Select one numerically converged Candidate before recording human acceptance.");
      return;
    }
    setAction("selection");
    setError(null);
    try {
      const result = await createReferenceCalibrationCandidateSelection(config, {
        classification: run.classification,
        selection_label: candidateSelectionLabel.trim(),
        calibration_run_id: run.calibration_run_id,
        calibration_candidate_id: selectedCandidate.calibration_candidate_id,
        selection_reason: candidateSelectionReason.trim(),
      });
      setCandidateSelection(result.data);
      setPromotedModel(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function promoteSelection(): Promise<void> {
    if (!run || !candidateSelection) {
      return;
    }
    setAction("promotion");
    setError(null);
    try {
      const result = await promoteSelectedReferenceCalibrationCandidate(
        config,
        candidateSelection.calibration_candidate_selection_id,
        {
          selection_revision_id: candidateSelection.current_revision.id,
          expected_material_model_revision_id: run.material_model_revision_id,
          change_reason: promotionReason.trim(),
        },
      );
      setPromotedModel(result.data.material_model);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  return (
    <section className="reference-calibration-workbench" aria-label="Reference calibration workbench">
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">Modeling workflow</p>
          <h4>Reference tensile calibration</h4>
        </div>
        <span className="reference-chip">Non-production</span>
      </div>
      <p className="form-hint">
        Pin one immutable normalized or processed tensile Selection and one reference linear-elastic
        IR revision. This deterministic closed-form slope fit is a workflow reference, not a
        validated material model or a production optimizer.
      </p>
      <button className="text-button workflow-toggle" type="button" onClick={() => setOpen((current) => !current)}>
        {open ? "Close calibration workbench" : "Open calibration workbench"}
      </button>
      {!open ? null : (
        <div className="workflow-stack calibration-workbench-stack">
          <div className="workflow-toolbar">
            <span>{loading ? "Loading pinned inputs…" : "Every plan and run records immutable input revisions."}</span>
            <button className="text-button" type="button" onClick={() => void refresh()} disabled={loading}>
              Refresh
            </button>
          </div>
          {error ? <p className="error-notice" role="alert">{error}</p> : null}
          {!loading && (!models.length || !selections.length) ? (
            <p className="muted">
              Create a reference Material Model IR and a normalized or processed Dataset Selection
              for this Material State before calibrating.
            </p>
          ) : null}
          {models.length && selections.length ? (
            <form className="workflow-step form-stack" onSubmit={(event) => void submitPlan(event)}>
              <strong>1. Pin Calibration Plan inputs and numerical conventions</strong>
              <div className="form-grid">
                <label>
                  Dataset Selection revision
                  <select value={selectedSelectionId} onChange={(event) => setSelectedSelectionId(event.target.value)}>
                    {selections.map((selection) => (
                      <option key={selection.selection_id} value={selection.selection_id}>
                        {selection.selection_label} · r{selection.current_revision.revision_no} · {shortId(selection.current_revision.content.dataset_revision_id)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Material Model IR revision
                  <select value={selectedModelId} onChange={(event) => setSelectedModelId(event.target.value)}>
                    {models.map((model) => (
                      <option key={model.material_model_id} value={model.material_model_id}>
                        r{model.current_revision.revision_no} · {shortId(model.current_revision.id)} · reference linear elasticity
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label>
                Calibration Plan label
                <input value={planLabel} onChange={(event) => setPlanLabel(event.target.value)} required />
              </label>
              <div className="form-grid calibration-parameter-grid">
                <label>
                  E lower bound (Pa)
                  <input aria-label="E lower bound (Pa)" type="number" min="0" step="any" value={lowerBound} onChange={(event) => setLowerBound(event.target.value)} required />
                </label>
                <label>
                  E initial value (Pa)
                  <input aria-label="E initial value (Pa)" type="number" min="0" step="any" value={initialValue} onChange={(event) => setInitialValue(event.target.value)} required />
                </label>
                <label>
                  E upper bound (Pa)
                  <input aria-label="E upper bound (Pa)" type="number" min="0" step="any" value={upperBound} onChange={(event) => setUpperBound(event.target.value)} required />
                </label>
                <label>
                  Stress normalization scale (Pa)
                  <input aria-label="Stress normalization scale (Pa)" type="number" min="0" step="any" value={normalizationScale} onChange={(event) => setNormalizationScale(event.target.value)} required />
                </label>
                <label>
                  Multistart count
                  <input aria-label="Multistart count" type="number" min="1" max="16" step="1" value={multistartCount} onChange={(event) => setMultistartCount(event.target.value)} required />
                </label>
                <label>
                  Random seed
                  <input aria-label="Random seed" type="number" step="1" value={randomSeed} onChange={(event) => setRandomSeed(event.target.value)} required />
                </label>
              </div>
              <p className="source-line">
                Objective: uniform point weight · mean normalized squared residual · all observed
                points · missing data rejected.
              </p>
              <label>
                Change reason
                <input value={planReason} onChange={(event) => setPlanReason(event.target.value)} required />
              </label>
              <button className="button secondary" type="submit" disabled={action !== null}>
                {action === "plan" ? "Pinning Calibration Plan…" : "Create immutable Calibration Plan"}
              </button>
            </form>
          ) : null}
          {plan ? (
            <div className="workflow-step calibration-plan-result">
              <strong>2. Execute the fixed reference plan</strong>
              <p className="source-line">
                Plan {shortId(plan.calibration_plan_id)} · r{plan.current_revision.revision_no} ·
                evaluator: closed-form curve · calibration is non-production.
              </p>
              <label>
                Run change reason
                <input value={runReason} onChange={(event) => setRunReason(event.target.value)} required />
              </label>
              <button className="button primary" type="button" onClick={() => void executePlan()} disabled={action !== null}>
                {action === "run" ? "Running reference calibration…" : "Execute Calibration Run"}
              </button>
            </div>
          ) : null}
          {run ? (
            <div className="statistics-result calibration-run-result" aria-live="polite">
              <div className="workflow-toolbar">
                <span>
                  Calibration Run {shortId(run.calibration_run_id)} · {run.status} · {run.candidate_count} candidate{run.candidate_count === 1 ? "" : "s"}
                </span>
                <span className="reference-chip">R{run.reproducibility_level.slice(1)}</span>
              </div>
              {run.failure_code ? <p className="error-notice">Failure: {run.failure_code}</p> : null}
              {selectedCandidate ? (
                <>
                  <dl className="statistics-definition-list calibration-candidate-summary">
                    <div><dt>Young&apos;s modulus (Pa)</dt><dd>{selectedCandidate.youngs_modulus_pa.toPrecision(8)}</dd></div>
                    <div><dt>Objective</dt><dd>{selectedCandidate.objective_total.toPrecision(6)}</dd></div>
                    <div><dt>Residual RMS (Pa)</dt><dd>{selectedCandidate.residual_root_mean_square_pa.toPrecision(6)}</dd></div>
                    <div><dt>Bound sticking</dt><dd>{selectedCandidate.bound_sticking ? "yes — review required" : "no"}</dd></div>
                    <div><dt>Identifiability</dt><dd>{selectedCandidate.identifiability_status.replaceAll("_", " ")}</dd></div>
                    <div><dt>Uncertainty</dt><dd>{selectedCandidate.uncertainty_status.replaceAll("_", " ")}</dd></div>
                  </dl>
                  <p className="source-line">
                    Candidate {shortId(selectedCandidate.calibration_candidate_id)} · {selectedCandidate.status} · diagnostics SHA-256 {shortId(selectedCandidate.diagnostics_sha256)} · {selectedCandidate.convergence_reason.replaceAll("_", " ")}.
                  </p>
                  {diagnostics ? <CalibrationCurvePanel preview={diagnostics} /> : null}
                  <form className="workflow-step form-stack" onSubmit={(event) => void recordCandidateSelection(event)}>
                    <strong>3. Record explicit human Candidate acceptance</strong>
                    <p className="form-hint">
                      Numerical convergence is not a release or approval decision. Record a human
                      reason against one converged Candidate; this creates an immutable, non-production
                      Selection revision and does not modify the Run or Candidate.
                    </p>
                    <label>
                      Converged Candidate
                      <select
                        aria-label="Converged Candidate"
                        value={selectedCandidateId}
                        onChange={(event) => {
                          setSelectedCandidateId(event.target.value);
                          setCandidateSelection(null);
                          setPromotedModel(null);
                        }}
                      >
                        {convergedCandidates.map((candidate) => (
                          <option key={candidate.calibration_candidate_id} value={candidate.calibration_candidate_id}>
                            {shortId(candidate.calibration_candidate_id)} · E {candidate.youngs_modulus_pa.toPrecision(8)} Pa · objective {candidate.objective_total.toPrecision(6)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Candidate Selection label
                      <input
                        value={candidateSelectionLabel}
                        onChange={(event) => setCandidateSelectionLabel(event.target.value)}
                        required
                      />
                    </label>
                    <label>
                      Human acceptance reason
                      <input
                        value={candidateSelectionReason}
                        onChange={(event) => setCandidateSelectionReason(event.target.value)}
                        required
                      />
                    </label>
                    <button className="button secondary" type="submit" disabled={action !== null}>
                      {action === "selection" ? "Recording human acceptance…" : "Record human Candidate acceptance"}
                    </button>
                  </form>
                  {candidateSelection ? (
                    <div className="workflow-step calibration-plan-result">
                      <strong>4. Promote the accepted Candidate into a new IR revision</strong>
                      <p className="source-line">
                        Human acceptance recorded as Selection r{candidateSelection.current_revision.revision_no} · {candidateSelection.current_revision.content.domain_acceptance_status.replaceAll("_", " ")}.
                      </p>
                      <p className="form-hint">
                        Promotion requires this Selection revision and the exact Material Model IR
                        revision evaluated by the Calibration Run to still be current. It appends a
                        new IR revision; it never overwrites the source revision.
                      </p>
                      <label>
                        IR promotion reason
                        <input
                          value={promotionReason}
                          onChange={(event) => setPromotionReason(event.target.value)}
                          required
                        />
                      </label>
                      <button className="button primary" type="button" onClick={() => void promoteSelection()} disabled={action !== null}>
                        {action === "promotion" ? "Promoting immutable IR…" : "Promote accepted Candidate to new IR revision"}
                      </button>
                      {promotedModel ? (
                        <p className="success-notice">
                          Promoted Material Model IR r{promotedModel.current_revision.revision_no} · E {promotedModel.current_revision.content.youngs_modulus_pa.toPrecision(8)} Pa. The new revision is linked to the Selection, Candidate, Run, and diagnostics artifact.
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </>
              ) : run.status === "succeeded" ? (
                <p className="muted">No numerically converged Candidate is available for human selection.</p>
              ) : null}
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
