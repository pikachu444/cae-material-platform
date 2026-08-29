import type { RevisionMetadata } from "../../../shared/model/core-contracts";

import type {

  CurveMetadataContract,

  CurveSeriesPreviewContract,

} from "../../../shared/model/curve-contracts";

export type ConfigurableAttributeDataType =
  | "number"
  | "integer"
  | "text"
  | "boolean"
  | "date"
  | "discrete"
  | "file"
  | "curve"
  | "record_reference";

export type CatalogDataCategory =
  | "technical_data"
  | "test_data"
  | "simulation_data"
  | "solver_cards";

export interface ConfigurableTableContent {
  key: string;
  name: string;
  description: string | null;
  data_category?: Exclude<CatalogDataCategory, "solver_cards"> | null;
}

export interface ConfigurableDatabaseContent {
  key: string;
  name: string;
  description: string | null;
}

export interface ConfigurableDatabaseResponse {
  database_id: string;
  current_revision: RevisionMetadata & { content: ConfigurableDatabaseContent };
}

export interface ConfigurableProfileContent {
  database_id: string;
  database_revision_id: string;
  key: string;
  name: string;
  description: string | null;
}

export interface ConfigurableProfileResponse {
  profile_id: string;
  current_revision: RevisionMetadata & { content: ConfigurableProfileContent };
}

export interface ConfigurableTableResponse {
  table_id: string;
  current_revision: RevisionMetadata & { content: ConfigurableTableContent };
}

export interface ConfigurableAttributeContent {
  table_revision_id: string;
  key: string;
  name: string;
  data_type: ConfigurableAttributeDataType;
  required: boolean;
  quantity_semantics: string | null;
  normalized_unit: string | null;
  minimum_number: number | null;
  maximum_number: number | null;
  minimum_length: number | null;
  maximum_length: number | null;
  pattern: string | null;
  allowed_values: string[];
  reference_table_id: string | null;
  help_text: string | null;
  business_key?: boolean;
}

export interface ConfigurableAttributeResponse {
  attribute_definition_id: string;
  table_id: string;
  current_revision: ConfigurableAttributeRevision;
}

export type ConfigurableAttributeRevision = RevisionMetadata & {
  content: ConfigurableAttributeContent;
};

export interface ConfigurableLayoutItem {
  attribute_definition_id: string;
  attribute_definition_revision_id: string;
  section: string;
  ordinal: number;
}

export interface ConfigurableLayoutResponse {
  layout_id: string;
  table_id: string;
  table_revision_id: string;
  revision: RevisionMetadata;
  name: string;
  description: string | null;
  items: ConfigurableLayoutItem[];
}

export interface ConfigurableSubsetResponse {
  subset_id: string;
  table_id: string;
  table_revision_id: string;
  revision: RevisionMetadata;
  name: string;
  description: string | null;
  filter_definition: Record<string, unknown> | null;
}

export interface ConfigurableCatalogFolderResponse {
  folder_id: string;
  table_id: string;
  current_revision: RevisionMetadata;
  content: {
    table_revision_id: string;
    name: string;
    description: string | null;
    parent_folder_id: string | null;
    parent_folder_revision_id: string | null;
  };
}

interface ConfigurableRecordValueBase {
  attribute_definition_id: string;
  attribute_definition_revision_id: string;
}

export type ConfigurableRecordValue =
  | (ConfigurableRecordValueBase & {
      data_type: "number";
      original_value: string;
      original_unit_string: string;
      normalized_value: string;
      normalized_unit: string;
      quantity_semantics: string;
    })
  | (ConfigurableRecordValueBase & { data_type: "integer"; value: number })
  | (ConfigurableRecordValueBase & { data_type: "text"; value: string })
  | (ConfigurableRecordValueBase & { data_type: "boolean"; value: boolean })
  | (ConfigurableRecordValueBase & { data_type: "date"; value: string })
  | (ConfigurableRecordValueBase & { data_type: "discrete"; value: string })
  | (ConfigurableRecordValueBase & {
      data_type: "file";
      artifact_id: string;
      artifact_sha256: string;
    })
  | (ConfigurableRecordValueBase & {
      data_type: "curve";
      artifact_id: string;
      artifact_sha256: string;
    })
  | (ConfigurableRecordValueBase & {
      data_type: "record_reference";
      target_record_id: string;
      target_record_revision_id: string;
    });

export interface ConfigurableCatalogRecordContent {
  table_revision_id: string;
  name: string;
  external_key: string | null;
  description: string | null;
  folder_id: string | null;
  folder_revision_id: string | null;
  values: ConfigurableRecordValue[];
}

