import { useCallback, useEffect, useMemo, useState } from "react";

import { ModelingWorkspaceLayout } from "../../../../../design/modeling-workspace-layout";
import { WorkbenchMessage } from "../../../../../design/semantic-ui";
import type { ApiConfig } from "../../../../../shared/api";
import type { CanonicalTestDataDocumentResponse } from "../../../../test-data/contracts";
import { useLinearViscoelasticCalibration } from "../../../controller/use-linear-viscoelastic-calibration";
import { useLinearViscoelasticApprovedSetup } from "../../../controller/use-linear-viscoelastic-approved-setup";
import { useLinearViscoelasticFitInput } from "../../../controller/use-linear-viscoelastic-fit-input";
import type { CommonProcessingOutputResponse } from "../../../model/common-processing-contracts";
import { parseDmaTemperatureSweep } from "../../../model/dma-tts-draft";
import type { LinearViscoelasticCatalogContext } from "../../../model/linear-viscoelastic-calibration-contracts";
import {
  activePolymerDirectPartitionCounts,
  countPolymerPartitions,
} from "../../../model/linear-viscoelastic-calibration-draft";
import type { ModelingSessionRecordRef } from "../../../model/session-controller";
import { PolymerLinearViscoelasticAdvanced } from "./polymer-linear-viscoelastic-advanced";
import { PolymerLinearViscoelasticCandidateComparison } from "./polymer-linear-viscoelastic-candidate-comparison";
import {
  buildPolymerFitInputReviewItems,
  buildPolymerApprovedSetupContext,
  formatPolymerApplicationRange,
  presentPolymerApprovedSetup,
} from "./polymer-linear-viscoelastic-fit-view";
import { PolymerLinearViscoelasticInputReview } from "./polymer-linear-viscoelastic-input-review";
import { PolymerLinearViscoelasticResidualPlot } from "./polymer-linear-viscoelastic-residual-plot";
import { PolymerLinearViscoelasticResponsePlot } from "./polymer-linear-viscoelastic-response-plot";
import {
  buildPolymerObservedSeries,
  buildProcessedPolymerObservedSeries,
} from "./polymer-linear-viscoelastic-presentation";
import { PolymerLinearViscoelasticResults } from "./polymer-linear-viscoelastic-results";
import "./polymer-linear-viscoelastic-workspace.css";

type PolymerPlotView = "response" | "residual";

interface PolymerLinearViscoelasticFitProps {
  config: ApiConfig;
  testData?: CanonicalTestDataDocumentResponse;
  testDataRef?: ModelingSessionRecordRef;
  sourceDisplayLabel?: string;
  materialDisplayLabel?: string;
  sourceDocument?: Record<string, unknown> | null;
  processingOutput?: CommonProcessingOutputResponse;
  catalogContext?: LinearViscoelasticCatalogContext;
  initialSelection?: ModelingSessionRecordRef;
  initialSelectedModel?: ModelingSessionRecordRef;
  staleTestData?: ModelingSessionRecordRef;
  staleTestDataDisplayLabel?: string;
  staleSelection?: ModelingSessionRecordRef;
  onSelectionSaved?: (selection: ModelingSessionRecordRef) => void;
  onSelectedModelSaved?: (model: ModelingSessionRecordRef) => void;
  onRestoreSavedInput?: () => void;
  onOpenData?: () => void;
  onOpenProcess?: () => void;
  onContinue?: () => void;
  ribbonOpen?: boolean;
  onRibbonOpenChange?: (open: boolean) => void;
}

