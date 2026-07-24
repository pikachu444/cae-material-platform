import { describe, expect, it } from "vitest";

import { hasVerifiedExactExportChain } from "./modeling-export-eligibility";
import type { ModelingSessionSummary } from "./modeling-session-context";

const session: ModelingSessionSummary = {
  version: 3, updatedAt: "2026-07-24T00:00:00Z", materialFamily: "metal", objective: "Card",
  material: { id: "material", revisionId: "material-r1", label: "DP780", revisionNo: 1 },
  materialState: { id: "state", revisionId: "state-r1", label: "As received", revisionNo: 1 },
  testData: { id: "test", revisionId: "test-r1", label: "Tensile", revisionNo: 1 },
  mappingProfile: { id: "mapping", revisionId: "mapping-r1", label: "Tensile mapping", revisionNo: 1 },
  processingOutput: { id: "output", revisionId: "output-r1", label: "Selected fit", revisionNo: 1 },
  workspace: { activeStage: "export", selectedDocumentIds: [], selectedStepIndex: 0, selectedStageOrdinal: 0, plotView: "pipeline", settingsOpen: false },
};

const material = { material_id: "material", current_revision: { id: "material-r1" } };
const materialState = { material_state_id: "state", current_revision: { id: "state-r1" } };
const testData = { test_data_document_id: "test", current_revision: { id: "test-r1" } };
const output = {
  processing_output_id: "output",
  current_revision: { id: "output-r1" },
  source_document: { aggregate_id: "test", revision_id: "test-r1" },
  mapping_profile: { aggregate_id: "mapping", revision_id: "mapping-r1" },
};

describe("verified exact Export chain", () => {
  it("permits the family adapter only for matching exact current pins", () => {
    expect(hasVerifiedExactExportChain({
      session,
      material: material as never,
      materialState: materialState as never,
      testData: testData as never,
      output: output as never,
    })).toBe(true);
  });

  it("fails closed for a stale or different-material output", () => {
    expect(hasVerifiedExactExportChain({
      session,
      material: { ...material, current_revision: { id: "material-r2" } } as never,
      materialState: materialState as never,
      testData: testData as never,
      output: output as never,
    })).toBe(false);
    expect(hasVerifiedExactExportChain({
      session,
      material: material as never,
      materialState: materialState as never,
      testData: testData as never,
      output: { ...output, source_document: { aggregate_id: "other-test", revision_id: "test-r1" } } as never,
    })).toBe(false);
    expect(hasVerifiedExactExportChain({
      session: { ...session, mappingProfile: undefined },
      material: material as never,
      materialState: materialState as never,
      testData: testData as never,
      output: output as never,
    })).toBe(false);
  });
});
