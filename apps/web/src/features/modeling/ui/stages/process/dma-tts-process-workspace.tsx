import { useMemo, useState } from "react";

import { ModelingWorkspaceLayout } from "../../../../../design/modeling-workspace-layout";
import { WorkbenchMessage } from "../../../../../design/semantic-ui";
import { EngineeringCurvePlot } from "../../../../../engineering-curve-plot";
import type { ApiConfig } from "../../../../../shared/api";
import type { CanonicalTestDataDocumentResponse } from "../../../../test-data/contracts";
import { useDmaTtsProcess } from "../../../controller/use-dma-tts-process";
import type { CreateDmaTtsResponse, DmaTtsPartition } from "../../../model/dma-tts-contracts";
import { dmaMasterCurvePreview, dmaTemperatureSweepPreview } from "../../../model/dma-tts-presentation";
import "./dma-tts-process-workspace.css";

export interface DmaTtsProcessWorkspaceProps {
  config: ApiConfig;
  testData: CanonicalTestDataDocumentResponse;
  sourceDocument: Record<string, unknown>;
  sourceLabel: string;
  initialOutput?: { id: string; revisionId: string };
  chart: { width: number; height: number };
  ribbonOpen: boolean;
  onRibbonOpenChange: (open: boolean) => void;
  onSaved: (created: CreateDmaTtsResponse) => Promise<void> | void;
  onContinue: () => void;
}

const PARTITION_LABELS: Record<DmaTtsPartition, string> = {
  CALIBRATION: "Use for shifted response",
  HOLDOUT: "Use for verification",
  EXCLUDED: "Do not use",
};

