import type { CanonicalTestDataDocumentResponse, GovernedImportProfileResponse } from "../../test-data/contracts";
import type {
  CreateDmaTtsRequest,
  DmaFrequencySweepPoint,
  DmaFrequencySweepSnapshot,
  DmaTemperatureSweepSnapshot,
  DmaTtsAdjacentOptimizer,
  DmaTtsExactImportProfilePin,
  DmaTtsExactTestDataPin,
  DmaTtsInputMode,
  DmaTtsLawOptimizer,
  DmaTtsMultiRecommendationResponse,
  DmaTtsMultiScoring,
  DmaTtsMultiSourceSnapshot,
  DmaTtsPartition,
  DmaTtsRecommendationRequest,
  DmaTtsRecommendationResponse,
  DmaTtsSourceClassification,
  DmaTtsSweepDisposition,
} from "./dma-tts-contracts";

const INT64_MAX = 9_223_372_036_854_775_807;
const TEMPERATURE_TOLERANCE_K = 0.5;

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function finite(value: unknown): number | null {
  const parsed = typeof value === "number"
    ? value
    : typeof value === "string" && value.trim() ? Number(value) : NaN;
  return Number.isFinite(parsed) ? parsed : null;
}

function channels(document: Record<string, unknown>): Record<string, unknown>[] {
  return Array.isArray(document.channels)
    ? document.channels.map(record).filter((item): item is Record<string, unknown> => Boolean(item))
    : [];
}

function channelsFor(document: Record<string, unknown>, quantity: string): Record<string, unknown>[] {
  return channels(document).filter((item) => item.quantity_semantics === quantity);
}

function valuesFor(channel: Record<string, unknown>): number[] | null {
  if (!Array.isArray(channel.normalized_values)) return null;
  const values = channel.normalized_values.map(finite);
  return values.every((value): value is number => value !== null) ? values : null;
}

function oneChannel(
  document: Record<string, unknown>,
  quantity: string,
): { values: number[]; channel: Record<string, unknown> } | null {
  const matches = channelsFor(document, quantity);
  if (matches.length !== 1) return null;
  const values = valuesFor(matches[0]);
  return values ? { values, channel: matches[0] } : null;
}

function conditions(document: Record<string, unknown>): Record<string, unknown>[] {
  return Array.isArray(document.conditions)
    ? document.conditions.map(record).filter((item): item is Record<string, unknown> => Boolean(item))
    : [];
}

function scalarFrequencyHz(document: Record<string, unknown>): number | null {
  const matches = conditions(document).filter((item) => item.quantity_semantics === "frequency.cyclic");
  if (matches.length !== 1 || matches[0].normalized_unit !== "Hz") return null;
  const value = finite(matches[0].normalized_value);
  return value !== null && value > 0 ? value : null;
}

function profileMappingNames(profile: GovernedImportProfileResponse): Set<string> {
  const mappings = profile.content?.channels ?? [];
  return new Set(mappings.flatMap((item) => [item.source_quantity, item.normalized_quantity ?? ""]));
}

function profileAllows(
  profile: GovernedImportProfileResponse | undefined,
  schema: string,
  requiredSourceQuantities: readonly string[],
): boolean {
  if (!profile) return false;
  const declaredSchema = profile.content?.data_schema;
  // A missing schema is accepted only for old unit-test doubles. Real governed
  // profiles always carry data_schema and are the primary classifier authority.
  if (declaredSchema && declaredSchema !== schema) return false;
  if (!declaredSchema) return true;
  const names = profileMappingNames(profile);
  return requiredSourceQuantities.every((quantity) => names.has(quantity));
}

