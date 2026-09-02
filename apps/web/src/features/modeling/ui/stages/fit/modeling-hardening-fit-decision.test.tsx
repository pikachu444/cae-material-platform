import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  CommonCurveStage,
  CommonHardeningCandidate,
  CommonProcessingStep,
} from "../../../model/common-processing-contracts";
import { METAL_HARDENING_EQUATION_CONTRACT } from "../../../model/fit-decision-contract";
import { HardeningFitDecision } from "./modeling-hardening-fit-decision";

const candidate = (family: string, relativeRmse: number): CommonHardeningCandidate => ({
  family,
  response: [1, 2, 3],
  residual: [0, 0, 0],
  tangent: [1, 1, 1],
  parameter_names: ["strength"],
  parameter_units: ["Pa"],
  lower: [0],
  initial: [1],
  fitted: [1],
  upper: [2],
  rmse_pa: relativeRmse * 1e6,
  relative_rmse: relativeRmse,
  objective: relativeRmse,
  scipy_cost: relativeRmse,
  convergence: true,
  nfev: 5,
  active_bound: [],
  jacobian_rank: 1,
  jacobian_tolerance: 1e-8,
  jacobian_condition: 1,
  identifiability: "identified",
  uncertainty: "bounded",
  objective_history: [relativeRmse],
});

const step: CommonProcessingStep = {
  method_id: "metal.hardening_fit_extrapolate",
  method_version: "1.0.0",
  options: {
    equation_contract: METAL_HARDENING_EQUATION_CONTRACT,
    families: ["swift", "voce"],
    fit_minimum_strain: 0,
    fit_maximum_strain: 0.4,
    extrapolation_maximum_strain: 0.6,
    primary_family: "swift",
    secondary_family: "voce",
    primary_weight: 0.6,
  },
};

const stage: CommonCurveStage = {
  ordinal: 1,
  method_id: step.method_id,
  method_version: step.method_version,
  point_count: 3,
  series: [{ quantity: "strain.true_plastic", unit: "1", values: [0, 0.2, 0.4] }],
  diagnostics: [],
  scalar_results: [
    { key: "swift.relative_rmse", quantity_semantics: "fit", value: 0.04, unit: "1" },
    { key: "voce.relative_rmse", quantity_semantics: "fit", value: 0.03, unit: "1" },
  ],
  fit_candidates: [
    candidate("swift", 0.04),
    candidate("voce", 0.03),
    candidate("swift+voce", 0.02),
  ],
};

afterEach(cleanup);

describe("HardeningFitDecision", () => {
  it("compares every calculated single and combined model and allows the combined model to be selected", () => {
    const onSelect = vi.fn();
    render(
      <HardeningFitDecision
        stage={stage}
        step={step}
        selection={null}
        stateLabel="Preview not saved"
        busy={false}
        saveReady={false}
        onSelect={onSelect}
        onChangeSelection={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("radio")).toHaveLength(3);
    expect(screen.getByText("swift + voce 60/40")).toBeTruthy();
    expect(screen.getAllByText("Recommended")).toHaveLength(1);
    fireEvent.click(screen.getByRole("radio", { name: "Select swift + voce 60/40" }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({
      candidateKey: "swift+voce",
      mode: "blend",
      primaryLaw: "swift",
      secondaryLaw: "voce",
      primaryWeight: 0.6,
    }));
  });

  it("keeps the selection reason and save action together", () => {
    const onChangeSelection = vi.fn();
    const onSave = vi.fn();
    render(
      <HardeningFitDecision
        stage={stage}
        step={step}
        selection={{
          candidateKey: "voce",
          displayLabel: "voce",
          mode: "single",
          primaryLaw: "voce",
          reason: "Good extrapolation behavior",
          warningAcknowledged: false,
          fitRange: "0–0.4 measured; to 0.6",
        }}
        stateLabel="Preview not saved"
        busy={false}
        saveReady
        onSelect={vi.fn()}
        onChangeSelection={onChangeSelection}
        onSave={onSave}
      />,
    );

    fireEvent.change(screen.getByLabelText("Candidate selection reason"), {
      target: { value: "Stable response over the required range" },
    });
    expect(onChangeSelection).toHaveBeenCalledWith(expect.objectContaining({
      reason: "Stable response over the required range",
    }));
    fireEvent.click(screen.getByRole("button", { name: "Save fit & continue" }));
    expect(onSave).toHaveBeenCalledOnce();
  });
});
