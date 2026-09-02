import { describe, expect, it } from "vitest";

import type { CommonProcessingOutputResponse } from "./common-processing-contracts";
import { hasExactFitHistory } from "./fit-surface-state";

function output(input: {
  id: string;
  revisionId: string;
  methodId: string;
  sourceId?: string;
  sourceRevisionId?: string;
}): CommonProcessingOutputResponse {
  return {
    processing_output_id: input.id,
    current_revision: { id: input.revisionId },
    steps: [{ method_id: input.methodId }],
    source_processing_output: input.sourceId && input.sourceRevisionId
      ? { aggregate_id: input.sourceId, revision_id: input.sourceRevisionId }
      : undefined,
  } as CommonProcessingOutputResponse;
}

describe("exact Fit history", () => {
  it("matches both the Process output identity and its immutable revision", () => {
    const source = output({
      id: "process-a",
      revisionId: "process-a-r1",
      methodId: "curve.crop",
    });
    const exact = output({
      id: "fit-a",
      revisionId: "fit-a-r1",
      methodId: "metal.hardening_fit_extrapolate",
      sourceId: "process-a",
      sourceRevisionId: "process-a-r1",
    });
    const differentRevision = output({
      id: "fit-old",
      revisionId: "fit-old-r1",
      methodId: "metal.hardening_fit_extrapolate",
      sourceId: "process-a",
      sourceRevisionId: "process-a-r0",
    });
    const unrelated = output({
      id: "fit-b",
      revisionId: "fit-b-r1",
      methodId: "metal.hardening_fit_extrapolate",
      sourceId: "process-b",
      sourceRevisionId: "process-b-r1",
    });

    expect(hasExactFitHistory([differentRevision, unrelated], source)).toBe(false);
    expect(hasExactFitHistory([differentRevision, exact, unrelated], source)).toBe(true);
    expect(hasExactFitHistory([exact], undefined)).toBe(false);
  });
});