function compact(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumSignificantDigits: 5 }).format(value);
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
  const plot = useMemo(() => process.fitInput
    ? dmaMasterCurvePreview(process.fitInput)
    : process.source ? dmaTemperatureSweepPreview(process.source) : null,
  [process.fitInput, process.source]);
  const stage = plot?.stages[0];
  const includedCount = process.draft?.dispositions.filter((item) => item.partition !== "EXCLUDED").length ?? 0;
  const settingsEdited = Boolean(process.draft && process.recommendation && (
    Number(process.draft.referenceTemperatureK) !== process.recommendation.reference_temperature_k
    || Number(process.draft.c1) !== process.recommendation.c1
    || Number(process.draft.c2K) !== process.recommendation.c2_k
  ));
  const graphTitle = process.fitInput
    ? `Shifted DMA response · ${compact(Number(process.fitInput.reference_temperature_k))} K`
    : "DMA temperature sweep";

  const ribbon = <div className="dma-tts-command-ribbon">
    <span>{process.fitInput ? "Response saved" : process.status === "loading" ? "Preparing WLF shift…" : "Recommended WLF shift ready"}</span>
    <div>
      <button type="button" className="button secondary" onClick={() => setSettingsOpen((value) => !value)} disabled={!process.draft}>{settingsOpen ? "Hide settings" : "Change settings"}</button>
      {process.fitInput ? <button type="button" className="button primary" onClick={onContinue}>Continue to Fit</button> : null}
    </div>
  </div>;

  return <ModelingWorkspaceLayout
    ribbon={ribbon}
    plot={<div className="dma-tts-process-surface">
      <section className="persistent-modeling-plot dma-tts-graph" aria-labelledby="dma-tts-graph-heading">
        <h2 id="dma-tts-graph-heading">{graphTitle}</h2>
        {plot && stage ? <EngineeringCurvePlot
          preview={plot}
          activeStage={stage}
          baseStage={stage}
          width={chart.width}
          height={chart.height}
        /> : null}
      </section>
      <section className="dma-tts-work-area" aria-label="DMA shift setup">
        {process.error ? <WorkbenchMessage kind="error" title="DMA response not ready" action={{ label: "Retry", onClick: process.retry }}>{process.error}</WorkbenchMessage> : null}
        {!process.fitInput && process.recommendation && process.draft ? <>
          <header className="dma-tts-summary">
            <div><span>Temperatures used</span><strong>{includedCount} of {process.source?.rows.length ?? 0}</strong></div>
            <div><span>Test frequency</span><strong>{compact(process.source?.frequencyHz ?? 0)} Hz</strong></div>
            <div><span>Shift method</span><strong>WLF</strong></div>
            <div><span>Reference temperature</span><strong>{compact(Number(process.draft.referenceTemperatureK))} K</strong></div>
          </header>
          {settingsOpen ? <div className="dma-tts-settings">
            <fieldset className="dma-tts-wlf-fields"><legend>WLF shift settings</legend>
              <label>Reference temperature <span><input name="dma-tts-reference-temperature" autoComplete="off" type="number" inputMode="decimal" value={process.draft.referenceTemperatureK} onChange={(event) => process.updateDraft({ referenceTemperatureK: event.target.value, reason: "" })} /><b>K</b></span></label>
              <label>C1 <span><input name="dma-tts-c1" autoComplete="off" type="number" inputMode="decimal" value={process.draft.c1} onChange={(event) => process.updateDraft({ c1: event.target.value, reason: "" })} /><b>1</b></span></label>
              <label>C2 <span><input name="dma-tts-c2" autoComplete="off" type="number" inputMode="decimal" value={process.draft.c2K} onChange={(event) => process.updateDraft({ c2K: event.target.value, reason: "" })} /><b>K</b></span></label>
              {settingsEdited ? <label>Reason for changes <span><input name="dma-tts-change-reason" autoComplete="off" type="text" value={process.draft.reason} onChange={(event) => process.updateDraft({ reason: event.target.value })} /></span></label> : null}
            </fieldset>
            <div className="dma-tts-temperature-table-scroll"><table><caption>Temperature use</caption><thead><tr><th>Temperature</th><th>Use</th><th>Reason when not used</th></tr></thead><tbody>{process.source?.rows.map((row) => {
              const disposition = process.draft!.dispositions[row.ordinal];
              return <tr key={row.ordinal}><td>{compact(row.temperatureK)} K</td><td><select name={`dma-tts-temperature-${row.ordinal}-use`} aria-label={`Use ${compact(row.temperatureK)} K`} value={disposition.partition} onChange={(event) => process.setDisposition(row.ordinal, event.target.value as DmaTtsPartition)}>{(Object.keys(PARTITION_LABELS) as DmaTtsPartition[]).map((value) => <option value={value} key={value}>{PARTITION_LABELS[value]}</option>)}</select></td><td>{disposition.partition === "EXCLUDED" ? <input name={`dma-tts-temperature-${row.ordinal}-exclusion-reason`} autoComplete="off" aria-label={`Reason for not using ${compact(row.temperatureK)} K`} value={disposition.exclusionReason} onChange={(event) => process.setExclusionReason(row.ordinal, event.target.value)} /> : "—"}</td></tr>;
            })}</tbody></table></div>
          </div> : null}
          <div className="dma-tts-confirmation">
            <button type="button" className="button primary" disabled={!process.canSave || process.status === "saving"} onClick={() => void process.save()}>{process.status === "saving" ? "Creating…" : "Create shifted response"}</button>
          </div>
        </> : null}
        {process.fitInput ? <div className="dma-tts-saved-row"><div><h2>DMA response saved</h2><p>{process.fitInput.rows.filter((row) => row.partition !== "EXCLUDED").length} shifted values at {compact(Number(process.fitInput.reference_temperature_k))} K</p></div></div> : null}
        {process.status === "loading" && !process.error ? <p className="dma-tts-loading" role="status">Preparing WLF shift…</p> : null}
      </section>
    </div>}
    ribbonOpen={ribbonOpen}
    onRibbonOpenChange={onRibbonOpenChange}
  />;
}
