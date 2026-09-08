import { ApiError, queryString, requestBytes, requestJson } from "../../shared/api/http-client";
import type { CurveDefinitionContract, CurveSeriesPreviewContract } from "../../shared/model/curve-contracts";

export interface RevisionPin {
  id: string;
  revision_no: number;
  schema_id: string;
  schema_version: string;
  content_hash: string;
  created_at: string;
}

export interface TestDataChannelSummary {
  key: string;
  name: string;
  quantity_semantics: string;
  axis_role: "independent" | "dependent" | "deviation";
  original_unit_string: string;
  normalized_unit: string;
  point_count: number;
  missing_count: number;
}

export interface TestDataRow {
  id: string;
  revisionId: string;
  revision: RevisionPin;
  documentKey: string;
  materialMaker: string;
  materialGrade: string;
  lotBatch: string | null;
  testDate: string;
  operator: string;
  laboratory: string;
  method: string;
  specimenId: string;
  pointCount: number;
  conditions?: TestDataCondition[];
  source?: { file_name: string; media_type: string; sha256: string };
  channels: TestDataChannelSummary[];
  materialId?: string;
  materialStateId?: string;
  materialStateRevisionId?: string;
}

export interface TestDataCondition {
  key: string;
  quantity_semantics: string;
  original_value: string;
  original_unit_string: string;
  normalized_value: string;
  normalized_unit: string;
}

export interface CanonicalChannel {
  key: string;
  name: string;
  quantity_semantics: string;
  axis_role: string;
  original_unit_string: string;
  normalized_unit: string;
  normalized_values: Array<number | string | null>;
}

export interface CurvePreview {
  curve_metadata?: {
    state?: string;
    metadata_state?: string;
    definition?: CurveDefinitionContract;
  };
  curve_series?: CurveSeriesPreviewContract;
}

export interface TestDataDetail {
  row: TestDataRow;
  conditions: TestDataCondition[];
  specimenDescription?: string;
  source?: { file_name: string; media_type: string; sha256: string };
  channels: CanonicalChannel[];
  curve: CurvePreview | null;
  canonicalBytes: Uint8Array;
}

interface ApiTestDataDocument {
  test_data_document_id: string;
  current_revision: RevisionPin;
  document_key: string;
  material_maker: string;
  material_grade: string;
  lot_batch: string | null;
  test_date: string;
  operator: string;
  laboratory: string;
  method: string;
  specimen_id: string;
  point_count: number;
  conditions?: TestDataCondition[];
  source?: { file_name: string; media_type: string; sha256: string };
  channels: TestDataChannelSummary[];
  governed_source?: {
    material?: { aggregate_id: string; revision_id: string };
    material_state?: { aggregate_id: string; revision_id: string };
  } | null;
}

interface ApiTestDataList { items: ApiTestDataDocument[] }

function mapRow(value: ApiTestDataDocument): TestDataRow {
  return {
    id: value.test_data_document_id,
    revisionId: value.current_revision.id,
    revision: value.current_revision,
    documentKey: value.document_key,
    materialMaker: value.material_maker,
    materialGrade: value.material_grade,
    lotBatch: value.lot_batch,
    testDate: value.test_date,
    operator: value.operator,
    laboratory: value.laboratory,
    method: value.method,
    specimenId: value.specimen_id,
    pointCount: value.point_count,
    channels: value.channels,
    conditions: value.conditions ?? [],
    source: value.source,
    materialId: value.governed_source?.material?.aggregate_id,
    materialStateId: value.governed_source?.material_state?.aggregate_id,
    materialStateRevisionId: value.governed_source?.material_state?.revision_id,
  };
}

export async function listTestData(signal?: AbortSignal): Promise<TestDataRow[]> {
  const response = await requestJson<ApiTestDataList>("/api/v1/test-data-documents", { signal });
  return response.items.map(mapRow).sort((left, right) => left.documentKey.localeCompare(right.documentKey) || left.id.localeCompare(right.id));
}

export async function readTestData(
  id: string,
  revisionId: string,
  signal?: AbortSignal,
): Promise<TestDataDetail> {
  const query = queryString({ revision_id: revisionId });
  const [document, curve, canonical] = await Promise.all([
    requestJson<ApiTestDataDocument>(`/api/v1/test-data-documents/${id}${query}`, { signal }),
    requestJson<CurvePreview>(`/api/v1/test-data-documents/${id}/revisions/${revisionId}/curve?maximum_points=500`, { signal }),
    requestBytes(`/api/v1/test-data-documents/${id}/revisions/${revisionId}/content`, { signal }),
  ]);
  if (document.test_data_document_id !== id || document.current_revision.id !== revisionId) {
    throw new ApiError(409, "TEST_DATA_REVISION_MISMATCH", "The Test Data response is not the pinned document revision.");
  }
  const parsed: {
    document_id?: string;
    conditions?: TestDataCondition[];
    specimen?: { description?: string | null };
    source?: { file_name: string; media_type: string; sha256: string };
    channels?: CanonicalChannel[];
  } = JSON.parse(new TextDecoder().decode(canonical.bytes)) as typeof parsed;
  if (parsed.document_id !== document.document_key) {
    throw new ApiError(409, "TEST_DATA_IDENTITY_MISMATCH", "The canonical Test Data bytes do not match the selected document.");
  }
  return {
    row: mapRow(document),
    conditions: parsed.conditions ?? [],
    specimenDescription: parsed.specimen?.description ?? undefined,
    source: parsed.source,
    channels: parsed.channels ?? [],
    curve,
    canonicalBytes: canonical.bytes,
  };
}

export async function downloadTestData(
  id: string,
  revisionId: string,
  signal?: AbortSignal,
) {
  return requestBytes(`/api/v1/test-data-documents/${id}/revisions/${revisionId}/content`, { signal });
}
