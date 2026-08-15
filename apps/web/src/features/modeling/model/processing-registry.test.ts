import { describe, expect, it } from "vitest";

import type {
  CanonicalTestDataDocumentResponse,
  CommonMappingProfileResponse,
  CommonProcessingStep,
} from "../../../types";
import {
  DEFAULT_PROFILE,
  ELASTOMER_CURVE_PROFILE,
  ELASTOMER_PREPARATION_STEPS,
  METAL_TENSILE_STEPS,
  POLYMER_DMA_PROFILE,
  POLYMER_DMA_STEPS,
  POLYMER_RELAXATION_PROFILE,
  POLYMER_RELAXATION_STEPS,
  defaultOptions,
  documentIsPolymerDma,
  documentMatchesDataTrack,
  documentMatchesTrack,
  isFitMethod,
  manualModulusDisplayValue,
  manualModulusPascals,
  methodDisplayName,
  normalizeToeWarningAcknowledgement,
  numberOption,
  parsedStepArray,
  profileMatchesTrack,
  serverProcessingSteps,
  workupOverridesFromSteps,
} from "./processing-registry";

function document(method: string, semantics: string[]): CanonicalTestDataDocumentResponse {
  return {
    method,
    channels: semantics.map((quantity_semantics) => ({ quantity_semantics })),
  } as CanonicalTestDataDocumentResponse;
}

function profile(content: CommonMappingProfileResponse["content"]): CommonMappingProfileResponse {
  return { content } as CommonMappingProfileResponse;
}

