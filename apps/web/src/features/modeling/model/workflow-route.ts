import type { CanonicalTestDataDocumentResponse } from "../../test-data/contracts";
import {
  documentIsPolymerDmaTemperatureSweep,
  documentMatchesTrack,
  type ModelingTrack,
} from "./processing-registry";
import type { ModelingStage } from "./session-controller";

export function modelingDataNextTask(
  track: ModelingTrack,
  item: CanonicalTestDataDocumentResponse | undefined,
): "fit" | "process" {
  if (track === "polymer" && item && documentMatchesTrack(item, "polymer")) {
    return documentIsPolymerDmaTemperatureSweep(item) ? "process" : "fit";
  }
  return "process";
}

export function modelingWorkflowPath(
  locationSearch: string,
  stage: ModelingStage,
  track: ModelingTrack,
): string {
  const params = new URLSearchParams(locationSearch);
  params.set("stage", stage);
  params.set("family", track);
  return `/modeling?${params.toString()}`;
}
