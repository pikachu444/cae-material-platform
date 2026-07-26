import { describe, expect, it } from "vitest";

import {
  buildFitDecisionSnapshot,
  fitDecisionIdentityLabel,
  type FitDecisionSelection,
} from "./modeling-fit-decision-contract";
import type { CommonCurveStage, CommonProcessingStep } from "./types";

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
});
