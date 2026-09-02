import type { ApiConfig } from "../../../shared/api";
import {
  getLinearViscoelasticPlan,
  getLinearViscoelasticRecommendation,
  getLinearViscoelasticResponseResiduals,
  getLinearViscoelasticRun,
  getLinearViscoelasticSelection,
  getLinearViscoelasticSelectedModel,
  listLinearViscoelasticCandidates,
} from "../api/linear-viscoelastic-calibration-api";
import type {
  LinearViscoelasticCandidate,
  LinearViscoelasticCatalogContext,
  LinearViscoelasticPlanResponse,
  LinearViscoelasticRecommendation,
  LinearViscoelasticResponseResidualEvidence,
  LinearViscoelasticRunResponse,
  LinearViscoelasticSelectionResponse,
} from "../model/linear-viscoelastic-calibration-contracts";
import { linearViscoelasticPlanSourceKey } from "../model/linear-viscoelastic-calibration-draft";
import type { LinearViscoelasticModelResponse } from "../model/modeling-resource-contracts";
import type { ModelingSessionRecordRef } from "../model/session-controller";
import { assertSelectedModelMatchesCalibration } from "./linear-viscoelastic-calibration-guards";

interface SavedCalibrationRef extends ModelingSessionRecordRef {
  calibrationPlanId?: string;
}

interface RestoredCalibration {
  kind: "loaded";
  sourceIdentity: string;
  plan: LinearViscoelasticPlanResponse;
  run: LinearViscoelasticRunResponse;
  selection: LinearViscoelasticSelectionResponse;
  candidates: LinearViscoelasticCandidate[];
  recommendation: LinearViscoelasticRecommendation | null;
  responseEvidence: LinearViscoelasticResponseResidualEvidence | null;
  model: LinearViscoelasticModelResponse | null;
}

interface StaleCalibration {
  kind: "stale";
  message: string;
}

export async function restoreLinearViscoelasticCalibration(input: {
  config: ApiConfig;
  selectionRef: SavedCalibrationRef;
  selectedModelRef?: ModelingSessionRecordRef;
  catalogContext?: LinearViscoelasticCatalogContext;
  directSourceIdentity: string;
  processingSourceIdentity: string;
}): Promise<RestoredCalibration | StaleCalibration> {
  const { config, selectionRef, selectedModelRef, catalogContext } = input;
  if (!selectionRef.calibrationPlanId) throw new Error("Saved Selection has no exact Plan reference.");
  const selection = (await getLinearViscoelasticSelection(config, selectionRef.id)).data;
  const [plan, run] = await Promise.all([
    getLinearViscoelasticPlan(config, selectionRef.calibrationPlanId).then((result) => result.data),
    getLinearViscoelasticRun(config, selection.run_id).then((result) => result.data),
  ]);
  if (plan.current_revision.id !== selection.plan_revision_id
    || run.plan_revision_id !== selection.plan_revision_id) {
    return {
      kind: "stale",
      message: "Saved Selection points to a different Plan revision. The immutable records remain readable, but this Fit context is stale.",
    };
  }
  const sourceIdentity = linearViscoelasticPlanSourceKey(plan.current_revision.content);
  if (sourceIdentity !== input.directSourceIdentity
    && sourceIdentity !== input.processingSourceIdentity) {
    return {
      kind: "stale",
      message: "Saved Selection points to an exact source revision that is not loaded in this Fit context. The immutable records remain readable; restore the matching source before retrying.",
    };
  }

  let candidates: LinearViscoelasticCandidate[] = [];
  let recommendation: LinearViscoelasticRecommendation | null = null;
  let responseEvidence: LinearViscoelasticResponseResidualEvidence | null = null;
  let model: LinearViscoelasticModelResponse | null = null;
  if (run.status === "succeeded") {
    [candidates, recommendation, responseEvidence] = await Promise.all([
      listLinearViscoelasticCandidates(config, run.run_id).then((result) => result.data),
      getLinearViscoelasticRecommendation(config, run.run_id).then((result) => result.data),
      getLinearViscoelasticResponseResiduals(config, run.run_id).then((result) => result.data),
    ]);
    if (selectedModelRef) {
      if (!catalogContext) throw new Error("The exact Material, State, and property context is not loaded.");
      model = (await getLinearViscoelasticSelectedModel(config, selectedModelRef.id)).data;
      assertSelectedModelMatchesCalibration(model, selectionRef, catalogContext, selectedModelRef.revisionId);
    }
  }
  return {
    kind: "loaded",
    sourceIdentity,
    plan,
    run,
    selection,
    candidates,
    recommendation,
    responseEvidence,
    model,
  };
}
