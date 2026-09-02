import { useEffect, useRef } from "react";

import { PolymerLinearViscoelasticDataStep } from "./polymer-linear-viscoelastic-data-step";
import { PolymerLinearViscoelasticModelStep } from "./polymer-linear-viscoelastic-model-step";
import type { PolymerFitSetupActions, PolymerFitSetupViewModel } from "./polymer-linear-viscoelastic-setup-types";
import "./polymer-linear-viscoelastic-advanced.css";
import "./polymer-linear-viscoelastic-panel.css";

const WEIGHT_FIELDS = [
  "relaxation_weight",
  "relaxation_scale_pa",
  "dma_storage_weight",
  "dma_loss_weight",
  "dma_storage_scale_pa",
  "dma_loss_scale_pa",
] as const;
type VisibleWeightField = typeof WEIGHT_FIELDS[number];

const DIFF_LABELS: Record<string, string> = {
  input_semantics: "Measured values and input conditions",
  term_counts: "Prony models",
  parameter_bounds: "Parameter ranges",
  start_vectors: "Initial values",
  weights: "Objective weights and scales",
  optimizer: "Solver limits",
  statuses: "Recorded test conditions",
  recommendation_policy: "Recommendation rule",
};

const WEIGHT_LABELS: Record<VisibleWeightField, { label: string; unit: string }> = {
  relaxation_weight: { label: "Relaxation response weight", unit: "0–1" },
  dma_storage_weight: { label: "Storage modulus weight", unit: "0–1" },
  dma_loss_weight: { label: "Loss modulus weight", unit: "0–1" },
  relaxation_scale_pa: { label: "Relaxation modulus scale", unit: "Pa" },
  dma_storage_scale_pa: { label: "Storage modulus scale", unit: "Pa" },
  dma_loss_scale_pa: { label: "Loss modulus scale", unit: "Pa" },
};

interface PolymerLinearViscoelasticAdvancedProps {
  view: PolymerFitSetupViewModel;
  actions: PolymerFitSetupActions;
  busy: boolean;
  onClose: () => void;
  onReset: () => void;
  onCreateDraft: () => void;
}

export function PolymerLinearViscoelasticAdvanced({
  view,
  actions,
  busy,
  onClose,
  onReset,
  onCreateDraft,
}: PolymerLinearViscoelasticAdvancedProps) {
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const dialogRef = useRef<HTMLElement | null>(null);
  const blocked = Boolean(view.directBlockers.length || view.modelBlockers.length || view.solverBlockers.length || !view.changeReason.trim());

  useEffect(() => {
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const handleDialogKeys = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const controls = [...(dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ) ?? [])].filter((element) => element.getClientRects().length > 0 || element === document.activeElement);
      if (!controls.length) return;
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleDialogKeys);
    return () => {
      window.removeEventListener("keydown", handleDialogKeys);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  return (
    <div className="polymer-advanced-backdrop">
      <section ref={dialogRef} className="polymer-advanced-dialog" role="dialog" aria-modal="true" aria-labelledby="polymer-advanced-heading">
        <header>
          <div><h2 id="polymer-advanced-heading">Calculation settings</h2>{view.reviewStatus === "pending" ? <span>Review requested</span> : null}</div>
          <button ref={closeRef} type="button" className="button secondary" onClick={onClose}>Close</button>
        </header>
        <div className="polymer-advanced-scroll">
          <section className="polymer-advanced-identity" aria-labelledby="polymer-advanced-identity-heading">
            <h2 id="polymer-advanced-identity-heading">Setup</h2>
            <div>
              <label>Setup name
                <input name="plan-setup-name" autoComplete="off" value={view.setupName} onChange={(event) => actions.setSetupName(event.target.value)} />
              </label>
              {view.baseSetupName ? <label>Based on<input name="plan-base-setup-name" autoComplete="off" value={view.baseSetupName} readOnly /></label> : null}
              {view.baseSetupName ? <label className="polymer-advanced-wide-field">Reason for changing the current settings
                <textarea rows={2} name="plan-override-reason" autoComplete="off" value={view.overrideReason} onChange={(event) => actions.setOverrideReason(event.target.value)} />
              </label> : null}
            </div>
          </section>
          <PolymerLinearViscoelasticDataStep view={view} actions={actions} />
          <PolymerLinearViscoelasticModelStep view={view} actions={actions} />
          <section className="polymer-advanced-policy" aria-labelledby="polymer-advanced-policy-heading">
            <h2 id="polymer-advanced-policy-heading">Calculation policy</h2>
            <div className="polymer-advanced-policy-grid">
              <table><caption>Objective weights and scales</caption><tbody>{WEIGHT_FIELDS.map((key) => (
                <tr key={key}><th scope="row">{WEIGHT_LABELS[key].label}</th><td><input
                  aria-label={`${WEIGHT_LABELS[key].label} (${WEIGHT_LABELS[key].unit})`}
                  name={key}
                  type="text"
                  inputMode="decimal"
                  autoComplete="off"
                  spellCheck={false}
                  value={view.weights[key]}
                  onChange={(event) => actions.setWeight(key, event.target.value)}
                /></td><td>{WEIGHT_LABELS[key].unit}</td></tr>
              ))}</tbody></table>
              <table><caption>Solver limits</caption><tbody>{(["ftol", "xtol", "gtol", "max_nfev"] as const).map((key) => (
                <tr key={key}><th scope="row">{{ ftol: "Function tolerance", xtol: "Parameter tolerance", gtol: "Gradient tolerance", max_nfev: "Maximum evaluations" }[key]}</th><td><input
                  aria-label={{ ftol: "Function tolerance", xtol: "Parameter tolerance", gtol: "Gradient tolerance", max_nfev: "Maximum evaluations" }[key]}
                  name={`optimizer-${key}`}
                  type="text"
                  inputMode="decimal"
                  autoComplete="off"
                  spellCheck={false}
                  value={view.optimizer[key]}
                  onChange={(event) => actions.setOptimizer(key, event.target.value)}
                /></td></tr>
              ))}</tbody></table>
            </div>
          </section>
          <label className="polymer-advanced-reason">Reason for this setup
            <textarea rows={2} name="plan-change-reason" autoComplete="off" value={view.changeReason} onChange={(event) => actions.setChangeReason(event.target.value)} />
          </label>
          {view.serverDiff ? <section className="polymer-advanced-diff" aria-labelledby="polymer-advanced-diff-heading">
            <h2 id="polymer-advanced-diff-heading">Changes sent for review</h2>
            {Object.keys(view.serverDiff).length
              ? <ul>{Object.keys(view.serverDiff).map((key) => <li key={key}>{DIFF_LABELS[key] ?? "Calculation setting"}</li>)}</ul>
              : <p>No calculation values changed.</p>}
          </section> : null}
          {view.solverBlockers.length ? <div className="polymer-validation-summary" role="alert"><strong>Calculation setup needs review</strong><ul>{view.solverBlockers.map((blocker) => <li key={blocker}>{blocker}</li>)}</ul></div> : null}
        </div>
        <footer>
          <button type="button" className="button secondary" disabled={busy} onClick={onReset}>Restore calculation defaults</button>
          <button type="button" className="button primary" disabled={blocked || busy || view.reviewStatus === "pending"} onClick={onCreateDraft}>{view.reviewStatus === "pending" ? "Review requested" : busy ? "Submitting…" : "Request settings review"}</button>
        </footer>
      </section>
    </div>
  );
}
