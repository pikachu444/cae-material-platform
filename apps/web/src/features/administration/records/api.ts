/**
 * Administration Records API boundary. The root transport remains a bounded
 * compatibility source until issue #263 has zero root API consumers.
 */
export {
  compareConfigurableCatalogRecordRevisions,
  createConfigurableCatalogFolder,
  createConfigurableCatalogRecord,
  createConfigurableCatalogSubset,
  getConfigurableCatalogRecord,
  getMaterialDetail,
  listConfigurableCatalogAttributes,
  listConfigurableCatalogFolders,
  listConfigurableCatalogLayouts,
  listConfigurableCatalogRecordRevisions,
  listConfigurableCatalogSubsets,
  listConfigurableCatalogTables,
  listMaterials,
  previewConfigurableCatalogRecordRegistration,
  publishConfigurableCatalogRecordRegistration,
  reviseConfigurableCatalogFolder,
  reviseConfigurableCatalogRecord,
  searchConfigurableCatalogRecords,
  uploadGovernedTabularFile,
  validateConfigurableCatalogPublication,
  type ApiConfig,
} from "../../../api";
