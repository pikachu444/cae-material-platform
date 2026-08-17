import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  type ApiConfig,
  createReferenceValidationPlan,
  evaluateReferenceValidationRun,
  getReferenceValidationResult,
  listDatasetRevisionSelections,
  listDatasetsForMaterialState,
  listMaterialModels,
  listSolverCards,
  listValidationPlans,
  listValidationTemplates,
  pollReferenceValidationRun,
  submitReferenceValidationRun,
} from "./api";
import type {
  DatasetSelectionResponse,
  MaterialModelResponse,
  MaterialStateResponse,
  ReferenceValidationResultResponse,
  SolverCardResponse,
  ValidationPlanResponse,
  ValidationRunResponse,
  ValidationTemplateResponse,
} from "./types";
import type { ModelingMaterialFamily, ModelingSessionEvent, ModelingSessionSummary } from "./features/modeling";

type Props = {
  config: ApiConfig;
  materialState?: MaterialStateResponse;
  session: ModelingSessionSummary | null | undefined;
  family: ModelingMaterialFamily;
  onSessionChange?: (patch: Partial<Omit<ModelingSessionSummary, "version" | "updatedAt">>) => void;
  onSessionEvent?: (event: ModelingSessionEvent) => void;
  onNavigate: (path: string) => void;
};

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "The protected validation service could not be reached. Try again.";
}

function ref(id: string, revisionId: string, label: string, revisionNo: number) {
  return { id, revisionId, label, revisionNo };
}

function shortId(value: string): string {
  return value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value;
}

/**
 * Normal Modeling's deliberately narrow bridge to the existing non-production
 * validation API.  It never invents a model, solver card, dataset selection,
 * review-package digest, or release input.  The generic admin workbenches keep
 * their manual-ID interfaces for administration; this surface is session-bound.
 */