export function PolymerLinearViscoelasticFit({
  config,
  testData,
  testDataRef,
  sourceDisplayLabel,
  sourceDocument,
  processingOutput,
  catalogContext,
  initialSelection,
  initialSelectedModel,
  staleTestData,
  staleTestDataDisplayLabel,
  staleSelection,
  onSelectionSaved,
  onSelectedModelSaved,
  onRestoreSavedInput,
  onOpenData,
  onOpenProcess,
  onContinue,
  ribbonOpen = true,
  onRibbonOpenChange = () => undefined,
}: PolymerLinearViscoelasticFitProps) {
  const processedDeclared = Boolean(
    processingOutput?.steps.some((step) => step.method_id === "polymer.dma_frequency_master_curve"),
  );
  const processingSource = processingOutput && processedDeclared
    ? { id: processingOutput.processing_output_id, revisionId: processingOutput.current_revision.id }
    : undefined;
  const dmaTemperatureSweepRequiresProcess = Boolean(parseDmaTemperatureSweep(sourceDocument));
  const directSourceAvailable = Boolean(testData && testDataRef && sourceDocument)
    && !dmaTemperatureSweepRequiresProcess;
  const processedInput = useLinearViscoelasticFitInput(config, processingSource);
  const processedAvailable = processedInput.status === "ready";
  const processedCalibrationObservationCount = (
    processedInput.data?.rows.filter((row) => row.partition === "CALIBRATION").length ?? 0
  ) * 2;
  const calibration = useLinearViscoelasticCalibration({
    config,
    sourceDocument,
    directSource: testDataRef ? { id: testDataRef.id, revisionId: testDataRef.revisionId } : undefined,
    directAvailable: directSourceAvailable,
    processingSource,
    processedAvailable,
    processedCalibrationObservationCount,
    catalogContext,
    initialSelection,
    initialSelectedModel,
    onSelectionSaved,
    onSelectedModelSaved,
  });
  const {
    state,
    snapshot,
    sourceChoice,
    draft,
    blockers,
    selectedCandidate,
    recommendedCandidate,
    recommendedCandidateId,
    plottedCandidate,
    warnings,
    acknowledgedWarnings,
    selectionReloadFailed,
    setupReview,
    actions,
  } = calibration;
  const approvedSetupContext = buildPolymerApprovedSetupContext({
    catalog: catalogContext,
    testData: testDataRef,
    directMode: snapshot.mode,
    sourceChoice,
    processingOutput: processingSource,
  });
  const approvedSetup = useLinearViscoelasticApprovedSetup(config, approvedSetupContext);
  const [plotView, setPlotView] = useState<PolymerPlotView>("response");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const closeAdvanced = useCallback(() => setAdvancedOpen(false), []);
  const staleSelectionKey = staleSelection ? `${staleSelection.id}:${staleSelection.revisionId}` : "";
  const staleInputKey = staleTestData ? `${staleTestData.id}:${staleTestData.revisionId}` : "";
  const [acknowledgedStaleSelectionKey, setAcknowledgedStaleSelectionKey] = useState("");
  const historicalSelectionStale = Boolean(
    !initialSelection
      && (staleSelectionKey || staleInputKey)
      && `${staleSelectionKey}:${staleInputKey}` !== acknowledgedStaleSelectionKey,
  );
  const inputChanged = state.phase === "stale" || historicalSelectionStale;
  const calculationBusy = state.phase === "creating-plan"
    || state.phase === "queueing-run"
    || state.phase === "running"
    || setupReview.status === "submitting";
  useEffect(() => {
    if (approvedSetup.status !== "ready" || !approvedSetup.plan || !approvedSetup.selected
      || state.run || state.selection || setupReview.status !== "idle") return;
    actions.prepareApprovedPlan(approvedSetup.plan, approvedSetup.selected);
  }, [approvedSetup.plan?.plan_id, approvedSetup.selected?.plan_revision_id, approvedSetup.status, setupReview.status, state.run, state.selection]);
  const processedPartitions = useMemo(() => {
    const rows = processedInput.data?.rows ?? [];
    const length = rows.reduce((maximum, row) => Math.max(maximum, row.ordinal + 1), 0);
    const values = Array.from({ length }, () => null as typeof draft.partitions[number]);
    for (const row of rows) values[row.ordinal] = row.partition;
    return values;
  }, [draft.partitions, processedInput.data]);
  const activePartitions = sourceChoice === "processing-output" ? processedPartitions : draft.partitions;
  const partitionCounts = sourceChoice === "processing-output"
    ? countPolymerPartitions(processedPartitions)
    : activePolymerDirectPartitionCounts(draft, snapshot);
  const fitObservationCount = sourceChoice === "processing-output"
    ? processedCalibrationObservationCount
    : partitionCounts.calibration * (snapshot.mode === "dma" ? 2 : 1);
  const observedSeries = useMemo(
    () => sourceChoice === "processing-output"
      ? buildProcessedPolymerObservedSeries(processedInput.data)
      : buildPolymerObservedSeries(snapshot, draft.selectedTemperature, draft.partitions),
    [draft.partitions, draft.selectedTemperature, processedInput.data, snapshot, sourceChoice],
  );
  const applicationRange = useMemo(() => formatPolymerApplicationRange(observedSeries), [observedSeries]);
  const sourceBlocked = sourceChoice === "test-data"
    ? !directSourceAvailable
    : !(processingSource && processedInput.status === "ready");
  const dmaNeedsProcess = Boolean(
    (sourceChoice === "processing-output" && processedInput.status !== "ready")
      || dmaTemperatureSweepRequiresProcess,
  );

  const sourceLabel = sourceChoice === "processing-output"
    ? processingOutput?.label ?? "Shifted DMA response not loaded"
    : sourceDisplayLabel ?? testDataRef?.label ?? (testData ? "Test Data" : "Test Data not loaded");
  const savedInputLabel = `${staleTestDataDisplayLabel ?? "Saved Test Data"}${
    staleTestData?.revisionNo ? ` · version ${staleTestData.revisionNo}` : ""
  }`;
  const currentInputLabel = `${sourceLabel}${
    testDataRef?.revisionNo ? ` · version ${testDataRef.revisionNo}` : ""
  }`;
  const modeLabel = sourceChoice === "processing-output"
    ? "Shifted DMA response"
    : snapshot.mode === "dma" ? "DMA frequency sweep" : "Relaxation response";
  const usedValueCount = sourceChoice === "processing-output"
    ? processedInput.data?.rows.length ?? 0
    : snapshot.pointCount;
  const dualResponse = sourceChoice === "processing-output" || snapshot.mode === "dma";
  const inputReviewItems = buildPolymerFitInputReviewItems({
    modeLabel,
    sourceLabel,
    measurementPointCount: usedValueCount,
    calculationPointCount: partitionCounts.calibration,
    calculationValueCount: fitObservationCount,
    verificationPointCount: partitionCounts.holdout,
    excludedPointCount: partitionCounts.excluded,
    dualResponse,
    ...(sourceChoice === "processing-output" && processedInput.data?.reference_temperature_k
      ? { temperature: { label: "Reference temperature" as const, value: processedInput.data.reference_temperature_k } }
      : snapshot.conditionTemperature !== null
        ? { temperature: { label: "Temperature" as const, value: snapshot.conditionTemperature } }
        : {}),
  });

  const setupView = {
    sourceChoice,
    processedAvailable,
    processedInputStatus: processedInput.status,
    processedInputError: processedInput.error,
    processedFitInput: processedInput.data,
    sourceDisplayLabel: sourceLabel,
    testData,
    testDataRef,
    processingOutput,
    activeDirectMode: snapshot.mode,
    snapshot,
    selectedTemperature: draft.selectedTemperature,
    candidateScopeMode: draft.candidateScopeMode,
    availableTemperatures: snapshot.temperatures,
    availability: draft.availability,
    partitions: activePartitions,
    partitionCounts,
    fitObservationCount,
    termCounts: draft.termCounts,
    bounds: draft.bounds,
    weights: draft.weights,
    optimizer: draft.optimizer,
    setupName: draft.setupName,
    baseSetupName: approvedSetup.status === "ready" ? approvedSetup.selected?.setup_name : undefined,
    overrideReason: draft.overrideReason,
    changeReason: draft.changeReason,
    serverDiff: setupReview.plan?.current_revision.content.base_diff,
    reviewStatus: setupReview.status,
    directBlockers: blockers.direct,
    modelBlockers: blockers.model,
    solverBlockers: blockers.solver,
  };
  const setupActions = {
    chooseSource: actions.chooseSource,
    setSelectedTemperature: actions.setSelectedTemperature,
    setAvailability: actions.setAvailability,
    setPartition: actions.setPartition,
    markAllCalibration: actions.markAllCalibration,
    excludeOtherTemperatures: actions.excludeOtherTemperatures,
    toggleTerm: actions.toggleTerm,
    setCandidateScopeMode: actions.setCandidateScopeMode,
    updateBound: actions.updateBound,
    setWeight: actions.setWeight,
    setOptimizer: actions.setOptimizer,
    setSetupName: actions.setSetupName,
    setOverrideReason: actions.setOverrideReason,
    setChangeReason: actions.setChangeReason,
  };

  const useCurrentInput = () => {
    actions.resetForNewPlan();
    setAcknowledgedStaleSelectionKey(`${staleSelectionKey}:${staleInputKey}`);
  };
  const createSetupDraft = async () => {
    await actions.createPlanForReview();
  };
  const openAdvanced = () => {
    if (approvedSetup.status === "ready" && approvedSetup.plan && approvedSetup.selected) {
      actions.prepareApprovedPlan(approvedSetup.plan, approvedSetup.selected);
    }
    setAdvancedOpen(true);
  };
  const graph = plotView === "residual" ? (
    <PolymerLinearViscoelasticResidualPlot
      candidate={plottedCandidate}
      observedSeries={observedSeries}
      weights={state.plan?.current_revision.content.weights}
      isBestEvaluated={Boolean(plottedCandidate && plottedCandidate.candidate_id === recommendedCandidateId)}
      isSelected={Boolean(selectedCandidate && plottedCandidate?.candidate_id === selectedCandidate.candidate_id)}
    />
  ) : (
    <PolymerLinearViscoelasticResponsePlot
      mode={sourceChoice === "processing-output" ? "dma" : snapshot.mode}
      shifted={sourceChoice === "processing-output"}
      observedSeries={observedSeries}
      recommendation={recommendedCandidate}
      selection={selectedCandidate}
      weights={state.plan?.current_revision.content.weights}
      responseEvidence={state.responseEvidence}
    />
  );

  const setupPresentation = presentPolymerApprovedSetup({
    resolverStatus: approvedSetup.status,
    reviewStatus: setupReview.status,
  });
  const setupStatus = setupPresentation.status;
  const calculateApprovedModels = () => {
    if (approvedSetup.status === "ready" && approvedSetup.plan && approvedSetup.selected) {
      void actions.runApprovedPlan(approvedSetup.plan, approvedSetup.selected);
    }
  };
  const selection = (
    <PolymerLinearViscoelasticResults
      state={state}
      selectedCandidate={selectedCandidate}
      recommendedCandidateId={recommendedCandidateId}
      warnings={warnings}
      acknowledgedWarnings={acknowledgedWarnings}
      onClearSelection={() => actions.selectCandidate("")}
      onSelectionReasonChange={actions.setSelectionReason}
      onWarningAcknowledgementChange={actions.setWarningAcknowledged}
      onSaveFit={() => void actions.saveFit().then((saved) => {
        if (saved) onContinue?.();
      })}
      onContinue={() => onContinue?.()}
    />
  );
  const candidateComparisonActive = Boolean(
    state.candidates.length || state.run?.attempts.length,
  );
  const workArea = candidateComparisonActive ? (
    <PolymerLinearViscoelasticCandidateComparison
      state={state}
      observedSeries={observedSeries}
      weights={state.plan?.current_revision.content.weights}
      recommendedCandidateId={recommendedCandidateId}
      applicationRange={applicationRange}
      onSelectCandidate={actions.selectCandidate}
      decision={selection}
    />
  ) : (
    <PolymerLinearViscoelasticInputReview
      items={inputReviewItems}
      setupStatus={setupStatus}
      setupOptions={approvedSetup.matches.map((item) => ({ id: item.plan_revision_id, label: item.setup_name }))}
      busy={calculationBusy}
      onChooseSetup={approvedSetup.choose}
      onReviewSetup={openAdvanced}
      onRetrySetup={setupReview.status === "error" ? actions.retryAfterError : approvedSetup.retry}
      onCalculate={calculateApprovedModels}
    />
  );

  return (
    <ModelingWorkspaceLayout
      ribbon={(
        <div className="polymer-fit-command-ribbon" aria-label="Polymer Fit controls">
          {sourceBlocked ? (
            <div className="polymer-fit-input-summary">
              <span>Fit input</span>
              <strong>{dmaNeedsProcess ? "Shifted DMA response required" : "Test Data required"}</strong>
            </div>
          ) : <>
            <div className="polymer-fit-input-summary">
              <span>Fit input</span>
              <strong>{sourceLabel}</strong>
            </div>
            <div className="polymer-fit-view-switch" role="group" aria-label="Graph view">
              <button type="button" className={plotView === "response" ? "active" : undefined} aria-pressed={plotView === "response"} onClick={() => setPlotView("response")}>Response curves</button>
              <button type="button" className={plotView === "residual" ? "active" : undefined} aria-pressed={plotView === "residual"} disabled={!plottedCandidate} onClick={() => setPlotView("residual")}>Point differences</button>
            </div>
            <div className="polymer-fit-ribbon-actions">
              {setupStatus !== "missing" ? <button type="button" className="button secondary" onClick={openAdvanced}>Calculation settings</button> : null}
              {state.candidates.length && !initialSelection && !state.selection
                ? <button type="button" className="button secondary" disabled={calculationBusy || setupStatus !== "approved"} onClick={calculateApprovedModels}>Recalculate</button>
                : null}
            </div>
          </>}
        </div>
      )}
      plot={(
        <div className={`persistent-modeling-plot polymer-fit-surface polymer-calibration-fit${sourceBlocked ? " source-blocked" : ""}`}>
          {sourceBlocked ? (
            <section className="polymer-source-blocked" aria-label="Fit input required">
              <div>
                <h2>{dmaNeedsProcess ? "Shifted DMA response required" : "Test Data required"}</h2>
                <p>{dmaNeedsProcess
                  ? "Create the shifted DMA response in Process before calculating models."
                  : "Select relaxation or DMA Test Data before calculating models."}</p>
              </div>
              <button type="button" className="button primary" onClick={dmaNeedsProcess ? onOpenProcess : onOpenData}>
                {dmaNeedsProcess ? "Go to Process" : "Choose Test Data"}
              </button>
            </section>
          ) : <div className="polymer-fit-graph-region">{graph}</div>}
          {advancedOpen ? (
            <PolymerLinearViscoelasticAdvanced
              view={setupView}
              actions={setupActions}
              busy={calculationBusy}
              onClose={closeAdvanced}
              onReset={actions.resetDraftToPlan}
              onCreateDraft={() => void createSetupDraft()}
            />
          ) : null}
        </div>
      )}
      dock={sourceBlocked ? undefined : inputChanged ? (
        <WorkbenchMessage kind="blocked" title="Input changed" className="polymer-stale-message">
          <div className="polymer-stale-body">
            <dl className="polymer-stale-context" role="list" aria-label="Saved and current Fit inputs">
              <div role="listitem"><dt>Saved result input</dt><dd>{savedInputLabel}</dd></div>
              <div role="listitem"><dt>Current input</dt><dd>{currentInputLabel}</dd></div>
            </dl>
            <div className="polymer-stale-actions">
              <button type="button" className="button primary" disabled={!staleTestData || !onRestoreSavedInput} onClick={onRestoreSavedInput}>Restore saved input</button>
              <button type="button" className="button secondary" onClick={useCurrentInput}>Use current input</button>
            </div>
          </div>
        </WorkbenchMessage>
      ) : <>
        {workArea}
        {state.error && state.phase !== "stale" ? (
          <WorkbenchMessage
            kind="error"
            title={setupReview.status === "error" ? "Setup could not be saved" : selectionReloadFailed ? "Saved model could not be loaded" : state.run?.status === "succeeded" ? state.selection ? "Model could not be saved" : "Selection could not be saved" : "Calculation failed"}
            action={state.run?.status === "succeeded"
              ? undefined
              : { label: state.recoveryHint ? "Retry" : "Open calculation settings", onClick: actions.retryAfterError }}
          >
            {state.error}{state.recoveryHint ? <><br />{state.recoveryHint}</> : null}
          </WorkbenchMessage>
        ) : null}
      </>}
      dockLabel={sourceBlocked ? undefined : "Fit decision"}
      dockVariant={sourceBlocked ? undefined : candidateComparisonActive ? "decision" : "work"}
      ribbonOpen={ribbonOpen}
      onRibbonOpenChange={onRibbonOpenChange}
    />
  );
}
