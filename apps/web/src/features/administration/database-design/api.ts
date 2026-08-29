export { ApiError } from "../../../shared/api/http";
export type { ApiConfig } from "../../../shared/api/http";
import type { ConfigurableCatalogRecordSearchResponse } from "../../catalog/contracts";
import type { ApiConfig, ApiResult } from "../../../shared/api/http";
import { searchConfigurableCatalogRecords as searchCatalogRecords } from "../../catalog";
export {
  catalogRevisionEtag,
  createConfigurableCatalogAttribute,
  createConfigurableCatalogDatabase,
  createConfigurableCatalogLayout,
  createConfigurableCatalogLinkType,
  createConfigurableCatalogProfile,
  createConfigurableCatalogSubset,
  createConfigurableCatalogTable,
  deleteConfigurableCatalogDraft,
  getDatabaseDesignAccess,
  getConfigurableCatalogAttributeRevision,
  listConfigurableCatalogAttributes,
  listConfigurableCatalogDatabases,
  listConfigurableCatalogLayouts,
  listConfigurableCatalogLinkTypes,
  listConfigurableCatalogProfiles,
  listConfigurableCatalogSubsets,
  listConfigurableCatalogTables,
  reviseConfigurableCatalogAttribute,
  reviseConfigurableCatalogDatabase,
  reviseConfigurableCatalogLayout,
  reviseConfigurableCatalogLinkType,
  reviseConfigurableCatalogProfile,
  reviseConfigurableCatalogSubset,
  reviseConfigurableCatalogTable,
  validateConfigurableCatalogPublication,
} from "../../catalog";

export function searchConfigurableCatalogRecords(
  config: ApiConfig,
  tableId: string,
): Promise<ApiResult<ConfigurableCatalogRecordSearchResponse>> {
  return searchCatalogRecords(config, {
    table_id: tableId,
    text: null,
    folder_id: null,
    discrete_filters: [],
    number_filters: [],
    facet_attribute_ids: [],
    offset: 0,
    limit: 50,
    published_only: false,
    sort_by: "name",
    sort_direction: "ascending",
  });
}
