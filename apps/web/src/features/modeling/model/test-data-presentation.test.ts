import { describe, expect, it } from "vitest";

import type { CanonicalTestDataDocumentResponse } from "../../test-data/contracts";
import { savedModelingInputDisplayLabel } from "./test-data-presentation";

const reference = {
  id: "test-data-1",
  revisionId: "revision-1",
  revisionNo: 1,
  label: "CMP-DEMO-POLYMER-FIT-RELAXATION-CSV",
};

function document(revisionId: string, pointCount: number): CanonicalTestDataDocumentResponse {
  return {
    test_data_document_id: reference.id,
    document_key: reference.label,
    method: "relaxation",
    specimen_id: "specimen-1",
    current_revision: { id: revisionId, revision_no: revisionId === "revision-1" ? 1 : 2 },
    channels: [{ point_count: pointCount }],
  } as CanonicalTestDataDocumentResponse;
}

describe("saved Modeling input presentation", () => {
  it("uses current document metadata only for the exact saved revision", () => {
    expect(savedModelingInputDisplayLabel(reference, document("revision-1", 43)))
      .toBe("Relaxation test 0001 · 43 measured points");
  });

  it("does not relabel a saved revision with metadata from the current head", () => {
    const label = savedModelingInputDisplayLabel(reference, document("revision-2", 99));

    expect(label).toBe("Saved Test Data");
    expect(label).not.toContain("99");
  });
});
