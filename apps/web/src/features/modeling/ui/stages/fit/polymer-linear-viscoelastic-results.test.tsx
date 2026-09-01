import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LinearViscoelasticCandidate } from "../../../model/linear-viscoelastic-calibration-contracts";
import type { LinearViscoelasticCalibrationState } from "../../../model/linear-viscoelastic-calibration-state";
import { PolymerLinearViscoelasticResults } from "./polymer-linear-viscoelastic-results";

afterEach(cleanup);

describe("PolymerLinearViscoelasticResults", () => {
  it("keeps every physical parameter and the Selection controls reachable for a 10-term candidate", () => {
    const candidate: LinearViscoelasticCandidate = {
      candidate_id: "candidate-10",
      candidate_sha256: "c".repeat(64),
      attempt_ordinal: 1,
      term_count: 10,
      physical_parameters: Array.from({ length: 21 }, (_, index) => index + 1),
      transformed_parameters: Array.from({ length: 21 }, (_, index) => Math.log(index + 1)),
      rss: 0.1,
      bic: -1234.5,
      calibration_residuals: Array.from({ length: 25 }, () => 0.01),
      holdout_residuals: [0.02, 0.03],
      rank: { rank: 21, status: "FULL_RANK" },
      warnings: [],
      uncertainty_status: "NOT_PROVIDED",
    };
    const state: LinearViscoelasticCalibrationState = {
      phase: "succeeded",
      plan: null,
      run: {
        run_id: "run-1",
        plan_revision_id: "plan-revision-1",
        status: "succeeded",
        attempts: [
          { ordinal: 3, term_count: 3, converged: true, physical: true },
          { ordinal: 2, term_count: 5, converged: true, physical: true },
          { ordinal: 4, term_count: 7, converged: false, physical: false, warnings: ["EXECUTION_REQUEST_INVALID"] },
          { ordinal: 1, term_count: 10, converged: true, physical: true },
        ],
        candidates: [candidate],
        recommendation: null,
        failure_code: null,
        failure_detail: null,
        recovery_hint: null,
        execution_ledger_sha256: "f".repeat(64),
      },
      candidates: [candidate],
      recommendation: null,
      responseEvidence: null,
      selection: null,
      selectedModel: null,
      selectedCandidateId: candidate.candidate_id,
      reason: "Use the reviewed 10-term candidate.",
      error: null,
      recoveryHint: null,
    };
    const { container } = render(
      <PolymerLinearViscoelasticResults
        state={state}
        selectedCandidate={candidate}
        recommendedCandidateId={candidate.candidate_id}
        warnings={[]}
        acknowledgedWarnings={new Set()}
        onClearSelection={vi.fn()}
        onSelectionReasonChange={vi.fn()}
        onWarningAcknowledgementChange={vi.fn()}
        onSaveFit={vi.fn()}
        onContinue={vi.fn()}
      />,
    );

    expect(container.querySelectorAll(".polymer-model-coefficients tbody tr")).toHaveLength(21);
    expect(screen.getByText("Relaxation time τ10")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Engineer selection" })).toBeTruthy();
    expect(screen.getByRole("textbox", { name: "Reason for selection" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save fit & continue" })).toBeTruthy();
    expect(screen.getByText("Recommended")).toBeTruthy();
    expect(screen.queryByText("-1234.5")).toBeNull();
    expect(screen.getByRole("heading", { name: "Engineer selection" })).toBeTruthy();
    expect(screen.getByText("10-term Prony")).toBeTruthy();
  });
});
