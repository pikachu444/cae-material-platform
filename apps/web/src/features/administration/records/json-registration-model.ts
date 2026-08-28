import type { ApiResult } from "../../../shared/api/http";

export type JsonDataClassification =
  | "internal"
  | "confidential"
  | "restricted"
  | "export_controlled";

export interface JsonRegistrationFormatArtifactPin {
  artifact_id: string;
  file: string;
  pointer: string;
  sha256: string;
}

export interface JsonRegistrationFormatTablePin {
  id: string;
  revision_id: string;
  key: string;
  source_file: string;
  source_pointer: string;
  source_sha256: string;
}

export interface JsonRegistrationAttributeBinding {
  pointer: string;
  attribute_id: string;
  attribute_revision_id: string;
  attribute_key: string;
  data_type:
    | "number"
    | "integer"
    | "text"
    | "boolean"
    | "date"
    | "discrete"
    | "curve"
    | "record_reference";
  source_unit?: string | null;
  quantity_semantics?: string | null;
  curve?: Record<string, unknown> | null;
  section: string;
}

export interface JsonRegistrationFormat {
  format_id: string;
  format_revision_id: string;
  format_key: string;
  application_id: string;
  application_revision_id: string;
  application_source: JsonRegistrationFormatArtifactPin;
  schema: JsonRegistrationFormatArtifactPin;
  table: JsonRegistrationFormatTablePin;
  wrapper: string;
  attribute_bindings: JsonRegistrationAttributeBinding[];
  link_type_revision_ids: string[];
  unit_profile_revision_ids: string[];
}

export interface JsonRegistrationReferencePin {
  file: string;
  pointer: string;
  identifier: string;
  record_id: string;
  revision_id: string;
  content_hash: string;
}

export interface JsonRegistrationDiagnostic {
  filename: string;
  code: string;
  message: string;
  recovery: string;
  json_pointer?: string;
  line?: number | null;
  column?: number | null;
  byte_offset?: number | null;
  severity: "warning" | "error";
}

export interface JsonRegistrationPreviewField {
  section: string;
  label: string;
  pointer: string;
  kind: string;
  value?: string | null;
  unit?: string | null;
  summary?: string | null;
}

export interface JsonRegistrationDomainBindingPin {
  file: string;
  component: string;
  kind: string;
  object_id: string;
  revision_id: string;
}

export interface JsonRegistrationFileResult {
  filename: string;
  sha256: string;
  size_bytes: number;
  valid: boolean;
  warnings: JsonRegistrationDiagnostic[];
  errors: JsonRegistrationDiagnostic[];
  external_key?: string | null;
  record_id?: string | null;
  record_revision_id?: string | null;
  lifecycle?: string | null;
  fields: JsonRegistrationPreviewField[];
  record_name?: string | null;
}

export interface JsonRegistrationPreviewResponse {
  $schema: string;
  contract_version: "1.0.0";
  preview_token: string;
  expires_at: string;
  package: {
    media_type: "application/zip" | "application/json";
    sha256: string;
    artifact_id?: string | null;
  };
  format_revision_id: string | null;
  detected_record_type: string | null;
  format: JsonRegistrationFormat | null;
  valid: boolean;
  files: JsonRegistrationFileResult[];
}

export interface JsonRegistrationSaveRecord {
  record_id: string;
  record_revision_id: string;
  revision_no: number;
  external_key: string | null;
}

export interface JsonRegistrationSaveResponse {
  batch_id: string;
  replayed: boolean;
  package_sha256: string;
  lifecycle: "DRAFT";
  records: JsonRegistrationSaveRecord[];
  publication: { state: "DRAFT"; allowed: false };
}

export interface JsonRegistrationArtifact {
  filename: string;
  artifact_id: string;
  sha256: string;
  media_type: "application/json" | "application/zip";
  size_bytes: number;
}

export interface JsonRegistrationFormatsResponse {
  items: JsonRegistrationFormat[];
}

const detectedContentLabels: Record<string, string> = {
  dma: "DMA",
  dma_test: "DMA test",
  elastoplasticity: "Elastoplasticity",
  fld: "Forming-limit test",
  fld_test: "Forming-limit test",
  simulation_data: "Simulation data",
  statistics: "Statistics",
  technical_data: "Technical data",
  tensile: "Tensile test",
  tensile_test: "Tensile test",
  test_data: "Test data",
};

/** Presentation-only label for the server's authoritative detected record type. */
export function detectedContentLabel(recordType: string | null): string | null {
  const normalized = recordType?.trim();
  if (!normalized) return null;
  const known = detectedContentLabels[normalized.toLowerCase()];
  if (known) return known;
  return normalized
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export type JsonRegistrationPreviewResult = ApiResult<JsonRegistrationPreviewResponse>;
export type JsonRegistrationSaveResult = ApiResult<JsonRegistrationSaveResponse>;
