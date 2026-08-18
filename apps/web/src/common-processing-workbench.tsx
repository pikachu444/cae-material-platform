import { lazy, Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type React from "react";

import {
  EngineeringCurvePlot,
  EngineeringCurvePlotEmpty,
  type ObservedCurveInput,
  type PlotInteractionCommand,
  type PlotInteractionMode,
  type PlotInteractionState,
} from "./engineering-curve-plot";
import { publishWorkspaceCommandState, publishWorkspaceStatus } from "./design/application-shell";
import { ModelingWorkspaceLayout } from "./design/modeling-workspace-layout";
import { EngineeringPane, EngineeringSection, SemanticText } from "./design/semantic-ui";
import {
  channelForQuantity,
  displayCurveMagnitude,
  displayCurveValue,
  resolveDeviationBand,
} from "./curve-contract";
const HardeningFitOptions = lazy(() => import("./fit-hardening-options").then((module) => ({ default: module.HardeningFitOptions })));

import {
  ApiError,
  downloadCanonicalTestDataDocument,
  listCanonicalTestDataDocuments,
  type ApiConfig,
} from "./api";
import type {
  CanonicalTestDataDocumentResponse,
  DataClassification,
  MaterialResponse,
  MaterialStateResponse,
  PropertySetResponse} from "./types";
import { DomainWorkflowLinks } from "./domain-workflow-links";
import { ModelingStageShell } from "./modeling-stage-shell";
import {
  buildFitDecisionSnapshot,
  commitCommonProcessingOutput, createCommonMappingProfile, createCommonProcessingRecipe,
  dispatchModelingSession, downloadCommonProcessingOutput, executeCommonProcessingBatch,
  executeMetalFitRun, exportPrerequisites,
  fitDecisionIdentityLabel,
  listCommonMappingProfiles, listCommonProcessingBatches, listCommonProcessingEnsembleMethods,
  listCommonProcessingMethods, listCommonProcessingOutputs, listCommonProcessingRecipes,
  modelingDataDocumentMatchesMaterialContext, modelingDocumentMatchesMaterialContext,
  modelingSessionRecordKey, modelingSessionRefFromRecord,
  preflightCommonProcessingBatch, previewCommonProcessing, previewCommonProcessingEnsemble,
  retryFailedCommonProcessingBatch, reviseCommonMappingProfile, reviseCommonProcessingRecipe,
  type CommonCurveStage, type CommonEnsemblePreview, type CommonExactRevisionPin,
  type CommonMappingProfileContent, type CommonMappingProfileResponse,
  type CommonProcessingBatchPreflight, type CommonProcessingBatchResponse,
  type CommonProcessingMethod, type CommonProcessingOutputResponse, type CommonProcessingPreview,
  type CommonProcessingRecipeContent, type CommonProcessingRecipeResponse, type CommonProcessingStep,
  type FitDecisionSelection, type GraphSelectionCommand, type ModelingMaterialFamily,
  type ModelingPlotView, type ModelingSessionEvent, type ModelingSessionRecordRef,
  type ModelingSessionSummary, type ModelingStage,
} from "./features/modeling";
import {
  DEFAULT_PROFILE,
  ELASTOMER_CURVE_PROFILE,
  ELASTOMER_PREPARATION_STEPS,
  METAL_TENSILE_STEPS,
  POLYMER_DMA_PROFILE,
  POLYMER_DMA_STEPS,
  POLYMER_RELAXATION_PROFILE,
  POLYMER_RELAXATION_STEPS,
  PRONY_TERM_COUNTS,
  defaultOptions,
  documentIsPolymerDma,
  documentMatchesDataTrack,
  documentMatchesTrack,
  isFitMethod,
  manualModulusDisplayValue,
  manualModulusPascals,
  methodDisplayName,
  modulusDisplayUnit,
  normalizeToeWarningAcknowledgement,
  numberOption,
  parsedStepArray,
  profileMatchesTrack,
  serverProcessingSteps,
  workupOverridesFromSteps,
  type ModelingTrack,
} from "./features/modeling";

const ModelingDataIntake = lazy(() =>
  import("./features/modeling/ui/stages/data/modeling-data-workspace").then((module) => ({ default: module.ModelingDataWorkspace })),
);
const HardeningCandidateEvidence = lazy(() =>
  import("./features/modeling/ui/stages/fit/modeling-fit-decision").then((module) => ({
    default: module.HardeningCandidateEvidence,
  })),
);
const PronyCandidateEvidence = lazy(() =>
  import("./features/modeling/ui/stages/fit/modeling-fit-decision").then((module) => ({
    default: module.PronyCandidateEvidence,
  })),
);
const ModelingValidationStage = lazy(() =>
  import("./modeling-validation-stage").then((module) => ({
    default: module.ModelingValidationStage,
  })),
);
const ModelingProcessPanel = lazy(() => import("./features/modeling/ui/stages/process/modeling-process-panel"));
const ModelingExportPrerequisites = lazy(() =>
  import("./modeling-export-prerequisites").then((module) => ({
    default: module.ModelingExportPrerequisites,
  })),
);
const ModelingTargetPreview = lazy(() =>
  import("./features/modeling/ui/stages/export/modeling-target-preview").then((module) => ({
    default: module.ModelingTargetPreview,
  })),
);
const ScalarDistributionWorkbench = lazy(() =>
  import("./scalar-distribution-workbench").then((module) => ({
    default: module.ScalarDistributionWorkbench,
  })),
);

interface Props {
  config: ApiConfig;
  onNavigate: (path: string) => void;
  onOpenConnection: () => void;
  onModelingTrackChange?: (track: ModelingTrack) => void;
  initialSession?: ModelingSessionSummary | null;
  onSessionChange?: (patch: Partial<Omit<ModelingSessionSummary, "version" | "updatedAt">>) => void;
  onSessionEvent?: (event: ModelingSessionEvent) => void;
  onNewSession?: (family: ModelingMaterialFamily) => void;
  familyWorkbench?: ReactNode;
  familyInspector?: ReactNode;
  material?: MaterialResponse;
  materialState?: MaterialStateResponse;
  propertySet?: PropertySetResponse;
  locationSearch?: string;
}

type WorkspaceInspector = "step" | "recipe" | "batch";
type PlotView = ModelingPlotView;
type ModelingWorkflowTask = ModelingStage;

type SavedResultLoadState = {
  status: "loading" | "ready" | "error";
  scalarPa?: number;
};

type MappingProfileRetryState =
  | { phase: "append"; profileId: string; etag: string }
  | { phase: "verify"; response: CommonMappingProfileResponse; profileId: string; etag: string };

export type FitSurfaceState =
  | "calculating"
  | "saved-current"
  | "preview-not-saved"
  | "saved-result-stale"
  | "not-calculated";

export function fitSurfaceState(input: {
  previewBusy: boolean;
  usablePreview: boolean;
  verifiedSavedFit: boolean;
  fitHistoryExists: boolean;
}): FitSurfaceState {
  if (input.previewBusy) return "calculating";
  if (input.verifiedSavedFit && input.usablePreview) return "saved-current";
  if (input.usablePreview) return "preview-not-saved";
  if (input.fitHistoryExists) return "saved-result-stale";
  return "not-calculated";
}

const FIT_SURFACE_STATE_LABELS: Record<FitSurfaceState, string> = {
  calculating: "Calculating",
  "saved-current": "Saved current",
  "preview-not-saved": "Preview not saved",
  "saved-result-stale": "Saved result stale",
  "not-calculated": "Not calculated",
};

type ExactFitRestore = {
  preview: CommonProcessingPreview;
  selection: FitDecisionSelection | null;
};

type FitRestoreInFlight = {
  identity: string;
  promise: Promise<ExactFitRestore>;
};

const PROCESS_DRAFT_NOTICE = "Current Process result cleared; saved results remain in history. Fit and Export require a new saved processed result.";

/**
 * Serialize exact restore inputs without depending on object insertion order.
 * Arrays retain their order because ordered processing steps are part of the
 * pinned identity.  The serializer deliberately includes every enumerable
 * field, including fields added by a newer response, so an unrecognised
 * metadata change cannot join an older in-flight request.
 */
function deterministicSerialize(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(deterministicSerialize).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0)
      .map(([key, nested]) => `${JSON.stringify(key)}:${deterministicSerialize(nested)}`);
    return `{${entries.join(",")}}`;
  }
  return value === undefined ? "undefined" : typeof value === "string" ? JSON.stringify(value) : String(value);
}

