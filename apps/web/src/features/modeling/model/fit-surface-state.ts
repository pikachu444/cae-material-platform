import type {
  CommonProcessingOutputResponse,
  CommonProcessingPreview,
} from "./common-processing-contracts";
import type { FitDecisionSelection } from "./fit-decision-contract";
import { isFitMethod } from "./processing-registry";

export type FitSurfaceState =
  | "calculating"
  | "saved-current"
  | "preview-not-saved"
  | "saved-result-stale"
  | "not-calculated";

export function fitSurfaceState(input: {
  previewBusy: boolean;
  usablePreview: boolean;
  verifiedSavedFit: boolean;
  fitHistoryExists: boolean;
}): FitSurfaceState {
  if (input.previewBusy) return "calculating";
  if (input.verifiedSavedFit && input.usablePreview) return "saved-current";
  if (input.usablePreview) return "preview-not-saved";
  if (input.fitHistoryExists) return "saved-result-stale";
  return "not-calculated";
}

export function hasExactFitHistory(
  outputs: CommonProcessingOutputResponse[],
  source: CommonProcessingOutputResponse | undefined,
): boolean {
  if (!source) return false;
  return outputs.some((output) =>
    output.steps.some((step) => isFitMethod(step.method_id))
      && output.source_processing_output?.aggregate_id === source.processing_output_id
      && output.source_processing_output.revision_id === source.current_revision.id,
  );
}

export const FIT_SURFACE_STATE_LABELS: Record<FitSurfaceState, string> = {
  calculating: "Calculating",
  "saved-current": "Saved current",
  "preview-not-saved": "Preview not saved",
  "saved-result-stale": "Saved result stale",
  "not-calculated": "Not calculated",
};

export interface ExactFitRestore {
  preview: CommonProcessingPreview;
  selection: FitDecisionSelection | null;
}

export interface FitRestoreInFlight {
  identity: string;
  promise: Promise<ExactFitRestore>;
}

/**
 * Serialize every exact restore input without relying on object insertion order.
 * Arrays retain order because processing steps are ordered contract data.
 */
export function deterministicFitRestoreIdentity(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(deterministicFitRestoreIdentity).join(",")}]`;
  }
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0)
      .map(([key, nested]) => `${JSON.stringify(key)}:${deterministicFitRestoreIdentity(nested)}`);
    return `{${entries.join(",")}}`;
  }
  if (value === undefined) return "undefined";
  return typeof value === "string" ? JSON.stringify(value) : String(value);
}
