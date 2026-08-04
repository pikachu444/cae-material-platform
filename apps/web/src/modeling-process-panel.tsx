import { useEffect, useRef, useState, type ReactNode } from "react";

import type {
  CommonProcessingOutputResponse,
  CommonProcessingStep,
} from "./types";

export type ProcessSavedResultState = {
  status: "loading" | "ready" | "error";
  scalarPa?: number;
};

type SavedProcessingOutputDocument = {
  document_type?: unknown;
  output_id?: unknown;
  source_document?: { aggregate_id?: unknown; revision_id?: unknown };
  mapping_profile?: { aggregate_id?: unknown; revision_id?: unknown };
  steps?: CommonProcessingStep[];
  result?: {
    stages?: Array<{
      scalar_results?: Array<{ key?: unknown; value?: unknown; unit?: unknown }>;
    }>;
  };
};

// Keep the exact four revision pins positional at the lazy boundary.  These
// values are Process-only and should not pull verbose field names into the
// common workbench chunk.
type SavedProcessingOutputPins = readonly [
  sourceDocumentId: string | undefined,
  sourceDocumentRevisionId: string | undefined,
  mappingProfileId: string | undefined,
  mappingProfileRevisionId: string | undefined,
];

function savedScalarFromDocument(document: SavedProcessingOutputDocument): number | null {
  const scalar = document.result?.stages?.flatMap((stage) => stage.scalar_results ?? [])
    .find((item) => item.key === "youngs_modulus");
  return scalar?.unit === "Pa"
    && typeof scalar.value === "number"
    && Number.isFinite(scalar.value)
    ? scalar.value
    : null;
}

function jsonStructureMatches(left: unknown, right: unknown): boolean {
  const canonical = (value: unknown) => JSON.stringify(value, (_key, nested) => {
    if (!nested || typeof nested !== "object" || Array.isArray(nested)) return nested;
    return Object.fromEntries(Object.entries(nested as Record<string, unknown>).sort());
  });
  return canonical(left) === canonical(right);
}

function exactOutputPinMatches(
  pin: { aggregate_id?: unknown; revision_id?: unknown } | undefined,
  id: string | undefined,
  revisionId: string | undefined,
): boolean {
  return pin?.aggregate_id === id && pin?.revision_id === revisionId;
}

/**
 * Parse and validate one immutable Process artifact against its exact list
 * response and currently pinned source/profile revisions.
 *
 * This is intentionally exported from the lazy Process module so the
 * Process-only artifact contract stays behind the existing module boundary.
 */
export function parseSavedProcessingOutput(
  text: string,
  output: CommonProcessingOutputResponse,
  pins: SavedProcessingOutputPins,
): number {
  const parsed = JSON.parse(text) as SavedProcessingOutputDocument;
  const valid = parsed.document_type === "cmp.processing-output"
    && parsed.output_id === output.processing_output_id
    && output.current_revision.revision_no === 1
    && jsonStructureMatches(parsed.steps, output.steps)
    && exactOutputPinMatches(parsed.source_document, output.source_document.aggregate_id, output.source_document.revision_id)
    && exactOutputPinMatches(parsed.source_document, pins[0], pins[1])
    && exactOutputPinMatches(parsed.mapping_profile, output.mapping_profile.aggregate_id, output.mapping_profile.revision_id)
    && exactOutputPinMatches(parsed.mapping_profile, pins[2], pins[3]);
  const scalarPa = valid ? savedScalarFromDocument(parsed) : null;
  if (!valid || scalarPa === null) {
    throw new Error("Saved result unavailable");
  }
  return scalarPa;
}

