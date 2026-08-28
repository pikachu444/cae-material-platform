import type {
  BulkExportBundleResponse,
  BulkExportCandidate,
  BulkExportJobResponse,
  BulkExportSourceRef,
  DataClassification,
  ExportSelectionResponse,
  MaterialCreateInput,
  MaterialDetail,
  MaterialLotCreateInput,
  MaterialLotResponse,
  MaterialResponse,
  MaterialReviseInput,
  MaterialRevisionComparison,
  MaterialRevisionList,
  MaterialStateCreateInput,
  MaterialStateResponse,
  MaterialStateReviseInput,
  ProcessDefinitionCreateInput,
  ProcessDefinitionResponse,
  ProcessKind,
  ProcessRunCreateInput,
  ProcessRunResponse,
  PropertySetCreateInput,
  PropertySetResponse,
  StateGenealogyCreateInput,
  StateGenealogyResponse,
} from "../../../types";

import {
  authenticatedHeaders,
  request,
  throwResponseError,
} from "../../../shared/api/http";

import type { ApiConfig, ApiResult } from "../../../shared/api/http";

export interface MaterialSearchRequest {
  query?: string;
  materialClass?: string;
  provider?: string;
  evidenceSource?: string;
  tableId?: string;
  folderId?: string | null;
  recordId?: string | null;
  includeDescendants?: boolean;
  offset?: number;
  limit?: number;
  sortBy?: "name" | "material_class";
  sortDirection?: "ascending" | "descending";
}

export interface MaterialSearchResponse {
  items: MaterialResponse[];
  total_count: number;
  offset: number;
  limit: number;
  facets: {
    material_classes: Array<{ material_class: string; count: number }>;
    providers: Array<{ provider: string; count: number }>;
    evidence_sources: Array<{ evidence_source: string; count: number }>;
  };
}

export function listMaterials(
  config: ApiConfig,
  requestOrQuery: MaterialSearchRequest | string,
  legacyMaterialClass?: string,
): Promise<ApiResult<MaterialSearchResponse>> {
  const searchRequest = typeof requestOrQuery === "string"
    ? { query: requestOrQuery, materialClass: legacyMaterialClass }
    : requestOrQuery;
  const search = new URLSearchParams({ limit: String(searchRequest.limit ?? 50), offset: String(searchRequest.offset ?? 0) });
  if (searchRequest.query?.trim()) {
    search.set("q", searchRequest.query.trim());
  }
  if (searchRequest.materialClass) {
    search.set("material_class", searchRequest.materialClass);
  }
  if (searchRequest.sortBy && searchRequest.sortBy !== "name") search.set("sort_by", searchRequest.sortBy);
  if (searchRequest.sortDirection && searchRequest.sortDirection !== "ascending") search.set("sort_direction", searchRequest.sortDirection);
  return request(config, `/materials?${search.toString()}`);
}


export function listBulkExportCandidates(
  config: ApiConfig,
  materialId: string,
): Promise<ApiResult<{ items: BulkExportCandidate[] }>> {
  const query = new URLSearchParams({ material_id: materialId });
  return request(config, `/bulk-export-candidates?${query.toString()}`);
}

