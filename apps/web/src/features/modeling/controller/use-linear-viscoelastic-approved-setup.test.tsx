import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as calibrationApi from "../api/linear-viscoelastic-calibration-api";
import type {
  LinearViscoelasticPlanContextMatch,
  LinearViscoelasticPlanContextRequest,
  LinearViscoelasticPlanResponse,
} from "../model/linear-viscoelastic-calibration-contracts";
import { useLinearViscoelasticApprovedSetup } from "./use-linear-viscoelastic-approved-setup";

vi.mock("../api/linear-viscoelastic-calibration-api", () => ({
  getLinearViscoelasticPlan: vi.fn(),
  resolveLinearViscoelasticPlanContext: vi.fn(),
}));

const config = { baseUrl: "/api/v1", accessToken: "token" };
const context: LinearViscoelasticPlanContextRequest = {
  material: { id: "37700000-0000-4000-8000-000000000001", revision_id: "37700000-0000-4000-8000-000000000002" },
  material_state: { id: "37700000-0000-4000-8000-000000000003", revision_id: "37700000-0000-4000-8000-000000000004" },
  test_data: { id: "37700000-0000-4000-8000-000000000005", revision_id: "37700000-0000-4000-8000-000000000006" },
  input_mode: "relaxation",
};

function match(ordinal: number): LinearViscoelasticPlanContextMatch {
  const planId = `37700000-0000-4000-8000-${String(ordinal).padStart(12, "0")}`;
  const revisionId = `37700000-0000-4000-9000-${String(ordinal).padStart(12, "0")}`;
  return {
    plan_id: planId,
    plan_revision_id: revisionId,
    plan_sha256: "a".repeat(64),
    setup_name: `Approved setup ${ordinal}`,
    input_mode: "relaxation",
    material: context.material,
    material_state: context.material_state,
    test_data: context.test_data,
    processing_output: null,
    approval: {
      plan_id: planId,
      plan_revision_id: revisionId,
      plan_sha256: "a".repeat(64),
      setup_name: `Approved setup ${ordinal}`,
      input_mode: "relaxation",
      material: context.material,
      material_state: context.material_state,
      test_data: context.test_data,
      processing_output: null,
      state: "active",
      review_request_id: "37700000-0000-4000-a000-000000000001",
      review_decision_id: "37700000-0000-4000-a000-000000000002",
      evidence_sha256: "b".repeat(64),
      approved_at: "2026-09-01T00:00:00Z",
      approved_by: "37700000-0000-4000-a000-000000000003",
      superseded_by_plan_id: null,
      superseded_by_plan_revision_id: null,
    },
  };
}

function plan(value: LinearViscoelasticPlanContextMatch): LinearViscoelasticPlanResponse {
  return {
    plan_id: value.plan_id,
    current_revision: {
      id: value.plan_revision_id,
      content_hash: value.plan_sha256,
      content: { setup_name: value.setup_name },
    },
    links: {},
  } as unknown as LinearViscoelasticPlanResponse;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("useLinearViscoelasticApprovedSetup", () => {
  it("reports no approved setup without inventing a fallback", async () => {
    vi.mocked(calibrationApi.resolveLinearViscoelasticPlanContext).mockResolvedValue({
      data: { summary: "0 setups", selection_required: true, matches: [] },
    } as never);
    const hook = renderHook(() => useLinearViscoelasticApprovedSetup(config, context));
    await waitFor(() => expect(hook.result.current.status).toBe("missing"));
    expect(calibrationApi.getLinearViscoelasticPlan).not.toHaveBeenCalled();
  });

  it("loads the only exact active approved setup", async () => {
    const approved = match(1);
    vi.mocked(calibrationApi.resolveLinearViscoelasticPlanContext).mockResolvedValue({
      data: { summary: "1 setup", selection_required: false, matches: [approved] },
    } as never);
    vi.mocked(calibrationApi.getLinearViscoelasticPlan).mockResolvedValue({ data: plan(approved) } as never);
    const hook = renderHook(() => useLinearViscoelasticApprovedSetup(config, context));
    await waitFor(() => expect(hook.result.current.status).toBe("ready"));
    expect(hook.result.current.selected?.setup_name).toBe("Approved setup 1");
    expect(calibrationApi.getLinearViscoelasticPlan).toHaveBeenCalledWith(config, approved.plan_id);
  });

  it("requires an explicit choice when several exact approved setups match", async () => {
    const first = match(1);
    const second = match(2);
    vi.mocked(calibrationApi.resolveLinearViscoelasticPlanContext).mockResolvedValue({
      data: { summary: "2 setups", selection_required: true, matches: [first, second] },
    } as never);
    vi.mocked(calibrationApi.getLinearViscoelasticPlan).mockImplementation(async (_config, planId) => ({
      data: plan(planId === first.plan_id ? first : second),
    }) as never);
    const hook = renderHook(() => useLinearViscoelasticApprovedSetup(config, context));
    await waitFor(() => expect(hook.result.current.status).toBe("multiple"));
    expect(calibrationApi.getLinearViscoelasticPlan).not.toHaveBeenCalled();
    act(() => hook.result.current.choose(second.plan_revision_id));
    await waitFor(() => expect(hook.result.current.status).toBe("ready"));
    expect(hook.result.current.selected?.plan_revision_id).toBe(second.plan_revision_id);
  });
});
