import type {
  ExportTarget,
  ElastoplasticCardCreatedResponse,
  ElastoplasticCardResponse,
  CompletedUpload,
  CalibrationDiagnosticPreview,
  CalibrationCandidateSelectionPromotionResponse,
  CalibrationCandidateSelectionResponse,
  CalibrationPlanResponse,
  CalibrationRunResponse,
  VoceCalibrationPlanResponse,
  VoceCalibrationDiagnosticPreview,
  VoceCalibrationRunResponse,
  VoceCandidateSelectionResponse,
  VoceHoldoutPlanResponse,
  VoceHoldoutResultResponse,
  CurvePreview,
  DatasetSelectionResponse,
  TensileReplicateSelectionResponse,
  DatasetResponse,
  DataClassification,
  MaterialCreateInput,
  MaterialDetail,
  MaterialModelList,
  MaterialModelResponse,
  MaterialResponse,
  MaterialRevisionComparison,
  MaterialReviseInput,
  MaterialRevisionList,
  MaterialStateCreateInput,
  MaterialStateReviseInput,
  MaterialStateResponse,
  MaterialLotCreateInput,
  MaterialLotResponse,
  ProcessDefinitionCreateInput,
  ProcessDefinitionResponse,
  ProcessKind,
  ProcessRunCreateInput,
  ProcessRunResponse,
  StateGenealogyCreateInput,
  StateGenealogyResponse,
  LinearViscoelasticModelResponse,
  LinearViscoelasticCardResponse,
  LinearViscoelasticMappingReport,
  LinearViscoelasticResponse,
  OgdenPronyCardResponse,
  OgdenPronyMappingResponse,
  OgdenPronyModelResponse,
  OgdenPronyRevisionListResponse,
  OgdenCandidateSelectionResponse,
  ScientificProfileResponse,
  OgdenCalibrationPlanResponse,
  OgdenCalibrationRunResponse,
  OgdenDiagnosticsResponse,
  HyperelasticDiagnosticsResponse,
  NeutralMaterialResponse,
  NeutralHyperelasticMappingReport,
  NeutralHyperelasticSolverCardResponse,
  OgdenCalibrationRole,
  OgdenTestMode,
  MappingReport,
  ImportDetectionReportResponse,
  ImportMappingResponse,
  ImportRunResponse,
  OutlierAssessmentResponse,
  OutlierDetectionPlanResponse,
  OutlierDetectionRunResponse,
  OutlierScopeComparisonResponse,
  PropertySetCreateInput,
  PropertySetResponse,
  ProcessingRecipeResponse,
  ProcessingRunResponse,
  PronyCalibrationDiagnosticsResponse,
  PronyCalibrationPlanResponse,
  PronyCalibrationRunResponse,
  PronyCandidateSelectionResponse,
  ReplicateAlignmentBatchResponse,
  ReplicateStatisticalCurveResponse,
  ReplicateStatisticalPlanResponse,
  ReplicateStatisticalResultResponse,
  ReplicateStatisticalRunResponse,
  ScalarDistributionResultResponse,
  ScalarDistributionSelectionResponse,
  DistributionFamily,
  ExactUnitProfilePin,
  ReplicateOutlierAssessmentResponse,
  ReplicateOutlierDecision,
  ReplicateOutlierPlanResponse,
  ReplicateOutlierRunResponse,
  ReferenceCalibrationScopeResponse,
  StatisticalCurvePreview,
  StatisticalPlanResponse,
  StatisticalResultResponse,
  StatisticalRunResponse,
  ReferenceModelCreateInput,
  SolverCardCreateInput,
  SolverCardList,
  SolverCardResponse,
  TabulatedPlasticityModelResponse,
  HardeningCurveResponse,
  ValidationExecutionMode,
  ReferenceValidationResultResponse,
  ValidationPlanResponse,
  ValidationResultCurveResponse,
  ValidationRunResponse,
  ValidationTemplateResponse,
  ReferenceRunnerOutcome,
  ReviewDecisionKind,
  ReviewRequestListResponse,
  ReviewRequestResponse,
  ReleaseCreateInput,
  ReleaseImpactResponse,
  ReleaseListResponse,
  ReleaseResponse,
  ReleaseUsageResponse,
  RecordReleaseUsageInput,
  SupersedeReleaseInput,
  WithdrawReleaseInput,
  AuditEventPage,
  AuditIntegrityReport,
  AuditOutcome,
  ProvenanceCompletenessReport,
  ProvenanceEntityResponse,
  ProvenanceLineagePage,
  SpecimenResponse,
  SpecimenSourceResponse,
  ShearRelaxationCurvePreview,
  ShearRelaxationDatasetResponse,
  ShearRelaxationProcessingRecipeResponse,
  ShearRelaxationProcessingRunResponse,
  ViscoelasticMasterPlanResponse,
  ViscoelasticMasterPreviewResponse,
  ViscoelasticMasterRunResponse,
  ViscoelasticSelectionResponse,
  ViscoelasticShiftMethod,
  TestMethodResponse,
  TestRunResponse,
  TestCampaignResponse,
  InstrumentResponse,
  InstrumentCalibrationResponse,
  TestConditionResponse,
  TestRunContextResponse,
  TestCampaignContent,
  InstrumentContent,
  TestConditionContent,
  TestRunContextContent,
  GovernedImportPreview,
  GovernedImportProfileContent,
  GovernedImportProfileResponse,
  GovernedImportRunResponse,
  GovernedDatasetResponse,
  GovernedTabularFileFormat,
  ReferenceTensileMapping,
  UploadSession,
  BulkExportBundleResponse,
  BulkExportCandidate,
  BulkExportJobResponse,
  BulkExportSourceRef,
  CatalogDataCategory,
  ExportSelectionResponse,
  OperationalSnapshotResponse,
  ConfigurableAttributeContent,
  ConfigurableAttributeResponse,
  ConfigurableDatabaseContent,
  ConfigurableDatabaseResponse,
  ConfigurableCatalogFolderResponse,
  ConfigurableCatalogRecordComparison,
  ConfigurableCatalogRecordContent,
  ConfigurableCatalogRecordResponse,
  ConfigurableCatalogRecordRevisionList,
  ConfigurableCatalogRecordSearchResponse,
  ConfigurableRegistrationPreviewResponse,
  ConfigurableLayoutItem,
  ConfigurableLayoutResponse,
  ConfigurableSubsetResponse,
  ConfigurableTableContent,
  ConfigurableTableResponse,
  ConfigurableProfileContent,
  ConfigurableProfileResponse,
  ConfigurableLinkTypeContent,
  ConfigurableLinkTypeResponse,
  ConfigurableRecordLinkContent,
  ConfigurableRecordLinkResponse,
  ConfigurableRecordLinkView,
  CatalogExplorerChildrenResponse,
  CatalogWorkflowGraphResponse,
  CatalogCurvePreviewResponse,
  DomainBindingKind,
  DomainRevisionBinding,
  RevisionMetadata,
  CanonicalTestDataDocumentResponse,
  CanonicalTestDataPreviewResponse,
  CommonProcessingBatchResponse,
  CommonExportProvenance,
  GrantProductAccessInput,
  AuthenticatedPrincipal,
  ProductAccessAssignment,
  ProductAccessSummary,
  SchemaDefinitionBundleApplication,
  SchemaDefinitionBundleExport,
  SchemaDefinitionBundlePlan,
} from "./types";
import {
  ApiError,
  authenticatedHeaders,
  endpoint,
  request,
  throwResponseError,
} from "./shared/api/http";
import type { ApiConfig, ApiResult } from "./shared/api/http";

export { ApiError } from "./shared/api/http";
export type { ApiConfig, ApiResult } from "./shared/api/http";

export function getEffectiveProductAccess(
  config: ApiConfig,
): Promise<ApiResult<ProductAccessSummary>> {
  return request(config, "/product-access/me");
}

export function getAuthenticatedPrincipal(
  config: ApiConfig,
): Promise<ApiResult<AuthenticatedPrincipal>> {
  return request(config, "/me");
}

export function listProductAccessAssignments(
  config: ApiConfig,
): Promise<ApiResult<{ items: ProductAccessAssignment[] }>> {
  return request(config, "/product-access/assignments");
}