function GuidedStepOptions({
  step,
  stage,
  onChange,
  graphInteraction,
  onGraphModeChange,
  onApplyGraphSelection,
}: {
  step: CommonProcessingStep;
  stage?: CommonCurveStage;
  onChange: (option: string, value: unknown) => void;
  graphInteraction?: { mode: PlotInteractionMode; canApply: boolean; available: boolean };
  onGraphModeChange?: (mode: PlotInteractionMode) => void;
  onApplyGraphSelection?: () => void;
}) {
  if (step.method_id === "rows.sort_unique") {
    const policy = String(step.options.duplicate_policy);
    return <div className="guided-step-options">
      <fieldset className="option-choice-grid"><legend>Duplicate x-values</legend>{[
        ["reject", "Stop and review"], ["first", "Keep first"], ["mean", "Average duplicates"],
      ].map(([value, label]) => <button type="button" className={policy === value ? "active" : ""} key={value} onClick={() => onChange("duplicate_policy", value)}>{label}</button>)}</fieldset>
      <p className="option-hint">Rows are sorted by the mapped independent quantity. The source Test Data revision is never changed.</p>
    </div>;
  }
  if (step.method_id === "curve.crop") {
    return <div className="guided-step-options">
      <div className="guided-range-row"><label>Range start<input aria-label="Crop range start" type="number" step="any" value={numberOption(step, "minimum")} onChange={(event) => onChange("minimum", Number(event.target.value))}/></label><label>Range end<input aria-label="Crop range end" type="number" step="any" value={numberOption(step, "maximum")} onChange={(event) => onChange("maximum", Number(event.target.value))}/></label></div>
      <p className="option-hint">Use <strong>Select range</strong> on the graph to place both crop boundaries.</p>
    </div>;
  }
  if (step.method_id === "curve.scale_shift") {
    return <div className="guided-step-options">
      <label>Response quantity<input aria-label="Scale and shift quantity" value={String(step.options.quantity)} onChange={(event) => onChange("quantity", event.target.value)}/></label>
      <label className="slider-option">Scale <output>{numberOption(step, "scale").toPrecision(5)}</output><input aria-label="Curve scale" type="range" min="0.5" max="1.5" step="0.001" value={numberOption(step, "scale")} onChange={(event) => onChange("scale", Number(event.target.value))}/></label>
      <label>Offset<input aria-label="Curve offset" type="number" step="any" value={numberOption(step, "offset")} onChange={(event) => onChange("offset", Number(event.target.value))}/></label>
      <p className="option-hint">Scale and offset are explicit Recipe parameters. The mapped input stays visible as a reference overlay.</p>
    </div>;
  }
  if (step.method_id === "curve.resample_linear") {
    return <div className="guided-step-options">
      <div className="guided-range-row"><label>Grid start<input aria-label="Resample grid start" type="number" step="any" value={numberOption(step, "start")} onChange={(event) => onChange("start", Number(event.target.value))}/></label><label>Grid end<input aria-label="Resample grid end" type="number" step="any" value={numberOption(step, "end")} onChange={(event) => onChange("end", Number(event.target.value))}/></label></div>
      <label className="slider-option">Grid points <output>{numberOption(step, "count")}</output><input aria-label="Resample point count" type="range" min="5" max="501" step="1" value={numberOption(step, "count")} onChange={(event) => onChange("count", Number(event.target.value))}/></label>
      <div className="engineering-callout"><strong>Observed domain only</strong><p>Linear interpolation rejects extrapolation. Extend the curve only in the reviewed model extrapolation step.</p></div>
    </div>;
  }
  if (step.method_id === "curve.moving_average") {
    const window = numberOption(step, "window");
    return <div className="guided-step-options">
      <label>Response quantity<input value={String(step.options.quantity)} onChange={(event) => onChange("quantity", event.target.value)}/></label>
      <label className="slider-option">Window points <output>{window}</output><input aria-label="Moving average window" type="range" min="3" max="51" step="2" value={window} onChange={(event) => onChange("window", Number(event.target.value))}/></label>
      <p className="option-hint">Centered moving average. Compare the orange processed curve against the gray mapped input before applying.</p>
    </div>;
  }
  if (step.method_id === "curve.savitzky_golay") {
    const window = numberOption(step, "window");
    return <div className="guided-step-options">
      <label>Response quantity<input value={String(step.options.quantity)} onChange={(event) => onChange("quantity", event.target.value)}/></label>
      <label className="slider-option">Window points <output>{window}</output><input aria-label="Savitzky-Golay window" type="range" min="5" max="51" step="2" value={window} onChange={(event) => onChange("window", Number(event.target.value))}/></label>
      <label className="slider-option">Polynomial order <output>{numberOption(step, "polynomial_order")}</output><input aria-label="Savitzky-Golay polynomial order" type="range" min="1" max={Math.max(1, window - 2)} step="1" value={numberOption(step, "polynomial_order")} onChange={(event) => onChange("polynomial_order", Number(event.target.value))}/></label>
      <p className="option-hint">Window size remains odd and must exceed the polynomial order.</p>
    </div>;
  }
  if (step.method_id === "curve.smoothing_spline") {
    return <div className="guided-step-options">
      <label>Response quantity<input value={String(step.options.quantity)} onChange={(event) => onChange("quantity", event.target.value)}/></label>
      <label>Smoothing factor<input aria-label="Spline smoothing factor" type="number" min="0" step="any" value={numberOption(step, "smoothing_factor")} onChange={(event) => onChange("smoothing_factor", Number(event.target.value))}/></label>
      <p className="option-hint">Zero interpolates the observations. Increase the non-negative factor only after comparing the residual shape.</p>
    </div>;
  }
  if (step.method_id === "tensile.toe_zero_intercept") {
    const warnings = stage?.method_id === step.method_id
      ? stage.diagnostics.filter((item) => item.startsWith("toe.warning."))
      : [];
    return <div className="guided-step-options toe-compensation-options">
      <div className="toe-method-contract"><span>Method</span><strong>OLS zero intercept</strong><small>σ = Eε + b · ε₀ = −b/E</small></div>
      <div className="guided-range-row toe-estimation-range"><label>Estimation start<input aria-label="Toe estimation range start" type="number" step="any" value={numberOption(step, "minimum_strain")} onChange={(event) => onChange("minimum_strain", Number(event.target.value))}/></label><label>Estimation end<input aria-label="Toe estimation range end" type="number" step="any" value={numberOption(step, "maximum_strain")} onChange={(event) => onChange("maximum_strain", Number(event.target.value))}/></label></div>
      <div className="toe-compliance-contract"><span>Equipment compliance</span><strong>Not provided</strong><small>Strain-axis shift only</small></div>
      {warnings.length ? <label className="toe-warning-acknowledgement"><input aria-label="Acknowledge toe quality warning" type="checkbox" checked={step.options.warning_acknowledged === true} onChange={(event) => onChange("warning_acknowledged", event.target.checked)} /><span>Warning reviewed</span></label> : null}
      <p className="option-hint">Choose the linear estimation domain explicitly or use <strong>Select range</strong>. Source Test Data and stress remain unchanged.</p>
    </div>;
  }
  if (step.method_id === "metal.elastic_modulus") {
    const method = String(step.options.method);
    const unit = modulusDisplayUnit(step.options.manual_modulus_unit);
    const manualValue = manualModulusDisplayValue(numberOption(step, "manual_modulus_pa"), unit);
    return <div className="guided-step-options elastic-modulus-options">
      <label className="elastic-modulus-method"><span>Evaluation method</span><select aria-label="Evaluation method" value={method} onChange={(event) => onChange("method", event.target.value)}>{[
        ["robust_huber", "Auto robust"], ["linear_regression", "Linear regression"], ["chord", "Chord"], ["secant", "Secant"], ["manual", "Manual slope"],
      ].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <div className="elastic-modulus-range"><label>Start strain<input aria-label="Elastic range start" type="number" step="any" value={numberOption(step, "minimum_strain")} onChange={(event) => onChange("minimum_strain", Number(event.target.value))}/></label><label>End strain<input aria-label="Elastic range end" type="number" step="any" value={numberOption(step, "maximum_strain")} onChange={(event) => onChange("maximum_strain", Number(event.target.value))}/></label></div>
      <p className="option-hint">Use <strong>Select range</strong> on the graph to set both limits directly.</p>
      <p className="option-hint">Calculated Young&apos;s modulus is derived from the selected elastic range. A manual value is a physical-workup override, not a Fit parameter.</p>
      {method === "manual" ? <div className="elastic-modulus-manual-row"><label>Manual Young&apos;s modulus<input aria-label="Manual Young's modulus" type="number" min="0" step="any" value={manualValue} onChange={(event) => onChange("manual_modulus_pa", manualModulusPascals(Number(event.target.value), unit))} /></label><label>Unit<select aria-label="Manual Young's modulus unit" value={unit} onChange={(event) => onChange("manual_modulus_unit", event.target.value)}><option>GPa</option><option>MPa</option></select></label><label>Override reason<input aria-label="Manual Young's modulus reason" value={String(step.options.manual_modulus_reason ?? "")} onChange={(event) => onChange("manual_modulus_reason", event.target.value)} /></label></div> : null}
    </div>;
  }
  if (step.method_id === "metal.proof_stress") {
    return <div className="guided-step-options">
      <label className="slider-option">Proof offset <output>{(numberOption(step, "offset_strain") * 100).toFixed(2)}%</output><input aria-label="Proof stress offset" type="range" min="0.05" max="1" step="0.05" value={numberOption(step, "offset_strain") * 100} onChange={(event) => onChange("offset_strain", Number(event.target.value) / 100)} /></label>
      <div className="guided-range-row"><label>Search start<input type="number" step="any" value={numberOption(step, "search_start")} onChange={(event) => onChange("search_start", Number(event.target.value))}/></label><label>Search end<input type="number" step="any" value={numberOption(step, "search_end")} onChange={(event) => onChange("search_end", Number(event.target.value))}/></label></div>
      <p><strong>Yield definition:</strong> curve-derived proof stress at the selected offset.</p><p className="option-hint">The offset line and observed intersection update in the live preview. A direct manual yield value is not supported until a production yield-definition contract is approved; supplier values remain source evidence and never silently replace this curve-derived result.</p>
    </div>;
  }
  if (step.method_id === "metal.necking_candidate") {
    return <div className="guided-step-options"><div className="engineering-callout"><strong>Automatic peak candidate</strong><p>The maximum observed engineering stress is marked as the first necking candidate. Confirm or replace it in the Workup step.</p></div></div>;
  }
  if (step.method_id === "metal.engineering_to_true_plastic") {
    return <div className="guided-step-options">
      <label>Necking boundary<select value={String(step.options.necking_policy)} onChange={(event) => onChange("necking_policy", event.target.value)}><option value="observed_full_domain">Use full observed domain</option><option value="manual_index">Use selected point</option></select></label>
      <label>Selected point index<input aria-label="Manual necking point index" type="number" min="0" step="1" value={numberOption(step, "manual_necking_index")} onChange={(event) => onChange("manual_necking_index", Number(event.target.value))}/></label>
      {String(step.options.necking_policy) === "manual_index" ? <div className="guided-range-row"><label>Unit<output aria-label="Manual necking unit">observed point index</output></label><label>Override reason<input aria-label="Manual necking reason" value={String(step.options.manual_necking_reason ?? "")} onChange={(event) => onChange("manual_necking_reason", event.target.value)} /></label></div> : null}
      <p className="option-hint">Choose <strong>Pick point</strong> on the graph; the nearest observed index is applied here.</p>
      <label>Negative plastic strain<select value={String(step.options.negative_plastic_policy)} onChange={(event) => onChange("negative_plastic_policy", event.target.value)}><option value="drop">Drop pre-yield negatives</option><option value="clip_zero">Clip to zero</option><option value="retain">Retain with warning</option></select></label>
    </div>;
  }
  if (step.method_id === "metal.hardening_fit_extrapolate") {
    return <Suspense fallback={<p className="loading-state">Loading Fit controls…</p>}><HardeningFitOptions step={step} onChange={onChange} graphInteraction={graphInteraction ?? { mode: "pan", canApply: false, available: false }} onGraphModeChange={onGraphModeChange ?? (() => undefined)} onApplyGraphSelection={onApplyGraphSelection ?? (() => undefined)} /></Suspense>;
  }
  if (step.method_id === "polymer.log_time_resample") {
    return <div className="guided-step-options polymer-step-options">
      <div className="engineering-callout"><strong>Logarithmic time domain</strong><p>Positive observed time is resampled uniformly in log10(t). Extrapolation is rejected.</p></div>
      <div className="guided-range-row"><label>Start time (s)<input aria-label="Log-time resample start" type="number" min="0.000000001" step="any" value={numberOption(step, "start_time_s")} onChange={(event) => onChange("start_time_s", Number(event.target.value))}/></label><label>End time (s)<input aria-label="Log-time resample end" type="number" min="0.000000001" step="any" value={numberOption(step, "end_time_s")} onChange={(event) => onChange("end_time_s", Number(event.target.value))}/></label></div>
      <label className="slider-option">Log-grid points <output>{numberOption(step, "count")}</output><input aria-label="Log-time resample point count" type="range" min="9" max="501" step="2" value={numberOption(step, "count")} onChange={(event) => onChange("count", Number(event.target.value))}/></label>
      <p className="option-hint">Use <strong>Select range</strong> on the logarithmic graph to place both observed time limits.</p>
    </div>;
  }
  if (step.method_id === "polymer.prony_fit_compare" || step.method_id === "polymer.dma_prony_fit_compare") {
    const dma = step.method_id === "polymer.dma_prony_fit_compare";
    const counts = Array.isArray(step.options.candidate_term_counts) ? step.options.candidate_term_counts.map(Number) : [];
    const toggleCount = (count: number) => onChange("candidate_term_counts", counts.includes(count) ? counts.filter((item) => item !== count) : [...counts, count].sort((a, b) => a - b));
    const mode = String(step.options.selection_mode);
    return <div className="guided-step-options polymer-step-options">
      <fieldset className="candidate-check-grid prony-count-grid"><legend>Generalized-Maxwell candidates</legend>{PRONY_TERM_COUNTS.map((count) => <label key={count}><input type="checkbox" checked={counts.includes(count)} onChange={() => toggleCount(count)} />{count} term{count === 1 ? "" : "s"}</label>)}</fieldset>
      <fieldset className="option-choice-grid"><legend>Candidate selection</legend><button type="button" className={mode === "automatic_bic" ? "active" : ""} onClick={() => onChange("selection_mode", "automatic_bic")}>Automatic · lowest BIC</button><button type="button" className={mode === "manual" ? "active" : ""} onClick={() => onChange("selection_mode", "manual")}>Engineer selection</button></fieldset>
      {mode === "manual" ? <label>Requested term count<select aria-label="Requested Prony term count" value={numberOption(step, "selected_term_count")} onChange={(event) => onChange("selected_term_count", Number(event.target.value))}>{counts.map((count) => <option key={count} value={count}>{count} term{count === 1 ? "" : "s"}</option>)}</select></label> : null}
      <div className="guided-range-row"><label>Minimum τ (s)<input aria-label="Minimum Prony relaxation time" type="number" min="0.000000001" step="any" value={numberOption(step, "minimum_relaxation_time_s")} onChange={(event) => onChange("minimum_relaxation_time_s", Number(event.target.value))}/></label><label>Maximum τ (s)<input aria-label="Maximum Prony relaxation time" type="number" min="0.000000001" step="any" value={numberOption(step, "maximum_relaxation_time_s")} onChange={(event) => onChange("maximum_relaxation_time_s", Number(event.target.value))}/></label></div>
      <label>Objective normalization (MPa)<input aria-label="Prony objective normalization" type="number" min="0.000001" step="any" value={numberOption(step, "normalization_modulus_pa") / 1e6} onChange={(event) => onChange("normalization_modulus_pa", Number(event.target.value) * 1e6)}/></label>
      <p className="option-hint">{dma ? "Storage and loss modulus are fitted jointly with one parameter set. " : ""}This policy is input intent. For automatic selection, the server's actual selected term count and metrics are the result identity; manual use still requires an explicit candidate-row selection.</p>
    </div>;
  }
  return <div className="step-option-grid">{Object.entries(step.options).map(([option, value]) => <label key={option}>{option.replaceAll("_", " ")}{typeof value === "boolean" ? <input type="checkbox" checked={value} onChange={(event) => onChange(option, event.target.checked)} /> : <input value={Array.isArray(value) ? value.join(", ") : String(value)} type={typeof value === "number" ? "number" : "text"} onChange={(event) => onChange(option, typeof value === "number" ? Number(event.target.value) : Array.isArray(value) ? event.target.value.split(",").map((item) => item.trim()).filter(Boolean) : event.target.value)} />}</label>)}</div>;
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "The Processing Workbench operation failed.";
}

function toeScalar(stage: CommonCurveStage | undefined, key: string): number | undefined {
  const value = stage?.scalar_results.find((item) => item.key === key)?.value;
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function ToeCompensationResult({ stage }: { stage: CommonCurveStage | undefined }) {
  if (!stage) return <strong>—</strong>;
  const offset = toeScalar(stage, "toe_strain_offset");
  const slope = toeScalar(stage, "toe_estimated_slope");
  const rSquared = toeScalar(stage, "toe_r_squared");
  const pointCount = toeScalar(stage, "toe_estimation_point_count");
  const warnings = stage.diagnostics.filter((item) => item.startsWith("toe.warning."));
  return <div className="toe-result-evidence">
    <dl>
      <div><dt>Offset ε₀</dt><dd>{offset === undefined ? "—" : offset.toExponential(4)}</dd></div>
      <div><dt>Slope E</dt><dd>{slope === undefined ? "—" : `${(slope / 1e9).toFixed(2)} GPa`}</dd></div>
      <div><dt>R²</dt><dd>{rSquared === undefined ? "—" : rSquared.toFixed(6)}</dd></div>
      <div><dt>Domain points</dt><dd>{pointCount === undefined ? "—" : pointCount.toFixed(0)}</dd></div>
    </dl>
    <small className={warnings.length ? "toe-result-warning" : "toe-result-clear"}>{warnings.length ? `${warnings.length} quality warning${warnings.length === 1 ? "" : "s"} · acknowledgement required` : "Quality checks passed · stress unchanged"}</small>
  </div>;
}

interface PlotBounds {
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
}

function paddedBounds(x: number[], y: number[]): PlotBounds {
  const finiteX = x.filter(Number.isFinite);
  const finiteY = y.filter(Number.isFinite);
  if (!finiteX.length || !finiteY.length) return { xMin: 0, xMax: 1, yMin: 0, yMax: 1 };
  const xMin = Math.min(...finiteX);
  const xMax = Math.max(...finiteX);
  const yMin = Math.min(...finiteY);
  const yMax = Math.max(...finiteY);
  const xPadding = Math.max((xMax - xMin) * 0.025, Math.abs(xMax || 1) * 0.0025);
  const yPadding = Math.max((yMax - yMin) * 0.06, Math.abs(yMax || 1) * 0.01);
  return {
    xMin: xMin - xPadding,
    xMax: xMax + xPadding,
    yMin: yMin - yPadding,
    yMax: yMax + yPadding,
  };
}

function curveDisplayName(item: CanonicalTestDataDocumentResponse): string {
  const specimenMatch = item.specimen_id.match(/(?:specimen|sample|s)?[-_ ]*(\d+)$/i)
    ?? item.document_key.match(/(?:^|[-_ ])(\d+)$/);
  const method = item.method.trim().toLowerCase();
  const testType = method === "tensile" || method === "uniaxial tensile reference method"
    ? "Tensile test"
    : method.includes("planar")
      ? "Planar tension test"
      : method.includes("biaxial")
        ? "Biaxial tension test"
        : method.includes("uniaxial")
          ? "Uniaxial tension test"
          : method.includes("relaxation")
            ? "Relaxation test"
            : method.includes("dma")
              ? "DMA test"
              : "Test Data";
  return specimenMatch ? `${testType} ${specimenMatch[1].slice(-4).padStart(4, "0")}` : testType;
}

function specimenDisplayName(value: string): string {
  const normalized = value.trim();
  const numericSpecimen = normalized.match(/(?:specimen|sample|s)[-_ ]*(\d+)$/i) ?? normalized.match(/(\d+)$/);
  if (numericSpecimen) return `Specimen ${numericSpecimen[1].padStart(2, "0")}`;
  if (/^(?:specimen|sample)\b/i.test(normalized)) return normalized;
  return normalized ? `Specimen ${normalized}` : "Specimen";
}

export function curveRailIdentity(
  specimenId: string,
  revisionNo: number,
  sessionRevisionNo?: number,
): { specimen: string; revision: string } {
  const numericSpecimen = specimenId.match(/(?:specimen|sample|s)[-_ ]*(\d+)$/i) ?? specimenId.match(/(\d+)$/);
  return {
    specimen: numericSpecimen ? `Specimen ${numericSpecimen[1].padStart(2, "0")}` : specimenDisplayName(specimenId),
    revision: sessionRevisionNo === undefined
      ? `Revision r${revisionNo}`
      : `Session revision r${sessionRevisionNo}`,
  };
}

/** Fit keeps the exact pinned revision on one readable normal-surface line. */
export function fitRailIdentity(
  specimenId: string,
  libraryRevisionNo: number,
  exactRevisionNo?: number,
): string {
  const specimen = specimenDisplayName(specimenId);
  return `${specimen} · r${exactRevisionNo ?? libraryRevisionNo}`;
}

function curveGroupLabel(item: CanonicalTestDataDocumentResponse): string {
  const method = item.method.trim().toLowerCase();
  if (method === "tensile" || method === "uniaxial tensile reference method") return "Tensile tests";
  if (method.includes("planar")) return "Planar tension tests";
  if (method.includes("biaxial")) return "Biaxial tension tests";
  if (method.includes("uniaxial")) return "Uniaxial tension tests";
  const quantities = new Set(item.channels.map((channel) => channel.quantity_semantics.toLowerCase()));
  if (quantities.has("frequency.cyclic")) return "DMA frequency sweeps";
  if (quantities.has("time.elapsed")) return "Relaxation tests";
  return item.method.trim() ? `${item.method.trim()} tests` : "Test curves";
}

function exactRefKey(ref: Pick<ModelingSessionRecordRef, "id" | "revisionId">): string {
  return modelingSessionRecordKey(ref.id, ref.revisionId);
}

function stableMappingJson(value: unknown): string {
  return JSON.stringify(value, (_key, nested) => {
    if (!nested || typeof nested !== "object" || Array.isArray(nested)) return nested;
    return Object.fromEntries(Object.entries(nested as Record<string, unknown>).sort());
  });
}

export function CommonProcessingWorkbench({ config, onNavigate, onModelingTrackChange, initialSession, onSessionChange, onSessionEvent, onNewSession, familyWorkbench, familyInspector, material, materialState, propertySet, locationSearch = "" }: Props) {
  const initialQuery = useMemo(() => new URLSearchParams(locationSearch), [locationSearch]);
  const queryStage = initialQuery.get("stage");
  const queryFamily = initialQuery.get("family");
  const queryBatchId = initialQuery.get("batch_id");
  const queryRecipeId = initialQuery.get("recipe_id");
  const queryRecipeRevisionId = initialQuery.get("recipe_revision_id");
  const querySourceRefs = useMemo<ModelingSessionRecordRef[]>(() => {
    const documentIds = initialQuery.getAll("source_document_id");
    const revisionIds = initialQuery.getAll("source_revision_id");
    return documentIds.flatMap((id, index) => {
      const revisionId = revisionIds[index];
      return id && revisionId ? [{ id, revisionId, label: id, revisionNo: 0 }] : [];
    });
  }, [initialQuery]);
  const initialTestDataRefs = useMemo<ModelingSessionRecordRef[]>(
    () => querySourceRefs.length
      ? querySourceRefs
      : initialSession?.workspace.selectedTestDataRefs?.length
      ? initialSession.workspace.selectedTestDataRefs
      : initialSession?.testData ? [initialSession.testData] : [],
    [initialSession, querySourceRefs],
  );
  const initialIncludedDocumentIds = useMemo(
    () => Array.isArray(initialSession?.workspace.selectedDocumentIds)
      ? [...new Set(initialSession.workspace.selectedDocumentIds.filter((id) => initialTestDataRefs.some((ref) => ref.id === id)))]
      : initialTestDataRefs.map((ref) => ref.id),
    [initialSession, initialTestDataRefs],
  );
  const initialVisibleDocumentKeys = useMemo(
    () => Array.isArray(initialSession?.workspace.visibleTestDataKeys)
      ? [...new Set(initialSession.workspace.visibleTestDataKeys)]
      : initialTestDataRefs.map(exactRefKey),
    [initialSession, initialTestDataRefs],
  );
  const [documents, setDocuments] = useState<CanonicalTestDataDocumentResponse[]>([]);
  const [profiles, setProfiles] = useState<CommonMappingProfileResponse[]>([]);
  const mappingProfileRetry = useRef<MappingProfileRetryState | null>(null);
  const [mappingProfileRetryPhase, setMappingProfileRetryPhase] = useState<"append" | "verify" | null>(null);
  const [methods, setMethods] = useState<CommonProcessingMethod[]>([]);
  const [, setEnsembleMethods] = useState<CommonProcessingMethod[]>([]);
  const [outputs, setOutputs] = useState<CommonProcessingOutputResponse[]>([]);
  const [recipes, setRecipes] = useState<CommonProcessingRecipeResponse[]>([]);
  const [batches, setBatches] = useState<CommonProcessingBatchResponse[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [selectedProfileId, setSelectedProfileId] = useState("");
  const [selectedRecipeId, setSelectedRecipeId] = useState("");
  const [document, setDocument] = useState<Record<string, unknown> | null>(null);
  // A Test Data aggregate id is not enough to bind Process. Keep the exact
  // revision key that produced the currently parsed bytes alongside them.
  // The document state update below supplies the render; the key itself does
  // not need a second React state update.
  const loadedExactRefKey = useRef<string | null>(null);
  const [profileText, setProfileText] = useState(JSON.stringify(DEFAULT_PROFILE, null, 2));
  const [stepsText, setStepsText] = useState(JSON.stringify(METAL_TENSILE_STEPS, null, 2));
  const [classification, setClassification] = useState<DataClassification>("internal");
  const [changeReason, setChangeReason] = useState("Save reusable channel mapping");
  const [outputLabel, setOutputLabel] = useState("Processed tensile curve");
  const [outputReason, setOutputReason] = useState("Save selected processing stages");
  const [recipeKey, setRecipeKey] = useState("normalized-tensile-cleanup");
  const [recipeLabel, setRecipeLabel] = useState("Normalized tensile cleanup");
  const [recipeDescription, setRecipeDescription] = useState("Reusable explicit processing steps");
  const [recipeReason, setRecipeReason] = useState("Save reusable Processing Recipe");
  const [preview, setPreview] = useState<CommonProcessingPreview | null>(null);
  // Process keeps the last server-valid graph visible while a new draft is
  // being previewed.  `preview` remains the only promotable/saveable result.
  const [lastValidPreview, setLastValidPreview] = useState<CommonProcessingPreview | null>(null);
  const [savedResultStates, setSavedResultStates] = useState<Record<string, SavedResultLoadState>>({});
  const [localCurrentOutput, setLocalCurrentOutput] = useState<{ id: string; revisionId: string } | null>(null);
  // Keep the mounted workbench's locally saved current pointer available to
  // exact-restore continuations without adding it to the restore effect's
  // identity/dependency set. This preserves one GET coalescing under
  // StrictMode while distinguishing a just-saved output from a fresh reload.
  const localCurrentOutputRef = useRef<{ id: string; revisionId: string } | null>(null);
  const updateLocalCurrentOutput = (next: { id: string; revisionId: string } | null): void => {
    localCurrentOutputRef.current = next;
    setLocalCurrentOutput(next);
  };
  // Selection is a working engineer decision, intentionally independent of Recipe intent.
  const [fitSelection, setFitSelection] = useState<FitDecisionSelection | null>(null);
  const [metalFitRunId, setMetalFitRunId] = useState<string | null>(null);
  // A saved pointer is verified only after the exact Fit Output has been
  // restored successfully (or saved in this mounted session).
  const [verifiedFitOutputKey, setVerifiedFitOutputKey] = useState<string | null>(null);
  const [fitEvidenceOpen, setFitEvidenceOpen] = useState(false);
  const [distributionEvidenceOpen, setDistributionEvidenceOpen] = useState(false);
  const [fitPlotCommand, setFitPlotCommand] = useState<PlotInteractionCommand | null>(null);
  const [fitPlotInteraction, setFitPlotInteraction] = useState<PlotInteractionState>({ mode: "pan", hasSelection: false });
  const [selectedStage, setSelectedStage] = useState(initialSession?.workspace.selectedStageOrdinal ?? 0);
  const [selectedStepIndex, setSelectedStepIndex] = useState(initialSession?.workspace.selectedStepIndex ?? 0);
  const [modelingTrack, setModelingTrack] = useState<ModelingTrack>(["metal", "polymer", "elastomer"].includes(String(queryFamily)) ? queryFamily as ModelingTrack : initialSession?.materialFamily ?? "metal");
  const [workspaceInspector, setWorkspaceInspector] = useState<WorkspaceInspector>("step");
  const [inspectorVisible, setInspectorVisible] = useState(() => initialSession?.workspace.settingsOpen ?? true);
  const [selectedTestDataRefs, setSelectedTestDataRefs] = useState<ModelingSessionRecordRef[]>(initialTestDataRefs);
  const selectedTestDataRefsRef = useRef<ModelingSessionRecordRef[]>(initialTestDataRefs);
  // Kept for Process/Batch APIs that still accept document ids. Data-stage
  // persistence uses selectedTestDataRefs as the source of truth.
  const [ensembleDocumentIds, setEnsembleDocumentIds] = useState<string[]>(initialIncludedDocumentIds);
  const [visibleDocumentIds, setVisibleDocumentIds] = useState<string[]>(initialVisibleDocumentKeys);
  const [observedCurves, setObservedCurves] = useState<ObservedCurveInput[]>([]);
  const [dataComparisonOpen, setDataComparisonOpen] = useState(false);
  const [batchDocumentIds, setBatchDocumentIds] = useState<string[]>([]);
  const [batchLabel, setBatchLabel] = useState("Published Recipe batch");
  const [batchPreflight, setBatchPreflight] = useState<CommonProcessingBatchPreflight | null>(null);
  const [ensemblePointCount, setEnsemblePointCount] = useState(21);
  const [ensemblePreview, setEnsemblePreview] = useState<CommonEnsemblePreview | null>(null);
  const [plotView, setPlotView] = useState<PlotView>(initialSession?.workspace.plotView ?? "pipeline");
  const [workflowTask, setWorkflowTask] = useState<ModelingWorkflowTask>(["data", "process", "fit", "validate", "review", "export"].includes(String(queryStage)) ? queryStage as ModelingWorkflowTask : initialSession?.workspace.activeStage ?? "data");
  const isProcessTask = workflowTask === "process";
  const [busy, setBusy] = useState(false);
  const [savedOutputsOpen, setSavedOutputsOpen] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [recipeConflict, setRecipeConflict] = useState<{ recipeId: string } | null>(null);
  const autoPreviewKey = useRef("");
  const exactDocumentGeneration = useRef(0);
  const attemptedExactDocumentKey = useRef<string | null>(null);
  const intakePreviewActive = useRef(false);
  const previousWorkflowTask = useRef<ModelingWorkflowTask | null>(null);
  // Process drafts copied or edited on the Process stage require an explicit
  // Preview changes action. Keep the marker across stage navigation so a
  // copied Process draft is not implicitly calculated by a neighboring stage.
  // The origin task lets a genuine Fit/Export edit retain that stage's normal
  // auto-preview behavior without clearing the pending Process requirement.
  const pendingExplicitProcessPreview = useRef<{ originTask: ModelingWorkflowTask } | null>(null);
  const exactContextKey = useRef<string | null>(null);
  const contextResetPending = useRef(false);
  const previewAbortController = useRef<AbortController | null>(null);
  const undoSteps = useRef<string[]>([]);
  const redoSteps = useRef<string[]>([]);
  const savedSteps = useRef(stepsText);
  const lastValidSteps = useRef(stepsText);
  const preferredStepContext = useRef("");
  // A restore attempt is settled only after the exact content request has
  // succeeded or failed.  React effect cleanup (for example, StrictMode's
  // setup/cleanup cycle) can re-subscribe to the same in-flight request; the
  // generation below makes only the newest subscription able to update the
  // workspace.
  const fitRestoreRequestGeneration = useRef(0);
  const fitRestoreInFlight = useRef<FitRestoreInFlight | null>(null);
  const fitRestoreSettledKey = useRef<string | null>(null);
  const [fitRestoreGeneration, setFitRestoreGeneration] = useState(0);
  const [fitRestoreError, setFitRestoreError] = useState<string | null>(null);
  const fitEvidenceTriggerRef = useRef<HTMLButtonElement | null>(null);
  const fitEvidenceBodyRef = useRef<HTMLDivElement | null>(null);
  const distributionEvidenceTriggerRef = useRef<HTMLButtonElement | null>(null);

  function closeDistributionEvidence(): void {
    setDistributionEvidenceOpen(false);
    queueMicrotask(() => distributionEvidenceTriggerRef.current?.focus());
  }

  function closeFitEvidence(): void {
    setFitEvidenceOpen(false);
    // Restore focus after React removes the dock.  The deferred focus keeps
    // Escape/Close from landing on a detached body while preserving the
    // discoverable trigger as the user's return point.
    queueMicrotask(() => fitEvidenceTriggerRef.current?.focus());
  }

  useEffect(() => {
    if (!fitEvidenceOpen) return;
    const frame = window.requestAnimationFrame(() => fitEvidenceBodyRef.current?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      closeFitEvidence();
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("keydown", onKeyDown, true);
    };
  }, [fitEvidenceOpen]);

  useEffect(() => {
    if (!distributionEvidenceOpen) return;
    const frame = window.requestAnimationFrame(() =>
      window.document.getElementById("scalar-distribution-analysis")?.focus(),
    );
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      closeDistributionEvidence();
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("keydown", onKeyDown, true);
    };
  }, [distributionEvidenceOpen]);

  useEffect(() => {
    if (workflowTask !== "fit" && fitEvidenceOpen) setFitEvidenceOpen(false);
  }, [fitEvidenceOpen, workflowTask]);

  useEffect(() => {
    if (workflowTask !== "process" && distributionEvidenceOpen) setDistributionEvidenceOpen(false);
  }, [distributionEvidenceOpen, workflowTask]);

  useEffect(() => {
    if (workflowTask !== "data" && dataComparisonOpen) setDataComparisonOpen(false);
  }, [dataComparisonOpen, workflowTask]);

  function clearExactDocumentBinding(): void {
    exactDocumentGeneration.current += 1;
    previewAbortController.current?.abort();
    setBusy(false);
    setPreviewBusy(false);
    setDocument(null);
    loadedExactRefKey.current = null;
    setPreview(null);
    setLastValidPreview(null);
    updateLocalCurrentOutput(null);
    setMetalFitRunId(null);
    setVerifiedFitOutputKey(null);
    setFitRestoreError(null);
    attemptedExactDocumentKey.current = null;
    pendingExplicitProcessPreview.current = null;
  }

  const draftDirty = stepsText !== savedSteps.current;

  function normalizeEditedDraftSteps(next: string): string {
    const normalized = normalizeToeWarningAcknowledgement(lastValidSteps.current, next);
    if (parsedStepArray(normalized)) lastValidSteps.current = normalized;
    return normalized;
  }

  function applyDraftSteps(next: string, force = false, preserveCurrentOutput = false): void {
    const normalizedNext = normalizeEditedDraftSteps(next);
    if (normalizedNext === stepsText && !force) return;
    undoSteps.current.push(stepsText);
    if (undoSteps.current.length > 50) undoSteps.current.shift();
    redoSteps.current = [];
    setStepsText(normalizedNext);
    setFitSelection(null);
    setPreview(null);
    setVerifiedFitOutputKey(null);
    if (isProcessTask) {
      pendingExplicitProcessPreview.current = { originTask: "process" };
    } else if (pendingExplicitProcessPreview.current) {
      pendingExplicitProcessPreview.current = { originTask: workflowTask };
    }
    if (!preserveCurrentOutput) {
      updateLocalCurrentOutput(null);
      // A normal draft edit is not a revision yet, but it must never leave a
      // downstream current chain looking valid. Saving later creates the
      // immutable Processing Output revision. Copying settings from history
      // is the explicit exception: it creates a local draft while the saved
      // current output remains the downstream reference until a new save.
      onSessionEvent?.({ type: "CHANGE_PROCESS" });
    }
    setNotice(PROCESS_DRAFT_NOTICE);
  }

  function replaceSavedSteps(next: string): void {
    setStepsText(next);
    if (parsedStepArray(next)) lastValidSteps.current = next;
    savedSteps.current = next;
    undoSteps.current = [];
    redoSteps.current = [];
    setPreview(null);
    setLastValidPreview(null);
    updateLocalCurrentOutput(null);
    setMetalFitRunId(null);
    setFitSelection(null);
    setVerifiedFitOutputKey(null);
    if (isProcessTask) {
      pendingExplicitProcessPreview.current = { originTask: "process" };
    } else if (pendingExplicitProcessPreview.current) {
      pendingExplicitProcessPreview.current = { originTask: workflowTask };
    }
  }

  function undoDraft(): void {
    const previous = undoSteps.current.pop();
    if (previous === undefined) return;
    redoSteps.current.push(stepsText);
    setStepsText(normalizeEditedDraftSteps(previous));
    setPreview(null);
    updateLocalCurrentOutput(null);
    setFitSelection(null);
    setVerifiedFitOutputKey(null);
    if (isProcessTask) {
      pendingExplicitProcessPreview.current = { originTask: "process" };
    } else if (pendingExplicitProcessPreview.current) {
      pendingExplicitProcessPreview.current = { originTask: workflowTask };
    }
    setNotice("Restored the previous local Recipe draft state.");
  }

  function redoDraft(): void {
    const next = redoSteps.current.pop();
    if (next === undefined) return;
    undoSteps.current.push(stepsText);
    setStepsText(normalizeEditedDraftSteps(next));
    setPreview(null);
    updateLocalCurrentOutput(null);
    setVerifiedFitOutputKey(null);
    if (isProcessTask) {
      pendingExplicitProcessPreview.current = { originTask: "process" };
    } else if (pendingExplicitProcessPreview.current) {
      pendingExplicitProcessPreview.current = { originTask: workflowTask };
    }
    setNotice("Reapplied the next local Recipe draft state.");
  }

  function resetSession(): void {
    if (draftDirty && !window.confirm("Discard the unsaved local Recipe draft and start a new Modeling session?")) return;
    dispatchModelingSession({ type: "NEW_SESSION", materialFamily: modelingTrack });
    onNewSession?.(modelingTrack);
    const defaults = modelingTrack === "metal" ? METAL_TENSILE_STEPS : modelingTrack === "polymer" ? POLYMER_RELAXATION_STEPS : ELASTOMER_PREPARATION_STEPS;
    const next = JSON.stringify(defaults, null, 2);
    setStepsText(next);
    lastValidSteps.current = next;
    savedSteps.current = next;
    undoSteps.current = [];
    redoSteps.current = [];
    setSelectedStepIndex(0);
    setSelectedStage(0);
    setWorkflowTask("data");
    setSelectedDocumentId("");
    clearExactDocumentBinding();
    selectedTestDataRefsRef.current = [];
    setSelectedTestDataRefs([]);
    setEnsembleDocumentIds([]);
    setVisibleDocumentIds([]);
    setObservedCurves([]);
    setSelectedProfileId("");
    setSelectedRecipeId("");
    setPlotView("pipeline");
    setSavedResultStates({});
    onNavigate(`/modeling?stage=data&family=${modelingTrack}`);
    setNotice("");
  }

  useEffect(() => () => previewAbortController.current?.abort(), []);

  useEffect(() => {
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!draftDirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, [draftDirty]);

  useEffect(() => {
    void Promise.all([
      listCanonicalTestDataDocuments(config),
      listCommonMappingProfiles(config),
      listCommonProcessingMethods(config),
      listCommonProcessingOutputs(config),
      listCommonProcessingEnsembleMethods(config),
      listCommonProcessingRecipes(config),
      listCommonProcessingBatches(config),
    ])
      .then(([documentResult, profileResult, methodResult, outputResult, ensembleMethodResult, recipeResult, batchResult]) => {
        setDocuments(documentResult.data.items);
        setProfiles(profileResult.data.items);
        setMethods(methodResult.data.items);
        setOutputs(outputResult.data.items);
        setEnsembleMethods(ensembleMethodResult.data.items);
        setRecipes(recipeResult.data.items);
        setBatches(batchResult.data.items);
      })
      .catch((caught: unknown) => setError(errorMessage(caught)));
  }, [config]);

  async function loadDocument(
    id: string,
    requestedRevisionId?: string,
  ): Promise<void> {
    const previousPrimaryId = selectedDocumentId;
    intakePreviewActive.current = false;
    autoPreviewKey.current = "";
    setSelectedDocumentId(id);
    const item = documents.find((candidate) => candidate.test_data_document_id === id);
    if (!item) {
      clearExactDocumentBinding();
      return;
    }
    // Restored sessions may point at an older immutable revision than the
    // list's current head; callers restoring a session pass that pin.
    const revisionId = requestedRevisionId ?? item.current_revision.id;
    const exactRef = selectedTestDataRefsRef.current.find((ref) => ref.id === id && ref.revisionId === revisionId)
      ?? modelingSessionRefFromRecord(item);
    const key = exactRefKey(exactRef);
    // Invalidate every source-dependent value before the request starts.  A
    // late response from an older generation is ignored below.
    clearExactDocumentBinding();
    attemptedExactDocumentKey.current = key;
    const generation = exactDocumentGeneration.current;
    setBusy(true);
    setError(null);
    if (workflowTask === "data") {
      // The Library row is the one Process input, not merely a table focus.
      // Pin its immutable identity immediately so a failed content read still
      // has an exact, recoverable session target and clears stale downstream
      // results through the established session reducer.
      onSessionEvent?.({ type: "PIN_TEST_DATA", testData: exactRef });
      const currentRefs = selectedTestDataRefsRef.current;
      const replacingPrimary = Boolean(previousPrimaryId && previousPrimaryId !== id);
      const retainedRefs = replacingPrimary
        ? currentRefs.filter((ref) => ref.id !== previousPrimaryId)
        : currentRefs;
      const isNewExactRef = !retainedRefs.some((ref) => exactRefKey(ref) === key);
      const nextRefs = isNewExactRef
        ? [...retainedRefs.filter((ref) => ref.id !== id), exactRef]
        : retainedRefs;
      if (nextRefs !== currentRefs) {
        // Keep only the new primary plus deliberately retained comparisons. A
        // new revision for the same document replaces its prior exact pin.
        selectedTestDataRefsRef.current = nextRefs;
        setSelectedTestDataRefs(nextRefs);
      }
      // Selecting a Library row replaces the current Process input. Optional
      // comparison overlays remain, but the previous primary never becomes an
      // implicit extra curve merely because the engineer inspected a new row.
      const previousPrimaryKeys = replacingPrimary
        ? currentRefs.filter((ref) => ref.id === previousPrimaryId).map(exactRefKey)
        : [];
      // Data has one exact Process input. Additional exact refs may remain
      // linked and visible for comparison, but they are not joint Process/Fit
      // members merely because they are overlaid on the graph.
      setEnsembleDocumentIds([id]);
      setVisibleDocumentIds((current) => {
        const retained = previousPrimaryKeys.length
          ? current.filter((visibleKey) => !previousPrimaryKeys.includes(visibleKey))
          : current;
        return retained.includes(key) ? retained : [...retained, key];
      });
    } else {
      setEnsembleDocumentIds((current) => current.includes(id) ? current : [...current, id]);
    }
    try {
      const result = await downloadCanonicalTestDataDocument(
        config,
        id,
        revisionId,
      );
      const parsedDocument = JSON.parse(await result.data.blob.text()) as Record<string, unknown>;
      if (exactDocumentGeneration.current !== generation) return;
      loadedExactRefKey.current = key;
      setDocument(parsedDocument);
      if (modelingTrack === "polymer") {
        const dma = documentIsPolymerDma(item);
        const template = dma ? POLYMER_DMA_PROFILE : POLYMER_RELAXATION_PROFILE;
        const steps = dma ? POLYMER_DMA_STEPS : POLYMER_RELAXATION_STEPS;
        const compatible = profiles.find((candidate) => candidate.content.profile_key === template.profile_key)
          ?? profiles.find((candidate) => candidate.content.independent_quantity === template.independent_quantity
            && candidate.content.bindings.every((binding) => template.bindings.some((expected) => expected.target_quantity === binding.target_quantity)));
        setSelectedProfileId(compatible?.mapping_profile_id ?? "");
        setProfileText(JSON.stringify(compatible?.content ?? template, null, 2));
        replaceSavedSteps(JSON.stringify(steps, null, 2));
        setSelectedStepIndex(steps.length - 1);
      }
    } catch (caught) {
      if (exactDocumentGeneration.current !== generation) return;
      setError(errorMessage(caught));
    } finally {
      if (exactDocumentGeneration.current === generation) setBusy(false);
    }
  }

  function retryExactSource(): void {
    if (!selectedSourceRef) return;
    void loadDocument(selectedSourceRef.id, selectedSourceRef.revisionId);
  }

  function retryExactSavedFit(): void {
    if (!exactSessionOutput?.source_processing_output || (workflowTask !== "fit" && workflowTask !== "export")) return;
    fitRestoreSettledKey.current = null;
    setFitRestoreError(null);
    setError(null);
    setFitRestoreGeneration((current) => current + 1);
  }

  function previewIntakeDocument(
    nextDocument: Record<string, unknown>,
    nextPreview: CommonProcessingPreview,
  ): void {
    intakePreviewActive.current = true;
    autoPreviewKey.current = "";
    setSelectedDocumentId("");
    setDocument(nextDocument);
    setPreview(nextPreview);
    setLastValidPreview(nextPreview);
    setSelectedStage(0);
    setPlotView("pipeline");
    setError(null);
    setNotice("Data source preview completed. Only explicit channel mapping was applied.");
  }

  function registerIntakeDocument(item: CanonicalTestDataDocumentResponse): void {
    intakePreviewActive.current = false;
    setDocuments((current) => [
      item,
      ...current.filter((candidate) => candidate.test_data_document_id !== item.test_data_document_id),
    ]);
    setSelectedDocumentId(item.test_data_document_id);
    const exactRef = modelingSessionRefFromRecord(item);
    const currentRefs = selectedTestDataRefsRef.current;
    const previousPrimaryId = ensembleDocumentIds[0] ?? "";
    const previousPrimaryKeys = previousPrimaryId && previousPrimaryId !== item.test_data_document_id
      ? currentRefs.filter((ref) => ref.id === previousPrimaryId).map(exactRefKey)
      : [];
    // A saved local import becomes the one focused Process input. Preserve
    // deliberately linked comparisons, but never turn the previous primary
    // into an implicit comparison or carry another revision of this record.
    const nextRefs = [
      ...currentRefs.filter((ref) => ref.id !== previousPrimaryId
        && ref.id !== item.test_data_document_id),
      exactRef,
    ];
    selectedTestDataRefsRef.current = nextRefs;
    setSelectedTestDataRefs(nextRefs);
    setEnsembleDocumentIds([item.test_data_document_id]);
    setVisibleDocumentIds((current) => {
      const retained = current.filter((key) => !previousPrimaryKeys.includes(key)
        && !key.startsWith(`${item.test_data_document_id}:`));
      const nextKey = exactRefKey(exactRef);
      return retained.includes(nextKey) ? retained : [...retained, nextKey];
    });
    onSessionChange?.({
        testData: exactRef,
    });
  }

  useEffect(() => {
    if (intakePreviewActive.current || selectedDocumentId || !documents.length) return;
    // The workspace ref order is comparison/persistence data, not the focused
    // source. Restore only the explicit exact focus; an incomplete or legacy
    // session waits for the engineer instead of choosing its first linked row.
    const focusedRef = initialSession?.testData
      ? initialTestDataRefs.find((ref) => ref.id === initialSession.testData?.id
        && ref.revisionId === initialSession.testData?.revisionId)
      : undefined;
    const restoredRef = focusedRef;
    const restored = documents.find((item) => item.test_data_document_id === restoredRef?.id
      && (workflowTask === "data"
        ? documentMatchesDataTrack(item, modelingTrack)
        : documentMatchesTrack(item, modelingTrack))
      && (workflowTask === "data" || isProcessTask
        ? modelingDataDocumentMatchesMaterialContext(item, material, materialState)
        : modelingDocumentMatchesMaterialContext(item, material, materialState, documents.some((candidate) => Boolean(candidate.governed_source)))));
    if (restored && restoredRef) {
      setSelectedDocumentId(restored.test_data_document_id);
      void loadDocument(restored.test_data_document_id, restoredRef.revisionId);
    }
  }, [documents, initialTestDataRefs, material, materialState, modelingTrack, selectedDocumentId, workflowTask]);

  useEffect(() => {
    const nextKey = `${material?.material_id ?? ""}:${material?.current_revision.id ?? ""}:${materialState?.material_state_id ?? ""}:${materialState?.current_revision.id ?? ""}`;
    if (!material || !materialState) return;
    if (exactContextKey.current === null) {
      exactContextKey.current = nextKey;
      return;
    }
    if (exactContextKey.current === nextKey) return;
    exactContextKey.current = nextKey;
    contextResetPending.current = true;
    clearExactDocumentBinding();
    intakePreviewActive.current = false;
    autoPreviewKey.current = "";
    setSelectedDocumentId("");
    selectedTestDataRefsRef.current = [];
    setSelectedTestDataRefs([]);
    setEnsembleDocumentIds([]);
    setVisibleDocumentIds([]);
    setObservedCurves([]);
    setSelectedProfileId("");
    setSelectedRecipeId("");
    setNotice("Material changed. Choose a saved dataset before continuing. Earlier results remain available in history.");
  }, [material, materialState]);

  useEffect(() => {
    if (contextResetPending.current && !selectedDocumentId && !selectedProfileId && !selectedRecipeId) {
      contextResetPending.current = false;
    }
  }, [selectedDocumentId, selectedProfileId, selectedRecipeId]);

  useEffect(() => {
    if (contextResetPending.current) return;
    if (selectedProfileId || !profiles.length) return;
    const exactRestored = profiles.find((item) => item.mapping_profile_id === initialSession?.mappingProfile?.id
      && item.current_revision.id === initialSession.mappingProfile.revisionId
      && profileMatchesTrack(item, modelingTrack));
    if (!exactRestored) return;
    setSelectedProfileId(exactRestored.mapping_profile_id);
    setProfileText(JSON.stringify(exactRestored.content, null, 2));
  }, [initialSession, modelingTrack, profiles, selectedProfileId]);

  useEffect(() => {
    if (!queryRecipeId || !queryRecipeRevisionId || selectedRecipeId) return;
    const exactRecipe = recipes.find((item) => item.processing_recipe_id === queryRecipeId
      && item.current_revision.id === queryRecipeRevisionId);
    if (exactRecipe) selectRecipe(exactRecipe.processing_recipe_id);
  }, [queryRecipeId, queryRecipeRevisionId, recipes, selectedRecipeId]);

  useEffect(() => {
    if (!querySourceRefs.length || !documents.length) return;
    const sourceIds = querySourceRefs
      .filter((ref) => documents.some((item) => item.test_data_document_id === ref.id))
      .map((ref) => ref.id);
    if (!sourceIds.length) return;
    setBatchDocumentIds((current) => current.length ? current : sourceIds);
  }, [documents, querySourceRefs]);

  useEffect(() => {
    if (!queryBatchId || !batches.length) return;
    const exactBatch = batches.find((item) => item.batch_id === queryBatchId);
    if (!exactBatch) return;
    setBatchLabel(exactBatch.label);
    setBatchDocumentIds(exactBatch.members.map((member) => member.source.document_id));
  }, [batches, queryBatchId]);

  useEffect(() => {
    if (contextResetPending.current) return;
    if (!selectedDocumentId || busy) return;
    const expectedRef = selectedTestDataRefsRef.current.find((ref) => ref.id === selectedDocumentId);
    const expectedKey = expectedRef ? exactRefKey(expectedRef) : null;
    if (!expectedRef || loadedExactRefKey.current === expectedKey || attemptedExactDocumentKey.current === expectedKey) return;
    void loadDocument(selectedDocumentId, expectedRef.revisionId);
  }, [busy, document, selectedDocumentId, selectedTestDataRefs]);

  const pinnedSavedFitPending = Boolean(
    (workflowTask === "fit" || workflowTask === "export")
      && initialSession?.processingOutput
      && outputs.some((output) => output.processing_output_id === initialSession.processingOutput?.id
        && output.current_revision.id === initialSession.processingOutput.revisionId
        && output.steps.some((step) => isFitMethod(step.method_id))),
  );
  useEffect(() => {
    if (contextResetPending.current) return;
    if (intakePreviewActive.current || !document || !selectedProfileId || preview) return;
    // A pinned Fit Output has its own exact, digest-verified restore path.
    // Do not let the source-document auto-preview race that restore and turn
    // the saved decision back into an unsaved preview after it settles.
    if (pinnedSavedFitPending) return;
    const pendingDraft = pendingExplicitProcessPreview.current;
    if (pendingDraft && !(pendingDraft.originTask === workflowTask && workflowTask !== "process")) return;
    const key = `${selectedDocumentId}:${selectedProfileId}:${stepsText}`;
    if (autoPreviewKey.current === key) return;
    const timer = window.setTimeout(() => {
      autoPreviewKey.current = key;
      void runPreview();
    }, 300);
    return () => window.clearTimeout(timer);
  }, [document, isProcessTask, pinnedSavedFitPending, preview, selectedDocumentId, selectedProfileId, stepsText, workflowTask]);

  function applyModelingTrack(track: ModelingTrack): void {
    setModelingTrack(track);
    onModelingTrackChange?.(track);
    onSessionChange?.({ materialFamily: track });
  }

  function selectProfile(id: string): void {
    setSelectedProfileId(id);
    const selectedProfile = profiles.find((candidate) => candidate.mapping_profile_id === id);
    if (selectedProfile) {
      onSessionEvent?.({ type: "CHANGE_MAPPING", mappingProfile: {
        id: selectedProfile.mapping_profile_id,
        revisionId: selectedProfile.current_revision.id,
        label: selectedProfile.content.label,
        revisionNo: selectedProfile.current_revision.revision_no,
      } });
    } else {
      onSessionEvent?.({ type: "CHANGE_MAPPING" });
    }
    const item = selectedProfile;
    if (item) {
      setProfileText(JSON.stringify(item.content, null, 2));
      if (item.content.profile_key.includes("polymer") || item.content.independent_quantity === "time") applyModelingTrack("polymer");
      else if (item.content.profile_key.includes("elastomer")) applyModelingTrack("elastomer");
      else applyModelingTrack("metal");
    }
  }

  function useProfileTemplate(
    profile: CommonMappingProfileContent,
    steps: CommonProcessingStep[],
  ): void {
    setSelectedProfileId("");
    setProfileText(JSON.stringify(profile, null, 2));
    replaceSavedSteps(JSON.stringify(steps, null, 2));
    setSelectedStepIndex(0);
    setPreview(null);
    setNotice(`Loaded the ${profile.label} template. Confirm channel keys, units, and bounds before saving.`);
  }

  function selectModelingTrack(track: ModelingTrack): void {
    applyModelingTrack(track);
    setWorkspaceInspector("step");
    clearExactDocumentBinding();
    // A family switch changes the quantity contract. Do not silently carry a Test Data
    // revision from another family into the new track; the user must select the exact input.
    setSelectedDocumentId("");
    selectedTestDataRefsRef.current = [];
    setSelectedTestDataRefs([]);
    setEnsembleDocumentIds([]);
    setVisibleDocumentIds([]);
    setObservedCurves([]);
    setBatchDocumentIds([]);
    setEnsemblePreview(null);
    setPlotView("pipeline");
    if (track === "metal") useProfileTemplate(DEFAULT_PROFILE, METAL_TENSILE_STEPS);
    if (track === "polymer") useProfileTemplate(POLYMER_RELAXATION_PROFILE, POLYMER_RELAXATION_STEPS);
    if (track === "elastomer") {
      useProfileTemplate(ELASTOMER_CURVE_PROFILE, ELASTOMER_PREPARATION_STEPS);
      setNotice("Elastomer workbench loaded the exact multi-mode Plan, holdout evidence and reviewed model result.");
    }
    setSelectedRecipeId("");
    setBatchPreflight(null);
    onNavigate(`/modeling?stage=${workflowTask}&family=${track}`);
  }

  function selectRecipe(id: string): void {
    setSelectedRecipeId(id);
    setBatchPreflight(null);
    const item = recipes.find((candidate) => candidate.processing_recipe_id === id);
    if (!item) return;
    setRecipeKey(item.content.recipe_key);
    setRecipeLabel(item.content.label);
    setRecipeDescription(item.content.description ?? "");
    replaceSavedSteps(JSON.stringify(item.content.steps, null, 2));
    if (item.content.steps.some((step) => step.method_id.startsWith("polymer."))) applyModelingTrack("polymer");
    else if (item.content.steps.some((step) => step.method_id.startsWith("metal."))) applyModelingTrack("metal");
    setSelectedStepIndex(0);
    setPreview(null);
    const exactProfile = profiles.find(
      (profile) => profile.mapping_profile_id === item.content.mapping_profile_id
        && profile.current_revision.id === item.content.mapping_profile_revision_id,
    );
    if (exactProfile) selectProfile(exactProfile.mapping_profile_id);
    else {
      setSelectedProfileId("");
      setNotice("This Recipe pins an older exact Mapping Profile revision. Select a current profile before saving a new Recipe revision.");
    }
  }

  function cloneSelectedRecipe(): void {
    const selected = recipes.find((item) => item.processing_recipe_id === selectedRecipeId);
    if (!selected) return;
    setSelectedRecipeId("");
    setRecipeKey(`${selected.content.recipe_key}-copy`);
    setRecipeLabel(`${selected.content.label} copy`);
    setRecipeDescription(selected.content.description ?? "");
    setRecipeReason("Create an independent Recipe from a reviewed revision");
    setBatchPreflight(null);
    setNotice(`Cloned ${selected.content.label} r${selected.current_revision.revision_no} into an unsaved Recipe draft.`);
  }

  function toggleBatchDocument(id: string): void {
    setBatchDocumentIds((current) => current.includes(id)
      ? current.filter((item) => item !== id)
      : current.length < 500 ? [...current, id] : current);
    setBatchPreflight(null);
  }

  function selectedBatchInputs(): {
    recipe: CommonProcessingRecipeResponse;
    sources: Array<{ document_id: string; revision_id: string }>;
  } | null {
    const recipe = recipes.find((item) => item.processing_recipe_id === selectedRecipeId);
    if (!recipe || recipe.content.lifecycle_state !== "published") {
      setError("Select an exact published Recipe revision before batch preflight.");
      return null;
    }
    const selected = batchDocumentIds.flatMap((id) => {
      const exactRef = selectedTestDataRefs.find((item) => item.id === id);
      if (exactRef) return [exactRef];
      const current = documents.find((item) => item.test_data_document_id === id);
      return current ? [modelingSessionRefFromRecord(current)] : [];
    });
    if (!selected.length) {
      setError("Select at least one exact Test Data revision for the batch.");
      return null;
    }
    return {
      recipe,
      sources: selected.map((item) => ({
        document_id: item.id,
        revision_id: item.revisionId,
      })),
    };
  }

  async function preflightBatch(): Promise<void> {
    const input = selectedBatchInputs();
    if (!input) return;
    setBusy(true);
    setError(null);
    try {
      const result = await preflightCommonProcessingBatch(config, {
        classification: input.recipe.current_revision.classification as DataClassification,
        recipe_id: input.recipe.processing_recipe_id,
        recipe_revision_id: input.recipe.current_revision.id,
        sources: input.sources,
      });
      setBatchPreflight(result.data);
      setNotice(result.data.compatible
        ? `Preflight accepted ${result.data.members.length} exact inputs.`
        : "Preflight found incompatible inputs; execution remains blocked.");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function executeBatch(): Promise<void> {
    const input = selectedBatchInputs();
    if (!input || !batchPreflight?.compatible) {
      setError("Run a successful compatibility preflight before batch execution.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await executeCommonProcessingBatch(config, {
        classification: input.recipe.current_revision.classification as DataClassification,
        label: batchLabel,
        recipe_id: input.recipe.processing_recipe_id,
        recipe_revision_id: input.recipe.current_revision.id,
        sources: input.sources,
        change_reason: "Execute exact published Processing Recipe batch",
      });
      const refreshed = await listCommonProcessingBatches(config);
      setBatches(refreshed.data.items);
      setNotice(`Batch ${result.data.status}: ${result.data.attempts.length} append-only attempts recorded.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function retryFailedBatch(batchId: string): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const result = await retryFailedCommonProcessingBatch(config, batchId);
      const refreshed = await listCommonProcessingBatches(config);
      setBatches(refreshed.data.items);
      setNotice(`Retry completed with batch status ${result.data.status}; earlier attempts remain immutable.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  function recipeContent(
    profile: CommonMappingProfileResponse,
    lifecycleState: "draft" | "published",
  ): CommonProcessingRecipeContent {
    return {
      recipe_key: recipeKey,
      label: recipeLabel,
      description: recipeDescription.trim() || null,
      mapping_profile_id: profile.mapping_profile_id,
      mapping_profile_revision_id: profile.current_revision.id,
      mapping_profile_sha256: profile.current_revision.content_hash,
      steps: serverProcessingSteps(JSON.parse(stepsText) as CommonProcessingStep[]),
      lifecycle_state: lifecycleState,
    };
  }

  async function saveRecipe(): Promise<void> {
    const profile = profiles.find((item) => item.mapping_profile_id === selectedProfileId);
    if (!profile) {
      setError("Select and save one exact Mapping Profile before saving a Recipe.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const selected = recipes.find((item) => item.processing_recipe_id === selectedRecipeId);
      const content = recipeContent(profile, "draft");
      const result = selected
        ? await reviseCommonProcessingRecipe(
            config,
            selected.processing_recipe_id,
            `"revision:${selected.current_revision.revision_no}:sha256:${selected.current_revision.content_hash}"`,
            { content, change_reason: recipeReason },
          )
        : await createCommonProcessingRecipe(config, {
            classification: profile.current_revision.classification as DataClassification,
            content,
            change_reason: recipeReason,
          });
      const refreshed = await listCommonProcessingRecipes(config);
      setRecipes(refreshed.data.items);
      setSelectedRecipeId(result.data.processing_recipe_id);
      savedSteps.current = stepsText;
      undoSteps.current = [];
      redoSteps.current = [];
      setNotice(`Saved reusable Recipe revision ${result.data.current_revision.revision_no} as draft.`);
    } catch (caught) {
      if (caught instanceof ApiError && (caught.status === 409 || caught.status === 412) && selectedRecipeId) {
        setRecipeConflict({ recipeId: selectedRecipeId });
        setError(null);
      } else {
        setError(caught instanceof SyntaxError ? `Invalid Recipe step JSON: ${caught.message}` : errorMessage(caught));
      }
    } finally {
      setBusy(false);
    }
  }

  async function resolveRecipeConflict(action: "reload" | "keep-local"): Promise<void> {
    if (!recipeConflict) return;
    setBusy(true);
    setError(null);
    try {
      const refreshed = await listCommonProcessingRecipes(config);
      const current = refreshed.data.items.find((item) => item.processing_recipe_id === recipeConflict.recipeId);
      if (!current) throw new Error("The conflicted Recipe is no longer available in this project.");
      setRecipes(refreshed.data.items);
      if (action === "reload") {
        setRecipeKey(current.content.recipe_key);
        setRecipeLabel(current.content.label);
        setRecipeDescription(current.content.description ?? "");
        replaceSavedSteps(JSON.stringify(current.content.steps, null, 2));
        setSelectedStepIndex(0);
        setRecipeConflict(null);
        setNotice(`Reloaded current Recipe revision ${current.current_revision.revision_no}; the stale local draft was discarded.`);
        return;
      }
      const profile = profiles.find((item) => item.mapping_profile_id === selectedProfileId);
      if (!profile) throw new Error("Select the exact Mapping Profile again before preserving the local draft.");
      const result = await reviseCommonProcessingRecipe(
        config,
        current.processing_recipe_id,
        `"revision:${current.current_revision.revision_no}:sha256:${current.current_revision.content_hash}"`,
        { content: recipeContent(profile, "draft"), change_reason: recipeReason },
      );
      const latest = await listCommonProcessingRecipes(config);
      setRecipes(latest.data.items);
      savedSteps.current = stepsText;
      undoSteps.current = [];
      redoSteps.current = [];
      setRecipeConflict(null);
      setNotice(`Preserved the local draft as Recipe revision ${result.data.current_revision.revision_no}.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function publishRecipe(): Promise<void> {
    const selected = recipes.find((item) => item.processing_recipe_id === selectedRecipeId);
    if (!selected || selected.content.lifecycle_state !== "draft") {
      setError("Select a saved draft Recipe before publishing it.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await reviseCommonProcessingRecipe(
        config,
        selected.processing_recipe_id,
        `"revision:${selected.current_revision.revision_no}:sha256:${selected.current_revision.content_hash}"`,
        {
          content: { ...selected.content, lifecycle_state: "published" },
          change_reason: "Publish reviewed Processing Recipe",
        },
      );
      const refreshed = await listCommonProcessingRecipes(config);
      setRecipes(refreshed.data.items);
      setNotice(`Published Recipe revision ${result.data.current_revision.revision_no}; earlier revisions remain unchanged.`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  function addMethod(method: CommonProcessingMethod): void {
    try {
      const steps = JSON.parse(stepsText) as CommonProcessingStep[];
      const existingIndex = steps.findIndex((step) => step.method_id === method.method_id);
      if (method.method_id === "tensile.toe_zero_intercept" && existingIndex >= 0) {
        setSelectedStepIndex(existingIndex);
        setNotice("Tensile toe compensation is already present in this Recipe draft.");
        return;
      }
      const newStep = { method_id: method.method_id, method_version: method.version, options: defaultOptions(method.method_id) };
      const insertionIndex = method.method_id === "tensile.toe_zero_intercept"
        ? steps.findIndex((step) => step.method_id === "metal.elastic_modulus")
        : -1;
      if (insertionIndex >= 0) steps.splice(insertionIndex, 0, newStep);
      else steps.push(newStep);
      applyDraftSteps(JSON.stringify(steps, null, 2));
      setSelectedStepIndex(insertionIndex >= 0 ? insertionIndex : steps.length - 1);
      setPreview(null);
      setError(null);
    } catch (caught) {
      setError(caught instanceof SyntaxError ? caught.message : errorMessage(caught));
    }
  }

  function updateStepOption(option: string, value: unknown): void {
    const step = configuredSteps[selectedStepIndex];
    updateStepOptions({
      [option]: value,
      ...(step?.method_id === "tensile.toe_zero_intercept"
        && option !== "warning_acknowledged"
        ? { warning_acknowledged: false }
        : {}),
    });
  }

  function updateStepOptions(options: Record<string, unknown>): void {
    try {
      const steps = JSON.parse(stepsText) as CommonProcessingStep[];
      const step = steps[selectedStepIndex];
      if (!step) return;
      steps[selectedStepIndex] = { ...step, options: { ...step.options, ...options } };
      applyDraftSteps(JSON.stringify(steps, null, 2));
    } catch {
      setError("The advanced processing definition is not valid JSON.");
    }
  }

  function removeSelectedStep(): void {
    try {
      const steps = JSON.parse(stepsText) as CommonProcessingStep[];
      steps.splice(selectedStepIndex, 1);
      applyDraftSteps(JSON.stringify(steps, null, 2));
      setSelectedStepIndex(Math.max(0, selectedStepIndex - 1));
      setPreview(null);
    } catch {
      setError("The advanced processing definition is not valid JSON.");
    }
  }

  async function adoptVerifiedMappingProfile(response: CommonMappingProfileResponse): Promise<void> {
    const refreshed = await listCommonMappingProfiles(config);
    const candidate = refreshed.data.items.find((item) => item.mapping_profile_id === response.mapping_profile_id);
    const verified = Boolean(
      candidate
        && candidate.current_revision.id === response.current_revision.id
        && candidate.current_revision.revision_no === response.current_revision.revision_no
        && candidate.current_revision.content_hash === response.current_revision.content_hash
        && stableMappingJson(candidate.content) === stableMappingJson(response.content),
    );
    if (!verified || !candidate) {
      throw new Error("Saved Mapping Profile could not be verified");
    }
    setProfiles(refreshed.data.items);
    setSelectedProfileId(candidate.mapping_profile_id);
    setProfileText(JSON.stringify(candidate.content, null, 2));
    mappingProfileRetry.current = null;
    setMappingProfileRetryPhase(null);
    setNotice(`Saved Mapping Profile revision ${candidate.current_revision.revision_no}.`);
  }

  async function saveProfile(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const content = JSON.parse(profileText) as CommonMappingProfileContent;
      const pendingAppend = mappingProfileRetry.current?.phase === "append" ? mappingProfileRetry.current : null;
      const selected = profiles.find((item) => item.mapping_profile_id === (pendingAppend?.profileId ?? selectedProfileId));
      const etag = selected
        ? pendingAppend?.etag ?? `"revision:${selected.current_revision.revision_no}:sha256:${selected.current_revision.content_hash}"`
        : "";
      const result = selected
        ? await reviseCommonMappingProfile(
            config,
            selected.mapping_profile_id,
            etag,
            { content, change_reason: changeReason },
          )
        : await createCommonMappingProfile(config, { classification, content, change_reason: changeReason });
      if (selected) {
        mappingProfileRetry.current = { phase: "verify", response: result.data, profileId: selected.mapping_profile_id, etag };
        setMappingProfileRetryPhase("verify");
        await adoptVerifiedMappingProfile(result.data);
      } else {
        setProfiles((current) => [...current.filter((item) => item.mapping_profile_id !== result.data.mapping_profile_id), result.data]);
        setSelectedProfileId(result.data.mapping_profile_id);
        setProfileText(JSON.stringify(result.data.content, null, 2));
        setNotice(`Saved Mapping Profile revision ${result.data.current_revision.revision_no}.`);
      }
    } catch (caught) {
      if (caught instanceof SyntaxError) {
        setError(`Invalid profile JSON: ${caught.message}`);
      } else if (mappingProfileRetry.current?.phase === "verify" || caught instanceof Error && caught.message === "Saved Mapping Profile could not be verified") {
        setError("Saved Mapping Profile could not be verified");
        setMappingProfileRetryPhase("verify");
      } else if (selectedProfileId) {
        const selected = profiles.find((item) => item.mapping_profile_id === selectedProfileId);
        if (selected) {
          const etag = `"revision:${selected.current_revision.revision_no}:sha256:${selected.current_revision.content_hash}"`;
          mappingProfileRetry.current = { phase: "append", profileId: selected.mapping_profile_id, etag };
          setMappingProfileRetryPhase("append");
        }
        setError("Mapping Profile revision was not saved");
      } else {
        setError(errorMessage(caught));
      }
    } finally {
      setBusy(false);
    }
  }

  async function retryMappingProfile(): Promise<void> {
    const attempt = mappingProfileRetry.current;
    if (!attempt) return;
    if (attempt.phase === "verify") {
      setBusy(true);
      setError(null);
      try {
        await adoptVerifiedMappingProfile(attempt.response);
      } catch {
        setError("Saved Mapping Profile could not be verified");
        setMappingProfileRetryPhase("verify");
      } finally {
        setBusy(false);
      }
      return;
    }
    await saveProfile();
  }

  async function runPreview(): Promise<void> {
    if (!document && workflowTask !== "fit") {
      setError("Choose a saved dataset before previewing processing.");
      return;
    }
    const shouldSelectLastPreviewStage = workflowTask === "data"
      || workflowTask === "fit"
      || workflowTask === "export";
    if (isProcessTask && !processSourceReady) {
      setError("Restore inputs in Data.");
      return;
    }
    if (workflowTask === "fit" && !fitSourceOutput) {
      setError("Fit requires a saved Process result. Return to Process and save the current result before fitting.");
      return;
    }
    previewAbortController.current?.abort();
    const controller = new AbortController();
    previewAbortController.current = controller;
    const requestNo = exactDocumentGeneration.current + 1;
    exactDocumentGeneration.current = requestNo;
    if (workflowTask === "fit") setVerifiedFitOutputKey(null);
    setPreviewBusy(true);
    setError(null);
    try {
      const draftSteps = JSON.parse(stepsText) as CommonProcessingStep[];
      const result = workflowTask === "fit"
        ? await (async () => {
          const fitStep = draftSteps.find((step) => isFitMethod(step.method_id));
          if (!fitStep || !fitSourceOutput) {
            throw new Error("Fit requires a saved exact Process Output. Return to Process and save the current result before fitting.");
          }
          const source_processing_output: CommonExactRevisionPin = {
            aggregate_id: fitSourceOutput.processing_output_id,
            revision_id: fitSourceOutput.current_revision.id,
          };
          const run = await executeMetalFitRun(config, {
            classification: fitSourceOutput.current_revision.classification,
            source_processing_output,
            fit_step: serverProcessingSteps([fitStep])[0],
            change_reason: "Calculate metal Fit candidates",
          }, controller.signal);
          setMetalFitRunId(run.data.id);
          if (!run.data.preview) {
            throw new Error(run.data.failure_reason ?? "The persisted metal Fit run returned no preview evidence.");
          }
          if (run.data.status !== "succeeded") {
            setNotice(`Calculation failed; persisted run ${run.data.id} retains the failure evidence.`);
            throw new Error(run.data.failure_reason ?? "Metal Fit calculation failed.");
          }
          return { data: run.data.preview, etag: run.etag };
        })()
        : await previewCommonProcessing(config, {
          document: document as Record<string, unknown>,
          mapping_profile: JSON.parse(profileText) as CommonMappingProfileContent,
          steps: serverProcessingSteps(isProcessTask
            ? draftSteps.filter((step) => !isFitMethod(step.method_id))
            : draftSteps),
        }, controller.signal);
      if (exactDocumentGeneration.current !== requestNo) return;
      if (isProcessTask) {
        const verifiedProfile = profiles.find((item) => item.mapping_profile_id === selectedProfileId);
        if (!verifiedProfile || result.data.mapping_profile_sha256 !== verifiedProfile.current_revision.content_hash) {
          throw new Error("Mapping validation changed; review and retry");
        }
      }
      setFitSelection(null);
      onSessionEvent?.({ type: "CHANGE_SELECTION" });
      setPreview(result.data);
      setLastValidPreview(result.data);
      if (isProcessTask) {
        pendingExplicitProcessPreview.current = null;
        if (draftSteps[selectedStepIndex]?.method_id !== "tensile.toe_zero_intercept") {
          preferredStepContext.current = "";
        }
      }
      if (shouldSelectLastPreviewStage) {
        setSelectedStage(result.data.stages.length - 1);
        setSelectedStepIndex(result.data.stages.length - 2);
      }
      setWorkspaceInspector("step");
      setPlotView("pipeline");
      setNotice("Preview ready.");
    } catch (caught) {
      if (caught instanceof Error && caught.name === "AbortError") return;
      setError(caught instanceof SyntaxError ? `Invalid Workbench JSON: ${caught.message}` : errorMessage(caught));
      // The last valid Process preview remains displayed.  The failed
      // response is never promoted to a save input.
    } finally {
      if (exactDocumentGeneration.current === requestNo) {
        setPreviewBusy(false);
        previewAbortController.current = null;
      }
    }
  }

  async function commitOutput(overrides?: {
    label: string;
    reason: string;
    nextTask?: ModelingWorkflowTask;
    fitDecision?: ReturnType<typeof buildFitDecisionSnapshot>;
  }): Promise<CommonProcessingOutputResponse | null> {
    const draftSteps = JSON.parse(stepsText) as CommonProcessingStep[];
    const modulus = draftSteps.find((step) => step.method_id === "metal.elastic_modulus");
    const workup = draftSteps.find((step) => step.method_id === "metal.engineering_to_true_plastic");
    if (modulus?.options.method === "manual" && (numberOption(modulus, "manual_modulus_pa") <= 0 || !String(modulus.options.manual_modulus_unit ?? "").trim() || !String(modulus.options.manual_modulus_reason ?? "").trim())) {
      setError("A manual Young's modulus needs its value, unit, and engineering reason before saving processed curves.");
      return null;
    }
    if (workup?.options.necking_policy === "manual_index" && (numberOption(workup, "manual_necking_index") < 0 || !String(workup.options.manual_necking_reason ?? "").trim())) {
      setError("A manual necking boundary needs its value, unit, and engineering reason before saving processed curves.");
      return null;
    }
    const fitSource = overrides?.fitDecision ? fitSourceOutput : undefined;
    const source = documents.find((item) => item.test_data_document_id === selectedDocumentId);
    const sourceRef = fitSource?.source_document
      ?? (() => {
        const ref = selectedTestDataRefsRef.current.find((item) => item.id === selectedDocumentId);
        return ref ? { aggregate_id: ref.id, revision_id: ref.revisionId } : undefined;
      })();
    const profile = profiles.find((item) => item.mapping_profile_id === selectedProfileId);
    const profilePin = fitSource?.mapping_profile
      ?? (profile ? { aggregate_id: profile.mapping_profile_id, revision_id: profile.current_revision.id } : undefined);
    const outputClassification = fitSource?.current_revision.classification
      ?? source?.current_revision.classification;
    if (!preview || (!fitSource && (!source || !exactSourceLoaded)) || !sourceRef || !profilePin) {
      setError(fitSource
        ? "The exact Process Output source is unavailable. Restore that saved result before committing Fit."
        : "Preview an exact Test Data revision with a saved Mapping Profile before commit.");
      return null;
    }
    if (!outputClassification) {
      setError("The selected source has no classification for commit.");
      return null;
    }
    if (fitSource
      ? preview.mapping_profile_sha256 !== fitSource.mapping_profile_sha256
        || preview.source_document_sha256 !== fitSource.source_document_sha256
      : !profile || preview.mapping_profile_sha256 !== profile.current_revision.content_hash) {
      setError("The preview differs from the selected exact input/profile. Save changes and preview again.");
      return null;
    }
    if (!fitSource && source && profile && source.current_revision.classification !== profile.current_revision.classification) {
      setError("Exact Test Data and Mapping Profile revisions must share classification.");
      return null;
    }
    setBusy(true);
    if (overrides?.fitDecision) setVerifiedFitOutputKey(null);
    setError(null);
    try {
      const result = await commitCommonProcessingOutput(config, {
        classification: outputClassification as DataClassification,
        label: overrides?.label ?? outputLabel,
        source_document: {
          aggregate_id: sourceRef.aggregate_id,
          revision_id: sourceRef.revision_id,
        },
        mapping_profile: profilePin,
        steps: serverProcessingSteps(
          isProcessTask && !overrides?.fitDecision
            ? draftSteps.filter((step) => !isFitMethod(step.method_id))
            : draftSteps,
        ),
        change_reason: overrides?.reason ?? outputReason,
        workup_overrides: workupOverridesFromSteps(draftSteps),
        ...(overrides?.fitDecision ? { fit_decision: overrides.fitDecision } : {}),
        ...(fitSource ? {
          source_processing_output: {
            aggregate_id: fitSource.processing_output_id,
            revision_id: fitSource.current_revision.id,
          },
        } : {}),
      });
      const refreshed = await listCommonProcessingOutputs(config);
      setOutputs(refreshed.data.items);
      setNotice(overrides?.fitDecision
        ? "New immutable Fit Output saved and current; earlier revisions remain. Modeling Export is separate and has not started."
        : "Processed result saved and current; earlier results remain in history.");
      updateLocalCurrentOutput({ id: result.data.processing_output_id, revisionId: result.data.current_revision.id });
      if (overrides?.fitDecision) {
        setVerifiedFitOutputKey(`${result.data.processing_output_id}:${result.data.current_revision.id}`);
      }
      const outputRef = {
        id: result.data.processing_output_id,
        revisionId: result.data.current_revision.id,
        label: result.data.label,
        revisionNo: result.data.current_revision.revision_no,
      };
      // A Processing Output is immutable processing evidence.  It is not, by itself,
      // a candidate selection, review, approval, or release.  UXC-04's decision
      // snapshot needs a dedicated typed API before it may become a session pointer.
      onSessionChange?.({ processingOutput: outputRef });
      if (overrides?.fitDecision) onSessionEvent?.({ type: "SELECT_CANDIDATE", selection: outputRef });
      if (overrides?.nextTask) openWorkflowTask(overrides.nextTask);
      return result.data;
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid step JSON: ${caught.message}` : errorMessage(caught));
    } finally {
      setBusy(false);
    }
    return null;
  }

  async function saveSelectedFitOutput(): Promise<void> {
    const fitStep = (JSON.parse(stepsText) as CommonProcessingStep[]).find(
      (step) => isFitMethod(step.method_id),
    );
    if (!fitStep) {
      setError("Add and calculate one fit method before saving a selected output.");
      return;
    }
    if (!fitSelection || !fitSelection.reason.trim() || (fitSelection.warning && !fitSelection.warningAcknowledged)) {
      setError("Select one calculated candidate, enter the engineering selection reason, and acknowledge its warning before saving.");
      return;
    }
    const fitDecision = activeStage && preview
      ? buildFitDecisionSnapshot(
        fitSelection,
        fitStep,
        activeStage,
        preview.independent_quantity,
      )
      : null;
    if (!fitDecision) {
      setError("The selected model no longer matches the recomputed fit evidence. Run fit again, then select it again.");
      return;
    }
    await commitOutput({
      label: `${material?.current_revision.content.name ?? modelingTrack} · ${fitDecisionIdentityLabel(fitSelection)} selected candidate`,
      reason: fitSelection.reason.trim(),
      fitDecision,
    });
  }

  async function downloadOutput(output: CommonProcessingOutputResponse): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const result = await downloadCommonProcessingOutput(config, output.processing_output_id);
      const url = URL.createObjectURL(result.data.blob);
      const anchor = window.document.createElement("a");
      anchor.href = url;
      anchor.download = result.data.filename;
      anchor.click();
      URL.revokeObjectURL(url);
      setNotice(`Downloaded exact Processing Output ${output.output_sha256.slice(0, 12)}…`);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  function focusExactDocument(item: CanonicalTestDataDocumentResponse): void {
    const exactRef = selectedTestDataRefsRef.current.find((ref) => ref.id === item.test_data_document_id)
      ?? modelingSessionRefFromRecord(item);
    if (isProcessTask) {
      if (!selectedTestDataRefsRef.current.some((ref) => exactRefKey(ref) === exactRefKey(exactRef))) {
        const nextRefs = [...selectedTestDataRefsRef.current, exactRef];
        selectedTestDataRefsRef.current = nextRefs;
        setSelectedTestDataRefs(nextRefs);
        setVisibleDocumentIds((current) => current.includes(exactRefKey(exactRef)) ? current : [...current, exactRefKey(exactRef)]);
      }
      onSessionEvent?.({ type: "PIN_TEST_DATA", testData: exactRef });
    }
    setPlotView("pipeline");
    void loadDocument(item.test_data_document_id, exactRef.revisionId);
  }

  async function loadSavedResult(output: CommonProcessingOutputResponse): Promise<void> {
    setSavedResultStates((current) => ({ ...current, [output.processing_output_id]: { status: "loading" } }));
    try {
      const result = await downloadCommonProcessingOutput(config, output.processing_output_id);
      const { parseSavedProcessingOutput } = await import("./features/modeling/ui/stages/process/modeling-process-panel");
      const scalarPa = parseSavedProcessingOutput(await result.data.blob.text(), output, [
        output.source_document.aggregate_id,
        output.source_document.revision_id,
        output.mapping_profile.aggregate_id,
        output.mapping_profile.revision_id,
      ]);
      setSavedResultStates((current) => ({ ...current, [output.processing_output_id]: { status: "ready", scalarPa } }));
    } catch {
      setSavedResultStates((current) => ({
        ...current,
        [output.processing_output_id]: {
          status: "error",
        },
      }));
    }
  }

  function useSavedSettings(output: CommonProcessingOutputResponse): void {
    const selectedMethodId = configuredSteps[selectedStepIndex]?.method_id;
    const nextSteps = JSON.stringify(output.steps, null, 2);
    applyDraftSteps(nextSteps, true, true);
    setOutputLabel(output.label);
    setOutputReason(`Re-run ${output.label} with the selected exact source`);
    if (output.source_processing_output) {
      updateLocalCurrentOutput({ id: output.source_processing_output.aggregate_id, revisionId: output.source_processing_output.revision_id });
    }
    const restoredMethodIndex = selectedMethodId
      ? output.steps.findIndex((step) => step.method_id === selectedMethodId)
      : -1;
    setSelectedStepIndex(restoredMethodIndex >= 0
      ? restoredMethodIndex
      : Math.max(0, output.steps.findIndex((step) => !isFitMethod(step.method_id))));
    setNotice("Saved Process settings restored as a new draft. Preview again before saving.");
  }

  function toggleEnsembleDocument(id: string): void {
    const item = documents.find((candidate) => candidate.test_data_document_id === id);
    if (workflowTask !== "data") {
      const included = ensembleDocumentIds.includes(id);
      const nextIncluded = included
        ? ensembleDocumentIds.filter((itemId) => itemId !== id)
        : ensembleDocumentIds.length < 100 ? [...ensembleDocumentIds, id] : ensembleDocumentIds;
      setEnsembleDocumentIds(nextIncluded);
      setEnsemblePreview(null);
      setFitSelection(null);
      const focused = selectedTestDataRefsRef.current.find((ref) => ref.id === selectedDocumentId);
      if (isProcessTask && included && focused?.id === id) {
        const remaining = selectedTestDataRefsRef.current.filter((ref) => ref.id !== id);
        const nextFocus = remaining[0];
        if (nextFocus) {
          onSessionEvent?.({ type: "PIN_TEST_DATA", testData: nextFocus });
          setSelectedDocumentId(nextFocus.id);
          void loadDocument(nextFocus.id, nextFocus.revisionId);
        } else {
          onSessionEvent?.({ type: "PIN_TEST_DATA" });
          clearExactDocumentBinding();
          setSelectedDocumentId("");
        }
        onSessionEvent?.({ type: "SET_TEST_DATA_SELECTION", selectedTestDataRefs: remaining });
        selectedTestDataRefsRef.current = remaining;
        setSelectedTestDataRefs(remaining);
      } else {
        // P-01a keeps Process output current when membership changes; the
        // selection event only clears downstream Fit/Export decisions.
        onSessionEvent?.({ type: "CHANGE_SELECTION" });
      }
      return;
    }
    const currentRefs = selectedTestDataRefsRef.current;
    const linkedRef = currentRefs.find((ref) => ref.id === id);
    const nextRefs = linkedRef
      ? currentRefs
      : item && currentRefs.length < 100
        ? [...currentRefs, modelingSessionRefFromRecord(item)]
        : currentRefs;
    if (!linkedRef && nextRefs !== currentRefs) {
      selectedTestDataRefsRef.current = nextRefs;
      setSelectedTestDataRefs(nextRefs);
    }
    const comparisonRef = linkedRef ?? (nextRefs !== currentRefs ? nextRefs[nextRefs.length - 1] : undefined);
    if (comparisonRef) {
      const comparisonKey = exactRefKey(comparisonRef);
      setVisibleDocumentIds((current) => current.includes(comparisonKey)
        ? current.filter((key) => key !== comparisonKey)
        : [...current, comparisonKey]);
    }
    setEnsemblePreview(null);
    // Data-stage comparison is graph/session presentation state. It does not
    // change the one exact Test Data source sent to Process and therefore must
    // not invalidate Process, Fit, or Export pointers.
  }

  // Keep the Data rail's compact JSX callback readable while preserving the
  // existing Include behavior for every other Modeling stage.
  function toggleEnsemble(id: string): void {
    toggleEnsembleDocument(id);
  }

  async function runEnsemblePreview(): Promise<void> {
    const linkedRefs = selectedTestDataRefsRef.current;
    const primaryRef = linkedRefs.find((ref) => ref.id === selectedDocumentId);
    const analysisRefs = [primaryRef, ...linkedRefs.filter((ref) => ref.id !== selectedDocumentId)]
      .filter((ref): ref is ModelingSessionRecordRef => Boolean(ref));
    if (analysisRefs.length < 2) {
      setError("Add a comparison curve in Data before calculating replicate statistics.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const downloads = await Promise.all(analysisRefs.map((ref) =>
        downloadCanonicalTestDataDocument(config, ref.id, ref.revisionId)));
      const canonicalDocuments = await Promise.all(downloads.map(async (item) =>
        JSON.parse(await item.data.blob.text()) as Record<string, unknown>));
      const preprocessingSteps = (JSON.parse(stepsText) as CommonProcessingStep[]).filter(
        (step) => step.method_id.startsWith("rows.") || step.method_id.startsWith("curve."),
      );
      const result = await previewCommonProcessingEnsemble(config, {
        documents: canonicalDocuments,
        mapping_profile: JSON.parse(profileText) as CommonMappingProfileContent,
        preprocessing_steps: preprocessingSteps,
        alignment: {
          point_count: ensemblePointCount,
          domain_policy: "intersection",
          extrapolation: "reject",
        },
      });
      setEnsemblePreview(result.data);
      setPlotView("ensemble");
      setNotice(`Aligned ${result.data.members.length} immutable curves; every member remains visible.`);
    } catch (caught) {
      setError(caught instanceof SyntaxError ? `Invalid ensemble JSON: ${caught.message}` : errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  // A Process-originated draft invalidates the promotable preview, but the
  // last server-valid graph remains visible while the engineer explicitly
  // previews that draft. Keep that continuity when navigating through Fit or
  // Export; only a successful Process preview replaces the retained graph.
  const graphPreview = preview
    ?? ((isProcessTask || pendingExplicitProcessPreview.current) ? lastValidPreview : null);
  const activeStage = graphPreview?.stages[selectedStage] ?? null;
  const baseStage = graphPreview?.stages[0] ?? null;
  // Data review must not depend on a saved Mapping Profile. ModelingDataIntake
  // already asks the server to read each exact Test Data revision with the
  // current in-memory mapping contract. Use that observed preview as the plot
  // frame until the engineer deliberately enters the Process workflow.
  const focusedObservedCurve = observedCurves.find(
    (curve) => curve.id.startsWith(`${selectedDocumentId}:`),
  ) ?? observedCurves[0];
  const dataObservedCurves = dataComparisonOpen
    ? observedCurves
    : focusedObservedCurve
      ? [focusedObservedCurve]
      : [];
  const observedDataPreview = focusedObservedCurve?.preview ?? null;
  const dataGraphPreview = graphPreview && activeStage && baseStage
    ? graphPreview
    : observedDataPreview;
  const dataActiveStage = graphPreview && activeStage && baseStage
    ? activeStage
    : observedDataPreview?.stages[0] ?? null;
  const dataBaseStage = graphPreview && activeStage && baseStage
    ? baseStage
    : observedDataPreview?.stages[0] ?? null;
  const configuredSteps = useMemo(() => {
    try {
      return JSON.parse(stepsText) as CommonProcessingStep[];
    } catch {
      return [];
    }
  }, [stepsText]);
  const activeConfiguredStep = activeStage && activeStage.ordinal > 0
    ? configuredSteps[activeStage.ordinal - 1]
    : undefined;
  const hasGovernedDocuments = useMemo(
    () => documents.some((item) => Boolean(item.governed_source)),
    [documents],
  );
  const dataTrackDocuments = useMemo(
    () => documents.filter((item) => documentMatchesDataTrack(item, modelingTrack)
      && modelingDataDocumentMatchesMaterialContext(item, material, materialState)),
    [documents, material, materialState, modelingTrack],
  );
  const trackDocuments = useMemo(
    () => documents.filter((item) => documentMatchesTrack(item, modelingTrack)
      && (isProcessTask && selectedTestDataRefs.some((ref) => ref.id === item.test_data_document_id)
        ? modelingDataDocumentMatchesMaterialContext(item, material, materialState)
        : modelingDocumentMatchesMaterialContext(item, material, materialState, hasGovernedDocuments))),
    [documents, hasGovernedDocuments, material, materialState, modelingTrack, selectedTestDataRefs, workflowTask],
  );
  // Fit is downstream of Process: bridge the exact refs selected in the
  // Process workspace into its rail, even when the library's current head is
  // on a newer Material/State revision.  The visible row still comes from the
  // server document identity, while `selectedTestDataRefs` supplies the exact
  // revision requested by the session.  Never broaden this bridge to the
  // unpinned current-head list.
  const fitTrackDocuments = useMemo(() => {
    if (workflowTask !== "fit") return [];
    const selectedIds = new Set(selectedTestDataRefs.map((ref) => ref.id));
    return documents.filter((item) => selectedIds.has(item.test_data_document_id)
      && documentMatchesTrack(item, modelingTrack)
      && modelingDataDocumentMatchesMaterialContext(item, material, materialState));
  }, [documents, material, materialState, modelingTrack, selectedTestDataRefs, workflowTask]);
  const stageDocuments = workflowTask === "data"
    ? dataTrackDocuments
    : workflowTask === "fit"
      ? fitTrackDocuments
      : trackDocuments;
  useEffect(() => {
    // Preserve the established full document title for keyboard/browser users;
    // the specimen and exact revision remain visible in the two-line identity
    // rather than being tooltip-only.
    window.document.querySelectorAll<HTMLButtonElement>(".curve-row-label").forEach((button) => {
      const label = button.querySelector("strong")?.textContent?.trim();
      const item = label ? stageDocuments.find((candidate) => curveDisplayName(candidate) === label) : undefined;
      if (item) button.title = `${item.document_key} · ${item.specimen_id} · revision r${item.current_revision.revision_no}`;
    });
  }, [stageDocuments, selectedTestDataRefs]);
  const selectedTrackDocument = stageDocuments.find(
    (item) => item.test_data_document_id === selectedDocumentId,
  );
  const selectedSourceRef = selectedTestDataRefs.find((ref) => ref.id === selectedDocumentId);
  // Keep the normal Process surface on the user-facing specimen identity. The
  // session ref still supplies the exact pinned revision; the internal
  // document key remains available to Evidence/Advanced surfaces and title
  // attributes, but must not replace the focused specimen here.
  const selectedSourceKey = selectedSourceRef ? exactRefKey(selectedSourceRef) : null;
  const exactSourceLoaded = Boolean(selectedSourceKey && loadedExactRefKey.current === selectedSourceKey && document);
  const processSourceIdentity = selectedSourceRef
    ? selectedTrackDocument ? curveDisplayName(selectedTrackDocument) : "Selected Test Data"
    : "";
  const selectedProfile = profiles.find((item) => item.mapping_profile_id === selectedProfileId);
  const processSourceReady = isProcessTask
    ? Boolean(selectedProfile && exactSourceLoaded)
    : true;
  const processBlocked = !processSourceReady;
  const matchingSavedOutputs = useMemo(
    () => selectedSourceRef && selectedProfile
      ? outputs.filter((output) => {
        const exactSourceAndProfile = output.source_document.aggregate_id === selectedSourceRef.id
          && output.source_document.revision_id === selectedSourceRef.revisionId
          && output.mapping_profile.aggregate_id === selectedProfile.mapping_profile_id
          && output.mapping_profile.revision_id === selectedProfile.current_revision.id;
        return exactSourceAndProfile
          && (!isProcessTask || !output.steps.some((step) => isFitMethod(step.method_id)));
      })
      : [],
    [isProcessTask, outputs, selectedProfile, selectedSourceRef],
  );
  const exactSessionOutput = useMemo(() => initialSession?.processingOutput
    ? outputs.find((output) => output.processing_output_id === initialSession.processingOutput?.id
      && output.current_revision.id === initialSession.processingOutput.revisionId)
    : undefined, [initialSession?.processingOutput, outputs]);
  const fitSourceOutput = useMemo(() => {
    if (workflowTask !== "fit" && workflowTask !== "export") return undefined;
    const pinned = exactSessionOutput?.source_processing_output;
    if (pinned) {
      return outputs.find((output) => output.processing_output_id === pinned.aggregate_id
        && output.current_revision.id === pinned.revision_id
        && !output.steps.some((step) => isFitMethod(step.method_id)));
    }
    const local = localCurrentOutput
      ? outputs.find((output) => output.processing_output_id === localCurrentOutput.id
        && output.current_revision.id === localCurrentOutput.revisionId)
      : undefined;
    if (local && !local.steps.some((step) => isFitMethod(step.method_id))) return local;
    const session = initialSession?.processingOutput
      ? outputs.find((output) => output.processing_output_id === initialSession.processingOutput?.id
        && output.current_revision.id === initialSession.processingOutput.revisionId)
      : undefined;
    return session && !session.steps.some((step) => isFitMethod(step.method_id)) ? session : undefined;
  }, [exactSessionOutput, initialSession?.processingOutput, localCurrentOutput, outputs, workflowTask]);
  const currentFitOutput = useMemo(() => {
    if (workflowTask !== "fit" && workflowTask !== "export") return undefined;
    if (exactSessionOutput?.steps.some((step) => isFitMethod(step.method_id))) return exactSessionOutput;
    if (localCurrentOutput) {
      const local = outputs.find((output) => output.processing_output_id === localCurrentOutput.id
        && output.current_revision.id === localCurrentOutput.revisionId);
      if (local?.steps.some((step) => isFitMethod(step.method_id))) return local;
    }
    return undefined;
  }, [exactSessionOutput, localCurrentOutput, outputs, workflowTask]);
  const fitHistoryExists = workflowTask === "fit"
    && outputs.some((output) => output.steps.some((step) => isFitMethod(step.method_id)));
  const fitPreviewUsable = workflowTask === "fit"
    && Boolean(preview?.stages.some((stage) => isFitMethod(stage.method_id)));
  const verifiedSavedFit = Boolean(
    currentFitOutput
      && verifiedFitOutputKey === `${currentFitOutput.processing_output_id}:${currentFitOutput.current_revision.id}`
      && !fitRestoreError,
  );
  const fitState = fitSurfaceState({
    previewBusy,
    usablePreview: fitPreviewUsable,
    verifiedSavedFit,
    fitHistoryExists: Boolean(fitSourceOutput) && fitHistoryExists,
  });
  const fitStateLabel = FIT_SURFACE_STATE_LABELS[fitState];
  useEffect(() => {
    if ((workflowTask !== "fit" && workflowTask !== "export") || !exactSessionOutput?.steps.some((step) => isFitMethod(step.method_id)) || !fitSourceOutput) return;
    // The complete identity is intentionally conservative.  In particular,
    // serializing both output objects (rather than selecting a few fields)
    // keeps new metadata from joining an older request, while the retry
    // generation makes an explicit retry a distinct request.
    const restoreIdentity = deterministicSerialize([
      fitRestoreGeneration,
      config.baseUrl,
      config.accessToken,
      exactSessionOutput,
      fitSourceOutput,
    ]);
    if (fitRestoreSettledKey.current === restoreIdentity) return;
    const requestGeneration = fitRestoreRequestGeneration.current + 1;
    fitRestoreRequestGeneration.current = requestGeneration;
    let active = true;
    let inFlight = fitRestoreInFlight.current;
    if (!inFlight || inFlight.identity !== restoreIdentity) {
      const promise = (async (): Promise<ExactFitRestore> => {
        const result = await downloadCommonProcessingOutput(config, exactSessionOutput.processing_output_id);
        const { parseExactSavedFitOutput, readVerifiedExactOutput } = await import("./modeling-fit-output");
        return parseExactSavedFitOutput(
          await readVerifiedExactOutput(result, exactSessionOutput.output_sha256),
          exactSessionOutput,
          fitSourceOutput,
        );
      })();
      inFlight = { identity: restoreIdentity, promise };
      fitRestoreInFlight.current = inFlight;
      // Only the exact promise that created the ref may clear it.  A newer
      // identity can start while this request is pending; its ref must remain
      // intact when the older request settles.
      void promise.then(
        () => {
          if (fitRestoreInFlight.current?.promise === promise) fitRestoreInFlight.current = null;
        },
        () => {
          if (fitRestoreInFlight.current?.promise === promise) fitRestoreInFlight.current = null;
        },
      );
    }
    const promise = inFlight.promise;
    void promise.then(
      (restored) => {
        if (!active || fitRestoreRequestGeneration.current !== requestGeneration) return;
        fitRestoreSettledKey.current = restoreIdentity;
        setPreview(restored.preview);
        setLastValidPreview(restored.preview);
        setFitSelection(restored.selection);
        setVerifiedFitOutputKey(`${exactSessionOutput.processing_output_id}:${exactSessionOutput.current_revision.id}`);
        setFitRestoreError(null);
        setSelectedStage(restored.preview.stages.length - 1);
        setSelectedStepIndex(restored.preview.stages.length - 2);
        const restoredOutputIsLocalCurrent = localCurrentOutputRef.current?.id === exactSessionOutput.processing_output_id
          && localCurrentOutputRef.current.revisionId === exactSessionOutput.current_revision.id;
        if (!restoredOutputIsLocalCurrent) {
          setNotice("Saved immutable Fit Output restored with its exact Process source and decision.");
        }
        setError(null);
      },
      (caught) => {
        if (!active || fitRestoreRequestGeneration.current !== requestGeneration) return;
        // Preserve the last valid graph/input/selection.  A tampered or
        // unreadable saved result is never replaced by a raw/latest fallback.
        fitRestoreSettledKey.current = restoreIdentity;
        setVerifiedFitOutputKey(null);
        setFitRestoreError(errorMessage(caught));
        setError(`Saved Fit result unavailable · Retry exact saved result. ${errorMessage(caught)}`);
      },
    );
    return () => { active = false; };
  }, [config.accessToken, config.baseUrl, exactSessionOutput, fitRestoreGeneration, fitSourceOutput, workflowTask]);
  const exactExportPrerequisites = exportPrerequisites({
    session: initialSession,
    material,
    materialState,
    testData: selectedTrackDocument,
    output: exactSessionOutput,
  });
  const exactExportSourceReady = exactExportPrerequisites.every((item) => item.status === "current");
  useEffect(() => {
    // The list request resolves asynchronously.  Do not reconcile a restored
    // exact session against the transient empty list; doing so would erase the
    // linked revisions before the Library rows arrive.
    if (!documents.length) return;
    // The documents request can resolve before the Material/State context
    // request.  In that window the aggregate-aware Data filter cannot decide
    // whether a restored exact revision belongs to this session.  Waiting for
    // both context records preserves the user's pinned refs until the real
    // Library surface is ready; explicit family/context changes still clear
    // refs through their reset paths above.
    if ((workflowTask === "data" || isProcessTask) && (!material || !materialState)) return;
    const enteredStage = previousWorkflowTask.current !== workflowTask;
    previousWorkflowTask.current = workflowTask;
    const exactIds = new Set(stageDocuments.map((item) => item.test_data_document_id));
    const exactKeys = new Set(stageDocuments.map((item) => modelingSessionRecordKey(item.test_data_document_id, item.current_revision.id)));
    // Fit/Export intentionally expose revision-strict stage lists.  A source
    // selected in Data/Process can be valid for the shared Process context
    // while absent from those lists; stage navigation must not turn that
    // visibility difference into a global source reset.  Data selection,
    // family/material changes, and exact-read failures still use their own
    // explicit invalidation paths above.
    const preserveSharedExactBinding = (workflowTask === "fit" || workflowTask === "export")
      && (Boolean(selectedDocumentId) || selectedTestDataRefsRef.current.length > 0);
    if (!preserveSharedExactBinding && !intakePreviewActive.current && selectedDocumentId && !exactIds.has(selectedDocumentId)) {
      clearExactDocumentBinding();
      setSelectedDocumentId("");
    }
    if (workflowTask === "data") {
      setEnsembleDocumentIds((current) => current.filter((id) => exactIds.has(id)));
    } else if (isProcessTask) {
      setEnsembleDocumentIds((current) => {
        const compatible = current.filter((id) => exactIds.has(id));
        // Preserve the Data-stage membership decision, including an empty
        // decision. The historical bridge above makes selected older
        // revisions compatible by aggregate identity, so entering Process
        // must not replace them with the first two current rows.
        if (compatible.length || selectedTestDataRefsRef.current.length) return compatible;
        return enteredStage ? stageDocuments.slice(0, 2).map((item) => item.test_data_document_id) : compatible;
      });
    }
    if (workflowTask === "data" || isProcessTask) {
      setVisibleDocumentIds((current) => {
        const historicalKeys = selectedTestDataRefsRef.current
          .filter((ref) => exactIds.has(ref.id))
          .map(exactRefKey);
        const allowedKeys = new Set([...exactKeys, ...historicalKeys]);
        return current.filter((id) => allowedKeys.has(id));
      });
      setBatchDocumentIds((current) => {
        const compatible = current.filter((id) => exactIds.has(id));
        return compatible.length ? compatible : stageDocuments.slice(0, 2).map((item) => item.test_data_document_id);
      });
    }
    const currentRefs = selectedTestDataRefsRef.current;
    const exactKeysForRefs = new Set(currentRefs.map(exactRefKey));
    const kept = currentRefs.filter((ref) => exactIds.has(ref.id));
    const nextRefs = workflowTask === "fit" || workflowTask === "export"
      ? currentRefs
      : kept.length || workflowTask === "data" || isProcessTask || !stageDocuments.length
        ? kept
        : stageDocuments.slice(0, 2).map(modelingSessionRefFromRecord).filter((ref) => !exactKeysForRefs.has(exactRefKey(ref)));
    const refsChanged = JSON.stringify(nextRefs) !== JSON.stringify(currentRefs);
    if (refsChanged) {
      selectedTestDataRefsRef.current = nextRefs;
      setSelectedTestDataRefs(nextRefs);
    }
  }, [modelingTrack, selectedDocumentId, stageDocuments, workflowTask]);

  const selectedConfiguredStep = configuredSteps[selectedStepIndex] ?? null;
  const selectedConfiguredStage = graphPreview?.stages.find(
    (stage) => stage.ordinal === selectedStepIndex + 1
      && stage.method_id === selectedConfiguredStep?.method_id,
  );
  const toeWarningSaveBlocked = Boolean(preview && configuredSteps.some((step, index) => (
    step.method_id === "tensile.toe_zero_intercept"
      && step.options.warning_acknowledged !== true
      && preview.stages[index + 1]?.method_id === step.method_id
      && preview.stages[index + 1].diagnostics.some((item) => item.startsWith("toe.warning."))
  )));
  const stepEntries = configuredSteps.map((step, index) => ({ step, index }));
  const fitStepEntry = stepEntries.find(({ step }) => isFitMethod(step.method_id));
  const fitDecisionReady = Boolean(
    preview
    && activeStage
    && isFitMethod(activeStage.method_id)
    && activeStage.method_id === fitStepEntry?.step.method_id
    && fitSelection
    && fitSelection.reason.trim()
    && (!fitSelection.warning || fitSelection.warningAcknowledged),
  );
  const visibleStepEntries = stepEntries
    .filter(({ step }) => workflowTask === "data"
      ? false
      : isProcessTask
        ? !isFitMethod(step.method_id)
        : true);
  const fitRailEntries = workflowTask === "fit" && modelingTrack === "metal"
    ? [
      ["rows.sort_unique", "Sort duplicate x"],
      ["metal.engineering_to_true_plastic", "True/plastic conversion"],
      ["metal.necking_candidate", "Necking boundary"],
      ["metal.hardening_fit_extrapolate", "Hardening fit"],
    ].flatMap(([methodId, label]) => {
      const entry = stepEntries.find(({ step }) => step.method_id === methodId);
      return entry ? [{ ...entry, label }] : [];
    })
    : visibleStepEntries.map((entry) => ({ ...entry, label: methods.find((method) => method.method_id === entry.step.method_id)?.label ?? methodDisplayName(entry.step.method_id) }));
  const displayedRailEntries = (workflowTask === "fit" ? fitRailEntries : visibleStepEntries.map((entry) => ({
    ...entry,
    label: methods.find((method) => method.method_id === entry.step.method_id)?.label ?? methodDisplayName(entry.step.method_id),
    title: undefined,
  }))).map((entry, railIndex) => ({
    ...entry,
    railIndex,
    title: entry.label,
  }));
  const isApprovedMetalFit = workflowTask === "fit" && modelingTrack === "metal";
  const [stageTitle, stageRail] = workflowTask === "data"
    ? ["Select Test Data", "Data sources"]
    : isProcessTask
      ? ["Process Test Data", "Process steps"]
      : workflowTask === "fit"
      ? ["Fit Material Model", "Fit steps"]
        : ["Create Solver Card", "Saved source"];
  const materialDisplayLabel = material?.current_revision.content.material_code?.trim()
    .replace(/^CMP-(?:DEMO-)?/iu, "")
    || material?.current_revision.content.name.trim().replace(/^CMP-(?:DEMO-)?/iu, "")
    || initialSession?.material?.label.replace(/\s+synthetic reference.*$/iu, "")
    || "Current material";
  const selectedTestDisplayLabel = selectedTrackDocument ? curveDisplayName(selectedTrackDocument) : "Select Test Data";
  const stageContextLabel = `${materialDisplayLabel} / ${selectedTestDisplayLabel}`;
  const trackRecipes = useMemo(() => recipes.filter((recipe) => {
    const methodIds = recipe.content.steps.map((step) => step.method_id);
    if (modelingTrack === "metal") return methodIds.some((methodId) => methodId.startsWith("metal."));
    if (modelingTrack === "polymer") return methodIds.some((methodId) => methodId.startsWith("polymer."));
    return !methodIds.some((methodId) => methodId.startsWith("metal.") || methodId.startsWith("polymer."));
  }), [recipes, modelingTrack]);
  const trackRecipeIds = useMemo(
    () => new Set(trackRecipes.map((recipe) => recipe.processing_recipe_id)),
    [trackRecipes],
  );
  const trackBatches = useMemo(
    () => batches.filter((batch) => trackRecipeIds.has(batch.recipe_id)),
    [batches, trackRecipeIds],
  );
  useEffect(() => {
    if (contextResetPending.current) return;
    if (selectedRecipeId || !trackRecipes.length) return;
    const exact = initialSession?.recipe ? trackRecipes.find((recipe) => recipe.processing_recipe_id === initialSession.recipe?.id
      && recipe.current_revision.id === initialSession.recipe.revisionId) : null;
    if (exact) selectRecipe(exact.processing_recipe_id);
  }, [initialSession, selectedRecipeId, trackRecipes]);
  const trackMethods = useMemo(() => methods.filter((method) => {
    const family = method.method_id.split(".")[0];
    if (family === "tensile") return modelingTrack === "metal";
    if (family === "metal") return modelingTrack === "metal";
    if (family === "polymer") return modelingTrack === "polymer";
    return true;
  }), [methods, modelingTrack]);
  const availableMethods = trackMethods.filter((method) => workflowTask === "fit" ? isFitMethod(method.method_id) : !isFitMethod(method.method_id));
  const availableToeMethod = isProcessTask
    && modelingTrack === "metal"
    && !configuredSteps.some((step) => step.method_id === "tensile.toe_zero_intercept")
    ? availableMethods.find((method) => method.method_id === "tensile.toe_zero_intercept")
    : undefined;
  const chart = useMemo(() => ({ width: 1750, height: 420 }), []);
  const dataChart = useMemo(() => ({ width: 1689, height: 660 }), []);
  const sessionContextMatchesLive = Boolean(
    material
    && materialState
    && initialSession?.material?.id === material.material_id
    && initialSession.material.revisionId === material.current_revision.id
    && initialSession.materialState?.id === materialState.material_state_id
    && initialSession.materialState.revisionId === materialState.current_revision.id,
  );
  useEffect(() => {
    const item = stageDocuments.find((candidate) => candidate.test_data_document_id === selectedDocumentId);
    if (contextResetPending.current || !sessionContextMatchesLive || !item) return;
    const selectedRef = selectedTestDataRefs.find((ref) => ref.id === item.test_data_document_id)
      ?? modelingSessionRefFromRecord(item);
    if (initialSession?.testData?.id === selectedRef.id
      && initialSession.testData.revisionId === selectedRef.revisionId
      && initialSession.materialFamily === modelingTrack) return;
    onSessionChange?.({
      materialFamily: modelingTrack,
      testData: selectedRef,
    });
  }, [initialSession, modelingTrack, onSessionChange, selectedDocumentId, selectedTestDataRefs, sessionContextMatchesLive, stageDocuments]);

  useEffect(() => {
    const profile = profiles.find((item) => item.mapping_profile_id === selectedProfileId);
    if (contextResetPending.current || !sessionContextMatchesLive || !profile || !selectedDocumentId) return;
    if (initialSession?.mappingProfile?.id === profile.mapping_profile_id
      && initialSession.mappingProfile.revisionId === profile.current_revision.id) return;
    onSessionChange?.({ mappingProfile: {
      id: profile.mapping_profile_id,
      revisionId: profile.current_revision.id,
      label: profile.content.label,
      revisionNo: profile.current_revision.revision_no,
    } });
  }, [initialSession, onSessionChange, profiles, selectedDocumentId, selectedProfileId, sessionContextMatchesLive]);

  useEffect(() => {
    const recipe = recipes.find((item) => item.processing_recipe_id === selectedRecipeId);
    if (contextResetPending.current || !sessionContextMatchesLive || !recipe || !selectedDocumentId || !selectedProfileId) return;
    onSessionChange?.({ recipe: {
      id: recipe.processing_recipe_id,
      revisionId: recipe.current_revision.id,
      label: recipe.content.label,
      revisionNo: recipe.current_revision.revision_no,
    } });
  }, [onSessionChange, recipes, selectedDocumentId, selectedProfileId, selectedRecipeId, sessionContextMatchesLive]);

  useEffect(() => {
    if (activeStage) onSessionChange?.({ lastStage: activeStage.method_id });
  }, [activeStage, onSessionChange]);

  useEffect(() => {
    publishWorkspaceCommandState(`modeling:${workflowTask}`);
    onSessionChange?.({
      workspace: {
        activeStage: workflowTask,
        // IDs are the included subset; exact refs remain the linked source set.
        selectedDocumentIds: ensembleDocumentIds,
        // Exact refs are authoritative.  Do not reconstruct a historical
        // selection from whatever current heads happen to be in the list.
        selectedTestDataRefs,
        visibleTestDataKeys: visibleDocumentIds,
        selectedStepIndex,
        selectedStageOrdinal: selectedStage,
        plotView,
        settingsOpen: inspectorVisible,
      },
    });
  }, [ensembleDocumentIds, inspectorVisible, onSessionChange, plotView, selectedStage, selectedStepIndex, selectedTestDataRefs, visibleDocumentIds, workflowTask]);
  const ensembleStatistic = ensemblePreview?.statistics[0] ?? null;
  const ensembleChannel = channelForQuantity(
    ensembleStatistic?.curve_definition,
    ensembleStatistic?.quantity ?? "",
    "dependent",
  );
  const ensembleBand = ensembleStatistic?.curve_definition
    && ensembleStatistic.curve_series
    && ensembleChannel
    ? resolveDeviationBand(
      ensembleStatistic.curve_definition,
      ensembleStatistic.curve_series,
      ensembleChannel,
    )
    : null;
  const ensembleDisplayUnit = ensembleChannel?.display_unit ?? ensembleStatistic?.unit ?? "";
  const formatEnsembleValue = (value: number | undefined, magnitude = false): string => {
    if (value === undefined) return "—";
    const displayed = ensembleChannel
      ? magnitude
        ? displayCurveMagnitude(ensembleChannel, value)
        : displayCurveValue(ensembleChannel, value)
      : value;
    return displayed === null ? "—" : displayed.toPrecision(6);
  };

  function focusConfiguredStep(index: number): void {
    setSelectedStepIndex(index);
    setWorkspaceInspector("step");
    const stage = preview?.stages.find((item) => item.ordinal === index + 1);
    if (stage) setSelectedStage(stage.ordinal);
  }

  function requestFitPlotMode(mode: PlotInteractionMode): void {
    setFitPlotCommand((current) => ({
      action: "set-mode",
      mode,
      requestId: (current?.requestId ?? 0) + 1,
    }));
  }

  function applyFitPlotSelection(): void {
    setFitPlotCommand((current) => ({
      action: "apply",
      requestId: (current?.requestId ?? 0) + 1,
    }));
  }

  function applyGraphSelection(selection: GraphSelectionCommand): void {
    if (!activeStage || activeStage.ordinal === 0) {
      setError("Choose a processing stage before applying a graph selection.");
      return;
    }
    try {
      const steps = JSON.parse(stepsText) as CommonProcessingStep[];
      const stepIndex = activeStage.ordinal - 1;
      const step = steps[stepIndex];
      if (!step) throw new Error("The selected preview stage no longer matches the Recipe draft.");
      if (step.method_id !== activeStage.method_id) {
        throw new Error("The selected preview stage is stale. Recalculate before applying a graph selection.");
      }
      const options = { ...step.options };
      if (selection.kind === "range") {
        if (step.method_id === "curve.crop") {
          options.minimum = selection.minimum;
          options.maximum = selection.maximum;
        } else if (step.method_id === "polymer.log_time_resample") {
          options.start_time_s = selection.minimum;
          options.end_time_s = selection.maximum;
        } else if (step.method_id === "tensile.toe_zero_intercept") {
          const offset = activeStage.scalar_results.find(
            (item) => item.key === "toe_strain_offset",
          )?.value ?? 0;
          options.minimum_strain = selection.minimum + offset;
          options.maximum_strain = selection.maximum + offset;
          options.warning_acknowledged = false;
        } else if (step.method_id === "metal.elastic_modulus") {
          options.minimum_strain = selection.minimum;
          options.maximum_strain = selection.maximum;
        } else if (step.method_id === "metal.proof_stress") {
          options.search_start = selection.minimum;
          options.search_end = selection.maximum;
        } else if (step.method_id === "metal.hardening_fit_extrapolate") {
          options.fit_minimum_strain = selection.minimum;
          options.fit_maximum_strain = selection.maximum;
        } else {
          throw new Error(`${step.method_id} does not accept an x-domain selection.`);
        }
      } else if (step.method_id === "metal.engineering_to_true_plastic" || step.method_id === "metal.necking_candidate") {
        const xValues = activeStage.series.find(
          (series) => series.quantity === selection.x_quantity,
        )?.values ?? [];
        if (!xValues.length) throw new Error("The selected stage has no points for a necking marker.");
        const nearestIndex = xValues.reduce(
          (best, value, index) => Math.abs(value - selection.x) < Math.abs(xValues[best] - selection.x) ? index : best,
          0,
        );
        if (step.method_id === "metal.necking_candidate") {
          const workupIndex = steps.findIndex(
            (candidate, index) => index > stepIndex && candidate.method_id === "metal.engineering_to_true_plastic",
          );
          if (workupIndex < 0) throw new Error("Add an engineering-to-true/plastic Workup step after necking detection before selecting a boundary.");
          const workup = steps[workupIndex];
          steps[workupIndex] = {
            ...workup,
            options: { ...workup.options, necking_policy: "manual_index", manual_necking_index: nearestIndex, manual_necking_unit: "observed-point-index" },
          };
          setSelectedStepIndex(workupIndex);
        } else {
          options.necking_policy = "manual_index";
          options.manual_necking_index = nearestIndex;
          options.manual_necking_unit = "observed-point-index";
          steps[stepIndex] = { ...step, options };
          setSelectedStepIndex(stepIndex);
        }
      } else {
        throw new Error(`${step.method_id} does not accept a point selection.`);
      }
      if (selection.kind === "range") steps[stepIndex] = { ...step, options };
      applyDraftSteps(JSON.stringify(steps, null, 2));
      setWorkspaceInspector("step");
      setPreview(null);
      setError(null);
      setNotice(`Applied the graph ${selection.kind} to ${step.method_id === "metal.necking_candidate" && selection.kind === "point" ? "the downstream plastic Workup" : step.method_id} in the Recipe draft. Save a new Recipe revision to preserve it.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The graph selection could not be applied.");
    }
  }

  function openWorkflowTask(task: ModelingWorkflowTask): void {
    if (task === "export") setPlotView("pipeline");
    if (task === "process" && pendingExplicitProcessPreview.current) setPreview(null);
    setWorkflowTask(task);
    setInspectorVisible(true);
    onNavigate(`/modeling?stage=${task}&family=${modelingTrack}`);
  }

  useEffect(() => {
    if (workflowTask === "export" && plotView !== "pipeline") setPlotView("pipeline");
  }, [plotView, workflowTask]);

  useEffect(() => {
    if (workflowTask === "data") {
      // Data intentionally focuses the raw source stage. Clear the remembered
      // Process/Fit focus so returning to either task restores its own active
      // engineering stage instead of leaving the graph on the Data ordinal.
      preferredStepContext.current = "";
      setSelectedStage(0);
      return;
    }
    const preferredMethod = workflowTask === "fit" || workflowTask === "export"
      ? modelingTrack === "metal"
        ? "metal.hardening_fit_extrapolate"
        : modelingTrack === "polymer"
          ? documentIsPolymerDma(selectedTrackDocument)
            ? "polymer.dma_prony_fit_compare"
            : "polymer.prony_fit_compare"
          : "rows.sort_unique"
      : isProcessTask
        ? modelingTrack === "metal" ? "metal.elastic_modulus" : "rows.sort_unique"
        : null;
    const preferredContext = `${workflowTask}:${graphPreview?.source_document_sha256 ?? ""}`;
    if (preferredStepContext.current === preferredContext) return;
    preferredStepContext.current = preferredContext;
    const currentStep = configuredSteps[selectedStepIndex];
    if ((isProcessTask && currentStep?.method_id === "tensile.toe_zero_intercept")
      || (workflowTask === "fit" && currentStep && isFitMethod(currentStep.method_id))) {
      const stage = graphPreview?.stages.find((item) => item.ordinal === selectedStepIndex + 1);
      if (stage) setSelectedStage(stage.ordinal);
      return;
    }
    if (preferredMethod) {
      let index = configuredSteps.findIndex((step) => step.method_id === preferredMethod);
      if (index < 0) {
        index = isProcessTask
          ? configuredSteps.map((step) => !isFitMethod(step.method_id)).lastIndexOf(true)
          : configuredSteps.findIndex((step) => isFitMethod(step.method_id));
      }
      if (index >= 0) {
        setSelectedStepIndex(index);
        const stage = graphPreview?.stages.find((item) => item.ordinal === index + 1);
        if (stage) setSelectedStage(stage.ordinal);
      }
    }
  }, [configuredSteps, graphPreview, modelingTrack, selectedStepIndex, selectedTrackDocument, workflowTask]);

  useEffect(() => {
    const params = new URLSearchParams(locationSearch);
    const stage = params.get("stage");
    const family = params.get("family");
    if (["data", "process", "fit", "validate", "review", "export"].includes(String(stage)) && stage !== workflowTask) {
      setWorkflowTask(stage as ModelingWorkflowTask);
    }
    if (["metal", "polymer", "elastomer"].includes(String(family)) && family !== modelingTrack) {
      selectModelingTrack(family as ModelingTrack);
    }
  }, [locationSearch]);

  useEffect(() => {
    const handleCommand = (event: Event) => {
      const command = (event as CustomEvent<{ command?: string }>).detail?.command;
      if (!command?.startsWith("modeling:")) return;
      const action = command.slice("modeling:".length);
      if (["data", "process", "fit", "validate", "review", "export"].includes(action)) openWorkflowTask(action as ModelingWorkflowTask);
      else if (action === "save") void saveRecipe();
      else if (action === "undo") undoDraft();
      else if (action === "redo") redoDraft();
      else if (action === "new") resetSession();
    };
    window.addEventListener("cmp:workspace-command", handleCommand);
    return () => window.removeEventListener("cmp:workspace-command", handleCommand);
  });

  useEffect(() => {
    publishWorkspaceStatus({
      selection: initialSession?.material?.label ?? selectedTrackDocument?.specimen_id ?? selectedTrackDocument?.document_key ?? "Modeling session",
      revision: selectedTrackDocument ? `Test Data r${selectedTrackDocument.current_revision.revision_no} · ${workflowTask}` : `${workflowTask} · no data selected`,
      jobs: busy || previewBusy ? "Engineering calculation running" : notice ? "Last operation completed" : "No active job",
      warnings: error ? "1 workspace error" : "0 warnings",
      connection: error ? "degraded" : "online",
    });
  }, [busy, error, initialSession?.material?.label, notice, previewBusy, selectedTrackDocument, workflowTask]);

  const elastomerWorkbenchTask = modelingTrack === "elastomer"
    && workflowTask === "fit"
    && familyWorkbench !== undefined;

  const updateFitSelection = (selection: FitDecisionSelection | null): void => {
    setFitSelection(selection);
    setVerifiedFitOutputKey(null);
    onSessionEvent?.({ type: "CHANGE_SELECTION" });
  };
  const fitSourceEvidence = <section className="fit-source-evidence" aria-label="Source evidence">
    <div className="fit-source-evidence-heading"><h3>Source evidence</h3><span>Exact revisions</span></div>
    {fitSourceOutput ? <dl>
      <div><dt>Process source</dt><dd>{fitSourceOutput.label} · r{fitSourceOutput.current_revision.revision_no}</dd></div>
      <div><dt>Source digest</dt><dd><code>{fitSourceOutput.output_sha256}</code></dd></div>
      {fitSourceOutput.steps.find((step) => step.method_id === "tensile.toe_zero_intercept") ? <div><dt>Toe compensation</dt><dd><strong>OLS zero intercept · v1.0.0</strong> · exact saved Process step</dd></div> : null}
      <div><dt>Fit method</dt><dd>{selectedConfiguredStep ? <><strong>{selectedConfiguredStep.method_id}</strong>{methods.find((method) => method.method_id === selectedConfiguredStep.method_id) ? ` · ${methods.find((method) => method.method_id === selectedConfiguredStep.method_id)?.version}` : ""}</> : "Not selected"}</dd></div>
      {metalFitRunId ? <div><dt>Fit run</dt><dd><code>{metalFitRunId}</code></dd></div> : null}
      {currentFitOutput ? <div><dt>Saved Fit Output</dt><dd>{currentFitOutput.label} · r{currentFitOutput.current_revision.revision_no}</dd></div> : null}
    </dl> : <p className="muted">No saved Process Output is bound. Save Process before calculating Fit.</p>}
  </section>;
  const fitEvidenceContent = <>
    {fitSourceEvidence}
    {selectedConfiguredStep && activeStage ? <>
      {selectedConfiguredStep.method_id === "metal.hardening_fit_extrapolate" && activeStage.method_id === "metal.hardening_fit_extrapolate" ? <Suspense fallback={<p className="loading-state">Loading fit evidence…</p>}><HardeningCandidateEvidence stage={activeStage} step={selectedConfiguredStep} selection={fitSelection} onSelect={updateFitSelection} onChangeSelection={updateFitSelection} /></Suspense> : null}
      {(selectedConfiguredStep.method_id === "polymer.prony_fit_compare" || selectedConfiguredStep.method_id === "polymer.dma_prony_fit_compare") && activeStage.method_id === selectedConfiguredStep.method_id ? <Suspense fallback={<p className="loading-state">Loading fit evidence…</p>}><PronyCandidateEvidence stage={activeStage} step={selectedConfiguredStep} selection={fitSelection} onSelect={updateFitSelection} onChangeSelection={updateFitSelection} /></Suspense> : null}
    </> : <p className="muted">Run Fit preview to calculate candidate evidence.</p>}
  </>;
  const fitEvidenceDock = workflowTask === "fit" && fitEvidenceOpen ? (
    <div className="fit-evidence-drawer" id="fit-evidence-dock">
      <header className="fit-evidence-drawer-header">
        <strong>Candidate parameters</strong>
        <span className="fit-evidence-drawer-status" role="status">{fitStateLabel}</span>
        <button className="text-button" type="button" onClick={closeFitEvidence}>Close</button>
      </header>
      <div className="fit-evidence-body" ref={fitEvidenceBodyRef} tabIndex={0} aria-label="Candidate parameters evidence">
        {fitEvidenceContent}
      </div>
    </div>
  ) : undefined;
  const distributionAnalysisSheet = isProcessTask && distributionEvidenceOpen ? (
    <Suspense fallback={<p className="loading-state">Loading distribution comparison…</p>}>
      <ScalarDistributionWorkbench
        config={config}
        classification={classification}
        state={materialState}
        onClose={closeDistributionEvidence}
      />
    </Suspense>
  ) : undefined;

  const activePlotView: PlotView = workflowTask === "export" ? "pipeline" : plotView;
  const dataComparisonDocumentIds = selectedTestDataRefs
    .filter((ref) => ref.id !== selectedDocumentId && visibleDocumentIds.includes(exactRefKey(ref)))
    .map((ref) => ref.id);
  const dataTechnicalDetails = workflowTask === "data" && modelingTrack !== "elastomer" ? (
    <EngineeringPane label="Technical details">
      <EngineeringSection className="processing-input-card" id="modeling-import" label="Selected Test Data">
        <SemanticText semanticRole="sectionHeading">Selected Test Data</SemanticText>
        {selectedTrackDocument && selectedSourceRef ? (
          <dl className="modeling-data-evidence-grid">
            <div><dt>Name</dt><dd>{curveDisplayName(selectedTrackDocument)}</dd></div>
            <div><dt>Exact revision</dt><dd>Revision {selectedSourceRef.revisionNo}</dd></div>
            <div><dt>System name</dt><dd><code>{selectedTrackDocument.document_key}</code></dd></div>
            <div><dt>Specimen ID</dt><dd><code>{selectedTrackDocument.specimen_id}</code></dd></div>
            <div><dt>Recorded method</dt><dd><code>{selectedTrackDocument.method}</code></dd></div>
            <div><dt>Channels</dt><dd><code>{selectedTrackDocument.channels.map((channel) => `${channel.name} [${channel.original_unit_string}]`).join(" · ")}</code></dd></div>
            <div><dt>Source</dt><dd>{selectedTrackDocument.governed_source ? "Materials and Test Run" : "Imported Test Data"}</dd></div>
          </dl>
        ) : <p className="muted">No Test Data selected.</p>}
      </EngineeringSection>

      <EngineeringSection className="mapping-profile-card" id="modeling-map" label="Column mapping">
        <SemanticText semanticRole="sectionHeading">Column mapping</SemanticText>
        <label>Saved mapping<select aria-label="Saved Mapping Profile" value={selectedProfileId} onChange={(event) => selectProfile(event.target.value)}><option value="">New mapping</option>{profiles.map((item) => <option key={item.mapping_profile_id} value={item.mapping_profile_id}>{item.content.label} · Revision {item.current_revision.revision_no}</option>)}</select></label>
        <details className="advanced-definition"><summary>Mapping JSON</summary><label>Mapping JSON<textarea className="mapping-profile-editor" aria-label="Mapping Profile JSON" value={profileText} onChange={(event) => setProfileText(event.target.value)} spellCheck={false} /></label></details>
        <div className="profile-save-row"><label>Classification<select value={classification} onChange={(event) => setClassification(event.target.value as DataClassification)}><option value="internal">Internal</option><option value="confidential">Confidential</option><option value="restricted">Restricted</option><option value="export_controlled">Export controlled</option></select></label><label>Change reason<input name="mapping-change-reason" autoComplete="off" value={changeReason} onChange={(event) => setChangeReason(event.target.value)} /></label><button className="button primary" type="button" disabled={busy || !changeReason.trim()} onClick={() => void saveProfile()}>{selectedProfileId ? "Save new version" : "Save new mapping"}</button>{mappingProfileRetryPhase ? <button className="button secondary" type="button" disabled={busy} onClick={() => void retryMappingProfile()}>{mappingProfileRetryPhase === "verify" ? "Retry verification" : "Retry save"}</button> : null}</div>
      </EngineeringSection>
    </EngineeringPane>
  ) : undefined;

  const processNavigatorDocuments = selectedTestDataRefs.flatMap((ref) => {
    const item = stageDocuments.find((candidate) => candidate.test_data_document_id === ref.id);
    return item ? [item] : [];
  });
  const currentProcessDocument = processNavigatorDocuments.find(
    (item) => item.test_data_document_id === selectedDocumentId,
  ) ?? selectedTrackDocument;
  const comparisonProcessDocuments = processNavigatorDocuments.filter(
    (item) => item.test_data_document_id !== selectedDocumentId,
  );
  const processCurveRow = (item: CanonicalTestDataDocumentResponse, current: boolean) => {
    const label = curveDisplayName(item);
    const selectedRef = selectedTestDataRefs.find((ref) => ref.id === item.test_data_document_id);
    const key = selectedRef ? exactRefKey(selectedRef) : modelingSessionRecordKey(item.test_data_document_id, item.current_revision.id);
    const visible = visibleDocumentIds.includes(key);
    const curveIndex = stageDocuments.indexOf(item);
    return <article className={current ? "active current-process-input" : "comparison-process-input"} key={key}>
      <span className="dataset-curve-swatch" aria-label={`Plot color for ${label}`} role="img" style={{ "--curve-index": curveIndex } as React.CSSProperties} />
      <span className="curve-row-label"><span><strong>{label}</strong></span></span>
      {current ? <span className="process-input-role">Current</span> : <button type="button" className="curve-visibility-toggle" aria-pressed={visible} aria-label={`${visible ? "Hide" : "Show"} ${label} on graph`} title={`${visible ? "Hide" : "Show"} ${label} on graph`} onClick={() => setVisibleDocumentIds((currentIds) => visible ? currentIds.filter((candidate) => candidate !== key) : [...currentIds, key])}><svg aria-hidden="true" viewBox="0 0 24 24" focusable="false"><path d="M2.5 12s3.5 6 9.5 6 9.5-6 9.5-6-3.5-6-9.5-6-9.5 6-9.5 6Z" /><circle cx="12" cy="12" r="2.75" />{!visible ? <path d="M3 3l18 18" /> : null}</svg></button>}
    </article>;
  };
  const configuredStepsNavigator = <div className={`configured-step-list${isApprovedMetalFit ? " approved-fit-process-tree" : ""}`}>
    <p className="rail-title">{stageRail}</p>
    {displayedRailEntries.map(({ step, index, label, title, railIndex }) => {
      const groupedFitRail = workflowTask === "fit" && modelingTrack === "metal";
      return <button type="button" title={title} disabled={processBlocked} className={selectedStepIndex === index ? "active" : ""} key={`${index}:${step.method_id}`} onClick={() => focusConfiguredStep(index)}><span>{groupedFitRail ? railIndex + 1 : index + 1}</span><span><strong>{label}</strong></span></button>;
    })}
    {availableToeMethod ? <button type="button" className="configured-step-add" aria-label="Add tensile toe compensation" disabled={processBlocked} onClick={() => addMethod(availableToeMethod)} title="Add an explicit OLS zero-intercept strain correction"><span aria-hidden="true">+</span><span><strong>Add tensile toe compensation</strong></span></button> : null}
  </div>;
  const processNavigator = <>
    <div className="modeling-dataset-list process-input-browser">
      <div className="rail-heading"><p>Test Data</p></div>
      <p className="process-rail-section-title">Current Process input</p>
      {currentProcessDocument ? processCurveRow(currentProcessDocument, true) : <p className="process-rail-empty">Choose Test Data in Data.</p>}
      {comparisonProcessDocuments.length ? <>
        <p className="process-rail-section-title">Comparison on graph</p>
        {comparisonProcessDocuments.map((item) => processCurveRow(item, false))}
      </> : null}
      <details className="rail-statistics-action"><summary>Replicate analysis</summary>{selectedTestDataRefs.length >= 2 ? <><label>Alignment points<input aria-label="Replicate alignment point count" type="number" min="5" max="1001" value={ensemblePointCount} disabled={processBlocked} onChange={(event) => { setEnsemblePointCount(Number(event.target.value)); setEnsemblePreview(null); }} /></label><button className="button secondary" type="button" disabled={busy || processBlocked} onClick={() => void runEnsemblePreview()}>{busy ? "Calculating…" : "Preview statistics"}</button><small>Shared observed range only.</small></> : <small>Add a comparison curve in Data first.</small>}</details>
    </div>
    {configuredStepsNavigator}
  </>;
  const fitNavigator = <>
    <div className="modeling-dataset-list fit-input-summary">
      <div className="rail-heading"><p>Fit input</p></div>
      <div className={fitSourceOutput ? "fit-input-row" : "fit-input-row blocked"}>
        <strong>{stageContextLabel}</strong>
        <span>{fitSourceOutput ? "Saved Process result" : "Save a Process result first"}</span>
      </div>
    </div>
    {configuredStepsNavigator}
  </>;

  return (
    <main className={`processing-workbench-page stage-${workflowTask}`}>
      <header className="modeling-context-strip" aria-label="Modeling context">
        <div className="modeling-work-title"><h1>{stageTitle}</h1>{workflowTask === "data" ? null : <><span className={workflowTask === "fit" ? "fit-context-source" : undefined} title={stageContextLabel}>{stageContextLabel}</span>{workflowTask === "fit" ? <span className={`fit-surface-state fit-surface-state-${fitState}`} role="status">{fitStateLabel}</span> : null}</>}</div>
        <div className="modeling-context-actions">
          <details className="modeling-advanced-menu"><summary className="button secondary">Advanced</summary><div role="tablist" aria-label="Material modeling family"><button type="button" role="tab" aria-selected={modelingTrack === "metal"} onClick={() => selectModelingTrack("metal")}>Metal · elastoplastic</button><button type="button" role="tab" aria-selected={modelingTrack === "polymer"} onClick={() => selectModelingTrack("polymer")}>Polymer · viscoelastic</button><button type="button" role="tab" aria-selected={modelingTrack === "elastomer"} onClick={() => selectModelingTrack("elastomer")}>Elastomer · hyper-viscoelastic</button><button type="button" onClick={() => openWorkflowTask("validate")}>Validation & review</button></div></details>
          {isProcessTask ? <button ref={distributionEvidenceTriggerRef} className="button secondary modeling-analysis-trigger" type="button" aria-expanded={distributionEvidenceOpen} aria-controls="scalar-distribution-analysis" onClick={() => distributionEvidenceOpen ? closeDistributionEvidence() : setDistributionEvidenceOpen(true)}>Distribution analysis</button> : null}
          {isProcessTask || workflowTask === "fit" ? <button className="button secondary" type="button" disabled={busy || previewBusy || (isProcessTask && !processSourceReady)} onClick={() => void runPreview()}>{previewBusy ? "Updating…" : "Preview changes"}</button> : null}
          {workflowTask === "fit" ? <button className="button primary" type="button" disabled={busy || !fitDecisionReady || (!selectedProfileId && !fitSourceOutput)} onClick={() => void saveSelectedFitOutput()}>Save fit &amp; continue</button> : null}
        </div>
      </header>
      <ModelingStageShell session={initialSession ?? null} activeStage={workflowTask} onStageChange={openWorkflowTask} />
      {error ? <div className="error-banner" role="alert">{error}</div> : null}
      {fitRestoreError && workflowTask === "fit" && exactSessionOutput?.source_processing_output ? <div className="modeling-notice-line" role="status"><span>Saved Fit could not be restored; the previous graph remains visible.</span><button className="button secondary" type="button" disabled={busy || previewBusy} onClick={retryExactSavedFit}>Retry saved Fit</button></div> : null}
      {recipeConflict ? <section className="modeling-conflict-banner" role="alert" aria-label="Stale Recipe revision conflict">
        <div><strong>The Recipe changed after this draft was opened.</strong><span>Reload the current revision, or preserve these local steps as a new revision.</span></div>
        <div><button className="button secondary" type="button" disabled={busy} onClick={() => void resolveRecipeConflict("reload")}>Reload current</button><button className="button primary" type="button" disabled={busy} onClick={() => void resolveRecipeConflict("keep-local")}>Keep local draft as new revision</button><button className="text-button" type="button" disabled={busy} onClick={() => setRecipeConflict(null)}>Cancel</button></div>
      </section> : null}
      {notice && notice !== "Preview ready." && workflowTask === "data" ? <div className="modeling-notice-line" role="status" title={notice}>{notice}</div> : null}

      {workflowTask === "export" ? <Suspense fallback={<p className="loading-state">Loading Export workspace…</p>}>{exactExportSourceReady ? <ModelingTargetPreview
        config={config}
        session={initialSession}
        output={exactSessionOutput}
        prerequisites={exactExportPrerequisites}
        onSessionEvent={onSessionEvent}
        onNavigate={onNavigate}
        fitPreview={verifiedSavedFit ? preview : null}
        fitSelection={fitSelection}
        fitSourceReady={verifiedSavedFit}
        fitRestoreError={fitRestoreError}
        onRetryFitSource={retryExactSavedFit}
      /> : <ModelingExportPrerequisites
        config={config}
        session={initialSession}
        output={exactSessionOutput}
        propertySet={propertySet}
        prerequisites={exactExportPrerequisites}
        onSessionEvent={onSessionEvent}
        onNavigate={onNavigate}
      />}</Suspense> : null}

      {elastomerWorkbenchTask ? <section className="modeling-elastomer-workspace" id="modeling-fit" aria-label="Elastomer multi-mode modeling workspace">{familyWorkbench}</section> : null}
      {workflowTask === "validate" || workflowTask === "review" ? <Suspense fallback={<p className="loading-state">Loading governed evidence…</p>}><ModelingValidationStage
        config={config}
        materialState={materialState}
        session={initialSession}
        family={modelingTrack}
        onSessionChange={onSessionChange}
        onSessionEvent={onSessionEvent}
        onNavigate={onNavigate}
      /></Suspense> : null}
      {!elastomerWorkbenchTask && workflowTask !== "validate" && workflowTask !== "review" && workflowTask !== "export" ? <section className={`workbench-card method-builder-card stage-${workflowTask}`} id="modeling-process">
        {isProcessTask || workflowTask === "fit" ? <div className="section-heading modeling-workspace-toolbar"><h2 className="visually-hidden">{stageTitle} workspace</h2><div className="modeling-section-actions"><details className="method-library" open={processBlocked || undefined}><summary aria-disabled={processBlocked}>{workflowTask === "fit" ? "Add fit method" : "Add operation"}</summary><div className="method-registry-strip" aria-label={workflowTask === "fit" ? "Available fitting methods" : "Available processing operations"}>{availableMethods.map((method) => <button type="button" className="method-pill" key={method.method_id} disabled={processBlocked} onClick={() => addMethod(method)}><strong>+ {method.label}</strong></button>)}</div></details></div></div> : null}
        <div className={`modeling-workspace-shell${workflowTask === "data" ? " modeling-workspace-stage-data" : isProcessTask ? " modeling-workspace-stage-process" : workflowTask === "fit" ? " modeling-workspace-stage-fit" : ""}${distributionAnalysisSheet ? " has-distribution-analysis" : ""}`}>
        {workflowTask === "data" ? <Suspense fallback={<p className="loading-state">Loading Test Data workspace…</p>}><ModelingDataIntake
          config={config}
          material={material}
          state={materialState}
          documents={stageDocuments}
          emptySession={initialSession?.contextSelectionRequired === true}
          selectedTestDataRefs={selectedTestDataRefs}
          selectedDocumentId={selectedDocumentId}
          includedDocumentIds={ensembleDocumentIds}
          comparisonDocumentIds={dataComparisonDocumentIds}
          comparisonMode={dataComparisonOpen}
          visibleDocumentKeys={visibleDocumentIds}
          processingMappingProfileText={profileText}
          plot={dataGraphPreview && dataActiveStage && dataBaseStage
            ? <EngineeringCurvePlot key={`${dataActiveStage.method_id}:${dataActiveStage.ordinal}:data:${dataObservedCurves.map((curve) => curve.id).join("|")}`} preview={dataGraphPreview} activeStage={dataActiveStage} baseStage={dataBaseStage} activeStep={graphPreview ? activeConfiguredStep : undefined} fitSelection={fitSelection} width={dataChart.width} height={dataChart.height} observedCurves={dataObservedCurves} reviewOnly />
            : <EngineeringCurvePlotEmpty
              width={dataChart.width}
              height={dataChart.height}
              title="No Test Data selected"
              message="Choose from Library or Local file."
            />}
          technicalDetails={dataTechnicalDetails}
          ribbonOpen={inspectorVisible}
          onRibbonOpenChange={setInspectorVisible}
          onSelectDocument={(id, revisionId) => void loadDocument(id, revisionId)}
          onToggleComparison={toggleEnsemble}
          onComparisonModeChange={setDataComparisonOpen}
          onPreviewDocument={previewIntakeDocument}
          onImported={registerIntakeDocument}
          onObservedCurves={setObservedCurves}
          onContinue={() => openWorkflowTask("process")}
        /></Suspense> : <ModelingWorkspaceLayout
          navigator={isProcessTask ? processNavigator : workflowTask === "fit" ? fitNavigator : undefined}
          plot={<article className="persistent-modeling-plot" id="modeling-fit">
             <div className="section-heading"><div>{workflowTask === "fit" ? <h2 className="fit-plot-heading">Hardening response</h2> : <h2>{activePlotView === "ensemble" ? "Replicate statistics" : activeStage ? methods.find((method) => method.method_id === activeStage.method_id)?.label ?? methodDisplayName(activeStage.method_id) : "Load data and preview"}</h2>}</div>{isProcessTask && ensemblePreview ? <div className="plot-view-switch" role="group" aria-label="Curve plot view"><button type="button" className={activePlotView === "pipeline" ? "active" : ""} disabled={!preview} onClick={() => setPlotView("pipeline")}>Response</button><button type="button" className={activePlotView === "ensemble" ? "active" : ""} onClick={() => setPlotView("ensemble")}>{ensembleBand ? "Mean & band" : "Mean"}</button></div> : null}</div>
             {workflowTask === "fit" && !fitSourceOutput ? <EngineeringCurvePlotEmpty width={chart.width} height={chart.height} blocked title="Fit is blocked" message="No saved Process Output is bound. Save Process before calculating Fit." blockedActionLabel="Back to Process" onBackToData={() => openWorkflowTask("process")} /> : graphPreview && activeStage && baseStage ? <EngineeringCurvePlot key={`${activeStage.method_id}:${activeStage.ordinal}:${workflowTask}`} preview={graphPreview} activeStage={activeStage} baseStage={baseStage} activeStep={activeConfiguredStep} fitSelection={fitSelection} width={chart.width} height={chart.height} observedCurves={isProcessTask ? observedCurves : undefined} processOverlay={isProcessTask} onApplySelection={activePlotView === "pipeline" ? applyGraphSelection : undefined} ensemblePreview={activePlotView === "ensemble" ? ensemblePreview : null} interactionCommand={workflowTask === "fit" ? fitPlotCommand : null} onInteractionStateChange={workflowTask === "fit" ? setFitPlotInteraction : undefined} /> : isProcessTask && !processSourceReady ? <EngineeringCurvePlotEmpty width={chart.width} height={chart.height} blocked message="Restore inputs." onBackToData={() => openWorkflowTask("data")} /> : <div className="modeling-plot-empty"><strong>{previewBusy ? "Updating the engineering preview…" : "The graph stays here while you prepare the curves."}</strong><p>{previewBusy ? "A newer processing change replaces the previous preview request." : matchingSavedOutputs.length > 0 ? "No Process preview is active. Choose Use settings for a saved result, then select Preview changes to preview the draft." : "No Process preview is active. Select Preview changes to preview the current Process settings."}</p></div>}
            {ensemblePreview && activePlotView === "ensemble" ? <><div className="statistics-grid compact-statistics"><article><span>Included curves</span><strong>{ensemblePreview.members.length}</strong></article><article><span>Common points</span><strong>{ensemblePreview.grid.length}</strong></article><article><span>Domain policy</span><strong>Intersection</strong></article></div>{ensembleStatistic ? <details className="ensemble-result-details"><summary>Statistics details</summary><div className="statistics-grid"><article><span>Quantity</span><strong>{ensembleChannel?.label ?? ensembleStatistic.quantity}</strong><small>{ensembleDisplayUnit}</small></article><article><span>Last mean</span><strong>{formatEnsembleValue(ensembleStatistic.mean.at(-1))}</strong><small>{ensembleDisplayUnit}</small></article><article><span>Sample SD</span><strong>{formatEnsembleValue(ensembleStatistic.standard_deviation.at(-1), true)}</strong><small>{ensembleDisplayUnit}</small></article><article><span>MAD</span><strong>{formatEnsembleValue(ensembleStatistic.mad.at(-1), true)}</strong><small>{ensembleDisplayUnit}</small></article><article><span>IQR</span><strong>{formatEnsembleValue(ensembleStatistic.q1.at(-1))} – {formatEnsembleValue(ensembleStatistic.q3.at(-1))}</strong><small>{ensembleDisplayUnit}</small></article></div></details> : null}</> : null}
          </article>}
          ribbon={isProcessTask ? <Suspense fallback={<p role="status" aria-label="Loading Process controls" aria-live="polite">Loading Process controls…</p>}><ModelingProcessPanel
            stepNumber={selectedConfiguredStep ? selectedStepIndex + 1 : undefined}
            stepLabel={selectedConfiguredStep ? methods.find((method) => method.method_id === selectedConfiguredStep.method_id)?.label ?? methodDisplayName(selectedConfiguredStep.method_id) : "Select an operation"}
            sourceIdentity={processSourceIdentity}
            stepControls={selectedConfiguredStep ? <GuidedStepOptions step={selectedConfiguredStep} stage={selectedConfiguredStage} onChange={updateStepOption} graphInteraction={{ mode: fitPlotInteraction.mode, canApply: fitPlotInteraction.hasSelection, available: Boolean(preview && activeStage && activeStage.method_id === selectedConfiguredStep.method_id) }} onGraphModeChange={requestFitPlotMode} onApplyGraphSelection={applyFitPlotSelection} /> : <p className="muted">Add or select an operation from the Process rail.</p>}
            scalarPa={graphPreview?.stages.flatMap((stage) => stage.scalar_results ?? []).find((item) => item.key === "youngs_modulus")?.value}
            resultContent={selectedConfiguredStep?.method_id === "tensile.toe_zero_intercept" ? <ToeCompensationResult stage={selectedConfiguredStage} /> : undefined}
            saveBlockedReason={toeWarningSaveBlocked ? "Review and acknowledge the toe quality warning, then preview again before saving." : undefined}
            processReady={processSourceReady}
            hasPreview={Boolean(preview)}
            hasLastValidPreview={Boolean(lastValidPreview)}
            notice={notice}
            busy={busy}
            outputLabel={outputLabel}
            outputReason={outputReason}
            savedOutputs={matchingSavedOutputs}
            savedResultStates={savedResultStates}
            currentOutputId={localCurrentOutput?.id ?? initialSession?.processingOutput?.id}
            onClose={setInspectorVisible}
            onOutputLabelChange={setOutputLabel}
            onOutputReasonChange={setOutputReason}
            onSave={commitOutput}
            onLoadSavedResult={loadSavedResult}
            onUseSavedSettings={useSavedSettings}
            onRetryExactSource={isProcessTask && selectedSourceKey && attemptedExactDocumentKey.current === selectedSourceKey && !exactSourceLoaded && !busy ? retryExactSource : undefined}
          /></Suspense> : <aside className={`step-option-panel ${workflowTask}-stage-options`}>
            <div className="workspace-inspector-heading"><p><strong>Fit settings</strong></p><div className="modeling-ribbon-actions"><button className="text-button" type="button" onClick={() => setInspectorVisible(false)}>Close</button></div></div>
            {selectedConfiguredStep ? <>
              <div className="section-heading"><h3>Step {workflowTask === "fit" && modelingTrack === "metal" ? Math.max(1, fitRailEntries.findIndex((entry) => entry.index === selectedStepIndex) + 1) : selectedStepIndex + 1} · {selectedConfiguredStep.method_id === "metal.hardening_fit_extrapolate" ? "Hardening fit" : methods.find((method) => method.method_id === selectedConfiguredStep.method_id)?.label ?? methodDisplayName(selectedConfiguredStep.method_id)}</h3><div className="fit-heading-actions"><button className="text-button" type="button" onClick={removeSelectedStep}>Remove step</button></div></div>
              <GuidedStepOptions step={selectedConfiguredStep} stage={selectedConfiguredStage} onChange={updateStepOption} graphInteraction={{ mode: fitPlotInteraction.mode, canApply: fitPlotInteraction.hasSelection, available: workflowTask === "fit" && activePlotView === "pipeline" && Boolean(preview && activeStage && activeStage.method_id === selectedConfiguredStep.method_id) }} onGraphModeChange={requestFitPlotMode} onApplyGraphSelection={applyFitPlotSelection} />
              {workflowTask === "fit" ? <button ref={fitEvidenceTriggerRef} className="fit-evidence-trigger" type="button" aria-expanded={fitEvidenceOpen} aria-controls="fit-evidence-dock" onClick={() => fitEvidenceOpen ? closeFitEvidence() : setFitEvidenceOpen(true)}>Candidate parameters</button> : null}
              {modelingTrack === "polymer" && selectedConfiguredStep.method_id === "polymer.prony_fit_compare" ? familyInspector : null}
            </> : <p className="muted">Add or select a processing step.</p>}
            <details className="advanced-workflow-settings">
              <summary>Advanced · Recipe and Batch</summary>
              <nav className="workspace-inspector-tabs" aria-label="Advanced Modeling tools">
                <button type="button" className={workspaceInspector === "recipe" ? "active" : ""} onClick={() => setWorkspaceInspector("recipe")}>Recipe <span>{trackRecipes.length}</span></button>
                <button type="button" className={workspaceInspector === "batch" ? "active" : ""} onClick={() => setWorkspaceInspector("batch")}>Batch <span>{trackBatches.length}</span></button>
              </nav>
            {workspaceInspector === "recipe" ? <div className="inspector-recipe-panel">
              <div className="section-heading"><div><p className="eyebrow">Reusable execution</p><h3>Recipe Library</h3></div><span className="status-chip">{trackRecipes.length} saved</span></div>
              <label>Saved Recipe<select aria-label="Saved Processing Recipe" value={selectedRecipeId} onChange={(event) => selectRecipe(event.target.value)}><option value="">New Recipe</option>{trackRecipes.map((item) => <option key={item.processing_recipe_id} value={item.processing_recipe_id}>{item.content.label} · r{item.current_revision.revision_no} · {item.content.lifecycle_state}</option>)}</select></label>
              {selectedRecipeId ? <div className="recipe-library-summary"><span><strong>{recipes.find((item) => item.processing_recipe_id === selectedRecipeId)?.content.lifecycle_state}</strong><small>Exact revision r{recipes.find((item) => item.processing_recipe_id === selectedRecipeId)?.current_revision.revision_no}</small></span><button className="text-button" type="button" onClick={cloneSelectedRecipe}>Clone as new</button></div> : <div className="recipe-library-summary draft"><span><strong>Unsaved draft</strong><small>Choose an existing Recipe or save this pipeline.</small></span></div>}
              <label>Recipe key<input value={recipeKey} onChange={(event) => setRecipeKey(event.target.value)} /></label>
              <label>Label<input value={recipeLabel} onChange={(event) => setRecipeLabel(event.target.value)} /></label>
              <label>Description<input value={recipeDescription} onChange={(event) => setRecipeDescription(event.target.value)} /></label>
              <label>Change reason<input value={recipeReason} onChange={(event) => setRecipeReason(event.target.value)} /></label>
              <div className="inspector-action-stack"><button className="button primary" type="button" disabled={busy || !selectedProfileId || !recipeKey.trim() || !recipeLabel.trim() || !recipeReason.trim()} onClick={() => void saveRecipe()}>{selectedRecipeId ? "Append draft revision" : "Save new Recipe"}</button><button className="button secondary" type="button" disabled={busy || !recipes.some((item) => item.processing_recipe_id === selectedRecipeId && item.content.lifecycle_state === "draft")} onClick={() => void publishRecipe()}>Publish reviewed revision</button></div>
              {selectedRecipeId ? <p className="digest-line"><span>Exact Recipe</span><code>{recipes.find((item) => item.processing_recipe_id === selectedRecipeId)?.current_revision.content_hash}</code></p> : <p className="muted">Save these ordered method versions and options for reuse.</p>}
            </div> : null}
            {workspaceInspector === "batch" ? <div className="inspector-batch-panel">
              <div className="section-heading"><div><p className="eyebrow">Exact revision batch</p><h3>Batch monitor</h3></div><span className="status-chip">{trackBatches.length} runs</span></div>
              <fieldset><legend>Test Data selection</legend>{trackDocuments.map((item) => <label key={item.test_data_document_id}><input type="checkbox" checked={batchDocumentIds.includes(item.test_data_document_id)} onChange={() => toggleBatchDocument(item.test_data_document_id)} />{item.document_key} · r{item.current_revision.revision_no}</label>)}</fieldset>
              <label>Batch label<input aria-label="Processing Batch label" value={batchLabel} onChange={(event) => setBatchLabel(event.target.value)} /></label>
              <div className="inspector-action-stack"><button className="button secondary" type="button" disabled={busy || !selectedRecipeId || !batchDocumentIds.length} onClick={() => void preflightBatch()}>Compatibility preflight</button><button className="button primary" type="button" disabled={busy || !batchPreflight?.compatible || !batchLabel.trim()} onClick={() => void executeBatch()}>Execute published Recipe</button></div>
              {batchPreflight ? <div className="batch-summary"><strong>{batchPreflight.compatible ? "Ready to run" : "Blocked"}</strong><span>{batchPreflight.members.filter((member) => member.compatible).length}/{batchPreflight.members.length} compatible exact revisions</span><div className="batch-preflight-members">{batchPreflight.members.map((member) => <span className={member.compatible ? "compatible" : "blocked"} key={`${member.source.document_id}:${member.source.revision_id}`}><i />Input {member.ordinal + 1}<small>{member.compatible ? `${member.final_point_count} output points` : member.diagnostic ?? "Incompatible"}</small></span>)}</div><code>{batchPreflight.recipe_sha256}</code></div> : <p className="muted">The current published Recipe is restored automatically. Select exact Test Data, then run compatibility preflight.</p>}
              <div className="inspector-batch-history">{trackBatches.map((batch) => { const succeeded = batch.attempts.filter((attempt) => attempt.status === "succeeded").length; return <article key={batch.batch_id}><div><strong>{batch.label}</strong><small>{batch.members.length} members · {succeeded}/{batch.attempts.length} attempts succeeded</small><em>{new Date(batch.created_at).toLocaleDateString()}</em></div><span className={`status-chip ${batch.status === "partial" || batch.status === "failed" ? "warning" : ""}`}>{batch.status}</span>{batch.status === "partial" || batch.status === "failed" ? <button className="text-button" type="button" disabled={busy} onClick={() => void retryFailedBatch(batch.batch_id)}>Retry failed</button> : null}</article>; })}{!trackBatches.length ? <p className="muted">No batch has run for this material family yet.</p> : null}</div>
            </div> : null}
            </details>
          </aside>}
          dock={fitEvidenceDock}
          dockLabel={fitEvidenceDock ? "Candidate parameters" : undefined}
          inactive={Boolean(distributionAnalysisSheet)}
          ribbonOpen={inspectorVisible}
          onRibbonOpenChange={setInspectorVisible}
        />}
        {distributionAnalysisSheet ? <aside className="distribution-analysis-sheet">{distributionAnalysisSheet}</aside> : null}
        </div>
        <details className="advanced-definition"><summary>Advanced Recipe JSON</summary><label>Ordered step JSON<textarea className="pipeline-editor" aria-label="Ordered processing steps" name="ordered-processing-steps" autoComplete="off" value={stepsText} onChange={(event) => applyDraftSteps(event.target.value)} spellCheck={false} /></label></details>
      </section> : null}

      <details className="modeling-support-drawer" id="modeling-output" open={savedOutputsOpen} onToggle={(event) => setSavedOutputsOpen(event.currentTarget.open)}><summary><span><strong>Saved outputs</strong></span></summary>{savedOutputsOpen ? <section className="workbench-card processing-output-card">
        <div className="section-heading"><div><p className="eyebrow">Immutable output history</p><h2>Saved processing result</h2></div><span className="status-chip">{outputs.length} saved</span></div>
        <p className="mapping-note">Save processed curves is the only Process primary action. It recomputes the selected exact Test Data and Mapping Profile on the server; preview arrays are never authoritative output.</p>
        {outputs.length ? <div className="processing-output-list">{outputs.map((output) => <article key={output.processing_output_id}><div><strong>{output.label}</strong><small>r{output.current_revision.revision_no} · {output.final_point_count} points · {output.stage_count} stages</small><code>{output.output_sha256}</code></div><button className="button secondary" type="button" disabled={busy} onClick={() => void downloadOutput(output)}>Download JSON</button><DomainWorkflowLinks compact config={config} target={{ kind: "processing_output", objectId: output.processing_output_id, revisionId: output.current_revision.id, label: `${output.label} r${output.current_revision.revision_no}` }} /></article>)}</div> : <p className="muted">No committed common Processing Output is visible yet.</p>}
      </section> : null}</details>

    </main>
  );
}
