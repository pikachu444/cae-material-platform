import {
  ApiError,
  type ApiConfig,
  type ApiResult,
  type SolverCardDownload,
} from "../../../api";
import type { DataClassification } from "../../../types";
import type {
  CommonEnsemblePreview,
  CommonMappingProfileContent,
  CommonMappingProfileResponse,
  CommonProcessingBatchPreflight,
  CommonProcessingBatchResponse,
  CommonProcessingFitDecision,
  CommonProcessingMethod,
  CommonProcessingOutputResponse,
  CommonProcessingPreview,
  CommonProcessingRecipeContent,
  CommonProcessingRecipeResponse,
  CommonProcessingStep,
  CommonProcessingWorkupOverride,
  MetalFitRunResponse,
} from "../model/common-processing-contracts";
import type {
  CommonExactRevisionPin,
} from "../model/exact-revision-contracts";
import type {
  ElastoplasticExportCapabilities,
  ExportTarget,
  TargetDeliveryResponse,
  TargetPreviewResponse,
} from "../model/export-contracts";

const {
  authenticatedHeaders,
  endpoint,
  request,
  throwResponseError,
} = ApiError.modelingTransportCompatibility;

export function listCommonProcessingMethods(
  config: ApiConfig,
): Promise<ApiResult<{ items: CommonProcessingMethod[] }>> {
  return request(config, "/processing-methods");
}

export function listCommonProcessingEnsembleMethods(
  config: ApiConfig,
): Promise<ApiResult<{ items: CommonProcessingMethod[] }>> {
  return request(config, "/processing-ensemble-methods");
}

export function listCommonMappingProfiles(
  config: ApiConfig,
): Promise<ApiResult<{ items: CommonMappingProfileResponse[] }>> {
  return request(config, "/mapping-profiles");
}

