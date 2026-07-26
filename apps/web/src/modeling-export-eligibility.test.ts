import { describe, expect, it } from "vitest";

import { exportPrerequisites } from "./modeling-export-eligibility";
import type { ModelingSessionSummary } from "./modeling-session-context";

const session: ModelingSessionSummary = {
  version: 3, updatedAt: "2026-07-24T00:00:00Z", materialFamily: "metal", objective: "Card",
  material: { id: "material", revisionId: "material-r1", label: "DP780", revisionNo: 1 },
  materialState: { id: "state", revisionId: "state-r1", label: "As received", revisionNo: 1 },
  testData: { id: "test", revisionId: "test-r1", label: "Tensile", revisionNo: 1 },
  mappingProfile: { id: "mapping", revisionId: "mapping-r1", label: "Tensile mapping", revisionNo: 1 },
  processingOutput: { id: "output", revisionId: "output-r1", label: "Selected fit", revisionNo: 1 },
  selection: { id: "output", revisionId: "output-r1", label: "Selected fit", revisionNo: 1 },
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
  fit_decision: { candidate_key: "swift" },
  export_provenance: {
    material: { aggregate_id: "material", revision_id: "material-r1" },
    material_state: { aggregate_id: "state", revision_id: "state-r1" },
    test_run: { aggregate_id: "run", revision_id: "run-r1" },
  },
};

describe("verified exact Export chain", () => {
  it("reports current only when the server proof and exact session pins agree", () => {
    const prerequisites = exportPrerequisites({
      session,
      material: material as never,
      materialState: materialState as never,
      testData: testData as never,
      output: output as never,
    });
    expect(prerequisites.map((item) => [item.label, item.status])).toContainEqual(["Processing Output", "current"]);
    expect(prerequisites).toContainEqual(expect.objectContaining({
      label: "Server provenance proof",
      status: "current",
    }));
    expect(prerequisites).toContainEqual(expect.objectContaining({
      label: "Ephemeral target preview producer",
      status: "not-supported",
    }));
  });

  it("marks present but mismatched source pins and server proof stale", () => {
    const prerequisites = exportPrerequisites({
      session,
      material: { ...material, current_revision: { id: "material-r2" } } as never,
      materialState: materialState as never,
      testData: testData as never,
      output: {
        ...output,
        source_document: { aggregate_id: "other-test", revision_id: "test-r1" },
        mapping_profile: { aggregate_id: "other-mapping", revision_id: "mapping-r1" },
        export_provenance: {
          ...output.export_provenance,
          material: { aggregate_id: "other-material", revision_id: "material-r1" },
        },
      } as never,
    });

    expect(prerequisites).toContainEqual(expect.objectContaining({ label: "Material", status: "stale" }));
    expect(prerequisites).toContainEqual(expect.objectContaining({ label: "Test Data", status: "stale" }));
    expect(prerequisites).toContainEqual(expect.objectContaining({ label: "Mapping Profile", status: "stale" }));
    expect(prerequisites).toContainEqual(expect.objectContaining({ label: "Server provenance proof", status: "stale" }));
  });

  it("never infers server proof for historical outputs with a null projection", () => {
    const prerequisites = exportPrerequisites({
      session,
      material: material as never,
      materialState: materialState as never,
      testData: testData as never,
      output: { ...output, export_provenance: null } as never,
    });

    expect(prerequisites).toContainEqual(expect.objectContaining({
      label: "Server provenance proof",
      status: "missing",
      detail: expect.stringContaining("never inferred"),
    }));
  });
});
