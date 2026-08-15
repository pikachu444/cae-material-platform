import { describe, expect, it } from "vitest";

import {
  modelingDataDocumentMatchesMaterialContext,
  modelingFamilyFromQuantities,
  reduceModelingSession,
} from "./modeling-session-context";
import { reduceModelingSession as reduceOwnedModelingSession } from "./features/modeling/model/session-controller";

describe("Modeling session context compatibility", () => {
  it("accepts earlier Material and State revisions only when their aggregate identities match", () => {
    const material = { material_id: "material", current_revision: { id: "material-r2" } };
    const state = { material_state_id: "state", current_revision: { id: "state-r2" } };
    expect(modelingDataDocumentMatchesMaterialContext({ governed_source: {
      material: { aggregate_id: "material", revision_id: "material-r1" },
      material_state: { aggregate_id: "state", revision_id: "state-r1" },
    } }, material, state)).toBe(true);
    expect(modelingDataDocumentMatchesMaterialContext({ governed_source: null }, material, state)).toBe(false);
    expect(modelingDataDocumentMatchesMaterialContext({ governed_source: {
      material: { aggregate_id: "other", revision_id: "material-r1" },
      material_state: { aggregate_id: "state", revision_id: "state-r1" },
    } }, material, state)).toBe(false);
  });

  it("selects a modeling family from quantity semantics", () => {
    expect(modelingFamilyFromQuantities(["mechanics.strain.engineering", "mechanics.stress.engineering"])).toBe("metal");
    expect(modelingFamilyFromQuantities(["time", "modulus.relaxation"])).toBe("polymer");
    expect(modelingFamilyFromQuantities(["mechanics.stress.planar"])).toBe("elastomer");
  });

  it("re-exports the Modeling-owned session controller during consumer migration", () => {
    expect(reduceModelingSession).toBe(reduceOwnedModelingSession);
  });
});