export interface ModelingProcessPanelProps {
  stepNumber?: number;
  stepLabel: string;
  sourceIdentity: string;
  stepControls: ReactNode;
  scalarPa?: number;
  processReady: boolean;
  hasPreview: boolean;
  hasLastValidPreview: boolean;
  notice?: string | null;
  busy: boolean;
  outputLabel: string;
  outputReason: string;
  savedOutputs: CommonProcessingOutputResponse[];
  savedResultStates: Record<string, ProcessSavedResultState>;
  currentOutputId?: string;
  onClose: (visible: boolean) => void;
  onOutputLabelChange: (value: string) => void;
  onOutputReasonChange: (value: string) => void;
  onSave: () => void;
  onLoadSavedResult: (output: CommonProcessingOutputResponse) => void;
  onUseSavedSettings: (output: CommonProcessingOutputResponse) => void;
  onRetryExactSource?: () => void;
}

function formatModulus(valuePa: number | undefined): string {
  return valuePa === undefined ? "—" : `${(valuePa / 1e9).toFixed(1)} GPa`;
}

function savedMethodRange(steps: CommonProcessingStep[]): { method: string; range: string } {
  const modulus = steps.find((step) => step.method_id === "metal.elastic_modulus");
  const method = String(modulus?.options.method ?? "processing");
  const methodLabels: Record<string, string> = {
    robust_huber: "Auto robust",
    linear_regression: "Linear regression",
    chord: "Chord",
    secant: "Secant",
    manual: "Manual slope",
  };
  return {
    method: methodLabels[method] ?? method,
    range: modulus
      ? `${String(modulus.options.minimum_strain ?? "—")}–${String(modulus.options.maximum_strain ?? "—")}`
      : "—",
  };
}

