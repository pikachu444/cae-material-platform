import type {
  CatalogCurvePreviewResponse,
  CatalogDataCategory,
  CatalogExplorerChildrenResponse,
  CatalogWorkflowGraphResponse,
  ConfigurableAttributeContent,
  ConfigurableAttributeResponse,
  ConfigurableAttributeRevision,
  ConfigurableCatalogFolderResponse,
  ConfigurableCatalogRecordComparison,
  ConfigurableCatalogRecordContent,
  ConfigurableCatalogRecordResponse,
  ConfigurableCatalogRecordRevisionList,
  ConfigurableCatalogRecordSearchResponse,
  ConfigurableDatabaseContent,
  ConfigurableDatabaseResponse,
  ConfigurableLayoutItem,
  ConfigurableLayoutResponse,
  ConfigurableLinkTypeContent,
  ConfigurableLinkTypeResponse,
  ConfigurableProfileContent,
  ConfigurableProfileResponse,
  ConfigurableRecordLinkContent,
  ConfigurableRecordLinkResponse,
  ConfigurableRecordLinkView,
  ConfigurableRegistrationPreviewResponse,
  ConfigurableSubsetResponse,
  ConfigurableTableContent,
  ConfigurableTableResponse,
  DomainBindingKind,
  DomainRevisionBinding,
} from "../contracts";
import type { GovernedTabularFileFormat } from "../../test-data/contracts";
import type { ProductAccessSummary } from "../../../shared/api/auth-contracts";
import type {
  DataClassification,
  RevisionMetadata,
} from "../../../shared/model/core-contracts";

import {
  request,
} from "../../../shared/api/http";

import type { ApiConfig, ApiResult } from "../../../shared/api/http";

export function listConfigurableCatalogTables(
  config: ApiConfig,
): Promise<ApiResult<{ items: ConfigurableTableResponse[] }>> {
  return request(config, "/catalog/tables");
}

export function listConfigurableCatalogDatabases(
  config: ApiConfig,
): Promise<ApiResult<{ items: ConfigurableDatabaseResponse[] }>> {
  return request(config, "/catalog/databases");
}

export function createConfigurableCatalogDatabase(
  config: ApiConfig,
  input: { classification: DataClassification; content: ConfigurableDatabaseContent; change_reason: string },
): Promise<ApiResult<ConfigurableDatabaseResponse>> {
  return request(config, "/catalog/databases", { method: "POST", body: JSON.stringify(input) });
}

