import { useMemo } from "react";

import { ModelingWorkspaceLayout } from "../../../../../design/modeling-workspace-layout";
import { WorkbenchMessage } from "../../../../../design/semantic-ui";
import { EngineeringCurvePlot } from "../../../../../engineering-curve-plot";
import type { ApiConfig } from "../../../../../shared/api";
import type { CanonicalTestDataDocumentResponse } from "../../../../test-data/contracts";
import { useDmaTtsProcess } from "../../../controller/use-dma-tts-process";
import type { CreateDmaTtsResponse, DmaTtsPartition } from "../../../model/dma-tts-contracts";
import {
  dmaMasterCurvePreview,
  dmaMultiFrequencyObservedCurves,
  dmaMultiFrequencyPreview,
  dmaReadBackObservedCurves,
  dmaReadBackPreview,
  dmaTemperatureSweepPreview,
} from "../../../model/dma-tts-presentation";
import "./dma-tts-process-workspace.css";

export interface DmaTtsProcessWorkspaceProps {
  config: ApiConfig;
  testData: CanonicalTestDataDocumentResponse;
  sourceDocument: Record<string, unknown>;
  initialOutput?: { id: string; revisionId: string; contentSha256: string };
  chart: { width: number; height: number };
  ribbonOpen: boolean;
  onRibbonOpenChange: (open: boolean) => void;
  onSaved: (created: CreateDmaTtsResponse) => Promise<void> | void;
  onContinue: () => void;
}

const PARTITION_LABELS: Record<DmaTtsPartition, string> = {
  CALIBRATION: "Fit",
  HOLDOUT: "Validate",
  EXCLUDED: "Ignore",
};

const PARTITION_OPTION_LABELS: Record<DmaTtsPartition, string> = {
  CALIBRATION: "Fit — calculate TTS",
  HOLDOUT: "Validate — check result only",
  EXCLUDED: "Ignore — exclude",
};

const SHIFT_LAW_LABELS: Record<string, string> = {
  wlf: "WLF",
  wlf_fit: "WLF fit",
  arrhenius: "Arrhenius",
  arrhenius_fit: "Arrhenius fit",
  manual_tabulated: "Manual",
};

const ASSESSMENT_LABELS: Record<string, string> = {
  not_assessed: "Not assessed",
  not_provided: "Not provided",
  non_production: "Not ready for production",
};

const WARNING_LABELS: Record<string, string> = {
  DMA_TTS_LVR_EVIDENCE_MISSING: "Linear viscoelastic range evidence is missing.",
  DMA_TTS_TEMPERATURE_EQUILIBRIUM_EVIDENCE_MISSING: "Temperature equilibrium evidence is missing.",
  DMA_TTS_PRECONDITIONING_EVIDENCE_MISSING: "Preconditioning evidence is missing.",
};

function compact(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumSignificantDigits: 5 }).format(value);
}

function rawRange(minimum: number, maximum: number, unit: string): string {
  return `${compact(minimum)}–${compact(maximum)} ${unit}`;
}

function statusText(status: string): string {
  switch (status) {
    case "preparing": return "Preparing a read-only recommendation…";
    case "saving": return "Saving one immutable TTS result and verifying its exact read-back…";
    case "saved": return "";
    case "read_error": return "The result pin exists, but exact read-back or Fit linking needs a retry.";
    case "save_outcome_unknown": return "Save outcome unknown; the create request will not be retried automatically.";
    default: return "";
  }
}

function backendValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return Number.isFinite(value) ? compact(value) : "—";
  if (typeof value === "string" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value) ?? "—";
  } catch {
    return "—";
  }
}

function MultiSweepRail({
  source,
  visibleSweepOrdinals,
  onToggle,
}: {
  source: NonNullable<ReturnType<typeof useDmaTtsProcess>["multiSource"]>;
  visibleSweepOrdinals: number[];
  onToggle: (ordinal: number) => void;
}) {
  return <nav className="dma-tts-sweep-rail" aria-label="DMA graph curve visibility">
    <div className="dma-tts-rail-heading"><span>Curves on graph</span><span>Show</span></div>
    <div className="dma-tts-sweep-list" tabIndex={0} aria-label="Temperature curves visible on graph">
      {source.sweeps.map((sweep) => {
        const visible = visibleSweepOrdinals.includes(sweep.sourceSweepOrdinal);
        return <label className="dma-tts-sweep-entry" key={sweep.sourceSweepOrdinal}>
          <strong>{compact(sweep.representativeTemperatureK)} K</strong>
          <input type="checkbox" aria-label={`Show ${compact(sweep.representativeTemperatureK)} K on graph`} checked={visible} onChange={() => onToggle(sweep.sourceSweepOrdinal)} />
        </label>;
      })}
    </div>
  </nav>;
}

