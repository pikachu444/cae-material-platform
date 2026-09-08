import { ApiError, queryString, requestBytes, requestJson } from "../../shared/api/http-client";
import type { RevisionPin } from "../test-data/api";
import type { CurveDefinitionContract, CurveSeriesPreviewContract } from "../../shared/model/curve-contracts";

export interface ProcessingOutputRow {
  id: string;
  revisionId: string;
  revision: RevisionPin;
  label: string;
  sourceDocument: { aggregate_id: string; revision_id: string };
  sourceDocumentSha256: string;
  mappingProfile: { aggregate_id: string; revision_id: string } | null;
  mappingProfileSha256: string | null;
  steps: Array<{ method_id: string; method_version: string; options: Record<string, unknown> }>;
  independentQuantity: string;
  stageCount: number;
  finalPointCount: number;
  outputSha256: string;
  exportProvenance: {
    material?: { aggregate_id: string; revision_id: string };
    material_state?: { aggregate_id: string; revision_id: string };
    test_run?: { aggregate_id: string; revision_id: string };
  } | null;
}

export interface ProcessingStage {
  ordinal: number;
  method_id: string;
  point_count: number;
  series: Array<{ quantity: string; unit: string; values: Array<number | null> }>;
  curveDefinition: CurveDefinitionContract | null;
  curveSeries: CurveSeriesPreviewContract | null;
  diagnostics?: string[];
}

export interface ProcessingOutputDetail {
  row: ProcessingOutputRow;
  stages: ProcessingStage[];
  outputBytes: Uint8Array;
}

interface ApiProcessingOutput {
  processing_output_id: string;
  current_revision: RevisionPin;
  label: string;
  source_document: { aggregate_id: string; revision_id: string };
  source_document_sha256: string;
  mapping_profile: { aggregate_id: string; revision_id: string } | null;
  mapping_profile_sha256: string | null;
  steps: ProcessingOutputRow["steps"];
  independent_quantity: string;
  stage_count: number;
  final_point_count: number;
  output_sha256: string;
  export_provenance: ProcessingOutputRow["exportProvenance"];
}

interface ApiOutputList { items: ApiProcessingOutput[] }

interface ApiProcessingStage {
  ordinal: number;
  method_id: string;
  point_count: number;
  series: Array<{ quantity: string; unit: string; values: Array<number | null> }>;
  curve_definition?: CurveDefinitionContract | null;
  diagnostics?: string[];
}

function mapStage(value: ApiProcessingStage): ProcessingStage {
  const curveDefinition = value.curve_definition ?? null;
  const curveSeries = curveDefinition ? {
    point_count: value.point_count,
    returned_point_count: value.series[0]?.values.length ?? 0,
    sampled: false,
    indices: Array.from({ length: value.series[0]?.values.length ?? 0 }, (_, index) => index),
    channels: value.series.map((item) => ({ key: item.quantity, values: item.values })),
    deviations: [],
    source_counts: [],
  } satisfies CurveSeriesPreviewContract : null;
  return {
    ordinal: value.ordinal,
    method_id: value.method_id,
    point_count: value.point_count,
    series: value.series,
    curveDefinition,
    curveSeries,
    diagnostics: value.diagnostics,
  };
}

function mapRow(value: ApiProcessingOutput): ProcessingOutputRow {
  return {
    id: value.processing_output_id,
    revisionId: value.current_revision.id,
    revision: value.current_revision,
    label: value.label,
    sourceDocument: value.source_document,
    sourceDocumentSha256: value.source_document_sha256,
    mappingProfile: value.mapping_profile,
    mappingProfileSha256: value.mapping_profile_sha256,
    steps: value.steps,
    independentQuantity: value.independent_quantity,
    stageCount: value.stage_count,
    finalPointCount: value.final_point_count,
    outputSha256: value.output_sha256,
    exportProvenance: value.export_provenance,
  };
}

export async function listProcessingOutputs(signal?: AbortSignal): Promise<ProcessingOutputRow[]> {
  const response = await requestJson<ApiOutputList>("/api/v1/processing-outputs", { signal });
  return response.items.map(mapRow).sort((left, right) => left.label.localeCompare(right.label) || left.id.localeCompare(right.id));
}

export async function readProcessingOutput(
  id: string,
  revisionId: string,
  signal?: AbortSignal,
): Promise<ProcessingOutputDetail> {
  const query = queryString({ revision_id: revisionId });
  const [output, raw] = await Promise.all([
    requestJson<ApiProcessingOutput>(`/api/v1/processing-outputs/${id}${query}`, { signal }),
    requestBytes(`/api/v1/processing-outputs/${id}/content${query}`, { signal }),
  ]);
  if (output.processing_output_id !== id || output.current_revision.id !== revisionId) {
    throw new ApiError(409, "PROCESSING_OUTPUT_REVISION_MISMATCH", "The Processing Output response is not the pinned revision.");
  }
  const parsed = JSON.parse(new TextDecoder().decode(raw.bytes)) as { output_id?: string; result?: { stages?: ApiProcessingStage[] } };
  if (parsed.output_id !== id) {
    throw new ApiError(409, "PROCESSING_OUTPUT_IDENTITY_MISMATCH", "The stored Processing Output bytes do not match the selected output.");
  }
  return { row: mapRow(output), stages: (parsed.result?.stages ?? []).map(mapStage), outputBytes: raw.bytes };
}

export async function downloadProcessingOutput(id: string, revisionId: string, signal?: AbortSignal) {
  return requestBytes(`/api/v1/processing-outputs/${id}/content${queryString({ revision_id: revisionId })}`, { signal });
}
