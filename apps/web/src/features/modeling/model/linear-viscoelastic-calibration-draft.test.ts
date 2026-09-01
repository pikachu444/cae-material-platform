import { describe, expect, it } from "vitest";

import {
  buildPolymerCalibrationPlanRequest,
  blankPolymerBounds,
  createPolymerCalibrationDraft,
  derivePolymerCalibrationBlockers,
  maximumSupportedPronyTermCount,
  polymerPronyParameterCount,
  togglePolymerCalibrationTerm,
  type PolymerCalibrationSourceContext,
  type PolymerSourceSnapshot,
} from "./linear-viscoelastic-calibration-draft";

const snapshot: PolymerSourceSnapshot = {
  mode: "relaxation",
  pointCount: 3,
  channels: [
    { key: "time", quantity: "time.elapsed", unit: "s", values: [0.1, 1, 10] },
    { key: "modulus", quantity: "modulus.shear.relaxation", unit: "Pa", values: [3, 2, 1] },
  ],
  temperatures: [],
  conditionTemperature: 293.15,
};

const source: PolymerCalibrationSourceContext = {
  sourceChoice: "test-data",
  directAvailable: true,
  processedAvailable: false,
  processedCalibrationObservationCount: 0,
  directSource: {
    id: "37700000-0000-4000-8000-000000000011",
    revisionId: "37700000-0000-4000-8000-000000000012",
  },
  snapshot,
};
const governance = {
  material: { id: "37700000-0000-4000-8000-000000000021", revisionId: "37700000-0000-4000-8000-000000000022" },
  materialState: { id: "37700000-0000-4000-8000-000000000023", revisionId: "37700000-0000-4000-8000-000000000024" },
  inputMode: "relaxation" as const,
};

