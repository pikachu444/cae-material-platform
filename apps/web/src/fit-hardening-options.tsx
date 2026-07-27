import type { CommonProcessingStep } from "./types";

const FAMILIES = [
  { value: "voce", label: "Voce" },
  { value: "swift", label: "Swift" },
  { value: "hockett_sherby", label: "Hockett–Sherby" },
  { value: "ghosh", label: "Ghosh" },
] as const;

interface Props {
  step: CommonProcessingStep;
  onChange: (key: string, value: unknown) => void;
  graphInteraction: { mode: "pan" | "range" | "point"; canApply: boolean; available: boolean };
  onGraphModeChange: (mode: "pan" | "range" | "point") => void;
  onApplyGraphSelection: () => void;
}

const numeric = (step: CommonProcessingStep, key: string) => Number(step.options[key] ?? 0);

export function HardeningFitOptions({ step, onChange, graphInteraction, onGraphModeChange, onApplyGraphSelection }: Props) {
  const families = Array.isArray(step.options.families) ? step.options.families.map(String) : [];
  const toggle = (family: string) => onChange("families", families.includes(family) ? families.filter((item) => item !== family) : [...families, family]);
  return <div className="guided-step-options">
    <fieldset className="fit-control-group candidate-check-grid"><legend>Candidate equations</legend>{FAMILIES.map((family) => <label key={family.value}><input aria-label={`Include ${family.label} candidate`} type="checkbox" checked={families.includes(family.value)} onChange={() => toggle(family.value)} />{family.label}</label>)}</fieldset>
    <fieldset className="fit-control-group"><legend>Fit domain</legend><div className="guided-range-row"><label>Start<input type="number" step="any" value={numeric(step, "fit_minimum_strain")} onChange={(event) => onChange("fit_minimum_strain", Number(event.target.value))}/></label><label>End<input type="number" step="any" value={numeric(step, "fit_maximum_strain")} onChange={(event) => onChange("fit_maximum_strain", Number(event.target.value))}/></label></div></fieldset>
    <fieldset className="fit-control-group selected-blend-group"><legend>Selected blend</legend><label>Primary<select aria-label="Primary hardening law" value={String(step.options.primary_family)} onChange={(event) => onChange("primary_family", event.target.value)}>{FAMILIES.map((family) => <option key={family.value} value={family.value}>{family.label}</option>)}</select></label><label>Secondary<select aria-label="Secondary hardening law" value={String(step.options.secondary_family)} onChange={(event) => onChange("secondary_family", event.target.value)}>{FAMILIES.map((family) => <option key={family.value} value={family.value}>{family.label}</option>)}</select></label></fieldset>
    <fieldset className="fit-control-group contribution-group"><legend>Primary contribution</legend><label className="slider-option"><span><input aria-label="Primary hardening contribution" type="range" min="0" max="1" step="0.01" value={numeric(step, "primary_weight")} onChange={(event) => onChange("primary_weight", Number(event.target.value))}/><output>{Math.round(numeric(step, "primary_weight") * 100)}%</output></span></label><label>Review metric<select aria-label="Fit review metric" value="relative_rmse" disabled><option value="relative_rmse">Relative RMSE</option></select></label></fieldset>
    <fieldset className="fit-control-group extrapolation-group"><legend>Extrapolation</legend><label>Target strain<input type="number" min="0" max="5" step="0.01" value={numeric(step, "extrapolation_maximum_strain")} onChange={(event) => onChange("extrapolation_maximum_strain", Number(event.target.value))}/></label><label>Output points<input aria-label="Output points" type="number" min="21" max="501" step="1" value={numeric(step, "output_point_count")} onChange={(event) => onChange("output_point_count", Number(event.target.value))}/></label></fieldset>
    <fieldset className="fit-control-group graph-interaction-group"><legend>Graph interaction</legend><div><button type="button" disabled={!graphInteraction.available} className={graphInteraction.mode === "range" ? "active" : ""} aria-pressed={graphInteraction.mode === "range"} onClick={() => onGraphModeChange(graphInteraction.mode === "range" ? "pan" : "range")}>Select fit range</button><button type="button" disabled={!graphInteraction.available} className={graphInteraction.mode === "point" ? "active" : ""} aria-pressed={graphInteraction.mode === "point"} onClick={() => onGraphModeChange(graphInteraction.mode === "point" ? "pan" : "point")}>Pick point</button>{graphInteraction.canApply ? <button type="button" onClick={onApplyGraphSelection}>Apply</button> : null}</div></fieldset>
  </div>;
}
