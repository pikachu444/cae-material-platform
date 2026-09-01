import type {
  ModelingSessionEvent,
  ModelingSessionRecordRef,
  ModelingSessionSummary,
} from "./session-controller";

export interface PolymerFitInputRestoration {
  staleInput: ModelingSessionRecordRef;
  selectedTestDataRefs: ModelingSessionRecordRef[];
  ensembleDocumentIds: string[];
  visibleDocumentKeys: string[];
  sessionEvent: Extract<ModelingSessionEvent, { type: "RESTORE_STALE_FIT" }>;
}

function exactRefKey(ref: ModelingSessionRecordRef): string {
  return `${ref.id}:${ref.revisionId}`;
}

export function buildPolymerFitInputRestoration(
  session: ModelingSessionSummary | null | undefined,
  selectedTestDataRefs: ModelingSessionRecordRef[],
  ensembleDocumentIds: string[],
  visibleDocumentKeys: string[],
): PolymerFitInputRestoration | undefined {
  const staleInput = session?.stalePointers?.testData;
  if (!staleInput) return undefined;

  return {
    staleInput,
    selectedTestDataRefs: [
      ...selectedTestDataRefs.filter((item) => item.id !== staleInput.id),
      staleInput,
    ],
    ensembleDocumentIds: [
      ...ensembleDocumentIds.filter((id) => id !== staleInput.id),
      staleInput.id,
    ],
    visibleDocumentKeys: [
      ...visibleDocumentKeys.filter((key) => !key.startsWith(`${staleInput.id}:`)),
      exactRefKey(staleInput),
    ],
    sessionEvent: {
      type: "RESTORE_STALE_FIT",
      testData: staleInput,
      processingOutput: session?.stalePointers?.processingOutput,
      selection: session?.stalePointers?.selection,
      materialModelIr: session?.stalePointers?.materialModelIr,
    },
  };
}