export function createBulkExportSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    members: Array<{
      ordinal: number;
      source: BulkExportSourceRef;
      required: boolean;
      archive_path: string | null;
    }>;
    change_reason: string;
  },
): Promise<ApiResult<ExportSelectionResponse>> {
  return request(config, "/export-selections", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createBulkExportJob(
  config: ApiConfig,
  selectionId: string,
): Promise<ApiResult<BulkExportJobResponse>> {
  return request(config, "/export-jobs", {
    method: "POST",
    body: JSON.stringify({ export_selection_id: selectionId }),
  });
}

export function listBulkExportJobs(
  config: ApiConfig,
): Promise<ApiResult<{ items: BulkExportJobResponse[] }>> {
  return request(config, "/export-jobs");
}

export function listBulkExportBundles(
  config: ApiConfig,
): Promise<ApiResult<{ items: BulkExportBundleResponse[] }>> {
  return request(config, "/export-bundles");
}

export async function downloadBulkExportBundle(
  config: ApiConfig,
  bundleId: string,
): Promise<ApiResult<{ blob: Blob; filename: string }>> {
  const authorization = await request<{
    transfer_url: string;
    transfer_token: string;
    sha256: string;
    size_bytes: number;
    media_type: string;
  }>(config, `/export-bundles/${encodeURIComponent(bundleId)}/download-authorizations`, {
    method: "POST",
  });
  const transferUrl = authorization.data.transfer_url.startsWith("http")
    ? authorization.data.transfer_url
    : new URL(authorization.data.transfer_url, window.location.origin).toString();
  const headers = authenticatedHeaders(config, {}, "application/zip");
  headers.set("Artifact-Transfer-Token", authorization.data.transfer_token);
  const response = await fetch(transferUrl, { headers });
  if (!response.ok) {
    return throwResponseError(response);
  }
  return {
    data: {
      blob: await response.blob(),
      filename: `cmp-bulk-export-${bundleId}.zip`,
    },
    etag: response.headers.get("etag"),
  };
}

export function getMaterialDetail(
  config: ApiConfig,
  materialId: string,
): Promise<ApiResult<MaterialDetail>> {
  return request(config, `/materials/${encodeURIComponent(materialId)}`);
}

export function getMaterialRevisions(
  config: ApiConfig,
  materialId: string,
): Promise<ApiResult<MaterialRevisionList>> {
  return request(config, `/materials/${encodeURIComponent(materialId)}/revisions`);
}

export function compareMaterialRevisions(
  config: ApiConfig,
  materialId: string,
  leftRevisionId: string,
  rightRevisionId: string,
): Promise<ApiResult<MaterialRevisionComparison>> {
  const search = new URLSearchParams({
    left_revision_id: leftRevisionId,
    right_revision_id: rightRevisionId,
  });
  return request(
    config,
    `/materials/${encodeURIComponent(materialId)}/revisions:compare?${search.toString()}`,
  );
}

export function createMaterial(
  config: ApiConfig,
  input: MaterialCreateInput,
): Promise<ApiResult<MaterialResponse>> {
  return request(config, "/materials", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseMaterial(
  config: ApiConfig,
  materialId: string,
  etag: string,
  input: MaterialReviseInput,
): Promise<ApiResult<MaterialResponse>> {
  return request(config, `/materials/${encodeURIComponent(materialId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}

export function createMaterialState(
  config: ApiConfig,
  materialId: string,
  input: MaterialStateCreateInput,
): Promise<ApiResult<MaterialStateResponse>> {
  return request(config, `/materials/${encodeURIComponent(materialId)}/states`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseMaterialState(
  config: ApiConfig,
  materialStateId: string,
  etag: string,
  input: MaterialStateReviseInput,
): Promise<ApiResult<MaterialStateResponse>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}

export function listProcessDefinitions(
  config: ApiConfig,
  kind?: ProcessKind,
): Promise<ApiResult<{ items: ProcessDefinitionResponse[] }>> {
  const query = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  return request(config, `/process-definitions${query}`);
}

export function createProcessDefinition(
  config: ApiConfig,
  input: ProcessDefinitionCreateInput,
): Promise<ApiResult<ProcessDefinitionResponse>> {
  return request(config, "/process-definitions", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listMaterialLots(
  config: ApiConfig,
  materialId: string,
): Promise<ApiResult<{ items: MaterialLotResponse[] }>> {
  return request(config, `/materials/${encodeURIComponent(materialId)}/lots`);
}

export function createMaterialLot(
  config: ApiConfig,
  materialId: string,
  input: MaterialLotCreateInput,
): Promise<ApiResult<MaterialLotResponse>> {
  return request(config, `/materials/${encodeURIComponent(materialId)}/lots`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getStateGenealogy(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<StateGenealogyResponse | null>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/genealogy`);
}

export function createStateGenealogy(
  config: ApiConfig,
  materialStateId: string,
  input: StateGenealogyCreateInput,
): Promise<ApiResult<StateGenealogyResponse>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/genealogy`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseStateGenealogy(
  config: ApiConfig,
  genealogyId: string,
  etag: string,
  input: StateGenealogyCreateInput,
): Promise<ApiResult<StateGenealogyResponse>> {
  return request(config, `/state-genealogies/${encodeURIComponent(genealogyId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}

export function listProcessRuns(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: ProcessRunResponse[] }>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/process-runs`);
}

export function createProcessRun(
  config: ApiConfig,
  materialStateId: string,
  input: ProcessRunCreateInput,
): Promise<ApiResult<ProcessRunResponse>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/process-runs`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getPropertySet(
  config: ApiConfig,
  propertySetId: string,
): Promise<ApiResult<PropertySetResponse>> {
  return request(config, `/property-sets/${encodeURIComponent(propertySetId)}`);
}

export function createPropertySet(
  config: ApiConfig,
  materialStateId: string,
  input: PropertySetCreateInput,
): Promise<ApiResult<PropertySetResponse>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/property-sets`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function revisePropertySet(
  config: ApiConfig,
  propertySetId: string,
  etag: string,
  input: PropertySetCreateInput,
): Promise<ApiResult<PropertySetResponse>> {
  return request(config, `/property-sets/${encodeURIComponent(propertySetId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}
