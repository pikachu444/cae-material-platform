import { ApiError } from "../../../shared/api";
import type { LinearViscoelasticModelResponse } from "../model/modeling-resource-contracts";

interface ExactSourceRef {
  id: string;
  revisionId: string;
}

interface ExactCatalogContext {
  material: ExactSourceRef;
  materialState: ExactSourceRef;
  propertySet: ExactSourceRef;
}

interface CalibrationSelectionEvidenceRef {
  id: string;
  revisionId: string;
  calibrationPlanId?: string;
  calibrationRunId?: string;
  calibrationCandidateId?: string;
}

export function linearViscoelasticErrorMessage(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  return cause instanceof Error ? cause.message : "The governed polymer calibration request failed.";
}

export function assertSelectedModelMatchesCalibration(
  model: LinearViscoelasticModelResponse,
  selection: CalibrationSelectionEvidenceRef,
  context: ExactCatalogContext,
  expectedRevisionId?: string,
): void {
  const revision = model.current_revision;
  const content = revision.content;
  const evidence = content.calibration_promotion_evidence;
  const exactCatalogMatches = content.material_id === context.material.id
    && content.material_revision_id === context.material.revisionId
    && content.material_state_id === context.materialState.id
    && content.material_state_revision_id === context.materialState.revisionId
    && content.property_set_id === context.propertySet.id
    && content.property_set_revision_id === context.propertySet.revisionId;
  if ((expectedRevisionId && revision.id !== expectedRevisionId)
    || !evidence
    || evidence.selection.id !== selection.id
    || evidence.selection.revision_id !== selection.revisionId
    || evidence.plan.id !== selection.calibrationPlanId
    || evidence.run.id !== selection.calibrationRunId
    || evidence.candidate.id !== selection.calibrationCandidateId
    || !exactCatalogMatches) {
    throw new Error("The saved model does not match this exact input, calculation, and engineer selection.");
  }
}
