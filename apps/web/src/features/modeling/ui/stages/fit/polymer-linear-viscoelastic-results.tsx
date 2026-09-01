import type { LinearViscoelasticCandidate } from "../../../model/linear-viscoelastic-calibration-contracts";
import type { LinearViscoelasticCalibrationState } from "../../../model/linear-viscoelastic-calibration-state";
import {
  formatPolymerFitNumber,
  polymerCandidateParameterLabel,
} from "./polymer-linear-viscoelastic-format";
import { polymerWarningLabel } from "./polymer-linear-viscoelastic-warning";
import "./polymer-linear-viscoelastic-panel.css";
import "./polymer-linear-viscoelastic-results.css";

interface PolymerLinearViscoelasticResultsProps {
  state: LinearViscoelasticCalibrationState;
  selectedCandidate?: LinearViscoelasticCandidate;
  recommendedCandidateId?: string;
  warnings: string[];
  acknowledgedWarnings: Set<string>;
  onClearSelection: () => void;
  onSelectionReasonChange: (reason: string) => void;
  onWarningAcknowledgementChange: (warning: string, checked: boolean) => void;
  onSaveFit: () => void;
  onContinue: () => void;
}

export function PolymerLinearViscoelasticResults({
  state,
  selectedCandidate,
  recommendedCandidateId,
  warnings,
  acknowledgedWarnings,
  onClearSelection,
  onSelectionReasonChange,
  onWarningAcknowledgementChange,
  onSaveFit,
  onContinue,
}: PolymerLinearViscoelasticResultsProps) {
  if (!state.candidates.length) return null;
  const saving = state.phase === "saving-selection" || state.phase === "saving-model";
  const selectionReady = Boolean(
    selectedCandidate?.candidate_sha256
      && state.reason.trim()
      && warnings.every((warning) => acknowledgedWarnings.has(warning)),
  );
  const saveBlocked = saving || Boolean(state.selectedModel) || (!state.selection && !selectionReady);
  const selectedIsRecommended = selectedCandidate?.candidate_id === recommendedCandidateId;

  return (
    <section className="polymer-fit-results-layout" aria-labelledby="polymer-results-heading">
      <header className="polymer-results-heading">
        <h2 id="polymer-results-heading">Engineer selection</h2>
        {selectedCandidate ? <div className="polymer-selected-model">
          <strong>{selectedCandidate.term_count}-term Prony</strong>
          {selectedIsRecommended ? <span>Recommended</span> : null}
        </div> : <span className="polymer-selection-empty">No model selected</span>}
      </header>

      {selectedCandidate ? (
        <section className="polymer-selection-section">
          <label className="polymer-selection-reason">Why this model was selected
            <textarea
              name="selection-reason"
              autoComplete="off"
              rows={2}
              value={state.reason}
              disabled={Boolean(state.selection)}
              aria-label="Reason for selection"
              onChange={(event) => onSelectionReasonChange(event.target.value)}
            />
          </label>
          {warnings.length ? (
            <fieldset className="polymer-warning-list">
              <legend>Warnings for the selected model</legend>
              {warnings.map((warning) => (
                <label key={warning}><input
                  name={`warning-${warning}`}
                  type="checkbox"
                  checked={acknowledgedWarnings.has(warning)}
                  disabled={Boolean(state.selection)}
                  onChange={(event) => onWarningAcknowledgementChange(warning, event.target.checked)}
                />{polymerWarningLabel(warning)}</label>
              ))}
            </fieldset>
          ) : null}
          <footer className="polymer-selection-actions">
            {state.selection && !state.selectedModel ? <button type="button" className="button secondary" disabled={saving} onClick={onClearSelection}>Change selection</button> : null}
            <button
              type="button"
              className="button primary"
              disabled={state.selectedModel ? false : saveBlocked}
              onClick={state.selectedModel ? onContinue : onSaveFit}
            >
              {saving ? "Saving…" : state.selectedModel ? "Continue to Export" : state.selection ? "Retry save & continue" : "Save fit & continue"}
            </button>
          </footer>
          <details className="polymer-model-coefficients">
            <summary>Model coefficients</summary>
            <div><table><caption>{selectedCandidate.term_count}-term Prony coefficients</caption><thead><tr><th scope="col">Parameter</th><th scope="col">Value</th><th scope="col">Unit</th></tr></thead><tbody>{selectedCandidate.physical_parameters.map((value, index) => (
              <tr key={`${index}:${value}`}><th scope="row">{polymerCandidateParameterLabel(index, selectedCandidate.term_count)}</th><td>{formatPolymerFitNumber(value)}</td><td>{index <= selectedCandidate.term_count ? "Pa" : "s"}</td></tr>
            ))}</tbody></table></div>
          </details>
        </section>
      ) : null}
    </section>
  );
}