export function grantProductAccess(
  config: ApiConfig,
  input: GrantProductAccessInput,
): Promise<ApiResult<ProductAccessAssignment>> {
  return request(config, "/product-access/assignments", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function revokeProductAccess(
  config: ApiConfig,
  assignmentId: string,
  reason: string,
): Promise<ApiResult<null>> {
  return request(config, `/product-access/assignments/${assignmentId}/revoke`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

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
  input: { kind: import("./types").DomainBindingKind; object_id: string; revision_id: string },
): Promise<ApiResult<import("./types").DomainRevisionBinding>> {
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

export function validateCanonicalTestData(
  config: ApiConfig,
  document: Record<string, unknown>,
): Promise<ApiResult<CanonicalTestDataPreviewResponse>> {
  return request(config, "/test-data:validate", {
    method: "POST",
    body: JSON.stringify(document),
  });
}

export function convertTabularToCanonicalTestData(
  config: ApiConfig,
  input: Record<string, unknown>,
): Promise<ApiResult<CanonicalTestDataPreviewResponse>> {
  return request(config, "/test-data:convert-tabular", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function importCanonicalTestData(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    document: Record<string, unknown>;
    change_reason: string;
    governed_source?: CommonExportProvenance;
  },
): Promise<ApiResult<CanonicalTestDataDocumentResponse>> {
  return request(config, "/test-data-documents", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listCanonicalTestDataDocuments(
  config: ApiConfig,
): Promise<ApiResult<{ items: CanonicalTestDataDocumentResponse[] }>> {
  return request(config, "/test-data-documents");
}

export function reviseCanonicalTestData(
  config: ApiConfig,
  documentId: string,
  etag: string,
  input: {
    document: Record<string, unknown>;
    change_reason: string;
    governed_source?: CommonExportProvenance;
  },
): Promise<ApiResult<CanonicalTestDataDocumentResponse>> {
  return request(config, `/test-data-documents/${encodeURIComponent(documentId)}/revisions`, {
    method: "POST",
    headers: { "If-Match": etag },
    body: JSON.stringify(input),
  });
}

export async function downloadCanonicalTestDataDocument(
  config: ApiConfig,
  documentId: string,
  revisionId: string,
): Promise<ApiResult<SolverCardDownload>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "application/vnd.cmp.test-data+json");
  const response = await fetch(
    endpoint(
      config,
      `/test-data-documents/${encodeURIComponent(documentId)}/revisions/${encodeURIComponent(revisionId)}/content`,
    ),
    { ...init, headers },
  );
  if (!response.ok) return throwResponseError(response);
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return {
    data: {
      blob: await response.blob(),
      filename: match?.[1] ?? `test-data-${documentId}.json`,
    },
    etag: response.headers.get("etag"),
  };
}

export async function downloadCanonicalTestDataPackage(
  config: ApiConfig,
  revisions: Array<{ document_id: string; revision_id: string }>,
): Promise<ApiResult<SolverCardDownload>> {
  const init: RequestInit = {
    method: "POST",
    body: JSON.stringify({ revisions }),
  };
  const headers = authenticatedHeaders(config, init, "application/vnd.cmp.test-data-package+zip");
  const response = await fetch(endpoint(config, "/test-data-packages:download"), {
    ...init,
    headers,
  });
  if (!response.ok) return throwResponseError(response);
  return {
    data: { blob: await response.blob(), filename: "cmp-test-data-package.zip" },
    etag: response.headers.get("etag"),
  };
}

/**
 * Compatibility for the Activity section still composed in
 * material-library.tsx. The Modeling feature owns the primary client; remove
 * these two root calls when #262 extracts Activity from the registered
 * Materials hotspot and #263 retires root API compatibility.
 */
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

export type LocalDemoPersona = "administrator" | "user" | "reviewer";

export interface LocalDemoAccessToken {
  access_token: string;
  token_type: "Bearer";
  expires_in_seconds: number;
  organization_id: string;
  project_id: string;
  group: string;
  persona: LocalDemoPersona;
}

export interface LocalDemoTokenSession {
  persona: LocalDemoPersona;
  expiresAt: number;
}

/**
 * Read only the local-demo fixture identity and expiry needed to renew its
 * browser session. These unverified claims never grant access; the API still
 * validates the signed bearer token for every protected request.
 */
export function inspectLocalDemoAccessToken(token: string): LocalDemoTokenSession | null {
  const payloadSegment = token.trim().split(".")[1];
  if (!payloadSegment) return null;

  try {
    const normalized = payloadSegment.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const payload = JSON.parse(window.atob(padded)) as { exp?: unknown; sub?: unknown };
    const personaBySubject: Record<string, LocalDemoPersona> = {
      "cmp-demo-administrator": "administrator",
      "cmp-demo-user": "user",
      "cmp-demo-reviewer": "reviewer",
    };
    const persona = typeof payload.sub === "string" ? personaBySubject[payload.sub] : undefined;
    if (!persona || typeof payload.exp !== "number" || !Number.isFinite(payload.exp)) return null;
    return { persona, expiresAt: payload.exp * 1000 };
  } catch {
    return null;
  }
}

export const defaultApiConfig: ApiConfig = {
  baseUrl: (import.meta.env.VITE_CMP_API_BASE_URL ?? "/api/v1").replace(/\/$/, ""),
  accessToken: "",
};

const storageKey = "cmp.material-platform.api-config";

export function loadApiConfig(): ApiConfig {
  const raw = window.localStorage.getItem(storageKey);
  if (!raw) {
    return defaultApiConfig;
  }
  try {
    const value: unknown = JSON.parse(raw);
    if (
      typeof value === "object" &&
      value !== null &&
      "baseUrl" in value &&
      "accessToken" in value &&
      typeof value.baseUrl === "string" &&
      typeof value.accessToken === "string"
    ) {
      return {
        baseUrl: value.baseUrl.replace(/\/$/, "") || defaultApiConfig.baseUrl,
        accessToken: value.accessToken,
      };
    }
  } catch {
    // A malformed local preference must not make the catalog inaccessible.
  }
  return defaultApiConfig;
}

export function saveApiConfig(config: ApiConfig): void {
  window.localStorage.setItem(storageKey, JSON.stringify(config));
}

function revisionPath(path: string, revisionId?: string): string {
  if (!revisionId) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}revision_id=${encodeURIComponent(revisionId)}`;
}

/**
 * Request the explicitly enabled local-demo token without attaching a bearer
 * credential.  A normal deployment has no such route, so this never becomes
 * an authentication fallback for the workbench.
 */
export async function requestLocalDemoAccessToken(
  config: Pick<ApiConfig, "baseUrl">,
  persona: LocalDemoPersona = "administrator",
): Promise<ApiResult<LocalDemoAccessToken>> {
  const baseUrl = config.baseUrl.trim().replace(/\/$/, "") || "/api/v1";
  const personaQuery = persona === "administrator" ? "" : `?persona=${persona}`;
  const response = await fetch(`${baseUrl}/demo-identity/token${personaQuery}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    return throwResponseError(response);
  }
  return {
    data: (await response.json()) as LocalDemoAccessToken,
    etag: response.headers.get("etag"),
  };
}

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

export function listMaterialModels(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<MaterialModelList>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/material-models`);
}

export function getMaterialModel(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<MaterialModelResponse>> {
  return request(config, `/material-models/${encodeURIComponent(materialModelId)}`);
}

export function createReferenceMaterialModel(
  config: ApiConfig,
  materialStateId: string,
  input: ReferenceModelCreateInput,
): Promise<ApiResult<MaterialModelResponse>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/material-models`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferenceLinearElasticCalibrationPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    plan_label: string;
    selection_id: string;
    selection_revision_id: string;
    material_model_id: string;
    material_model_revision_id: string;
    youngs_modulus_lower_bound_pa: number;
    youngs_modulus_initial_value_pa: number;
    youngs_modulus_upper_bound_pa: number;
    normalization_stress_scale_pa: number;
    multistart_count: number;
    random_seed: number;
    change_reason: string;
  },
): Promise<ApiResult<CalibrationPlanResponse>> {
  return request(config, "/calibration-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceLinearElasticCalibration(
  config: ApiConfig,
  input: {
    plan_id: string;
    plan_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<CalibrationRunResponse>> {
  return request(config, "/calibration-runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function previewCalibrationCandidateDiagnostics(
  config: ApiConfig,
  candidateId: string,
  maximumPoints = 500,
): Promise<ApiResult<CalibrationDiagnosticPreview>> {
  return request(
    config,
    `/calibration-candidates/${encodeURIComponent(candidateId)}/diagnostics-preview?maximum_points=${maximumPoints}`,
  );
}

export interface VoceParameterInput {
  lower: number;
  initial: number;
  upper: number;
  scale: number;
}

export function createReferenceVoceCalibrationPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    plan_label: string;
    calibration_input_scope_id: string;
    calibration_input_scope_revision_id: string;
    material_state_id: string;
    material_state_revision_id: string;
    property_set_id: string;
    property_set_revision_id: string;
    youngs_modulus_pa: number;
    sigma_0_pa: VoceParameterInput;
    q_pa: VoceParameterInput;
    b: VoceParameterInput;
    normalization_stress_scale_pa: number;
    multistart_count: number;
    random_seed: number;
    maximum_function_evaluations: number;
    ftol: number;
    xtol: number;
    gtol: number;
    change_reason: string;
  },
): Promise<ApiResult<VoceCalibrationPlanResponse>> {
  return request(config, "/voce-calibration-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceVoceCalibration(
  config: ApiConfig,
  planId: string,
  input: { plan_revision_id: string; change_reason: string },
): Promise<ApiResult<VoceCalibrationRunResponse>> {
  return request(
    config,
    `/voce-calibration-plans/${encodeURIComponent(planId)}/runs`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function previewReferenceVoceCalibrationDiagnostics(
  config: ApiConfig,
  candidateId: string,
  maximumPoints = 1000,
): Promise<ApiResult<VoceCalibrationDiagnosticPreview>> {
  return request(
    config,
    `/voce-calibration-candidates/${encodeURIComponent(candidateId)}/diagnostics-preview?maximum_points=${maximumPoints}`,
  );
}

export function createReferenceVoceCandidateSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    voce_calibration_run_id: string;
    voce_calibration_candidate_id: string;
    selection_reason: string;
  },
): Promise<ApiResult<VoceCandidateSelectionResponse>> {
  return request(config, "/voce-candidate-selections", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function projectSelectedReferenceVoceCandidate(
  config: ApiConfig,
  selectionId: string,
  input: {
    selection_revision_id: string;
    sampling_point_count: number;
    extension_max_true_plastic_strain: number;
    acknowledge_constant_extension: boolean;
    change_reason: string;
  },
): Promise<ApiResult<TabulatedPlasticityModelResponse>> {
  return request(
    config,
    `/voce-candidate-selections/${encodeURIComponent(selectionId)}/tabulated-plasticity-models`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function createReferenceVoceHoldoutPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      plan_label: string;
      material_model_id: string;
      material_model_revision_id: string;
      holdout_dataset_id: string;
      holdout_dataset_revision_id: string;
    };
    change_reason: string;
  },
): Promise<ApiResult<VoceHoldoutPlanResponse>> {
  return request(config, "/voce-holdout-validation-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceVoceHoldout(
  config: ApiConfig,
  planId: string,
  input: { plan_revision_id: string; change_reason: string },
): Promise<ApiResult<VoceHoldoutResultResponse>> {
  return request(
    config,
    `/voce-holdout-validation-plans/${encodeURIComponent(planId)}/runs`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function listReferenceVoceHoldoutResults(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<{ items: VoceHoldoutResultResponse[] }>> {
  return request(
    config,
    `/tabulated-plasticity-models/${encodeURIComponent(materialModelId)}/voce-holdout-results`,
  );
}

export function createReferenceCalibrationCandidateSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    calibration_run_id: string;
    calibration_candidate_id: string;
    selection_reason: string;
  },
): Promise<ApiResult<CalibrationCandidateSelectionResponse>> {
  return request(config, "/calibration-candidate-selections", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function promoteSelectedReferenceCalibrationCandidate(
  config: ApiConfig,
  selectionId: string,
  input: {
    selection_revision_id: string;
    expected_material_model_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<CalibrationCandidateSelectionPromotionResponse>> {
  return request(
    config,
    `/calibration-candidate-selections/${encodeURIComponent(selectionId)}/promote-material-model`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function listValidationTemplates(
  config: ApiConfig,
): Promise<ApiResult<{ items: ValidationTemplateResponse[] }>> {
  return request(config, "/validation-templates?limit=100");
}

export function createReferenceValidationTemplate(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      template_label: string;
      gauge_length_m: number;
      cross_section_area_m2: number;
      axial_element_count: number;
      axial_displacement_end_m: number;
      output_sample_count: number;
    };
    change_reason: string;
  },
): Promise<ApiResult<ValidationTemplateResponse>> {
  return request(config, "/validation-templates", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listValidationPlans(
  config: ApiConfig,
): Promise<ApiResult<{ items: ValidationPlanResponse[] }>> {
  return request(config, "/validation-plans?limit=100");
}

export function createReferenceValidationPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      plan_label: string;
      validation_template_id: string;
      validation_template_revision_id: string;
      material_model_id: string;
      material_model_revision_id: string;
      solver_card_id: string;
      solver_card_revision_id: string;
      experimental_selection_id: string;
      experimental_selection_revision_id: string;
    };
    change_reason: string;
  },
): Promise<ApiResult<ValidationPlanResponse>> {
  return request(config, "/validation-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function submitReferenceValidationRun(
  config: ApiConfig,
  input: {
    validation_plan_id: string;
    validation_plan_revision_id: string;
    execution_mode: ValidationExecutionMode;
    external_job_reference?: string;
    change_reason: string;
  },
): Promise<ApiResult<ValidationRunResponse>> {
  return request(config, "/validation-runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function pollReferenceValidationRun(
  config: ApiConfig,
  runId: string,
  input: { change_reason: string; outcome: ReferenceRunnerOutcome },
): Promise<ApiResult<ValidationRunResponse>> {
  return request(config, `/validation-runs/${encodeURIComponent(runId)}:poll`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function cancelValidationRun(
  config: ApiConfig,
  runId: string,
  input: { change_reason: string },
): Promise<ApiResult<ValidationRunResponse>> {
  return request(config, `/validation-runs/${encodeURIComponent(runId)}:cancel`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function attachManualValidationResult(
  config: ApiConfig,
  runId: string,
  input: {
    stdout_text: string;
    stderr_text: string;
    native_result_text: string;
    change_reason: string;
  },
): Promise<ApiResult<ValidationRunResponse>> {
  return request(config, `/validation-runs/${encodeURIComponent(runId)}:attach-result`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function evaluateReferenceValidationRun(
  config: ApiConfig,
  runId: string,
  input: { change_reason: string },
): Promise<ApiResult<ValidationRunResponse>> {
  return request(config, `/validation-runs/${encodeURIComponent(runId)}:evaluate`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getReferenceValidationResult(
  config: ApiConfig,
  validationResultId: string,
): Promise<ApiResult<ReferenceValidationResultResponse>> {
  return request(config, `/validation-results/${encodeURIComponent(validationResultId)}`);
}

export function previewReferenceValidationResultCurve(
  config: ApiConfig,
  validationResultId: string,
  maximumPoints = 1_000,
): Promise<ApiResult<ValidationResultCurveResponse>> {
  const query = new URLSearchParams({ maximum_points: String(maximumPoints) });
  return request(
    config,
    `/validation-results/${encodeURIComponent(validationResultId)}/curve?${query.toString()}`,
  );
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

export function preflightSolverCardMapping(
  config: ApiConfig,
  materialModelId: string,
  target: ExportTarget,
): Promise<ApiResult<MappingReport>> {
  return request(config, `/material-models/${encodeURIComponent(materialModelId)}/mapping-preflight`, {
    method: "POST",
    body: JSON.stringify({ target }),
  });
}

export function listSolverCards(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<SolverCardList>> {
  return request(config, `/material-models/${encodeURIComponent(materialModelId)}/solver-cards`);
}

export function getSolverCard(
  config: ApiConfig,
  solverCardId: string,
  revisionId?: string,
): Promise<ApiResult<SolverCardResponse>> {
  return request(
    config,
    revisionPath(`/solver-cards/${encodeURIComponent(solverCardId)}`, revisionId),
  );
}

export function createSolverCard(
  config: ApiConfig,
  materialModelId: string,
  input: SolverCardCreateInput,
): Promise<ApiResult<SolverCardResponse>> {
  return request(config, `/material-models/${encodeURIComponent(materialModelId)}/solver-cards`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function previewSolverCard(
  config: ApiConfig,
  solverCardId: string,
  revisionId?: string,
): Promise<ApiResult<string>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(
      config,
      revisionPath(`/solver-cards/${encodeURIComponent(solverCardId)}/preview`, revisionId),
    ),
    { ...init, headers },
  );
  if (!response.ok) {
    return throwResponseError(response);
  }
  return { data: await response.text(), etag: response.headers.get("etag") };
}

export interface SolverCardDownload {
  blob: Blob;
  filename: string;
}

export async function downloadSolverCard(
  config: ApiConfig,
  solverCardId: string,
  revisionId?: string,
): Promise<ApiResult<SolverCardDownload>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(
      config,
      revisionPath(`/solver-cards/${encodeURIComponent(solverCardId)}/download`, revisionId),
    ),
    { ...init, headers },
  );
  if (!response.ok) {
    return throwResponseError(response);
  }
  const header = response.headers.get("content-disposition") ?? "";
  const match = header.match(/filename="?([^";]+)"?/i);
  return {
    data: {
      blob: await response.blob(),
      filename: match?.[1] ?? `solver-card-${solverCardId}.rad`,
    },
    etag: response.headers.get("etag"),
  };
}

export function listTabulatedPlasticityModels(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: TabulatedPlasticityModelResponse[] }>> {
  return request(
    config,
    `/material-states/${encodeURIComponent(materialStateId)}/tabulated-plasticity-models`,
  );
}

export function listLinearViscoelasticModels(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: LinearViscoelasticModelResponse[] }>> {
  return request(
    config,
    `/material-states/${encodeURIComponent(materialStateId)}/linear-viscoelastic-models`,
  );
}

export function createLinearViscoelasticModel(
  config: ApiConfig,
  materialStateId: string,
  input: {
    property_set_revision_id: string;
    bulk_relaxation_status: "characterized" | "not_characterized";
    terms: Array<{ g_ratio: number; k_ratio: number; relaxation_time_s: number }>;
    change_reason: string;
  },
): Promise<ApiResult<LinearViscoelasticModelResponse>> {
  return request(
    config,
    `/material-states/${encodeURIComponent(materialStateId)}/linear-viscoelastic-models`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function promotePronyProcessingOutput(
  config: ApiConfig,
  processingOutputId: string,
  input: {
    material_state_id: string;
    property_set_revision_id: string;
    processing_output_revision_id: string;
    acknowledged_maximum_relative_mismatch: number;
    review_acknowledged: boolean;
    change_reason: string;
  },
): Promise<ApiResult<LinearViscoelasticModelResponse>> {
  return request(
    config,
    `/processing-outputs/${encodeURIComponent(processingOutputId)}/linear-viscoelastic-models`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function previewLinearViscoelasticResponse(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<LinearViscoelasticResponse>> {
  return request(
    config,
    `/linear-viscoelastic-models/${encodeURIComponent(materialModelId)}/response`,
  );
}

export function preflightLinearViscoelasticMapping(
  config: ApiConfig,
  materialModelId: string,
  materialModelRevisionId: string,
): Promise<ApiResult<LinearViscoelasticMappingReport>> {
  return request(
    config,
    `/linear-viscoelastic-models/${encodeURIComponent(materialModelId)}/mapping-preflight`,
    {
      method: "POST",
      body: JSON.stringify({
        material_model_revision_id: materialModelRevisionId,
        target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s" },
      }),
    },
  );
}

export function listLinearViscoelasticSolverCards(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<{ items: LinearViscoelasticCardResponse[] }>> {
  return request(
    config,
    `/linear-viscoelastic-models/${encodeURIComponent(materialModelId)}/solver-cards`,
  );
}

export function createLinearViscoelasticSolverCard(
  config: ApiConfig,
  materialModelId: string,
  input: {
    material_model_revision_id: string;
    expected_mapping_report_sha256: string;
    solver_material_id: number;
    material_name: string;
    change_reason: string;
  },
): Promise<ApiResult<{ card: LinearViscoelasticCardResponse; mapping_report: LinearViscoelasticMappingReport }>> {
  return request(
    config,
    `/linear-viscoelastic-models/${encodeURIComponent(materialModelId)}/solver-cards`,
    {
      method: "POST",
      body: JSON.stringify({
        ...input,
        target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s" },
      }),
    },
  );
}

export async function previewLinearViscoelasticSolverCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<string>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/linear-viscoelastic-solver-cards/${encodeURIComponent(solverCardId)}/preview`),
    { ...init, headers },
  );
  if (!response.ok) return throwResponseError(response);
  return { data: await response.text(), etag: response.headers.get("etag") };
}

export async function downloadLinearViscoelasticSolverCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<{ blob: Blob; filename: string }>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/linear-viscoelastic-solver-cards/${encodeURIComponent(solverCardId)}/download`),
    { ...init, headers },
  );
  if (!response.ok) return throwResponseError(response);
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "material.inp";
  return { data: { blob: await response.blob(), filename }, etag: response.headers.get("etag") };
}

export function listOgdenPronyModels(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: OgdenPronyModelResponse[] }>> {
  return request(
    config,
    `/material-states/${encodeURIComponent(materialStateId)}/ogden-prony-models`,
  );
}

export function createOgdenPronyModel(
  config: ApiConfig,
  materialStateId: string,
  input: {
    property_set_revision_id: string;
    ogden_mu_pa: number;
    ogden_alpha: number;
    prony_terms: Array<{ g_ratio: number; relaxation_time_s: number }>;
    change_reason: string;
  },
): Promise<ApiResult<OgdenPronyModelResponse>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/ogden-prony-models`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function listScientificProfiles(
  config: ApiConfig,
  family: "steel_voce" | "polymer_linear_prony" | "elastomer_ogden_prony",
): Promise<ApiResult<ScientificProfileResponse[]>> {
  const result = await request<{ items: ScientificProfileResponse[] }>(
    config,
    `/scientific-profiles?family=${encodeURIComponent(family)}`,
  );
  return { data: result.data.items, etag: result.etag };
}

export function createOgdenScientificProfile(
  config: ApiConfig,
): Promise<ApiResult<ScientificProfileResponse>> {
  return request(config, "/scientific-profiles", {
    method: "POST",
    body: JSON.stringify({
      classification: "internal",
      content: {
        profile_label: "Reference elastomer multi-test Ogden",
        family: "elastomer_ogden_prony",
        approval_status: "reference_unapproved",
        multistart_count: 8,
        seed: 20260716,
        status_note: "Synthetic/public reference bounds; domain sign-off is not recorded.",
        ogden: {
          mu_initial_pa: 1200000,
          mu_lower_pa: 1000,
          mu_upper_pa: 100000000,
          mu_scale_pa: 1000000,
          alpha_initial: 2.4,
          alpha_lower: 0.1,
          alpha_upper: 20,
          alpha_scale: 2,
          uniaxial_weight: 1,
          planar_weight: 1,
          biaxial_weight: 1,
        },
      },
      change_reason: "Create explicit reference Ogden scientific profile",
    }),
  });
}

export function createReferenceOgdenCalibrationPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    plan_label: string;
    scientific_profile_id: string;
    scientific_profile_revision_id: string;
    material_state_id: string;
    material_state_revision_id: string;
    baseline_model_id: string;
    baseline_model_revision_id: string;
    members: Array<{
      role: OgdenCalibrationRole;
      test_mode: OgdenTestMode;
      dataset_id: string;
      dataset_revision_id: string;
      weight: number;
    }>;
    change_reason: string;
  },
): Promise<ApiResult<OgdenCalibrationPlanResponse>> {
  return request(config, "/ogden-calibration-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listReferenceOgdenCalibrationPlans(
  config: ApiConfig,
  limit = 100,
): Promise<ApiResult<{ items: OgdenCalibrationPlanResponse[] }>> {
  return request(config, `/ogden-calibration-plans?limit=${encodeURIComponent(String(limit))}`);
}

export function getReferenceOgdenCalibrationPlan(
  config: ApiConfig,
  planId: string,
): Promise<ApiResult<OgdenCalibrationPlanResponse>> {
  return request(config, `/ogden-calibration-plans/${encodeURIComponent(planId)}`);
}

export function reviseReferenceOgdenCalibrationPlan(
  config: ApiConfig,
  planId: string,
  input: {
    expected_current_revision_id: string;
    plan_label: string;
    scientific_profile_id: string;
    scientific_profile_revision_id: string;
    material_state_id: string;
    material_state_revision_id: string;
    baseline_model_id: string;
    baseline_model_revision_id: string;
    members: Array<{
      role: OgdenCalibrationRole;
      test_mode: OgdenTestMode;
      dataset_id: string;
      dataset_revision_id: string;
      weight: number;
    }>;
    change_reason: string;
  },
): Promise<ApiResult<OgdenCalibrationPlanResponse>> {
  return request(
    config,
    `/ogden-calibration-plans/${encodeURIComponent(planId)}/revisions`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function executeReferenceOgdenCalibration(
  config: ApiConfig,
  planId: string,
  input: { plan_revision_id: string; change_reason: string },
): Promise<ApiResult<OgdenCalibrationRunResponse>> {
  return request(config, `/ogden-calibration-plans/${encodeURIComponent(planId)}/runs`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getReferenceOgdenCandidateDiagnostics(
  config: ApiConfig,
  candidateId: string,
): Promise<ApiResult<OgdenDiagnosticsResponse>> {
  return request(
    config,
    `/ogden-calibration-candidates/${encodeURIComponent(candidateId)}/diagnostics`,
  );
}

export function getReferenceOgdenCalibrationRun(
  config: ApiConfig,
  runId: string,
): Promise<ApiResult<OgdenCalibrationRunResponse>> {
  return request(config, `/ogden-calibration-runs/${encodeURIComponent(runId)}`);
}

export function getHyperelasticFamilyCandidateDiagnostics(
  config: ApiConfig,
  candidateId: string,
): Promise<ApiResult<HyperelasticDiagnosticsResponse>> {
  return request(
    config,
    `/hyperelastic-family-candidates/${encodeURIComponent(candidateId)}/diagnostics`,
  );
}

export function promoteHyperelasticCandidateToNeutralMaterial(
  config: ApiConfig,
  input: {
    candidate_id: string;
    selection_reason: string;
    change_reason: string;
  },
): Promise<ApiResult<NeutralMaterialResponse>> {
  return request(config, "/neutral-materials:promote", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function promoteModelToNeutralMaterial(
  config: ApiConfig,
  family: "metal" | "linear-viscoelastic",
  input: {
    material_model_id: string;
    material_model_revision_id: string;
    selection_reason: string;
    change_reason: string;
  },
): Promise<ApiResult<NeutralMaterialResponse>> {
  return request(config, `/neutral-materials:promote-${family}`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getNeutralMaterial(
  config: ApiConfig,
  neutralMaterialId: string,
): Promise<ApiResult<NeutralMaterialResponse>> {
  return request(
    config,
    `/neutral-materials/${encodeURIComponent(neutralMaterialId)}`,
  );
}

export function importNeutralMaterial(
  config: ApiConfig,
  input: { document: Record<string, unknown>; change_reason: string },
): Promise<ApiResult<NeutralMaterialResponse>> {
  return request(config, "/neutral-materials:import", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function downloadNeutralMaterial(
  config: ApiConfig,
  neutralMaterialId: string,
): Promise<ApiResult<{ blob: Blob; filename: string }>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "application/json");
  const response = await fetch(
    endpoint(
      config,
      `/neutral-materials/${encodeURIComponent(neutralMaterialId)}/download`,
    ),
    { ...init, headers },
  );
  if (!response.ok) {
    return throwResponseError(response);
  }
  return {
    data: {
      blob: await response.blob(),
      filename: `neutral-material-${neutralMaterialId}.json`,
    },
    etag: response.headers.get("etag"),
  };
}

export function preflightNeutralHyperelasticSolverCard(
  config: ApiConfig,
  neutralMaterialId: string,
  input: { neutral_material_revision_id: string; target: ExportTarget },
): Promise<ApiResult<NeutralHyperelasticMappingReport>> {
  return request(
    config,
    `/neutral-materials/${encodeURIComponent(neutralMaterialId)}/solver-card-preflight`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function createNeutralHyperelasticSolverCard(
  config: ApiConfig,
  neutralMaterialId: string,
  input: {
    neutral_material_revision_id: string;
    target: ExportTarget;
    expected_mapping_report_sha256: string;
    solver_material_id: number;
    material_name: string;
    change_reason: string;
  },
): Promise<ApiResult<NeutralHyperelasticSolverCardResponse>> {
  return request(
    config,
    `/neutral-materials/${encodeURIComponent(neutralMaterialId)}/solver-cards`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function getNeutralSolverCard(
  config: ApiConfig,
  solverCardId: string,
  revisionId?: string,
): Promise<ApiResult<NeutralHyperelasticSolverCardResponse>> {
  return request(
    config,
    revisionPath(`/neutral-solver-cards/${encodeURIComponent(solverCardId)}`, revisionId),
  );
}

export function getNeutralSolverMappingReport(
  config: ApiConfig,
  solverCardId: string,
  revisionId?: string,
): Promise<ApiResult<NeutralHyperelasticMappingReport>> {
  return request(
    config,
    revisionPath(
      `/neutral-solver-cards/${encodeURIComponent(solverCardId)}/mapping-report`,
      revisionId,
    ),
  );
}

export async function previewNeutralHyperelasticSolverCard(
  config: ApiConfig,
  solverCardId: string,
  revisionId?: string,
): Promise<ApiResult<string>> {
  const headers = authenticatedHeaders(config, {}, "text/plain");
  const response = await fetch(
    endpoint(
      config,
      revisionPath(
        `/neutral-solver-cards/${encodeURIComponent(solverCardId)}/preview`,
        revisionId,
      ),
    ),
    { headers },
  );
  if (!response.ok) return throwResponseError(response);
  return { data: await response.text(), etag: response.headers.get("etag") };
}

export async function downloadNeutralHyperelasticSolverCard(
  config: ApiConfig,
  solverCardId: string,
  revisionId?: string,
): Promise<ApiResult<SolverCardDownload>> {
  const headers = authenticatedHeaders(config, {}, "text/plain");
  const response = await fetch(
    endpoint(
      config,
      revisionPath(
        `/neutral-solver-cards/${encodeURIComponent(solverCardId)}/download`,
        revisionId,
      ),
    ),
    { headers },
  );
  if (!response.ok) return throwResponseError(response);
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? `solver-card-${solverCardId}.txt`;
  return {
    data: { blob: await response.blob(), filename },
    etag: response.headers.get("etag"),
  };
}

export async function downloadNeutralHyperelasticMappingReport(
  config: ApiConfig,
  solverCardId: string,
  revisionId?: string,
): Promise<ApiResult<{ blob: Blob; filename: string }>> {
  const result = await request<NeutralHyperelasticMappingReport>(
    config,
    revisionPath(
      `/neutral-solver-cards/${encodeURIComponent(solverCardId)}/mapping-report`,
      revisionId,
    ),
  );
  return {
    data: {
      blob: new Blob([JSON.stringify(result.data, null, 2)], { type: "application/json" }),
      filename: `mapping-report-${solverCardId}.json`,
    },
    etag: result.etag,
  };
}

export function createReferenceOgdenCandidateSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    calibration_run_id: string;
    calibration_candidate_id: string;
    selection_reason: string;
  },
): Promise<ApiResult<OgdenCandidateSelectionResponse>> {
  return request(config, "/ogden-candidate-selections", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function promoteReferenceOgdenCandidate(
  config: ApiConfig,
  selectionId: string,
  modelEtag: string,
  input: { selection_revision_id: string; change_reason: string },
): Promise<ApiResult<OgdenPronyModelResponse>> {
  return request(
    config,
    `/ogden-candidate-selections/${encodeURIComponent(selectionId)}/promotions`,
    {
      method: "POST",
      headers: { "If-Match": modelEtag },
      body: JSON.stringify(input),
    },
  );
}

export function listOgdenPronyModelRevisions(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<OgdenPronyRevisionListResponse>> {
  return request(
    config,
    `/ogden-prony-models/${encodeURIComponent(materialModelId)}/revisions`,
  );
}

export function preflightOgdenPronyCard(
  config: ApiConfig,
  materialModelId: string,
  materialModelRevisionId: string,
  solver: "abaqus" | "openradioss",
): Promise<ApiResult<OgdenPronyMappingResponse>> {
  return request(
    config,
    `/ogden-prony-models/${encodeURIComponent(materialModelId)}/solver-card-preflight`,
    {
      method: "POST",
      body: JSON.stringify({
        material_model_revision_id: materialModelRevisionId,
        target: { solver, version: "2025", unit_system: "kg_m_s" },
      }),
    },
  );
}

export function listOgdenPronyCards(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<{ items: OgdenPronyCardResponse[] }>> {
  return request(config, `/ogden-prony-models/${encodeURIComponent(materialModelId)}/solver-cards`);
}

export function createOgdenPronyCard(
  config: ApiConfig,
  materialModelId: string,
  input: {
    material_model_revision_id: string;
    solver: "abaqus" | "openradioss";
    expected_mapping_report_sha256: string;
    solver_material_id: number;
    material_name: string;
    change_reason: string;
  },
): Promise<ApiResult<OgdenPronyCardResponse>> {
  return request(config, `/ogden-prony-models/${encodeURIComponent(materialModelId)}/solver-cards`, {
    method: "POST",
    body: JSON.stringify({
      material_model_revision_id: input.material_model_revision_id,
      target: { solver: input.solver, version: "2025", unit_system: "kg_m_s" },
      expected_mapping_report_sha256: input.expected_mapping_report_sha256,
      solver_material_id: input.solver_material_id,
      material_name: input.material_name,
      change_reason: input.change_reason,
    }),
  });
}

export async function previewOgdenPronyCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<string>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/ogden-prony-solver-cards/${encodeURIComponent(solverCardId)}/preview`),
    { ...init, headers },
  );
  if (!response.ok) return throwResponseError(response);
  return { data: await response.text(), etag: response.headers.get("etag") };
}

export async function downloadOgdenPronyCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<{ blob: Blob; filename: string }>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/ogden-prony-solver-cards/${encodeURIComponent(solverCardId)}/download`),
    { ...init, headers },
  );
  if (!response.ok) return throwResponseError(response);
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "elastomer-card.txt";
  return { data: { blob: await response.blob(), filename }, etag: response.headers.get("etag") };
}

export function createTabulatedPlasticityModel(
  config: ApiConfig,
  materialStateId: string,
  input: {
    property_set_revision_id: string;
    dataset_revision_id: string;
    extension_max_true_plastic_strain: number;
    acknowledge_post_necking_approximation: boolean;
    change_reason: string;
  },
): Promise<ApiResult<TabulatedPlasticityModelResponse>> {
  return request(
    config,
    `/material-states/${encodeURIComponent(materialStateId)}/tabulated-plasticity-models`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function promoteProcessingOutputToTabulatedPlasticity(
  config: ApiConfig,
  processingOutputId: string,
  input: {
    material_state_id: string;
    property_set_revision_id: string;
    processing_output_revision_id: string;
    acknowledge_bounded_extrapolation: boolean;
    change_reason: string;
  },
): Promise<ApiResult<TabulatedPlasticityModelResponse>> {
  return request(
    config,
    `/processing-outputs/${encodeURIComponent(processingOutputId)}/tabulated-plasticity-models`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function getTabulatedPlasticityHardeningCurve(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<HardeningCurveResponse>> {
  return request(
    config,
    `/tabulated-plasticity-models/${encodeURIComponent(materialModelId)}/hardening-curve`,
  );
}

export function preflightElastoplasticMapping(
  config: ApiConfig,
  materialModelId: string,
  materialModelRevisionId: string,
  target: ExportTarget,
): Promise<ApiResult<MappingReport>> {
  return request(
    config,
    `/tabulated-plasticity-models/${encodeURIComponent(materialModelId)}/mapping-preflight`,
    {
      method: "POST",
      body: JSON.stringify({ material_model_revision_id: materialModelRevisionId, target }),
    },
  );
}

export function listElastoplasticSolverCards(
  config: ApiConfig,
  materialModelId: string,
): Promise<ApiResult<{ items: ElastoplasticCardResponse[] }>> {
  return request(
    config,
    `/tabulated-plasticity-models/${encodeURIComponent(materialModelId)}/solver-cards`,
  );
}

export function createElastoplasticSolverCard(
  config: ApiConfig,
  materialModelId: string,
  input: {
    material_model_revision_id: string;
    target: ExportTarget;
    expected_mapping_report_sha256: string;
    solver_material_id: number;
    material_name: string;
    change_reason: string;
  },
): Promise<ApiResult<ElastoplasticCardCreatedResponse>> {
  return request(
    config,
    `/tabulated-plasticity-models/${encodeURIComponent(materialModelId)}/solver-cards`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export async function previewElastoplasticSolverCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<string>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/elastoplastic-solver-cards/${encodeURIComponent(solverCardId)}/preview`),
    { ...init, headers },
  );
  if (!response.ok) {
    return throwResponseError(response);
  }
  return { data: await response.text(), etag: response.headers.get("etag") };
}

export async function downloadElastoplasticSolverCard(
  config: ApiConfig,
  solverCardId: string,
): Promise<ApiResult<SolverCardDownload>> {
  const init: RequestInit = {};
  const headers = authenticatedHeaders(config, init, "text/plain");
  const response = await fetch(
    endpoint(config, `/elastoplastic-solver-cards/${encodeURIComponent(solverCardId)}/download`),
    { ...init, headers },
  );
  if (!response.ok) {
    return throwResponseError(response);
  }
  const header = response.headers.get("content-disposition") ?? "";
  const match = header.match(/filename="?([^";]+)"?/i);
  return {
    data: {
      blob: await response.blob(),
      filename: match?.[1] ?? `elastoplastic-card-${solverCardId}.txt`,
    },
    etag: response.headers.get("etag"),
  };
}

export function listSpecimensForMaterialState(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: SpecimenResponse[] }>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/specimens`);
}

export function createSpecimen(
  config: ApiConfig,
  materialStateId: string,
  input: {
    material_state_revision_id: string;
    specimen_code: string;
    orientation: string | null;
    preparation_note: string | null;
    change_reason: string;
  },
): Promise<ApiResult<SpecimenResponse>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/specimens`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getSpecimenSource(
  config: ApiConfig,
  specimenId: string,
): Promise<ApiResult<SpecimenSourceResponse | null>> {
  return request(config, `/specimens/${encodeURIComponent(specimenId)}/source-genealogy`);
}

export function createSpecimenSource(
  config: ApiConfig,
  specimenId: string,
  input: {
    content: {
      specimen_revision_id: string;
      sources: Array<{
        material_lot_id: string;
        material_lot_revision_id: string;
        note: string | null;
      }>;
      note: string | null;
    };
    change_reason: string;
  },
): Promise<ApiResult<SpecimenSourceResponse>> {
  return request(config, `/specimens/${encodeURIComponent(specimenId)}/source-genealogy`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listTestMethods(
  config: ApiConfig,
): Promise<ApiResult<{ items: TestMethodResponse[] }>> {
  return request(config, "/test-methods");
}

export function createReferenceTensileTestMethod(
  config: ApiConfig,
  input: { classification: DataClassification; change_reason: string },
): Promise<ApiResult<TestMethodResponse>> {
  return request(config, "/test-methods/reference-uniaxial-tensile", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferenceShearRelaxationTestMethod(
  config: ApiConfig,
  input: { classification: DataClassification; change_reason: string },
): Promise<ApiResult<TestMethodResponse>> {
  return request(config, "/test-methods/reference-shear-relaxation", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferenceTensileTestRun(
  config: ApiConfig,
  input: {
    specimen_id: string;
    specimen_revision_id: string;
    test_method_id: string;
    test_method_revision_id: string;
    run_label: string;
    performed_at: string;
    test_temperature_k: number | null;
    crosshead_speed_mm_per_min: number | null;
    change_reason: string;
  },
): Promise<ApiResult<TestRunResponse>> {
  return request(config, "/test-runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferenceShearRelaxationTestRun(
  config: ApiConfig,
  input: {
    specimen_id: string;
    specimen_revision_id: string;
    test_method_id: string;
    test_method_revision_id: string;
    run_label: string;
    performed_at: string;
    test_temperature_k: number | null;
    change_reason: string;
  },
): Promise<ApiResult<TestRunResponse>> {
  return request(config, "/test-runs/reference-shear-relaxation", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listTestRunsForMaterialState(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: TestRunResponse[] }>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/test-runs`);
}

export function listTestCampaigns(
  config: ApiConfig,
): Promise<ApiResult<{ items: TestCampaignResponse[] }>> {
  return request(config, "/test-campaigns");
}

export function createTestCampaign(
  config: ApiConfig,
  content: TestCampaignContent,
): Promise<ApiResult<TestCampaignResponse>> {
  return request(config, "/test-campaigns", {
    method: "POST",
    body: JSON.stringify({ content, change_reason: "Register governed Test Campaign" }),
  });
}

export function listInstruments(
  config: ApiConfig,
): Promise<ApiResult<{ items: InstrumentResponse[] }>> {
  return request(config, "/instruments");
}

export function createInstrument(
  config: ApiConfig,
  classification: DataClassification,
  content: InstrumentContent,
): Promise<ApiResult<InstrumentResponse>> {
  return request(config, "/instruments", {
    method: "POST",
    body: JSON.stringify({ classification, content, change_reason: "Register governed Instrument" }),
  });
}

export function listInstrumentCalibrations(
  config: ApiConfig,
  instrumentId: string,
): Promise<ApiResult<{ items: InstrumentCalibrationResponse[] }>> {
  return request(config, `/instruments/${encodeURIComponent(instrumentId)}/calibrations`);
}

export function createInstrumentCalibration(
  config: ApiConfig,
  instrumentId: string,
  content: Omit<InstrumentCalibrationResponse["current_revision"]["content"], "instrument_id">,
): Promise<ApiResult<InstrumentCalibrationResponse>> {
  return request(config, `/instruments/${encodeURIComponent(instrumentId)}/calibrations`, {
    method: "POST",
    body: JSON.stringify({ content, change_reason: "Record exact Instrument calibration" }),
  });
}

export function listTestConditions(
  config: ApiConfig,
): Promise<ApiResult<{ items: TestConditionResponse[] }>> {
  return request(config, "/test-conditions");
}

export function createTestCondition(
  config: ApiConfig,
  content: TestConditionContent,
): Promise<ApiResult<TestConditionResponse>> {
  return request(config, "/test-conditions", {
    method: "POST",
    body: JSON.stringify({ content, change_reason: "Capture typed Test conditions" }),
  });
}

export function getTestRunContext(
  config: ApiConfig,
  testRunId: string,
): Promise<ApiResult<TestRunContextResponse | null>> {
  return request(config, `/test-runs/${encodeURIComponent(testRunId)}/context`);
}

export function createTestRunContext(
  config: ApiConfig,
  testRunId: string,
  content: Omit<TestRunContextContent, "test_run_id">,
): Promise<ApiResult<TestRunContextResponse>> {
  return request(config, `/test-runs/${encodeURIComponent(testRunId)}/context`, {
    method: "POST",
    body: JSON.stringify({ content, change_reason: "Bind exact Test Run execution context" }),
  });
}

export function listDatasetsForMaterialState(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: DatasetResponse[] }>> {
  return request(config, `/material-states/${encodeURIComponent(materialStateId)}/datasets`);
}

export function listShearRelaxationDatasetsForMaterialState(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: ShearRelaxationDatasetResponse[] }>> {
  return request(
    config,
    `/material-states/${encodeURIComponent(materialStateId)}/shear-relaxation-datasets`,
  );
}

export function importReferenceShearRelaxationDataset(
  config: ApiConfig,
  input: {
    test_run_id: string;
    test_run_revision_id: string;
    raw_asset_id: string;
    raw_artifact_id: string;
    mapping: {
      time_column: string;
      shear_modulus_column: string;
      time_unit: "s" | "ms" | "min" | "h";
      shear_modulus_unit: "Pa" | "kPa" | "MPa" | "GPa";
    };
    change_reason: string;
  },
): Promise<ApiResult<ShearRelaxationDatasetResponse>> {
  return request(config, "/shear-relaxation-datasets", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function previewShearRelaxationDataset(
  config: ApiConfig,
  datasetId: string,
  maximumPoints = 500,
): Promise<ApiResult<ShearRelaxationCurvePreview>> {
  return request(
    config,
    `/shear-relaxation-datasets/${encodeURIComponent(datasetId)}/preview?maximum_points=${maximumPoints}`,
  );
}

export function createReferenceShearRelaxationCropRecipe(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    recipe_label: string;
    minimum_time_s: number;
    maximum_time_s: number;
    change_reason: string;
  },
): Promise<ApiResult<ShearRelaxationProcessingRecipeResponse>> {
  return request(config, "/processing-recipes/reference-shear-relaxation-crop", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceShearRelaxationCrop(
  config: ApiConfig,
  input: {
    recipe_id: string;
    recipe_revision_id: string;
    input_dataset_id: string;
    input_dataset_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<ShearRelaxationProcessingRunResponse>> {
  return request(config, "/processing-runs/reference-shear-relaxation-crop", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferencePronyCalibrationPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    plan_label: string;
    input_dataset_id: string;
    input_dataset_revision_id: string;
    baseline_model_id: string;
    baseline_model_revision_id: string;
    total_g_ratio: { lower: number; initial: number; upper: number };
    fast_term_fraction: { lower: number; initial: number; upper: number };
    fast_relaxation_time_s: { lower: number; initial: number; upper: number };
    slow_relaxation_time_s: { lower: number; initial: number; upper: number };
    normalization_modulus_pa: number;
    multistart_count: number;
    random_seed: number;
    change_reason: string;
  },
): Promise<ApiResult<PronyCalibrationPlanResponse>> {
  return request(config, "/prony-calibration-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferencePronyCalibration(
  config: ApiConfig,
  planId: string,
  input: { plan_revision_id: string; change_reason: string },
): Promise<ApiResult<PronyCalibrationRunResponse>> {
  return request(config, `/prony-calibration-plans/${encodeURIComponent(planId)}/runs`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getReferencePronyCandidateDiagnostics(
  config: ApiConfig,
  candidateId: string,
): Promise<ApiResult<PronyCalibrationDiagnosticsResponse>> {
  return request(
    config,
    `/prony-calibration-candidates/${encodeURIComponent(candidateId)}/diagnostics`,
  );
}

export function createReferencePronyCandidateSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    calibration_run_id: string;
    calibration_candidate_id: string;
    selection_reason: string;
  },
): Promise<ApiResult<PronyCandidateSelectionResponse>> {
  return request(config, "/prony-candidate-selections", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function promoteReferencePronyCandidate(
  config: ApiConfig,
  selectionId: string,
  input: { selection_revision_id: string; change_reason: string },
): Promise<ApiResult<LinearViscoelasticModelResponse>> {
  return request(
    config,
    `/prony-candidate-selections/${encodeURIComponent(selectionId)}/promotions`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function listDatasetRevisions(
  config: ApiConfig,
  datasetId: string,
): Promise<ApiResult<{ dataset_id: string; revisions: DatasetResponse["current_revision"][] }>> {
  return request(config, `/datasets/${encodeURIComponent(datasetId)}/revisions`);
}

export function createReferenceDatasetSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    dataset_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<DatasetSelectionResponse>> {
  return request(config, "/dataset-selections", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listDatasetRevisionSelections(
  config: ApiConfig,
  datasetRevisionId: string,
): Promise<ApiResult<{ items: DatasetSelectionResponse[] }>> {
  return request(
    config,
    `/dataset-revisions/${encodeURIComponent(datasetRevisionId)}/selections`,
  );
}

export function createReferenceTensileReplicateSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    dataset_revision_ids: string[];
    change_reason: string;
  },
): Promise<ApiResult<TensileReplicateSelectionResponse>> {
  return request(config, "/dataset-selections/reference-tensile-replicates", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseReferenceTensileReplicateSelection(
  config: ApiConfig,
  selectionId: string,
  input: {
    expected_current_revision_id: string;
    dataset_revision_ids: string[];
    change_reason: string;
  },
): Promise<ApiResult<TensileReplicateSelectionResponse>> {
  return request(
    config,
    `/dataset-selections/reference-tensile-replicates/${encodeURIComponent(selectionId)}/revisions`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function listReferenceTensileReplicateSelections(
  config: ApiConfig,
  materialStateId: string,
): Promise<ApiResult<{ items: TensileReplicateSelectionResponse[] }>> {
  return request(
    config,
    `/dataset-selections/reference-tensile-replicates?material_state_id=${encodeURIComponent(materialStateId)}`,
  );
}

export function listProcessingRecipes(
  config: ApiConfig,
): Promise<ApiResult<{ items: ProcessingRecipeResponse[] }>> {
  return request(config, "/processing-recipes");
}

export function createReferenceTensileCropRecipe(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      recipe_label: string;
      minimum_engineering_strain: number;
      maximum_engineering_strain: number;
    };
    change_reason: string;
  },
): Promise<ApiResult<ProcessingRecipeResponse>> {
  return request(config, "/processing-recipes/reference-tensile-crop", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceTensileCrop(
  config: ApiConfig,
  input: {
    selection_id: string;
    selection_revision_id: string;
    recipe_id: string;
    recipe_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<ProcessingRunResponse>> {
  return request(config, "/processing-runs/reference-tensile-crop", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferenceTensileAlignmentRecipe(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      recipe_label: string;
      grid_start_engineering_strain: number;
      grid_end_engineering_strain: number;
      grid_point_count: number;
      domain_policy: "intersection";
      interpolation_policy: "piecewise_linear";
      extrapolation_policy: "reject";
    };
    change_reason: string;
  },
): Promise<ApiResult<ProcessingRecipeResponse>> {
  return request(config, "/processing-recipes/reference-tensile-common-grid", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceTensileAlignment(
  config: ApiConfig,
  input: {
    selection_id: string;
    selection_revision_id: string;
    recipe_id: string;
    recipe_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<ReplicateAlignmentBatchResponse>> {
  return request(config, "/processing-runs/reference-tensile-common-grid", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listReferenceTensileReplicateStatisticalPlans(
  config: ApiConfig,
  selectionRevisionId: string,
): Promise<ApiResult<{ items: ReplicateStatisticalPlanResponse[] }>> {
  const query = new URLSearchParams({ selection_revision_id: selectionRevisionId, limit: "100" });
  return request(config, `/replicate-statistical-plans?${query.toString()}`);
}

export function createReferenceTensileReplicateStatisticalPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    plan_label: string;
    selection_id: string;
    selection_revision_id: string;
    sample_count: number;
    scalar_distribution?: {
      seed: number;
      bootstrap_samples: 999;
      unit_profile: ExactUnitProfilePin | null;
    } | null;
    change_reason: string;
  },
): Promise<ApiResult<ReplicateStatisticalPlanResponse>> {
  return request(config, "/replicate-statistical-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceTensileReplicateStatistics(
  config: ApiConfig,
  input: { plan_id: string; plan_revision_id: string; change_reason: string },
): Promise<ApiResult<ReplicateStatisticalRunResponse>> {
  return request(config, "/replicate-statistical-runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listReferenceTensileReplicateStatisticalRuns(
  config: ApiConfig,
  planRevisionId: string,
): Promise<ApiResult<{ items: ReplicateStatisticalRunResponse[] }>> {
  const query = new URLSearchParams({ plan_revision_id: planRevisionId, limit: "100" });
  return request(config, `/replicate-statistical-runs?${query.toString()}`);
}

export function getReferenceTensileReplicateStatisticalResult(
  config: ApiConfig,
  resultId: string,
): Promise<ApiResult<ReplicateStatisticalResultResponse>> {
  return request(config, `/replicate-statistical-results/${encodeURIComponent(resultId)}`);
}

export function previewReferenceTensileReplicateStatisticalResultCurve(
  config: ApiConfig,
  resultId: string,
  maximumPoints = 1_000,
): Promise<ApiResult<ReplicateStatisticalCurveResponse>> {
  const query = new URLSearchParams({ maximum_points: String(maximumPoints) });
  return request(
    config,
    `/replicate-statistical-results/${encodeURIComponent(resultId)}/curve?${query.toString()}`,
  );
}

export function getScalarDistributionResult(
  config: ApiConfig,
  resultId: string,
): Promise<ApiResult<ScalarDistributionResultResponse>> {
  return request(config, `/scalar-distribution-results/${encodeURIComponent(resultId)}`);
}

export function listScalarDistributionSelections(
  config: ApiConfig,
  resultId: string,
): Promise<ApiResult<{ items: ScalarDistributionSelectionResponse[] }>> {
  return request(
    config,
    `/scalar-distribution-results/${encodeURIComponent(resultId)}/selections`,
  );
}

export function createScalarDistributionSelection(
  config: ApiConfig,
  resultId: string,
  input: {
    classification: DataClassification;
    distribution_result_revision_id: string;
    selected_family: DistributionFamily;
    candidate_sha256: string;
    selection_reason: string;
  },
): Promise<ApiResult<ScalarDistributionSelectionResponse>> {
  return request(
    config,
    `/scalar-distribution-results/${encodeURIComponent(resultId)}/selections`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function reviseScalarDistributionSelection(
  config: ApiConfig,
  selectionId: string,
  input: {
    expected_current_revision_id: string;
    distribution_result_id: string;
    distribution_result_revision_id: string;
    selected_family: DistributionFamily;
    candidate_sha256: string;
    selection_reason: string;
  },
): Promise<ApiResult<ScalarDistributionSelectionResponse>> {
  return request(
    config,
    `/scalar-distribution-selections/${encodeURIComponent(selectionId)}`,
    { method: "PUT", body: JSON.stringify(input) },
  );
}

export function createReplicateOutlierDetectionPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    plan_label: string;
    statistical_result_id: string;
    statistical_result_revision_id: string;
    absolute_modified_z_threshold: number;
    change_reason: string;
  },
): Promise<ApiResult<ReplicateOutlierPlanResponse>> {
  return request(config, "/replicate-outlier-detection-plans", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReplicateOutlierDetection(
  config: ApiConfig,
  input: { detection_plan_id: string; detection_plan_revision_id: string },
): Promise<ApiResult<ReplicateOutlierRunResponse>> {
  return request(config, "/replicate-outlier-detection-runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReplicateOutlierAssessment(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    candidate_id: string;
    detection_plan_id: string;
    detection_plan_revision_id: string;
    decision: ReplicateOutlierDecision;
    assessment_reason: string;
    change_reason: string;
  },
): Promise<ApiResult<ReplicateOutlierAssessmentResponse>> {
  return request(config, "/replicate-outlier-assessments", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferenceCalibrationInputScope(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    scope_label: string;
    detection_run_id: string;
    assessment_revision_ids: string[];
    change_reason: string;
  },
): Promise<ApiResult<ReferenceCalibrationScopeResponse>> {
  return request(config, "/reference-calibration-input-scopes", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listStatisticalPlans(
  config: ApiConfig,
): Promise<ApiResult<{ items: StatisticalPlanResponse[] }>> {
  return request(config, "/statistical-plans?limit=100");
}

export function createReferenceTensilePairStatisticalPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      plan_label: string;
      first_selection_id: string;
      first_selection_revision_id: string;
      second_selection_id: string;
      second_selection_revision_id: string;
    };
    change_reason: string;
  },
): Promise<ApiResult<StatisticalPlanResponse>> {
  return request(config, "/statistical-plans/reference-tensile-pair", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceTensilePairStatistics(
  config: ApiConfig,
  input: {
    plan_id: string;
    plan_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<StatisticalRunResponse>> {
  return request(config, "/statistical-runs/reference-tensile-pair", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getStatisticalResult(
  config: ApiConfig,
  resultId: string,
): Promise<ApiResult<StatisticalResultResponse>> {
  return request(config, `/statistical-results/${encodeURIComponent(resultId)}`);
}

export function previewStatisticalResultCurve(
  config: ApiConfig,
  resultId: string,
  maximumPoints = 1_000,
): Promise<ApiResult<StatisticalCurvePreview>> {
  const query = new URLSearchParams({ maximum_points: String(maximumPoints) });
  return request(
    config,
    `/statistical-results/${encodeURIComponent(resultId)}/curve?${query.toString()}`,
  );
}

export function listOutlierDetectionPlans(
  config: ApiConfig,
): Promise<ApiResult<{ items: OutlierDetectionPlanResponse[] }>> {
  return request(config, "/outlier-detection-plans?limit=100");
}

export function createReferenceTensilePairOutlierDetectionPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      plan_label: string;
      statistical_result_id: string;
      statistical_result_revision_id: string;
      relative_peak_difference_threshold: number;
    };
    change_reason: string;
  },
): Promise<ApiResult<OutlierDetectionPlanResponse>> {
  return request(config, "/outlier-detection-plans/reference-tensile-pair", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceTensilePairOutlierDetection(
  config: ApiConfig,
  input: {
    detection_plan_id: string;
    detection_plan_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<OutlierDetectionRunResponse>> {
  return request(config, "/outlier-detection-runs/reference-tensile-pair", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferenceTensilePairOutlierAssessment(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: {
      candidate_id: string;
      statistical_plan_id: string;
      statistical_plan_revision_id: string;
      decision: "retained" | "excluded_from_reference_analysis";
      assessment_reason: string;
    };
    change_reason: string;
  },
): Promise<ApiResult<OutlierAssessmentResponse>> {
  return request(config, "/outlier-assessments/reference-tensile-pair", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getReferenceTensilePairOutlierScopeComparison(
  config: ApiConfig,
  input: {
    detection_plan_id: string;
    detection_plan_revision_id: string;
  },
): Promise<ApiResult<OutlierScopeComparisonResponse>> {
  const query = new URLSearchParams({
    detection_plan_id: input.detection_plan_id,
    detection_plan_revision_id: input.detection_plan_revision_id,
  });
  return request(
    config,
    `/outlier-scope-comparisons/reference-tensile-pair?${query.toString()}`,
  );
}

export function importReferenceTensileDataset(
  config: ApiConfig,
  input: {
    test_run_id: string;
    test_run_revision_id: string;
    raw_asset_id: string;
    raw_artifact_id: string;
    mapping: ReferenceTensileMapping;
    change_reason: string;
  },
): Promise<ApiResult<DatasetResponse>> {
  return request(config, "/datasets/reference-uniaxial-tensile:import", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function detectReferenceImport(
  config: ApiConfig,
  input: { raw_asset_id: string; raw_artifact_id: string },
): Promise<ApiResult<ImportDetectionReportResponse>> {
  return request(config, "/imports:detect", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createReferenceImportMapping(
  config: ApiConfig,
  input: {
    detection_report_id: string;
    mapping_label: string;
    strain_column: string;
    stress_column: string;
    strain_unit: ReferenceTensileMapping["strain_unit"];
    stress_unit: ReferenceTensileMapping["stress_unit"];
    change_reason: string;
  },
): Promise<ApiResult<ImportMappingResponse>> {
  return request(config, "/import-mappings", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeReferenceImport(
  config: ApiConfig,
  input: {
    test_run_id: string;
    test_run_revision_id: string;
    raw_asset_id: string;
    raw_artifact_id: string;
    import_mapping_id: string;
    import_mapping_revision_id: string;
    change_reason: string;
  },
): Promise<ApiResult<ImportRunResponse>> {
  return request(config, "/imports", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function previewDatasetCurve(
  config: ApiConfig,
  datasetRevisionId: string,
  maximumPoints = 1_000,
): Promise<ApiResult<CurvePreview>> {
  const query = new URLSearchParams({ maximum_points: String(maximumPoints) });
  return request(
    config,
    `/dataset-revisions/${encodeURIComponent(datasetRevisionId)}/curve?${query.toString()}`,
  );
}

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

export async function uploadReferenceTensileCsv(
  config: ApiConfig,
  input: {
    file: File;
    classification: DataClassification;
    test_run_revision_id: string;
  },
): Promise<ApiResult<CompletedUpload>> {
  const filename = input.file.name.trim();
  if (!filename || filename.includes("/") || filename.includes("\\")) {
    throw new ApiError(422, "Choose a CSV file with a safe, non-empty filename.");
  }
  if (input.file.size < 1 || input.file.size > 16 * 1024 * 1024) {
    throw new ApiError(422, "The reference CSV must be between 1 byte and 16 MiB.");
  }
  const digest = await sha256Hex(input.file);
  const created = await request<{ upload: UploadSession; upload_capability: string }>(config, "/uploads", {
    method: "POST",
    headers: { "Idempotency-Key": browserIdempotencyKey() },
    body: JSON.stringify({
      classification: input.classification,
      original_filename: filename,
      media_type: "text/csv",
      expected_size_bytes: input.file.size,
      expected_sha256: digest,
      test_run_revision_id: input.test_run_revision_id,
    }),
  });
  const { upload, upload_capability: capability } = created.data;
  for (let partNumber = 1; partNumber <= upload.expected_part_count; partNumber += 1) {
    const start = (partNumber - 1) * upload.part_size_bytes;
    const part = input.file.slice(start, Math.min(input.file.size, start + upload.part_size_bytes));
    await request<UploadSession>(
      config,
      `/uploads/${encodeURIComponent(upload.upload_id)}/parts/${partNumber}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "text/csv",
          "Upload-Capability": capability,
        },
        body: part,
      },
    );
  }
  return request<CompletedUpload>(
    config,
    `/uploads/${encodeURIComponent(upload.upload_id)}:complete`,
    {
      method: "POST",
      headers: { "Upload-Capability": capability },
    },
  );
}

export async function uploadGovernedTabularFile(
  config: ApiConfig,
  input: {
    file: File;
    file_format: GovernedTabularFileFormat;
    classification: DataClassification;
    test_run_revision_id?: string | null;
  },
): Promise<ApiResult<CompletedUpload>> {
  const filename = input.file.name.trim();
  if (!filename || filename.includes("/") || filename.includes("\\")) {
    throw new ApiError(422, "Choose a file with a safe, non-empty filename.");
  }
  if (input.file.size < 1 || input.file.size > 16 * 1024 * 1024) {
    throw new ApiError(422, "The governed source must be between 1 byte and 16 MiB.");
  }
  const mediaType = {
    csv: "text/csv",
    tsv: "text/tab-separated-values",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  }[input.file_format];
  const digest = await sha256Hex(input.file);
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
        test_run_revision_id: input.test_run_revision_id ?? null,
      }),
    },
  );
  const { upload, upload_capability: capability } = created.data;
  for (let partNumber = 1; partNumber <= upload.expected_part_count; partNumber += 1) {
    const start = (partNumber - 1) * upload.part_size_bytes;
    const part = input.file.slice(start, Math.min(input.file.size, start + upload.part_size_bytes));
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
  return request<CompletedUpload>(
    config,
    `/uploads/${encodeURIComponent(upload.upload_id)}:complete`,
    { method: "POST", headers: { "Upload-Capability": capability } },
  );
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

export function previewGovernedTabularImport(
  config: ApiConfig,
  input: {
    raw_asset_id: string;
    raw_artifact_id: string;
    file_format: GovernedTabularFileFormat;
    sheet_name: string | null;
    header_row: number;
    encoding: string;
    delimiter: string | null;
    decimal_separator: "." | ",";
  },
): Promise<ApiResult<GovernedImportPreview>> {
  return request(config, "/tabular-import-previews", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function listGovernedImportProfiles(
  config: ApiConfig,
): Promise<ApiResult<GovernedImportProfileResponse[]>> {
  const result = await request<{ items: GovernedImportProfileResponse[] }>(
    config,
    "/import-profiles",
  );
  return { data: result.data.items, etag: result.etag };
}

export function createGovernedImportProfile(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    content: GovernedImportProfileContent;
    change_reason: string;
  },
): Promise<ApiResult<GovernedImportProfileResponse>> {
  return request(config, "/import-profiles", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reviseGovernedImportProfile(
  config: ApiConfig,
  profileId: string,
  input: {
    expected_current_revision_id: string;
    content: GovernedImportProfileContent;
    change_reason: string;
  },
): Promise<ApiResult<GovernedImportProfileResponse>> {
  return request(config, `/import-profiles/${encodeURIComponent(profileId)}/revisions`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeGovernedTabularImport(
  config: ApiConfig,
  input: {
    test_run_id: string;
    test_run_revision_id: string;
    raw_asset_id: string;
    raw_artifact_id: string;
    import_profile_id: string;
    import_profile_revision_id: string;
    change_reason: string;
  },
  idempotencyKey: string = crypto.randomUUID(),
): Promise<ApiResult<GovernedImportRunResponse>> {
  return request(config, "/tabular-import-runs", {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(input),
  });
}

export function listGovernedDatasetsForTestRun(
  config: ApiConfig,
  testRunId: string,
): Promise<ApiResult<{ items: GovernedDatasetResponse[] }>> {
  return request(
    config,
    `/governed-datasets?test_run_id=${encodeURIComponent(testRunId)}`,
  );
}

export function createViscoelasticSelection(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    selection_label: string;
    members: Array<{ dataset_id: string; dataset_revision_id: string }>;
    change_reason: string;
  },
): Promise<ApiResult<ViscoelasticSelectionResponse>> {
  return request(config, "/viscoelastic-selections", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createViscoelasticMasterPlan(
  config: ApiConfig,
  input: {
    classification: DataClassification;
    plan_label: string;
    selection_id: string;
    selection_revision_id: string;
    reference_temperature_k: number;
    grid_point_count: number;
    shift_method: ViscoelasticShiftMethod;
    manual_shift_factors: Array<{ temperature_k: number; log10_a_t: number }>;
    change_reason: string;
  },
): Promise<ApiResult<ViscoelasticMasterPlanResponse>> {
  return request(config, "/processing-plans/viscoelastic-master-curve", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function executeViscoelasticMasterPlan(
  config: ApiConfig,
  input: { plan_id: string; plan_revision_id: string; change_reason: string },
): Promise<ApiResult<ViscoelasticMasterRunResponse>> {
  return request(config, "/processing-runs/viscoelastic-master-curve", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function previewViscoelasticMasterRun(
  config: ApiConfig,
  runId: string,
): Promise<ApiResult<ViscoelasticMasterPreviewResponse>> {
  return request(
    config,
    `/processing-runs/viscoelastic-master-curve/${encodeURIComponent(runId)}/preview`,
  );
}
