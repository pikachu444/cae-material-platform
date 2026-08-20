import type {
  ConfigurableAttributeContent,
  ConfigurableAttributeRevision,
  ConfigurableAttributeResponse,
  ConfigurableCatalogRecordSearchResponse,
  ConfigurableDatabaseContent,
  ConfigurableDatabaseResponse,
  ConfigurableLayoutItem,
  ConfigurableLayoutResponse,
  ConfigurableLinkTypeContent,
  ConfigurableLinkTypeResponse,
  ConfigurableProfileContent,
  ConfigurableProfileResponse,
  ConfigurableSubsetResponse,
  ConfigurableTableContent,
  ConfigurableTableResponse,
  DataClassification,
  ProductAccessSummary,
  RevisionMetadata,
} from "../../types";
import { request } from "../api/http";
import type { ApiConfig, ApiResult } from "../api/http";

export type ConfigurableDefinitionKind =
  | "database"
  | "profile"
  | "table"
  | "attribute"
  | "layout"
  | "subset"
  | "link-type";

export interface ConfigurablePublicationValidation {
  aggregate_type: string;
  aggregate_id: string;
  revision_id: string;
  valid: boolean;
  errors: string[];
}

export function getDatabaseDesignAccess(
  config: ApiConfig,
): Promise<ApiResult<ProductAccessSummary>> {
  return request(config, "/product-access/me");
}

export function catalogRevisionEtag(revision: RevisionMetadata): string {
  return `"revision:${revision.revision_no}:sha256:${revision.content_hash}"`;
}

export function listConfigurableCatalogDatabases(
  config: ApiConfig,
): Promise<ApiResult<{ items: ConfigurableDatabaseResponse[] }>> {
  return request(config, "/catalog/databases");
}

export function createConfigurableCatalogDatabase(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: ConfigurableDatabaseContent;
    change_reason: string;
  },
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
  input: {
    classification: DataClassification;
    content: ConfigurableProfileContent;
    change_reason: string;
  },
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

export function listConfigurableCatalogTables(
  config: ApiConfig,
): Promise<ApiResult<{ items: ConfigurableTableResponse[] }>> {
  return request(config, "/catalog/tables");
}

export function searchConfigurableCatalogRecords(
  config: ApiConfig,
  tableId: string,
): Promise<ApiResult<ConfigurableCatalogRecordSearchResponse>> {
  return request(config, "/catalog/records:search", {
    method: "POST",
    body: JSON.stringify({
      table_id: tableId,
      text: null,
      folder_id: null,
      discrete_filters: [],
      number_filters: [],
      facet_attribute_ids: [],
      offset: 0,
      limit: 1,
      published_only: false,
      sort_by: "name",
      sort_direction: "ascending",
    }),
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
  return request(config, "/catalog/tables", { method: "POST", body: JSON.stringify(input) });
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
    description?: string | null;
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
    description?: string | null;
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
    description?: string | null;
    filter_definition: Record<string, unknown>;
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
    description?: string | null;
    filter_definition: Record<string, unknown>;
    change_reason: string;
  },
): Promise<ApiResult<ConfigurableSubsetResponse>> {
  return request(config, `/catalog/subsets/${encodeURIComponent(subsetId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": catalogRevisionEtag(revision) },
    body: JSON.stringify(input),
  });
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
  return request(config, "/catalog/link-types", { method: "POST", body: JSON.stringify(input) });
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

export function validateConfigurableCatalogPublication(
  config: ApiConfig,
  input: { aggregate_type: string; aggregate_id: string; revision_id: string },
): Promise<ApiResult<ConfigurablePublicationValidation>> {
  return request(config, "/catalog/publication:validate", {
    method: "POST",
    body: JSON.stringify(input),
  });
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
