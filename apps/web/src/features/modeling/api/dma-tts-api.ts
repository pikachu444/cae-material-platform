import {
  ApiError,
  authenticatedHeaders,
  endpoint,
  type ApiConfig,
  type ApiResult,
} from "../../../shared/api";
import type {
  CreateDmaTtsRequest,
  CreateDmaTtsResponse,
  DmaTtsRecommendationRequest,
  DmaTtsRecommendationResponse,
} from "../model/dma-tts-contracts";

interface DmaTtsErrorDocument {
  error?: { code?: string; cause?: string; recovery_hint?: string };
  detail?: string;
}

async function postDmaTts<T>(config: ApiConfig, path: string, body: unknown): Promise<ApiResult<T>> {
  const response = await fetch(endpoint(config, path), {
    method: "POST",
    headers: authenticatedHeaders(config, { body: JSON.stringify(body) }, "application/json"),
    body: JSON.stringify(body),
  });
  const payload = await response.json() as T | DmaTtsErrorDocument;
  if (!response.ok) {
    const problem = payload as DmaTtsErrorDocument;
    const cause = problem.error?.cause ?? problem.detail ?? `DMA TTS request failed (${response.status}).`;
    const recovery = problem.error?.recovery_hint;
    throw new ApiError(
      response.status,
      recovery ? `${cause} ${recovery}` : cause,
      problem.error?.code,
      response.headers.get("X-Trace-Id") ?? undefined,
    );
  }
  return {
    data: payload as T,
    etag: response.headers.get("ETag"),
    requestId: response.headers.get("X-Request-Id"),
  };
}

export function recommendDmaTts(
  config: ApiConfig,
  input: DmaTtsRecommendationRequest,
): Promise<ApiResult<DmaTtsRecommendationResponse>> {
  return postDmaTts(config, "/processing/dma-frequency-master-curves/recommendations", input);
}

export function createDmaTts(
  config: ApiConfig,
  input: CreateDmaTtsRequest,
): Promise<ApiResult<CreateDmaTtsResponse>> {
  return postDmaTts(config, "/processing/dma-frequency-master-curves", input);
}
