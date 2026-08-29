import { describe, expect, it } from "vitest";

import type {
  CommonProcessingBatchResponse as RootCommonProcessingBatchResponse,
  CommonExportProvenance as RootCommonExportProvenance,
  CommonExactRevisionPin as RootCommonExactRevisionPin,
  ExportTarget as RootExportTarget,
  MappingItem as RootMappingItem,
  MappingReport as RootMappingReport,
  MappingStatus as RootMappingStatus,
  TargetDeliveryLinks as RootTargetDeliveryLinks,
  TargetDeliveryResponse as RootTargetDeliveryResponse,
  TargetPreviewResponse as RootTargetPreviewResponse,
} from "../contracts";
import type {
  CommonProcessingBatchResponse,
  CommonProcessingFitDecision,
  CommonProcessingOutputResponse,
  CommonProcessingPreview,
} from "./common-processing-contracts";
import type { CommonExportProvenance, CommonExactRevisionPin } from "./exact-revision-contracts";
import type {
  ExportTarget,
  MappingItem,
  MappingReport,
  MappingStatus,
  TargetDeliveryLinks,
  TargetDeliveryResponse,
  TargetPreviewResponse,
} from "./export-contracts";

type Equal<Left, Right> =
  (<Value>() => Value extends Left ? 1 : 2) extends
  (<Value>() => Value extends Right ? 1 : 2)
    ? (<Value>() => Value extends Right ? 1 : 2) extends
      (<Value>() => Value extends Left ? 1 : 2)
      ? true
      : false
    : false;
type Expect<Value extends true> = Value;

type CompatibilityContracts = [
  Expect<Equal<RootCommonProcessingBatchResponse, CommonProcessingBatchResponse>>,
  Expect<Equal<RootCommonExactRevisionPin, CommonExactRevisionPin>>,
  Expect<Equal<RootCommonExportProvenance, CommonExportProvenance>>,
  Expect<Equal<RootExportTarget, ExportTarget>>,
  Expect<Equal<RootMappingStatus, MappingStatus>>,
  Expect<Equal<RootMappingItem, MappingItem>>,
  Expect<Equal<RootMappingReport, MappingReport>>,
  Expect<Equal<RootTargetPreviewResponse, TargetPreviewResponse>>,
  Expect<Equal<RootTargetDeliveryResponse, TargetDeliveryResponse>>,
  Expect<Equal<RootTargetDeliveryLinks, TargetDeliveryLinks>>,
];

const compatibilityContracts: CompatibilityContracts = [
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
];

describe("Modeling type ownership contract", () => {
  it("keeps exact-revision, Fit decision, Processing output, and Export discriminants unchanged", () => {
    const fitDecision = {
      candidate_key: "voce",
      mode: "single",
      primary_law: "voce",
      secondary_law: null,
      primary_weight: null,
      parameter_sets: [{ law: "voce", parameters: [{ name: "sigma_0", value: 300e6, unit: "Pa", lower: 0, upper: null }] }],
      fit_minimum: 0,
      fit_maximum: 0.4,
      extrapolation_maximum: 0.6,
      extrapolation_policy: "bounded",
      metric_definition: "relative_rmse",
      metric_value: 0.01,
      requested_term_policy: null,
      actual_term_count: null,
      selection_reason: "Selected exact Fit",
      warning_acknowledged: true,
    } satisfies CommonProcessingFitDecision;
    const preview = {
      execution_mode: "preview",
      promotable: false,
      source_document_sha256: "a".repeat(64),
      mapping_profile_sha256: "b".repeat(64),
      independent_quantity: "strain.true_plastic",
      stages: [],
    } satisfies CommonProcessingPreview;
    const outputPins: Pick<CommonProcessingOutputResponse, "source_document" | "mapping_profile" | "source_processing_output" | "fit_decision"> = {
      source_document: { aggregate_id: "data", revision_id: "data-r3" },
      mapping_profile: { aggregate_id: "mapping", revision_id: "mapping-r2" },
      source_processing_output: { aggregate_id: "process", revision_id: "process-r4" },
      fit_decision: fitDecision,
    };
    const statuses: MappingStatus[] = [
      "exact",
      "transformed",
      "approximated",
      "ignored",
      "unsupported",
      "not_applicable",
    ];

    expect(compatibilityContracts).toEqual(Array(10).fill(true));
    expect(preview).toMatchObject({ execution_mode: "preview", promotable: false });
    expect(outputPins).toEqual({
      source_document: { aggregate_id: "data", revision_id: "data-r3" },
      mapping_profile: { aggregate_id: "mapping", revision_id: "mapping-r2" },
      source_processing_output: { aggregate_id: "process", revision_id: "process-r4" },
      fit_decision: fitDecision,
    });
    expect(statuses).toEqual([
      "exact",
      "transformed",
      "approximated",
      "ignored",
      "unsupported",
      "not_applicable",
    ]);
  });
});
