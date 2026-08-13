import type { DataClassification } from "./types";

export type ModelingMaterialFamily = "metal" | "polymer" | "elastomer";
export type ModelingStage = "data" | "process" | "fit" | "validate" | "review" | "export";
export type ModelingPlotView = "pipeline" | "ensemble";

export interface ModelingWorkspaceState {
  activeStage: ModelingStage;
  /** Legacy id-only selection retained for callers still being migrated. New writes use refs. */
  selectedDocumentIds: string[];
  /** Exact Test Data revisions included in the Data decision. */
  selectedTestDataRefs?: ModelingSessionRecordRef[];
  /** Exact Test Data keys currently shown on the graph. */
  visibleTestDataKeys?: string[];
  selectedStepIndex: number;
  selectedStageOrdinal: number;
  plotView: ModelingPlotView;
  settingsOpen: boolean;
}

export interface ModelingSessionRecordRef {
  id: string;
  revisionId: string;
  label: string;
  revisionNo: number;
  /** Optional server evidence carried when a review-capable surface loaded the revision. */
  manifestSha256?: string;
  classification?: DataClassification;
  lifecycleState?: "draft" | "published";
}

export function modelingSessionRecordKey(id: string, revisionId: string): string {
  return `${id}:${revisionId}`;
}

export function modelingSessionRefFromRecord(item: {
  test_data_document_id: string;
  document_key: string;
  current_revision: { id: string; revision_no: number };
}): ModelingSessionRecordRef {
  return {
    id: item.test_data_document_id,
    revisionId: item.current_revision.id,
    label: item.document_key,
    revisionNo: item.current_revision.revision_no,
  };
}

export function modelingDocumentMatchesMaterialContext(
  item: {
    governed_source?: {
      material: { aggregate_id: string; revision_id: string };
      material_state: { aggregate_id: string; revision_id: string };
    } | null;
  },
  material?: { material_id: string; current_revision: { id: string } },
  materialState?: { material_state_id: string; current_revision: { id: string } },
  hasGovernedDocuments = false,
): boolean {
  if (!hasGovernedDocuments) return true;
  const source = item.governed_source;
  return Boolean(
    source
      && material
      && materialState
      && source.material.aggregate_id === material.material_id
      && source.material.revision_id === material.current_revision.id
      && source.material_state.aggregate_id === materialState.material_state_id
      && source.material_state.revision_id === materialState.current_revision.id,
  );
}

/**
 * Data-stage candidates may be recorded against an earlier revision of the
 * same Material/State.  The aggregate identity is the deliberate relinking
 * boundary; revision differences are shown to the engineer rather than used
 * to hide the test source.  Later Process/Fit consumers keep using the
 * revision-strict matcher above.
 */
export function modelingDataDocumentMatchesMaterialContext(
  item: {
    governed_source?: {
      material: { aggregate_id: string; revision_id: string };
      material_state: { aggregate_id: string; revision_id: string };
    } | null;
  },
  material?: { material_id: string; current_revision: { id: string } },
  materialState?: { material_state_id: string; current_revision: { id: string } },
): boolean {
  const source = item.governed_source;
  return Boolean(
    source
      && material
      && materialState
      && source.material.aggregate_id === material.material_id
      && source.material_state.aggregate_id === materialState.material_state_id,
  );
}

export type ModelingPointerKey =
  | "testData"
  | "mappingProfile"
  | "recipe"
  | "processingOutput"
  | "fitCandidate"
  | "selection"
  | "validationPlan"
  | "validation"
  | "reviewRelease"
  | "materialModelIr"
  | "neutralModel"
  | "exportArtifact";

export type ModelingPointerDisposition = "current" | "clear" | "stale" | "regenerate";
export type ModelingInvalidationReason =
  | "material-revision"
  | "material-state"
  | "physical-family"
  | "test-data"
  | "mapping-profile"
  | "process"
  | "fit"
  | "selection"
  | "validation-target"
  | "target-profile";

export interface ModelingInvalidationState {
  reason: ModelingInvalidationReason;
  dispositions: Partial<Record<ModelingPointerKey, ModelingPointerDisposition>>;
  at: string;
}