describe("linear-viscoelastic calibration draft", () => {
  it("does not create a request from implicit or incomplete production policy", () => {
    const draft = createPolymerCalibrationDraft(snapshot);

    expect(derivePolymerCalibrationBlockers(draft, source).direct).toContain(
      "Choose how each of the 3 unassigned measured points will be used.",
    );
    expect(buildPolymerCalibrationPlanRequest(draft, source, governance)).toBeNull();
  });

  it("pins the exact Test Data revision in a fully explicit request", () => {
    const draft = createPolymerCalibrationDraft(snapshot);
    draft.partitions = ["CALIBRATION", "CALIBRATION", "CALIBRATION"];
    draft.termCounts = [1];
    draft.bounds = { "1": blankPolymerBounds(1).map((bound, index) => ({
      ...bound,
      lower: index === 2 ? 0.01 : 100_000,
      start: index === 0 ? 900_000 : index === 1 ? 1_800_000 : 0.4,
      upper: index === 2 ? 1 : 5_000_000,
    })) };
    draft.availability = {
      ramp: "NOT_PROVIDED",
      sweep: "NOT_PROVIDED",
      preconditioning: "NOT_PROVIDED",
      linear_range: "NOT_PROVIDED",
    };
    draft.weights = {
      relaxation_weight: "1",
      dma_storage_weight: "0.5",
      dma_loss_weight: "0.5",
      relaxation_scale_pa: "1",
      dma_storage_scale_pa: "1",
      dma_loss_scale_pa: "1",
      q_rule_version: "equal_per_point@1.0.0",
    };
    draft.optimizer = { ftol: "1e-8", xtol: "1e-8", gtol: "1e-8", max_nfev: "1000" };
    draft.setupName = "Reference relaxation setup";
    draft.changeReason = "Calibrate the exact governed relaxation dataset.";

    const request = buildPolymerCalibrationPlanRequest(draft, source, governance);

    expect(request).toMatchObject({
      test_data: {
        id: source.directSource?.id,
        revision_id: source.directSource?.revisionId,
      },
      selected_temperature_k: 293.15,
      term_counts: [1],
      recommendation_policy: "lowest_bic_then_term_count_then_attempt_ordinal@1.0.0",
      setup_name: "Reference relaxation setup",
      material: { id: governance.material.id, revision_id: governance.material.revisionId },
      material_state: { id: governance.materialState.id, revision_id: governance.materialState.revisionId },
    });
  });

  it("limits term choices by the values actually used to calculate the model", () => {
    expect(polymerPronyParameterCount(1)).toBe(3);
    expect(polymerPronyParameterCount(3)).toBe(7);
    expect(polymerPronyParameterCount(10)).toBe(21);
    expect(maximumSupportedPronyTermCount(6)).toBe(2);
    expect(maximumSupportedPronyTermCount(21)).toBe(10);

    const sixPointSnapshot = { ...snapshot, pointCount: 6 };
    const draft = createPolymerCalibrationDraft(sixPointSnapshot);
    draft.partitions = Array.from({ length: 6 }, () => "CALIBRATION" as const);
    draft.candidateScopeMode = "manual";
    draft.termCounts = [3];
    const blockers = derivePolymerCalibrationBlockers(draft, { ...source, snapshot: sixPointSnapshot });

    expect(blockers.model).toContain(
      "The selected Prony models need more values than the 6 values used to calculate the model.",
    );
  });

  it("uses reviewed bounds already carried by the approved setup when another term is selected", () => {
    const draft = createPolymerCalibrationDraft(snapshot);
    const reviewedTenTermBounds = blankPolymerBounds(10).map((bound) => ({
      ...bound,
      lower: 1,
      start: 2,
      upper: 3,
    }));
    draft.termCounts = [3, 5];
    draft.bounds = { "10": reviewedTenTermBounds };

    const changed = togglePolymerCalibrationTerm(draft, 10);

    expect(changed.termCounts).toEqual([3, 5, 10]);
    expect(changed.bounds["10"]).toBe(reviewedTenTermBounds);
    expect(changed.bounds["10"]).toHaveLength(21);
  });

  it("builds the complete 21-parameter request for a supported 10-term model", () => {
    const denseSnapshot = { ...snapshot, pointCount: 25 };
    const denseSource = { ...source, snapshot: denseSnapshot };
    const draft = createPolymerCalibrationDraft(denseSnapshot);
    draft.partitions = Array.from({ length: 25 }, () => "CALIBRATION" as const);
    draft.candidateScopeMode = "manual";
    draft.termCounts = [10];
    draft.bounds = {
      "10": blankPolymerBounds(10).map((bound, index) => {
        if (index <= 10) return { ...bound, lower: 1, start: 2, upper: 3 };
        const branch = index - 11;
        const lower = 10 ** (branch - 3);
        return { ...bound, lower, start: lower * 2, upper: lower * 4 };
      }),
    };
    draft.availability = {
      ramp: "NOT_PROVIDED",
      sweep: "NOT_PROVIDED",
      preconditioning: "NOT_PROVIDED",
      linear_range: "NOT_PROVIDED",
    };
    draft.weights = {
      relaxation_weight: "1",
      dma_storage_weight: "0.5",
      dma_loss_weight: "0.5",
      relaxation_scale_pa: "1",
      dma_storage_scale_pa: "1",
      dma_loss_scale_pa: "1",
      q_rule_version: "equal_per_point@1.0.0",
    };
    draft.optimizer = { ftol: "1e-8", xtol: "1e-8", gtol: "1e-8", max_nfev: "1000" };
    draft.setupName = "Ten-term verification setup";
    draft.changeReason = "Evaluate the supported 10-term contract with sufficient values.";

    const request = buildPolymerCalibrationPlanRequest(draft, denseSource, governance);

    expect(request?.term_counts).toEqual([10]);
    expect(request).not.toBeNull();
    if (!request) throw new Error("Expected a valid ten-term request");
    expect(request.parameter_bounds?.["10"]).toHaveLength(21);
    expect(request.start_vectors?.["10"]?.[0]).toHaveLength(21);
  });

});