export function DmaTtsProcessWorkspace({
  config,
  testData,
  sourceDocument,
  initialOutput,
  chart,
  ribbonOpen,
  onRibbonOpenChange,
  onSaved,
  onContinue,
}: DmaTtsProcessWorkspaceProps) {
  const process = useDmaTtsProcess({ config, testData, sourceDocument, initialOutput, onSaved });
  const isMulti = process.inputMode === "multi_frequency_isotherms" && process.multiSource;
  const plot = useMemo(() => {
    if (process.readBack) return dmaReadBackPreview(process.readBack, process.visibleSweepOrdinals);
    if (process.fitInput) return dmaMasterCurvePreview(process.fitInput);
    if (process.multiSource) return dmaMultiFrequencyPreview(process.multiSource, process.visibleSweepOrdinals);
    if (process.fixedSource) return dmaTemperatureSweepPreview(process.fixedSource);
    return null;
  }, [process.fitInput, process.fixedSource, process.multiSource, process.readBack, process.visibleSweepOrdinals]);
  const observedCurves = useMemo(() => process.readBack
    ? dmaReadBackObservedCurves(process.readBack, process.visibleSweepOrdinals)
    : process.multiSource
      ? dmaMultiFrequencyObservedCurves(process.multiSource, process.visibleSweepOrdinals)
      : undefined,
  [process.multiSource, process.readBack, process.visibleSweepOrdinals]);
  const stage = plot?.stages[0];
  const fixedDraft = process.draft?.inputMode === "fixed_frequency_temperature_sweep" ? process.draft : null;
  const multiDraft = process.draft?.inputMode === "multi_frequency_isotherms" ? process.draft : null;
  const fixedRecommendation = process.recommendation?.input_mode === "multi_frequency_isotherms" ? null : process.recommendation;
  const multiRecommendation = process.recommendation?.input_mode === "multi_frequency_isotherms" ? process.recommendation : null;
  const settingsEdited = Boolean(fixedDraft && fixedRecommendation && (
    Number(fixedDraft.referenceTemperatureK) !== fixedRecommendation.reference_temperature_k
    || Number(fixedDraft.c1) !== fixedRecommendation.c1
    || Number(fixedDraft.c2K) !== fixedRecommendation.c2_k
  )) || Boolean(multiDraft && multiRecommendation && (
    JSON.stringify({
      referenceTemperatureK: multiDraft.referenceTemperatureK,
      shiftLawKind: multiDraft.shiftLawKind,
      initialParameters: multiDraft.initialParameters,
      lowerBounds: multiDraft.lowerBounds,
      upperBounds: multiDraft.upperBounds,
      manualTable: multiDraft.manualTable,
      scoring: multiDraft.scoring,
      adjacentOptimizer: multiDraft.adjacentOptimizer,
      lawOptimizer: multiDraft.lawOptimizer,
      sweepDispositions: multiDraft.sweepDispositions,
    }) !== JSON.stringify({
      referenceTemperatureK: String(multiRecommendation.reference_temperature_k),
      shiftLawKind: multiRecommendation.shift_law.kind,
      initialParameters: multiRecommendation.shift_law.initial_parameters.map(String),
      lowerBounds: multiRecommendation.shift_law.lower_bounds.map(String),
      upperBounds: multiRecommendation.shift_law.upper_bounds.map(String),
      manualTable: [],
      scoring: multiRecommendation.scoring,
      adjacentOptimizer: multiRecommendation.adjacent_optimizer,
      lawOptimizer: multiRecommendation.law_optimizer,
      sweepDispositions: multiRecommendation.sweep_dispositions,
    })
  ));
  const graphTitle = process.readBack
    ? "Saved DMA response"
    : isMulti ? "DMA frequency isotherms" : "DMA temperature sweep";
  const includedCount = fixedDraft?.dispositions.filter((item) => item.partition !== "EXCLUDED").length
    ?? multiDraft?.sweepDispositions.filter((item) => item.partition !== "EXCLUDED").length ?? 0;
  const referenceCurve = process.multiSource?.sweeps.find((sweep) => sweep.sourceSweepOrdinal === multiDraft?.referenceSweepOrdinal);
  const savedOptions = process.readBack?.options ?? {};
  const savedAssessment = savedOptions.assessment;
  const savedShiftLaw = savedOptions.shift_law;
  const savedApplicationRange = savedOptions.application_range;
  const savedWarnings = savedOptions.warnings ?? [];
  const savedFrequencyRange = savedApplicationRange?.reduced_angular_frequency_intervals_rad_per_s
    .map((interval) => rawRange(interval.minimum, interval.maximum, "rad/s"))
    .join(", ") ?? "—";
  const savedTemperatureRange = savedApplicationRange
    ? rawRange(
      savedApplicationRange.calibration_temperature_interval_k.minimum,
      savedApplicationRange.calibration_temperature_interval_k.maximum,
      "K",
    )
    : "—";
  const commandTitle = process.readBack
    ? "3. Continue to Prony Fit"
    : process.recommendation ? "2. Review and save" : "1. Prepare the DMA master curve";

  function numberField(value: number): string {
    return Number.isFinite(value) ? String(value) : "";
  }

  function setMultiLawKind(kind: "wlf_fit" | "arrhenius_fit" | "manual_tabulated"): void {
    if (!multiDraft) return;
    const included = multiDraft.sweepDispositions.filter((item) => item.partition !== "EXCLUDED");
    if (kind === "manual_tabulated") {
      process.updateDraft({
        shiftLawKind: kind,
        initialParameters: [],
        lowerBounds: [],
        upperBounds: [],
        lawOptimizer: null,
        manualTable: included.map((item) => {
          const previous = multiDraft.manualTable.find((row) => Number(row.temperatureK) === item.representative_temperature_k);
          return {
            temperatureK: String(item.representative_temperature_k),
            log10At: previous?.log10At ?? (item.source_sweep_ordinal === multiDraft.referenceSweepOrdinal ? "0" : ""),
          };
        }),
        reason: "",
      });
      return;
    }
    const length = kind === "wlf_fit" ? 2 : 1;
    const values = multiDraft.shiftLawKind === kind && multiDraft.initialParameters.length === length
      ? multiDraft.initialParameters
      : Array.from({ length }, () => "");
    const lower = multiDraft.shiftLawKind === kind && multiDraft.lowerBounds.length === length
      ? multiDraft.lowerBounds
      : Array.from({ length }, () => "");
    const upper = multiDraft.shiftLawKind === kind && multiDraft.upperBounds.length === length
      ? multiDraft.upperBounds
      : Array.from({ length }, () => "");
    const currentOptimizer = multiDraft.shiftLawKind === kind && multiDraft.lawOptimizer?.initial_parameters.length === length
      ? multiDraft.lawOptimizer
      : {
          initial_parameters: Array.from({ length }, () => Number.NaN),
          lower_bounds: Array.from({ length }, () => Number.NaN),
          upper_bounds: Array.from({ length }, () => Number.NaN),
          ftol: 1e-12,
          xtol: 1e-12,
          gtol: 1e-12,
          max_nfev: 5000,
          seed: null as null,
        };
    process.updateDraft({
      shiftLawKind: kind,
      initialParameters: values,
      lowerBounds: lower,
      upperBounds: upper,
      manualTable: [],
      lawOptimizer: currentOptimizer,
      reason: "",
    });
  }

  function setMultiVector(field: "initialParameters" | "lowerBounds" | "upperBounds", index: number, value: string): void {
    if (!multiDraft) return;
    const values = [...multiDraft[field]];
    values[index] = value;
    const optimizerField = field === "initialParameters" ? "initial_parameters" : field === "lowerBounds" ? "lower_bounds" : "upper_bounds";
    const optimizer = multiDraft.lawOptimizer
      ? { ...multiDraft.lawOptimizer, [optimizerField]: values.map((item) => item.trim() ? Number(item) : Number.NaN) }
      : null;
    process.updateDraft({ [field]: values, ...(optimizer ? { lawOptimizer: optimizer } : {}), reason: "" });
  }

  function setMultiVectorText(field: "initialParameters" | "lowerBounds" | "upperBounds", value: string): void {
    const values = value.split(",").map((item) => item.trim());
    const optimizerField = field === "initialParameters" ? "initial_parameters" : field === "lowerBounds" ? "lower_bounds" : "upper_bounds";
    const optimizer = multiDraft?.lawOptimizer
      ? { ...multiDraft.lawOptimizer, [optimizerField]: values.map((item) => item ? Number(item) : Number.NaN) }
      : null;
    process.updateDraft({ [field]: values, ...(optimizer ? { lawOptimizer: optimizer } : {}), reason: "" });
  }

  function setLawOptimizerVector(field: "initial_parameters" | "lower_bounds" | "upper_bounds", index: number, value: string): void {
    if (!multiDraft?.lawOptimizer) return;
    const values = [...multiDraft.lawOptimizer[field]];
    values[index] = value.trim() ? Number(value) : Number.NaN;
    process.updateDraft({ lawOptimizer: { ...multiDraft.lawOptimizer, [field]: values }, reason: "" });
  }

  const rail = isMulti ? <MultiSweepRail
    source={process.multiSource!}
    visibleSweepOrdinals={process.visibleSweepOrdinals}
    onToggle={process.toggleSweepVisibility}
  /> : undefined;

  const ribbon = <div className="dma-tts-command-ribbon">
    <div className="dma-tts-command-context">
      <strong>{commandTitle}</strong>
    </div>
    <div className="dma-tts-command-actions">
      {process.canPrepare && !process.recommendation ? <button type="button" className="button primary" disabled={process.status === "preparing"} onClick={() => void process.prepareRecommendation()}>{process.status === "preparing" ? "Preparing…" : "Prepare recommendation"}</button> : null}
      {process.recommendation && !process.readBack ? <button type="button" className="button primary" disabled={!process.canSave || process.status === "saving" || process.status === "save_outcome_unknown"} onClick={() => void process.save()}>{process.status === "saving" ? "Saving…" : "Save TTS result"}</button> : null}
      {process.fitInput && process.status === "saved" ? <button type="button" className="button primary" onClick={onContinue}>Continue to Prony Fit</button> : null}
    </div>
  </div>;

  return <ModelingWorkspaceLayout
    navigator={rail}
    navigatorLabel="DMA frequency sweeps"
    navigatorSize={isMulti ? { min: 184, default: 196, max: 210 } : undefined}
    ribbon={ribbon}
    plot={<div className={`dma-tts-process-surface${isMulti ? " dma-tts-process-surface-multi" : ""}${process.readBack ? " is-saved" : ""}`}>
      <section className="persistent-modeling-plot dma-tts-graph" aria-labelledby="dma-tts-graph-heading">
        <h2 id="dma-tts-graph-heading">{graphTitle}</h2>
        {plot && stage ? <EngineeringCurvePlot
          preview={plot}
          activeStage={stage}
          baseStage={stage}
          observedCurves={observedCurves}
          width={chart.width}
          height={chart.height}
        /> : <div className="dma-tts-plot-placeholder" role="status">Select an exact governed DMA source to show measured curves.</div>}
        <details className="dma-tts-text-alternative"><summary>Textual curve data</summary>
          {process.fixedSource ? <p>Fixed source: {process.fixedSource.rows.map((row) => `${compact(row.temperatureK)} K, G′ ${compact(row.storageModulusPa)} Pa, G″ ${compact(row.lossModulusPa)} Pa`).join("; ")}.</p> : null}
          {process.multiSource ? <ul>{process.multiSource.sweeps.map((sweep) => <li key={sweep.sourceSweepOrdinal}>Sweep {sweep.sourceSweepOrdinal}: {compact(sweep.representativeTemperatureK)} K, {sweep.points.length} points, raw {rawRange(sweep.sourceFrequencyMinHz, sweep.sourceFrequencyMaxHz, "Hz")}, G′ and G″ measured.</li>)}</ul> : null}
          {process.readBack ? <p>Backend reduced range and shifts: {process.readBack.isotherms.map((row) => `Sweep ${row.source_sweep_ordinal ?? "fixed"}: ${row.shifted_angular_frequency_min_rad_per_s === null ? "not shifted" : rawRange(row.shifted_angular_frequency_min_rad_per_s, row.shifted_angular_frequency_max_rad_per_s ?? row.shifted_angular_frequency_min_rad_per_s, "rad/s")}, log10(aT) ${row.applied_log10_a_t ?? "—"}, residual ${row.shift_residual_log10_a_t ?? "—"}`).join("; ")}.</p> : null}
        </details>
      </section>
      <section className="dma-tts-work-area" aria-label="DMA shift setup">
        {statusText(process.status) ? <div className="dma-tts-status" role="status" aria-live="polite">{statusText(process.status)}</div> : null}
        {process.error ? <WorkbenchMessage kind="error" title={process.status === "save_outcome_unknown" ? "Save outcome unknown" : "DMA response not ready"} action={{ label: process.createdOutput ? "Retry exact read" : "Retry", onClick: process.retry }}>{process.error}</WorkbenchMessage> : null}
        {!process.readBack && !process.recommendation && isMulti ? <div className="dma-tts-reference-setup"><label>Reference curve<select aria-label="Reference curve" value={process.selectedReferenceSweepOrdinal ?? ""} onChange={(event) => process.setReferenceSweep(Number(event.target.value))}>{process.multiSource?.sweeps.map((sweep) => <option value={sweep.sourceSweepOrdinal} key={sweep.sourceSweepOrdinal}>{compact(sweep.representativeTemperatureK)} K · Sweep {sweep.sourceSweepOrdinal}</option>)}</select></label></div> : null}
        {!process.readBack && process.recommendation && process.draft ? <>
          <header className="dma-tts-summary">
            <div><span>{isMulti ? "Sweeps included" : "Temperatures used"}</span><strong>{includedCount} of {isMulti ? process.multiSource?.sweeps.length ?? 0 : process.fixedSource?.rows.length ?? 0}</strong></div>
            <div><span>{isMulti ? "Reference curve" : "Test frequency"}</span><strong>{isMulti ? `${compact(referenceCurve?.representativeTemperatureK ?? 0)} K · #${multiDraft?.referenceSweepOrdinal}` : `${compact(process.fixedSource?.frequencyHz ?? 0)} Hz`}</strong></div>
            <div><span>Shift method</span><strong>{isMulti ? (SHIFT_LAW_LABELS[multiDraft?.shiftLawKind ?? ""] ?? "—") : "WLF"}</strong></div>
            <div><span>Reference temperature</span><strong>{compact(Number(process.draft.referenceTemperatureK))} K</strong></div>
          </header>
          <details className="dma-tts-settings-disclosure">
            <summary>TTS settings</summary>
            <div className="dma-tts-settings">
            {fixedDraft ? <fieldset className="dma-tts-wlf-fields"><legend>WLF shift settings</legend>
              <label>Reference temperature <span><input name="dma-tts-reference-temperature" autoComplete="off" type="number" inputMode="decimal" value={fixedDraft.referenceTemperatureK} onChange={(event) => process.updateDraft({ referenceTemperatureK: event.target.value, reason: "" })} /><b>K</b></span></label>
              <label>C1 <span><input name="dma-tts-c1" autoComplete="off" type="number" inputMode="decimal" value={fixedDraft.c1} onChange={(event) => process.updateDraft({ c1: event.target.value, reason: "" })} /><b>1</b></span></label>
              <label>C2 <span><input name="dma-tts-c2" autoComplete="off" type="number" inputMode="decimal" value={fixedDraft.c2K} onChange={(event) => process.updateDraft({ c2K: event.target.value, reason: "" })} /><b>K</b></span></label>
            </fieldset> : null}
            {multiDraft ? <div className="dma-tts-multi-settings">
              <section className="dma-tts-sweep-settings" aria-labelledby="dma-tts-sweep-settings-heading">
                <div className="dma-tts-sweep-settings-heading"><h3 id="dma-tts-sweep-settings-heading">Sweep roles</h3><label>Reference curve<select aria-label="Reference curve" value={multiDraft.referenceSweepOrdinal ?? ""} onChange={(event) => process.setReferenceSweep(Number(event.target.value))}>{process.multiSource?.sweeps.map((sweep) => <option value={sweep.sourceSweepOrdinal} key={sweep.sourceSweepOrdinal}>{compact(sweep.representativeTemperatureK)} K · Sweep {sweep.sourceSweepOrdinal}</option>)}</select></label></div>
                <div className="dma-tts-temperature-table-scroll"><table><thead><tr><th>Temperature curve</th><th>Role</th></tr></thead><tbody>{multiDraft.sweepDispositions.map((item) => <tr key={item.source_sweep_ordinal}><td>{compact(item.representative_temperature_k)} K · Sweep {item.source_sweep_ordinal}</td><td><div className={`dma-tts-sweep-role-cell${item.partition === "EXCLUDED" ? " has-reason" : ""}`}><select aria-label={`Analysis role for sweep ${item.source_sweep_ordinal}`} value={item.partition} disabled={item.source_sweep_ordinal === multiDraft.referenceSweepOrdinal} onChange={(event) => process.setSweepDisposition(item.source_sweep_ordinal, event.target.value as DmaTtsPartition)}>{(Object.keys(PARTITION_OPTION_LABELS) as DmaTtsPartition[]).map((value) => <option value={value} key={value}>{PARTITION_OPTION_LABELS[value]}</option>)}</select>{item.partition === "EXCLUDED" ? <label><span>Reason</span><input aria-label={`Reason for ignoring sweep ${item.source_sweep_ordinal}`} value={item.exclusion_reason ?? ""} onChange={(event) => process.setSweepExclusionReason(item.source_sweep_ordinal, event.target.value)} /></label> : null}</div></td></tr>)}</tbody></table></div>
              </section>
              <fieldset className="dma-tts-wlf-fields"><legend>Shift method</legend>
                <label>Method<select name="dma-tts-shift-law" aria-label="Shift method" value={multiDraft.shiftLawKind} onChange={(event) => setMultiLawKind(event.target.value as typeof multiDraft.shiftLawKind)}><option value="wlf_fit">WLF fit</option><option value="arrhenius_fit">Arrhenius fit</option><option value="manual_tabulated">Manual</option></select></label>
                <label>Reference temperature <span><input name="dma-tts-multi-reference-temperature" type="number" value={multiDraft.referenceTemperatureK} onChange={(event) => process.updateDraft({ referenceTemperatureK: event.target.value, reason: "" })} /><b>K</b></span></label>
                {multiDraft.shiftLawKind === "wlf_fit" ? <>
                  <label>Initial C1 <span><input name="dma-tts-multi-c1" type="number" value={multiDraft.initialParameters[0] ?? ""} onChange={(event) => setMultiVector("initialParameters", 0, event.target.value)} /><b>1</b></span></label>
                  <label>Initial C2 <span><input name="dma-tts-multi-c2" type="number" value={multiDraft.initialParameters[1] ?? ""} onChange={(event) => setMultiVector("initialParameters", 1, event.target.value)} /><b>K</b></span></label>
                  <label>Lower C1 / C2 <span><input name="dma-tts-multi-lower" type="text" aria-label="WLF lower bounds" value={multiDraft.lowerBounds.join(", ")} onChange={(event) => setMultiVectorText("lowerBounds", event.target.value)} /><b>fit</b></span></label>
                  <label>Upper C1 / C2 <span><input name="dma-tts-multi-upper" type="text" aria-label="WLF upper bounds" value={multiDraft.upperBounds.join(", ")} onChange={(event) => setMultiVectorText("upperBounds", event.target.value)} /><b>fit</b></span></label>
                </> : null}
                {multiDraft.shiftLawKind === "arrhenius_fit" ? <>
                  <label>Initial activation energy <span><input name="dma-tts-arrhenius-initial" type="number" value={multiDraft.initialParameters[0] ?? ""} onChange={(event) => setMultiVector("initialParameters", 0, event.target.value)} /><b>J/mol</b></span></label>
                  <label>Lower activation energy <span><input name="dma-tts-arrhenius-lower" type="number" value={multiDraft.lowerBounds[0] ?? ""} onChange={(event) => setMultiVector("lowerBounds", 0, event.target.value)} /><b>J/mol</b></span></label>
                  <label>Upper activation energy <span><input name="dma-tts-arrhenius-upper" type="number" value={multiDraft.upperBounds[0] ?? ""} onChange={(event) => setMultiVector("upperBounds", 0, event.target.value)} /><b>J/mol</b></span></label>
                </> : null}
                {multiDraft.shiftLawKind === "manual_tabulated" ? <div className="dma-tts-manual-table-scroll"><table><caption>Manual per-temperature log10(aT)</caption><thead><tr><th>Temperature</th><th>log10(aT)</th></tr></thead><tbody>{multiDraft.manualTable.map((row) => <tr key={row.temperatureK}><td>{row.temperatureK} K</td><td><input name={`dma-tts-manual-${row.temperatureK}`} aria-label={`Manual log10(aT) at ${row.temperatureK} K`} type="number" value={row.log10At} onChange={(event) => process.updateDraft({ manualTable: multiDraft.manualTable.map((item) => item.temperatureK === row.temperatureK ? { ...item, log10At: event.target.value } : item), reason: "" })} /></td></tr>)}</tbody></table></div> : null}
              </fieldset>
              <fieldset className="dma-tts-wlf-fields"><legend>Scoring controls</legend>
                <label>Minimum overlap <span><input name="dma-tts-overlap" type="number" step="0.01" value={multiDraft.scoring.minimum_overlap_decades} onChange={(event) => process.updateDraft({ scoring: { ...multiDraft.scoring, minimum_overlap_decades: Number(event.target.value) }, reason: "" })} /><b>dec</b></span></label>
                <label>Scoring point count <span><input name="dma-tts-scoring-point-count" type="number" min="2" max="10001" value={multiDraft.scoring.scoring_point_count} onChange={(event) => process.updateDraft({ scoring: { ...multiDraft.scoring, scoring_point_count: Number(event.target.value) }, reason: "" })} /><b>points</b></span></label>
                <label>Storage weight <span><input name="dma-tts-storage-weight" type="number" step="0.01" min="0" value={multiDraft.scoring.storage_weight} onChange={(event) => process.updateDraft({ scoring: { ...multiDraft.scoring, storage_weight: Number(event.target.value) }, reason: "" })} /><b>0–1</b></span></label>
                <label>Loss weight <span><input name="dma-tts-loss-weight" type="number" step="0.01" min="0" value={multiDraft.scoring.loss_weight} onChange={(event) => process.updateDraft({ scoring: { ...multiDraft.scoring, loss_weight: Number(event.target.value) }, reason: "" })} /><b>0–1</b></span></label>
              </fieldset>
              <fieldset className="dma-tts-wlf-fields"><legend>Adjacent optimizer</legend>
                <label>Relative lower bound <span><input name="dma-tts-adjacent-lower" type="number" value={multiDraft.adjacentOptimizer.relative_shift_lower_bound_log10} onChange={(event) => process.updateDraft({ adjacentOptimizer: { ...multiDraft.adjacentOptimizer, relative_shift_lower_bound_log10: Number(event.target.value) }, reason: "" })} /><b>log10</b></span></label>
                <label>Relative upper bound <span><input name="dma-tts-adjacent-upper" type="number" value={multiDraft.adjacentOptimizer.relative_shift_upper_bound_log10} onChange={(event) => process.updateDraft({ adjacentOptimizer: { ...multiDraft.adjacentOptimizer, relative_shift_upper_bound_log10: Number(event.target.value) }, reason: "" })} /><b>log10</b></span></label>
                <label>xatol <span><input name="dma-tts-adjacent-xatol" type="number" value={multiDraft.adjacentOptimizer.xatol} readOnly aria-readonly="true" /><b>fixed</b></span></label>
                <label>maxiter <span><input name="dma-tts-adjacent-maxiter" type="number" value={multiDraft.adjacentOptimizer.maxiter} readOnly aria-readonly="true" /><b>fixed</b></span></label>
                <label>Seed <input name="dma-tts-adjacent-seed" type="text" value="null" disabled /></label>
              </fieldset>
              {multiDraft.shiftLawKind !== "manual_tabulated" ? <fieldset className="dma-tts-wlf-fields"><legend>Fitted-law optimizer</legend>
                {multiDraft.initialParameters.map((value, index) => <div className="dma-tts-vector-row" key={`optimizer-${index}`}><label>Start {index + 1}<span><input name={`dma-tts-law-start-${index}`} type="number" value={numberField(multiDraft.lawOptimizer?.initial_parameters[index] ?? Number.NaN)} onChange={(event) => setLawOptimizerVector("initial_parameters", index, event.target.value)} /><b>fit</b></span></label><label>Lower {index + 1}<span><input name={`dma-tts-law-lower-${index}`} type="number" value={numberField(multiDraft.lawOptimizer?.lower_bounds[index] ?? Number.NaN)} onChange={(event) => setLawOptimizerVector("lower_bounds", index, event.target.value)} /><b>fit</b></span></label><label>Upper {index + 1}<span><input name={`dma-tts-law-upper-${index}`} type="number" value={numberField(multiDraft.lawOptimizer?.upper_bounds[index] ?? Number.NaN)} onChange={(event) => setLawOptimizerVector("upper_bounds", index, event.target.value)} /><b>fit</b></span></label></div>)}
                <label>ftol <span><input name="dma-tts-law-ftol" type="number" value={multiDraft.lawOptimizer?.ftol ?? 1e-12} readOnly aria-readonly="true" /><b>fixed</b></span></label>
                <label>xtol <span><input name="dma-tts-law-xtol" type="number" value={multiDraft.lawOptimizer?.xtol ?? 1e-12} readOnly aria-readonly="true" /><b>fixed</b></span></label>
                <label>gtol <span><input name="dma-tts-law-gtol" type="number" value={multiDraft.lawOptimizer?.gtol ?? 1e-12} readOnly aria-readonly="true" /><b>fixed</b></span></label>
                <label>max_nfev <span><input name="dma-tts-law-max-nfev" type="number" value={multiDraft.lawOptimizer?.max_nfev ?? 5000} readOnly aria-readonly="true" /><b>fixed</b></span></label>
                <label>Seed <input name="dma-tts-law-seed" type="text" value="null" disabled /></label>
              </fieldset> : null}
              <label className="dma-tts-change-reason">Engineer reason <input name="dma-tts-change-reason" autoComplete="off" type="text" value={multiDraft.reason} onChange={(event) => process.updateDraft({ reason: event.target.value })} /></label>
            </div> : null}
            {fixedDraft && settingsEdited ? <label className="dma-tts-change-reason">Reason for changes <input name="dma-tts-change-reason" autoComplete="off" type="text" value={fixedDraft.reason} onChange={(event) => process.updateDraft({ reason: event.target.value })} /></label> : null}
            {fixedDraft ? <div className="dma-tts-temperature-table-scroll"><table><caption>Temperature disposition</caption><thead><tr><th>Temperature</th><th>Role</th><th>Reason when ignored</th></tr></thead><tbody>{process.fixedSource?.rows.map((row) => {
              const disposition = fixedDraft.dispositions[row.ordinal];
              return <tr key={row.ordinal}><td>{compact(row.temperatureK)} K</td><td><select name={`dma-tts-temperature-${row.ordinal}-use`} aria-label={`Use ${compact(row.temperatureK)} K`} value={disposition.partition} onChange={(event) => process.setDisposition(row.ordinal, event.target.value as DmaTtsPartition)}>{(Object.keys(PARTITION_OPTION_LABELS) as DmaTtsPartition[]).map((value) => <option value={value} key={value}>{PARTITION_OPTION_LABELS[value]}</option>)}</select></td><td>{disposition.partition === "EXCLUDED" ? <input name={`dma-tts-temperature-${row.ordinal}-exclusion-reason`} autoComplete="off" aria-label={`Reason for not using ${compact(row.temperatureK)} K`} value={disposition.exclusionReason} onChange={(event) => process.setExclusionReason(row.ordinal, event.target.value)} /> : "—"}</td></tr>;
            })}</tbody></table></div> : null}
            </div>
          </details>
        </> : null}
        {process.readBack ? <div className="dma-tts-result-evidence">
          <div className="dma-tts-saved-row"><h2>TTS result saved</h2><p>{process.status === "saved" ? "Ready for Prony Fit." : "The saved result is available. Fit linking needs a retry."}</p></div>
          <section className="dma-tts-result-summary" aria-labelledby="dma-tts-result-summary-heading"><h3 id="dma-tts-result-summary-heading">Result summary</h3><dl><div><dt>Shift method</dt><dd>{SHIFT_LAW_LABELS[savedShiftLaw?.kind ?? ""] ?? "—"}</dd></div><div><dt>Reference temperature</dt><dd>{savedShiftLaw ? `${compact(savedShiftLaw.reference_temperature_k)} K` : "—"}</dd></div><div><dt>Fit frequency range</dt><dd>{savedFrequencyRange}</dd></div><div><dt>Fit temperature range</dt><dd>{savedTemperatureRange}</dd></div></dl></section>
          <details className="dma-tts-result-details"><summary>Calculation details</summary><div className="dma-tts-result-details-body">
            <section aria-labelledby="dma-tts-isotherm-results-heading"><h3 id="dma-tts-isotherm-results-heading">Sweep results</h3><div className="dma-tts-result-table-scroll"><table><thead><tr><th>Sweep</th><th>Temperature</th><th>Role</th><th>Shift reference</th><th>Validation state</th><th>Applied log10(aT)</th><th>Shift factor</th><th>Shift residual</th><th>G′ RMSE</th><th>G″ RMSE</th><th>Overlap</th></tr></thead><tbody>{process.readBack.isotherms.map((row) => <tr key={`${row.source_sweep_ordinal ?? "fixed"}-${row.representative_temperature_k}`}><td>{row.source_sweep_ordinal ?? "fixed"}</td><td>{backendValue(row.representative_temperature_k)} K</td><td>{PARTITION_LABELS[row.partition]}</td><td>{row.is_reference ? "Yes" : "No"}</td><td>{backendValue(row.holdout_evaluation_status)}</td><td>{backendValue(row.applied_log10_a_t)}</td><td>{backendValue(row.shift_factor)}</td><td>{backendValue(row.shift_residual_log10_a_t)}</td><td>{backendValue(row.storage_rmse)}</td><td>{backendValue(row.loss_rmse)}</td><td>{backendValue(row.overlap_log10_reduced_angular_frequency_min)}–{backendValue(row.overlap_log10_reduced_angular_frequency_max)}</td></tr>)}</tbody></table></div></section>
            <section className="dma-tts-output-summary" aria-labelledby="dma-tts-output-summary-heading"><h3 id="dma-tts-output-summary-heading">Assessment</h3><dl><div><dt>Adequacy</dt><dd>{ASSESSMENT_LABELS[savedAssessment?.adequacy ?? ""] ?? "—"}</dd></div><div><dt>Uncertainty</dt><dd>{ASSESSMENT_LABELS[savedAssessment?.uncertainty ?? ""] ?? "—"}</dd></div><div><dt>Identifiability</dt><dd>{ASSESSMENT_LABELS[savedAssessment?.identifiability ?? ""] ?? "—"}</dd></div><div><dt>Production use</dt><dd>{ASSESSMENT_LABELS[savedAssessment?.production_readiness ?? ""] ?? "—"}</dd></div>{savedWarnings.length ? <div className="dma-tts-output-warnings"><dt>Missing evidence</dt><dd><span className="dma-tts-warning-list">{savedWarnings.map((warning) => <span key={warning}>{WARNING_LABELS[warning] ?? warning}</span>)}</span></dd></div> : null}</dl></section>
          </div></details>
        </div> : null}
        {process.status === "loading" && !process.error ? <p className="dma-tts-loading" role="status">Loading exact governed DMA source…</p> : null}
      </section>
    </div>}
    ribbonOpen={ribbonOpen}
    onRibbonOpenChange={onRibbonOpenChange}
  />;
}
