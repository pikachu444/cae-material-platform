import { useMemo, useState } from "react";

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
  sourceLabel: string;
  initialOutput?: { id: string; revisionId: string; contentSha256: string };
  chart: { width: number; height: number };
  ribbonOpen: boolean;
  onRibbonOpenChange: (open: boolean) => void;
  onSaved: (created: CreateDmaTtsResponse) => Promise<void> | void;
  onContinue: () => void;
}

const PARTITION_LABELS: Record<DmaTtsPartition, string> = {
  CALIBRATION: "CALIBRATION",
  HOLDOUT: "HOLDOUT",
  EXCLUDED: "EXCLUDED",
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
    case "saved": return "Exact GET and common Process → Fit link verified.";
    case "read_error": return "The result pin exists, but exact read-back or Fit linking needs a retry.";
    case "save_outcome_unknown": return "Save outcome unknown; the create request will not be retried automatically.";
    default: return "";
  }
}

function backendRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
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

function backendList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function backendShiftLawSummary(value: unknown): string {
  const law = backendRecord(value);
  if (!law) return backendValue(value);

  const kind = typeof law.kind === "string"
    ? ({
      wlf: "WLF",
      wlf_fit: "WLF fit",
      arrhenius: "Arrhenius",
      arrhenius_fit: "Arrhenius fit",
      manual_tabulated: "Manual/tabulated",
    } as Record<string, string>)[law.kind] ?? law.kind
    : "Backend shift law";
  const reference = typeof law.reference_temperature_k === "number" && Number.isFinite(law.reference_temperature_k)
    ? `reference ${compact(law.reference_temperature_k)} K`
    : null;
  return [kind, reference].filter(Boolean).join(" · ");
}

function backendScalar(value: unknown): string | null {
  if (typeof value === "number") return Number.isFinite(value) ? compact(value) : null;
  if (typeof value === "string" && value.trim()) return value;
  return null;
}

function backendIntervalSummary(value: unknown, unit: string): string | null {
  const interval = backendRecord(value);
  if (!interval) return null;
  const minimum = backendScalar(interval.minimum);
  const maximum = backendScalar(interval.maximum);
  return minimum !== null && maximum !== null ? `${minimum}–${maximum} ${unit}` : null;
}

function backendApplicationRangeSummary(value: unknown): string {
  if (value === null || value === undefined) return "—";
  const range = backendRecord(value);
  if (!range) return backendScalar(value) ?? "Backend application range details unavailable";

  const facts: string[] = [];
  const frequencyIntervals = backendList(range.reduced_angular_frequency_intervals_rad_per_s)
    .map((interval) => backendIntervalSummary(interval, "rad/s"))
    .filter((interval): interval is string => interval !== null);
  if (frequencyIntervals.length) facts.push(`Reduced frequency ${frequencyIntervals.join("; ")}`);

  const temperatureInterval = backendIntervalSummary(range.calibration_temperature_interval_k, "K");
  if (temperatureInterval) facts.push(`Calibration temperature ${temperatureInterval}`);

  if (typeof range.holdout_included === "boolean") {
    facts.push(`Holdout ${range.holdout_included ? "included" : "not included"}`);
  }
  return facts.length ? facts.join(" · ") : "Backend application range details unavailable";
}

