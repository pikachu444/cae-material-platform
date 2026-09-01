import { useEffect, useMemo, useReducer, useRef, useState } from "react";

import type { ApiConfig } from "../../../shared/api";
import {
  createLinearViscoelasticPlan,
  createProcessedLinearViscoelasticPlan,
} from "../api/linear-viscoelastic-calibration-api";
import type {
  DirectLinearViscoelasticPlanRequest,
  LinearViscoelasticCatalogContext,
  LinearViscoelasticPlanContextMatch,
  LinearViscoelasticPlanResponse,
  LinearViscoelasticPointPartition,
  LinearViscoelasticRunResponse,
  ProcessedLinearViscoelasticPlanRequest,
} from "../model/linear-viscoelastic-calibration-contracts";
import {
  blankPolymerBounds,
  buildPolymerCalibrationPlanRequest,
  countPolymerPartitions,
  createPolymerCalibrationDraft,
  derivePolymerCalibrationBlockers,
  linearViscoelasticPlanSourceKey,
  polymerSnapshotChannel,
  polymerSourceSnapshot,
  restorePolymerCalibrationDraft,
  setPolymerCandidateScopeMode,
  togglePolymerCalibrationTerm,
  type PolymerCalibrationDraft,
  type PolymerCalibrationGovernanceContext,
  type PolymerCalibrationSourceContext,
  type PolymerDraftAvailability,
  type PolymerFitSourceChoice,
} from "../model/linear-viscoelastic-calibration-draft";
import {
  INITIAL_LINEAR_VISCOELASTIC_CALIBRATION_STATE,
  reduceLinearViscoelasticCalibration,
  terminalRunStatus,
} from "../model/linear-viscoelastic-calibration-state";
import type { ModelingSessionRecordRef } from "../model/session-controller";
import {
  linearViscoelasticErrorMessage,
} from "./linear-viscoelastic-calibration-guards";
import { executeLinearViscoelasticRun } from "./execute-linear-viscoelastic-run";
import { linearViscoelasticCalibrationStatus } from "./linear-viscoelastic-calibration-status";
import {
  createEngineerLinearViscoelasticSelection,
  saveSelectedLinearViscoelasticModel,
} from "./persist-linear-viscoelastic-fit";
import { restoreLinearViscoelasticCalibration } from "./restore-linear-viscoelastic-calibration";
import { useLinearViscoelasticPlanReview } from "./use-linear-viscoelastic-plan-review";

interface CalibrationSelectionRef extends ModelingSessionRecordRef {
  calibrationPlanId?: string;
  calibrationRunId?: string;
  calibrationCandidateId?: string;
}

interface ExactSourceRef {
  id: string;
  revisionId: string;
}

export interface UseLinearViscoelasticCalibrationOptions {
  config: ApiConfig;
  sourceDocument?: Record<string, unknown> | null;
  directSource?: ExactSourceRef;
  directAvailable: boolean;
  processingSource?: ExactSourceRef;
  processedAvailable: boolean;
  processedCalibrationObservationCount?: number;
  catalogContext?: LinearViscoelasticCatalogContext;
  initialSelection?: ModelingSessionRecordRef;
  initialSelectedModel?: ModelingSessionRecordRef;
  onSelectionSaved?: (selection: ModelingSessionRecordRef) => void;
  onSelectedModelSaved?: (model: ModelingSessionRecordRef) => void;
}

