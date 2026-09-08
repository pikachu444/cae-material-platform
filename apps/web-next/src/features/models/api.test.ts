import { describe, expect, it } from "vitest";
import { modelProcessingRelation, type MaterialModelRow } from "./api";

function model(content: Record<string, unknown>, ir: Record<string, unknown> = {}): MaterialModelRow {
  return {
    id: "model-1",
    stateId: "state-1",
    stateRevisionId: "state-revision-1",
    revisionId: "model-revision-1",
    family: "tabulated_plasticity",
    schemaId: "cmp.tabulated-plasticity-model",
    content,
    ir,
    resourcePath: "tabulated-plasticity-models",
  };
}

describe("stored model processing relations", () => {
  it("uses the exact persisted output identity from the model projection", () => {
    expect(modelProcessingRelation(model({
      processing_projection: { output_id: "output-1", output_revision_id: "output-revision-1" },
    }))).toEqual({ id: "output-1", revisionId: "output-revision-1" });
  });

  it("does not infer a generation edge from material membership", () => {
    expect(modelProcessingRelation(model({ material_id: "same-material" }))).toBeNull();
    expect(modelProcessingRelation(model({}, {
      material_id: "same-material",
      source_revisions: { test_data: { id: "other-test", revision_id: "other-test-revision" } },
    }))).toBeNull();
  });
});