export interface ModelingSessionSummary {
  /** v4 adds exact multi-Test-Data references to the workspace. */
  version: 3 | 4;
  updatedAt: string;
  materialFamily: ModelingMaterialFamily;
  objective: string;
  /** Explicit New session stays pin-free until the user chooses a Material context. */
  contextSelectionRequired?: boolean;
  material?: ModelingSessionRecordRef;
  materialState?: ModelingSessionRecordRef;
  testData?: ModelingSessionRecordRef;
  mappingProfile?: ModelingSessionRecordRef;
  recipe?: ModelingSessionRecordRef;
  processingOutput?: ModelingSessionRecordRef;
  fitCandidate?: ModelingSessionRecordRef;
  selection?: ModelingSessionRecordRef;
  validationPlan?: ModelingSessionRecordRef;
  validation?: ModelingSessionRecordRef;
  reviewRelease?: ModelingSessionRecordRef;
  materialModelIr?: ModelingSessionRecordRef;
  neutralModel?: ModelingSessionRecordRef;
  exportArtifact?: ModelingSessionRecordRef;
  /** Historical pointers are evidence only; they are never current-action fallbacks. */
  stalePointers?: Partial<Record<ModelingPointerKey, ModelingSessionRecordRef>>;
  invalidation?: ModelingInvalidationState;
  lastStage?: string;
  workspace: ModelingWorkspaceState;
}

export type ModelingSessionPatch = Partial<Omit<ModelingSessionSummary, "version" | "updatedAt">>;
export type ModelingSessionEvent =
  | { type: "NEW_SESSION"; materialFamily?: ModelingMaterialFamily; objective?: string }
  | { type: "CHANGE_MATERIAL"; material?: ModelingSessionRecordRef }
  | { type: "CHANGE_MATERIAL_STATE"; materialState?: ModelingSessionRecordRef }
  | { type: "CHANGE_FAMILY"; materialFamily: ModelingMaterialFamily }
  | { type: "PIN_TEST_DATA"; testData?: ModelingSessionRecordRef }
  | { type: "SET_TEST_DATA_SELECTION"; selectedTestDataRefs: ModelingSessionRecordRef[] }
  | { type: "CHANGE_MAPPING"; mappingProfile?: ModelingSessionRecordRef }
  | { type: "CHANGE_PROCESS"; recipe?: ModelingSessionRecordRef }
  | { type: "CHANGE_FIT" }
  | { type: "CHANGE_SELECTION" }
  | { type: "SELECT_CANDIDATE"; selection?: ModelingSessionRecordRef }
  | { type: "CHANGE_VALIDATION_TARGET" }
  | { type: "CHANGE_TARGET_PROFILE" }
  | { type: "CHANGE_EXPORT_TARGET" }
  | { type: "SET_CURRENT"; key: ModelingPointerKey; value?: ModelingSessionRecordRef }
  | { type: "PATCH"; patch: ModelingSessionPatch };

const STORAGE_KEY = "cmp.modeling.recent-session.v4";
const V3_STORAGE_KEY = "cmp.modeling.recent-session.v3";
const V2_STORAGE_KEY = "cmp.modeling.recent-session.v2";
const LEGACY_STORAGE_KEY = "cmp.modeling.recent-session.v1";
const CONTEXT_SELECTION_REQUIRED_KEY = "cmp.modeling.context-selection-required.v4";
const LEGACY_CONTEXT_SELECTION_REQUIRED_KEY = "cmp.modeling.context-selection-required.v3";

const DEFAULT_WORKSPACE: ModelingWorkspaceState = {
  activeStage: "data",
  selectedDocumentIds: [],
  selectedTestDataRefs: [],
  visibleTestDataKeys: [],
  selectedStepIndex: 0,
  selectedStageOrdinal: 0,
  plotView: "pipeline",
  settingsOpen: typeof window === "undefined" || window.innerWidth >= 1400,
};

