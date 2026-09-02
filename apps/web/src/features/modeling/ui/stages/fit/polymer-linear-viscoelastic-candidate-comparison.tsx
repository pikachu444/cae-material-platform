import type { ReactNode } from "react";

import type {
  LinearViscoelasticCandidate,
  LinearViscoelasticWeights,
} from "../../../model/linear-viscoelastic-calibration-contracts";
import type { LinearViscoelasticCalibrationState } from "../../../model/linear-viscoelastic-calibration-state";
import type { PolymerMeasuredRange } from "./polymer-linear-viscoelastic-fit-view";
import { formatPolymerDeviation } from "./polymer-linear-viscoelastic-format";
import {
  ModelingFitCandidateComparison,
  type ModelingFitCandidateRow,
} from "./modeling-fit-candidate-comparison";
import {
  meanAbsolutePolymerRelativeDeviation,
  type PolymerObservedSeries,
} from "./polymer-linear-viscoelastic-presentation";
import { polymerWarningLabel } from "./polymer-linear-viscoelastic-warning";

interface PolymerLinearViscoelasticCandidateComparisonProps {
  state: LinearViscoelasticCalibrationState;
  observedSeries: PolymerObservedSeries[];
  weights?: Partial<LinearViscoelasticWeights>;
  recommendedCandidateId?: string;
  applicationRange: PolymerMeasuredRange | null;
  onSelectCandidate: (candidateId: string) => void;
  decision: ReactNode;
}

function failedAttemptLabel(input: { converged?: boolean; physical?: boolean }): string {
  if (input.converged === false) return "Calculation failed";
  if (input.physical === false) return "Invalid result";
  return "No result";
}

export function PolymerLinearViscoelasticCandidateComparison({
  state,
  observedSeries,
  weights,
  recommendedCandidateId,
  applicationRange,
  onSelectCandidate,
  decision,
}: PolymerLinearViscoelasticCandidateComparisonProps) {
  const orderedCandidates = [...state.candidates].sort((left, right) => (
    left.term_count - right.term_count || left.attempt_ordinal - right.attempt_ordinal
  ));
  const candidateByAttempt = new Map<number, LinearViscoelasticCandidate>(
    orderedCandidates.map((candidate) => [candidate.attempt_ordinal, candidate]),
  );
  const attempts = state.run?.attempts?.length
    ? [...state.run.attempts].sort((left, right) => (
      left.term_count - right.term_count || left.ordinal - right.ordinal
    ))
    : orderedCandidates.map((candidate) => ({
      ordinal: candidate.attempt_ordinal,
      term_count: candidate.term_count,
      converged: true,
      physical: true,
      warnings: candidate.warnings,
    }));
  const rows: ModelingFitCandidateRow[] = attempts.map((attempt) => {
    const candidate = candidateByAttempt.get(attempt.ordinal);
    const warnings = candidate?.warnings ?? attempt.warnings ?? [];
    const fitDifference = candidate
      ? meanAbsolutePolymerRelativeDeviation(observedSeries, candidate, weights, "CALIBRATION")
      : null;
    const checkDifference = candidate
      ? meanAbsolutePolymerRelativeDeviation(observedSeries, candidate, weights, "HOLDOUT")
      : null;
    return {
      id: candidate?.candidate_id ?? `attempt:${attempt.ordinal}`,
      label: `${attempt.term_count}-term Prony`,
      selected: candidate?.candidate_id === state.selectedCandidateId,
      recommended: candidate?.candidate_id === recommendedCandidateId,
      disabled: !candidate,
      primaryValue: fitDifference === null ? "—" : formatPolymerDeviation(fitDifference),
      secondaryValue: checkDifference === null ? "—" : formatPolymerDeviation(checkDifference),
      status: candidate ? "Calculated" : failedAttemptLabel(attempt),
      warning: warnings.length ? warnings.map(polymerWarningLabel).join(" · ") : undefined,
    };
  });
  const rangeLabel = applicationRange
    ? `${applicationRange.quantity} ${applicationRange.from}–${applicationRange.to} ${applicationRange.unit}`
    : undefined;

  return (
    <ModelingFitCandidateComparison
      rows={rows}
      primaryColumnLabel="Fit difference"
      secondaryColumnLabel="Check difference"
      rangeLabel={rangeLabel}
      selectionLocked={Boolean(state.selection)}
      onSelect={onSelectCandidate}
      decision={decision}
    />
  );
}