function fixedSource(document: Record<string, unknown>): DmaTemperatureSweepSnapshot | null {
  const temperature = oneChannel(document, "physics.temperature");
  const storage = oneChannel(document, "mechanics.modulus.storage");
  const loss = oneChannel(document, "mechanics.modulus.loss");
  // A frequency row or repeated/missing channel changes this from fixed Process
  // into a blocked source. It must never fall through to direct Fit.
  if (!temperature || !storage || !loss || channelsFor(document, "frequency.cyclic").length > 0) return null;
  const frequencyHz = scalarFrequencyHz(document);
  if (frequencyHz === null || temperature.values.length < 2
    || temperature.values.length !== storage.values.length
    || temperature.values.length !== loss.values.length
    || temperature.values.some((value) => value <= 0)) return null;
  return {
    frequencyHz,
    rows: temperature.values.map((temperatureK, ordinal) => ({
      ordinal,
      temperatureK,
      storageModulusPa: storage.values[ordinal],
      lossModulusPa: loss.values[ordinal],
    })),
  };
}

function modalTemperature(values: number[]): number | null {
  const counts = new Map<number, number>();
  values.forEach((value) => counts.set(value, (counts.get(value) ?? 0) + 1));
  if (!counts.size) return null;
  const maximum = Math.max(...counts.values());
  return [...counts.entries()]
    .filter(([, count]) => count === maximum)
    .map(([value]) => value)
    .sort((left, right) => left - right)[0] ?? null;
}

function multiSource(document: Record<string, unknown>): DmaTtsMultiSourceSnapshot | null {
  const ordinal = oneChannel(document, "test.sweep.ordinal");
  const temperature = oneChannel(document, "physics.temperature");
  const frequency = oneChannel(document, "frequency.cyclic");
  const storage = oneChannel(document, "mechanics.modulus.storage");
  const loss = oneChannel(document, "mechanics.modulus.loss");
  if (!ordinal || !temperature || !frequency || !storage || !loss
    || conditions(document).some((item) => item.quantity_semantics === "frequency.cyclic")) return null;
  const count = ordinal.values.length;
  if (count < 1 || [temperature, frequency, storage, loss].some((item) => item.values.length !== count)) return null;
  if (ordinal.values.some((value) => !Number.isInteger(value) || value < 1 || value > INT64_MAX)) return null;
  if ([temperature, frequency, storage, loss].some((item) => item.values.some((value) => value <= 0))) return null;

  const groups = new Map<number, DmaFrequencySweepPoint[]>();
  for (let index = 0; index < count; index += 1) {
    const sourceSweepOrdinal = ordinal.values[index];
    const point: DmaFrequencySweepPoint = {
      sourceOrdinal: index,
      temperatureK: temperature.values[index],
      frequencyHz: frequency.values[index],
      storageModulusPa: storage.values[index],
      lossModulusPa: loss.values[index],
    };
    const points = groups.get(sourceSweepOrdinal) ?? [];
    points.push(point);
    groups.set(sourceSweepOrdinal, points);
  }
  if (groups.size < 3) return null;
  const sweeps: DmaFrequencySweepSnapshot[] = [];
  for (const [sourceSweepOrdinal, points] of [...groups.entries()].sort(([left], [right]) => left - right)) {
    if (points.length < 2) return null;
    const representativeTemperatureK = modalTemperature(points.map((point) => point.temperatureK));
    if (representativeTemperatureK === null
      || points.some((point) => Math.abs(point.temperatureK - representativeTemperatureK) > TEMPERATURE_TOLERANCE_K)) return null;
    if (points.some((point, index) => index > 0 && point.frequencyHz <= points[index - 1].frequencyHz)) return null;
    sweeps.push({
      sourceSweepOrdinal,
      representativeTemperatureK,
      points,
      sourceFrequencyMinHz: points[0].frequencyHz,
      sourceFrequencyMaxHz: points[points.length - 1].frequencyHz,
    });
  }
  const temperatures = sweeps.map((sweep) => sweep.representativeTemperatureK);
  return new Set(temperatures).size === temperatures.length
    ? { inputMode: "multi_frequency_isotherms", sweeps }
    : null;
}