export function createCommonMappingProfile(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: CommonMappingProfileContent;
    change_reason: string;
  },
): Promise<ApiResult<CommonMappingProfileResponse>> {
  return request(config, "/mapping-profiles", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseCommonMappingProfile(
  config: ApiConfig,
  profileId: string,
  etag: string,
  input: { content: CommonMappingProfileContent; change_reason: string },
): Promise<ApiResult<CommonMappingProfileResponse>> {
  return request(config, `/mapping-profiles/${encodeURIComponent(profileId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}

export function listCommonProcessingRecipes(
  config: ApiConfig,
): Promise<ApiResult<{ items: CommonProcessingRecipeResponse[] }>> {
  return request(config, "/common-processing-recipes");
}

export function createCommonProcessingRecipe(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: CommonProcessingRecipeContent;
    change_reason: string;
  },
): Promise<ApiResult<CommonProcessingRecipeResponse>> {
  return request(config, "/common-processing-recipes", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseCommonProcessingRecipe(
  config: ApiConfig,
  recipeId: string,
  etag: string,
  input: { content: CommonProcessingRecipeContent; change_reason: string },
): Promise<ApiResult<CommonProcessingRecipeResponse>> {
  return request(config, `/common-processing-recipes/${encodeURIComponent(recipeId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}

export function preflightCommonProcessingBatch(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    recipe_id: string;
    recipe_revision_id: string;
    sources: Array<{ document_id: string; revision_id: string }>;
  },
): Promise<ApiResult<CommonProcessingBatchPreflight>> {
  return request(config, "/common-processing-batches:preflight", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeCommonProcessingBatch(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    label: string;
    recipe_id: string;
    recipe_revision_id: string;
    sources: Array<{ document_id: string; revision_id: string }>;
    change_reason: string;
  },
): Promise<ApiResult<CommonProcessingBatchResponse>> {
  return request(config, "/common-processing-batches", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listCommonProcessingBatches(
  config: ApiConfig,
): Promise<ApiResult<{ items: CommonProcessingBatchResponse[] }>> {
  return request(config, "/common-processing-batches");
}

export function retryFailedCommonProcessingBatch(
  config: ApiConfig,
  batchId: string,
): Promise<ApiResult<CommonProcessingBatchResponse>> {
  return request(config, `/common-processing-batches/${encodeURIComponent(batchId)}:retry-failed`, {
    method: "POST",
  });
}

export function previewCommonProcessing(
  config: ApiConfig,
  input: {
    document: Record<string, unknown>;
    mapping_profile: CommonMappingProfileContent;
    steps: CommonProcessingStep[];
  },
  signal?: AbortSignal,
): Promise<ApiResult<CommonProcessingPreview>> {
  return request(config, "/processing:preview", {
    method: "POST",
    body: JSON.stringify(input),
    signal,
  });
}

export function previewCommonProcessingFromOutput(
  config: ApiConfig,
  input: {
    source_processing_output: CommonExactRevisionPin;
    fit_step: CommonProcessingStep;
  },
  signal?: AbortSignal,
): Promise<ApiResult<CommonProcessingPreview>> {
  return request(config, "/processing:preview-from-output", {
    method: "POST",
    body: JSON.stringify(input),
    signal,
  });
}

export function executeMetalFitRun(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    source_processing_output: CommonExactRevisionPin;
    fit_step: CommonProcessingStep;
    change_reason: string;
  },
  signal?: AbortSignal,
): Promise<ApiResult<MetalFitRunResponse>> {
  return request(config, "/metal-fit-runs", {
    method: "POST",
    body: JSON.stringify(input),
    signal,
  });
}

export function previewCommonProcessingEnsemble(
  config: ApiConfig,
  input: {
    documents: Record<string, unknown>[];
    mapping_profile: CommonMappingProfileContent;
    preprocessing_steps: CommonProcessingStep[];
    alignment: {
      point_count: number;
      domain_policy: "intersection";
      extrapolation: "reject";
    };
  },
): Promise<ApiResult<CommonEnsemblePreview>> {
  return request(config, "/processing:preview-ensemble", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listCommonProcessingOutputs(
  config: ApiConfig,
): Promise<ApiResult<{ items: CommonProcessingOutputResponse[] }>> {
  return request(config, "/processing-outputs");
}

export function commitCommonProcessingOutput(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    label: string;
    source_document: { aggregate_id: string; revision_id: string };
    mapping_profile: { aggregate_id: string; revision_id: string };
    steps: CommonProcessingStep[];
    change_reason: string;
    workup_overrides?: CommonProcessingWorkupOverride[];
    fit_decision?: CommonProcessingFitDecision | null;
    source_processing_output?: CommonExactRevisionPin | null;
  },
): Promise<ApiResult<CommonProcessingOutputResponse>> {
  return request(config, "/processing-outputs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function downloadCommonProcessingOutput(
  config: ApiConfig,
  outputId: string,
): Promise<ApiResult<SolverCardDownload>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(
    config,
    init,
    "application/vnd.cmp.processing-output+json",
  );
  const response = await fetch(
    endpoint(config, `/processing-outputs/${encodeURIComponent(outputId)}/content`),
    { ...init, headers },
  );
  if (!response.ok) return throwResponseError(response);
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return {
    data: {
      blob: await response.blob(),
      filename: match?.[1] ?? `processing-output-${outputId}.json`,
    },
    etag: response.headers.get("etag"),
  };
}

export function createExactTargetPreview(
  config: ApiConfig,
  input: {
    processing_output_id: string;
    processing_output_revision_id: string;
    neutral_material_id: string;
    neutral_material_revision_id: string;
    target: ExportTarget;
    solver_material_id: number;
    material_name: string;
    expected_mapping_report_sha256?: string;
  },
): Promise<ApiResult<TargetPreviewResponse>> {
  return request(config, "/exporting/target-previews", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** Download the exact Neutral revision selected by the Material Model export gate. */
export async function downloadSelectedModelNeutralMaterial(
  config: ApiConfig,
  neutralMaterialId: string,
  neutralMaterialRevisionId: string,
): Promise<ApiResult<{ blob: Blob; filename: string }>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "application/json");
  const response = await fetch(
    endpoint(
      config,
      `/neutral-materials/${encodeURIComponent(neutralMaterialId)}/revisions/${encodeURIComponent(neutralMaterialRevisionId)}/download`,
    ),
    { ...init, headers },
  );
  if (!response.ok) return throwResponseError(response);
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename = /filename="([^"]+)"/i.exec(disposition)?.[1]
    ?? `selected-model-${neutralMaterialRevisionId}.cmp-neutral.json`;
  return {
    data: { blob: await response.blob(), filename },
    etag: response.headers.get("etag"),
  };
}

export function getReferenceElastoplasticExportCapabilities(
  config: ApiConfig,
): Promise<ApiResult<ElastoplasticExportCapabilities>> {
  return request(config, "/exporters/reference-elastoplastic/capabilities");
}

export function deliverExactTargetPreview(
  config: ApiConfig,
  input: {
    processing_output_id: string;
    processing_output_revision_id: string;
    neutral_material_id: string;
    neutral_material_revision_id: string;
    target: ExportTarget;
    solver_material_id: number;
    material_name: string;
    preview_identity: string;
    expected_mapping_report_sha256: string;
    acknowledgement_identity?: string;
  },
): Promise<ApiResult<TargetDeliveryResponse>> {
  return request(config, "/exporting/target-deliveries", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
