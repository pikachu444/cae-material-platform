export type DataClassification =
  | "internal"
  | "confidential"
  | "restricted"
  | "export_controlled";

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
  lifecycle_state: "draft" | "published";
}
