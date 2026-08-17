/**
 * Type-only public compatibility surface for root DTO consumers. Keeping this
 * entry free of runtime exports preserves the existing dependency boundary.
 */
export type {
  CommonExactRevisionPin,
  CommonExportProvenance,
} from "./model/exact-revision-contracts";
export type {
  ElastoplasticExportCapabilities,
  ExportTarget,
  MappingItem,
  MappingReport,
  MappingStatus,
  TargetDeliveryLinks,
  TargetDeliveryResponse,
  TargetPreviewResponse,
} from "./model/export-contracts";
