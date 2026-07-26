import { beforeEach, describe, expect, it } from "vitest";

import {
  clearModelingSession,
  dispatchModelingSession,
  loadModelingSession,
  modelingFamilyFromQuantities,
  reduceModelingSession,
  saveModelingSession,
  type ModelingSessionRecordRef,
} from "./modeling-session-context";

const ref = (id: string): ModelingSessionRecordRef => ({ id, revisionId: `${id}-r1`, label: id, revisionNo: 1 });

function populatedSession() {
  let session = reduceModelingSession(null, { type: "PATCH", patch: {
    material: ref("material"), materialState: ref("state"), testData: ref("test-data"),
    mappingProfile: ref("mapping"), recipe: ref("recipe"), processingOutput: ref("processed"),
    fitCandidate: ref("fit"), selection: ref("selection"), validation: ref("validation"),
    reviewRelease: ref("review"), materialModelIr: ref("ir"), neutralModel: ref("neutral"), exportArtifact: ref("export"),
  } });
  return session;
}

describe("Modeling session v3 reducer", () => {
  beforeEach(() => clearModelingSession());

  it("starts a new session in Data without inheriting a prior current pointer", () => {
    saveModelingSession({ material: ref("old"), processingOutput: ref("old-output") });
    const next = reduceModelingSession(loadModelingSession(), { type: "NEW_SESSION" });

    expect(next.workspace.activeStage).toBe("data");
    expect(next.processingOutput).toBeUndefined();
    expect(next.material).toBeUndefined();
    expect(next.contextSelectionRequired).toBe(true);
  });

  it("persists a new Data session for URL reload/back navigation without parent pins", () => {
    saveModelingSession({
      materialFamily: "polymer",
      material: ref("old-material"),
      materialState: ref("old-state"),
      testData: ref("old-test"),
      workspace: { activeStage: "export", selectedDocumentIds: ["old-test"], selectedStepIndex: 4, selectedStageOrdinal: 5, plotView: "ensemble", settingsOpen: false },
    });

    dispatchModelingSession({ type: "NEW_SESSION", materialFamily: "metal" });
    saveModelingSession({
      workspace: { activeStage: "data", selectedDocumentIds: [], selectedStepIndex: 0, selectedStageOrdinal: 0, plotView: "pipeline", settingsOpen: false },
    });

    expect(loadModelingSession()).toMatchObject({
      materialFamily: "metal",
      contextSelectionRequired: true,
      workspace: { activeStage: "data", selectedDocumentIds: [], selectedStepIndex: 0, selectedStageOrdinal: 0, plotView: "pipeline" },
    });
    expect(loadModelingSession()?.material).toBeUndefined();
    expect(loadModelingSession()?.materialState).toBeUndefined();
    expect(loadModelingSession()?.testData).toBeUndefined();

    saveModelingSession({ contextSelectionRequired: false });
    expect(loadModelingSession()?.contextSelectionRequired).toBe(false);
  });

  it.each([
    ["CHANGE_MATERIAL", { type: "CHANGE_MATERIAL", material: ref("next-material") }],
    ["CHANGE_MATERIAL_STATE", { type: "CHANGE_MATERIAL_STATE", materialState: ref("next-state") }],
    ["CHANGE_FAMILY", { type: "CHANGE_FAMILY", materialFamily: "polymer" }],
    ["PIN_TEST_DATA", { type: "PIN_TEST_DATA", testData: ref("next-test-data") }],
  ] as const)("%s clears every current downstream source pointer", (_name, event) => {
    const next = reduceModelingSession(populatedSession(), event);

    expect(next.processingOutput).toBeUndefined();
    expect(next.fitCandidate).toBeUndefined();
    expect(next.selection).toBeUndefined();
    expect(next.validation).toBeUndefined();
    expect(next.materialModelIr).toBeUndefined();
    expect(next.neutralModel).toBeUndefined();
    expect(next.exportArtifact).toBeUndefined();
    expect(next.reviewRelease).toBeUndefined();
    expect(next.invalidation?.dispositions.reviewRelease).toBe("stale");
    expect(next.stalePointers?.reviewRelease).toMatchObject({ id: "review" });
  });

  it("does not show a stale review/release history when no historical review pointer exists", () => {
    const session = reduceModelingSession(null, { type: "PATCH", patch: { material: ref("material"), testData: ref("test") } });
    const next = reduceModelingSession(session, { type: "CHANGE_MATERIAL", material: ref("next-material") });

    expect(next.invalidation?.dispositions.reviewRelease).toBe("clear");
    expect(next.stalePointers?.reviewRelease).toBeUndefined();
  });

  it("keeps upstream pins while process, fit, selection, validation, and target invalidation only affect their matrix scope", () => {
    const process = reduceModelingSession(populatedSession(), { type: "CHANGE_PROCESS", recipe: ref("next-recipe") });
    expect(process.testData).toMatchObject({ id: "test-data" });
    expect(process.processingOutput).toBeUndefined();

    const fit = reduceModelingSession(populatedSession(), { type: "CHANGE_FIT" });
    expect(fit.recipe).toMatchObject({ id: "recipe" });
    expect(fit.fitCandidate).toBeUndefined();

    const selection = reduceModelingSession(populatedSession(), { type: "SELECT_CANDIDATE", selection: ref("new-selection") });
    expect(selection.processingOutput).toMatchObject({ id: "processed" });
    expect(selection.selection).toMatchObject({ id: "new-selection" });
    expect(selection.validation).toBeUndefined();

    const draftSelection = reduceModelingSession(populatedSession(), { type: "CHANGE_SELECTION" });
    expect(draftSelection.selection).toBeUndefined();
    expect(draftSelection.processingOutput).toMatchObject({ id: "processed" });
    expect(draftSelection.validation).toBeUndefined();
    expect(draftSelection.reviewRelease).toBeUndefined();
    expect(draftSelection.materialModelIr).toBeUndefined();
    expect(draftSelection.neutralModel).toBeUndefined();
    expect(draftSelection.exportArtifact).toBeUndefined();
    expect(draftSelection.invalidation?.reason).toBe("selection");
    expect(draftSelection.invalidation?.dispositions.materialModelIr).toBe("clear");
    expect(draftSelection.invalidation?.dispositions.reviewRelease).toBe("stale");
    expect(draftSelection.stalePointers?.reviewRelease).toMatchObject({ id: "review" });

    const savedFit = reduceModelingSession(populatedSession(), {
      type: "PATCH",
      patch: {
        processingOutput: ref("saved-fit"),
        selection: ref("saved-fit"),
      },
    });
    const changedSavedFit = reduceModelingSession(savedFit, { type: "CHANGE_SELECTION" });
    expect(changedSavedFit.processingOutput).toBeUndefined();
    expect(changedSavedFit.selection).toBeUndefined();
    expect(changedSavedFit.invalidation?.dispositions.processingOutput).toBe("clear");

    const validation = reduceModelingSession(populatedSession(), { type: "CHANGE_VALIDATION_TARGET" });
    expect(validation.processingOutput).toMatchObject({ id: "processed" });
    expect(validation.validation).toBeUndefined();
    expect(validation.exportArtifact).toBeUndefined();

    const target = reduceModelingSession(populatedSession(), { type: "CHANGE_TARGET_PROFILE" });
    expect(target.processingOutput).toMatchObject({ id: "processed" });
    expect(target.materialModelIr).toBeUndefined();
    expect(target.invalidation?.dispositions.neutralModel).toBe("regenerate");
  });

  it("invalidates a recipe-less Process draft and its complete downstream output chain", () => {
    const withOutputOnly = reduceModelingSession(populatedSession(), {
      type: "SET_CURRENT",
      key: "recipe",
      value: undefined,
    });
    const next = reduceModelingSession(withOutputOnly, { type: "CHANGE_PROCESS" });

    expect(next.recipe).toBeUndefined();
    expect(next.processingOutput).toBeUndefined();
    expect(next.fitCandidate).toBeUndefined();
    expect(next.selection).toBeUndefined();
    expect(next.validation).toBeUndefined();
    expect(next.materialModelIr).toBeUndefined();
    expect(next.neutralModel).toBeUndefined();
    expect(next.exportArtifact).toBeUndefined();
    expect(next.reviewRelease).toBeUndefined();
    expect(next.stalePointers?.reviewRelease).toMatchObject({ id: "review" });
    expect(next.invalidation?.reason).toBe("process");
  });

  it("keeps the new exact Mapping Profile while clearing its downstream working chain", () => {
    const next = reduceModelingSession(populatedSession(), { type: "CHANGE_MAPPING", mappingProfile: ref("next-mapping") });

    expect(next.testData).toMatchObject({ id: "test-data" });
    expect(next.mappingProfile).toMatchObject({ id: "next-mapping" });
    expect(next.recipe).toBeUndefined();
    expect(next.processingOutput).toBeUndefined();
    expect(next.fitCandidate).toBeUndefined();
    expect(next.selection).toBeUndefined();
    expect(next.validation).toBeUndefined();
    expect(next.materialModelIr).toBeUndefined();
    expect(next.neutralModel).toBeUndefined();
    expect(next.exportArtifact).toBeUndefined();
  });

  it("treats an already-pinned exact input as an idempotent event", () => {
    const session = reduceModelingSession(null, {
      type: "PATCH",
      patch: { material: ref("material"), materialState: ref("state"), testData: ref("test"), mappingProfile: ref("mapping") },
    });

    expect(reduceModelingSession(session, { type: "PIN_TEST_DATA", testData: ref("test") })).toBe(session);
    expect(reduceModelingSession(session, { type: "CHANGE_MAPPING", mappingProfile: ref("mapping") })).toBe(session);
  });

  it("does not mutate an explicit candidate selection when a route/workspace patch is saved", () => {
    const session = populatedSession();
    const next = reduceModelingSession(session, { type: "PATCH", patch: {
      workspace: { ...session.workspace, activeStage: "export", plotView: "ensemble" },
    } });

    expect(next.selection).toMatchObject({ id: "selection", revisionId: "selection-r1" });
    expect(next.workspace).toMatchObject({ activeStage: "export", plotView: "ensemble" });
  });

  it("migrates an ambiguous v2 default Fit workspace to Data", () => {
    window.sessionStorage.setItem("cmp.modeling.recent-session.v2", JSON.stringify({
      version: 2,
      updatedAt: "2026-07-22T00:00:00Z",
      materialFamily: "metal",
      objective: "Create a card",
      workspace: { activeStage: "fit", selectedDocumentIds: [], selectedStepIndex: 0, selectedStageOrdinal: 0, plotView: "pipeline", settingsOpen: true },
    }));

    expect(loadModelingSession()).toMatchObject({
      version: 3,
      workspace: { activeStage: "data", selectedDocumentIds: [], plotView: "pipeline" },
    });
  });

  it("preserves a persisted v2 Fit stage and view when it contains unambiguous work", () => {
    window.sessionStorage.setItem("cmp.modeling.recent-session.v2", JSON.stringify({
      version: 2,
      updatedAt: "2026-07-22T00:00:00Z",
      materialFamily: "metal",
      objective: "Create a card",
      workspace: { activeStage: "fit", selectedDocumentIds: ["curve-1"], selectedStepIndex: 2, selectedStageOrdinal: 2, plotView: "ensemble", settingsOpen: false },
    }));

    expect(loadModelingSession()).toMatchObject({
      version: 3,
      workspace: { activeStage: "fit", selectedDocumentIds: ["curve-1"], selectedStepIndex: 2, plotView: "ensemble", settingsOpen: false },
    });
  });

  it("preserves a v2 Fit stage with an exact pinned source even when the legacy workspace fields are default", () => {
    window.sessionStorage.setItem("cmp.modeling.recent-session.v2", JSON.stringify({
      version: 2,
      updatedAt: "2026-07-22T00:00:00Z",
      materialFamily: "metal",
      objective: "Create a card",
      testData: ref("curve-1"),
      workspace: { activeStage: "fit", selectedDocumentIds: [], selectedStepIndex: 0, selectedStageOrdinal: 0, plotView: "pipeline", settingsOpen: true },
    }));

    expect(loadModelingSession()).toMatchObject({
      version: 3,
      testData: { id: "curve-1", revisionId: "curve-1-r1" },
      workspace: { activeStage: "fit", selectedDocumentIds: [], plotView: "pipeline" },
    });
  });

  it("preserves a resumed exact stage and plot state independently from the route", () => {
    saveModelingSession({ workspace: { activeStage: "process", selectedDocumentIds: ["curve-1"], selectedStepIndex: 2, selectedStageOrdinal: 3, plotView: "ensemble", settingsOpen: false } });
    expect(loadModelingSession()?.workspace).toMatchObject({ activeStage: "process", selectedDocumentIds: ["curve-1"], plotView: "ensemble", settingsOpen: false });
  });

  it("selects a modeling family from quantity semantics", () => {
    expect(modelingFamilyFromQuantities(["mechanics.strain.engineering", "mechanics.stress.engineering"])).toBe("metal");
    expect(modelingFamilyFromQuantities(["time", "modulus.relaxation"])).toBe("polymer");
    expect(modelingFamilyFromQuantities(["mechanics.stress.planar"])).toBe("elastomer");
  });
});
