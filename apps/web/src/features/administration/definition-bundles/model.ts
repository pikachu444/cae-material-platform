import type { DataClassification } from "../../../shared/model/core-contracts";

export type { DataClassification } from "../../../shared/model/core-contracts";

export interface SchemaDefinitionBundleSourceArtifact {
  artifact_id: string;
  organization_id: string;
  project_id: string;
  classification: DataClassification;
  media_type: string;
  size_bytes: number;
  sha256: string;
}

export interface SchemaDefinitionBundleSummary {
  bundle_key: string;
  bundle_version: string;
  scope: {
    organization_id: string;
    project_id: string;
    classification: DataClassification;
  };
  database_key: string;
  profile_key: string;
  record_schema_count: number;
  unit_profile_count: number;
  dependency_order: string[];
}

export type SchemaDefinitionBundleDisposition =
  | "create"
  | "update"
  | "no-op"
  | "conflict"
  | "error";

export type SchemaDefinitionBundleTargetType =
  | "bundle"
  | "database"
  | "profile"
  | "table"
  | "attribute"
  | "layout"
  | "profile_table_placement"
  | "link_type";

export interface SchemaDefinitionBundlePlanAction {
  sequence: number;
  disposition: SchemaDefinitionBundleDisposition;
  target_type: SchemaDefinitionBundleTargetType;
  external_key: string;
  parent_external_key: string | null;
  current: {
    id: string | null;
    revision_id: string | null;
    content_hash: string;
    published: boolean;
  } | null;
  projected: Record<string, unknown> | null;
  reason_codes: string[];
}

export interface SchemaDefinitionBundleDiagnostic {
  severity: "warning" | "error";
  code: string;
  location: string;
  message: string;
  remediation: string;
}

export interface SchemaDefinitionBundlePlan {
  $schema: string;
  contract_version: "1.0.0";
  source_artifact: SchemaDefinitionBundleSourceArtifact;
  bundle: SchemaDefinitionBundleSummary | null;
  catalog_snapshot_fingerprint: string;
  plan_fingerprint: string;
  valid: boolean;
  action_counts: {
    create: number;
    update: number;
    "no-op": number;
    conflict: number;
    error: number;
  };
  actions: SchemaDefinitionBundlePlanAction[];
  diagnostics: SchemaDefinitionBundleDiagnostic[];
  mutations_applied: false;
  delete_missing: false;
  write_set: [];
}

export interface AppliedSchemaDefinitionBundleObject {
  sequence: number;
  disposition: Exclude<SchemaDefinitionBundleDisposition, "conflict" | "error">;
  target_type: Exclude<SchemaDefinitionBundleTargetType, "bundle">;
  external_key: string;
  parent_external_key: string | null;
  aggregate_id: string | null;
  revision_id: string | null;
  content_hash: string;
  published: boolean;
  source_schema_id: string;
  source_schema_version: string;
  source_pointer: string;
}

export interface SchemaDefinitionBundleApplication {
  $schema: string;
  contract_version: "1.0.0";
  application_id: string;
  bundle_id: string;
  bundle_key: string;
  bundle_version: string;
  classification: DataClassification;
  source_artifact: SchemaDefinitionBundleSourceArtifact;
  plan_fingerprint: string;
  before_snapshot_fingerprint: string;
  after_snapshot_fingerprint: string;
  results: AppliedSchemaDefinitionBundleObject[];
  mutations_applied: boolean;
  delete_missing: false;
  applied_at: string;
  applied_by: string;
  idempotency_key: string;
}

export interface SchemaDefinitionBundleExport {
  blob: Blob;
  sha256: string;
  filename: string;
  media_type: string;
  application_id: string;
  source_artifact_id: string;
  source_artifact_sha256: string;
  request_id: string | null;
}
