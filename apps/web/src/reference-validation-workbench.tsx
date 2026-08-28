import { type FormEvent, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  type ApiConfig,
} from "./shared/api";
import {
  attachManualValidationResult,
  cancelValidationRun,
  createReferenceValidationPlan,
  createReferenceValidationTemplate,
  evaluateReferenceValidationRun,
  listMaterialModels,
  listSolverCards,
  listValidationPlans,
  listValidationTemplates,
  pollReferenceValidationRun,
  previewReferenceValidationResultCurve,
  submitReferenceValidationRun,
} from "./features/modeling";
import {
  listDatasetRevisionSelections,
  listDatasetsForMaterialState,
} from "./features/test-data";
import type {
  DatasetSelectionResponse,
  MaterialModelResponse,
  MaterialStateResponse,
  ReferenceRunnerOutcome,
  SolverCardResponse,
  ValidationExecutionMode,
  ValidationPlanResponse,
  ValidationResultCurveResponse,
  ValidationRunResponse,
  ValidationTemplateResponse,
} from "./types";
import "./features/modeling/ui/modeling-calibration-workbenches.css";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "The reference validation workbench could not reach the protected API. Try again.";
}

function shortId(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function defaultNativeResult(): string {
  return JSON.stringify(
    {
      schema_id: "urn:cmp:validation:reference-native-result:1.0.0",
      schema_version: "1.0.0",
      source: "manual_reference_attachment",
      non_production: true,
      target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" },
      solver_termination: "normal",
      channel_units: { engineering_strain: "1", engineering_stress_pa: "Pa" },
      points: [
        { engineering_strain: 0, engineering_stress_pa: 0 },
        { engineering_strain: 0.01, engineering_stress_pa: 2100000000 },
        { engineering_strain: 0.02, engineering_stress_pa: 4200000000 },
      ],
    },
    null,
    2,
  );
}

function ArtifactEvidence({ label, artifact }: { label: string; artifact: { artifact_id: string; sha256: string } | null }) {
  if (!artifact) {
    return <li><strong>{label}</strong><span>not available</span></li>;
  }
  return <li><strong>{label}</strong><span>{shortId(artifact.artifact_id)} · {shortId(artifact.sha256)}</span></li>;
}

function formatScientific(value: number | null, digits = 3): string {
  return value === null ? "not evaluated" : value.toExponential(digits);
}

function ReferenceValidationCurve({ curve }: { curve: ValidationResultCurveResponse }) {
  const points = curve.comparison_points;
  if (points.length < 2) {
    return <p className="muted">No aligned observed-grid curve is available for this result.</p>;
  }
  const width = 560;
  const height = 250;
  const padding = 28;
  const maximumStrain = Math.max(...points.map((point) => point.engineering_strain), 1e-12);
  const maximumStress = Math.max(
    ...points.flatMap((point) => [
      point.observed_engineering_stress_pa,
      point.simulated_engineering_stress_pa,
    ]),
    1,
  );
  const coordinate = (strain: number, stress: number): string => {
    const x = padding + (strain / maximumStrain) * (width - padding * 2);
    const y = height - padding - (stress / maximumStress) * (height - padding * 2);
    return `${x},${y}`;
  };
  const observed = points
    .map((point) => coordinate(point.engineering_strain, point.observed_engineering_stress_pa))
    .join(" ");
  const simulated = points
    .map((point) => coordinate(point.engineering_strain, point.simulated_engineering_stress_pa))
    .join(" ");

  return (
    <figure className="validation-curve-preview">
      <svg
        aria-label="Observed and reference simulated engineering stress-strain curves"
        role="img"
        viewBox={`0 0 ${width} ${height}`}
      >
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} />
        <polyline className="validation-observed-curve" points={observed} fill="none" />
        <polyline className="validation-simulated-curve" points={simulated} fill="none" />
      </svg>
      <figcaption>
        <span className="curve-legend observed">Observed experimental selection</span>
        <span className="curve-legend simulated">Reference simulated response</span>
        <span className="muted">
          {curve.returned_comparison_point_count}/{curve.comparison_point_count} observed-grid points
          {curve.comparison_sampled ? " (sampled)" : ""}
        </span>
      </figcaption>
    </figure>
  );
}