const ALL_POINTERS: ModelingPointerKey[] = [
  "testData", "mappingProfile", "recipe", "processingOutput", "fitCandidate", "selection",
  "validationPlan", "validation", "reviewRelease", "materialModelIr", "neutralModel", "exportArtifact",
];
const DOWNSTREAM_OF_DATA = ALL_POINTERS.filter((key) => key !== "testData");
const DOWNSTREAM_OF_MAPPING = ALL_POINTERS.filter(
  (key) => key !== "testData" && key !== "mappingProfile",
);
const DOWNSTREAM_OF_PROCESS = ["processingOutput", "fitCandidate", "selection", "validationPlan", "validation", "reviewRelease", "materialModelIr", "neutralModel", "exportArtifact"] as const;
const DOWNSTREAM_OF_FIT = ["fitCandidate", "selection", "validationPlan", "validation", "reviewRelease", "materialModelIr", "neutralModel", "exportArtifact"] as const;

function now(): string {
  return new Date().toISOString();
}

function createSession(overrides: Partial<Pick<ModelingSessionSummary, "materialFamily" | "objective">> = {}): ModelingSessionSummary {
  return {
    version: 4,
    updatedAt: now(),
    materialFamily: overrides.materialFamily ?? "metal",
    objective: overrides.objective ?? "Create a simulation-ready material card",
    workspace: { ...DEFAULT_WORKSPACE },
  };
}

function isRecordRef(value: unknown): value is ModelingSessionRecordRef {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.id === "string"
    && typeof candidate.revisionId === "string"
    && typeof candidate.label === "string"
    && typeof candidate.revisionNo === "number";
}

function sameRef(left?: ModelingSessionRecordRef, right?: ModelingSessionRecordRef): boolean {
  return left?.id === right?.id && left?.revisionId === right?.revisionId;
}

function sameRefList(left: ModelingSessionRecordRef[] = [], right: ModelingSessionRecordRef[] = []): boolean {
  return left.length === right.length && left.every((item, index) => sameRef(item, right[index]));
}

