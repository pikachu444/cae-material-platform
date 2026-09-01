import { describe, expect, it } from "vitest";

import type { CanonicalTestDataDocumentResponse, GovernedImportProfileResponse } from "../../test-data/contracts";
import type { DmaTtsRecommendationResponse } from "./dma-tts-contracts";
import {
  buildCreateDmaTtsRequest,
  draftFromDmaTtsRecommendation,
  exactDmaTtsPins,
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
      .toMatchObject({ recommendation_sha256: "d".repeat(64), shift_law: { value_origin: "generic_wlf_at_tg_starting_suggestion" } });
    expect(buildCreateDmaTtsRequest(testData, pins, recommendation, { ...confirmed, c1: "18" }, "Shifted DMA response"))
      .toMatchObject({ recommendation_sha256: null, shift_law: { c1: 18, value_origin: "engineer_edited" } });
  });
});