export default function ModelingProcessPanel({
  stepNumber,
  stepLabel,
  sourceIdentity,
  stepControls,
  scalarPa,
  processReady,
  hasPreview,
  hasLastValidPreview,
  notice,
  busy,
  outputLabel,
  outputReason,
  savedOutputs,
  savedResultStates,
  currentOutputId,
  onClose,
  onOutputLabelChange,
  onOutputReasonChange,
  onSave,
  onLoadSavedResult,
  onUseSavedSettings,
  onRetryExactSource,
}: ModelingProcessPanelProps) {
  const [savedResultsOpen, setSavedResultsOpen] = useState(false);
  const requestedSavedOutputIds = useRef(new Set<string>());
  // Keep the latest callback without making parent callback identity changes
  // restart the artifact-load effect.
  const onLoadSavedResultRef = useRef(onLoadSavedResult);
  onLoadSavedResultRef.current = onLoadSavedResult;

  function requestSavedResult(output: CommonProcessingOutputResponse): void {
    const outputId = output.processing_output_id;
    if (requestedSavedOutputIds.current.has(outputId)) return;
    requestedSavedOutputIds.current.add(outputId);
    onLoadSavedResultRef.current(output);
  }

  useEffect(() => {
    if (!savedResultsOpen) {
      // A new disclosure opening is a fresh request window (and preserves the
      // existing refresh-on-reopen behavior).  While it is open, the set below
      // prevents parent rerenders from issuing duplicate requests.
      requestedSavedOutputIds.current.clear();
      return;
    }
    const visibleSavedOutputIds = new Set(savedOutputs.map((output) => output.processing_output_id));
    requestedSavedOutputIds.current.forEach((outputId) => {
      if (!visibleSavedOutputIds.has(outputId)) requestedSavedOutputIds.current.delete(outputId);
    });
    savedOutputs.forEach(requestSavedResult);
  }, [savedOutputs, savedResultsOpen]);

  const previewState = hasPreview ? "Server result · preview only" : hasLastValidPreview ? "Last valid server result · draft changed" : "No valid preview";
  const statusClass = processReady ? "status-current" : "status-blocked";
  const visibleScalarPa = processReady ? scalarPa : undefined;
  const visibleSourceIdentity = onRetryExactSource && sourceIdentity
    ? `Exact source unavailable · ${sourceIdentity.split(" · ").at(-1)}`
    : sourceIdentity || "No exact Test Data";
  const statusText = `${processReady ? (currentOutputId ? "Current exact source" : "Draft · not saved") : "Blocked · choose exact source in Data"} · ${notice ?? "No current Process result."}`;
  const saveDisabled = busy || !hasPreview || !processReady || !outputLabel.trim() || !outputReason.trim();
  const stepTitle = `Step ${stepNumber ?? "—"} · Process · ${stepLabel}`;
  return (
    <aside className="process-stage-options" aria-label="Process settings" data-modeling-process-panel="ready">
      <div className="process-band-heading">
        <strong>{stepTitle}</strong>
        <span className="process-band-source">{visibleSourceIdentity}</span>
        <button className="text-button" type="button" onClick={() => onClose(false)}>Close</button>
      </div>
      <div className="process-band-groups">
        <section className="process-band-group process-band-calculation" aria-labelledby="process-calculation-title">
          <h3 id="process-calculation-title">Calculation</h3>
          <fieldset className="process-band-controls" disabled={!processReady}>
            <legend className="visually-hidden">Current Process settings</legend>
            {stepControls}
          </fieldset>
        </section>
        <section className="process-band-group process-band-preview" aria-labelledby="process-preview-title">
          <h3 id="process-preview-title">Preview</h3>
          <div className="process-band-result"><span>Calculated preview</span><strong>{formatModulus(visibleScalarPa)}</strong><small>{previewState}</small></div>
        </section>
        <section className="process-band-group process-band-save-result" aria-labelledby="process-save-result-title">
          <h3 id="process-save-result-title">Save result</h3>
          <div className="process-band-save">
            <label>Processed curve label<input aria-label="Processed curve label" value={outputLabel} onChange={(event) => onOutputLabelChange(event.target.value)} /></label>
            <label>Save reason<input aria-label="Save reason" value={outputReason} onChange={(event) => onOutputReasonChange(event.target.value)} /></label>
            <button className="button primary" type="button" disabled={saveDisabled} onClick={onSave}>Save processed curves</button>
          </div>
        </section>
      </div>
      <div className={`process-band-status ${statusClass}`} role="status">
        <span>{statusText}</span>
        {onRetryExactSource ? <button className="text-button" type="button" disabled={busy} onClick={onRetryExactSource}>Retry exact source</button> : null}
      </div>
      <details className="process-saved-results" onToggle={(event) => {
        const open = event.currentTarget.open;
        setSavedResultsOpen(open);
        // The native toggle event can be coalesced when a user closes and
        // immediately reopens the disclosure.  Reset and request directly on
        // every opening event so reopening remains an explicit refresh.
        requestedSavedOutputIds.current.clear();
        if (open) savedOutputs.forEach(requestSavedResult);
      }}>
        <summary>Saved processing results ({savedOutputs.length})</summary>
        <div className="process-comparison-region">
          {savedOutputs.length ? <table className="process-comparison-table" aria-label="Saved processing results">
            <thead><tr><th scope="col">Label</th><th scope="col">Method</th><th scope="col">Range</th><th scope="col">Result</th><th scope="col">Revision</th><th scope="col">State</th><th scope="col">Action</th></tr></thead>
            <tbody>{savedOutputs.map((output) => {
              const state = savedResultStates[output.processing_output_id] ?? { status: "loading" as const };
              const current = currentOutputId === output.processing_output_id;
              const { method, range } = savedMethodRange(output.steps);
              const value = state.status === "ready"
                ? formatModulus(state.scalarPa)
                : state.status === "loading" ? "Loading saved result…" : "Saved result unavailable";
              return <tr className="process-comparison-row" key={output.processing_output_id}>
                <td>{output.label}</td><td>{method}</td><td>{range}</td><td>{value}</td><td>r{output.current_revision.revision_no}</td><td>{current ? "current" : "history"}</td><td>
                  {state.status === "error"
                    ? <button className="text-button" type="button" onClick={() => onLoadSavedResult(output)}>Retry</button>
                    : <button className="text-button" type="button" disabled={state.status !== "ready"} onClick={() => onUseSavedSettings(output)}>Use settings</button>}
                </td>
              </tr>;
            })}</tbody>
          </table> : <p className="muted">No saved results for this exact source.</p>}
        </div>
      </details>
    </aside>
  );
}
