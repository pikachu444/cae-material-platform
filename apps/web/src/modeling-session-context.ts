export type ModelingMaterialFamily = "metal" | "polymer" | "elastomer";
export type ModelingStage = "data" | "process" | "fit" | "validate" | "review" | "export";
export type ModelingPlotView = "pipeline" | "ensemble";

export interface ModelingWorkspaceState {
  activeStage: ModelingStage;
  selectedDocumentIds: string[];
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
}

export type ModelingPointerKey =
  | "testData"
  | "mappingProfile"
  | "recipe"
  | "processingOutput"
  | "fitCandidate"
  | "selection"
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
  version: 3;
  updatedAt: string;
  materialFamily: ModelingMaterialFamily;
  objective: string;
  material?: ModelingSessionRecordRef;
  materialState?: ModelingSessionRecordRef;
  testData?: ModelingSessionRecordRef;
  mappingProfile?: ModelingSessionRecordRef;
  recipe?: ModelingSessionRecordRef;
  processingOutput?: ModelingSessionRecordRef;
  fitCandidate?: ModelingSessionRecordRef;
  selection?: ModelingSessionRecordRef;
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
  | { type: "CHANGE_MAPPING"; mappingProfile?: ModelingSessionRecordRef }
  | { type: "CHANGE_PROCESS"; recipe?: ModelingSessionRecordRef }
  | { type: "CHANGE_FIT" }
  | { type: "SELECT_CANDIDATE"; selection?: ModelingSessionRecordRef }
  | { type: "CHANGE_VALIDATION_TARGET" }
  | { type: "CHANGE_TARGET_PROFILE" }
  | { type: "SET_CURRENT"; key: ModelingPointerKey; value?: ModelingSessionRecordRef }
  | { type: "PATCH"; patch: ModelingSessionPatch };

const STORAGE_KEY = "cmp.modeling.recent-session.v3";
const V2_STORAGE_KEY = "cmp.modeling.recent-session.v2";
const LEGACY_STORAGE_KEY = "cmp.modeling.recent-session.v1";

const DEFAULT_WORKSPACE: ModelingWorkspaceState = {
  activeStage: "data",
  selectedDocumentIds: [],
  selectedStepIndex: 0,
  selectedStageOrdinal: 0,
  plotView: "pipeline",
  settingsOpen: typeof window === "undefined" || window.innerWidth >= 1400,
};

const ALL_POINTERS: ModelingPointerKey[] = [
  "testData", "mappingProfile", "recipe", "processingOutput", "fitCandidate", "selection",
  "validation", "reviewRelease", "materialModelIr", "neutralModel", "exportArtifact",
];
const DOWNSTREAM_OF_DATA = ALL_POINTERS.filter((key) => key !== "testData");
const DOWNSTREAM_OF_MAPPING = ALL_POINTERS.filter(
  (key) => key !== "testData" && key !== "mappingProfile",
);
const DOWNSTREAM_OF_PROCESS = ["processingOutput", "fitCandidate", "selection", "validation", "materialModelIr", "neutralModel", "exportArtifact"] as const;
const DOWNSTREAM_OF_FIT = ["fitCandidate", "selection", "validation", "materialModelIr", "neutralModel", "exportArtifact"] as const;

function now(): string {
  return new Date().toISOString();
}

