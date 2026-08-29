import type {
  SchemaDefinitionBundleApplication,
  SchemaDefinitionBundleExport,
  SchemaDefinitionBundlePlan,
} from "../contracts";
import type {
  CompletedUpload,
  UploadSession,
} from "../../test-data/contracts";
import type { DataClassification } from "../../../shared/model/core-contracts";

import {
  ApiError,
  authenticatedHeaders,
  endpoint,
  request,
  throwResponseError,
} from "../../../shared/api/http";

import type { ApiConfig, ApiResult } from "../../../shared/api/http";

export { ApiError } from "../../../shared/api/http";
export type { ApiConfig } from "../../../shared/api/http";
export { getEffectiveProductAccess } from "../../../shared/api/auth";

function browserIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `browser-upload-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

async function sha256Hex(file: Blob): Promise<string> {
  if (typeof crypto === "undefined" || !crypto.subtle) {
    throw new ApiError(503, "This browser cannot calculate the required SHA-256 upload digest.");
  }
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

const SCHEMA_DEFINITION_BUNDLE_MEDIA_TYPE =
  "application/vnd.cmp.catalog-schema-definition-bundle+json";
const SCHEMA_DEFINITION_SOURCE_SET_MEDIA_TYPE =
  "application/vnd.cmp.catalog-schema-source-set+json";
const SCHEMA_DEFINITION_SOURCE_ZIP_MEDIA_TYPE =
  "application/vnd.cmp.catalog-schema-source-set+zip";
const SCHEMA_DEFINITION_BUNDLE_MAX_BYTES = 64 * 1024 * 1024;
const SCHEMA_DEFINITION_BUNDLE_FILE_TYPES = new Set([
  "",
  "application/json",
  "application/schema+json",
  SCHEMA_DEFINITION_BUNDLE_MEDIA_TYPE,
  SCHEMA_DEFINITION_SOURCE_SET_MEDIA_TYPE,
  "application/zip",
  SCHEMA_DEFINITION_SOURCE_ZIP_MEDIA_TYPE,
]);

export async function uploadSchemaDefinitionBundle(
  config: ApiConfig,
  input: { file: File; classification: DataClassification },
): Promise<ApiResult<CompletedUpload>> {
  const filename = input.file.name.trim();
  if (!filename || filename.includes("/") || filename.includes("\\")) {
    throw new ApiError(422, "Choose a JSON bundle with a safe, non-empty filename.");
  }
  const lowerFilename = filename.toLowerCase();
  const isZip = lowerFilename.endsWith(".zip");
  if (
    (!lowerFilename.endsWith(".json") && !isZip)
    || !SCHEMA_DEFINITION_BUNDLE_FILE_TYPES.has(input.file.type)
  ) {
    throw new ApiError(415, "Choose a JSON source set or ZIP Schema Definition source.");
  }
  if (input.file.size < 1 || input.file.size > SCHEMA_DEFINITION_BUNDLE_MAX_BYTES) {
    throw new ApiError(413, "The definition bundle must be between 1 byte and 64 MiB.");
  }

  const digest = await sha256Hex(input.file);
  const mediaType = isZip
    ? SCHEMA_DEFINITION_SOURCE_ZIP_MEDIA_TYPE
    : input.file.type === SCHEMA_DEFINITION_SOURCE_SET_MEDIA_TYPE
      ? SCHEMA_DEFINITION_SOURCE_SET_MEDIA_TYPE
      : SCHEMA_DEFINITION_BUNDLE_MEDIA_TYPE;
  const created = await request<{ upload: UploadSession; upload_capability: string }>(
    config,
    "/uploads",
    {
      method: "POST",
      headers: { "Idempotency-Key": browserIdempotencyKey() },
      body: JSON.stringify({
        classification: input.classification,
        original_filename: filename,
        media_type: mediaType,
        expected_size_bytes: input.file.size,
        expected_sha256: digest,
      }),
    },
  );
  const { upload, upload_capability: capability } = created.data;
  for (let partNumber = 1; partNumber <= upload.expected_part_count; partNumber += 1) {
    const start = (partNumber - 1) * upload.part_size_bytes;
    const part = input.file.slice(
      start,
      Math.min(input.file.size, start + upload.part_size_bytes),
      mediaType,
    );
    await request<UploadSession>(
      config,
      `/uploads/${encodeURIComponent(upload.upload_id)}/parts/${partNumber}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": mediaType,
          "Upload-Capability": capability,
        },
        body: part,
      },
    );
  }
  const completed = await request<CompletedUpload>(
    config,
    `/uploads/${encodeURIComponent(upload.upload_id)}:complete`,
    { method: "POST", headers: { "Upload-Capability": capability } },
  );
  if (!completed.data.available_artifact_id) {
    throw new ApiError(
      503,
      "The verified upload is not yet available as an immutable Artifact. Retry when Artifact finalization is available.",
    );
  }
  return completed;
}