export function ModelingValidationStage({ config, materialState, session, family, onSessionChange, onSessionEvent, onNavigate }: Props) {
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<ValidationTemplateResponse[]>([]);
  const [plans, setPlans] = useState<ValidationPlanResponse[]>([]);
  const [models, setModels] = useState<MaterialModelResponse[]>([]);
  const [cards, setCards] = useState<SolverCardResponse[]>([]);
  const [selections, setSelections] = useState<DatasetSelectionResponse[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [modelId, setModelId] = useState("");
  const [cardId, setCardId] = useState("");
  const [selectionId, setSelectionId] = useState("");
  const [plan, setPlan] = useState<ValidationPlanResponse | null>(null);
  const [run, setRun] = useState<ValidationRunResponse | null>(null);
  const [persistedResult, setPersistedResult] = useState<ReferenceValidationResultResponse | null>(null);

  const selectedTemplate = templates.find((value) => value.validation_template_id === templateId) ?? null;
  const candidatePinned = Boolean(session?.selection && session?.processingOutput);
  const familySupported = family === "metal";
  const eligibleModels = useMemo(() => models.filter((value) => {
    const evidence = value.current_revision.content.calibration_evidence;
    return Boolean(
      session?.selection
      && evidence?.calibration_candidate_id === session.selection.id
      && value.current_revision.id === session.materialModelIr?.revisionId
      && value.material_model_id === session.materialModelIr?.id,
    );
  }), [models, session?.materialModelIr, session?.selection]);
  const selectedModel = eligibleModels.find((value) => value.material_model_id === modelId) ?? null;
  const eligibleCards = useMemo(() => cards.filter((value) => (
    value.material_model_id === session?.materialModelIr?.id
    && value.solver_card_id === session?.exportArtifact?.id
    && value.current_revision.id === session.exportArtifact.revisionId
  )), [cards, session?.exportArtifact, session?.materialModelIr]);
  const compatibleCards = useMemo(
    () => eligibleCards.filter((value) => value.material_model_id === modelId),
    [eligibleCards, modelId],
  );
  const selectedCard = compatibleCards.find((value) => (
    value.solver_card_id === cardId
    && value.solver_card_id === session?.exportArtifact?.id
    && value.current_revision.id === session.exportArtifact.revisionId
  )) ?? null;
  const selectedSelection = selections.find((value) => value.selection_id === selectionId) ?? null;
  const planCreationSupported = familySupported
    && eligibleModels.length > 0
    && eligibleCards.length > 0;
  const validationPathAvailable = planCreationSupported || Boolean(plan);
  const prerequisitesReady = Boolean(
    candidatePinned
    && planCreationSupported
    && selectedTemplate
    && selectedModel
    && selectedCard
    && selectedSelection,
  );

  async function load(): Promise<void> {
    if (!materialState) return;
    setLoading(true);
    setError(null);
    try {
      const [templateResult, planResult, modelResult, datasetResult, savedResult] = await Promise.all([
        listValidationTemplates(config),
        listValidationPlans(config),
        listMaterialModels(config, materialState.material_state_id),
        listDatasetsForMaterialState(config, materialState.material_state_id),
        session?.validation
          ? getReferenceValidationResult(config, session.validation.id)
          : Promise.resolve(null),
      ]);
      const [cardResults, selectionResults] = await Promise.all([
        Promise.all(modelResult.data.items.map((model) => listSolverCards(config, model.material_model_id))),
        Promise.all(datasetResult.data.items.map((dataset) => listDatasetRevisionSelections(config, dataset.current_revision.id))),
      ]);
      const nextTemplates = templateResult.data.items;
      const nextPlans = planResult.data.items;
      const nextModels = modelResult.data.items;
      const nextCards = cardResults.flatMap((item) => item.data.items);
      const nextSelections = selectionResults.flatMap((item) => item.data.items);
      setTemplates(nextTemplates);
      setPlans(nextPlans);
      setModels(nextModels);
      setCards(nextCards);
      setSelections(nextSelections);
      // No first-item fallback: choosing an exact artifact is an engineer action.
      setPlan((current) => current ?? nextPlans.find((item) => item.validation_plan_id === session?.validationPlan?.id) ?? null);
      setPersistedResult(savedResult?.data ?? null);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [
    config,
    materialState?.material_state_id,
    session?.validation?.id,
    session?.validationPlan?.id,
  ]);

  useEffect(() => {
    if (compatibleCards.some((item) => item.solver_card_id === cardId)) return;
    setCardId("");
  }, [cardId, compatibleCards]);

  async function createPlan(): Promise<void> {
    if (!selectedTemplate || !selectedModel || !selectedCard || !selectedSelection) return;
    setBusy(true);
    setError(null);
    try {
      const result = await createReferenceValidationPlan(config, {
        classification: "internal",
        content: {
          plan_label: `Pinned validation · ${session?.selection?.label ?? "selected candidate"}`,
          validation_template_id: selectedTemplate.validation_template_id,
          validation_template_revision_id: selectedTemplate.current_revision.id,
          material_model_id: selectedModel.material_model_id,
          material_model_revision_id: selectedModel.current_revision.id,
          solver_card_id: selectedCard.solver_card_id,
          solver_card_revision_id: selectedCard.current_revision.id,
          experimental_selection_id: selectedSelection.selection_id,
          experimental_selection_revision_id: selectedSelection.current_revision.id,
        },
        change_reason: "Pin non-production OpenRadioss validation inputs to the selected Modeling candidate",
      });
      setPlan(result.data);
      setPersistedResult(null);
      setPlans((items) => [result.data, ...items.filter((item) => item.validation_plan_id !== result.data.validation_plan_id)]);
      onSessionEvent?.({ type: "CHANGE_VALIDATION_TARGET" });
      onSessionChange?.({ validationPlan: ref(result.data.validation_plan_id, result.data.current_revision.id, result.data.current_revision.content.plan_label, result.data.current_revision.revision_no) });
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function submitRun(): Promise<void> {
    if (!plan) return;
    setBusy(true);
    setError(null);
    try {
      const result = await submitReferenceValidationRun(config, {
        validation_plan_id: plan.validation_plan_id,
        validation_plan_revision_id: plan.current_revision.id,
        execution_mode: "reference_inline_mock",
        change_reason: "Submit pinned non-production OpenRadioss reference validation",
      });
      setRun(result.data);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  async function finishReferenceRun(): Promise<void> {
    if (!run) return;
    setBusy(true);
    setError(null);
    try {
      const polled = await pollReferenceValidationRun(config, run.validation_run_id, {
        outcome: "succeeded",
        change_reason: "Collect non-production reference runner evidence",
      });
      const evaluated = await evaluateReferenceValidationRun(config, polled.data.validation_run_id, {
        change_reason: "Evaluate the independent validation result separately from fit metrics",
      });
      setRun(evaluated.data);
      const result = evaluated.data.validation_result;
      if (result) {
        setPersistedResult(result);
        onSessionChange?.({ validation: ref(result.validation_result_id, result.validation_result_manifest_id, `Validation ${result.verdict}`, 1) });
      }
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  const result = run?.validation_result ?? persistedResult;
  const validationState = !familySupported || (candidatePinned && !validationPathAvailable)
    ? "Not supported"
    : result ? result.verdict : plan ? "Not run" : "Not configured";
  const reviewState = session?.stalePointers?.reviewRelease ? "Stale" : "Not configured";
  const activityContext = new URLSearchParams({
    ...(session?.selection ? { candidate_id: session.selection.id, candidate_revision_id: session.selection.revisionId } : {}),
    ...(result ? { validation_result_id: result.validation_result_id } : {}),
    ...(selectedCard
      ? { solver_card_id: selectedCard.solver_card_id, solver_card_revision_id: selectedCard.current_revision.id }
      : plan
        ? {
            solver_card_id: plan.current_revision.content.solver_card_id,
            solver_card_revision_id: plan.current_revision.content.solver_card_revision_id,
          }
        : {}),
  }).toString();
  const activityPath = `/activity${activityContext ? `?${activityContext}` : ""}`;
  const governancePath = `/governance${activityContext ? `?${activityContext}` : ""}`;

  return <section className="modeling-governance-stage" aria-label="Validation and review lifecycle">
    <header>
      <div>
        <p className="workspace-caption">Governed evidence</p>
        <h2>Validation, review and release</h2>
      </div>
      <button className="text-button" type="button" onClick={() => void load()} disabled={loading}>{loading ? "Loading…" : "Refresh exact artifacts"}</button>
    </header>
    <p className="muted">Fit metrics remain fit evidence. A validation result is created only by a pinned validation plan and runner result; approval and release are never inferred from either.</p>
    {error ? <p className="error-notice" role="alert">{error}</p> : null}

    <ol className="modeling-governance-ledger">
      <li><strong>Selected candidate</strong><span>{candidatePinned ? `${session?.selection?.label} · r${session?.selection?.revisionNo}` : "Not configured — save an explicit candidate first"}</span></li>
      <li><strong>Fit metric</strong><span>{candidatePinned ? "Available as fit evidence only" : "Not run"}</span></li>
      <li><strong>Validation plan / result</strong><span>{validationState}{result ? ` · ${result.holdout_independence.replaceAll("_", " ")}` : ""}</span></li>
      <li><strong>Review package</strong><span>{reviewState} — immutable candidate-package production is not exposed by this session API</span></li>
      <li><strong>Release</strong><span>Not configured — release inputs require a passed result and approved immutable review package</span></li>
    </ol>

    {!familySupported ? <p className="modeling-governance-block">Not supported: this non-production OpenRadioss reference path currently validates a bounded metal reference workflow only. No fallback result is shown for {family}.</p> : null}
    {familySupported && candidatePinned && !loading && !validationPathAvailable ? <p className="modeling-governance-block">Not supported for this selected candidate: no current Material Model IR carries matching calibration-candidate evidence, or its exact Solver Card is not pinned. A model from the same Material State is never substituted.</p> : null}
    {familySupported && validationPathAvailable ? <div className="modeling-governance-grid">
      <section aria-labelledby="validation-plan-title">
        <h3 id="validation-plan-title">Pinned validation plan</h3>
        {planCreationSupported ? <>
          <p>Select concrete revisions; no current or latest revision is substituted.</p>
          <label>Reference virtual specimen template<select aria-label="Validation template" value={templateId} onChange={(event) => setTemplateId(event.target.value)}><option value="">Choose exact template</option>{templates.map((item) => <option key={item.validation_template_id} value={item.validation_template_id}>{item.current_revision.content.template_label} · r{item.current_revision.revision_no}</option>)}</select></label>
          <label>Material Model revision<select aria-label="Validation Material Model" value={modelId} onChange={(event) => setModelId(event.target.value)}><option value="">Choose exact candidate-linked Material Model</option>{eligibleModels.map((item) => <option key={item.material_model_id} value={item.material_model_id}>{shortId(item.material_model_id)} · r{item.current_revision.revision_no}</option>)}</select></label>
          <label>OpenRadioss Solver Card revision<select aria-label="Validation Solver Card" value={cardId} onChange={(event) => setCardId(event.target.value)} disabled={!modelId}><option value="">Choose exact Solver Card</option>{compatibleCards.map((item) => <option key={item.solver_card_id} value={item.solver_card_id}>{item.current_revision.content.card_title} · r{item.current_revision.revision_no}</option>)}</select></label>
          <label>Experimental Dataset selection<select aria-label="Validation experimental selection" value={selectionId} onChange={(event) => setSelectionId(event.target.value)}><option value="">Choose exact reference selection</option>{selections.map((item) => <option key={item.selection_id} value={item.selection_id}>{item.selection_label} · r{item.current_revision.revision_no}</option>)}</select></label>
          <button className="button primary" type="button" disabled={busy || !prerequisitesReady} onClick={() => void createPlan()}>{busy ? "Pinning…" : "Create pinned validation plan"}</button>
        </> : plan ? <p className="state-detail">Plan {shortId(plan.validation_plan_id)} pins model revision {shortId(plan.current_revision.content.material_model_revision_id)}, Solver Card revision {shortId(plan.current_revision.content.solver_card_revision_id)}, and experimental selection revision {shortId(plan.current_revision.content.experimental_selection_revision_id)}. Change the upstream target to create a replacement plan.</p> : null}
        {!candidatePinned ? <small>Requires a saved Processing Output and explicit candidate selection.</small> : null}
      </section>
      <section aria-labelledby="validation-run-title">
        <h3 id="validation-run-title">Non-production OpenRadioss job</h3>
        <p>{plan ? `${plan.current_revision.content.plan_label} · r${plan.current_revision.revision_no}` : "Not run — create a pinned plan first."}</p>
        {run ? <p className="state-detail">Run {shortId(run.validation_run_id)} · {run.status}{result ? ` · result ${result.verdict}` : ""}</p> : null}
        {!run ? <button className="button secondary" type="button" disabled={busy || !plan} onClick={() => void submitRun()}>Submit validation job</button> : null}
        {run?.status === "queued" || run?.status === "running" ? <button className="button secondary" type="button" disabled={busy} onClick={() => void finishReferenceRun()}>Collect and evaluate result</button> : null}
        {result ? <p className="state-detail">Validation result {result.verdict} · relative RMSE {result.relative_root_mean_squared_error?.toExponential(3) ?? "not evaluated"}. This is not the Fit metric.</p> : null}
      </section>
    </div> : null}

    <section className="modeling-governance-review-block" aria-labelledby="review-release-title">
      <h3 id="review-release-title">Review and release are separate commands</h3>
      <p>Submit, Request changes, Approve, and Release remain unavailable here until the API supplies one immutable candidate package digest. The session never guesses SHA-256 values or promotes a fit or validation result into approval.</p>
      <div className="modeling-governance-commands" role="group" aria-label="Review and release commands">
        <button className="button secondary" type="button" disabled title="Not configured: immutable candidate package digest is unavailable">Submit · Not configured</button>
        <button className="button secondary" type="button" disabled title="Not run: requires an immutable submitted review request">Request changes · Not run</button>
        <button className="button secondary" type="button" disabled title="Not run: requires an immutable submitted review request">Approve · Not run</button>
        <button className="button primary" type="button" disabled title="Not configured: requires passed validation and approved immutable review package">Release · Not configured</button>
      </div>
      <div className="modeling-governance-links"><button className="button secondary" type="button" onClick={() => onNavigate(activityPath)}>Open Activity context</button><button className="text-button" type="button" onClick={() => onNavigate(governancePath)}>Open governed reference harness context</button></div>
    </section>
  </section>;
}
