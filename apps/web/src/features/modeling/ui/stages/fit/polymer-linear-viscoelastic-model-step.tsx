import { useState } from "react";

import {
  automaticPolymerTermCounts,
  blankPolymerBounds,
  polymerPronyParameterCount,
} from "../../../model/linear-viscoelastic-calibration-draft";
import {
  formatPolymerInputNumber,
  polymerParameterLabel,
} from "./polymer-linear-viscoelastic-format";
import type {
  PolymerFitSetupActions,
  PolymerFitSetupViewModel,
} from "./polymer-linear-viscoelastic-setup-types";
import "./polymer-linear-viscoelastic-model-step.css";

const TERM_CHOICES = Array.from({ length: 10 }, (_, index) => index + 1);

interface PolymerLinearViscoelasticModelStepProps {
  view: PolymerFitSetupViewModel;
  actions: PolymerFitSetupActions;
}

export function PolymerLinearViscoelasticModelStep({
  view,
  actions,
}: PolymerLinearViscoelasticModelStepProps) {
  const { termCounts, bounds, modelBlockers, fitObservationCount } = view;
  const automatic = view.candidateScopeMode === "automatic";
  const automaticTerms = automaticPolymerTermCounts(fitObservationCount);
  const [preferredTerm, setPreferredTerm] = useState<number | null>(null);
  const editingTerm = preferredTerm && termCounts.includes(preferredTerm)
    ? preferredTerm
    : termCounts.at(-1) ?? null;
  const editingBounds = editingTerm === null ? [] : bounds[String(editingTerm)] ?? blankPolymerBounds(editingTerm);

  return (
    <section className="polymer-fit-work-step polymer-model-step" aria-labelledby="polymer-model-step-heading">
      <header className="polymer-work-step-heading">
        <h2 id="polymer-model-step-heading">Prony models</h2>
      </header>
      <div className="polymer-model-step-body">
        <fieldset className="polymer-candidate-scope">
          <legend>Candidate scope</legend>
          <label>
            <input
              name="candidate-scope-mode"
              type="radio"
              value="automatic"
              checked={automatic}
              onChange={() => actions.setCandidateScopeMode("automatic")}
            />
            <span>Automatic</span>
          </label>
          <label>
            <input
              name="candidate-scope-mode"
              type="radio"
              value="manual"
              checked={!automatic}
              onChange={() => actions.setCandidateScopeMode("manual")}
            />
            <span>Manual</span>
          </label>
        </fieldset>

        {automatic ? (
          <div className="polymer-model-automatic" role="status">
            {automaticTerms.length
              ? `Fit will compare every feasible Prony term from ${automaticTerms[0]} through ${automaticTerms.at(-1)}.`
              : "The selected data does not yet provide a feasible Prony term."}
          </div>
        ) : <>
          <fieldset className="polymer-term-choice">
            <legend>Terms to compare</legend>
            {TERM_CHOICES.map((term) => {
              const parameterCount = polymerPronyParameterCount(term);
              const unavailable = parameterCount > fitObservationCount;
              return (
              <label
                key={term}
                className={`${termCounts.includes(term) ? "selected" : ""}${unavailable ? " unavailable" : ""}`.trim() || undefined}
              >
                <input
                  name={`term-count-${term}`}
                  type="checkbox"
                  checked={termCounts.includes(term)}
                  disabled={unavailable && !termCounts.includes(term)}
                  aria-label={`${term}-term Prony, ${parameterCount} parameters${unavailable ? `, unavailable with ${fitObservationCount} values` : ""}`}
                  onChange={() => {
                    actions.toggleTerm(term);
                    if (!termCounts.includes(term)) setPreferredTerm(term);
                  }}
                />
                <span>{term}-term</span>
              </label>
            );})}
          </fieldset>

          {editingTerm === null ? (
            <div className="polymer-model-empty" role="status">Choose at least one Prony model.</div>
          ) : (
            <section
              className="polymer-bound-editor"
              aria-labelledby="polymer-bound-editor-heading"
              tabIndex={0}
            >
              <header>
                <h3 id="polymer-bound-editor-heading">Parameter ranges</h3>
                <label>Model
                  <select name="prony-model-range" value={editingTerm} onChange={(event) => setPreferredTerm(Number(event.target.value))}>
                    {termCounts.map((term) => <option key={term} value={term}>{term}-term Prony</option>)}
                  </select>
                </label>
              </header>
              <table className="polymer-bound-table">
                <thead><tr><th scope="col">Parameter</th><th scope="col">Initial value</th><th scope="col">Minimum</th><th scope="col">Maximum</th><th scope="col">Unit</th></tr></thead>
                <tbody>{editingBounds.map((item, index) => (
                  <tr key={item.name}>
                    <th scope="row">{polymerParameterLabel(item.name)}</th>
                    {(["start", "lower", "upper"] as const).map((key) => (
                      <td key={key}><input
                        name={`${editingTerm}-${item.name}-${key}`}
                        aria-label={`${editingTerm}-term ${polymerParameterLabel(item.name)} ${key}`}
                        type="text"
                        inputMode="decimal"
                        autoComplete="off"
                        spellCheck={false}
                        value={formatPolymerInputNumber(item[key])}
                        onChange={(event) => actions.updateBound(editingTerm, index, key, event.target.value)}
                      /></td>
                    ))}
                    <td>{item.unit}</td>
                  </tr>
                ))}</tbody>
              </table>
            </section>
          )}
        </>}
      </div>
      {modelBlockers.length ? <div className="polymer-validation-summary" role="alert"><strong>Prony models need review</strong><ul>{modelBlockers.map((blocker) => <li key={blocker}>{blocker}</li>)}</ul></div> : null}
    </section>
  );
}
