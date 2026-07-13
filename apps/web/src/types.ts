export type DataClassification =
  | "internal"
  | "confidential"
  | "restricted"
  | "export_controlled";

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

export interface Applicability {
  temperature_min_k: number | null;
  temperature_max_k: number | null;
  strain_rate_min_per_s: number | null;
  strain_rate_max_per_s: number | null;
  note: string | null;
}

export interface ProvenanceSummary {
  entity_type: string;
  reference_type: string;
  revision_id: string;
  content_sha256: string;
  based_on_revision_id: string | null;
  recorded_at: string;
  recorded_by: string;
}

export interface RevisionMetadata {
  id: string;
  aggregate_id: string;
  revision_no: number;
  based_on_revision_id: string | null;
  schema_id: string;
  schema_version: string;
  content_hash: string;
  created_at: string;
  created_by: string;
  change_reason: string;
  organization_id: string;
  project_id: string;
  classification: DataClassification;
  lifecycle_state: "draft";
}

export interface MaterialContent {
  name: string;
  material_code: string | null;
  material_family: string | null;
  description: string | null;
}

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

export interface MaterialStateCreateInput {
  content: Omit<MaterialStateContent, "material_id">;
  change_reason: string;
}

export interface PropertySetCreateInput {
  content: Omit<PropertySetContent, "material_state_id">;
  change_reason: string;
}

export interface ReferenceLinearElasticContent {
  model_family_id: string;
  model_schema_version: string;
  model_schema_digest: string;
  material_id: string;
  material_revision_id: string;
  material_state_id: string;
  material_state_revision_id: string;
  property_set_id: string;
  property_set_revision_id: string;
  density_kg_per_m3: number;
  youngs_modulus_pa: number;
  poisson_ratio: number;
  source_yield_stress_pa: number | null;
  applicable_temperature_min_k: number | null;
  applicable_temperature_max_k: number | null;
  applicable_strain_rate_min_per_s: number | null;
  applicable_strain_rate_max_per_s: number | null;
  applicability_note: string | null;
  reference_temperature_k: number;
  non_production: true;
}

export interface MaterialModelProvenanceSummary extends ProvenanceSummary {
  source_property_set_revision_id: string;
}

export interface MaterialModelRevision extends RevisionMetadata {
  content: ReferenceLinearElasticContent;
  ir: Record<string, unknown>;
  provenance: MaterialModelProvenanceSummary;
}

export interface MaterialModelResponse {
  material_model_id: string;
  material_state_id: string;
  current_revision: MaterialModelRevision;
  links: {
    self: string;
    revisions: string;
    preflight: string;
    solver_cards: string;
  };
}

export interface MaterialModelList {
  items: MaterialModelResponse[];
}

export interface ReferenceModelCreateInput {
  property_set_revision_id: string;
  change_reason: string;
}

export interface ExportTarget {
  solver: string;
  version: string;
  unit_system: string;
}

export type MappingStatus =
  | "exact"
  | "transformed"
  | "approximated"
  | "ignored"
  | "unsupported"
  | "not_applicable";

export interface MappingItem {
  name: string;
  ir_path: string;
  target_representation: string | null;
  status: MappingStatus;
  detail: string;
}

export interface MappingReport {
  material_model_id: string;
  material_model_revision_id: string;
  model_schema_digest: string;
  target: ExportTarget;
  items: MappingItem[];
  exporter_id: string;
  exporter_version: string;
  exporter_digest: string;
  mapping_report_sha256: string;
  exportable: boolean;
  non_production: true;
}

export interface SolverCardContent {
  material_model_id: string;
  material_model_revision_id: string;
  model_schema_digest: string;
  target: ExportTarget;
  solver_material_id: number;
  card_title: string;
  density_kg_per_m3: number;
  youngs_modulus_pa: number;
  poisson_ratio: number;
  source_yield_stress_pa: number | null;
  applicable_temperature_min_k: number | null;
  applicable_temperature_max_k: number | null;
  applicable_strain_rate_min_per_s: number | null;
  applicable_strain_rate_max_per_s: number | null;
  mapping_report_sha256: string;
  card_sha256: string;
  exporter_id: string;
  exporter_version: string;
  exporter_digest: string;
  non_production: true;
}

export interface SolverCardProvenanceSummary extends ProvenanceSummary {
  source_material_model_revision_id: string;
  mapping_report_sha256: string;
}

export interface SolverCardRevision extends RevisionMetadata {
  content: SolverCardContent;
  mapping_report: MappingReport;
  provenance: SolverCardProvenanceSummary;
}

export interface SolverCardResponse {
  solver_card_id: string;
  material_model_id: string;
  target: ExportTarget;
  solver_material_id: number;
  current_revision: SolverCardRevision;
  links: {
    self: string;
    revisions: string;
    preview: string;
    download: string;
  };
}

export interface SolverCardList {
  items: SolverCardResponse[];
}

export interface SolverCardCreateInput {
  material_model_revision_id: string;
  target: ExportTarget;
  expected_mapping_report_sha256: string;
  solver_material_id: number;
  card_title: string;
  change_reason: string;
}
