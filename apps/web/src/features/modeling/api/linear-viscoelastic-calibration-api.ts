import { request, type ApiConfig, type ApiResult } from "../../../shared/api";
import type {
  DirectLinearViscoelasticPlanRequest,
  LinearViscoelasticCandidate,
  LinearViscoelasticPlanApproval,
  LinearViscoelasticPlanContextRequest,
  LinearViscoelasticPlanContextResponse,
  LinearViscoelasticPlanResponse,
  LinearViscoelasticResponseResidualEvidence,
  LinearViscoelasticRunAcceptedResponse,
  LinearViscoelasticRunResponse,
  LinearViscoelasticSelectionRequest,
  LinearViscoelasticSelectionResponse,
  ProcessedLinearViscoelasticFitInput,
  ProcessedLinearViscoelasticPlanRequest,
} from "../model/linear-viscoelastic-calibration-contracts";
import type { LinearViscoelasticModelResponse } from "../model/modeling-resource-contracts";

function idempotencyKey(prefix: string): string {
  const uuid = globalThis.crypto?.randomUUID?.();
  return `${prefix}:${uuid ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`}`;
}

function postJson<T>(config: ApiConfig, path: string, body: unknown, prefix: string): Promise<ApiResult<T>> {
  return request(config, path, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey(prefix) },
    body: JSON.stringify(body),
  });
}

export function createLinearViscoelasticPlan(
  config: ApiConfig,
  input: DirectLinearViscoelasticPlanRequest,
): Promise<ApiResult<LinearViscoelasticPlanResponse>> {
  return postJson(config, "/linear-viscoelastic-calibration-plans", input, "lve-plan");
}

export function createProcessedLinearViscoelasticPlan(
  config: ApiConfig,
  input: ProcessedLinearViscoelasticPlanRequest,
): Promise<ApiResult<LinearViscoelasticPlanResponse>> {
  return postJson(config, "/linear-viscoelastic-calibration-plans/from-processing-output", input, "lve-processed-plan");
}

export function getProcessedLinearViscoelasticFitInput(
  config: ApiConfig,
  processingOutputId: string,
  processingOutputRevisionId: string,
): Promise<ApiResult<ProcessedLinearViscoelasticFitInput>> {
  return request(
    config,
    `/processing-outputs/${encodeURIComponent(processingOutputId)}/revisions/${encodeURIComponent(processingOutputRevisionId)}/linear-viscoelastic-fit-input`,
  );
}

export function getLinearViscoelasticPlan(
  config: ApiConfig,
  planId: string,
): Promise<ApiResult<LinearViscoelasticPlanResponse>> {
  return request(config, `/linear-viscoelastic-calibration-plans/${encodeURIComponent(planId)}`);
}

export function resolveLinearViscoelasticPlanContext(
  config: ApiConfig,
  input: LinearViscoelasticPlanContextRequest,
): Promise<ApiResult<LinearViscoelasticPlanContextResponse>> {
  return request(config, "/linear-viscoelastic-calibration-plans/resolve", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getLinearViscoelasticPlanApproval(
  config: ApiConfig,
  planId: string,
  planRevisionId: string,
): Promise<ApiResult<LinearViscoelasticPlanApproval>> {
  const query = new URLSearchParams({ plan_revision_id: planRevisionId });
  return request(
    config,
    `/linear-viscoelastic-calibration-plans/${encodeURIComponent(planId)}/approval?${query.toString()}`,
  );
}

export function queueLinearViscoelasticRun(
  config: ApiConfig,
  planId: string,
  input: { plan_revision_id: string; change_reason: string },
): Promise<ApiResult<LinearViscoelasticRunAcceptedResponse>> {
  return postJson(config, `/linear-viscoelastic-calibration-plans/${encodeURIComponent(planId)}/runs`, input, "lve-run");
}

export function getLinearViscoelasticRun(
  config: ApiConfig,
  runId: string,
): Promise<ApiResult<LinearViscoelasticRunResponse>> {
  return request(config, `/linear-viscoelastic-calibration-runs/${encodeURIComponent(runId)}`);
}

export function getLinearViscoelasticResponseResiduals(
  config: ApiConfig,
  runId: string,
): Promise<ApiResult<LinearViscoelasticResponseResidualEvidence>> {
  return request(config, `/linear-viscoelastic-calibration-runs/${encodeURIComponent(runId)}/response-residuals`);
}

export function listLinearViscoelasticCandidates(
  config: ApiConfig,
  runId: string,
): Promise<ApiResult<LinearViscoelasticCandidate[]>> {
  return request(config, `/linear-viscoelastic-calibration-runs/${encodeURIComponent(runId)}/candidates`);
}

export function getLinearViscoelasticRecommendation(
  config: ApiConfig,
  runId: string,
): Promise<ApiResult<LinearViscoelasticRunResponse["recommendation"]>> {
  return request(config, `/linear-viscoelastic-calibration-runs/${encodeURIComponent(runId)}/recommendation`);
}

export function createLinearViscoelasticSelection(
  config: ApiConfig,
  input: LinearViscoelasticSelectionRequest,
): Promise<ApiResult<LinearViscoelasticSelectionResponse>> {
  return postJson(config, "/linear-viscoelastic-calibration-selections", input, "lve-selection");
}

export function getLinearViscoelasticSelection(
  config: ApiConfig,
  selectionId: string,
): Promise<ApiResult<LinearViscoelasticSelectionResponse>> {
  return request(config, `/linear-viscoelastic-calibration-selections/${encodeURIComponent(selectionId)}`);
}

export function promoteLinearViscoelasticSelection(
  config: ApiConfig,
  selectionId: string,
  input: {
    material: { id: string; revision_id: string };
    material_state: { id: string; revision_id: string };
    property_set: { id: string; revision_id: string };
    change_reason: string;
  },
): Promise<ApiResult<LinearViscoelasticModelResponse>> {
  return postJson(
    config,
    `/linear-viscoelastic-calibration-selections/${encodeURIComponent(selectionId)}/linear-viscoelastic-model`,
    input,
    "lve-selected-model",
  );
}

export function getLinearViscoelasticSelectedModel(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<LinearViscoelasticModelResponse>> {
  return request(config, `/linear-viscoelastic-models/${encodeURIComponent(materialModelId)}`);
}