function createSession(overrides: Partial<Pick<ModelingSessionSummary, "materialFamily" | "objective">> = {}): ModelingSessionSummary {
  return {
    version: 3,
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
      return createSession(event);
    case "CHANGE_MATERIAL":
      if (sameRef(current.material, event.material)) return current;
      return withInvalidation({ ...current, material: event.material }, "material-revision", clearEntries(ALL_POINTERS));
    case "CHANGE_MATERIAL_STATE":
      if (sameRef(current.materialState, event.materialState)) return current;
      return withInvalidation({ ...current, materialState: event.materialState }, "material-state", clearEntries(ALL_POINTERS));
    case "CHANGE_FAMILY":
      if (current.materialFamily === event.materialFamily) return current;
      return withInvalidation({ ...current, materialFamily: event.materialFamily }, "physical-family", clearEntries(ALL_POINTERS));
    case "PIN_TEST_DATA":
      if (sameRef(current.testData, event.testData)) return current;
      return withInvalidation({ ...current, testData: event.testData }, "test-data", clearEntries(DOWNSTREAM_OF_DATA));
    case "CHANGE_MAPPING":
      if (sameRef(current.mappingProfile, event.mappingProfile)) return current;
      return withInvalidation({ ...current, mappingProfile: event.mappingProfile }, "mapping-profile", clearEntries(DOWNSTREAM_OF_MAPPING));
    case "CHANGE_PROCESS":
      if (sameRef(current.recipe, event.recipe)) return current;
      return withInvalidation({ ...current, recipe: event.recipe }, "process", clearEntries(DOWNSTREAM_OF_PROCESS));
    case "CHANGE_FIT":
      return withInvalidation(current, "fit", clearEntries(DOWNSTREAM_OF_FIT));
    case "SELECT_CANDIDATE":
      if (sameRef(current.selection, event.selection)) return current;
      return withInvalidation({ ...current, selection: event.selection }, "selection", clearEntries(["validation", "reviewRelease", "materialModelIr", "neutralModel", "exportArtifact"]));
    case "CHANGE_VALIDATION_TARGET":
      return withInvalidation(current, "validation-target", {
        validation: "clear", reviewRelease: "stale", exportArtifact: "clear",
      });
    case "CHANGE_TARGET_PROFILE":
      return withInvalidation(current, "target-profile", {
        validation: "stale", materialModelIr: "regenerate", neutralModel: "regenerate", exportArtifact: "regenerate",
      });
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
    lastStage: patch.lastStage ?? next.lastStage,
    workspace: patch.workspace ?? next.workspace,
    updatedAt: now(),
  };
}

function migrate(value: Record<string, unknown>): ModelingSessionSummary | null {
  if (![1, 2, 3].includes(Number(value.version))
    || typeof value.updatedAt !== "string"
    || !["metal", "polymer", "elastomer"].includes(String(value.materialFamily))
    || typeof value.objective !== "string") return null;
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
  return { ...value, version: 3, workspace: { ...workspace, activeStage } } as ModelingSessionSummary;
}

function isAmbiguousLegacyFitWorkspace(
  value: Record<string, unknown>,
  workspace: ModelingWorkspaceState,
): boolean {
  return workspace.activeStage === "fit"
    && ALL_POINTERS.every((key) => value[key] === undefined)
    && workspace.selectedDocumentIds.length === 0
    && workspace.selectedStepIndex === 0
    && workspace.selectedStageOrdinal === 0
    && workspace.plotView === "pipeline";
}

export function loadModelingSession(): ModelingSessionSummary | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY)
      ?? window.sessionStorage.getItem(V2_STORAGE_KEY)
      ?? window.sessionStorage.getItem(LEGACY_STORAGE_KEY);
    if (!raw) return null;
    const migrated = migrate(JSON.parse(raw) as Record<string, unknown>);
    if (migrated && window.sessionStorage.getItem(STORAGE_KEY) !== raw) {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(migrated));
    }
    return migrated;
  } catch {
    return null;
  }
}

export function dispatchModelingSession(event: ModelingSessionEvent): ModelingSessionSummary {
  const next = reduceModelingSession(loadModelingSession(), event);
  if (typeof window !== "undefined") window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
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
    window.sessionStorage.removeItem(V2_STORAGE_KEY);
    window.sessionStorage.removeItem(LEGACY_STORAGE_KEY);
  }
}

function legacyStageOrdinal(lastStage: unknown): number {
  return typeof lastStage === "string" && lastStage.length > 0 ? 1 : 0;
}

function isWorkspaceState(value: unknown): value is ModelingWorkspaceState {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return ["data", "process", "fit", "validate", "review", "export"].includes(String(candidate.activeStage))
    && Array.isArray(candidate.selectedDocumentIds)
    && candidate.selectedDocumentIds.every((item) => typeof item === "string")
    && Number.isInteger(candidate.selectedStepIndex)
    && Number(candidate.selectedStepIndex) >= 0
    && Number.isInteger(candidate.selectedStageOrdinal)
    && Number(candidate.selectedStageOrdinal) >= 0
    && ["pipeline", "ensemble"].includes(String(candidate.plotView))
    && typeof candidate.settingsOpen === "boolean";
}

export function modelingFamilyFromQuantities(quantities: string[]): ModelingMaterialFamily {
  if (quantities.some((quantity) => quantity.includes("relaxation") || quantity.includes("storage_modulus") || quantity === "time")) return "polymer";
  if (quantities.some((quantity) => quantity.includes("planar") || quantity.includes("biaxial") || quantity.includes("shear"))) return "elastomer";
  return "metal";
}
