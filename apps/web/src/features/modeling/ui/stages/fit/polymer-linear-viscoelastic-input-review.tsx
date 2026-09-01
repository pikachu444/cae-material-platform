import "./polymer-linear-viscoelastic-input-review.css";

export interface PolymerInputReviewItem {
  label: string;
  value: string;
}

interface PolymerLinearViscoelasticInputReviewProps {
  items: PolymerInputReviewItem[];
  setupStatus: "approved" | "loading" | "missing" | "multiple" | "inactive" | "review" | "error";
  setupOptions?: Array<{ id: string; label: string }>;
  busy: boolean;
  onChooseSetup?: (id: string) => void;
  onReviewSetup?: () => void;
  onRetrySetup?: () => void;
  onCalculate: () => void;
}

const STATUS_LABELS: Record<PolymerLinearViscoelasticInputReviewProps["setupStatus"], string> = {
  approved: "",
  loading: "Loading calculation settings…",
  missing: "Calculation settings need review",
  multiple: "Choose calculation settings",
  inactive: "Calculation input unavailable",
  review: "Calculation review is pending",
  error: "Calculation settings unavailable",
};

export function PolymerLinearViscoelasticInputReview({
  items,
  setupStatus,
  setupOptions = [],
  busy,
  onChooseSetup,
  onReviewSetup,
  onRetrySetup,
  onCalculate,
}: PolymerLinearViscoelasticInputReviewProps) {
  const ready = setupStatus === "approved";
  return (
    <section className="polymer-input-review" aria-label="Calculate Prony models">
      <details className="polymer-input-review-values">
        <summary>Input details</summary>
        <dl>{items.map((item) => <div key={item.label}><dt>{item.label}</dt><dd title={item.value}>{item.value}</dd></div>)}</dl>
      </details>
      <div className="polymer-input-review-calculation">
        {setupStatus === "multiple" ? (
          <label className="polymer-setup-choice">Calculation settings
            <select name="approved-calculation-settings" defaultValue="" onChange={(event) => onChooseSetup?.(event.target.value)}>
              <option value="" disabled>Choose settings</option>
              {setupOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
            </select>
          </label>
        ) : setupStatus !== "approved" ? (
          <span className={`polymer-setup-status ${setupStatus}`}>{STATUS_LABELS[setupStatus]}</span>
        ) : null}
        {setupStatus === "missing" && onReviewSetup
          ? <button type="button" className="button primary" disabled={busy} onClick={onReviewSetup}>Review calculation settings</button>
          : setupStatus === "review" && onRetrySetup
            ? <button type="button" className="button secondary" disabled={busy} onClick={onRetrySetup}>Check review status</button>
            : setupStatus === "error" && onRetrySetup
          ? <button type="button" className="button secondary" onClick={onRetrySetup}>Retry</button>
          : null}
        {ready ? <button type="button" className="button primary" disabled={busy} onClick={onCalculate}>{busy ? "Calculating…" : "Calculate Prony models"}</button> : null}
      </div>
    </section>
  );
}
