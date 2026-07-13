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
