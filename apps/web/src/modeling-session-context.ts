import type {
  ModelingMaterialFamily as ModelingMaterialFamilyType,
} from "./features/modeling/model/session-controller";

// Compatibility surface for existing Modeling consumers. FE-04G moves those
// imports to the feature owner and removes these controller re-exports.
export {
  clearModelingSession,
  dispatchModelingSession,
  loadModelingSession,
  modelingSessionRecordKey,
  modelingSessionRefFromRecord,
  reduceModelingSession,
  saveModelingSession,
} from "./features/modeling/model/session-controller";
export type {
  ModelingInvalidationReason,
  ModelingInvalidationState,
  ModelingMaterialFamily,
  ModelingPlotView,
  ModelingPointerDisposition,
  ModelingPointerKey,
  ModelingSessionEvent,
  ModelingSessionPatch,
  ModelingSessionRecordRef,
  ModelingSessionSummary,
  ModelingStage,
  ModelingWorkspaceState,
} from "./features/modeling/model/session-controller";

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

export function modelingFamilyFromQuantities(quantities: string[]): ModelingMaterialFamilyType {
  if (quantities.some((quantity) => quantity.includes("relaxation")
    || quantity.includes("storage_modulus")
    || quantity.includes("modulus.storage")
    || quantity.includes("frequency.cyclic")
    || quantity === "time")) return "polymer";
  if (quantities.some((quantity) => quantity.includes("planar") || quantity.includes("biaxial") || quantity.includes("shear"))) return "elastomer";
  return "metal";
}
