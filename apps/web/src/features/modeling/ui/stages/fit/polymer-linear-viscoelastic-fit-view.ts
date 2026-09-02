import { formatPolymerRangeCoordinate } from "./polymer-linear-viscoelastic-format";
import type { PolymerInputReviewItem } from "./polymer-linear-viscoelastic-input-review";
import type { PolymerObservedSeries } from "./polymer-linear-viscoelastic-presentation";
import type {
  LinearViscoelasticCatalogContext,
  LinearViscoelasticPlanContextRequest,
} from "../../../model/linear-viscoelastic-calibration-contracts";

export function buildPolymerApprovedSetupContext(input: {
  catalog?: LinearViscoelasticCatalogContext;
  testData?: { id: string; revisionId: string };
  directMode: "relaxation" | "dma" | "unknown";
  sourceChoice: "test-data" | "processing-output";
  processingOutput?: { id: string; revisionId: string };
}): LinearViscoelasticPlanContextRequest | null {
  if (!input.catalog || !input.testData) return null;

  let inputMode: LinearViscoelasticPlanContextRequest["input_mode"];
  if (input.sourceChoice === "processing-output") {
    if (!input.processingOutput) return null;
    inputMode = "dma_frequency_master_curve";
  } else {
    if (input.directMode === "unknown") return null;
    inputMode = input.directMode;
  }

  return {
    material: { id: input.catalog.material.id, revision_id: input.catalog.material.revisionId },
    material_state: { id: input.catalog.materialState.id, revision_id: input.catalog.materialState.revisionId },
    test_data: { id: input.testData.id, revision_id: input.testData.revisionId },
    ...(input.sourceChoice === "processing-output" ? {
      processing_output: { id: input.processingOutput!.id, revision_id: input.processingOutput!.revisionId },
    } : {}),
    input_mode: inputMode,
  };
}

export type PolymerSetupSurfaceStatus = "approved" | "loading" | "missing" | "multiple" | "inactive" | "review" | "error";

export function presentPolymerApprovedSetup(input: {
  resolverStatus: "unavailable" | "loading" | "missing" | "multiple" | "ready" | "error";
  reviewStatus: "idle" | "submitting" | "pending" | "error";
}): { status: PolymerSetupSurfaceStatus } {
  const status = input.resolverStatus === "ready" ? "approved"
    : input.resolverStatus === "loading" ? "loading"
      : input.resolverStatus === "multiple" ? "multiple"
        : input.resolverStatus === "error" ? "error"
          : input.resolverStatus === "unavailable" ? "inactive"
            : input.reviewStatus === "pending" || input.reviewStatus === "submitting" ? "review"
              : input.reviewStatus === "error" ? "error"
                : "missing";
  return { status };
}

export interface PolymerMeasuredRange {
  quantity: string;
  from: string;
  to: string;
  unit: string;
}

export function formatPolymerApplicationRange(series: PolymerObservedSeries[]): PolymerMeasuredRange | null {
  const firstSeries = series[0];
  const coordinates = firstSeries?.points
    .filter((point) => point.partition === "CALIBRATION" || point.partition === "HOLDOUT")
    .map((point) => point.x)
    .filter(Number.isFinite) ?? [];
  if (!firstSeries || !coordinates.length) return null;
  return {
    quantity: firstSeries.xLabel,
    from: formatPolymerRangeCoordinate(Math.min(...coordinates)),
    to: formatPolymerRangeCoordinate(Math.max(...coordinates)),
    unit: firstSeries.xUnit,
  };
}

export function buildPolymerFitInputReviewItems(input: {
  modeLabel: string;
  sourceLabel: string;
  measurementPointCount: number;
  calculationPointCount: number;
  calculationValueCount: number;
  verificationPointCount: number;
  excludedPointCount: number;
  dualResponse: boolean;
  temperature?: { label: "Temperature" | "Reference temperature"; value: number | string };
}): PolymerInputReviewItem[] {
  const items: PolymerInputReviewItem[] = [
    { label: "Input", value: input.modeLabel },
    { label: "Source", value: input.sourceLabel },
    { label: "Measurement points", value: String(input.measurementPointCount) },
    {
      label: "Used to fit",
      value: input.dualResponse
        ? `${input.calculationPointCount} points · ${input.calculationValueCount} response values`
        : `${input.calculationPointCount} points`,
    },
    { label: "Used to verify", value: `${input.verificationPointCount} points` },
    { label: "Not used", value: `${input.excludedPointCount} points` },
  ];
  if (input.temperature) {
    items.push({ label: input.temperature.label, value: `${input.temperature.value} K` });
  }
  return items;
}
