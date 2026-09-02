import type { CanonicalTestDataDocumentResponse, GovernedImportProfileResponse } from "../../test-data/contracts";
import type {
  CreateDmaTtsRequest,
  DmaTemperatureSweepSnapshot,
  DmaTtsPartition,
  DmaTtsRecommendationRequest,
  DmaTtsRecommendationResponse,
} from "./dma-tts-contracts";

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function finite(value: unknown): number | null {
  const parsed = typeof value === "number" ? value : typeof value === "string" && value.trim() ? Number(value) : NaN;
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizedChannel(document: Record<string, unknown>, quantity: string): number[] | null {
  const channels = Array.isArray(document.channels) ? document.channels : [];
  const channel = channels.map(record).find((item) => item?.quantity_semantics === quantity);
  if (!channel || !Array.isArray(channel.normalized_values)) return null;
  const values = channel.normalized_values.map(finite);
  return values.every((value): value is number => value !== null) ? values : null;
}

export function parseDmaTemperatureSweep(
  document: Record<string, unknown> | null | undefined,
): DmaTemperatureSweepSnapshot | null {
  if (!document) return null;
  const temperature = normalizedChannel(document, "physics.temperature");
  const storage = normalizedChannel(document, "mechanics.modulus.storage");
  const loss = normalizedChannel(document, "mechanics.modulus.loss");
  if (!temperature || !storage || !loss || temperature.length < 2
    || temperature.length !== storage.length || temperature.length !== loss.length) return null;
  const conditions = Array.isArray(document.conditions) ? document.conditions : [];
  const frequency = conditions.map(record).find((item) => item?.quantity_semantics === "frequency.cyclic");
  const frequencyHz = frequency?.normalized_unit === "Hz" ? finite(frequency.normalized_value) : null;
  if (frequencyHz === null || frequencyHz <= 0) return null;
  return {
    frequencyHz,
    rows: temperature.map((temperatureK, ordinal) => ({
      ordinal,
      temperatureK,
      storageModulusPa: storage[ordinal],
      lossModulusPa: loss[ordinal],
    })),
  };
}

export function exactDmaTtsPins(
  testData: CanonicalTestDataDocumentResponse,
  profiles: readonly GovernedImportProfileResponse[],
): DmaTtsRecommendationRequest | null {
  const lineage = testData.governed_source?.tabular_import?.import_profile;
  if (!lineage) return null;
  const profile = profiles.find((item) => item.import_profile_id === lineage.aggregate_id
    && item.current_revision.id === lineage.revision_id);
  if (!profile) return null;
  return {
    test_data: {
      document_id: testData.test_data_document_id,
      revision_id: testData.current_revision.id,
      content_sha256: testData.current_revision.content_hash,
    },
    import_profile: {
      profile_id: profile.import_profile_id,
      revision_id: profile.current_revision.id,
      content_sha256: profile.current_revision.content_hash,
    },
  };
}

export interface DmaTtsDraft {
  referenceTemperatureK: string;
  c1: string;
  c2K: string;
  dispositions: Array<{ partition: DmaTtsPartition; exclusionReason: string }>;
  confirmed: boolean;
  reason: string;
}

export const DMA_TTS_RECOMMENDATION_REASON = "Use the recommended shift settings for this test.";

export function draftFromDmaTtsRecommendation(
  recommendation: DmaTtsRecommendationResponse,
  rowCount: number,
): DmaTtsDraft {
  return {
    referenceTemperatureK: String(recommendation.reference_temperature_k),
    c1: String(recommendation.c1),
    c2K: String(recommendation.c2_k),
    dispositions: Array.from({ length: rowCount }, () => ({ partition: "CALIBRATION", exclusionReason: "" })),
    // Creating the shifted response is the explicit confirmation. Persist
    // that decision without asking the user to confirm the same action twice.
    confirmed: true,
    reason: DMA_TTS_RECOMMENDATION_REASON,
  };
}

export function buildCreateDmaTtsRequest(
  testData: CanonicalTestDataDocumentResponse,
  pins: DmaTtsRecommendationRequest,
  recommendation: DmaTtsRecommendationResponse,
  draft: DmaTtsDraft,
  label: string,
): CreateDmaTtsRequest | null {
  const referenceTemperatureK = finite(draft.referenceTemperatureK);
  const c1 = finite(draft.c1);
  const c2K = finite(draft.c2K);
  const reason = draft.reason.trim();
  if (!dmaTtsDraftReady(draft, label) || referenceTemperatureK === null || c1 === null || c2K === null) return null;
  const recommendationUnchanged = referenceTemperatureK === recommendation.reference_temperature_k
    && c1 === recommendation.c1 && c2K === recommendation.c2_k;
  return {
    classification: testData.current_revision.classification,
    label: label.trim(),
    ...pins,
    dispositions: draft.dispositions.map((item, source_ordinal) => ({
      source_ordinal,
      partition: item.partition,
      exclusion_reason: item.partition === "EXCLUDED" ? item.exclusionReason.trim() : null,
    })),
    shift_law: {
      kind: "wlf",
      reference_temperature_k: referenceTemperatureK,
      c1,
      c2_k: c2K,
      value_origin: recommendationUnchanged ? "generic_wlf_at_tg_starting_suggestion" : "engineer_edited",
    },
    confirmation: { confirmed: true, reason },
    recommendation_sha256: recommendationUnchanged ? recommendation.recommendation_sha256 : null,
    change_reason: reason,
  };
}

export function dmaTtsDraftReady(draft: DmaTtsDraft, label: string): boolean {
  const referenceTemperatureK = finite(draft.referenceTemperatureK);
  const c1 = finite(draft.c1);
  const c2K = finite(draft.c2K);
  const included = draft.dispositions.filter((item) => item.partition !== "EXCLUDED").length;
  const exclusionsComplete = draft.dispositions.every((item) => item.partition !== "EXCLUDED" || item.exclusionReason.trim());
  return draft.confirmed && Boolean(draft.reason.trim()) && Boolean(label.trim())
    && referenceTemperatureK !== null && referenceTemperatureK > 0
    && c1 !== null && c1 > 0 && c2K !== null && c2K > 0
    && included >= 2 && exclusionsComplete;
}
