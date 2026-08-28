import {
  ApiError,
  request,
  type ApiConfig,
  type ApiResult,
} from "../../../shared/api/http";
import type {
  JsonDataClassification,
  JsonRegistrationArtifact,
  JsonRegistrationDomainBindingPin,
  JsonRegistrationFormatsResponse,
  JsonRegistrationPreviewResponse,
  JsonRegistrationReferencePin,
  JsonRegistrationSaveResponse,
} from "./json-registration-model";
import {
  buildJsonRegistrationPackage,
  MAX_COMPONENT_BYTES,
  MAX_PACKAGE_BYTES,
  MAX_SINGLE_JSON_BYTES,
  safeFilename,
  sha256Hex,
} from "./json-registration-package";

const JSON_MEDIA_TYPE = "application/json";
const ZIP_MEDIA_TYPE = "application/zip";

interface UploadSession {
  upload_id: string;
  expected_part_count: number;
  part_size_bytes: number;
}

interface UploadResponse {
  upload: UploadSession;
  upload_capability: string;
}

interface CompletedUploadResponse {
  available_artifact_id: string | null;
}

function browserIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `json-registration-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function listInstalledJsonRecordFormats(
  config: ApiConfig,
): Promise<ApiResult<JsonRegistrationFormatsResponse>> {
  return request(config, "/catalog/json-record-formats");
}

/** Transport only: package construction lives in json-registration-package.ts. */
export async function uploadJsonRegistrationArtifact(
  config: ApiConfig,
  input: { file: File; classification: JsonDataClassification },
): Promise<ApiResult<JsonRegistrationArtifact>> {
  const filename = safeFilename(input.file.name);
  const isZip = input.file.type === ZIP_MEDIA_TYPE || filename.toLowerCase().endsWith(".zip");
  if (input.file.size < 1 || input.file.size > MAX_COMPONENT_BYTES) {
    throw new ApiError(413, "A source must be between 1 byte and 250 MiB.");
  }
  if (isZip && input.file.size > MAX_PACKAGE_BYTES) {
    throw new ApiError(413, "A JSON package is limited to 64 MiB.");
  }
  if (!isZip && input.file.size > MAX_SINGLE_JSON_BYTES) {
    throw new ApiError(
      413,
      "A raw JSON source is limited to 25 MiB; select it with other files to build a package.",
    );
  }
  const mediaType = isZip ? ZIP_MEDIA_TYPE : JSON_MEDIA_TYPE;
  const digest = await sha256Hex(input.file);
  const created = await request<UploadResponse>(config, "/uploads", {
    method: "POST",
    headers: { "Idempotency-Key": browserIdempotencyKey() },
    body: JSON.stringify({
      classification: input.classification,
      original_filename: filename,
      media_type: mediaType,
      expected_size_bytes: input.file.size,
      expected_sha256: digest,
    }),
  });
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
        headers: { "Content-Type": mediaType, "Upload-Capability": capability },
        body: part,
      },
    );
  }
  const completed = await request<CompletedUploadResponse>(
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
  return {
    data: {
      filename,
      artifact_id: completed.data.available_artifact_id,
      sha256: digest,
      media_type: mediaType,
      size_bytes: input.file.size,
    },
    etag: completed.etag,
    requestId: completed.requestId,
  };
}

export async function uploadJsonRegistrationFiles(
  config: ApiConfig,
  input: { files: File[]; classification: JsonDataClassification },
): Promise<ApiResult<JsonRegistrationArtifact>> {
  if (!input.files.length) throw new ApiError(422, "Choose at least one source file.");
  const isZip = input.files.some(
    (file) => file.type === ZIP_MEDIA_TYPE || file.name.toLowerCase().endsWith(".zip"),
  );
  if (isZip) {
    if (input.files.length !== 1) {
      throw new ApiError(422, "A ZIP package must be uploaded by itself.");
    }
    return uploadJsonRegistrationArtifact(config, {
      file: input.files[0],
      classification: input.classification,
    });
  }
  if (input.files.length === 1 && input.files[0].size <= MAX_SINGLE_JSON_BYTES) {
    return uploadJsonRegistrationArtifact(config, {
      file: input.files[0],
      classification: input.classification,
    });
  }
  const packageFile = await buildJsonRegistrationPackage(input.files, input.classification);
  return uploadJsonRegistrationArtifact(config, {
    file: packageFile,
    classification: input.classification,
  });
}

export function previewJsonRecordRegistration(
  config: ApiConfig,
  input: {
    format_revision_id?: string;
    classification: JsonDataClassification;
    files: JsonRegistrationArtifact[];
    reference_pins?: JsonRegistrationReferencePin[];
    domain_bindings?: JsonRegistrationDomainBindingPin[];
  },
): Promise<ApiResult<JsonRegistrationPreviewResponse>> {
  const files = input.files.map(({ filename, artifact_id, sha256, media_type }) => ({
    filename,
    artifact_id,
    sha256,
    media_type,
  }));
  return request(config, "/catalog/json-record-registrations:preview", {
    method: "POST",
    body: JSON.stringify({ ...input, files }),
  });
}

export function saveJsonRecordRegistration(
  config: ApiConfig,
  previewToken: string,
  input: {
    format_revision_id?: string;
    package_sha256: string;
    change_reason: string;
    reference_pins?: JsonRegistrationReferencePin[];
    domain_bindings?: JsonRegistrationDomainBindingPin[];
  },
): Promise<ApiResult<JsonRegistrationSaveResponse>> {
  return request(
    config,
    `/catalog/json-record-registrations/${encodeURIComponent(previewToken)}:save`,
    { method: "POST", body: JSON.stringify(input) },
  );
}