export interface ConfigurableCatalogRecordResponse {
  record_id: string;
  table_id: string;
  current_revision: RevisionMetadata & { content: ConfigurableCatalogRecordContent };
  domain_binding?: DomainRevisionBinding | null;
  domain_bindings?: DomainRevisionBinding[];
}

export interface ConfigurableRegistrationCellError {
  row: number;
  column: string;
  message: string;
  action: string;
}

export interface ConfigurableRegistrationPreviewResponse {
  token: string;
  valid: boolean;
  rows: Array<Record<string, unknown>>;
  errors: ConfigurableRegistrationCellError[];
  source_columns: string[];
  sample_rows: Array<Record<string, unknown>>;
}

export interface ConfigurableCatalogRecordSearchResponse {
  items: ConfigurableCatalogRecordResponse[];
  total_count: number;
  offset: number;
  limit: number;
  facets: Array<{
    attribute_definition_id: string;
    value: string;
    count: number;
  }>;
}

export interface ConfigurableCatalogRecordRevisionList {
  items: Array<RevisionMetadata & { content: ConfigurableCatalogRecordContent }>;
}

export interface ConfigurableCatalogRecordComparison {
  record_id: string;
  from_revision: RevisionMetadata & { content: ConfigurableCatalogRecordContent };
  to_revision: RevisionMetadata & { content: ConfigurableCatalogRecordContent };
  metadata_changed: boolean;
  value_differences: Array<{
    attribute_definition_id: string;
    status: "added" | "removed" | "changed" | "unchanged";
    before: ConfigurableRecordValue | null;
    after: ConfigurableRecordValue | null;
  }>;
}

export type ConfigurableLinkCardinality = "one" | "many";

export interface ConfigurableLinkTypeContent {
  key: string;
  name: string;
  source_table_id: string;
  source_table_revision_id: string;
  target_table_id: string;
  target_table_revision_id: string;
  forward_label: string;
  reverse_label: string;
  source_cardinality: ConfigurableLinkCardinality;
  target_cardinality: ConfigurableLinkCardinality;
  description: string | null;
}

export interface ConfigurableLinkTypeResponse {
  link_type_id: string;
  current_revision: RevisionMetadata & { content: ConfigurableLinkTypeContent };
}

export interface ConfigurableRecordLinkContent {
  link_type_id: string;
  link_type_revision_id: string;
  source_record_id: string;
  source_record_revision_id: string;
  target_record_id: string;
  target_record_revision_id: string;
  active: boolean;
  note: string | null;
}

export interface ConfigurableRecordLinkResponse {
  record_link_id: string;
  current_revision: RevisionMetadata & { content: ConfigurableRecordLinkContent };
}

export interface ConfigurableLinkEndpoint {
  record_id: string;
  record_revision_id: string;
  revision_no: number;
  table_id: string;
  name: string;
  external_key: string | null;
  /** Category from the immutable Table revision pinned by this Record. */
  data_category: CatalogDataCategory | null;
  domain_binding: DomainRevisionBinding | null;
  /** All approved bindings on this exact record revision.  `domain_binding`
   * remains the backwards-compatible primary summary. */
  domain_bindings?: DomainRevisionBinding[];
}

export type DomainBindingKind =
  | "material"
  | "material_state"
  | "specimen"
  | "test_run"
  | "test_data"
  | "processing_output"
  | "material_model"
  | "neutral_material"
  | "solver_card"
  | "neutral_solver_card"
  | "release";

export interface DomainRevisionBinding {
  binding_id: string;
  record_id: string;
  record_revision_id: string;
  kind: DomainBindingKind;
  object_id: string;
  revision_id: string;
  workbench_path: string;
}

export interface ConfigurableRecordLinkView {
  record_link_id: string;
  current_revision: RevisionMetadata & { content: ConfigurableRecordLinkContent };
  link_type_revision: RevisionMetadata & { content: ConfigurableLinkTypeContent };
  source: ConfigurableLinkEndpoint;
  target: ConfigurableLinkEndpoint;
}

export interface CatalogExplorerChildrenResponse {
  table: ConfigurableTableResponse;
  folders: ConfigurableCatalogFolderResponse[];
  records: ConfigurableCatalogRecordResponse[];
}

export interface CatalogWorkflowGraphResponse {
  root: ConfigurableLinkEndpoint;
  nodes: ConfigurableLinkEndpoint[];
  links: ConfigurableRecordLinkView[];
}

export interface CatalogCurvePreviewResponse {
  record_id: string;
  record_revision_id: string;
  attribute_definition_id: string;
  curve_available: true;
  modeling_use: "fit_input" | "view_only" | "unavailable";
  modeling_source: DomainRevisionBinding | null;
  curve_metadata: CurveMetadataContract;
  curve_series: CurveSeriesPreviewContract | null;
}