export function ReferenceValidationWorkbench({
  config,
  state,
}: {
  config: ApiConfig;
  state: MaterialStateResponse;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [action, setAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<ValidationTemplateResponse[]>([]);
  const [plans, setPlans] = useState<ValidationPlanResponse[]>([]);
  const [models, setModels] = useState<MaterialModelResponse[]>([]);
  const [cards, setCards] = useState<SolverCardResponse[]>([]);
  const [selections, setSelections] = useState<DatasetSelectionResponse[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [selectedModelId, setSelectedModelId] = useState("");
  const [selectedCardId, setSelectedCardId] = useState("");
  const [selectedSelectionId, setSelectedSelectionId] = useState("");
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [run, setRun] = useState<ValidationRunResponse | null>(null);
  const [executionMode, setExecutionMode] = useState<ValidationExecutionMode>("reference_inline_mock");
  const [outcome, setOutcome] = useState<ReferenceRunnerOutcome>("succeeded");
  const [externalJobReference, setExternalJobReference] = useState("external/reference-job-001");
  const [templateLabel, setTemplateLabel] = useState("Reference tensile virtual specimen");
  const [gaugeLength, setGaugeLength] = useState("0.05");
  const [crossSectionArea, setCrossSectionArea] = useState("0.00001");
  const [elementCount, setElementCount] = useState("10");
  const [displacement, setDisplacement] = useState("0.001");
  const [sampleCount, setSampleCount] = useState("3");
  const [templateReason, setTemplateReason] = useState("Create non-production reference virtual specimen template");
  const [planLabel, setPlanLabel] = useState("Reference tensile validation");
  const [planReason, setPlanReason] = useState("Pin Material Model, Solver Card, Template, and experimental selection");
  const [runReason, setRunReason] = useState("Submit non-production reference validation run");
  const [nativeResultText, setNativeResultText] = useState(defaultNativeResult);
  const [stdoutText, setStdoutText] = useState("Manual reference execution completed.");
  const [stderrText, setStderrText] = useState("No stderr captured.");
  const [attachReason, setAttachReason] = useState("Attach bounded manual reference result evidence");
  const [validationCurve, setValidationCurve] = useState<ValidationResultCurveResponse | null>(null);

  const selectedTemplate = templates.find((item) => item.validation_template_id === selectedTemplateId) ?? null;
  const selectedModel = models.find((item) => item.material_model_id === selectedModelId) ?? null;
  const compatibleCards = useMemo(
    () => cards.filter((item) => item.material_model_id === selectedModelId),
    [cards, selectedModelId],
  );
  const selectedCard = compatibleCards.find((item) => item.solver_card_id === selectedCardId) ?? null;
  const selectedSelection = selections.find((item) => item.selection_id === selectedSelectionId) ?? null;
  const selectedPlan = plans.find((item) => item.validation_plan_id === selectedPlanId) ?? null;

  useEffect(() => {
    if (!open) {
      return;
    }
    let current = true;
    setLoading(true);
    setError(null);
    void (async () => {
      try {
        const [templateResult, planResult, modelResult, datasetResult] = await Promise.all([
          listValidationTemplates(config),
          listValidationPlans(config),
          listMaterialModels(config, state.material_state_id),
          listDatasetsForMaterialState(config, state.material_state_id),
        ]);
        const [cardResults, selectionResults] = await Promise.all([
          Promise.all(modelResult.data.items.map((model) => listSolverCards(config, model.material_model_id))),
          Promise.all(datasetResult.data.items.map((dataset) => (
            listDatasetRevisionSelections(config, dataset.current_revision.id)
          ))),
        ]);
        if (!current) {
          return;
        }
        const loadedCards = cardResults.flatMap((result) => result.data.items);
        const loadedSelections = selectionResults.flatMap((result) => result.data.items);
        setTemplates(templateResult.data.items);
        setPlans(planResult.data.items);
        setModels(modelResult.data.items);
        setCards(loadedCards);
        setSelections(loadedSelections);
        setSelectedTemplateId((value) => value || templateResult.data.items[0]?.validation_template_id || "");
        setSelectedModelId((value) => value || modelResult.data.items[0]?.material_model_id || "");
        setSelectedSelectionId((value) => value || loadedSelections[0]?.selection_id || "");
        setSelectedPlanId((value) => value || planResult.data.items[0]?.validation_plan_id || "");
        const firstModel = modelResult.data.items[0]?.material_model_id;
        setSelectedCardId((value) => value || loadedCards.find((card) => card.material_model_id === firstModel)?.solver_card_id || "");
      } catch (cause) {
        if (current) {
          setError(messageFor(cause));
        }
      } finally {
        if (current) {
          setLoading(false);
        }
      }
    })();
    return () => {
      current = false;
    };
  }, [config, open, state.material_state_id]);

  useEffect(() => {
    if (!selectedModelId) {
      return;
    }
    setSelectedCardId((value) => (
      compatibleCards.some((card) => card.solver_card_id === value)
        ? value
        : compatibleCards[0]?.solver_card_id || ""
    ));
  }, [compatibleCards, selectedModelId]);

  async function createTemplate(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setAction("template");
    setError(null);
    try {
      const result = await createReferenceValidationTemplate(config, {
        classification: state.current_revision.classification,
        content: {
          template_label: templateLabel.trim(),
          gauge_length_m: Number(gaugeLength),
          cross_section_area_m2: Number(crossSectionArea),
          axial_element_count: Number(elementCount),
          axial_displacement_end_m: Number(displacement),
          output_sample_count: Number(sampleCount),
        },
        change_reason: templateReason.trim(),
      });
      setTemplates((items) => [result.data, ...items]);
      setSelectedTemplateId(result.data.validation_template_id);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function createPlan(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedTemplate || !selectedModel || !selectedCard || !selectedSelection) {
      setError("Create or select a Template, Material Model IR, compatible Solver Card, and experimental Dataset Selection first.");
      return;
    }
    setAction("plan");
    setError(null);
    try {
      const result = await createReferenceValidationPlan(config, {
        classification: state.current_revision.classification,
        content: {
          plan_label: planLabel.trim(),
          validation_template_id: selectedTemplate.validation_template_id,
          validation_template_revision_id: selectedTemplate.current_revision.id,
          material_model_id: selectedModel.material_model_id,
          material_model_revision_id: selectedModel.current_revision.id,
          solver_card_id: selectedCard.solver_card_id,
          solver_card_revision_id: selectedCard.current_revision.id,
          experimental_selection_id: selectedSelection.selection_id,
          experimental_selection_revision_id: selectedSelection.current_revision.id,
        },
        change_reason: planReason.trim(),
      });
      setPlans((items) => [result.data, ...items]);
      setSelectedPlanId(result.data.validation_plan_id);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function submitRun(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedPlan) {
      setError("Create or select an immutable Validation Plan first.");
      return;
    }
    setAction("submit");
    setError(null);
    try {
      const result = await submitReferenceValidationRun(config, {
        validation_plan_id: selectedPlan.validation_plan_id,
        validation_plan_revision_id: selectedPlan.current_revision.id,
        execution_mode: executionMode,
        ...(executionMode === "manual_attach" ? { external_job_reference: externalJobReference.trim() } : {}),
        change_reason: runReason.trim(),
      });
      setRun(result.data);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function pollRun(): Promise<void> {
    if (!run) {
      return;
    }
    setAction("poll");
    setError(null);
    try {
      const result = await pollReferenceValidationRun(config, run.validation_run_id, {
        outcome,
        change_reason: `Collect explicit non-production mock outcome: ${outcome}`,
      });
      setRun(result.data);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function attachResult(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!run) {
      return;
    }
    setAction("attach");
    setError(null);
    try {
      const result = await attachManualValidationResult(config, run.validation_run_id, {
        stdout_text: stdoutText,
        stderr_text: stderrText,
        native_result_text: nativeResultText,
        change_reason: attachReason.trim(),
      });
      setRun(result.data);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function evaluateRun(): Promise<void> {
    if (!run || !run.result_manifest) {
      return;
    }
    setAction("evaluate");
    setError(null);
    setValidationCurve(null);
    try {
      const result = await evaluateReferenceValidationRun(config, run.validation_run_id, {
        change_reason: "Extract reference response, assess numerical health, and compare evidence",
      });
      setRun(result.data);
      const validationResult = result.data.validation_result;
      if (validationResult?.response_extraction.normalized_response) {
        const curve = await previewReferenceValidationResultCurve(
          config,
          validationResult.validation_result_id,
        );
        setValidationCurve(curve.data);
      }
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  async function cancelRun(): Promise<void> {
    if (!run) {
      return;
    }
    setAction("cancel");
    setError(null);
    try {
      const result = await cancelValidationRun(config, run.validation_run_id, {
        change_reason: "Cancel nonterminal reference validation run",
      });
      setRun(result.data);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setAction(null);
    }
  }

  return (
    <section className="reference-validation-workbench" aria-label="Reference validation workbench">
      <div className="section-heading compact-heading">
        <div>
          <p className="eyebrow">Validation boundary</p>
          <h4>Reference virtual specimen runner</h4>
        </div>
        <span className="reference-chip">Non-production only</span>
      </div>
      <p className="form-hint">
        This records a frozen 1D tensile Template, Material Model IR, Solver Card, and experiment selection.
        It uses an inline mock or manual evidence attachment only; extraction and comparison produce
        non-production reference evidence, not a production solver or material qualification.
      </p>
      <button className="button secondary" type="button" onClick={() => setOpen((value) => !value)}>
        {open ? "Close validation workbench" : "Open validation workbench"}
      </button>
      {open ? (
        <div className="workflow-stack validation-workbench-stack">
          {loading ? <p className="muted">Loading immutable Template, Plan, IR, Card, and Selection heads…</p> : null}
          {error ? <p className="error-notice" role="alert">{error}</p> : null}
          <form className="workflow-step" onSubmit={createTemplate}>
            <strong>1. Create a reference virtual-specimen Template</strong>
            <small>OpenRadioss 2025 / kg-m-s is pinned for this narrow reference contract.</small>
            <div className="form-grid validation-template-grid">
              <label>Template label<input value={templateLabel} onChange={(event) => setTemplateLabel(event.target.value)} required /></label>
              <label>Gauge length (m)<input type="number" min="0" step="any" value={gaugeLength} onChange={(event) => setGaugeLength(event.target.value)} required /></label>
              <label>Cross-section area (m²)<input type="number" min="0" step="any" value={crossSectionArea} onChange={(event) => setCrossSectionArea(event.target.value)} required /></label>
              <label>Axial elements<input type="number" min="1" max="10000" value={elementCount} onChange={(event) => setElementCount(event.target.value)} required /></label>
              <label>End displacement (m)<input type="number" min="0" step="any" value={displacement} onChange={(event) => setDisplacement(event.target.value)} required /></label>
              <label>Output samples<input type="number" min="2" max="10000" value={sampleCount} onChange={(event) => setSampleCount(event.target.value)} required /></label>
            </div>
            <label>Change reason<input value={templateReason} onChange={(event) => setTemplateReason(event.target.value)} required /></label>
            <button className="button primary" type="submit" disabled={action !== null}>
              {action === "template" ? "Creating Template…" : "Create immutable Template"}
            </button>
          </form>

          <form className="workflow-step" onSubmit={createPlan}>
            <strong>2. Pin the validation Plan inputs</strong>
            <small>Each reference pins an exact revision; the workspace verifies compatible access, target, and Material State.</small>
            <div className="form-grid">
              <label>Virtual-specimen Template
                <select value={selectedTemplateId} onChange={(event) => setSelectedTemplateId(event.target.value)} required>
                  <option value="">Select Template</option>
                  {templates.map((item) => <option key={item.validation_template_id} value={item.validation_template_id}>{item.current_revision.content.template_label} · r{item.current_revision.revision_no}</option>)}
                </select>
              </label>
              <label>Material Model IR
                <select value={selectedModelId} onChange={(event) => setSelectedModelId(event.target.value)} required>
                  <option value="">Select IR</option>
                  {models.map((item) => <option key={item.material_model_id} value={item.material_model_id}>{shortId(item.material_model_id)} · r{item.current_revision.revision_no}</option>)}
                </select>
              </label>
              <label>Compatible Solver Card
                <select value={selectedCardId} onChange={(event) => setSelectedCardId(event.target.value)} required>
                  <option value="">Select Solver Card</option>
                  {compatibleCards.map((item) => <option key={item.solver_card_id} value={item.solver_card_id}>/MAT/ELAST/{item.solver_material_id} · r{item.current_revision.revision_no}</option>)}
                </select>
              </label>
              <label>Experimental Dataset Selection
                <select value={selectedSelectionId} onChange={(event) => setSelectedSelectionId(event.target.value)} required>
                  <option value="">Select experiment</option>
                  {selections.map((item) => <option key={item.selection_id} value={item.selection_id}>{item.selection_label} · r{item.current_revision.revision_no}</option>)}
                </select>
              </label>
            </div>
            <label>Plan label<input value={planLabel} onChange={(event) => setPlanLabel(event.target.value)} required /></label>
            <label>Change reason<input value={planReason} onChange={(event) => setPlanReason(event.target.value)} required /></label>
            <button className="button primary" type="submit" disabled={action !== null}>
              {action === "plan" ? "Creating Plan…" : "Create immutable Validation Plan"}
            </button>
            {selectedPlan ? <small className="source-line">Selected Plan {shortId(selectedPlan.validation_plan_id)} · r{selectedPlan.current_revision.revision_no}</small> : null}
          </form>

          <form className="workflow-step" onSubmit={submitRun}>
            <strong>3. Submit a bounded reference run</strong>
            <div className="form-grid">
              <label>Validation Plan
                <select value={selectedPlanId} onChange={(event) => setSelectedPlanId(event.target.value)} required>
                  <option value="">Select Validation Plan</option>
                  {plans.map((item) => <option key={item.validation_plan_id} value={item.validation_plan_id}>{item.current_revision.content.plan_label} · r{item.current_revision.revision_no}</option>)}
                </select>
              </label>
              <label>Execution evidence mode
                <select value={executionMode} onChange={(event) => setExecutionMode(event.target.value as ValidationExecutionMode)}>
                  <option value="reference_inline_mock">Reference inline mock</option>
                  <option value="manual_attach">Manual result attachment</option>
                </select>
              </label>
              {executionMode === "manual_attach" ? <label>Opaque external job reference<input value={externalJobReference} onChange={(event) => setExternalJobReference(event.target.value)} required /></label> : null}
            </div>
            <label>Change reason<input value={runReason} onChange={(event) => setRunReason(event.target.value)} required /></label>
            <button className="button primary" type="submit" disabled={action !== null}>
              {action === "submit" ? "Submitting…" : "Submit Validation Run"}
            </button>
          </form>

          {run ? (
            <section className="statistics-result validation-run-result" aria-live="polite">
              <div className="section-heading compact-heading">
                <div>
                  <p className="eyebrow">Run evidence</p>
                  <h5>Validation Run {shortId(run.validation_run_id)} · {run.status.replaceAll("_", " ")}</h5>
                </div>
                <span className="reference-chip">
                  {run.validation_result
                    ? `Reference ${run.validation_result.verdict.replaceAll("_", " ")}`
                    : "Awaiting result interpretation"}
                </span>
              </div>
              <p className="source-line">Deck {shortId(run.deck.artifact_id)} · frozen Plan r{selectedPlan?.current_revision.revision_no ?? "?"} · runner {run.runner_version}</p>
              {run.status === "queued" ? (
                <div className="workflow-step inline-action">
                  <label>Explicit mock outcome
                    <select value={outcome} onChange={(event) => setOutcome(event.target.value as ReferenceRunnerOutcome)}>
                      <option value="succeeded">Succeeded</option>
                      <option value="license_unavailable">License unavailable</option>
                      <option value="queue_timeout">Queue timeout</option>
                      <option value="solver_failed">Solver failed</option>
                    </select>
                  </label>
                  <button className="button secondary" type="button" onClick={() => void pollRun()} disabled={action !== null}>
                    {action === "poll" ? "Collecting…" : "Collect mock outcome"}
                  </button>
                  <button className="text-button" type="button" onClick={() => void cancelRun()} disabled={action !== null}>Cancel run</button>
                </div>
              ) : null}
              {run.status === "waiting_manual" ? (
                <form className="form-stack manual-result-form" onSubmit={attachResult}>
                  <p>Attach bounded JSON native output and captured logs. The platform records evidence only; it does not infer a verdict here.</p>
                  <label>stdout<textarea value={stdoutText} onChange={(event) => setStdoutText(event.target.value)} rows={3} required /></label>
                  <label>stderr<textarea value={stderrText} onChange={(event) => setStderrText(event.target.value)} rows={3} required /></label>
                  <label>Reference native result JSON<textarea value={nativeResultText} onChange={(event) => setNativeResultText(event.target.value)} rows={12} required /></label>
                  <label>Change reason<input value={attachReason} onChange={(event) => setAttachReason(event.target.value)} required /></label>
                  <div className="form-actions">
                    <button className="button primary" type="submit" disabled={action !== null}>{action === "attach" ? "Attaching…" : "Attach immutable result evidence"}</button>
                    <button className="text-button" type="button" onClick={() => void cancelRun()} disabled={action !== null}>Cancel run</button>
                  </div>
                </form>
              ) : null}
              {run.result_manifest ? (
                <>
                  <p className="source-line">Termination: {run.result_manifest.solver_termination} · native result: {run.result_manifest.native_result_state} · manifest SHA-256 {shortId(run.result_manifest.manifest_sha256)}</p>
                  <ul className="validation-evidence-list">
                    <ArtifactEvidence label="Deck" artifact={run.result_manifest.deck} />
                    <ArtifactEvidence label="stdout" artifact={run.result_manifest.stdout} />
                    <ArtifactEvidence label="stderr" artifact={run.result_manifest.stderr} />
                    <ArtifactEvidence label="Native result" artifact={run.result_manifest.native_result} />
                    <ArtifactEvidence label="Result manifest" artifact={run.result_manifest.manifest_artifact} />
                  </ul>
                </>
              ) : null}
              {run.result_manifest && !run.validation_result ? (
                <div className="workflow-step inline-action">
                  <p>
                    Extract the typed SI response, assess numerical health, and compare only at the
                    observed experimental strain grid. This remains reference evidence, not a
                    production validation claim.
                  </p>
                  <button
                    className="button primary"
                    type="button"
                    onClick={() => void evaluateRun()}
                    disabled={action !== null}
                  >
                    {action === "evaluate"
                      ? "Interpreting reference result…"
                      : "Extract response and evaluate"}
                  </button>
                </div>
              ) : null}
              {run.validation_result ? (
                <section className="workflow-step validation-interpretation-result">
                  <div className="section-heading compact-heading">
                    <div>
                      <p className="eyebrow">Reference result interpretation</p>
                      <h5>{run.validation_result.verdict.replaceAll("_", " ")}</h5>
                    </div>
                    <span className="reference-chip">
                      numerical health: {run.validation_result.numerical_health_report.status}
                    </span>
                  </div>
                  <p className="source-line">
                    Holdout: {run.validation_result.holdout_independence.replaceAll("_", " ")}
                    {run.validation_result.reason_code
                      ? ` · reason: ${run.validation_result.reason_code.replaceAll("_", " ")}`
                      : ""}
                  </p>
                  <dl className="metric-grid">
                    <div>
                      <dt>Relative RMSE</dt>
                      <dd>{formatScientific(run.validation_result.relative_root_mean_squared_error)}</dd>
                    </div>
                    <div>
                      <dt>Threshold</dt>
                      <dd>{run.validation_result.relative_rmse_threshold.toFixed(3)}</dd>
                    </div>
                    <div>
                      <dt>RMSE (Pa)</dt>
                      <dd>{formatScientific(run.validation_result.root_mean_squared_error_pa)}</dd>
                    </div>
                    <div>
                      <dt>Compared points</dt>
                      <dd>{run.validation_result.compared_point_count}</dd>
                    </div>
                  </dl>
                  <ul className="validation-evidence-list">
                    <ArtifactEvidence
                      label="Normalized response"
                      artifact={run.validation_result.response_extraction.normalized_response}
                    />
                    <ArtifactEvidence
                      label="Numerical health report"
                      artifact={run.validation_result.numerical_health_report.report_artifact}
                    />
                    <ArtifactEvidence label="Comparison result" artifact={run.validation_result.result_artifact} />
                  </ul>
                  {validationCurve ? <ReferenceValidationCurve curve={validationCurve} /> : null}
                  <p className="muted">
                    Explicit linear interpolation is limited to the observed experimental grid; no
                    extrapolation or silent approximation is allowed.
                  </p>
                </section>
              ) : null}
              {run.failure_code ? <p className="error-notice">Recorded run failure: {run.failure_code.replaceAll("_", " ")}</p> : null}
            </section>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
