export type ModelingMaterialFamily = "metal" | "polymer" | "elastomer";
export type ModelingStage = "data" | "process" | "fit" | "export";
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

export interface ModelingSessionSummary {
  version: 2;
  updatedAt: string;
  materialFamily: ModelingMaterialFamily;
  objective: string;
  material?: ModelingSessionRecordRef;
  materialState?: ModelingSessionRecordRef;
  testData?: ModelingSessionRecordRef;
  mappingProfile?: ModelingSessionRecordRef;
  recipe?: ModelingSessionRecordRef;
  processingOutput?: ModelingSessionRecordRef;
  lastStage?: string;
  workspace: ModelingWorkspaceState;
}

const STORAGE_KEY = "cmp.modeling.recent-session.v2";
const LEGACY_STORAGE_KEY = "cmp.modeling.recent-session.v1";

const DEFAULT_WORKSPACE: ModelingWorkspaceState = {
  activeStage: "fit",
  selectedDocumentIds: [],
  selectedStepIndex: 0,
  selectedStageOrdinal: 0,
  plotView: "pipeline",
  settingsOpen: typeof window === "undefined" || window.innerWidth >= 1400,
};

function isRecordRef(value: unknown): value is ModelingSessionRecordRef {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.id === "string"
    && typeof candidate.revisionId === "string"
    && typeof candidate.label === "string"
    && typeof candidate.revisionNo === "number";
}

export function loadModelingSession(): ModelingSessionSummary | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY) ?? window.sessionStorage.getItem(LEGACY_STORAGE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Record<string, unknown>;
    if (![1, 2].includes(Number(value.version))
      || typeof value.updatedAt !== "string"
      || !["metal", "polymer", "elastomer"].includes(String(value.materialFamily))
      || typeof value.objective !== "string") return null;
    for (const key of ["material", "materialState", "testData", "mappingProfile", "recipe", "processingOutput"] as const) {
      if (value[key] !== undefined && !isRecordRef(value[key])) return null;
    }
    const workspace = value.version === 2 && isWorkspaceState(value.workspace)
      ? value.workspace
      : { ...DEFAULT_WORKSPACE, selectedStageOrdinal: legacyStageOrdinal(value.lastStage) };
    return { ...value, version: 2, workspace } as unknown as ModelingSessionSummary;
  } catch {
    return null;
  }
}

export function saveModelingSession(
  patch: Partial<Omit<ModelingSessionSummary, "version" | "updatedAt">>,
): ModelingSessionSummary {
  const current = loadModelingSession();
  const next: ModelingSessionSummary = {
    version: 2,
    updatedAt: new Date().toISOString(),
    materialFamily: patch.materialFamily ?? current?.materialFamily ?? "metal",
    objective: patch.objective ?? current?.objective ?? "Create a simulation-ready material card",
    material: patch.material ?? current?.material,
    materialState: patch.materialState ?? current?.materialState,
    testData: patch.testData ?? current?.testData,
    mappingProfile: patch.mappingProfile ?? current?.mappingProfile,
    recipe: patch.recipe ?? current?.recipe,
    processingOutput: patch.processingOutput ?? current?.processingOutput,
    lastStage: patch.lastStage ?? current?.lastStage,
    workspace: patch.workspace ?? current?.workspace ?? DEFAULT_WORKSPACE,
  };
  if (typeof window !== "undefined") window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return next;
}

export function clearModelingSession(): void {
  if (typeof window !== "undefined") {
    window.sessionStorage.removeItem(STORAGE_KEY);
    window.sessionStorage.removeItem(LEGACY_STORAGE_KEY);
  }
}

function legacyStageOrdinal(lastStage: unknown): number {
  return typeof lastStage === "string" && lastStage.length > 0 ? 1 : 0;
}

function isWorkspaceState(value: unknown): value is ModelingWorkspaceState {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Record<string, unknown>;
  return ["data", "process", "fit", "export"].includes(String(candidate.activeStage))
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
