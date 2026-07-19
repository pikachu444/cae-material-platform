export type ModelingMaterialFamily = "metal" | "polymer" | "elastomer";

export interface ModelingSessionRecordRef {
  id: string;
  revisionId: string;
  label: string;
  revisionNo: number;
}

export interface ModelingSessionSummary {
  version: 1;
  updatedAt: string;
  materialFamily: ModelingMaterialFamily;
  objective: string;
  material?: ModelingSessionRecordRef;
  materialState?: ModelingSessionRecordRef;
  testData?: ModelingSessionRecordRef;
  mappingProfile?: ModelingSessionRecordRef;
  recipe?: ModelingSessionRecordRef;
  lastStage?: string;
}

const STORAGE_KEY = "cmp.modeling.recent-session.v1";

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
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Record<string, unknown>;
    if (value.version !== 1
      || typeof value.updatedAt !== "string"
      || !["metal", "polymer", "elastomer"].includes(String(value.materialFamily))
      || typeof value.objective !== "string") return null;
    for (const key of ["material", "materialState", "testData", "mappingProfile", "recipe"] as const) {
      if (value[key] !== undefined && !isRecordRef(value[key])) return null;
    }
    return value as unknown as ModelingSessionSummary;
  } catch {
    return null;
  }
}

export function saveModelingSession(
  patch: Partial<Omit<ModelingSessionSummary, "version" | "updatedAt">>,
): ModelingSessionSummary {
  const current = loadModelingSession();
  const next: ModelingSessionSummary = {
    version: 1,
    updatedAt: new Date().toISOString(),
    materialFamily: patch.materialFamily ?? current?.materialFamily ?? "metal",
    objective: patch.objective ?? current?.objective ?? "Create a simulation-ready material card",
    material: patch.material ?? current?.material,
    materialState: patch.materialState ?? current?.materialState,
    testData: patch.testData ?? current?.testData,
    mappingProfile: patch.mappingProfile ?? current?.mappingProfile,
    recipe: patch.recipe ?? current?.recipe,
    lastStage: patch.lastStage ?? current?.lastStage,
  };
  if (typeof window !== "undefined") window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return next;
}

export function clearModelingSession(): void {
  if (typeof window !== "undefined") window.sessionStorage.removeItem(STORAGE_KEY);
}

export function modelingFamilyFromQuantities(quantities: string[]): ModelingMaterialFamily {
  if (quantities.some((quantity) => quantity.includes("relaxation") || quantity.includes("storage_modulus") || quantity === "time")) return "polymer";
  if (quantities.some((quantity) => quantity.includes("planar") || quantity.includes("biaxial") || quantity.includes("shear"))) return "elastomer";
  return "metal";
}
