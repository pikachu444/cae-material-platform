export interface ExportTarget {
  solver: string;
  version: string;
  unit_system: string;
}

/** Bounded metal elastoplastic capability declaration used to populate Export controls. */
export interface ElastoplasticExportCapabilities {
  model_family_id: string;
  model_schema_version: string;
  model_schema_digest: string;
  exporters: Array<{
    exporter_id: string;
    exporter_version: string;
    exporter_digest: string;
    solver: string;
    version: string;
    unit_system: string;
    keywords: string[];
  }>;
  mapping_statuses: readonly MappingStatus[];
  non_production: true;
}

/** UXC-06C1 ephemeral output; it is never an immutable Solver Card. */
export interface TargetPreviewResponse {
  preview_identity: string;
  filename: string;
  native_text: string;
  native_sha256: string;
  mapping_report_sha256: string;
  mapping: { items: MappingItem[]; [key: string]: unknown };
  source: {
    processing_output_id: string;
    processing_output_revision_id: string;
    processing_output_sha256: string;
    material_id: string;
    material_revision_id: string;
    material_state_id: string;
    material_state_revision_id: string;
    material_model_ir_revision_id: string;
    neutral_material_id: string;
    neutral_material_revision_id: string;
  };
  target: ExportTarget & { solver_material_id: number; material_name: string };
  acknowledgement_identity: string | null;
  non_production: true;
  delivery_status: "preview_only";
}

/** UXC-06C2 immutable card plus transactional outbox receipt. */
export interface TargetDeliveryResponse {
  delivery_status: "delivered";
  receipt_id: string;
  delivery_identity: string;
  solver_card_id: string;
  solver_card_revision_id: string;
  filename: string;
  native_sha256: string;
  mapping_report_sha256: string;
  mapping_statuses: string[];
  source: TargetPreviewResponse["source"];
  target: TargetPreviewResponse["target"];
  occurred_at: string;
  recorded_by: string;
  /** The API contract is a closed, typed resource-link set. */
  links: TargetDeliveryLinks;
}

export interface TargetDeliveryLinks {
  solver_card: string;
  preview: string;
  download: string;
  receipt: string;
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
