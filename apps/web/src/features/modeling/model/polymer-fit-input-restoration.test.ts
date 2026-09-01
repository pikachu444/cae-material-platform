import { describe, expect, it } from "vitest";

import type { ModelingSessionRecordRef, ModelingSessionSummary } from "./session-controller";
import { buildPolymerFitInputRestoration } from "./polymer-fit-input-restoration";

const currentInput: ModelingSessionRecordRef = {
  id: "test-data-1",
  revisionId: "revision-2",
  revisionNo: 2,
  label: "Relaxation current",
};

const savedInput: ModelingSessionRecordRef = {
  id: "test-data-1",
  revisionId: "revision-1",
  revisionNo: 1,
  label: "Relaxation saved",
};

function staleSession(): ModelingSessionSummary {
  return {
    version: 4,
    updatedAt: "2026-09-01T00:00:00Z",
    materialFamily: "polymer",
    objective: "Fit relaxation response",
    stalePointers: {
      testData: savedInput,
      processingOutput: { id: "output-1", revisionId: "output-revision-1", revisionNo: 1, label: "Saved output" },
      selection: { id: "selection-1", revisionId: "selection-revision-1", revisionNo: 1, label: "Saved selection" },
      materialModelIr: { id: "model-1", revisionId: "model-revision-1", revisionNo: 1, label: "Saved model" },
    },
    workspace: {
      activeStage: "fit",
      selectedDocumentIds: [],
      selectedTestDataRefs: [],
      visibleTestDataKeys: [],
      selectedStepIndex: 0,
      selectedStageOrdinal: 0,
      plotView: "pipeline",
      settingsOpen: true,
    },
  };
}

describe("buildPolymerFitInputRestoration", () => {
  it("restores the exact saved revision and its downstream pointers", () => {
    const result = buildPolymerFitInputRestoration(
      staleSession(),
      [currentInput],
      [currentInput.id],
      [`${currentInput.id}:${currentInput.revisionId}`],
    );

    expect(result).toMatchObject({
      staleInput: savedInput,
      selectedTestDataRefs: [savedInput],
      ensembleDocumentIds: [savedInput.id],
      visibleDocumentKeys: [`${savedInput.id}:${savedInput.revisionId}`],
      sessionEvent: {
        type: "RESTORE_STALE_FIT",
        testData: savedInput,
        processingOutput: { id: "output-1", revisionId: "output-revision-1" },
        selection: { id: "selection-1", revisionId: "selection-revision-1" },
        materialModelIr: { id: "model-1", revisionId: "model-revision-1" },
      },
    });
  });

  it("does not invent a fallback when no saved input revision exists", () => {
    expect(buildPolymerFitInputRestoration(undefined, [currentInput], [], [])).toBeUndefined();
  });
});