function exactRefs(value: ModelingSessionRecordRef[] | undefined): ModelingSessionRecordRef[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  return value.filter((item) => {
    if (!isRecordRef(item)) return false;
    const key = `${item.id}:${item.revisionId}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function withInvalidation(
  session: ModelingSessionSummary,
  reason: ModelingInvalidationReason,
  entries: Partial<Record<ModelingPointerKey, ModelingPointerDisposition>>,
): ModelingSessionSummary {
  const dispositions = { ...entries };
  const stalePointers = { ...session.stalePointers };
  const next: ModelingSessionSummary = { ...session, updatedAt: now(), stalePointers, invalidation: { reason, dispositions, at: now() } };
  for (const [key, requestedDisposition] of Object.entries(dispositions) as Array<[ModelingPointerKey, ModelingPointerDisposition]>) {
    const disposition = requestedDisposition === "stale" && !session[key] ? "clear" : requestedDisposition;
    dispositions[key] = disposition;
    if (disposition === "stale" && session[key]) stalePointers[key] = session[key];
    if (disposition !== "current") delete next[key];
  }
  if (!Object.keys(stalePointers).length) delete next.stalePointers;
  return next;
}

function clearEntries(keys: readonly ModelingPointerKey[], reviewIsStale = true): Partial<Record<ModelingPointerKey, ModelingPointerDisposition>> {
  const entries: Partial<Record<ModelingPointerKey, ModelingPointerDisposition>> = {};
  for (const key of keys) entries[key] = key === "reviewRelease" && reviewIsStale ? "stale" : "clear";
  return entries;
}

export function reduceModelingSession(session: ModelingSessionSummary | null, event: ModelingSessionEvent): ModelingSessionSummary {
  const current = session ?? createSession();
  switch (event.type) {
    case "NEW_SESSION":
      return { ...createSession(event), contextSelectionRequired: true };
    case "CHANGE_MATERIAL":
      if (sameRef(current.material, event.material)) return current;
      return withInvalidation({
        ...current,
        material: event.material,
        workspace: { ...current.workspace, selectedDocumentIds: [], selectedTestDataRefs: [], visibleTestDataKeys: [] },
      }, "material-revision", clearEntries(ALL_POINTERS));
    case "CHANGE_MATERIAL_STATE":
      if (sameRef(current.materialState, event.materialState)) return current;
      return withInvalidation({
        ...current,
        materialState: event.materialState,
        workspace: { ...current.workspace, selectedDocumentIds: [], selectedTestDataRefs: [], visibleTestDataKeys: [] },
      }, "material-state", clearEntries(ALL_POINTERS));
    case "CHANGE_FAMILY":
      if (current.materialFamily === event.materialFamily) return current;
      return withInvalidation({
        ...current,
        materialFamily: event.materialFamily,
        workspace: { ...current.workspace, selectedDocumentIds: [], selectedTestDataRefs: [], visibleTestDataKeys: [] },
      }, "physical-family", clearEntries(ALL_POINTERS));
    case "PIN_TEST_DATA":
      if (sameRef(current.testData, event.testData)
        && (!event.testData || (current.workspace.selectedTestDataRefs ?? []).some((item) => sameRef(item, event.testData)))) return current;
      {
        const previousRefs = current.workspace.selectedTestDataRefs ?? [];
        const nextTestData = event.testData;
        const wasLinked = Boolean(nextTestData && previousRefs.some((item) => item.id === nextTestData.id));
        const nextRefs = nextTestData
          ? [...previousRefs.filter((item) => item.id !== nextTestData.id), nextTestData]
          : [];
        const previousIncluded = current.workspace.selectedDocumentIds ?? [];
        const nextIncluded = nextTestData
          ? [...previousIncluded.filter((id) => nextRefs.some((item) => item.id === id)), ...(wasLinked ? [] : [nextTestData.id])]
            .filter((id, index, ids) => ids.indexOf(id) === index)
          : [];
        const previousVisible = current.workspace.visibleTestDataKeys ?? previousRefs.map((item) => exactRefKey(item));
        const previousRef = nextTestData ? previousRefs.find((item) => item.id === nextTestData.id) : undefined;
        const shouldRemainVisible = !wasLinked || Boolean(previousRef && previousVisible.includes(exactRefKey(previousRef)));
        const nextVisible = nextTestData
          ? [...previousVisible.filter((key) => nextRefs.some((item) => exactRefKey(item) === key)), ...(shouldRemainVisible ? [exactRefKey(nextTestData)] : [])]
            .filter((key, index, keys) => keys.indexOf(key) === index)
          : [];
        return withInvalidation({
        ...current,
        testData: event.testData,
        workspace: {
          ...current.workspace,
          selectedTestDataRefs: nextRefs,
          selectedDocumentIds: nextIncluded,
          visibleTestDataKeys: nextVisible,
        },
        }, "test-data", clearEntries(DOWNSTREAM_OF_DATA));
      }
    case "SET_TEST_DATA_SELECTION": {
      const selectedTestDataRefs = exactRefs(event.selectedTestDataRefs);
      const focused = selectedTestDataRefs.find((item) => sameRef(item, current.testData))
        ?? selectedTestDataRefs[0];
      const previousRefs = current.workspace.selectedTestDataRefs ?? [];
      const previousIncluded = current.workspace.selectedDocumentIds ?? [];
      const previousVisible = current.workspace.visibleTestDataKeys ?? previousRefs.map((item) => exactRefKey(item));
      const previousRefKeys = new Set(previousRefs.map(exactRefKey));
      const selectedDocumentIds = [
        ...previousIncluded.filter((id) => selectedTestDataRefs.some((item) => item.id === id)),
        ...selectedTestDataRefs
          .filter((item) => !previousRefKeys.has(exactRefKey(item)))
          .map((item) => item.id),
      ].filter((id, index, ids) => ids.indexOf(id) === index);
      const visibleTestDataKeys = [
        ...previousVisible.filter((key) => selectedTestDataRefs.some((item) => exactRefKey(item) === key)),
        ...selectedTestDataRefs
          .filter((item) => !previousRefKeys.has(exactRefKey(item)))
          .map(exactRefKey),
      ].filter((key, index, keys) => keys.indexOf(key) === index);
      const workspace = {
        ...current.workspace,
        selectedTestDataRefs,
        // Keep this field for older activity consumers; it is never used to resolve revisions.
        selectedDocumentIds,
        visibleTestDataKeys,
      };
      if (sameRefList(current.workspace.selectedTestDataRefs ?? [], selectedTestDataRefs)
        && sameRef(current.testData, focused)) return current;
      return reduceModelingSession(
        { ...current, workspace, testData: focused },
        { type: "CHANGE_SELECTION" },
      );
    }
    case "CHANGE_MAPPING":
      if (sameRef(current.mappingProfile, event.mappingProfile)) return current;
      return withInvalidation({ ...current, mappingProfile: event.mappingProfile }, "mapping-profile", clearEntries(DOWNSTREAM_OF_MAPPING));
    case "CHANGE_PROCESS":
      // A draft edit has no immutable Recipe ref to compare. It still changes
      // the executed process and must never leave its old output chain current.
      if (event.recipe !== undefined && sameRef(current.recipe, event.recipe)) return current;
      return withInvalidation(
        event.recipe === undefined ? current : { ...current, recipe: event.recipe },
        "process",
        clearEntries(DOWNSTREAM_OF_PROCESS),
      );
    case "CHANGE_FIT":
      return withInvalidation(current, "fit", clearEntries(DOWNSTREAM_OF_FIT));
    case "CHANGE_SELECTION": {
      const keys: ModelingPointerKey[] = [
        "selection",
        "validationPlan",
        "validation",
        "reviewRelease",
        "materialModelIr",
        "neutralModel",
        "exportArtifact",
      ];
      if (sameRef(current.selection, current.processingOutput)) {
        keys.unshift("processingOutput");
      }
      return withInvalidation(
        current,
        "selection",
        clearEntries(keys),
      );
    }
    case "SELECT_CANDIDATE":
      if (sameRef(current.selection, event.selection)) return current;
      return withInvalidation({ ...current, selection: event.selection }, "selection", clearEntries(["validationPlan", "validation", "reviewRelease", "materialModelIr", "neutralModel", "exportArtifact"]));
    case "CHANGE_VALIDATION_TARGET":
      return withInvalidation(current, "validation-target", {
        validationPlan: "clear", validation: "clear", reviewRelease: "stale", exportArtifact: "clear",
      });
    case "CHANGE_TARGET_PROFILE":
      return withInvalidation(current, "target-profile", {
        validation: "stale", materialModelIr: "regenerate", neutralModel: "regenerate", exportArtifact: "regenerate",
      });
    case "CHANGE_EXPORT_TARGET":
      // A target tuple changes only the ephemeral preview/delivery candidate;
      // it never invalidates the exact source IR or Neutral revision.
      return withInvalidation(current, "target-profile", { exportArtifact: "clear" });
    case "SET_CURRENT": {
      const next = { ...current, updatedAt: now(), invalidation: undefined };
      if (event.value) next[event.key] = event.value;
      else delete next[event.key];
      return next;
    }
    case "PATCH":
      return reducePatch(current, event.patch);
  }
}

function reducePatch(current: ModelingSessionSummary, patch: ModelingSessionPatch): ModelingSessionSummary {
  let next = current;
  if (patch.materialFamily !== undefined) next = reduceModelingSession(next, { type: "CHANGE_FAMILY", materialFamily: patch.materialFamily });
  if (patch.material !== undefined) next = reduceModelingSession(next, { type: "CHANGE_MATERIAL", material: patch.material });
  if (patch.materialState !== undefined) next = reduceModelingSession(next, { type: "CHANGE_MATERIAL_STATE", materialState: patch.materialState });
  if (patch.testData !== undefined) next = reduceModelingSession(next, { type: "PIN_TEST_DATA", testData: patch.testData });
  if (patch.mappingProfile !== undefined) next = reduceModelingSession(next, { type: "CHANGE_MAPPING", mappingProfile: patch.mappingProfile });
  if (patch.recipe !== undefined) next = reduceModelingSession(next, { type: "CHANGE_PROCESS", recipe: patch.recipe });
  for (const key of ALL_POINTERS) {
    if (["testData", "mappingProfile", "recipe"].includes(key) || patch[key] === undefined) continue;
    next = reduceModelingSession(next, { type: "SET_CURRENT", key, value: patch[key] });
  }
  return {
    ...next,
    objective: patch.objective ?? next.objective,
    contextSelectionRequired: patch.contextSelectionRequired ?? next.contextSelectionRequired,
    lastStage: patch.lastStage ?? next.lastStage,
    workspace: patch.workspace ? normalizeWorkspace({ ...next.workspace, ...patch.workspace }) : next.workspace,
    updatedAt: now(),
  };
}

function migrate(value: Record<string, unknown>): ModelingSessionSummary | null {
  if (![1, 2, 3, 4].includes(Number(value.version))
    || typeof value.updatedAt !== "string"
    || !["metal", "polymer", "elastomer"].includes(String(value.materialFamily))
    || typeof value.objective !== "string"
    || (value.contextSelectionRequired !== undefined && typeof value.contextSelectionRequired !== "boolean")) return null;
  for (const key of ALL_POINTERS) if (value[key] !== undefined && !isRecordRef(value[key])) return null;
  if (value.stalePointers !== undefined) {
    if (!value.stalePointers || typeof value.stalePointers !== "object") return null;
    for (const key of ALL_POINTERS) {
      const stale = (value.stalePointers as Record<string, unknown>)[key];
      if (stale !== undefined && !isRecordRef(stale)) return null;
    }
  }
  const workspace = isWorkspaceState(value.workspace)
    ? value.workspace
    : { ...DEFAULT_WORKSPACE, selectedStageOrdinal: legacyStageOrdinal(value.lastStage) };
  const activeStage = Number(value.version) < 3 && isAmbiguousLegacyFitWorkspace(value, workspace)
    ? "data"
    : workspace.activeStage;
  const persistedRefs = Array.isArray((workspace as Partial<ModelingWorkspaceState>).selectedTestDataRefs)
    ? exactRefs((workspace as Partial<ModelingWorkspaceState>).selectedTestDataRefs)
    : isRecordRef(value.testData) ? [value.testData] : [];
  const hasPersistedExactRefs = Array.isArray((workspace as Partial<ModelingWorkspaceState>).selectedTestDataRefs);
  const migratedIncludedIds = hasPersistedExactRefs
    ? normalizeIncludedIds(workspace.selectedDocumentIds, persistedRefs)
    : persistedRefs.length
      ? persistedRefs.map((item) => item.id)
      : [];
  return {
    ...value,
    version: 4,
    workspace: {
      ...normalizeWorkspace(workspace),
      activeStage,
      selectedTestDataRefs: persistedRefs,
      // Id-only legacy entries are intentionally discarded; no current head guessing.
      selectedDocumentIds: migratedIncludedIds,
      visibleTestDataKeys: normalizeVisibleKeys(workspace.visibleTestDataKeys, persistedRefs),
    },
  } as ModelingSessionSummary;
}

function normalizeWorkspace(value: ModelingWorkspaceState): ModelingWorkspaceState {
  const refs = exactRefs(value.selectedTestDataRefs);
  return {
    ...value,
    selectedTestDataRefs: refs,
    selectedDocumentIds: normalizeIncludedIds(value.selectedDocumentIds, refs),
    visibleTestDataKeys: normalizeVisibleKeys(value.visibleTestDataKeys, refs),
  };
}

function normalizeIncludedIds(value: string[] | undefined, refs: ModelingSessionRecordRef[]): string[] {
  const candidates = Array.isArray(value) ? value : refs.map((item) => item.id);
  const allowed = new Set(refs.map((item) => item.id));
  return candidates.filter((id, index) => allowed.has(id) && candidates.indexOf(id) === index);
}

function exactRefKey(ref: Pick<ModelingSessionRecordRef, "id" | "revisionId">): string {
  return modelingSessionRecordKey(ref.id, ref.revisionId);
}

function normalizeVisibleKeys(value: string[] | undefined, refs: ModelingSessionRecordRef[]): string[] {
  const candidates = Array.isArray(value) ? value : refs.map(exactRefKey);
  const allowed = new Set(refs.map(exactRefKey));
  return candidates.filter((key, index) => allowed.has(key) && candidates.indexOf(key) === index);
}

function isAmbiguousLegacyFitWorkspace(
  value: Record<string, unknown>,
  workspace: ModelingWorkspaceState,
): boolean {
  return workspace.activeStage === "fit"
    && ALL_POINTERS.every((key) => value[key] === undefined)
    && (workspace.selectedTestDataRefs ?? []).length === 0
    && (workspace.selectedDocumentIds ?? []).length === 0
    && workspace.selectedStepIndex === 0
    && workspace.selectedStageOrdinal === 0
    && workspace.plotView === "pipeline";
}

export function loadModelingSession(): ModelingSessionSummary | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY)
      ?? window.sessionStorage.getItem(V3_STORAGE_KEY)
      ?? window.sessionStorage.getItem(V2_STORAGE_KEY)
      ?? window.sessionStorage.getItem(LEGACY_STORAGE_KEY);
    if (!raw) return null;
    const migrated = migrate(JSON.parse(raw) as Record<string, unknown>);
    if (migrated && window.sessionStorage.getItem(STORAGE_KEY) !== raw) {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(migrated));
    }
    return migrated && (window.sessionStorage.getItem(CONTEXT_SELECTION_REQUIRED_KEY) === "1"
      || window.sessionStorage.getItem(LEGACY_CONTEXT_SELECTION_REQUIRED_KEY) === "1")
      ? { ...migrated, contextSelectionRequired: true }
      : migrated;
  } catch {
    return null;
  }
}

export function dispatchModelingSession(event: ModelingSessionEvent): ModelingSessionSummary {
  if (typeof window !== "undefined" && event.type === "NEW_SESSION") {
    window.sessionStorage.setItem(CONTEXT_SELECTION_REQUIRED_KEY, "1");
  }
  const next = reduceModelingSession(loadModelingSession(), event);
  if (typeof window !== "undefined") {
    if (next.contextSelectionRequired === false) {
      window.sessionStorage.removeItem(CONTEXT_SELECTION_REQUIRED_KEY);
    }
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }
  return next;
}

// Compatibility adapter for callers being migrated to explicit events. Passing `undefined` keeps
// a pointer; clearing is deliberately done through SET_CURRENT or a context-change event.
export function saveModelingSession(patch: ModelingSessionPatch): ModelingSessionSummary {
  return dispatchModelingSession({ type: "PATCH", patch });
}

export function clearModelingSession(): void {
  if (typeof window !== "undefined") {
    window.sessionStorage.removeItem(STORAGE_KEY);
    window.sessionStorage.removeItem(V3_STORAGE_KEY);
    window.sessionStorage.removeItem(V2_STORAGE_KEY);
    window.sessionStorage.removeItem(LEGACY_STORAGE_KEY);
    window.sessionStorage.removeItem(CONTEXT_SELECTION_REQUIRED_KEY);
    window.sessionStorage.removeItem(LEGACY_CONTEXT_SELECTION_REQUIRED_KEY);
  }
}

function legacyStageOrdinal(lastStage: unknown): number {
  return typeof lastStage === "string" && lastStage.length > 0 ? 1 : 0;
}

function isWorkspaceState(value: unknown): value is ModelingWorkspaceState {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return ["data", "process", "fit", "validate", "review", "export"].includes(String(candidate.activeStage))
    && (candidate.selectedDocumentIds === undefined
      || (Array.isArray(candidate.selectedDocumentIds)
        && candidate.selectedDocumentIds.every((item) => typeof item === "string")))
    && (candidate.selectedTestDataRefs === undefined || exactRefs(candidate.selectedTestDataRefs as ModelingSessionRecordRef[]).length === (candidate.selectedTestDataRefs as unknown[]).length)
    && (candidate.visibleTestDataKeys === undefined || (Array.isArray(candidate.visibleTestDataKeys) && candidate.visibleTestDataKeys.every((item) => typeof item === "string")))
    && Number.isInteger(candidate.selectedStepIndex)
    && Number(candidate.selectedStepIndex) >= 0
    && Number.isInteger(candidate.selectedStageOrdinal)
    && Number(candidate.selectedStageOrdinal) >= 0
    && ["pipeline", "ensemble"].includes(String(candidate.plotView))
    && typeof candidate.settingsOpen === "boolean";
}

export function modelingFamilyFromQuantities(quantities: string[]): ModelingMaterialFamily {
  if (quantities.some((quantity) => quantity.includes("relaxation")
    || quantity.includes("storage_modulus")
    || quantity.includes("modulus.storage")
    || quantity.includes("frequency.cyclic")
    || quantity === "time")) return "polymer";
  if (quantities.some((quantity) => quantity.includes("planar") || quantity.includes("biaxial") || quantity.includes("shear"))) return "elastomer";
  return "metal";
}
