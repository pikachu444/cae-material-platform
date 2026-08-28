import {
  ApiError,
  authenticatedHeaders,
  endpoint,
  request,
  throwResponseError,
  type ApiConfig,
  type ApiResult,
} from "../../../shared/api/http";

export type ExactCatalogSourceFormat = "json" | "csv";

export interface ExactCatalogSourceAvailability {
  available: boolean;
  published: boolean;
  ready: boolean;
}

interface ExactCatalogSourceDownload {
  blob: Blob;
  filename: string;
  sha256: string;
}

async function sha256Hex(value: Blob): Promise<string> {
  if (typeof crypto === "undefined" || !crypto.subtle) {
    throw new ApiError(503, "This browser cannot verify exact source bytes.");
  }
  const digest = await crypto.subtle.digest("SHA-256", await value.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

function filenameFromResponse(
  response: Response,
  recordId: string,
  revisionId: string,
  format: ExactCatalogSourceFormat,
): string {
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return match?.[1] ?? `catalog-record-${recordId}-${revisionId}.${format}`;
}

async function downloadExactCatalogSource(
  config: ApiConfig,
  recordId: string,
  revisionId: string,
  format: ExactCatalogSourceFormat,
): Promise<ApiResult<ExactCatalogSourceDownload>> {
  if (!recordId || !revisionId) {
    throw new ApiError(400, "An exact Catalog Record identity and revision are required.");
  }
  const init: RequestInit = {};
  const accept = format === "json" ? "application/json" : "text/csv";
  const headers = authenticatedHeaders(config, init, accept);
  const query = "?published_only=true";
  const response = await fetch(
    endpoint(
      config,
      `/catalog/records/${encodeURIComponent(recordId)}/revisions/${encodeURIComponent(revisionId)}/source.${format}${query}`,
    ),
    { ...init, headers },
  );
  if (!response.ok) await throwResponseError(response);
  const blob = await response.blob();
  const sha256 = await sha256Hex(blob);
  const evidence = response.headers.get("x-content-sha256");
  if (!evidence || evidence !== sha256) {
    throw new ApiError(409, "The exact source response checksum does not match its evidence.");
  }
  return {
    data: {
      blob,
      filename: filenameFromResponse(response, recordId, revisionId, format),
      sha256,
    },
    etag: response.headers.get("etag"),
    requestId: response.headers.get("x-request-id"),
  };
}

export function downloadExactJsonSource(
  config: ApiConfig,
  recordId: string,
  revisionId: string,
): Promise<ApiResult<ExactCatalogSourceDownload>> {
  return downloadExactCatalogSource(config, recordId, revisionId, "json");
}

export function downloadExactCsvSource(
  config: ApiConfig,
  recordId: string,
  revisionId: string,
): Promise<ApiResult<ExactCatalogSourceDownload>> {
  return downloadExactCatalogSource(config, recordId, revisionId, "csv");
}

export function getExactCatalogSourceAvailability(
  config: ApiConfig,
  recordId: string,
  revisionId: string,
): Promise<ApiResult<ExactCatalogSourceAvailability>> {
  if (!recordId || !revisionId) {
    throw new ApiError(400, "An exact Catalog Record identity and revision are required.");
  }
  return request<ExactCatalogSourceAvailability>(
    config,
    `/catalog/records/${encodeURIComponent(recordId)}/revisions/${encodeURIComponent(revisionId)}/source-availability?published_only=true`,
  );
}