function MultiSweepRail({
  source,
  draft,
  recommendation,
  readBack,
  selectedReferenceSweepOrdinal,
  visibleSweepOrdinals,
  locked,
  onReference,
  onToggle,
  onPartition,
}: {
  source: NonNullable<ReturnType<typeof useDmaTtsProcess>["multiSource"]>;
  draft: ReturnType<typeof useDmaTtsProcess>["draft"];
  recommendation: ReturnType<typeof useDmaTtsProcess>["recommendation"];
  readBack: ReturnType<typeof useDmaTtsProcess>["readBack"];
  selectedReferenceSweepOrdinal: number | null;
  visibleSweepOrdinals: number[];
  locked: boolean;
  onReference: (ordinal: number) => void;
  onToggle: (ordinal: number) => void;
  onPartition: (ordinal: number, partition: DmaTtsPartition) => void;
}) {
  return <nav className="dma-tts-sweep-rail" aria-label="DMA frequency sweeps">
    <div className="dma-tts-rail-heading"><span>Measured sweeps</span><strong>{source.sweeps.length}</strong></div>
    <p className="dma-tts-rail-note">{locked ? "Saved partitions and reference are read-only. Visibility changes affect display only." : "Choose one calibration reference. Visibility changes affect display only."}</p>
    <div className="dma-tts-sweep-list" tabIndex={0} aria-label="Measured DMA frequency sweeps">
      {source.sweeps.map((sweep) => {
        const disposition = draft?.sweepDispositions.find((item) => item.source_sweep_ordinal === sweep.sourceSweepOrdinal);
        const saved = readBack?.isotherms.find((item) => item.source_sweep_ordinal === sweep.sourceSweepOrdinal);
        const partition = saved?.partition ?? disposition?.partition ?? "CALIBRATION";
        const isReference = saved?.is_reference ?? ((recommendation?.input_mode === "multi_frequency_isotherms"
          ? recommendation.reference_sweep_ordinal
          : selectedReferenceSweepOrdinal) === sweep.sourceSweepOrdinal);
        const visible = visibleSweepOrdinals.includes(sweep.sourceSweepOrdinal);
        return <article className={`dma-tts-sweep-entry${isReference ? " is-reference" : ""}`} key={sweep.sourceSweepOrdinal}>
          <div className="dma-tts-sweep-entry-head">
            <button type="button" className="dma-tts-sweep-visibility" aria-pressed={visible} aria-label={`${visible ? "Hide" : "Show"} sweep ${sweep.sourceSweepOrdinal}`} onClick={() => onToggle(sweep.sourceSweepOrdinal)}>{visible ? "◉" : "○"}</button>
            <strong>Sweep {sweep.sourceSweepOrdinal}</strong>
            <label><input type="radio" name="dma-tts-reference-sweep" checked={isReference} disabled={locked} onChange={() => onReference(sweep.sourceSweepOrdinal)} /><span>Reference</span></label>
          </div>
          <div className="dma-tts-sweep-meta"><span>{compact(sweep.representativeTemperatureK)} K</span><span>{sweep.points.length} points</span></div>
          <div className="dma-tts-sweep-meta"><span>{rawRange(sweep.sourceFrequencyMinHz, sweep.sourceFrequencyMaxHz, "Hz")}</span></div>
          <label className="dma-tts-rail-partition">Partition<select aria-label={`Partition sweep ${sweep.sourceSweepOrdinal}`} value={partition} disabled={locked} onChange={(event) => onPartition(sweep.sourceSweepOrdinal, event.target.value as DmaTtsPartition)}>{(Object.keys(PARTITION_LABELS) as DmaTtsPartition[]).map((value) => <option value={value} key={value}>{PARTITION_LABELS[value]}</option>)}</select></label>
        </article>;
      })}
    </div>
  </nav>;
}

