import type { ApiConfig } from "../../../shared/api";
import { listCommonProcessingOutputs } from "../api/modeling-api";
import type { CreateDmaTtsResponse } from "../model/dma-tts-contracts";
import type { CommonProcessingOutputResponse } from "../model/common-processing-contracts";
import type { ModelingSessionRecordRef } from "../model/session-controller";

function matchesDmaTtsSource(
  output: CommonProcessingOutputResponse | undefined,
  source: Pick<ModelingSessionRecordRef, "id" | "revisionId">,
): output is CommonProcessingOutputResponse {
  return Boolean(output
    && output.source_document.aggregate_id === source.id
    && output.source_document.revision_id === source.revisionId
    && output.steps.some((step) => step.method_id === "polymer.dma_frequency_master_curve"));
}

export function findExactDmaTtsOutput(
  outputs: CommonProcessingOutputResponse[],
  source: Pick<ModelingSessionRecordRef, "id" | "revisionId"> | undefined,
  localRef: Pick<ModelingSessionRecordRef, "id" | "revisionId"> | undefined,
  sessionOutput: CommonProcessingOutputResponse | undefined,
): CommonProcessingOutputResponse | undefined {
  if (!source) return undefined;
  const local = localRef
    ? outputs.find((output) => output.processing_output_id === localRef.id
      && output.current_revision.id === localRef.revisionId)
    : undefined;
  return [local, sessionOutput].find((output) => matchesDmaTtsSource(output, source));
}

export async function readBackDmaTtsOutput(
  config: ApiConfig,
  created: CreateDmaTtsResponse,
  source: Pick<ModelingSessionRecordRef, "id" | "revisionId">,
): Promise<{ outputs: CommonProcessingOutputResponse[]; output: CommonProcessingOutputResponse }> {
  const refreshed = await listCommonProcessingOutputs(config);
  const output = refreshed.data.items.find((candidate) =>
    candidate.processing_output_id === created.master_curve_output.output_id
    && candidate.current_revision.id === created.master_curve_output.revision_id
    && candidate.current_revision.content_hash === created.master_curve_output.content_sha256);
  if (!matchesDmaTtsSource(output, source)) {
    throw new Error("The newly saved DMA response did not read back with its exact source.");
  }
  return { outputs: refreshed.data.items, output };
}