export function reviseConfigurableCatalogDatabase(
  config: ApiConfig,
  databaseId: string,
  etag: string,
  input: { content: ConfigurableDatabaseContent; change_reason: string },
): Promise<ApiResult<ConfigurableDatabaseResponse>> {
  return request(config, `/catalog/databases/${encodeURIComponent(databaseId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}

export function listConfigurableCatalogProfiles(
  config: ApiConfig,
  databaseId?: string,
): Promise<ApiResult<{ items: ConfigurableProfileResponse[] }>> {
  const suffix = databaseId ? `?database_id=${encodeURIComponent(databaseId)}` : "";
  return request(config, `/catalog/profiles${suffix}`);
}

export function createConfigurableCatalogProfile(
  config: ApiConfig,
  input: { classification: DataClassification; content: ConfigurableProfileContent; change_reason: string },
): Promise<ApiResult<ConfigurableProfileResponse>> {
  return request(config, "/catalog/profiles", { method: "POST", body: JSON.stringify(input) });
}

export function reviseConfigurableCatalogProfile(
  config: ApiConfig,
  profileId: string,
  etag: string,
  input: { content: ConfigurableProfileContent; change_reason: string },
): Promise<ApiResult<ConfigurableProfileResponse>> {
  return request(config, `/catalog/profiles/${encodeURIComponent(profileId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}

export function listCatalogExplorerTables(
  config: ApiConfig,
): Promise<ApiResult<{ items: ConfigurableTableResponse[] }>> {
  return request(config, "/catalog/explorer/tables");
}

export function listCatalogExplorerChildren(
  config: ApiConfig,
  tableId: string,
  parentFolderId: string | null,
): Promise<ApiResult<CatalogExplorerChildrenResponse>> {
  const suffix = parentFolderId
    ? `?parent_folder_id=${encodeURIComponent(parentFolderId)}`
    : "";
  return request(
    config,
    `/catalog/explorer/tables/${encodeURIComponent(tableId)}/children${suffix}`,
  );
}

export function listConfigurableCatalogLinkTypes(
  config: ApiConfig,
): Promise<ApiResult<{ items: ConfigurableLinkTypeResponse[] }>> {
  return request(config, "/catalog/link-types");
}

export function createConfigurableCatalogLinkType(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: ConfigurableLinkTypeContent;
    change_reason: string;
  },
): Promise<ApiResult<ConfigurableLinkTypeResponse>> {
  return request(config, "/catalog/link-types", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listConfigurableRecordLinks(
  config: ApiConfig,
  recordId: string,
  revisionId: string | null,
  includeInactive = false,
): Promise<ApiResult<{ items: ConfigurableRecordLinkView[] }>> {
  const parameters = new URLSearchParams();
  if (revisionId) parameters.set("revision_id", revisionId);
  if (includeInactive) parameters.set("include_inactive", "true");
  const query = parameters.toString();
  return request(
    config,
    `/catalog/records/${encodeURIComponent(recordId)}/links${query ? `?${query}` : ""}`,
  );
}

export function createConfigurableRecordLink(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: ConfigurableRecordLinkContent;
    change_reason: string;
  },
): Promise<ApiResult<ConfigurableRecordLinkResponse>> {
  return request(config, "/catalog/record-links", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseConfigurableRecordLink(
  config: ApiConfig,
  recordLinkId: string,
  etag: string,
  input: { content: ConfigurableRecordLinkContent; change_reason: string },
): Promise<ApiResult<ConfigurableRecordLinkResponse>> {
  return request(config, `/catalog/record-links/${encodeURIComponent(recordLinkId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}

export function getCatalogWorkflowGraph(
  config: ApiConfig,
  recordId: string,
  revisionId: string,
  depth = 3,
  publishedOnly = false,
): Promise<ApiResult<CatalogWorkflowGraphResponse>> {
  const query = new URLSearchParams({ depth: String(depth) });
  if (publishedOnly) query.set("published_only", "true");
  return request(
    config,
    `/catalog/workflow-explorer/${encodeURIComponent(recordId)}/revisions/${encodeURIComponent(revisionId)}?${query.toString()}`,
  );
}

export function bindCatalogRecordDomainRevision(
  config: ApiConfig,
  recordId: string,
  revisionId: string,
  input: { kind: DomainBindingKind; object_id: string; revision_id: string },
): Promise<ApiResult<DomainRevisionBinding>> {
  return request(
    config,
    `/catalog/records/${encodeURIComponent(recordId)}/revisions/${encodeURIComponent(revisionId)}/domain-binding`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function resolveCatalogDomainRevision(
  config: ApiConfig,
  kind: DomainBindingKind,
  objectId: string,
  revisionId: string,
): Promise<ApiResult<DomainRevisionBinding | null>> {
  const parameters = new URLSearchParams({
    kind,
    object_id: objectId,
    revision_id: revisionId,
  });
  return request(config, `/catalog/domain-bindings:resolve?${parameters.toString()}`);
}

export function catalogRevisionEtag(revision: RevisionMetadata): string {
  return `"revision:${revision.revision_no}:sha256:${revision.content_hash}"`;
}

export function reviseConfigurableCatalogLinkType(
  config: ApiConfig,
  linkTypeId: string,
  revision: RevisionMetadata,
  input: { content: ConfigurableLinkTypeContent; change_reason: string },
): Promise<ApiResult<ConfigurableLinkTypeResponse>> {
  return request(config, `/catalog/link-types/${encodeURIComponent(linkTypeId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": catalogRevisionEtag(revision) },
    body: JSON.stringify(input),
  });
}

export interface ConfigurablePublicationValidation {
  aggregate_type: string;
  aggregate_id: string;
  revision_id: string;
  valid: boolean;
  errors: string[];
}

export function validateConfigurableCatalogPublication(
  config: ApiConfig,
  input: { aggregate_type: string; aggregate_id: string; revision_id: string },
): Promise<ApiResult<ConfigurablePublicationValidation>> {
  return request(config, "/catalog/publication:validate", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function publishConfigurableCatalogRevision(
  config: ApiConfig,
  input: { aggregate_type: string; aggregate_id: string; revision_id: string },
): Promise<ApiResult<ConfigurablePublicationValidation>> {
  return request(config, "/catalog/publication:publish", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createConfigurableCatalogTable(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: ConfigurableTableContent;
    change_reason: string;
    profile_id?: string | null;
    profile_revision_id?: string | null;
  },
): Promise<ApiResult<ConfigurableTableResponse>> {
  return request(config, "/catalog/tables", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseConfigurableCatalogTable(
  config: ApiConfig,
  tableId: string,
  revision: RevisionMetadata,
  input: { content: ConfigurableTableContent; change_reason: string },
): Promise<ApiResult<ConfigurableTableResponse>> {
  return request(config, `/catalog/tables/${encodeURIComponent(tableId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": catalogRevisionEtag(revision) },
    body: JSON.stringify(input),
  });
}

export function listConfigurableCatalogAttributes(
  config: ApiConfig,
  tableId: string,
): Promise<ApiResult<{ items: ConfigurableAttributeResponse[] }>> {
  return request(config, `/catalog/tables/${encodeURIComponent(tableId)}/attributes`);
}

export function createConfigurableCatalogAttribute(
  config: ApiConfig,
  tableId: string,
  input: { content: ConfigurableAttributeContent; change_reason: string },
): Promise<ApiResult<ConfigurableAttributeResponse>> {
  return request(config, `/catalog/tables/${encodeURIComponent(tableId)}/attributes`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseConfigurableCatalogAttribute(
  config: ApiConfig,
  attributeId: string,
  revision: RevisionMetadata,
  input: { content: ConfigurableAttributeContent; change_reason: string },
): Promise<ApiResult<ConfigurableAttributeResponse>> {
  return request(config, `/catalog/attributes/${encodeURIComponent(attributeId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": catalogRevisionEtag(revision) },
    body: JSON.stringify(input),
  });
}

export function listConfigurableCatalogLayouts(
  config: ApiConfig,
  tableId: string,
): Promise<ApiResult<{ items: ConfigurableLayoutResponse[] }>> {
  return request(config, `/catalog/tables/${encodeURIComponent(tableId)}/layouts`);
}

export function createConfigurableCatalogLayout(
  config: ApiConfig,
  tableId: string,
  input: {
    table_revision_id: string;
    name: string;
    description: string | null;
    items: ConfigurableLayoutItem[];
    change_reason: string;
  },
): Promise<ApiResult<ConfigurableLayoutResponse>> {
  return request(config, `/catalog/tables/${encodeURIComponent(tableId)}/layouts`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseConfigurableCatalogLayout(
  config: ApiConfig,
  layoutId: string,
  revision: RevisionMetadata,
  input: {
    table_revision_id: string;
    name: string;
    description: string | null;
    items: ConfigurableLayoutItem[];
    change_reason: string;
  },
): Promise<ApiResult<ConfigurableLayoutResponse>> {
  return request(config, `/catalog/layouts/${encodeURIComponent(layoutId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": catalogRevisionEtag(revision) },
    body: JSON.stringify(input),
  });
}

export function listConfigurableCatalogSubsets(
  config: ApiConfig,
  tableId: string,
): Promise<ApiResult<{ items: ConfigurableSubsetResponse[] }>> {
  return request(config, `/catalog/tables/${encodeURIComponent(tableId)}/subsets`);
}

export function createConfigurableCatalogSubset(
  config: ApiConfig,
  tableId: string,
  input: {
    table_revision_id: string;
    name: string;
    description: string | null;
    filter_definition: Record<string, unknown> | null;
    change_reason: string;
  },
): Promise<ApiResult<ConfigurableSubsetResponse>> {
  return request(config, `/catalog/tables/${encodeURIComponent(tableId)}/subsets`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseConfigurableCatalogSubset(
  config: ApiConfig,
  subsetId: string,
  revision: RevisionMetadata,
  input: {
    table_revision_id: string;
    name: string;
    description: string | null;
    filter_definition: Record<string, unknown> | null;
    change_reason: string;
  },
): Promise<ApiResult<ConfigurableSubsetResponse>> {
  return request(config, `/catalog/subsets/${encodeURIComponent(subsetId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": catalogRevisionEtag(revision) },
    body: JSON.stringify(input),
  });
}

export function listConfigurableCatalogFolders(
  config: ApiConfig,
  tableId: string,
): Promise<ApiResult<{ items: ConfigurableCatalogFolderResponse[] }>> {
  return request(config, `/catalog/tables/${encodeURIComponent(tableId)}/folders`);
}

export function createConfigurableCatalogFolder(
  config: ApiConfig,
  tableId: string,
  input: {
    classification: DataClassification;
    content: ConfigurableCatalogFolderResponse["content"];
    change_reason: string;
  },
): Promise<ApiResult<ConfigurableCatalogFolderResponse>> {
  return request(config, `/catalog/tables/${encodeURIComponent(tableId)}/folders`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function searchConfigurableCatalogRecords(
  config: ApiConfig,
  input: {
    table_id?: string | null;
    data_category?: CatalogDataCategory | null;
    text: string | null;
    folder_id: string | null;
    record_id?: string | null;
    discrete_filters: Array<{ attribute_definition_id: string; values: string[] }>;
    number_filters: Array<{
      attribute_definition_id: string;
      minimum: string | null;
      maximum: string | null;
    }>;
    facet_attribute_ids: string[];
    offset?: number;
    limit?: number;
    domain_binding_kind?: DomainBindingKind;
    include_descendants?: boolean;
    sort_by?: "name" | "external_key" | "attribute";
    sort_attribute_id?: string;
    sort_direction?: "ascending" | "descending";
    published_only?: boolean;
  },
): Promise<ApiResult<ConfigurableCatalogRecordSearchResponse>> {
  return request(config, "/catalog/records:search", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createConfigurableCatalogRecord(
  config: ApiConfig,
  tableId: string,
  input: {
    classification: DataClassification;
    content: ConfigurableCatalogRecordContent;
    change_reason: string;
  },
): Promise<ApiResult<ConfigurableCatalogRecordResponse>> {
  return request(config, `/catalog/tables/${encodeURIComponent(tableId)}/records`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseConfigurableCatalogFolder(
  config: ApiConfig,
  folderId: string,
  revision: RevisionMetadata,
  input: {
    content: ConfigurableCatalogFolderResponse["content"];
    change_reason: string;
  },
): Promise<ApiResult<ConfigurableCatalogFolderResponse>> {
  return request(config, `/catalog/folders/${encodeURIComponent(folderId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": catalogRevisionEtag(revision) },
    body: JSON.stringify(input),
  });
}

export function previewConfigurableCatalogRecordRegistration(
  config: ApiConfig,
  input: {
    table_id: string;
    table_revision_id: string;
    rows?: Array<Record<string, unknown>>;
    mapping: Record<string, string | { attribute: string; unit: string | null }>;
    common_material_state?: Record<string, string> | null;
    raw_asset_id?: string;
    raw_artifact_id?: string;
    file_format?: GovernedTabularFileFormat;
    sheet_name?: string | null;
    header_row?: number;
    encoding?: string;
    delimiter?: string | null;
    decimal_separator?: "." | ",";
    corrections?: Record<number, Record<string, string>>;
  },
): Promise<ApiResult<ConfigurableRegistrationPreviewResponse>> {
  return request(config, "/catalog/record-registrations:preview", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function publishConfigurableCatalogRecordRegistration(
  config: ApiConfig,
  input: {
    token: string;
    table_id: string;
    table_revision_id: string;
    change_reason: string;
    classification: DataClassification;
  },
): Promise<ApiResult<{ items: ConfigurableCatalogRecordResponse[] }>> {
  return request(config, "/catalog/record-registrations:publish", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getConfigurableCatalogRecord(
  config: ApiConfig,
  recordId: string,
): Promise<ApiResult<ConfigurableCatalogRecordResponse>> {
  return request(config, `/catalog/records/${encodeURIComponent(recordId)}`);
}

export function reviseConfigurableCatalogRecord(
  config: ApiConfig,
  recordId: string,
  etag: string,
  input: { content: ConfigurableCatalogRecordContent; change_reason: string },
): Promise<ApiResult<ConfigurableCatalogRecordResponse>> {
  return request(config, `/catalog/records/${encodeURIComponent(recordId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}

export function listConfigurableCatalogRecordRevisions(
  config: ApiConfig,
  recordId: string,
): Promise<ApiResult<ConfigurableCatalogRecordRevisionList>> {
  return request(config, `/catalog/records/${encodeURIComponent(recordId)}/revisions`);
}

export function previewExactCatalogCurveValue(
  config: ApiConfig,
  recordId: string,
  recordRevisionId: string,
  attributeDefinitionId: string,
  maximumPoints = 1000,
): Promise<ApiResult<CatalogCurvePreviewResponse>> {
  const query = new URLSearchParams({ maximum_points: String(maximumPoints) });
  return request(
    config,
    `/catalog/records/${encodeURIComponent(recordId)}/revisions/${encodeURIComponent(recordRevisionId)}/curve-values/${encodeURIComponent(attributeDefinitionId)}/preview?${query.toString()}`,
  );
}

export function compareConfigurableCatalogRecordRevisions(
  config: ApiConfig,
  recordId: string,
  fromRevisionId: string,
  toRevisionId: string,
): Promise<ApiResult<ConfigurableCatalogRecordComparison>> {
  const query = new URLSearchParams({
    from_revision_id: fromRevisionId,
    to_revision_id: toRevisionId,
  });
  return request(
    config,
    `/catalog/records/${encodeURIComponent(recordId)}/revisions:compare?${query.toString()}`,
  );
}

export type ConfigurableDefinitionKind =
  | "database"
  | "profile"
  | "table"
  | "attribute"
  | "layout"
  | "subset"
  | "link-type";

export function getDatabaseDesignAccess(
  config: ApiConfig,
): Promise<ApiResult<ProductAccessSummary>> {
  return request(config, "/product-access/me");
}

export function getConfigurableCatalogAttributeRevision(
  config: ApiConfig,
  attributeId: string,
  revisionId: string,
): Promise<ApiResult<ConfigurableAttributeRevision>> {
  return request(
    config,
    `/catalog/attributes/${encodeURIComponent(attributeId)}/revisions/${encodeURIComponent(revisionId)}`,
  );
}

export function deleteConfigurableCatalogDraft(
  config: ApiConfig,
  kind: ConfigurableDefinitionKind,
  aggregateId: string,
  revision: RevisionMetadata,
): Promise<ApiResult<undefined>> {
  const paths: Record<ConfigurableDefinitionKind, string> = {
    database: `/catalog/databases/${encodeURIComponent(aggregateId)}`,
    profile: `/catalog/profiles/${encodeURIComponent(aggregateId)}`,
    table: `/catalog/tables/${encodeURIComponent(aggregateId)}`,
    attribute: `/catalog/attributes/${encodeURIComponent(aggregateId)}`,
    layout: `/catalog/layouts/${encodeURIComponent(aggregateId)}`,
    subset: `/catalog/subsets/${encodeURIComponent(aggregateId)}`,
    "link-type": `/catalog/link-types/${encodeURIComponent(aggregateId)}`,
  };
  return request(config, paths[kind], {
    method: "DELETE",
    headers: { "If-Match": catalogRevisionEtag(revision) },
  });
}