describe("Modeling Processing registry", () => {
  it("keeps the family profiles and ordered method registries exact", () => {
    expect(DEFAULT_PROFILE).toEqual({
      profile_key: "normalized-tensile",
      label: "Normalized tensile channels",
      independent_quantity: "strain.engineering",
      missing_data_policy: "drop_any",
      bindings: [
        {
          channel_key: "engineering_strain",
          target_quantity: "strain.engineering",
          accepted_normalized_units: ["1"],
          required: true,
          scale: 1,
          offset: 0,
        },
        {
          channel_key: "engineering_stress",
          target_quantity: "stress.engineering",
          accepted_normalized_units: ["Pa"],
          required: true,
          scale: 1,
          offset: 0,
        },
      ],
      attribute_bindings: [],
    });
    expect([
      POLYMER_RELAXATION_PROFILE.profile_key,
      POLYMER_DMA_PROFILE.profile_key,
      ELASTOMER_CURVE_PROFILE.profile_key,
    ]).toEqual([
      "polymer-shear-relaxation",
      "polymer-dma-frequency",
      "elastomer-test-mode-preparation",
    ]);
    expect(METAL_TENSILE_STEPS.map((step) => step.method_id)).toEqual([
      "rows.sort_unique",
      "metal.elastic_modulus",
      "metal.proof_stress",
      "metal.necking_candidate",
      "metal.engineering_to_true_plastic",
      "metal.hardening_fit_extrapolate",
    ]);
    expect(POLYMER_RELAXATION_STEPS.map((step) => step.method_id)).toEqual([
      "rows.sort_unique",
      "curve.crop",
      "polymer.log_time_resample",
      "polymer.prony_fit_compare",
    ]);
    expect(POLYMER_DMA_STEPS.map((step) => step.method_id)).toEqual([
      "rows.sort_unique",
      "polymer.dma_prony_fit_compare",
    ]);
    expect(ELASTOMER_PREPARATION_STEPS).toEqual([
      { method_id: "rows.sort_unique", method_version: "1.0.0", options: { duplicate_policy: "reject" } },
    ]);
    expect(METAL_TENSILE_STEPS.at(-1)?.options).toEqual({
      equation_contract: "altair-material-modeler-2025-v1",
      plastic_strain_quantity: "strain.true_plastic",
      stress_quantity: "stress.true",
      families: ["voce", "swift", "hockett_sherby", "ghosh"],
      fit_minimum_strain: 0,
      fit_maximum_strain: 0.1,
      extrapolation_maximum_strain: 1,
      output_point_count: 101,
      primary_family: "swift",
      secondary_family: "voce",
      primary_weight: 0.5,
      normalization_stress_pa: 100000000,
      maximum_function_evaluations: 5000,
    });
  });

  it("returns the existing method defaults as fresh objects", () => {
    const expected = {
      time_quantity: "time",
      modulus_quantity: "modulus.shear.relaxation",
      candidate_term_counts: [1, 2, 3, 4],
      selection_mode: "automatic_bic",
      selected_term_count: 2,
      normalization_modulus_pa: 10000000,
      minimum_relaxation_time_s: 0.0001,
      maximum_relaxation_time_s: 1000000,
      maximum_function_evaluations: 5000,
    };
    const first = defaultOptions("polymer.prony_fit_compare");
    expect(first).toEqual(expected);
    expect(POLYMER_RELAXATION_STEPS.at(-1)?.options.normalization_modulus_pa).toBe(1000000000);
    (first.candidate_term_counts as number[]).push(8);
    expect(defaultOptions("polymer.prony_fit_compare")).toEqual(expected);
    expect(defaultOptions("unknown.method")).toEqual({});
  });

  it("removes only UI workup fields from server steps without mutating the draft", () => {
    const draft: CommonProcessingStep[] = [{
      method_id: "metal.elastic_modulus",
      method_version: "1.0.0",
      options: {
        method: "manual",
        manual_modulus_pa: 205000000000,
        manual_modulus_unit: "GPa",
        manual_modulus_reason: "  Lab certificate  ",
        manual_necking_unit: "observed-point-index",
        manual_necking_reason: "Reviewed peak",
        retained_option: "exact",
      },
    }];
    const before = JSON.parse(JSON.stringify(draft)) as CommonProcessingStep[];

    expect(serverProcessingSteps(draft)).toEqual([{
      method_id: "metal.elastic_modulus",
      method_version: "1.0.0",
      options: {
        method: "manual",
        manual_modulus_pa: 205000000000,
        retained_option: "exact",
      },
    }]);
    expect(draft).toEqual(before);
    expect(serverProcessingSteps(draft)[0]).not.toBe(draft[0]);
    expect(serverProcessingSteps(draft)[0].options).not.toBe(draft[0].options);
  });

  it("clears a toe warning acknowledgement only when its decision context changes", () => {
    const step = {
      method_id: "tensile.toe_zero_intercept",
      method_version: "1.0.0",
      options: {
        strain_quantity: "strain.engineering",
        stress_quantity: "stress.engineering",
        minimum_strain: 0,
        maximum_strain: 0.002,
        equipment_compliance: "not_provided",
        warning_acknowledged: true,
      },
    };
    const previous = JSON.stringify([step], null, 2);
    const sameContext = JSON.stringify([{ ...step, options: { ...step.options, warning_acknowledged: true } }]);
    const changedContext = JSON.stringify([{
      ...step,
      options: { ...step.options, maximum_strain: 0.003, warning_acknowledged: true },
    }]);

    expect(normalizeToeWarningAcknowledgement(previous, sameContext)).toBe(sameContext);
    expect(parsedStepArray(normalizeToeWarningAcknowledgement(previous, changedContext))).toEqual([{
      ...step,
      options: { ...step.options, maximum_strain: 0.003, warning_acknowledged: false },
    }]);
    expect(normalizeToeWarningAcknowledgement(previous, "not json")).toBe("not json");
  });

  it("builds exact ordered workup overrides and preserves unit conversion", () => {
    const steps: CommonProcessingStep[] = [{
      method_id: "metal.elastic_modulus",
      method_version: "1.0.0",
      options: {
        method: "manual",
        manual_modulus_pa: 205000000000,
        manual_modulus_unit: "GPa",
        manual_modulus_reason: "  Certificate value  ",
      },
    }, {
      method_id: "metal.engineering_to_true_plastic",
      method_version: "1.0.0",
      options: {
        necking_policy: "manual_index",
        manual_necking_index: "42",
        manual_necking_unit: "observed-point-index",
        manual_necking_reason: "  Reviewed peak  ",
      },
    }];

    expect(workupOverridesFromSteps(steps)).toEqual([{
      kind: "youngs_modulus",
      original_value: 205,
      original_unit: "GPa",
      canonical_value: 205000000000,
      canonical_unit: "Pa",
      reason: "Certificate value",
    }, {
      kind: "necking_boundary",
      original_value: 42,
      original_unit: "observed-point-index",
      canonical_value: 42,
      canonical_unit: "observed-point-index",
      reason: "Reviewed peak",
    }]);
    expect(manualModulusPascals(205, "GPa")).toBe(205000000000);
    expect(manualModulusDisplayValue(205000000000, "MPa")).toBe(205000);
    expect(numberOption(steps[1], "manual_necking_index")).toBe(42);
  });

  it("keeps track eligibility and the governed Data-only extensions distinct", () => {
    const metal = document("tensile", ["strain.engineering", "stress.engineering"]);
    const elastomer = document("planar tension", ["strain.engineering", "stress.engineering"]);
    const relaxation = document("stress relaxation", ["time.elapsed", "modulus.shear.relaxation"]);
    const dma = document("frequency sweep", [
      "frequency.cyclic",
      "modulus.shear.storage",
      "modulus.shear.loss",
    ]);
    const governedDma = document("bounded governed import", [
      "physics.temperature",
      "frequency.cyclic",
      "mechanics.modulus.storage",
      "mechanics.modulus.loss",
    ]);
    const fld = document("bounded governed import", ["mechanics.strain.minor", "mechanics.strain.major"]);

    expect(documentMatchesTrack(metal, "metal")).toBe(true);
    expect(documentMatchesTrack(metal, "elastomer")).toBe(false);
    expect(documentMatchesTrack(elastomer, "elastomer")).toBe(true);
    expect(documentMatchesTrack(relaxation, "polymer")).toBe(true);
    expect(documentMatchesTrack(dma, "polymer")).toBe(true);
    expect(documentIsPolymerDma(dma)).toBe(true);
    expect(documentIsPolymerDma(governedDma)).toBe(false);
    expect(documentMatchesDataTrack(governedDma, "polymer")).toBe(true);
    expect(documentMatchesDataTrack(fld, "metal")).toBe(true);
    expect(documentMatchesTrack(fld, "metal")).toBe(false);
  });

  it("keeps Mapping Profile track checks unchanged", () => {
    expect(profileMatchesTrack(profile(DEFAULT_PROFILE), "metal")).toBe(true);
    expect(profileMatchesTrack(profile(POLYMER_RELAXATION_PROFILE), "polymer")).toBe(true);
    expect(profileMatchesTrack(profile(POLYMER_DMA_PROFILE), "polymer")).toBe(true);
    expect(profileMatchesTrack(profile(ELASTOMER_CURVE_PROFILE), "elastomer")).toBe(true);
    expect(profileMatchesTrack(profile(DEFAULT_PROFILE), "polymer")).toBe(false);
  });

  it("keeps Fit method classification and labels exact", () => {
    expect(isFitMethod("metal.hardening_fit_extrapolate")).toBe(true);
    expect(isFitMethod("polymer.prony_fit_compare")).toBe(true);
    expect(isFitMethod("curve.crop")).toBe(false);
    expect(methodDisplayName("mapping")).toBe("Mapped source");
    expect(methodDisplayName("metal.elastic_modulus")).toBe("Young's modulus");
    expect(methodDisplayName("curve.scale_shift")).toBe("Scale Shift");
  });
});
