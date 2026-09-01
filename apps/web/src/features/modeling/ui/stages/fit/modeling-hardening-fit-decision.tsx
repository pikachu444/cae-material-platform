import type { CommonCurveStage, CommonProcessingStep } from "../../../model/common-processing-contracts";
import {
  fitDecisionIdentityLabel,
  hardeningCandidateWarning,
  type FitDecisionSelection,
} from "../../../model/fit-decision-contract";
import {
  ModelingFitCandidateComparison,
  type ModelingFitCandidateRow,
} from "./modeling-fit-candidate-comparison";
import "./modeling-hardening-fit-decision.css";
import "./modeling-metal-fit-workspace.css";

interface HardeningFitDecisionProps {
  stage: CommonCurveStage;
  step: CommonProcessingStep;
  selection: FitDecisionSelection | null;
  stateLabel: string;
  busy: boolean;
  saveReady: boolean;
  onSelect: (selection: FitDecisionSelection) => void;
  onChangeSelection: (selection: FitDecisionSelection) => void;
  onSave: () => void;
}

function modelLabel(value: string): string {
  return value.replaceAll("_", "-");
}

function percent(value: number | undefined): string {
  return value === undefined || !Number.isFinite(value) ? "—" : `${(value * 100).toFixed(2)}%`;
}

