import { describe, expect, it } from "vitest";

import type { CanonicalTestDataDocumentResponse, GovernedImportProfileResponse } from "../../test-data/contracts";
import type { DmaTtsMultiRecommendationResponse, DmaTtsRecommendationResponse } from "./dma-tts-contracts";
import {
  buildCreateDmaTtsRequest,
  classifyDmaTtsSource,
  draftFromDmaTtsRecommendation,
  exactDmaTtsPins,
  parseDmaFrequencyTemperatureSweeps,
  parseDmaTemperatureSweep,
} from "./dma-tts-draft";

const revision = {
  id: "revision-a", aggregate_id: "document-a", revision_no: 1, based_on_revision_id: null,
  schema_id: "schema", schema_version: "1", content_hash: "a".repeat(64), created_at: "2026-01-01T00:00:00Z",
  created_by: "engineer", change_reason: "test", organization_id: "org", project_id: "project",
  classification: "internal" as const, lifecycle_state: "draft" as const,
};

const testData = {
  test_data_document_id: "document-a",
  current_revision: revision,
  governed_source: { material: { aggregate_id: "material", revision_id: "m-r" }, material_state: { aggregate_id: "state", revision_id: "s-r" }, test_run: { aggregate_id: "run", revision_id: "run-r" }, tabular_import: { raw_asset_id: "raw", raw_artifact_id: "artifact", import_run_id: "import", import_profile: { aggregate_id: "profile", revision_id: "profile-r" }, normalized_dataset: { aggregate_id: "dataset", revision_id: "dataset-r" } } },
} as CanonicalTestDataDocumentResponse;

const profile = {
  import_profile_id: "profile",
  current_revision: { ...revision, id: "profile-r", aggregate_id: "profile", content_hash: "b".repeat(64) },
  content: { profile_sha256: "c".repeat(64) },
} as GovernedImportProfileResponse;

const recommendation: DmaTtsRecommendationResponse = {
  source_evidence: {}, reference_temperature_k: 293.15, source_ordinal: 3, c1: 17.44, c2_k: 51.6,
  value_origin: "generic_wlf_at_tg_starting_suggestion", material_specific: false, requires_confirmation: true,
  rule_id: "polymer.dma_wlf_starting_suggestion", rule_version: "1.0.0", recommendation_sha256: "d".repeat(64),
};

const multiProfile = {
  ...profile,
  content: {
    ...profile.content,
    data_schema: "dma_frequency_temperature_sweep",
    channels: [
      { source_quantity: "source_sweep_ordinal", normalized_quantity: "source_sweep_ordinal" },
      { source_quantity: "temperature", normalized_quantity: "temperature" },
      { source_quantity: "frequency", normalized_quantity: "frequency" },
      { source_quantity: "storage_modulus", normalized_quantity: "storage_modulus" },
      { source_quantity: "loss_modulus", normalized_quantity: "loss_modulus" },
    ],
  },
} as unknown as GovernedImportProfileResponse;

const multiDocument = {
  channels: [
    { quantity_semantics: "test.sweep.ordinal", normalized_values: [1, 1, 2, 2, 3, 3] },
    { quantity_semantics: "physics.temperature", normalized_values: [273.15, 273.15, 293.15, 293.15, 303.15, 303.15] },
    { quantity_semantics: "frequency.cyclic", normalized_values: [1, 2, 1, 2, 1, 2] },
    { quantity_semantics: "mechanics.modulus.storage", normalized_values: [1, 2, 3, 4, 5, 6] },
    { quantity_semantics: "mechanics.modulus.loss", normalized_values: [2, 3, 4, 5, 6, 7] },
  ],
};

