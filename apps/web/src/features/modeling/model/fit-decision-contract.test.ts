import { describe, expect, it } from "vitest";

import {
  buildFitDecisionSnapshot,
  fitDecisionIdentityLabel,
  hardeningCandidateWarning,
  METAL_HARDENING_EQUATION_CONTRACT,
  type FitDecisionSelection,
} from "./fit-decision-contract";
import type { CommonCurveStage, CommonProcessingStep } from "./common-processing-contracts";

const polymerStep: CommonProcessingStep = {
  method_id: "polymer.prony_fit_compare",
  method_version: "1.0.0",
  options: { selection_mode: "automatic_bic", candidate_term_counts: [2, 3] },
};

const polymerStage: CommonCurveStage = {
  ordinal: 1,
  method_id: polymerStep.method_id,
  method_version: polymerStep.method_version,
  point_count: 3,
  series: [{ quantity: "time", unit: "s", values: [0.1, 1, 10] }],
  diagnostics: [],
  scalar_results: [
    {
      key: "prony_selected_term_count",
      quantity_semantics: "count",
      value: 3,
      unit: "1",
    },
    {
      key: "prony_3_normalized_rmse",
      quantity_semantics: "statistics.normalized_rmse",
      value: 0.01,
      unit: "1",
    },
    {
      key: "prony_equilibrium_modulus",
      quantity_semantics: "model.parameter",
      value: 1e6,
      unit: "Pa",
    },
    {
      key: "prony_g_ratio_1",
      quantity_semantics: "model.parameter",
      value: 0.4,
      unit: "1",
    },
    {
      key: "prony_relaxation_time_1",
      quantity_semantics: "model.parameter",
      value: 2,
      unit: "s",
    },
  ],
};

const ghoshStep: CommonProcessingStep = {
  method_id: "metal.hardening_fit_extrapolate",
  method_version: "1.0.0",
  options: {
    equation_contract: METAL_HARDENING_EQUATION_CONTRACT,
    fit_minimum_strain: 0,
    fit_maximum_strain: 0.4,
    extrapolation_maximum_strain: 0.6,
  },
};

const ghoshStage: CommonCurveStage = {
  ordinal: 1,
  method_id: ghoshStep.method_id,
  method_version: ghoshStep.method_version,
  point_count: 3,
  series: [{ quantity: "strain.true_plastic", unit: "1", values: [0, 0.2, 0.4] }],
  diagnostics: ["equation_contract=altair-material-modeler-2025-v1"],
  scalar_results: [
    { key: "ghosh.relative_rmse", quantity_semantics: "statistics.relative_rmse", value: 0, unit: "1" },
    { key: "ghosh.parameter.k_pa", quantity_semantics: "model.parameter.k_pa", value: 420e6, unit: "Pa" },
    { key: "ghosh.parameter.epsilon_0", quantity_semantics: "model.parameter.epsilon_0", value: 0.8, unit: "1" },
    { key: "ghosh.parameter.delta_p_minus_n", quantity_semantics: "model.parameter.delta_p_minus_n", value: 0.24, unit: "1" },
  ],
};

function selection(actualTermCount: number): FitDecisionSelection {
  return {
    candidateKey: `prony:${actualTermCount}`,
    displayLabel: `${actualTermCount}-term Generalized Maxwell`,
    mode: "single",
    primaryLaw: "generalized_maxwell",
    actualTermCount,
    requestedTermPolicy: "automatic_bic",
    reason: "Select the recomputed server result.",
    warningAcknowledged: false,
    fitRange: "Measured time grid; no extrapolation",
  };
}

describe("Fit decision persistence contract", () => {
  it("persists only the actual server Prony result identity", () => {
    expect(
      buildFitDecisionSnapshot(selection(2), polymerStep, polymerStage, "time"),
    ).toBeNull();

    const snapshot = buildFitDecisionSnapshot(
      selection(3),
      polymerStep,
      polymerStage,
      "time",
    );
    expect(snapshot).toMatchObject({
      candidate_key: "prony:3",
      primary_law: "generalized_maxwell",
      actual_term_count: 3,
      requested_term_policy: "automatic_bic",
      extrapolation_policy: "observed_only",
      fit_minimum: 0.1,
      fit_maximum: 10,
    });
  });

  it("keeps both laws and their ratio in the visible blend identity", () => {
    expect(fitDecisionIdentityLabel({
      mode: "blend",
      primaryLaw: "swift",
      secondaryLaw: "voce",
      primaryWeight: 0.65,
    })).toBe("swift + voce 65/35");
  });

  it("persists only the identifiable Ghosh combination under the Altair equation contract", () => {
    const selected: FitDecisionSelection = {
      candidateKey: "ghosh",
      displayLabel: "ghosh",
      mode: "single",
      primaryLaw: "ghosh",
      reason: "Use the bounded Altair 2025 reference curve.",
      warningAcknowledged: true,
      fitRange: "0–0.4 measured; to 0.6 extrapolated",
      warning: hardeningCandidateWarning("ghosh", false),
    };
    const snapshot = buildFitDecisionSnapshot(
      selected,
      ghoshStep,
      ghoshStage,
      "strain.true_plastic",
    );

    expect(snapshot?.parameter_sets).toEqual([{
      law: "ghosh",
      parameters: [
        { name: "k_pa", value: 420e6, unit: "Pa", lower: null, upper: null },
        { name: "epsilon_0", value: 0.8, unit: "1", lower: null, upper: null },
        { name: "delta_p_minus_n", value: 0.24, unit: "1", lower: null, upper: null },
      ],
    }]);
    expect(hardeningCandidateWarning("ghosh", false)).toContain("not separately identifiable");
    expect(buildFitDecisionSnapshot(
      selected,
      { ...ghoshStep, options: { ...ghoshStep.options, equation_contract: "legacy" } },
      ghoshStage,
      "strain.true_plastic",
    )).toBeNull();
  });
});
