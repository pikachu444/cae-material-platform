import type { ApiConfig } from "../../../shared/api";
import { getAuthenticatedPrincipal } from "../../../shared/api";
import {
  createLinearViscoelasticSelection,
  getLinearViscoelasticSelectedModel,
  promoteLinearViscoelasticSelection,
} from "../api/linear-viscoelastic-calibration-api";
import type {
  LinearViscoelasticCandidate,
  LinearViscoelasticPlanResponse,
  LinearViscoelasticRunResponse,
  LinearViscoelasticSelectionResponse,
} from "../model/linear-viscoelastic-calibration-contracts";
import type { LinearViscoelasticModelResponse } from "../model/modeling-resource-contracts";
import { assertSelectedModelMatchesCalibration } from "./linear-viscoelastic-calibration-guards";

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

interface CreateEngineerSelectionOptions {
  config: ApiConfig;
  plan: LinearViscoelasticPlanResponse;
  run: LinearViscoelasticRunResponse;
  candidate: LinearViscoelasticCandidate;
  reason: string;
  warnings: string[];
}

export async function createEngineerLinearViscoelasticSelection({
  config,
  plan,
  run,
  candidate,
  reason,
  warnings,
}: CreateEngineerSelectionOptions): Promise<LinearViscoelasticSelectionResponse> {
  const principal = warnings.length ? await getAuthenticatedPrincipal(config) : null;
  if (warnings.length && !principal?.data.principal_id) {
    throw new Error("The authenticated actor could not be resolved for warning acknowledgement.");
  }
  const acknowledgements = warnings.map((warning) => ({
    code: warning,
    rule_version: "candidate-warning@1.0.0",
    plan_revision_id: plan.current_revision.id,
    run_id: run.run_id,
    candidate_id: candidate.candidate_id,
    actor: principal?.data.principal_id,
    reason,
    time: new Date().toISOString(),
  }));
  return (await createLinearViscoelasticSelection(config, {
    plan_revision_id: plan.current_revision.id,
    run_id: run.run_id,
    candidate_id: candidate.candidate_id,
    candidate_sha256: candidate.candidate_sha256,
    reason,
    warning_acknowledgements: acknowledgements,
    change_reason: "Save the engineer polymer Candidate Selection",
  })).data;
}

interface SaveSelectedModelOptions {
  config: ApiConfig;
  selection: LinearViscoelasticSelectionResponse;
  selectionRef: CalibrationSelectionEvidenceRef;
  catalogContext: ExactCatalogContext;
}

export async function saveSelectedLinearViscoelasticModel({
  config,
  selection,
  selectionRef,
  catalogContext,
}: SaveSelectedModelOptions): Promise<LinearViscoelasticModelResponse> {
  const promoted = (await promoteLinearViscoelasticSelection(config, selection.selection_id, {
    material: { id: catalogContext.material.id, revision_id: catalogContext.material.revisionId },
    material_state: { id: catalogContext.materialState.id, revision_id: catalogContext.materialState.revisionId },
    property_set: { id: catalogContext.propertySet.id, revision_id: catalogContext.propertySet.revisionId },
    change_reason: "Save the exact engineer-selected polymer model",
  })).data;
  const reloaded = (await getLinearViscoelasticSelectedModel(config, promoted.material_model_id)).data;
  assertSelectedModelMatchesCalibration(reloaded, selectionRef, catalogContext, promoted.current_revision.id);
  return reloaded;
}