const multiRecommendation = {
  input_mode: "multi_frequency_isotherms",
  source_evidence: {
    test_data_document_id: "document-a",
    test_data_revision_id: "revision-a",
    test_data_content_sha256: "a".repeat(64),
    import_profile_id: "profile",
    import_profile_revision_id: "profile-r",
    import_profile_content_sha256: "b".repeat(64),
    source_normalized_artifact_id: "normalized-artifact",
    source_normalized_artifact_sha256: "f".repeat(64),
  },
  sweeps: [
    { source_sweep_ordinal: 1, representative_temperature_k: 273.15, point_count: 2, source_frequency_min_hz: 1, source_frequency_max_hz: 2 },
    { source_sweep_ordinal: 2, representative_temperature_k: 293.15, point_count: 2, source_frequency_min_hz: 1, source_frequency_max_hz: 2 },
    { source_sweep_ordinal: 3, representative_temperature_k: 313.15, point_count: 2, source_frequency_min_hz: 1, source_frequency_max_hz: 2 },
  ],
  reference_sweep_ordinal: 2,
  reference_temperature_k: 293.15,
  sweep_dispositions: [
    { source_sweep_ordinal: 1, representative_temperature_k: 273.15, partition: "HOLDOUT", exclusion_reason: null },
    { source_sweep_ordinal: 2, representative_temperature_k: 293.15, partition: "CALIBRATION", exclusion_reason: null },
    { source_sweep_ordinal: 3, representative_temperature_k: 313.15, partition: "CALIBRATION", exclusion_reason: null },
  ],
  shift_law: { kind: "wlf_fit", reference_temperature_k: 293.15, initial_parameters: [17.44, 51.6], lower_bounds: [1, 10], upper_bounds: [100, 100] },
  scoring: { minimum_overlap_decades: 0.25, scoring_point_count: 101, storage_weight: 0.5, loss_weight: 0.5 },
  adjacent_optimizer: { relative_shift_lower_bound_log10: -12, relative_shift_upper_bound_log10: 12, xatol: 1e-10, maxiter: 1000, seed: null },
  law_optimizer: { initial_parameters: [17.44, 51.6], lower_bounds: [1, 10], upper_bounds: [100, 100], ftol: 1e-12, xtol: 1e-12, gtol: 1e-12, max_nfev: 5000, seed: null },
  profile_id: "cmp.dma_tts.multi_frequency_wlf_starting_profile",
  profile_version: "1.0.0",
  material_specific: false,
  production_readiness: "non_production",
  requires_confirmation: true,
  recommendation_sha256: "g".repeat(64),
} satisfies DmaTtsMultiRecommendationResponse;

