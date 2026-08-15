import { beforeEach, describe, expect, it } from "vitest";

import {
  clearModelingSession,
  dispatchModelingSession,
  loadModelingSession,
  reduceModelingSession,
  saveModelingSession,
  type ModelingSessionRecordRef,
} from "./session-controller";

const ref = (id: string): ModelingSessionRecordRef => ({ id, revisionId: `${id}-r1`, label: id, revisionNo: 1 });

function populatedSession() {
  let session = reduceModelingSession(null, { type: "PATCH", patch: {
    material: ref("material"), materialState: ref("state"), testData: ref("test-data"),
    mappingProfile: ref("mapping"), recipe: ref("recipe"), processingOutput: ref("processed"),
    fitCandidate: ref("fit"), selection: ref("selection"), validationPlan: ref("validation-plan"), validation: ref("validation"),
    reviewRelease: ref("review"), materialModelIr: ref("ir"), neutralModel: ref("neutral"), exportArtifact: ref("export"),
  } });
  return session;
}

describe("Modeling session v4 reducer", () => {
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
    expect(next.validationPlan).toBeUndefined();
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
    expect(selection.validationPlan).toBeUndefined();
    expect(selection.validation).toBeUndefined();

    const draftSelection = reduceModelingSession(populatedSession(), { type: "CHANGE_SELECTION" });
    expect(draftSelection.selection).toBeUndefined();
    expect(draftSelection.processingOutput).toMatchObject({ id: "processed" });
    expect(draftSelection.validationPlan).toBeUndefined();
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
    expect(validation.validationPlan).toBeUndefined();
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
    expect(next.validationPlan).toBeUndefined();
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
    expect(next.validationPlan).toBeUndefined();
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

  it("stores multiple exact Test Data revisions and promotes the first remaining focus", () => {
    const first = ref("curve-1");
    const second = ref("curve-2");
    const selected = reduceModelingSession(null, { type: "SET_TEST_DATA_SELECTION", selectedTestDataRefs: [first, second] });
    expect(selected.version).toBe(4);
    expect(selected.workspace.selectedTestDataRefs).toEqual([first, second]);
    expect(selected.testData).toEqual(first);
    const promoted = reduceModelingSession(selected, { type: "SET_TEST_DATA_SELECTION", selectedTestDataRefs: [second] });
    expect(promoted.workspace.selectedDocumentIds).toEqual([second.id]);
    expect(promoted.testData).toEqual(second);
    expect(promoted.invalidation?.reason).toBe("selection");
  });

  it("relinks the same Test Data identity without replacing the stored revision with a current head", () => {
    const first = ref("curve-1");
    const second = { ...first, revisionId: "curve-1-r2", revisionNo: 2 };
    const selected = reduceModelingSession(null, { type: "SET_TEST_DATA_SELECTION", selectedTestDataRefs: [first] });
    const relinked = reduceModelingSession(selected, { type: "PIN_TEST_DATA", testData: second });
    expect(relinked.workspace.selectedTestDataRefs).toEqual([second]);
    expect(relinked.testData).toEqual(second);
  });

  it("keeps every linked exact ref while Include and Show remain independent decisions", () => {
    const first = ref("curve-1");
    const second = ref("curve-2");
    const third = ref("curve-3");
    const selected = reduceModelingSession(null, { type: "SET_TEST_DATA_SELECTION", selectedTestDataRefs: [first, second, third] });
    const includedSubset = reduceModelingSession(selected, {
      type: "PATCH",
      patch: {
        workspace: {
          ...selected.workspace,
          selectedDocumentIds: [first.id, second.id],
          visibleTestDataKeys: [first.id + ":" + first.revisionId, second.id + ":" + second.revisionId, third.id + ":" + third.revisionId],
        },
      },
    });

    expect(includedSubset.workspace.selectedTestDataRefs).toEqual([first, second, third]);
    expect(includedSubset.workspace.selectedDocumentIds).toEqual([first.id, second.id]);
    expect(includedSubset.workspace.visibleTestDataKeys).toEqual([
      `${first.id}:${first.revisionId}`,
      `${second.id}:${second.revisionId}`,
      `${third.id}:${third.revisionId}`,
    ]);
    expect(loadModelingSession()).toBeNull();
    saveModelingSession({ workspace: includedSubset.workspace });
    expect(loadModelingSession()?.workspace).toMatchObject({
      selectedTestDataRefs: [first, second, third],
      selectedDocumentIds: [first.id, second.id],
      visibleTestDataKeys: [
        `${first.id}:${first.revisionId}`,
        `${second.id}:${second.revisionId}`,
        `${third.id}:${third.revisionId}`,
      ],
    });

    const focused = reduceModelingSession(includedSubset, { type: "PIN_TEST_DATA", testData: third });
    expect(focused.workspace.selectedDocumentIds).toEqual([first.id, second.id]);
    expect(focused.workspace.visibleTestDataKeys).toEqual(includedSubset.workspace.visibleTestDataKeys);
  });

  it("keeps the current Process output for a same-focus Include decision", () => {
    const first = ref("curve-1");
    const second = ref("curve-2");
    const output = ref("processed");
    const selected = reduceModelingSession(null, { type: "SET_TEST_DATA_SELECTION", selectedTestDataRefs: [first, second] });
    const session = reduceModelingSession(selected, { type: "PATCH", patch: { mappingProfile: ref("mapping"), processingOutput: output } });
    const next = reduceModelingSession(session, { type: "CHANGE_SELECTION" });

    expect(next.testData).toEqual(first);
    expect(next.workspace.selectedTestDataRefs).toEqual([first, second]);
    expect(next.processingOutput).toEqual(output);
    expect(next.invalidation?.reason).toBe("selection");
  });

  it("clears Process when focus moves to a linked exact row and handles focused removal order", () => {
    const first = ref("curve-1");
    const second = ref("curve-2");
    const selected = reduceModelingSession(null, { type: "SET_TEST_DATA_SELECTION", selectedTestDataRefs: [first, second] });
    const focused = reduceModelingSession({ ...selected, processingOutput: ref("processed") }, { type: "PIN_TEST_DATA", testData: second });
    expect(focused.testData).toEqual(second);
    expect(focused.workspace.selectedTestDataRefs).toEqual([first, second]);
    expect(focused.processingOutput).toBeUndefined();

    const afterPinFirst = reduceModelingSession(focused, { type: "PIN_TEST_DATA", testData: first });
    expect(afterPinFirst.testData).toEqual(first);
    expect(afterPinFirst.workspace.selectedTestDataRefs).toEqual([second, first]);
    expect(afterPinFirst.processingOutput).toBeUndefined();
    const afterSetRemaining = reduceModelingSession(afterPinFirst, { type: "SET_TEST_DATA_SELECTION", selectedTestDataRefs: [first] });
    expect(afterSetRemaining.workspace.selectedTestDataRefs).toEqual([first]);
    expect(afterSetRemaining.workspace.selectedDocumentIds).toEqual([first.id]);

    const emptied = reduceModelingSession(afterSetRemaining, { type: "PIN_TEST_DATA" });
    expect(emptied.testData).toBeUndefined();
    expect(emptied.workspace.selectedTestDataRefs).toEqual([]);
    expect(emptied.workspace.selectedDocumentIds).toEqual([]);
    expect(reduceModelingSession(emptied, { type: "PIN_TEST_DATA" })).toBe(emptied);
    expect(reduceModelingSession(emptied, { type: "SET_TEST_DATA_SELECTION", selectedTestDataRefs: [] })).toBe(emptied);
  });

  it("does not mutate an explicit candidate selection when a route/workspace patch is saved", () => {
    const session = populatedSession();
    const next = reduceModelingSession(session, { type: "PATCH", patch: {
      workspace: { ...session.workspace, activeStage: "export", plotView: "ensemble" },
    } });

    expect(next.selection).toMatchObject({ id: "selection", revisionId: "selection-r1" });
    expect(next.workspace).toMatchObject({ activeStage: "export", plotView: "ensemble" });
  });

  it.each([
    [1, "cmp.modeling.recent-session.v1"],
    [2, "cmp.modeling.recent-session.v2"],
    [3, "cmp.modeling.recent-session.v3"],
    [4, "cmp.modeling.recent-session.v4"],
  ] as const)("restores a v%s session as the unchanged v4 storage contract", (version, storageKey) => {
    window.sessionStorage.setItem(storageKey, JSON.stringify({
      version,
      updatedAt: "2026-07-22T00:00:00Z",
      materialFamily: "metal",
      objective: "Create a card",
      testData: ref("curve-1"),
      workspace: { activeStage: "process", selectedDocumentIds: ["legacy-id"], selectedStepIndex: 1, selectedStageOrdinal: 1, plotView: "ensemble", settingsOpen: false },
    }));

    expect(loadModelingSession()).toMatchObject({
      version: 4,
      testData: { id: "curve-1", revisionId: "curve-1-r1" },
      workspace: {
        activeStage: "process",
        selectedDocumentIds: ["curve-1"],
        selectedTestDataRefs: [ref("curve-1")],
        visibleTestDataKeys: ["curve-1:curve-1-r1"],
        plotView: "ensemble",
      },
    });
    expect(JSON.parse(window.sessionStorage.getItem("cmp.modeling.recent-session.v4") ?? "null")).toMatchObject({
      version: 4,
      workspace: { activeStage: "process" },
    });
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
      version: 4,
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
      version: 4,
      workspace: { activeStage: "fit", selectedDocumentIds: [], selectedTestDataRefs: [], selectedStepIndex: 2, plotView: "ensemble", settingsOpen: false },
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
      version: 4,
      testData: { id: "curve-1", revisionId: "curve-1-r1" },
      workspace: { activeStage: "fit", selectedDocumentIds: ["curve-1"], selectedTestDataRefs: [ref("curve-1")], plotView: "pipeline" },
    });
  });

  it("preserves a resumed exact stage and plot state independently from the route", () => {
    saveModelingSession({ workspace: { activeStage: "process", selectedDocumentIds: ["curve-1"], selectedStepIndex: 2, selectedStageOrdinal: 3, plotView: "ensemble", settingsOpen: false } });
    expect(loadModelingSession()?.workspace).toMatchObject({ activeStage: "process", selectedDocumentIds: [], selectedTestDataRefs: [], plotView: "ensemble", settingsOpen: false });
  });

});
