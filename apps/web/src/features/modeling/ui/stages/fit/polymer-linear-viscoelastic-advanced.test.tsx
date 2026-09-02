import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PolymerLinearViscoelasticAdvanced } from "./polymer-linear-viscoelastic-advanced";
import type { PolymerFitSetupActions, PolymerFitSetupViewModel } from "./polymer-linear-viscoelastic-setup-types";

const actions = Object.fromEntries([
  "chooseSource", "setSelectedTemperature", "setAvailability", "setPartition",
  "markAllCalibration", "excludeOtherTemperatures", "toggleTerm", "setCandidateScopeMode", "updateBound",
  "setWeight", "setOptimizer", "setSetupName", "setOverrideReason", "setChangeReason",
].map((name) => [name, vi.fn()])) as unknown as PolymerFitSetupActions;

const view: PolymerFitSetupViewModel = {
  sourceChoice: "test-data",
  processedAvailable: false,
  processedInputStatus: "idle",
  processedInputError: null,
  processedFitInput: null,
  activeDirectMode: "relaxation",
  snapshot: { mode: "relaxation", pointCount: 0, channels: [], temperatures: [], conditionTemperature: null },
  selectedTemperature: "",
  availableTemperatures: [],
  availability: { ramp: "NOT_PROVIDED", sweep: "NOT_PROVIDED", preconditioning: "NOT_PROVIDED", linear_range: "NOT_PROVIDED" },
  partitions: [],
  partitionCounts: { calibration: 0, holdout: 0, excluded: 0, unresolved: 0 },
  fitObservationCount: 0,
  candidateScopeMode: "automatic",
  termCounts: [],
  bounds: {},
  weights: {
    relaxation_weight: "1",
    dma_storage_weight: "0.5",
    dma_loss_weight: "0.5",
    relaxation_scale_pa: "1",
    dma_storage_scale_pa: "1",
    dma_loss_scale_pa: "1",
    q_rule_version: "equal_per_point@1.0.0",
  },
  optimizer: { ftol: "1e-8", xtol: "1e-8", gtol: "1e-8", max_nfev: "1000" },
  setupName: "Reviewed setup B",
  baseSetupName: "Approved setup A",
  overrideReason: "Extend the comparison to longer relaxation times.",
  changeReason: "Compare the reviewed extension.",
  serverDiff: { term_counts: { before: [1, 2], after: [1, 2, 3] }, optimizer: { before: {}, after: {} } },
  reviewStatus: "pending",
  directBlockers: [],
  modelBlockers: [],
  solverBlockers: [],
};

afterEach(cleanup);

describe("Polymer Advanced calculation setup", () => {
  it("shows the approved base, human-readable server diff, and pending review state", () => {
    render(<PolymerLinearViscoelasticAdvanced
      view={view}
      actions={actions}
      busy={false}
      onClose={vi.fn()}
      onReset={vi.fn()}
      onCreateDraft={vi.fn()}
    />);

    expect((screen.getByLabelText("Based on") as HTMLInputElement).value).toBe("Approved setup A");
    const diff = screen.getByRole("heading", { name: "Changes sent for review" }).closest("section")!;
    expect(within(diff).getByText("Prony models")).toBeTruthy();
    expect(within(diff).getByText("Solver limits")).toBeTruthy();
    expect(within(diff).queryByText("term_counts")).toBeNull();
    expect((screen.getByRole("button", { name: "Review requested" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
