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
  DmaTtsMultiRecommendationRequest,
  DmaTtsMultiRecommendationResponse,
  DmaTtsReadResponse,
} from "../model/dma-tts-contracts";

interface DmaTtsErrorDocument {
  error?: { code?: string; cause?: string; recovery_hint?: string } | string;
  detail?: string | { message?: string };
  title?: string;
}

function readableError(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (value && typeof value === "object") {
    const message = (value as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message.trim();
  }
  return null;
}

export function dmaTtsErrorMessage(caught: unknown, fallback = "The DMA TTS operation failed."): string {
  if (caught instanceof ApiError) return caught.message;
  const message = readableError(caught);
  return message ?? fallback;
}

async function postDmaTts<T>(config: ApiConfig, path: string, body: unknown): Promise<ApiResult<T>> {
  const serialized = JSON.stringify(body);
  const response = await fetch(endpoint(config, path), {
    method: "POST",
    headers: authenticatedHeaders(config, { body: serialized }, "application/json"),
    body: serialized,
  });
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    payload = undefined;
  }
  if (!response.ok) {
    const problem = payload as DmaTtsErrorDocument;
    const nested = problem?.error && typeof problem.error === "object" ? problem.error : undefined;
    const cause = readableError(nested?.cause)
      ?? readableError(problem?.detail)
      ?? readableError(problem?.title)
      ?? readableError(problem?.error)
      ?? `DMA TTS request failed (${response.status}).`;
    const recovery = readableError(nested?.recovery_hint);
    throw new ApiError(
      response.status,
      recovery ? `${cause} ${recovery}` : cause,
      nested?.code,
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

export function recommendMultiDmaTts(
  config: ApiConfig,
  input: DmaTtsMultiRecommendationRequest,
): Promise<ApiResult<DmaTtsMultiRecommendationResponse>> {
  return postDmaTts(config, "/processing/dma-frequency-master-curves/recommendations/multi-frequency", input);
}

export function createDmaTts(
  config: ApiConfig,
  input: CreateDmaTtsRequest,
): Promise<ApiResult<CreateDmaTtsResponse>> {
  return postDmaTts(config, "/processing/dma-frequency-master-curves", input);
}

export function getDmaTtsRevision(
  config: ApiConfig,
  outputId: string,
  revisionId: string,
  contentSha256: string,
): Promise<ApiResult<DmaTtsReadResponse>> {
  const query = new URLSearchParams({ content_sha256: contentSha256 });
  return fetch(endpoint(config, `/processing/dma-frequency-master-curves/${encodeURIComponent(outputId)}/revisions/${encodeURIComponent(revisionId)}?${query.toString()}`), {
    headers: authenticatedHeaders(config, {}, "application/json"),
  }).then(async (response) => {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = undefined;
    }
    if (!response.ok) {
      const problem = payload as DmaTtsErrorDocument;
      const nested = problem?.error && typeof problem.error === "object" ? problem.error : undefined;
      const cause = readableError(nested?.cause)
        ?? readableError(problem?.detail)
        ?? readableError(problem?.title)
        ?? readableError(problem?.error)
        ?? `DMA TTS read-back failed (${response.status}).`;
      const recovery = readableError(nested?.recovery_hint);
      throw new ApiError(
        response.status,
        recovery ? `${cause} ${recovery}` : cause,
        nested?.code,
        response.headers.get("X-Trace-Id") ?? undefined,
      );
    }
    return {
      data: payload as DmaTtsReadResponse,
      etag: response.headers.get("ETag"),
      requestId: response.headers.get("X-Request-Id"),
    };
  });
}