export function useLinearViscoelasticCalibration({
  config,
  sourceDocument,
  directSource,
  directAvailable,
  processingSource,
  processedAvailable,
  processedCalibrationObservationCount = 0,
  catalogContext,
  initialSelection,
  initialSelectedModel,
  onSelectionSaved,
  onSelectedModelSaved,
}: UseLinearViscoelasticCalibrationOptions) {
  const snapshot = useMemo(() => polymerSourceSnapshot(sourceDocument), [sourceDocument]);
  const [state, dispatch] = useReducer(
    reduceLinearViscoelasticCalibration,
    INITIAL_LINEAR_VISCOELASTIC_CALIBRATION_STATE,
  );
  const [sourceChoice, setSourceChoice] = useState<PolymerFitSourceChoice>("test-data");
  const [draft, setDraft] = useState<PolymerCalibrationDraft>(() => createPolymerCalibrationDraft(snapshot));
  const [approvedBase, setApprovedBase] = useState<LinearViscoelasticPlanContextMatch | null>(null);
  const planReview = useLinearViscoelasticPlanReview(config);
  const setupReview = planReview.state;
  const [acknowledgedWarnings, setAcknowledgedWarnings] = useState<Set<string>>(new Set());
  const [restoreAttempt, setRestoreAttempt] = useState(0);
  const directSourceIdentity = `test-data:${directSource?.id ?? ""}:${directSource?.revisionId ?? ""}`;
  const processingSourceIdentity = `processing-output:${processingSource?.id ?? ""}:${processingSource?.revisionId ?? ""}`;
  const sourceIdentity = sourceChoice === "test-data" ? directSourceIdentity : processingSourceIdentity;
  const previousSourceIdentity = useRef(sourceIdentity);
  const restoredSelectionKey = useRef("");
  const restoreFailed = useRef(false);
  const lifecycleGeneration = useRef(0);
  const approvedPlan = useRef<LinearViscoelasticPlanResponse | null>(null);
  const sourceChoiceExplicit = useRef(false);

  const sourceContext = useMemo<PolymerCalibrationSourceContext>(() => ({
    sourceChoice,
    directAvailable: directAvailable && snapshot.mode !== "unknown",
    processedAvailable,
    processedCalibrationObservationCount,
    directSource,
    processingSource,
    snapshot,
  }), [directAvailable, directSource, processedAvailable, processedCalibrationObservationCount, processingSource, snapshot, sourceChoice]);
  const blockers = useMemo(
    () => derivePolymerCalibrationBlockers(draft, sourceContext, Boolean(approvedBase)),
    [approvedBase, draft, sourceContext],
  );
  const governance = useMemo<PolymerCalibrationGovernanceContext | null>(() => {
    if (!catalogContext) return null;
    const inputMode = sourceChoice === "processing-output" ? "dma_frequency_master_curve" : snapshot.mode;
    if (inputMode === "unknown") return null;
    return {
      material: catalogContext.material,
      materialState: catalogContext.materialState,
      inputMode,
      ...(approvedBase ? {
        basedOn: {
          planId: approvedBase.plan_id,
          planRevisionId: approvedBase.plan_revision_id,
        },
      } : {}),
    };
  }, [approvedBase, catalogContext, snapshot.mode, sourceChoice]);
  const request = useMemo(() => buildPolymerCalibrationPlanRequest(
    draft,
    sourceContext,
    governance,
  ), [draft, governance, sourceContext]);
  const partitionCounts = useMemo(() => countPolymerPartitions(draft.partitions), [draft.partitions]);

  useEffect(() => {
    // A fixed-frequency DMA temperature sweep is not a direct Fit input. Its caller marks
    // direct input unavailable, so the exact saved TTS result becomes current. Isothermal
    // DMA frequency sweeps remain valid direct inputs and are never silently replaced.
    if (sourceChoiceExplicit.current
      || sourceChoice !== "test-data"
      || !processingSource
      || !processedAvailable
      || directAvailable
      || state.plan
      || state.run
      || state.selection) return;
    sourceChoiceExplicit.current = true;
    setSourceChoice("processing-output");
    lifecycleGeneration.current += 1;
    setApprovedBase(null);
    approvedPlan.current = null;
    planReview.clear();
    setAcknowledgedWarnings(new Set());
    dispatch({ type: "RESET" });
  }, [directAvailable, processedAvailable, processingSource, planReview, snapshot.mode, sourceChoice, state.plan, state.run, state.selection]);

  useEffect(() => {
    const restoredSourceIdentity = state.plan
      ? linearViscoelasticPlanSourceKey(state.plan.current_revision.content)
      : "";
    if (restoredSourceIdentity === directSourceIdentity
      || restoredSourceIdentity === processingSourceIdentity) {
      return;
    }
    setDraft((current) => ({
      ...current,
      selectedTemperature: snapshot.mode === "relaxation" && snapshot.conditionTemperature !== null
        ? String(snapshot.conditionTemperature)
        : "",
      partitions: Array.from({ length: snapshot.pointCount }, () => null),
    }));
  }, [directSourceIdentity, processingSourceIdentity, snapshot, state.plan]);

  useEffect(() => {
    if (previousSourceIdentity.current === sourceIdentity) return;
    previousSourceIdentity.current = sourceIdentity;
    setApprovedBase(null);
    approvedPlan.current = null;
    planReview.clear();
    if (state.plan || state.run || state.selection) {
      dispatch({
        type: "STALE",
        error: "The exact upstream source changed. The previous Plan and Run remain evidence; create a new Plan for this source.",
      });
    } else {
      dispatch({ type: "RESET" });
    }
  }, [sourceIdentity, state.plan, state.run, state.selection]);

  useEffect(() => {
    const saved = initialSelection as CalibrationSelectionRef | undefined;
    const savedModel = initialSelectedModel;
    const selectionKey = saved?.id && saved.revisionId
      ? `${saved.id}:${saved.revisionId}:${savedModel?.id ?? ""}:${savedModel?.revisionId ?? ""}`
      : "";
    const exactSourceLoaded = Boolean(
      (directSource?.id && directSource.revisionId && directAvailable && snapshot.pointCount > 0)
      || (processingSource?.id && processingSource.revisionId && processedAvailable),
    );
    // The common workspace hydrates exact source content after its session pointer.
    // Do not consume the one-shot restore key against empty source identities.
    if (!selectionKey || restoredSelectionKey.current === selectionKey || !saved?.calibrationPlanId || !exactSourceLoaded) return;
    restoredSelectionKey.current = selectionKey;
    restoreFailed.current = false;
    const generation = lifecycleGeneration.current;
    void (async () => {
      try {
        const restored = await restoreLinearViscoelasticCalibration({
          config,
          selectionRef: saved,
          selectedModelRef: savedModel,
          catalogContext,
          directSourceIdentity,
          processingSourceIdentity,
        });
        if (generation !== lifecycleGeneration.current) return;
        if (restored.kind === "stale") {
          dispatch({ type: "STALE", error: restored.message });
          return;
        }
        const restoredSourceChoice = restored.sourceIdentity.startsWith("processing-output:") ? "processing-output" : "test-data";
        sourceChoiceExplicit.current = true;
        setSourceChoice(restoredSourceChoice);
        setDraft(restorePolymerCalibrationDraft(snapshot, restored.plan));
        dispatch({ type: "PLAN_READY", plan: restored.plan });
        dispatch({ type: "RUN_ACCEPTED", run: restored.run });
        if (restored.run.status === "succeeded") {
          dispatch({
            type: "RUN_SUCCEEDED",
            run: restored.run,
            candidates: restored.candidates,
            recommendation: restored.recommendation,
            responseEvidence: restored.responseEvidence,
          });
          dispatch({ type: "SELECTION_RESTORED", selection: restored.selection });
          if (restored.model) dispatch({ type: "MODEL_SAVED", model: restored.model });
          restoreFailed.current = false;
        } else if (terminalRunStatus(restored.run.status)) {
          dispatch({ type: "RUN_FAILED", run: restored.run });
        }
      } catch (cause) {
        if (generation === lifecycleGeneration.current) {
          restoreFailed.current = true;
          dispatch({
            type: "ERROR",
            error: `Saved calibration could not be reloaded. ${linearViscoelasticErrorMessage(cause)}`,
            recoveryHint: "Reload the matching Test Data or TTS Process result, then retry.",
          });
        }
      }
    })();
  }, [catalogContext, config, directAvailable, directSource, directSourceIdentity, initialSelectedModel, initialSelection, processedAvailable, processingSource, processingSourceIdentity, restoreAttempt, snapshot]);

  const selectedCandidate = state.candidates.find((candidate) => candidate.candidate_id === state.selectedCandidateId);
  const recommendedCandidateId = state.recommendation?.candidate_id ?? "";
  const recommendedCandidate = state.candidates.find((candidate) => candidate.candidate_id === recommendedCandidateId);
  const plottedCandidate = selectedCandidate ?? recommendedCandidate;
  const warnings = selectedCandidate?.warnings ?? [];

  function resetForNewPlan(): void {
    lifecycleGeneration.current += 1;
    setApprovedBase(null);
    approvedPlan.current = null;
    planReview.clear();
    dispatch({ type: "RESET" });
    setAcknowledgedWarnings(new Set());
  }

  function resetDraftToPlan(): void {
    setDraft(approvedPlan.current
      ? restorePolymerCalibrationDraft(snapshot, approvedPlan.current)
      : state.plan ? restorePolymerCalibrationDraft(snapshot, state.plan)
      : createPolymerCalibrationDraft(snapshot));
  }

  function chooseSource(choice: PolymerFitSourceChoice): void {
    sourceChoiceExplicit.current = true;
    setSourceChoice(choice);
    resetForNewPlan();
  }

  function setSelectedTemperature(value: string): void {
    setDraft((current) => ({
      ...current,
      selectedTemperature: value,
      partitions: snapshot.mode === "dma" ? current.partitions.map(() => null) : current.partitions,
    }));
  }

  function setAvailability(
    key: keyof PolymerCalibrationDraft["availability"],
    value: PolymerDraftAvailability,
  ): void {
    setDraft((current) => ({ ...current, availability: { ...current.availability, [key]: value } }));
  }

  function setPartition(ordinal: number, partition: LinearViscoelasticPointPartition): void {
    setDraft((current) => ({
      ...current,
      partitions: current.partitions.map((item, index) => index === ordinal ? partition : item),
    }));
  }

  function markAllCalibration(): void {
    setDraft((current) => ({
      ...current,
      partitions: Array.from({ length: snapshot.pointCount }, () => "CALIBRATION"),
    }));
  }

  function excludeOtherTemperatures(): void {
    const temperature = Number(draft.selectedTemperature);
    const temperatureChannel = polymerSnapshotChannel(snapshot, "physics.temperature");
    if (!Number.isFinite(temperature) || !temperatureChannel) return;
    setDraft((current) => ({
      ...current,
      partitions: current.partitions.map((partition, ordinal) => temperatureChannel.values[ordinal] === temperature
        ? (partition ?? "CALIBRATION")
        : "EXCLUDED"),
    }));
  }

  function toggleTerm(term: number): void {
    setDraft((current) => togglePolymerCalibrationTerm(current, term));
  }

  function updateBound(
    term: number,
    index: number,
    key: "lower" | "start" | "upper",
    value: string,
  ): void {
    setDraft((current) => ({
      ...current,
      bounds: {
        ...current.bounds,
        [String(term)]: (current.bounds[String(term)] ?? blankPolymerBounds(term)).map((item, itemIndex) => itemIndex === index
          ? { ...item, [key]: value === "" ? NaN : Number(value) }
          : item),
      },
    }));
  }

  async function createExactPlan(generation: number): Promise<LinearViscoelasticPlanResponse | null> {
    if (!request) return null;
    const result = sourceChoice === "processing-output"
      ? await createProcessedLinearViscoelasticPlan(config, request as ProcessedLinearViscoelasticPlanRequest)
      : await createLinearViscoelasticPlan(config, request as DirectLinearViscoelasticPlanRequest);
    if (generation !== lifecycleGeneration.current) return null;
    dispatch({ type: "PLAN_READY", plan: result.data });
    return result.data;
  }

  async function executePlan(plan: LinearViscoelasticPlanResponse, generation: number): Promise<void> {
    await executeLinearViscoelasticRun({
      config,
      plan,
      dispatch,
      isCurrent: () => generation === lifecycleGeneration.current,
    });
  }

  async function createPlan(): Promise<LinearViscoelasticPlanResponse | null> {
    if (!request) return null;
    lifecycleGeneration.current += 1;
    const generation = lifecycleGeneration.current;
    dispatch({ type: "PLAN_START" });
    try {
      return await createExactPlan(generation);
    } catch (cause) {
      if (generation === lifecycleGeneration.current) {
        dispatch({
          type: "ERROR",
          error: linearViscoelasticErrorMessage(cause),
          recoveryHint: "Review the selected input and calculation values, then retry.",
        });
      }
      return null;
    }
  }

  async function submitPlanReview(plan: LinearViscoelasticPlanResponse): Promise<boolean> {
    const result = await planReview.submit(
      plan,
      draft.overrideReason.trim() || draft.changeReason.trim(),
    );
    if (!result.ok) {
      dispatch({
        type: "ERROR",
        error: `The setup draft was created, but its review request was not sent. ${result.error}`,
        recoveryHint: "Retry the review request. The immutable setup draft will be reused.",
      });
    }
    return result.ok;
  }

  async function createPlanForReview(): Promise<boolean> {
    const plan = await createPlan();
    return plan ? submitPlanReview(plan) : false;
  }

  async function retryPlanReview(): Promise<void> {
    const result = await planReview.retry();
    if (!result.ok) {
      dispatch({
        type: "ERROR",
        error: `The review request was not sent. ${result.error}`,
        recoveryHint: "Retry the review request. The immutable setup draft will be reused.",
      });
    }
  }

  async function runPlan(): Promise<void> {
    if (!state.plan || !approvedBase || approvedBase.approval.state !== "active"
      || approvedBase.plan_id !== state.plan.plan_id
      || approvedBase.plan_revision_id !== state.plan.current_revision.id) return;
    await executePlan(state.plan, lifecycleGeneration.current);
  }

  function prepareApprovedPlan(
    plan: LinearViscoelasticPlanResponse,
    setup: LinearViscoelasticPlanContextMatch,
  ): boolean {
    if (setup.approval.state !== "active"
      || setup.plan_id !== plan.plan_id
      || setup.plan_revision_id !== plan.current_revision.id
      || setup.plan_sha256 !== plan.current_revision.content_hash) return false;
    const exactSource = linearViscoelasticPlanSourceKey(plan.current_revision.content);
    if (exactSource !== directSourceIdentity && exactSource !== processingSourceIdentity) return false;
    setApprovedBase(setup);
    approvedPlan.current = plan;
    sourceChoiceExplicit.current = true;
    setSourceChoice(exactSource.startsWith("processing-output:") ? "processing-output" : "test-data");
    setDraft(restorePolymerCalibrationDraft(snapshot, plan));
    return true;
  }

  async function runApprovedPlan(
    plan: LinearViscoelasticPlanResponse,
    setup: LinearViscoelasticPlanContextMatch,
  ): Promise<void> {
    if (!prepareApprovedPlan(plan, setup)) return;
    lifecycleGeneration.current += 1;
    const generation = lifecycleGeneration.current;
    dispatch({ type: "PLAN_READY", plan });
    await executePlan(plan, generation);
  }

  async function saveSelection(): Promise<NonNullable<typeof state.selection> | null> {
    if (state.selection) return state.selection;
    if (!state.plan || !state.run || !selectedCandidate?.candidate_sha256 || !state.reason.trim()) return null;
    if (warnings.some((warning) => !acknowledgedWarnings.has(warning))) return null;
    dispatch({ type: "SELECTION_START" });
    try {
      const saved = await createEngineerLinearViscoelasticSelection({
        config,
        plan: state.plan,
        run: state.run,
        candidate: selectedCandidate,
        reason: state.reason.trim(),
        warnings,
      });
      dispatch({ type: "SELECTION_RECORDED", selection: saved });
      onSelectionSaved?.({
        id: saved.selection_id,
        revisionId: saved.selection_revision_id,
        label: `Polymer model choice · ${selectedCandidate.term_count}-term`,
        revisionNo: 1,
        calibrationPlanId: state.plan.plan_id,
        calibrationRunId: saved.run_id,
        calibrationCandidateId: saved.candidate_id,
      } as CalibrationSelectionRef);
      return saved;
    } catch (cause) {
      dispatch({
        type: "ERROR",
        error: linearViscoelasticErrorMessage(cause),
        recoveryHint: "The chosen model and reason are preserved. Retry saving.",
      });
      return null;
    }
  }

  async function saveModel(saved = state.selection): Promise<boolean> {
    if (state.selectedModel) return true;
    if (!state.plan || !saved || !selectedCandidate) return false;
    if (!catalogContext) {
      dispatch({
        type: "ERROR",
        error: "The exact Material, State, and property context is not available.",
        recoveryHint: "Restore the selected Material context, then retry saving the model.",
      });
      return false;
    }
    dispatch({ type: "MODEL_SAVE_START" });
    try {
      const selectionRef: CalibrationSelectionRef = {
        id: saved.selection_id,
        revisionId: saved.selection_revision_id,
        label: `Polymer model choice · ${selectedCandidate.term_count}-term`,
        revisionNo: 1,
        calibrationPlanId: state.plan.plan_id,
        calibrationRunId: saved.run_id,
        calibrationCandidateId: saved.candidate_id,
      };
      const reloaded = await saveSelectedLinearViscoelasticModel({
        config,
        selection: saved,
        selectionRef,
        catalogContext,
      });
      dispatch({ type: "MODEL_SAVED", model: reloaded });
      restoredSelectionKey.current = `${saved.selection_id}:${saved.selection_revision_id}:${reloaded.material_model_id}:${reloaded.current_revision.id}`;
      onSelectedModelSaved?.({
        id: reloaded.material_model_id,
        revisionId: reloaded.current_revision.id,
        label: `Polymer model · ${selectedCandidate.term_count}-term`,
        revisionNo: reloaded.current_revision.revision_no,
        manifestSha256: reloaded.current_revision.content_hash,
        classification: reloaded.current_revision.classification,
        lifecycleState: reloaded.current_revision.lifecycle_state,
      });
      return true;
    } catch (cause) {
      dispatch({
        type: "ERROR",
        error: linearViscoelasticErrorMessage(cause),
        recoveryHint: "Your model choice is saved. Retry saving the fitted model.",
      });
      return false;
    }
  }

  async function saveFit(): Promise<boolean> {
    const saved = state.selection ?? await saveSelection();
    return saved ? saveModel(saved) : false;
  }

  function retryAfterError(): void {
    if (state.phase === "error" && setupReview.status === "error" && setupReview.plan) {
      void retryPlanReview();
    }
    else if (state.phase === "error" && state.run?.status === "succeeded" && selectedCandidate) {
      if (state.selection) void saveModel();
      else void saveSelection();
    }
    else if (state.phase === "error" && restoreFailed.current && initialSelection) {
      lifecycleGeneration.current += 1;
      restoredSelectionKey.current = "";
      dispatch({ type: "RESET" });
      setRestoreAttempt((current) => current + 1);
    }
    else if (state.phase === "failed" && state.plan) void runPlan();
    else if (state.plan && !state.run) void runPlan();
    else void createPlan();
  }

  function setWarningAcknowledged(warning: string, checked: boolean): void {
    setAcknowledgedWarnings((current) => {
      const next = new Set(current);
      if (checked) next.add(warning);
      else next.delete(warning);
      return next;
    });
  }

  const currentPlanSourceMatches = !state.plan
    || linearViscoelasticPlanSourceKey(state.plan.current_revision.content) === sourceIdentity;
  const status = linearViscoelasticCalibrationStatus(state.phase);

  return {
    state,
    setupReview,
    snapshot,
    sourceChoice,
    draft,
    blockers,
    partitionCounts,
    requestReady: Boolean(request),
    selectedCandidate,
    recommendedCandidate,
    recommendedCandidateId,
    plottedCandidate,
    warnings,
    acknowledgedWarnings,
    currentPlanSourceMatches,
    selectionReloadFailed: state.phase === "error" && restoreFailed.current,
    status,
    actions: {
      chooseSource,
      setSelectedTemperature,
      setAvailability,
      setPartition,
      markAllCalibration,
      excludeOtherTemperatures,
      toggleTerm,
      setCandidateScopeMode: (mode: "automatic" | "manual") => setDraft((current) => setPolymerCandidateScopeMode(current, mode)),
      updateBound,
      setWeight: (key: keyof PolymerCalibrationDraft["weights"], value: string) => setDraft((current) => ({
        ...current,
        weights: { ...current.weights, [key]: value },
      })),
      setOptimizer: (key: keyof PolymerCalibrationDraft["optimizer"], value: string) => setDraft((current) => ({
        ...current,
        optimizer: { ...current.optimizer, [key]: value },
      })),
      setSetupName: (value: string) => setDraft((current) => ({ ...current, setupName: value })),
      setOverrideReason: (value: string) => setDraft((current) => ({ ...current, overrideReason: value })),
      setChangeReason: (value: string) => setDraft((current) => ({ ...current, changeReason: value })),
      selectCandidate: (candidateId: string) => {
        dispatch({ type: "SELECT_CANDIDATE", candidateId });
        setAcknowledgedWarnings(new Set());
      },
      setSelectionReason: (reason: string) => dispatch({ type: "SET_REASON", reason }),
      setWarningAcknowledged,
      createPlan,
      createPlanForReview,
      runPlan,
      prepareApprovedPlan,
      runApprovedPlan,
      saveSelection,
      saveModel,
      saveFit,
      retryAfterError,
      resetDraftToPlan,
      resetForNewPlan,
    },
  };
}
