import type {
  AuditEventPage,
  AuditIntegrityReport,
  AuditOutcome,
  OperationalSnapshotResponse,
  ProvenanceCompletenessReport,
  ProvenanceEntityResponse,
  ProvenanceLineagePage,
  RecordReleaseUsageInput,
  ReleaseCreateInput,
  ReleaseImpactResponse,
  ReleaseListResponse,
  ReleaseResponse,
  ReleaseUsageResponse,
  ReviewDecisionKind,
  ReviewRequestListResponse,
  ReviewRequestResponse,
  SupersedeReleaseInput,
  WithdrawReleaseInput,
} from "../contracts";
import type { CommonProcessingBatchResponse } from "../../modeling/contracts";
import type { DataClassification } from "../../../shared/model/core-contracts";

import {
  authenticatedHeaders,
  endpoint,
  request,
  throwResponseError,
} from "../../../shared/api/http";

import type { ApiConfig, ApiResult } from "../../../shared/api/http";

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

export function createReviewRequest(
  config: ApiConfig,
  input: {
    classification?: DataClassification;
    aggregate_type: string;
    aggregate_id: string;
    revision_id: string;
    manifest_sha256?: string;
    reason: string;
  },
): Promise<ApiResult<ReviewRequestResponse>> {
  return request(config, "/review-requests", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listReviewRequests(
  config: ApiConfig,
  filters: {
    aggregate_type?: string;
    aggregate_id?: string;
    revision_id?: string;
    limit?: number;
  } = {},
): Promise<ApiResult<ReviewRequestListResponse>> {
  const query = new URLSearchParams();
  if (filters.aggregate_type?.trim()) query.set("aggregate_type", filters.aggregate_type.trim());
  if (filters.aggregate_id?.trim()) query.set("aggregate_id", filters.aggregate_id.trim());
  if (filters.revision_id?.trim()) query.set("revision_id", filters.revision_id.trim());
  if (filters.limit) query.set("limit", String(filters.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request(config, `/review-requests${suffix}`);
}

export function getReviewRequest(
  config: ApiConfig,
  reviewRequestId: string,
): Promise<ApiResult<ReviewRequestResponse>> {
  return request(config, `/review-requests/${encodeURIComponent(reviewRequestId)}`);
}

export function createReviewDecision(
  config: ApiConfig,
  reviewRequestId: string,
  input: {
    expected_manifest_sha256: string;
    decision: ReviewDecisionKind;
    reason: string;
  },
): Promise<ApiResult<ReviewRequestResponse>> {
  return request(config, `/review-requests/${encodeURIComponent(reviewRequestId)}/decisions`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createRelease(
  config: ApiConfig,
  input: ReleaseCreateInput,
): Promise<ApiResult<ReleaseResponse>> {
  return request(config, "/releases", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listReleases(
  config: ApiConfig,
  limit = 50,
): Promise<ApiResult<ReleaseListResponse>> {
  const query = new URLSearchParams({ limit: String(limit) });
  return request(config, `/releases?${query.toString()}`);
}

export function getRelease(
  config: ApiConfig,
  releaseId: string,
): Promise<ApiResult<ReleaseResponse>> {
  return request(config, `/releases/${encodeURIComponent(releaseId)}`);
}

export function supersedeRelease(
  config: ApiConfig,
  releaseId: string,
  input: SupersedeReleaseInput,
): Promise<ApiResult<ReleaseResponse>> {
  return request(config, `/releases/${encodeURIComponent(releaseId)}/supersede`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function withdrawRelease(
  config: ApiConfig,
  releaseId: string,
  input: WithdrawReleaseInput,
): Promise<ApiResult<ReleaseResponse>> {
  return request(config, `/releases/${encodeURIComponent(releaseId)}/withdraw`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function recordReleaseUsage(
  config: ApiConfig,
  releaseId: string,
  input: RecordReleaseUsageInput,
): Promise<ApiResult<ReleaseUsageResponse>> {
  return request(config, `/releases/${encodeURIComponent(releaseId)}/usage`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getReleaseImpact(
  config: ApiConfig,
  releaseId: string,
): Promise<ApiResult<ReleaseImpactResponse>> {
  return request(config, `/releases/${encodeURIComponent(releaseId)}/impact`);
}

export function getProvenanceEntity(
  config: ApiConfig,
  entityId: string,
): Promise<ApiResult<ProvenanceEntityResponse>> {
  return request(config, `/provenance/entities/${encodeURIComponent(entityId)}`);
}

export function findProvenanceEntityByReference(
  config: ApiConfig,
  referenceType: string,
  referenceId: string,
): Promise<ApiResult<ProvenanceEntityResponse>> {
  const query = new URLSearchParams({
    reference_type: referenceType.trim(),
    reference_id: referenceId.trim(),
  });
  return request(config, `/provenance/entities/by-reference?${query.toString()}`);
}

interface ProvenanceGraphQuery {
  max_depth?: number;
  limit?: number;
  cursor?: string | null;
  target_entity_type?: string | null;
}

function provenanceGraphQuery(input: ProvenanceGraphQuery): string {
  const query = new URLSearchParams();
  if (input.max_depth !== undefined) query.set("max_depth", String(input.max_depth));
  if (input.limit !== undefined) query.set("limit", String(input.limit));
  if (input.cursor) query.set("cursor", input.cursor);
  if (input.target_entity_type?.trim()) query.set("target_entity_type", input.target_entity_type.trim());
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
}

export function getProvenanceLineage(
  config: ApiConfig,
  entityId: string,
  input: ProvenanceGraphQuery & { direction?: "upstream" | "downstream" } = {},
): Promise<ApiResult<ProvenanceLineagePage>> {
  const query = new URLSearchParams(provenanceGraphQuery(input).slice(1));
  query.set("direction", input.direction ?? "upstream");
  return request(config, `/provenance/entities/${encodeURIComponent(entityId)}/lineage?${query.toString()}`);
}

export function getProvenanceImpact(
  config: ApiConfig,
  entityId: string,
  input: ProvenanceGraphQuery = {},
): Promise<ApiResult<ProvenanceLineagePage>> {
  return request(
    config,
    `/provenance/entities/${encodeURIComponent(entityId)}/impact${provenanceGraphQuery(input)}`,
  );
}

export function getProvenanceCompleteness(
  config: ApiConfig,
  entityId: string,
): Promise<ApiResult<ProvenanceCompletenessReport>> {
  return request(config, `/provenance/entities/${encodeURIComponent(entityId)}/completeness`);
}

export interface AuditEventQuery {
  after_sequence?: number;
  limit?: number;
  action?: string | null;
  actor_id?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  outcome?: AuditOutcome | null;
  occurred_from?: string | null;
  occurred_to?: string | null;
}

export function listAuditEvents(
  config: ApiConfig,
  input: AuditEventQuery = {},
): Promise<ApiResult<AuditEventPage>> {
  const query = new URLSearchParams();
  query.set("after_sequence", String(input.after_sequence ?? 0));
  query.set("limit", String(input.limit ?? 25));
  for (const [key, value] of Object.entries(input)) {
    if (key === "after_sequence" || key === "limit" || value === null || value === undefined) continue;
    if (typeof value === "string" && !value.trim()) continue;
    query.set(key, String(value));
  }
  return request(config, `/audit/events?${query.toString()}`);
}

export function getAuditIntegrity(
  config: ApiConfig,
): Promise<ApiResult<AuditIntegrityReport>> {
  return request(config, "/audit/integrity");
}

export function getOperationalObservability(
  config: ApiConfig,
): Promise<ApiResult<OperationalSnapshotResponse>> {
  return request(config, "/operations/observability");
}

export async function downloadRelease(
  config: ApiConfig,
  releaseId: string,
): Promise<ApiResult<{ blob: Blob; filename: string }>> {
  const headers = authenticatedHeaders(config, {}, "application/vnd.cmp.release-manifest+json");
  const response = await fetch(
    endpoint(config, `/releases/${encodeURIComponent(releaseId)}/download`),
    { headers },
  );
  if (!response.ok) {
    return throwResponseError(response);
  }
  const header = response.headers.get("content-disposition") ?? "";
  const match = header.match(/filename="?([^";]+)"?/i);
  return {
    data: {
      blob: await response.blob(),
      filename: match?.[1] ?? `release-${releaseId}.cmp-release.json`,
    },
    etag: response.headers.get("etag"),
  };
}