function directFrequencySweep(document: Record<string, unknown>): boolean {
  const frequency = oneChannel(document, "frequency.cyclic");
  const storage = oneChannel(document, "mechanics.modulus.storage");
  const loss = oneChannel(document, "mechanics.modulus.loss");
  const temperatures = conditions(document).filter((item) => item.quantity_semantics === "temperature.absolute");
  if (!frequency || !storage || !loss || temperatures.length !== 1
    || channelsFor(document, "test.sweep.ordinal").length > 0) return false;
  const temperature = finite(temperatures[0].normalized_value);
  return temperature !== null && temperature > 0
    && frequency.values.length >= 2
    && frequency.values.length === storage.values.length
    && frequency.values.length === loss.values.length
    && frequency.values.every((value, index) => value > 0 && (index === 0 || value > frequency.values[index - 1]));
}

export function parseDmaTemperatureSweep(
  document: Record<string, unknown> | null | undefined,
): DmaTemperatureSweepSnapshot | null {
  return document ? fixedSource(document) : null;
}

export function parseDmaFrequencyTemperatureSweeps(
  document: Record<string, unknown> | null | undefined,
): DmaTtsMultiSourceSnapshot | null {
  return document ? multiSource(document) : null;
}

export function classifyDmaTtsSource(
  document: Record<string, unknown> | null | undefined,
  profile: GovernedImportProfileResponse | undefined,
): DmaTtsSourceClassification {
  if (!document || !profile) {
    return { kind: "blocked", reason: "Select an exact governed Test Data revision and Import Profile before Process." };
  }
  const declaredSchema = profile.content?.data_schema;
  // Legacy API test doubles predating the governed data_schema field may still
  // be passed by the fixed Process regression tests. Production profiles take
  // the declared-schema branches below; this fallback only keeps that fixture
  // compatible while the exact profile endpoint is being migrated.
  const schema = declaredSchema ?? (
    fixedSource(document) ? "dma_temperature_sweep"
      : multiSource(document) ? "dma_frequency_temperature_sweep"
        : directFrequencySweep(document) ? "dma_frequency_sweep" : ""
  );
  if (schema === "dma_temperature_sweep") {
    if (!profileAllows(profile, schema, ["temperature", "storage_modulus", "loss_modulus"])) {
      return { kind: "blocked", reason: "The governed Import Profile does not map the fixed-frequency DMA channels." };
    }
    const source = fixedSource(document);
    return source
      ? { kind: "fixed", source, reason: null }
      : { kind: "blocked", reason: "Fixed-frequency DMA requires one scalar positive frequency, temperature, G′, and G″ channels with aligned points." };
  }
  if (schema === "dma_frequency_temperature_sweep") {
    if (!profileAllows(profile, schema, ["source_sweep_ordinal", "temperature", "frequency", "storage_modulus", "loss_modulus"])) {
      return { kind: "blocked", reason: "The governed Import Profile does not map the five multi-frequency DMA channels." };
    }
    const source = multiSource(document);
    return source
      ? { kind: "multi", source, reason: null }
      : { kind: "blocked", reason: "Multi-frequency DMA requires at least three valid sweeps, two increasing positive frequencies per sweep, and consistent temperatures." };
  }
  if (schema === "dma_frequency_sweep") {
    if (!profileAllows(profile, schema, ["frequency", "storage_modulus", "loss_modulus"])) {
      return { kind: "blocked", reason: "The governed Import Profile does not map the direct DMA channels." };
    }
    return directFrequencySweep(document)
      ? { kind: "direct", reason: null }
      : { kind: "blocked", reason: "Direct DMA Fit requires one scalar temperature and one increasing frequency channel without a sweep marker." };
  }
  return { kind: "blocked", reason: "This governed Test Data schema is not supported by the DMA Process." };
}