export function HardeningFitDecision({
  stage,
  step,
  selection,
  stateLabel,
  busy,
  saveReady,
  onSelect,
  onChangeSelection,
  onSave,
}: HardeningFitDecisionProps) {
  const families = Array.isArray(step.options.families) ? step.options.families.map(String) : [];
  const scalar = new Map(stage.scalar_results.map((item) => [item.key, item]));
  const fitMinimum = Number(step.options.fit_minimum_strain);
  const fitMaximum = Number(step.options.fit_maximum_strain);
  const extrapolationMaximum = Number(step.options.extrapolation_maximum_strain);
  const fitRange = Number.isFinite(fitMinimum) && Number.isFinite(fitMaximum)
    ? `${fitMinimum.toPrecision(3)}–${fitMaximum.toPrecision(3)} measured; to ${Number.isFinite(extrapolationMaximum) ? extrapolationMaximum.toPrecision(3) : "declared limit"}`
    : "Observed fit domain; declared bounded extrapolation";
  const numerical = new Map((stage.fit_candidates ?? []).map((candidate) => [candidate.family, candidate]));
  const singleCandidates = families.map((family) => {
    const relative = scalar.get(`${family}.relative_rmse`)?.value;
    const fit = numerical.get(family);
    const warning = hardeningCandidateWarning(family, Boolean(fit?.active_bound.length));
    return {
      id: family,
      label: modelLabel(family),
      relative,
      fit,
      warning,
      selection: {
        candidateKey: family,
        displayLabel: modelLabel(family),
        mode: "single" as const,
        primaryLaw: family,
        reason: "",
        warningAcknowledged: false,
        fitRange,
        warning,
      },
    };
  });
  const primaryLaw = String(step.options.primary_family ?? "");
  const secondaryLaw = String(step.options.secondary_family ?? "");
  const primaryWeight = Number(step.options.primary_weight);
  const blendKey = `${primaryLaw}+${secondaryLaw}`;
  const blendFit = numerical.get(blendKey);
  const blendWarnings = [primaryLaw, secondaryLaw]
    .map((family) => hardeningCandidateWarning(family, Boolean(numerical.get(family)?.active_bound.length)))
    .filter((item): item is string => Boolean(item));
  const blendWarning = Array.from(new Set(blendWarnings)).join("; ") || undefined;
  const blendSelection: FitDecisionSelection | null = primaryLaw
    && secondaryLaw
    && primaryLaw !== secondaryLaw
    && families.includes(primaryLaw)
    && families.includes(secondaryLaw)
    && Number.isFinite(primaryWeight)
    && primaryWeight > 0
    && primaryWeight < 1
    ? {
        candidateKey: blendKey,
        displayLabel: `${modelLabel(primaryLaw)} + ${modelLabel(secondaryLaw)} ${Math.round(primaryWeight * 100)}/${Math.round((1 - primaryWeight) * 100)}`,
        mode: "blend",
        primaryLaw,
        secondaryLaw,
        primaryWeight,
        reason: "",
        warningAcknowledged: false,
        fitRange,
        warning: blendWarning,
      }
    : null;
  const candidates = [
    ...singleCandidates,
    ...(blendSelection ? [{
      id: blendKey,
      label: blendSelection.displayLabel,
      relative: blendFit?.relative_rmse,
      fit: blendFit,
      warning: blendWarning,
      selection: blendSelection,
    }] : []),
  ].sort((left, right) => (left.relative ?? Number.POSITIVE_INFINITY) - (right.relative ?? Number.POSITIVE_INFINITY));
  const recommended = candidates.find((candidate) => Number.isFinite(candidate.relative))?.id;
  const candidateSelection = (id: string): FitDecisionSelection => {
    const candidate = candidates.find((item) => item.id === id);
    if (candidate) return candidate.selection;
    return {
      candidateKey: id,
      displayLabel: modelLabel(id),
      mode: "single",
      primaryLaw: id,
      reason: "",
      warningAcknowledged: false,
      fitRange,
    };
  };
  const rows: ModelingFitCandidateRow[] = candidates.map((candidate) => {
    const scalarResultAvailable = Number.isFinite(candidate.relative);
    const graphResponseAvailable = candidate.selection.mode === "blend";
    return {
      id: candidate.id,
      label: candidate.label,
      selected: selection?.candidateKey === candidate.id,
      recommended: candidate.id === recommended,
      disabled: !candidate.fit && !scalarResultAvailable && !graphResponseAvailable,
      primaryValue: percent(candidate.relative),
      status: candidate.fit?.convergence
        ? "Calculated"
        : candidate.fit
          ? "Not converged"
          : scalarResultAvailable
            ? "Calculated"
            : graphResponseAvailable
              ? "Response available"
              : "Not available",
      warning: candidate.warning ? "Needs review" : undefined,
    };
  });
  const updateSelection = (patch: Partial<FitDecisionSelection>) => {
    if (selection) onChangeSelection({ ...selection, ...patch });
  };

  const decision = (
    <section className="hardening-fit-selection" aria-labelledby="hardening-fit-selection-heading">
      <header>
        <h2 id="hardening-fit-selection-heading">Engineer selection</h2>
        <span>{stateLabel}</span>
      </header>
      {selection ? <>
        <strong className="hardening-fit-selected-model">{fitDecisionIdentityLabel(selection)}</strong>
        <label>Why this model was selected
          <textarea
            aria-label="Candidate selection reason"
            name="hardening-fit-selection-reason"
            autoComplete="off"
            rows={2}
            value={selection.reason}
            onChange={(event) => updateSelection({ reason: event.target.value })}
          />
        </label>
        {selection.warning ? <label className="hardening-fit-warning"><input
          aria-label="Acknowledge selected candidate warning"
          name="hardening-fit-warning-acknowledgement"
          type="checkbox"
          checked={selection.warningAcknowledged}
          onChange={(event) => updateSelection({ warningAcknowledged: event.target.checked })}
        />I reviewed: {selection.warning}</label> : null}
        <footer>
          <button className="button primary" type="button" disabled={busy || !saveReady} onClick={onSave}>
            {busy ? "Saving…" : "Save fit & continue"}
          </button>
        </footer>
      </> : <p>No model selected</p>}
    </section>
  );

  return (
    <ModelingFitCandidateComparison
      rows={rows}
      primaryColumnLabel="Fit difference"
      rangeLabel={`Plastic strain ${fitRange}`}
      selectionLocked={stateLabel === "Saved current"}
      onSelect={(id) => onSelect(candidateSelection(id))}
      decision={decision}
    />
  );
}
