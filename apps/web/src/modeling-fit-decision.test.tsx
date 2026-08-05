import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { METAL_HARDENING_EQUATION_CONTRACT } from "./modeling-fit-decision-contract";
import { HardeningCandidateEvidence } from "./modeling-fit-decision";
import type { CommonCurveStage, CommonProcessingStep } from "./types";

const step: CommonProcessingStep = {
  method_id: "metal.hardening_fit_extrapolate",
  method_version: "1.0.0",
  options: {
    equation_contract: METAL_HARDENING_EQUATION_CONTRACT,
    families: ["voce", "ghosh"],
    fit_minimum_strain: 0,
    fit_maximum_strain: 0.4,
    extrapolation_maximum_strain: 0.6,
    primary_family: "ghosh",
    secondary_family: "voce",
    primary_weight: 0.5,
  },
};

const scalar = (
  key: string,
  value: number,
  unit: string,
) => ({ key, quantity_semantics: "fixture", value, unit });

const stage: CommonCurveStage = {
  ordinal: 1,
  method_id: step.method_id,
  method_version: step.method_version,
  point_count: 3,
  series: [{ quantity: "strain.true_plastic", unit: "1", values: [0, 0.2, 0.4] }],
  diagnostics: [],
  scalar_results: [
    scalar("ghosh.rmse_pa", 1, "Pa"),
    scalar("ghosh.relative_rmse", 1e-9, "1"),
    scalar("ghosh.parameter.k_pa", 420e6, "Pa"),
    scalar("ghosh.parameter.epsilon_0", 0.8, "1"),
    scalar("ghosh.parameter.delta_p_minus_n", 0.24, "1"),
    scalar("voce.rmse_pa", 2, "Pa"),
    scalar("voce.relative_rmse", 2e-9, "1"),
    scalar("voce.parameter.sigma_0_pa", 300e6, "Pa"),
  ],
};

describe("HardeningCandidateEvidence", () => {
  afterEach(cleanup);

  it("shows and carries the Ghosh structural-identifiability warning", () => {
    const onSelect = vi.fn();
    render(
      <HardeningCandidateEvidence
        stage={stage}
        step={step}
        selection={null}
        onSelect={onSelect}
        onChangeSelection={vi.fn()}
      />,
    );

    expect(screen.getByText("Structural identifiability")).toBeTruthy();
    expect(screen.getAllByText(/n and p are not separately identifiable/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Select ghosh candidate" }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({
      primaryLaw: "ghosh",
      warningAcknowledged: false,
      warning: expect.stringContaining("evidence stores p − n"),
    }));
  });
});