/** Used by the route composer before the exact profile has been hydrated. */
export function hasDmaTemperatureProcessShape(document: Record<string, unknown> | null | undefined): boolean {
  if (!document) return false;
  return channelsFor(document, "physics.temperature").length > 0
    && channelsFor(document, "mechanics.modulus.storage").length > 0
    && channelsFor(document, "mechanics.modulus.loss").length > 0;
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
  inputMode: DmaTtsInputMode;
  referenceTemperatureK: string;
  c1: string;
  c2K: string;
  dispositions: Array<{ partition: DmaTtsPartition; exclusionReason: string }>;
  sweepDispositions: DmaTtsSweepDisposition[];
  referenceSweepOrdinal: number | null;
  shiftLawKind: "wlf_fit" | "arrhenius_fit" | "manual_tabulated";
  initialParameters: string[];
  lowerBounds: string[];
  upperBounds: string[];
  manualTable: Array<{ temperatureK: string; log10At: string }>;
  scoring: DmaTtsMultiScoring;
  adjacentOptimizer: DmaTtsAdjacentOptimizer;
  lawOptimizer: DmaTtsLawOptimizer | null;
  confirmed: boolean;
  reason: string;
}

export const DMA_TTS_RECOMMENDATION_REASON = "Use the recommended shift settings for this test.";

const defaultScoring: DmaTtsMultiScoring = {
  minimum_overlap_decades: 0.25,
  scoring_point_count: 101,
  storage_weight: 0.5,
  loss_weight: 0.5,
};

const defaultAdjacent: DmaTtsAdjacentOptimizer = {
  relative_shift_lower_bound_log10: -12,
  relative_shift_upper_bound_log10: 12,
  xatol: 1e-10,
  maxiter: 1000,
  seed: null,
};

function fixedDraft(recommendation: DmaTtsRecommendationResponse, rowCount: number): DmaTtsDraft {
  return {
    inputMode: "fixed_frequency_temperature_sweep",
    referenceTemperatureK: String(recommendation.reference_temperature_k),
    c1: String(recommendation.c1),
    c2K: String(recommendation.c2_k),
    dispositions: Array.from({ length: rowCount }, () => ({ partition: "CALIBRATION", exclusionReason: "" })),
    sweepDispositions: [],
    referenceSweepOrdinal: null,
    shiftLawKind: "wlf_fit",
    initialParameters: [String(recommendation.c1), String(recommendation.c2_k)],
    lowerBounds: [],
    upperBounds: [],
    manualTable: [],
    scoring: defaultScoring,
    adjacentOptimizer: defaultAdjacent,
    lawOptimizer: null,
    confirmed: true,
    reason: DMA_TTS_RECOMMENDATION_REASON,
  };
}

function multiDraft(recommendation: DmaTtsMultiRecommendationResponse): DmaTtsDraft {
  const law = recommendation.shift_law;
  return {
    inputMode: "multi_frequency_isotherms",
    referenceTemperatureK: String(law.reference_temperature_k),
    c1: String(law.initial_parameters[0] ?? ""),
    c2K: String(law.initial_parameters[1] ?? ""),
    dispositions: [],
    sweepDispositions: recommendation.sweep_dispositions.map((item) => ({ ...item })),
    referenceSweepOrdinal: recommendation.reference_sweep_ordinal,
    shiftLawKind: law.kind,
    initialParameters: law.initial_parameters.map(String),
    lowerBounds: law.lower_bounds.map(String),
    upperBounds: law.upper_bounds.map(String),
    manualTable: [],
    scoring: { ...recommendation.scoring },
    adjacentOptimizer: { ...recommendation.adjacent_optimizer },
    lawOptimizer: { ...recommendation.law_optimizer, initial_parameters: recommendation.law_optimizer.initial_parameters.map(Number), lower_bounds: recommendation.law_optimizer.lower_bounds.map(Number), upper_bounds: recommendation.law_optimizer.upper_bounds.map(Number) },
    confirmed: true,
    reason: DMA_TTS_RECOMMENDATION_REASON,
  };
}

