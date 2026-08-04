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
  const value = Number(scalar?.value);
  return scalar?.unit === "Pa" && isFinite(value) ? value : null;
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
    && exactOutputPinMatches(parsed.source_document, pins[0], pins[1])
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
}

function formatModulus(valuePa: number | undefined): string {
  return valuePa === undefined ? "—" : `${(valuePa / 1e9).toFixed(1)} GPa`;
}

function savedMethodRange(steps: CommonProcessingStep[]): { method: string; range: string } {
  const modulus = steps.find((step) => step.method_id === "metal.elastic_modulus");
  return {
    method: String(modulus?.options.method ?? "processing"),
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
  const statusText = `${processReady ? (currentOutputId ? "Current exact source" : "Draft · not saved") : "Blocked · choose exact source in Data"} · Preview ${formatModulus(scalarPa)} · ${notice ?? "No current Process result."}`;
  const saveDisabled = busy || !hasPreview || !processReady || !outputLabel.trim() || !outputReason.trim();
  const stepTitle = `Step ${stepNumber ?? "—"} · Process · ${stepLabel}`;
  return (
    <aside className="process-stage-options" aria-label="Process settings" data-modeling-process-panel="ready">
      <div className="process-band-heading">
        <strong>{stepTitle}</strong>
        <span className="process-band-source">{sourceIdentity}</span>
        <button className="text-button" type="button" onClick={() => onClose(false)}>Close</button>
      </div>
      <fieldset className="process-band-controls" disabled={!processReady}>
        <legend className="visually-hidden">Current Process settings</legend>
        {stepControls}
      </fieldset>
      <div className="process-band-save">
        <div className="process-band-result"><span>Calculated preview</span><strong>{formatModulus(scalarPa)}</strong><small>{previewState}</small></div>
        <label>Processed curve label<input aria-label="Processed curve label" value={outputLabel} onChange={(event) => onOutputLabelChange(event.target.value)} /></label>
        <label>Save reason<input aria-label="Save reason" value={outputReason} onChange={(event) => onOutputReasonChange(event.target.value)} /></label>
        <button className="button primary" type="button" disabled={saveDisabled} onClick={onSave}>Save processed curves</button>
      </div>
      <div className={`process-band-status ${statusClass}`} role="status">{statusText}</div>
      <details className="process-saved-results" onToggle={(event) => {
        const open = event.currentTarget.open;
        setSavedResultsOpen(open);
        // The native toggle event can be coalesced when a user closes and
        // immediately reopens the disclosure.  Reset and request directly on
        // every opening event so reopening remains an explicit refresh.
        requestedSavedOutputIds.current.clear();
        if (open) savedOutputs.forEach(requestSavedResult);
      }}>
        <summary>Saved results ({savedOutputs.length})</summary>
        <div className="process-comparison-region">
          {savedOutputs.length ? savedOutputs.map((output) => {
            const state = savedResultStates[output.processing_output_id] ?? { status: "loading" as const };
            const current = currentOutputId === output.processing_output_id;
            const { method, range } = savedMethodRange(output.steps);
            const value = state.status === "ready"
              ? formatModulus(state.scalarPa)
              : state.status === "loading" ? "Loading saved result…" : "Saved result unavailable";
            return <article className="process-comparison-row" key={output.processing_output_id}>
              <div>{output.label} · {sourceIdentity} · {method} · {range} · {value} · output r{output.current_revision.revision_no} · {current ? "current" : "history"}</div>
              {state.status === "error"
                ? <button className="text-button" type="button" onClick={() => onLoadSavedResult(output)}>Retry</button>
                : <button className="text-button" type="button" disabled={state.status !== "ready"} onClick={() => onUseSavedSettings(output)}>Use settings</button>}
            </article>;
          }) : <p className="muted">No saved results for this exact source.</p>}
        </div>
      </details>
    </aside>
  );
}