export function DmaTtsProcessWorkspace({
  config,
  testData,
  sourceDocument,
  sourceLabel,
  initialOutput,
  chart,
  ribbonOpen,
  onRibbonOpenChange,
  onSaved,
  onContinue,
}: DmaTtsProcessWorkspaceProps) {
  const process = useDmaTtsProcess({ config, testData, sourceDocument, sourceLabel, initialOutput, onSaved });
  const [settingsOpen, setSettingsOpen] = useState(false);
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
    ? "Saved DMA response · backend reduced frequency"
    : isMulti ? "DMA frequency isotherms" : "DMA temperature sweep";
  const includedCount = fixedDraft?.dispositions.filter((item) => item.partition !== "EXCLUDED").length
    ?? multiDraft?.sweepDispositions.filter((item) => item.partition !== "EXCLUDED").length ?? 0;
  const savedOptions = process.readBack?.options ?? {};
  const savedAssessment = backendRecord(savedOptions.assessment);
  const savedShiftLaw = backendRecord(savedOptions.shift_law);
  const savedWarnings = backendList(savedOptions.warnings);

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
    draft={process.draft}
    recommendation={process.recommendation}
    readBack={process.readBack}
    selectedReferenceSweepOrdinal={process.selectedReferenceSweepOrdinal}
    visibleSweepOrdinals={process.visibleSweepOrdinals}
    locked={Boolean(process.readBack)}
    onReference={process.setReferenceSweep}
    onToggle={process.toggleSweepVisibility}
    onPartition={process.setSweepDisposition}
  /> : undefined;

  const ribbon = <div className="dma-tts-command-ribbon">
    <span>{process.status === "saved" ? "Exact saved TTS result verified" : process.inputMode === "fixed_frequency_temperature_sweep" ? "Fixed-frequency reduced-frequency projection" : process.status === "preparing" ? "Preparing recommendation…" : multiDraft ? `Multi-frequency ${multiDraft.shiftLawKind}` : "Multi-frequency recommendation"}</span>
    <div>
      {process.canPrepare && !process.recommendation ? <button type="button" className="button primary" disabled={process.status === "preparing"} onClick={() => void process.prepareRecommendation()}>{process.status === "preparing" ? "Preparing…" : "Prepare recommendation"}</button> : null}
      {process.recommendation && !process.readBack ? <button type="button" className="button secondary" onClick={() => setSettingsOpen((value) => !value)} disabled={process.status === "saving"}>{settingsOpen ? "Hide settings" : "Advanced settings"}</button> : null}
      {process.fitInput && process.status === "saved" ? <button type="button" className="button primary" onClick={onContinue}>Continue to Fit</button> : null}
    </div>
  </div>;

  return <ModelingWorkspaceLayout
    navigator={rail}
    navigatorLabel="DMA frequency sweeps"
    navigatorSize={isMulti ? { min: 184, default: 192, max: 210 } : undefined}
    ribbon={ribbon}
    plot={<div className={`dma-tts-process-surface${isMulti ? " dma-tts-process-surface-multi" : ""}`}>
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
          {process.fixedSource ? <p>Fixed source: {process.fixedSource.rows.map((row) => `${compact(row.temperatureK)} K · G′ ${compact(row.storageModulusPa)} Pa · G″ ${compact(row.lossModulusPa)} Pa`).join("; ")}.</p> : null}
          {process.multiSource ? <ul>{process.multiSource.sweeps.map((sweep) => <li key={sweep.sourceSweepOrdinal}>Sweep {sweep.sourceSweepOrdinal}: {compact(sweep.representativeTemperatureK)} K, {sweep.points.length} points, raw {rawRange(sweep.sourceFrequencyMinHz, sweep.sourceFrequencyMaxHz, "Hz")}, G′ and G″ measured.</li>)}</ul> : null}
          {process.readBack ? <p>Backend reduced range and shifts: {process.readBack.isotherms.map((row) => `${row.source_sweep_ordinal ?? "fixed"} ${row.shifted_angular_frequency_min_rad_per_s === null ? "not shifted" : rawRange(row.shifted_angular_frequency_min_rad_per_s, row.shifted_angular_frequency_max_rad_per_s ?? row.shifted_angular_frequency_min_rad_per_s, "rad/s")} · log10(aT) ${row.applied_log10_a_t ?? "—"} · residual ${row.shift_residual_log10_a_t ?? "—"}`).join("; ")}.</p> : null}
        </details>
      </section>
      <section className="dma-tts-work-area" aria-label="DMA shift setup">
        <div className="dma-tts-status" role="status" aria-live="polite">{statusText(process.status)}</div>
        {process.error ? <WorkbenchMessage kind="error" title={process.status === "save_outcome_unknown" ? "Save outcome unknown" : "DMA response not ready"} action={{ label: process.createdOutput ? "Retry exact read" : "Retry", onClick: process.retry }}>{process.error}</WorkbenchMessage> : null}
        {!process.readBack && process.recommendation && process.draft ? <>
          <header className="dma-tts-summary">
            <div><span>{isMulti ? "Sweeps included" : "Temperatures used"}</span><strong>{includedCount} of {isMulti ? process.multiSource?.sweeps.length ?? 0 : process.fixedSource?.rows.length ?? 0}</strong></div>
            <div><span>{isMulti ? "Reference sweep" : "Test frequency"}</span><strong>{isMulti ? `#${multiDraft?.referenceSweepOrdinal}` : `${compact(process.fixedSource?.frequencyHz ?? 0)} Hz`}</strong></div>
            <div><span>Shift method</span><strong>{isMulti ? (multiDraft?.shiftLawKind ?? "—") : "WLF"}</strong></div>
            <div><span>Reference temperature</span><strong>{compact(Number(process.draft.referenceTemperatureK))} K</strong></div>
          </header>
          {settingsOpen ? <div className="dma-tts-settings">
            {fixedDraft ? <fieldset className="dma-tts-wlf-fields"><legend>WLF shift settings</legend>
              <label>Reference temperature <span><input name="dma-tts-reference-temperature" autoComplete="off" type="number" inputMode="decimal" value={fixedDraft.referenceTemperatureK} onChange={(event) => process.updateDraft({ referenceTemperatureK: event.target.value, reason: "" })} /><b>K</b></span></label>
              <label>C1 <span><input name="dma-tts-c1" autoComplete="off" type="number" inputMode="decimal" value={fixedDraft.c1} onChange={(event) => process.updateDraft({ c1: event.target.value, reason: "" })} /><b>1</b></span></label>
              <label>C2 <span><input name="dma-tts-c2" autoComplete="off" type="number" inputMode="decimal" value={fixedDraft.c2K} onChange={(event) => process.updateDraft({ c2K: event.target.value, reason: "" })} /><b>K</b></span></label>
            </fieldset> : null}
            {multiDraft ? <div className="dma-tts-multi-settings">
              <fieldset className="dma-tts-wlf-fields"><legend>Multi-frequency shift law</legend>
                <label>Law<select name="dma-tts-shift-law" aria-label="Multi-frequency shift law" value={multiDraft.shiftLawKind} onChange={(event) => setMultiLawKind(event.target.value as typeof multiDraft.shiftLawKind)}><option value="wlf_fit">WLF fit</option><option value="arrhenius_fit">Arrhenius fit</option><option value="manual_tabulated">Manual/tabulated shift law</option></select></label>
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
            {fixedDraft ? <div className="dma-tts-temperature-table-scroll"><table><caption>Temperature disposition</caption><thead><tr><th>Temperature</th><th>Use</th><th>Reason when not used</th></tr></thead><tbody>{process.fixedSource?.rows.map((row) => {
              const disposition = fixedDraft.dispositions[row.ordinal];
              return <tr key={row.ordinal}><td>{compact(row.temperatureK)} K</td><td><select name={`dma-tts-temperature-${row.ordinal}-use`} aria-label={`Use ${compact(row.temperatureK)} K`} value={disposition.partition} onChange={(event) => process.setDisposition(row.ordinal, event.target.value as DmaTtsPartition)}>{(Object.keys(PARTITION_LABELS) as DmaTtsPartition[]).map((value) => <option value={value} key={value}>{PARTITION_LABELS[value]}</option>)}</select></td><td>{disposition.partition === "EXCLUDED" ? <input name={`dma-tts-temperature-${row.ordinal}-exclusion-reason`} autoComplete="off" aria-label={`Reason for not using ${compact(row.temperatureK)} K`} value={disposition.exclusionReason} onChange={(event) => process.setExclusionReason(row.ordinal, event.target.value)} /> : "—"}</td></tr>;
            })}</tbody></table></div> : null}
            {multiDraft ? <div className="dma-tts-temperature-table-scroll"><table><caption>Sweep disposition</caption><thead><tr><th>Sweep</th><th>Partition</th><th>Reason when excluded</th></tr></thead><tbody>{multiDraft.sweepDispositions.map((item) => <tr key={item.source_sweep_ordinal}><td>#{item.source_sweep_ordinal} · {compact(item.representative_temperature_k)} K</td><td><select name={`dma-tts-sweep-${item.source_sweep_ordinal}-partition`} aria-label={`Partition sweep ${item.source_sweep_ordinal}`} value={item.partition} onChange={(event) => process.setSweepDisposition(item.source_sweep_ordinal, event.target.value as DmaTtsPartition)}>{(Object.keys(PARTITION_LABELS) as DmaTtsPartition[]).map((value) => <option value={value} key={value}>{PARTITION_LABELS[value]}</option>)}</select></td><td>{item.partition === "EXCLUDED" ? <input name={`dma-tts-sweep-${item.source_sweep_ordinal}-reason`} aria-label={`Reason for excluding sweep ${item.source_sweep_ordinal}`} value={item.exclusion_reason ?? ""} onChange={(event) => process.setSweepExclusionReason(item.source_sweep_ordinal, event.target.value)} /> : "—"}</td></tr>)}</tbody></table></div> : null}
          </div> : null}
          <div className="dma-tts-confirmation"><button type="button" className="button primary" disabled={!process.canSave || process.status === "saving" || process.status === "save_outcome_unknown"} onClick={() => void process.save()}>{process.status === "saving" ? "Saving…" : "Save TTS result"}</button></div>
        </> : null}
        {process.readBack ? <div className="dma-tts-result-evidence">
          <div className="dma-tts-saved-row"><div><h2>Shifted DMA response saved</h2><p>{process.status === "saved" ? "Exact GET and common Processing Output link verified; Fit handoff is available." : "Exact GET verified; the common Processing Output link still needs a retry."}</p><p className="dma-tts-results-summary">Backend-provided shift factors, overlap ranges, G′/G″ RMSE, holdout evaluation, application range, assessment, and warnings are shown below.</p></div></div>
          <section aria-labelledby="dma-tts-isotherm-results-heading"><h3 id="dma-tts-isotherm-results-heading">Backend isotherm results</h3><div className="dma-tts-result-table-scroll"><table><thead><tr><th>Sweep</th><th>Temperature</th><th>Partition</th><th>Reference</th><th>Holdout state</th><th>Applied log10(aT)</th><th>Shift factor</th><th>Shift residual</th><th>G′ RMSE</th><th>G″ RMSE</th><th>Overlap</th></tr></thead><tbody>{process.readBack.isotherms.map((row) => <tr key={`${row.source_sweep_ordinal ?? "fixed"}-${row.representative_temperature_k}`}><td>{row.source_sweep_ordinal ?? "fixed"}</td><td>{backendValue(row.representative_temperature_k)} K</td><td>{row.partition}</td><td>{row.is_reference ? "Yes" : "No"}</td><td>{backendValue(row.holdout_evaluation_status)}</td><td>{backendValue(row.applied_log10_a_t)}</td><td>{backendValue(row.shift_factor)}</td><td>{backendValue(row.shift_residual_log10_a_t)}</td><td>{backendValue(row.storage_rmse)}</td><td>{backendValue(row.loss_rmse)}</td><td>{backendValue(row.overlap_log10_reduced_angular_frequency_min)}–{backendValue(row.overlap_log10_reduced_angular_frequency_max)}</td></tr>)}</tbody></table></div></section>
          <section className="dma-tts-output-summary" aria-labelledby="dma-tts-output-summary-heading"><h3 id="dma-tts-output-summary-heading">Backend output summary</h3><dl><div><dt>Application range</dt><dd>{backendApplicationRangeSummary(savedOptions.application_range)}</dd></div><div><dt>Shift law</dt><dd>{backendShiftLawSummary(savedShiftLaw ?? savedOptions.shift_law)}</dd></div><div><dt>Assessment</dt><dd>{savedAssessment ? <span className="dma-tts-assessment-list">{Object.entries(savedAssessment).map(([key, value]) => <span key={key}>{key}: {backendValue(value)}</span>)}</span> : backendValue(savedOptions.assessment)}</dd></div><div><dt>Production status</dt><dd>{backendValue(savedOptions.production_readiness ?? savedAssessment?.production_readiness)}</dd></div><div><dt>Warnings</dt><dd>{savedWarnings.length ? <span className="dma-tts-warning-list">{savedWarnings.map((warning, index) => <span key={`${index}-${String(warning)}`}>{backendValue(warning)}</span>)}</span> : "—"}</dd></div></dl></section>
        </div> : null}
        {process.status === "loading" && !process.error ? <p className="dma-tts-loading" role="status">Loading exact governed DMA source…</p> : null}
      </section>
    </div>}
    ribbonOpen={ribbonOpen}
    onRibbonOpenChange={onRibbonOpenChange}
  />;
}
