import type {
  Applicability,
  DataClassification,
  ProvenanceSummary,
  RevisionMetadata,
} from "../../../shared/model/core-contracts";

export type PropertySourceKind =
  | "manual"
  | "supplier_datasheet"
  | "test_derived"
  | "literature"
  | "calibration";

export interface PropertySource {
  kind: PropertySourceKind;
  reference: string | null;
}

export interface MaterialContent {
  name: string;
  material_code: string | null;
  material_family: string | null;
  description: string | null;
  material_class: MaterialClass;
}

export type MaterialClass =
  | "unclassified"
  | "metal"
  | "polymer"
  | "elastomer"
  | "composite"
  | "ceramic"
  | "other";

export interface MaterialRevision extends RevisionMetadata {
  content: MaterialContent;
  provenance: ProvenanceSummary;
}

export interface MaterialResponse {
  material_id: string;
  current_revision: MaterialRevision;
  links: {
    self: string;
    revisions: string;
    states: string;
  };
}

export interface MaterialStateContent {
  material_id: string;
  material_revision_id: string;
  name: string;
  manufacturing_route: string | null;
  heat_treatment: string | null;
  lot_or_batch: string | null;
  description: string | null;
}

export interface MaterialStateRevision extends RevisionMetadata {
  content: MaterialStateContent;
  provenance: ProvenanceSummary;
}

export interface MaterialStateResponse {
  material_state_id: string;
  material_id: string;
  current_revision: MaterialStateRevision;
  property_sets_url: string;
}

export type ProcessKind = "manufacturing" | "heat_treatment" | "conditioning" | "other";
export type LotKind = "lot" | "batch";

export interface ProcessDefinitionContent {
  process_code: string;
  name: string;
  kind: ProcessKind;
  description: string | null;
}

export interface ProcessDefinitionResponse {
  process_definition_id: string;
  current_revision: RevisionMetadata & {
    content: ProcessDefinitionContent;
    provenance: ProvenanceSummary;
  };
}

export interface MaterialLotContent {
  material_id: string;
  material_revision_id: string;
  lot_code: string;
  kind: LotKind;
  manufacturer: string | null;
  supplier: string | null;
  description: string | null;
}

export interface MaterialLotResponse {
  material_lot_id: string;
  material_id: string;
  current_revision: RevisionMetadata & {
    content: MaterialLotContent;
    provenance: ProvenanceSummary;
  };
}

export interface StateGenealogyContent {
  material_state_id: string;
  material_state_revision_id: string;
  manufacturing_process_id: string | null;
  manufacturing_process_revision_id: string | null;
  heat_treatment_process_id: string | null;
  heat_treatment_process_revision_id: string | null;
  material_lot_id: string | null;
  material_lot_revision_id: string | null;
  note: string | null;
}

export interface StateGenealogyResponse {
  state_genealogy_id: string;
  material_state_id: string;
  current_revision: RevisionMetadata & {
    content: StateGenealogyContent;
    provenance: ProvenanceSummary;
  };
}

export type BalanceBasis = "mass" | "volume" | "count" | "not_assessed";

export interface LotFlowContent {
  material_lot_id: string;
  material_lot_revision_id: string;
  original_quantity: string;
  original_unit: string;
  quantity_basis: Exclude<BalanceBasis, "not_assessed">;
  normalized_quantity: string;
  normalized_unit: string;
  normalization_factor: string;
}

export interface ProcessRunContent {
  process_definition_id: string;
  process_definition_revision_id: string;
  material_state_id: string;
  material_state_revision_id: string;
  run_code: string;
  started_at: string;
  ended_at: string | null;
  operator_name: string | null;
  equipment_reference: string | null;
  balance_basis: BalanceBasis;
  balance_tolerance_fraction: string | null;
  balance_not_assessed_reason: string | null;
  balance: {
    input_total: string;
    output_total: string;
    relative_difference: string;
    within_tolerance: boolean;
  } | null;
  inputs: LotFlowContent[];
  outputs: LotFlowContent[];
  note: string | null;
}

export interface ProcessRunResponse {
  process_run_id: string;
  material_state_id: string;
  current_revision: RevisionMetadata & {
    content: ProcessRunContent;
    provenance: ProvenanceSummary;
  };
}

export interface ProcessDefinitionCreateInput {
  classification: DataClassification;
  content: ProcessDefinitionContent;
  change_reason: string;
}

export interface MaterialLotCreateInput {
  content: Omit<MaterialLotContent, "material_id">;
  change_reason: string;
}

export interface StateGenealogyCreateInput {
  content: Omit<StateGenealogyContent, "material_state_id">;
  change_reason: string;
}

export interface ProcessRunCreateInput {
  content: {
    process_definition_id: string;
    process_definition_revision_id: string;
    material_state_revision_id: string;
    run_code: string;
    started_at: string;
    ended_at: string | null;
    operator_name: string | null;
    equipment_reference: string | null;
    balance_basis: BalanceBasis;
    balance_tolerance_fraction: string | null;
    balance_not_assessed_reason: string | null;
    inputs: Array<{
      material_lot_id: string;
      material_lot_revision_id: string;
      original_quantity: string;
      original_unit: string;
    }>;
    outputs: Array<{
      material_lot_id: string;
      material_lot_revision_id: string;
      original_quantity: string;
      original_unit: string;
    }>;
    note: string | null;
  };
  change_reason: string;
}