describe("DMA TTS draft", () => {
  it("recognizes only an exact fixed-frequency temperature sweep", () => {
    const source = parseDmaTemperatureSweep({
      conditions: [{ quantity_semantics: "frequency.cyclic", normalized_unit: "Hz", normalized_value: "1" }],
      channels: [
        { quantity_semantics: "physics.temperature", normalized_values: [273.15, 293.15] },
        { quantity_semantics: "mechanics.modulus.storage", normalized_values: [3e6, 2e6] },
        { quantity_semantics: "mechanics.modulus.loss", normalized_values: [1e5, 4e5] },
      ],
    });
    expect(source).toEqual({ frequencyHz: 1, rows: [
      { ordinal: 0, temperatureK: 273.15, storageModulusPa: 3e6, lossModulusPa: 1e5 },
      { ordinal: 1, temperatureK: 293.15, storageModulusPa: 2e6, lossModulusPa: 4e5 },
    ] });
    expect(parseDmaTemperatureSweep({ channels: [] })).toBeNull();
  });

  it("uses the governed multi schema and blocks disagreement instead of falling through to Fit", () => {
    const source = parseDmaFrequencyTemperatureSweeps(multiDocument);
    expect(source?.sweeps.map((item) => item.sourceSweepOrdinal)).toEqual([1, 2, 3]);
    expect(classifyDmaTtsSource(multiDocument, multiProfile).kind).toBe("multi");

    const scalarFrequency = {
      ...multiDocument,
      conditions: [{ quantity_semantics: "frequency.cyclic", normalized_unit: "Hz", normalized_value: 1 }],
    };
    expect(classifyDmaTtsSource(scalarFrequency, multiProfile).kind).toBe("blocked");

    const directProfile = { ...multiProfile, content: { ...multiProfile.content, data_schema: "dma_frequency_sweep" } } as unknown as GovernedImportProfileResponse;
    expect(classifyDmaTtsSource(multiDocument, directProfile).kind).toBe("blocked");
  });

  it("pins the exact Test Data and governed lineage profile revisions", () => {
    expect(exactDmaTtsPins(testData, [profile])).toEqual({
      test_data: { document_id: "document-a", revision_id: "revision-a", content_sha256: "a".repeat(64) },
      import_profile: { profile_id: "profile", revision_id: "profile-r", content_sha256: "b".repeat(64) },
    });
    expect(exactDmaTtsPins(testData, [])).toBeNull();
  });

  it("uses the server suggestion until the engineer edits it and treats Create as confirmation", () => {
    const pins = exactDmaTtsPins(testData, [profile])!;
    const draft = draftFromDmaTtsRecommendation(recommendation, 3);
    expect(buildCreateDmaTtsRequest(testData, pins, recommendation, draft, "Shifted DMA response"))
      .toMatchObject({ confirmation: { confirmed: true } });
    const confirmed = { ...draft, reason: "Reviewed the WLF starting values." };
    expect(buildCreateDmaTtsRequest(testData, pins, recommendation, confirmed, "Shifted DMA response"))
      .toMatchObject({ recommendation_sha256: "d".repeat(64), shift_law: { kind: "wlf", c1: 17.44 } });
    expect(buildCreateDmaTtsRequest(testData, pins, recommendation, { ...confirmed, c1: "18" }, "Shifted DMA response"))
      .toMatchObject({ recommendation_sha256: null, shift_law: { kind: "wlf", c1: 18 } });
  });

  it("keeps a multi WLF recommendation digest only when every governed control is unchanged", () => {
    const pins = exactDmaTtsPins(testData, [profile])!;
    const draft = draftFromDmaTtsRecommendation(multiRecommendation);
    expect(buildCreateDmaTtsRequest(testData, pins, multiRecommendation, draft, "Multi DMA response"))
      .toMatchObject({
        recommendation_sha256: "g".repeat(64),
        shift_law: { kind: "wlf_fit", initial_parameters: [17.44, 51.6] },
        law_optimizer: { initial_parameters: [17.44, 51.6], seed: null },
      });
    expect(buildCreateDmaTtsRequest(testData, pins, multiRecommendation, { ...draft, initialParameters: ["18", "51.6"], lawOptimizer: { ...draft.lawOptimizer!, initial_parameters: [18, 51.6] }, reason: "Changed WLF start." }, "Multi DMA response"))
      .toMatchObject({ recommendation_sha256: null, shift_law: { kind: "wlf_fit" } });
  });

  it("builds exact Arrhenius vectors and manual tables without inventing client-side TTS values", () => {
    const pins = exactDmaTtsPins(testData, [profile])!;
    const base = draftFromDmaTtsRecommendation(multiRecommendation);
    const arrhenius = {
      ...base,
      shiftLawKind: "arrhenius_fit" as const,
      initialParameters: ["1000"],
      lowerBounds: ["100"],
      upperBounds: ["2000"],
      lawOptimizer: { ...base.lawOptimizer!, initial_parameters: [1000], lower_bounds: [100], upper_bounds: [2000] },
      reason: "Reviewed Arrhenius bounds.",
    };
    expect(buildCreateDmaTtsRequest(testData, pins, multiRecommendation, arrhenius, "Multi DMA response"))
      .toMatchObject({ recommendation_sha256: null, shift_law: { kind: "arrhenius_fit", initial_parameters: [1000], lower_bounds: [100], upper_bounds: [2000] }, law_optimizer: { initial_parameters: [1000] } });
    const manual = {
      ...base,
      shiftLawKind: "manual_tabulated" as const,
      initialParameters: [],
      lowerBounds: [],
      upperBounds: [],
      lawOptimizer: null,
      manualTable: [
        { temperatureK: "273.15", log10At: "0.4" },
        { temperatureK: "293.15", log10At: "0" },
        { temperatureK: "313.15", log10At: "-0.2" },
      ],
      reason: "Reviewed tabulated factors.",
    };
    expect(buildCreateDmaTtsRequest(testData, pins, multiRecommendation, manual, "Multi DMA response"))
      .toMatchObject({ recommendation_sha256: null, shift_law: { kind: "manual_tabulated", manual_table: [{ temperature_k: 273.15, log10_a_t: 0.4 }, { temperature_k: 293.15, log10_a_t: 0 }, { temperature_k: 313.15, log10_a_t: -0.2 }] }, law_optimizer: null });
    expect(buildCreateDmaTtsRequest(testData, pins, multiRecommendation, { ...manual, manualTable: manual.manualTable.slice(1) }, "Multi DMA response"))
      .toBeNull();
  });

  it("requires a calibration reference, one holdout, two calibration sweeps, and exclusion reasons", () => {
    const pins = exactDmaTtsPins(testData, [profile])!;
    const draft = draftFromDmaTtsRecommendation(multiRecommendation);
    expect(buildCreateDmaTtsRequest(testData, pins, multiRecommendation, {
      ...draft,
      sweepDispositions: draft.sweepDispositions.map((item) => item.source_sweep_ordinal === 2 ? { ...item, partition: "HOLDOUT" as const } : item),
      reason: "Invalid partition.",
    }, "Multi DMA response")).toBeNull();
    expect(buildCreateDmaTtsRequest(testData, pins, multiRecommendation, {
      ...draft,
      sweepDispositions: draft.sweepDispositions.map((item) => item.source_sweep_ordinal === 3 ? { ...item, partition: "EXCLUDED" as const, exclusion_reason: "" } : item),
      reason: "Missing exclusion reason.",
    }, "Multi DMA response")).toBeNull();
  });
});
