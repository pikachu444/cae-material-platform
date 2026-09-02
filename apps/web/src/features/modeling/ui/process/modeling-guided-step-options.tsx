import { lazy, Suspense } from "react";

import type { PlotInteractionMode } from "../../../../engineering-curve-plot";
import type { CommonCurveStage, CommonProcessingStep } from "../../model/common-processing-contracts";
import {
  PRONY_TERM_COUNTS,
  manualModulusDisplayValue,
  manualModulusPascals,
  modulusDisplayUnit,
  numberOption,
} from "../../model/processing-registry";

const HardeningFitOptions = lazy(() => import("../../../../fit-hardening-options").then((module) => ({ default: module.HardeningFitOptions })));

export function ModelingGuidedStepOptions({
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
      <label className="slider-option">Proof offset <output>{(numberOption(step, "offset_strain") * 100).toFixed(2)}%</output><input aria-label="Proof stress offset" type="range" min="0.05" max="1" step="0.05" value={numberOption(step, "offset_strain") * 100} onChange={(event) => onChange("offset_strain", Number(event.target.value) / 100)}/></label>
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
      <p className="option-hint">{dma ? "Storage and loss modulus are fitted jointly with one parameter set. " : ""}This policy is input intent. For automatic selection, the server&apos;s actual selected term count and metrics are the result identity; manual use still requires an explicit candidate-row selection.</p>
    </div>;
  }
  return <div className="step-option-grid">{Object.entries(step.options).map(([option, value]) => <label key={option}>{option.replaceAll("_", " ")}{typeof value === "boolean" ? <input type="checkbox" checked={value} onChange={(event) => onChange(option, event.target.checked)} /> : <input value={Array.isArray(value) ? value.join(", ") : String(value)} type={typeof value === "number" ? "number" : "text"} onChange={(event) => onChange(option, typeof value === "number" ? Number(event.target.value) : Array.isArray(value) ? event.target.value.split(",").map((item) => item.trim()).filter(Boolean) : event.target.value)} />}</label>)}</div>;
}