export interface PropertySetContent {
  material_state_id: string;
  material_state_revision_id: string;
  density_kg_per_m3: number;
  density_source: PropertySource;
  youngs_modulus_pa: number;
  youngs_modulus_source: PropertySource;
  poisson_ratio: number;
  poisson_ratio_source: PropertySource;
  yield_stress_pa: number | null;
  yield_stress_source: PropertySource | null;
  applicability: Applicability;
}

export interface PropertySetRevision extends RevisionMetadata {
  content: PropertySetContent;
  provenance: ProvenanceSummary;
}

export interface PropertySetResponse {
  property_set_id: string;
  material_state_id: string;
  current_revision: PropertySetRevision;
}

export interface MaterialDetail {
  material: MaterialResponse;
  states: MaterialStateResponse[];
  property_sets: PropertySetResponse[];
}

export interface MaterialRevisionList {
  material_id: string;
  revisions: MaterialRevision[];
}

export interface MaterialRevisionComparison {
  material_id: string;
  left: MaterialRevision;
  right: MaterialRevision;
  changed_fields: string[];
}

export interface MaterialCreateInput {
  classification: DataClassification;
  content: Omit<MaterialContent, "material_id">;
  change_reason: string;
}

export interface MaterialReviseInput {
  content: MaterialContent;
  change_reason: string;
}

export interface MaterialStateCreateInput {
  content: Omit<MaterialStateContent, "material_id">;
  change_reason: string;
}

export type MaterialStateReviseInput = MaterialStateCreateInput;

export interface PropertySetCreateInput {
  content: Omit<PropertySetContent, "material_state_id">;
  change_reason: string;
}

export type BulkExportMemberKind =
  | "raw_original"
  | "dataset_parquet"
  | "dataset_csv"
  | "model_ir_json"
  | "model_ir_schema"
  | "solver_mapping_report"
  | "solver_card_native"
  | "test_data_json"
  | "mapping_profile_json"
  | "processing_recipe_json"
  | "neutral_material_json"
  | "neutral_solver_mapping_report"
  | "neutral_solver_card_native";

export interface BulkExportSourceRef {
  kind: BulkExportMemberKind;
  raw_asset_id: string | null;
  artifact_id: string | null;
  dataset_id: string | null;
  dataset_revision_id: string | null;
  material_model_id: string | null;
  material_model_revision_id: string | null;
  solver_card_id: string | null;
  solver_card_revision_id: string | null;
  test_data_document_id?: string | null;
  test_data_document_revision_id?: string | null;
  mapping_profile_id?: string | null;
  mapping_profile_revision_id?: string | null;
  processing_recipe_id?: string | null;
  processing_recipe_revision_id?: string | null;
  neutral_material_id?: string | null;
  neutral_material_revision_id?: string | null;
  neutral_solver_card_id?: string | null;
  neutral_solver_card_revision_id?: string | null;
}

export interface BulkExportCandidate {
  source: BulkExportSourceRef;
  classification: DataClassification;
  source_sha256: string;
  source_size_bytes: number;
  media_type: string;
  default_archive_path: string;
  label: string;
}

export interface ExportSelectionResponse {
  export_selection_id: string;
  current_revision: RevisionMetadata & {
    content: {
      selection_label: string;
      classification: DataClassification;
      expected_size_bytes: number;
      selection_digest: string;
      members: Array<BulkExportCandidate & { ordinal: number; archive_path: string }>;
      omissions: Array<{
        ordinal: number;
        source: BulkExportSourceRef;
        reason_code: string;
        reason: string;
      }>;
    };
  };
  links: Record<string, string | null>;
}

export interface BulkExportJobResponse {
  export_job_id: string;
  classification: DataClassification;
  export_selection_id: string;
  export_selection_revision_id: string;
  state:
    | "queued"
    | "running"
    | "reconciliation_required"
    | "reconciling"
    | "succeeded"
    | "failed";
  attempt_count: number;
  bundle_id: string | null;
  failure_code: string | null;
  failure_detail: string | null;
  submitted_at: string;
  submitted_by: string;
  started_at: string | null;
  completed_at: string | null;
  lease_expires_at: string | null;
  heartbeat_at: string | null;
  committed_output: {
    output_commit_id: string;
    archive_artifact_id: string;
    archive_sha256: string;
    archive_size_bytes: number;
    manifest_sha256: string;
    committed_at: string;
    committed_by: string;
  } | null;
  links: Record<string, string | null>;
}

export interface BulkExportBundleResponse {
  export_bundle_id: string;
  classification: DataClassification;
  export_selection_id: string;
  export_selection_revision_id: string;
  archive_artifact_id: string;
  archive_sha256: string;
  archive_size_bytes: number;
  manifest_sha256: string;
  component_count: number;
  omission_count: number;
  created_at: string;
  created_by: string;
  links: Record<string, string | null>;
}