export function planSchemaDefinitionBundle(
  config: ApiConfig,
  input: { artifact_id: string; artifact_sha256: string },
): Promise<ApiResult<SchemaDefinitionBundlePlan>> {
  return request(config, "/catalog/schema-definition-bundles:plan", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function applySchemaDefinitionBundle(
  config: ApiConfig,
  input: { artifact_id: string; artifact_sha256: string; plan_fingerprint: string },
): Promise<ApiResult<SchemaDefinitionBundleApplication>> {
  return request(config, "/catalog/schema-definition-bundles:apply", {
    method: "POST",
    headers: { "Idempotency-Key": `schema-bundle-${browserIdempotencyKey()}` },
    body: JSON.stringify({ ...input, delete_missing: false }),
  });
}

export function getSchemaDefinitionBundleApplication(
  config: ApiConfig,
  applicationId: string,
): Promise<ApiResult<SchemaDefinitionBundleApplication>> {
  return request(
    config,
    `/catalog/schema-definition-bundle-applications/${encodeURIComponent(applicationId)}`,
  );
}

function digestBase64(hexDigest: string): string {
  let binary = "";
  for (let index = 0; index < hexDigest.length; index += 2) {
    binary += String.fromCharCode(Number.parseInt(hexDigest.slice(index, index + 2), 16));
  }
  return btoa(binary);
}

export async function downloadSchemaDefinitionBundle(
  config: ApiConfig,
  bundleKey: string,
  bundleVersion: string,
): Promise<SchemaDefinitionBundleExport> {
  const headers = authenticatedHeaders(
    config,
    {},
    SCHEMA_DEFINITION_BUNDLE_MEDIA_TYPE,
  );
  const response = await fetch(
    endpoint(
      config,
      `/catalog/schema-definition-bundles/${encodeURIComponent(bundleKey)}:export`,
    ),
    { headers },
  );
  if (!response.ok) {
    return throwResponseError(response);
  }

  const mediaType = response.headers.get("content-type")?.split(";", 1)[0]?.trim() ?? "";
  if (mediaType !== SCHEMA_DEFINITION_BUNDLE_MEDIA_TYPE) {
    throw new ApiError(409, "The exported bundle has an unexpected media type.");
  }
  const blob = await response.blob();
  const sha256 = await sha256Hex(blob);
  const etag = response.headers.get("etag");
  const digestHeader = response.headers.get("digest");
  if (etag !== `\"sha256:${sha256}\"` || digestHeader !== `sha-256=${digestBase64(sha256)}`) {
    throw new ApiError(409, "The exported bundle checksum does not match its response evidence.");
  }

  const applicationId = response.headers.get("x-cmp-bundle-application-id") ?? "";
  const sourceArtifactId = response.headers.get("x-cmp-source-artifact-id") ?? "";
  const sourceArtifactSha256 = response.headers.get("x-cmp-source-artifact-sha256") ?? "";
  if (!applicationId || !sourceArtifactId || !/^[0-9a-f]{64}$/.test(sourceArtifactSha256)) {
    throw new ApiError(409, "The exported bundle is missing immutable source evidence.");
  }

  return {
    blob,
    sha256,
    filename: `${bundleKey}-${bundleVersion}.json`,
    media_type: mediaType,
    application_id: applicationId,
    source_artifact_id: sourceArtifactId,
    source_artifact_sha256: sourceArtifactSha256,
    request_id: response.headers.get("x-request-id"),
  };
}