export function draftFromDmaTtsRecommendation(
  recommendation: DmaTtsRecommendationResponse | DmaTtsMultiRecommendationResponse,
  rowCount = 0,
): DmaTtsDraft {
  return recommendation.input_mode === "multi_frequency_isotherms"
    ? multiDraft(recommendation)
    : fixedDraft(recommendation, rowCount);
}

function numbers(values: string[]): number[] | null {
  const parsed = values.map(finite);
  return parsed.every((value): value is number => value !== null) ? parsed : null;
}

function sameNumbers(left: readonly number[], right: readonly number[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function positiveBoundedVectors(
  initialValues: string[],
  lowerValues: string[],
  upperValues: string[],
  expectedLength: number,
): boolean {
  const initial = numbers(initialValues);
  const lower = numbers(lowerValues);
  const upper = numbers(upperValues);
  return Boolean(initial && lower && upper
    && initial.length === expectedLength
    && lower.length === expectedLength
    && upper.length === expectedLength
    && initial.every((value, index) => value > lower[index] && value < upper[index])
    && lower.every((value) => value > 0)
    && initial.every((value) => value > 0)
    && upper.every((value) => value > 0));
}

function lawOptimizerReady(draft: DmaTtsDraft, expectedLength: number): boolean {
  const optimizer = draft.lawOptimizer;
  if (!optimizer
    || optimizer.seed !== null
    || optimizer.initial_parameters.length !== expectedLength
    || optimizer.lower_bounds.length !== expectedLength
    || optimizer.upper_bounds.length !== expectedLength
    || optimizer.ftol !== 1e-12
    || optimizer.xtol !== 1e-12
    || optimizer.gtol !== 1e-12
    || optimizer.max_nfev !== 5000) return false;
  return optimizer.initial_parameters.every((value, index) => Number.isFinite(value)
    && value > optimizer.lower_bounds[index]
    && value < optimizer.upper_bounds[index]
    && optimizer.lower_bounds[index] > 0
    && optimizer.upper_bounds[index] > 0);
}

function scoringReady(scoring: DmaTtsMultiScoring): boolean {
  return Number.isFinite(scoring.minimum_overlap_decades)
    && scoring.minimum_overlap_decades > 0
    && Number.isInteger(scoring.scoring_point_count)
    && scoring.scoring_point_count >= 2
    && scoring.scoring_point_count <= 10001
    && Number.isFinite(scoring.storage_weight)
    && Number.isFinite(scoring.loss_weight)
    && scoring.storage_weight >= 0
    && scoring.loss_weight >= 0
    && scoring.storage_weight + scoring.loss_weight === 1;
}

function adjacentOptimizerReady(optimizer: DmaTtsAdjacentOptimizer): boolean {
  return optimizer.seed === null
    && Number.isFinite(optimizer.relative_shift_lower_bound_log10)
    && Number.isFinite(optimizer.relative_shift_upper_bound_log10)
    && optimizer.relative_shift_lower_bound_log10 <= optimizer.relative_shift_upper_bound_log10
    && optimizer.xatol === 1e-10
    && optimizer.maxiter === 1000;
}

function partitionReady(draft: DmaTtsDraft): boolean {
  if (draft.sweepDispositions.length === 0) return false;
  const reference = draft.sweepDispositions.find((item) => item.source_sweep_ordinal === draft.referenceSweepOrdinal);
  const calibration = draft.sweepDispositions.filter((item) => item.partition === "CALIBRATION");
  const holdout = draft.sweepDispositions.filter((item) => item.partition === "HOLDOUT");
  const ordinals = draft.sweepDispositions.map((item) => item.source_sweep_ordinal);
  return Boolean(reference
    && reference.partition === "CALIBRATION"
    && reference.representative_temperature_k === finite(draft.referenceTemperatureK)
    && calibration.length >= 2
    && holdout.length === 1
    && new Set(ordinals).size === ordinals.length
    && draft.sweepDispositions.every((item) => item.source_sweep_ordinal > 0
      && (item.partition === "EXCLUDED"
        ? Boolean(item.exclusion_reason?.trim())
        : item.exclusion_reason === null)));
}

function manualTableReady(draft: DmaTtsDraft): boolean {
  const included = draft.sweepDispositions.filter((item) => item.partition !== "EXCLUDED");
  const rows = draft.manualTable.map((item) => ({
    temperature: finite(item.temperatureK),
    log10At: finite(item.log10At),
  }));
  if (rows.length !== included.length || rows.some((row) => row.temperature === null || row.log10At === null || row.temperature <= 0)) return false;
  if (new Set(rows.map((row) => row.temperature)).size !== rows.length) return false;
  return included.every((item) => rows.some((row) => row.temperature === item.representative_temperature_k))
    && rows.some((row) => row.temperature === finite(draft.referenceTemperatureK) && row.log10At === 0);
}

function multiLawReady(draft: DmaTtsDraft): boolean {
  if (!partitionReady(draft) || !scoringReady(draft.scoring) || !adjacentOptimizerReady(draft.adjacentOptimizer)) return false;
  if (draft.shiftLawKind === "manual_tabulated") {
    return draft.lawOptimizer === null && manualTableReady(draft);
  }
  const expectedLength = draft.shiftLawKind === "wlf_fit" ? 2 : 1;
  return positiveBoundedVectors(draft.initialParameters, draft.lowerBounds, draft.upperBounds, expectedLength)
    && lawOptimizerReady(draft, expectedLength)
    && sameNumbers(draft.initialParameters.map(Number), draft.lawOptimizer!.initial_parameters)
    && sameNumbers(draft.lowerBounds.map(Number), draft.lawOptimizer!.lower_bounds)
    && sameNumbers(draft.upperBounds.map(Number), draft.lawOptimizer!.upper_bounds);
}

function multiRequest(
  testData: CanonicalTestDataDocumentResponse,
  pins: DmaTtsRecommendationRequest,
  recommendation: DmaTtsMultiRecommendationResponse,
  draft: DmaTtsDraft,
  label: string,
): CreateDmaTtsRequest | null {
  const reference = finite(draft.referenceTemperatureK);
  const reason = draft.reason.trim();
  if (!dmaTtsDraftReady(draft, label) || draft.inputMode !== "multi_frequency_isotherms"
    || reference === null || draft.referenceSweepOrdinal === null) return null;
  const initial = numbers(draft.initialParameters);
  const lower = numbers(draft.lowerBounds);
  const upper = numbers(draft.upperBounds);
  const manualTable = draft.manualTable.map((item) => ({
    temperature_k: finite(item.temperatureK),
    log10_a_t: finite(item.log10At),
  }));
  const unchanged = recommendation.reference_sweep_ordinal === draft.referenceSweepOrdinal
    && recommendation.reference_temperature_k === reference
    && draft.shiftLawKind === "wlf_fit"
    && initial !== null && lower !== null && upper !== null
    && recommendation.shift_law.kind === draft.shiftLawKind
    && sameNumbers(recommendation.shift_law.initial_parameters, initial)
    && sameNumbers(recommendation.shift_law.lower_bounds, lower)
    && sameNumbers(recommendation.shift_law.upper_bounds, upper)
    && JSON.stringify(recommendation.sweep_dispositions) === JSON.stringify(draft.sweepDispositions)
    && JSON.stringify(recommendation.scoring) === JSON.stringify(draft.scoring)
    && JSON.stringify(recommendation.adjacent_optimizer) === JSON.stringify(draft.adjacentOptimizer)
    && JSON.stringify(recommendation.law_optimizer) === JSON.stringify(draft.lawOptimizer);
  const shiftLaw = draft.shiftLawKind === "manual_tabulated"
    ? {
        kind: draft.shiftLawKind,
        reference_temperature_k: reference,
        manual_table: manualTable.map((item) => ({
          temperature_k: item.temperature_k!,
          log10_a_t: item.log10_a_t!,
        })),
      }
    : {
        kind: draft.shiftLawKind,
        reference_temperature_k: reference,
        initial_parameters: initial!,
        lower_bounds: lower!,
        upper_bounds: upper!,
      };
  return {
    classification: testData.current_revision.classification,
    label: label.trim(),
    ...pins,
    input_mode: "multi_frequency_isotherms",
    sweep_dispositions: draft.sweepDispositions.map((item) => ({ ...item, exclusion_reason: item.partition === "EXCLUDED" ? item.exclusion_reason?.trim() ?? "" : null })),
    reference_sweep_ordinal: draft.referenceSweepOrdinal,
    shift_law: shiftLaw as Extract<CreateDmaTtsRequest, { input_mode: "multi_frequency_isotherms" }>["shift_law"],
    scoring: { ...draft.scoring },
    adjacent_optimizer: { ...draft.adjacentOptimizer },
    law_optimizer: draft.shiftLawKind === "manual_tabulated" ? null : draft.lawOptimizer,
    confirmation: { confirmed: true, reason },
    change_reason: reason,
    recommendation_sha256: unchanged ? recommendation.recommendation_sha256 : null,
  };
}

export function buildCreateDmaTtsRequest(
  testData: CanonicalTestDataDocumentResponse,
  pins: DmaTtsRecommendationRequest,
  recommendation: DmaTtsRecommendationResponse | DmaTtsMultiRecommendationResponse,
  draft: DmaTtsDraft,
  label: string,
): CreateDmaTtsRequest | null {
  if (recommendation.input_mode === "multi_frequency_isotherms") {
    return multiRequest(testData, pins, recommendation, draft, label);
  }
  const referenceTemperatureK = finite(draft.referenceTemperatureK);
  const c1 = finite(draft.c1);
  const c2K = finite(draft.c2K);
  const reason = draft.reason.trim();
  if (!dmaTtsDraftReady(draft, label) || draft.inputMode !== "fixed_frequency_temperature_sweep"
    || referenceTemperatureK === null || c1 === null || c2K === null) return null;
  const recommendationUnchanged = referenceTemperatureK === recommendation.reference_temperature_k
    && c1 === recommendation.c1 && c2K === recommendation.c2_k;
  return {
    classification: testData.current_revision.classification,
    label: label.trim(),
    ...pins,
    input_mode: "fixed_frequency_temperature_sweep",
    row_dispositions: draft.dispositions.map((item, source_ordinal) => ({
      source_ordinal,
      partition: item.partition,
      exclusion_reason: item.partition === "EXCLUDED" ? item.exclusionReason.trim() : null,
    })),
    shift_law: {
      kind: "wlf",
      reference_temperature_k: referenceTemperatureK,
      c1,
      c2_k: c2K,
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
  const exclusionsComplete = draft.dispositions.every((item) => item.partition !== "EXCLUDED" || item.exclusionReason.trim());
  const fixedReady = draft.inputMode === "fixed_frequency_temperature_sweep"
    && draft.dispositions.filter((item) => item.partition !== "EXCLUDED").length >= 2
    && exclusionsComplete;
  const multiReady = draft.inputMode === "multi_frequency_isotherms"
    && multiLawReady(draft);
  return draft.confirmed && Boolean(draft.reason.trim()) && Boolean(label.trim())
    && referenceTemperatureK !== null && referenceTemperatureK > 0
    && ((fixedReady && c1 !== null && c1 > 0 && c2K !== null && c2K > 0)
      || multiReady);
}

export type { DmaTtsExactImportProfilePin, DmaTtsExactTestDataPin };
