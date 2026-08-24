import type { ApiConfig } from "../../../shared/api/http";
import {
  downloadCommonProcessingOutput,
  listCommonProcessingOutputs,
  type CommonProcessingFitDecision,
  type CommonProcessingOutputResponse,
  type CommonCurveStage,
  type CommonProcessingStep,
  type CommonProcessingWorkupOverride,
} from "../../modeling";

interface ExactRevisionPin {
  aggregate_id: string;
  revision_id: string;
}

export interface ExactProcessingOutputDocument {
  document_type: "cmp.processing-output";
  document_version: string;
  output_id: string;
  source_document: ExactRevisionPin;
  source_canonical_artifact_sha256: string;
  mapping_profile: ExactRevisionPin;
  source_processing_output: ExactRevisionPin | null;
  source_processing_output_sha256: string | null;
  steps: CommonProcessingStep[];
  workup_overrides: CommonProcessingWorkupOverride[];
  fit_decision: CommonProcessingFitDecision | null;
  result: {
    source_document_sha256: string;
    mapping_profile_sha256: string;
    independent_quantity: string;
    stages: CommonCurveStage[];
  };
}

export interface ExactProcessingOutput {
  summary: CommonProcessingOutputResponse;
  document: ExactProcessingOutputDocument;
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function string(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function exactPin(value: unknown): value is ExactRevisionPin {
  const candidate = record(value);
  return Boolean(
    candidate
      && string(candidate.aggregate_id)
      && string(candidate.revision_id),
  );
}

function validSeries(value: unknown): boolean {
  const candidate = record(value);
  return Boolean(
    candidate
      && string(candidate.quantity)
      && typeof candidate.unit === "string"
      && Array.isArray(candidate.values)
      && candidate.values.length > 0
      && candidate.values.every(
        (item) => typeof item === "number" && Number.isFinite(item),
      ),
  );
}

function validStage(value: unknown): boolean {
  const candidate = record(value);
  return Boolean(
    candidate
      && typeof candidate.ordinal === "number"
      && string(candidate.method_id)
      && string(candidate.method_version)
      && typeof candidate.point_count === "number"
      && Array.isArray(candidate.series)
      && candidate.series.every(validSeries)
      && Array.isArray(candidate.scalar_results)
      && Array.isArray(candidate.diagnostics),
  );
}

function parseDocument(value: unknown): ExactProcessingOutputDocument {
  const candidate = record(value);
  const result = record(candidate?.result);
  if (
    !candidate
    || candidate.document_type !== "cmp.processing-output"
    || !string(candidate.document_version)
    || !string(candidate.output_id)
    || !exactPin(candidate.source_document)
    || !string(candidate.source_canonical_artifact_sha256)
    || !exactPin(candidate.mapping_profile)
    || !Array.isArray(candidate.steps)
    || !Array.isArray(candidate.workup_overrides)
    || !result
    || !string(result.source_document_sha256)
    || !string(result.mapping_profile_sha256)
    || !string(result.independent_quantity)
    || !Array.isArray(result.stages)
    || result.stages.length === 0
    || !result.stages.every(validStage)
  ) {
    throw new Error("The exact Processing Output artifact does not match the supported contract.");
  }
  return candidate as unknown as ExactProcessingOutputDocument;
}

async function sha256(bytes: ArrayBuffer): Promise<string> {
  if (!globalThis.crypto?.subtle) {
    throw new Error("This browser cannot verify the exact Processing Output artifact.");
  }
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((item) => item.toString(16).padStart(2, "0"))
    .join("");
}

function normalizedDigest(value: string): string {
  return value.toLowerCase().replace(/^sha256:/, "");
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  const candidate = record(value);
  if (candidate) {
    return `{${Object.keys(candidate).sort().map(
      (key) => `${JSON.stringify(key)}:${stableJson(candidate[key])}`,
    ).join(",")}}`;
  }
  return JSON.stringify(value) ?? "undefined";
}

export async function loadExactProcessingOutput(
  config: ApiConfig,
  outputId: string,
  revisionId: string,
): Promise<ExactProcessingOutput> {
  const listed = await listCommonProcessingOutputs(config);
  const summary = listed.data.items.find(
    (item) => item.processing_output_id === outputId,
  );
  if (!summary) {
    throw new Error("The linked Processing Output is not available in this project.");
  }
  if (summary.current_revision.id !== revisionId) {
    throw new Error("The linked exact Processing Output revision is not available for read-back.");
  }

  const artifact = await downloadCommonProcessingOutput(config, outputId);
  const bytes = await artifact.data.blob.arrayBuffer();
  const digest = await sha256(bytes);
  if (normalizedDigest(summary.output_sha256) !== digest) {
    throw new Error("The Processing Output artifact digest does not match its exact revision.");
  }
  const document = parseDocument(
    JSON.parse(new TextDecoder().decode(bytes)) as unknown,
  );
  if (
    document.output_id !== outputId
    || document.source_document.aggregate_id !== summary.source_document.aggregate_id
    || document.source_document.revision_id !== summary.source_document.revision_id
    || document.mapping_profile.aggregate_id !== summary.mapping_profile.aggregate_id
    || document.mapping_profile.revision_id !== summary.mapping_profile.revision_id
    || document.source_canonical_artifact_sha256 !== summary.source_canonical_artifact_sha256
    || stableJson(document.steps) !== stableJson(summary.steps)
    || stableJson(document.fit_decision) !== stableJson(summary.fit_decision)
    || document.result.source_document_sha256 !== summary.source_document_sha256
    || document.result.mapping_profile_sha256 !== summary.mapping_profile_sha256
    || document.result.independent_quantity !== summary.independent_quantity
    || document.result.stages.length !== summary.stage_count
    || document.result.stages[document.result.stages.length - 1]?.point_count !== summary.final_point_count
  ) {
    throw new Error("The Processing Output artifact does not match its bound record.");
  }

  // The content endpoint exposes the current immutable revision. Re-read the
  // scoped summary after the byte read so an intervening revision cannot be
  // presented as the exact Catalog binding.
  const readBack = await listCommonProcessingOutputs(config);
  const readBackSummary = readBack.data.items.find(
    (item) => item.processing_output_id === outputId,
  );
  if (
    readBackSummary?.current_revision.id !== revisionId
    || normalizedDigest(readBackSummary.output_sha256) !== digest
  ) {
    throw new Error("The Processing Output changed during exact revision read-back.");
  }

  return { summary: readBackSummary, document };
}
