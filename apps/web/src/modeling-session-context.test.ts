import { beforeEach, describe, expect, it } from "vitest";

import {
  clearModelingSession,
  loadModelingSession,
  modelingFamilyFromQuantities,
  saveModelingSession,
} from "./modeling-session-context";

describe("recent Material Modeling session", () => {
  beforeEach(() => clearModelingSession());

  it("preserves friendly exact-revision context across navigation", () => {
    saveModelingSession({
      materialFamily: "metal",
      objective: "Create a card",
      material: { id: "material-1", revisionId: "material-r1", label: "DP780", revisionNo: 1 },
    });
    saveModelingSession({
      testData: { id: "test-1", revisionId: "test-r2", label: "DP780 tensile", revisionNo: 2 },
      processingOutput: {
        id: "output-1",
        revisionId: "output-r1",
        label: "DP780 · Swift reviewed fit",
        revisionNo: 1,
      },
    });

    expect(loadModelingSession()).toMatchObject({
      materialFamily: "metal",
      material: { revisionId: "material-r1", label: "DP780", revisionNo: 1 },
      testData: { revisionId: "test-r2", label: "DP780 tensile", revisionNo: 2 },
      processingOutput: { revisionId: "output-r1", label: "DP780 · Swift reviewed fit", revisionNo: 1 },
      version: 2,
      workspace: { activeStage: "fit" },
    });
  });

  it("rejects malformed stored state instead of restoring an ambiguous revision", () => {
    window.sessionStorage.setItem("cmp.modeling.recent-session.v1", JSON.stringify({ version: 1 }));
    expect(loadModelingSession()).toBeNull();
  });

  it("migrates a valid v1 session into the persistent Modeling workspace", () => {
    window.sessionStorage.setItem("cmp.modeling.recent-session.v1", JSON.stringify({
      version: 1,
      updatedAt: "2026-07-22T00:00:00Z",
      materialFamily: "metal",
      objective: "Create a card",
    }));

    expect(loadModelingSession()).toMatchObject({
      version: 2,
      workspace: {
        activeStage: "fit",
        selectedDocumentIds: [],
        plotView: "pipeline",
      },
    });
  });

  it("selects a modeling family from quantity semantics", () => {
    expect(modelingFamilyFromQuantities(["mechanics.strain.engineering", "mechanics.stress.engineering"])).toBe("metal");
    expect(modelingFamilyFromQuantities(["time", "modulus.relaxation"])).toBe("polymer");
    expect(modelingFamilyFromQuantities(["mechanics.stress.planar"])).toBe("elastomer");
  });
});
