import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as calibrationApi from "../api/linear-viscoelastic-calibration-api";
import type {
  LinearViscoelasticCandidate,
  LinearViscoelasticPlanContextMatch,
  LinearViscoelasticPlanResponse,
  LinearViscoelasticResponseResidualEvidence,
  LinearViscoelasticRunResponse,
  LinearViscoelasticSelectionResponse,
} from "../model/linear-viscoelastic-calibration-contracts";
import type { LinearViscoelasticModelResponse } from "../model/modeling-resource-contracts";
import type { ModelingSessionRecordRef } from "../model/session-controller";
import {
  useLinearViscoelasticCalibration,
  type UseLinearViscoelasticCalibrationOptions,
} from "./use-linear-viscoelastic-calibration";

vi.mock("../api/linear-viscoelastic-calibration-api", () => ({
  createLinearViscoelasticPlan: vi.fn(),
  createLinearViscoelasticSelection: vi.fn(),
  createProcessedLinearViscoelasticPlan: vi.fn(),
  getLinearViscoelasticPlan: vi.fn(),
  getLinearViscoelasticRecommendation: vi.fn(),
  getLinearViscoelasticResponseResiduals: vi.fn(),
  getLinearViscoelasticRun: vi.fn(),
  getLinearViscoelasticSelection: vi.fn(),
  getLinearViscoelasticSelectedModel: vi.fn(),
  listLinearViscoelasticCandidates: vi.fn(),
  promoteLinearViscoelasticSelection: vi.fn(),
  queueLinearViscoelasticRun: vi.fn(),
}));

const config = { baseUrl: "/api/v1", accessToken: "token" };
const sourceId = "37700000-0000-4000-8000-000000000011";
const sourceRevisionId = "37700000-0000-4000-8000-000000000012";
const planId = "37700000-0000-4000-8000-000000000021";
const planRevisionId = "37700000-0000-4000-8000-000000000022";
const runId = "37700000-0000-4000-8000-000000000031";
const candidateId = "37700000-0000-4000-8000-000000000041";
const materialId = "37700000-0000-4000-8000-000000000101";
const materialRevisionId = "37700000-0000-4000-8000-000000000102";
const materialStateId = "37700000-0000-4000-8000-000000000103";
const materialStateRevisionId = "37700000-0000-4000-8000-000000000104";
const propertySetId = "37700000-0000-4000-8000-000000000105";
const propertySetRevisionId = "37700000-0000-4000-8000-000000000106";
const sourceDocument = {
  channels: [
    { key: "time", quantity_semantics: "time.elapsed", normalized_unit: "s", normalized_values: [0.1, 1, 10, 100] },
    { key: "modulus", quantity_semantics: "modulus.shear.relaxation", normalized_unit: "Pa", normalized_values: [3_000_000, 2_000_000, 1_000_000, 800_000] },
  ],
  conditions: [{ quantity_semantics: "physics.temperature", normalized_unit: "K", normalized_value: 298.15 }],
};
const plan = {
  plan_id: planId,
  current_revision: {
    id: planRevisionId,
    content_hash: "a".repeat(64),
    change_reason: "Create the exact reviewed calibration Plan.",
    content: {
      setup_name: "Approved relaxation setup",
      material: { id: materialId, revision_id: materialRevisionId },
      material_state: { id: materialStateId, revision_id: materialStateRevisionId },
      input_mode: "relaxation",
      test_data: { id: sourceId, revision_id: sourceRevisionId },
      input_semantics: {
        mode: "relaxation",
        source_kind: "test_data",
        selected_temperature_k: "298.15",
        point_dispositions: [
          { ordinal: 0, partition: "CALIBRATION", exclusion_reason: null },
          { ordinal: 1, partition: "CALIBRATION", exclusion_reason: null },
          { ordinal: 2, partition: "CALIBRATION", exclusion_reason: null },
          { ordinal: 3, partition: "HOLDOUT", exclusion_reason: null },
        ],
      },
      term_counts: [1],
      parameter_bounds: {
        "1": [
          { name: "G_inf_pa", lower: "100000", start: "900000", upper: "5000000", unit: "Pa", transform: "ln" },
          { name: "G_1_pa", lower: "100000", start: "1800000", upper: "5000000", unit: "Pa", transform: "ln" },
          { name: "tau_1_s", lower: "0.01", start: "0.4", upper: "1", unit: "s", transform: "ln" },
        ],
      },
      weights: {
        relaxation_weight: "1",
        dma_storage_weight: "0.5",
        dma_loss_weight: "0.5",
        relaxation_scale_pa: "3000000",
        dma_storage_scale_pa: "1",
        dma_loss_scale_pa: "1",
        q_rule_version: "equal_per_point@1.0.0",
      },
      optimizer: { method: "trf", x_scale: "jac", transform: "ln", ftol: 1e-8, xtol: 1e-8, gtol: 1e-8, max_nfev: 1000 },
      statuses: { ramp: "NOT_PROVIDED", sweep: "NOT_PROVIDED", preconditioning: "NOT_PROVIDED", linear_range: "NOT_PROVIDED" },
    },
  },
  links: {},
} as unknown as LinearViscoelasticPlanResponse;
const approvedSetup = {
  plan_id: planId,
  plan_revision_id: planRevisionId,
  plan_sha256: "a".repeat(64),
  setup_name: "Approved relaxation setup",
  input_mode: "relaxation",
  material: { id: materialId, revision_id: materialRevisionId },
  material_state: { id: materialStateId, revision_id: materialStateRevisionId },
  test_data: { id: sourceId, revision_id: sourceRevisionId },
  processing_output: null,
  approval: {
    plan_id: planId,
    plan_revision_id: planRevisionId,
    plan_sha256: "a".repeat(64),
    setup_name: "Approved relaxation setup",
    input_mode: "relaxation",
    material: { id: materialId, revision_id: materialRevisionId },
    material_state: { id: materialStateId, revision_id: materialStateRevisionId },
    test_data: { id: sourceId, revision_id: sourceRevisionId },
    processing_output: null,
    state: "active",
    review_request_id: "37700000-0000-4000-8000-000000000023",
    review_decision_id: "37700000-0000-4000-8000-000000000024",
    evidence_sha256: "d".repeat(64),
    approved_at: "2026-09-01T00:00:00Z",
    approved_by: "37700000-0000-4000-8000-000000000025",
    superseded_by_plan_id: null,
    superseded_by_plan_revision_id: null,
  },
} as LinearViscoelasticPlanContextMatch;
const run = {
  run_id: runId,
  plan_revision_id: planRevisionId,
  status: "succeeded",
  attempts: [],
  candidates: [],
  recommendation: null,
  failure_code: null,
  failure_detail: null,
  recovery_hint: null,
  execution_ledger_sha256: "b".repeat(64),
} as LinearViscoelasticRunResponse;
const candidate = {
  candidate_id: candidateId,
  candidate_sha256: "c".repeat(64),
  attempt_ordinal: 1,
  term_count: 1,
  physical_parameters: [1_000_000, 2_000_000, 0.1],
  transformed_parameters: [13.8, 14.5, -2.3],
  rss: 1,
  bic: 2,
  calibration_residuals: [0.1, -0.1],
  holdout_residuals: [0.2],
  rank: { rank: 3, status: "FULL_RANK" },
  warnings: [],
  uncertainty_status: "NOT_PROVIDED",
} as LinearViscoelasticCandidate;
const recommendation = {
  recommendation_id: "37700000-0000-4000-8000-000000000051",
  candidate_id: candidateId,
  candidate_digest: candidate.candidate_sha256,
  rule_version: "linear_viscoelastic_bic@1.0.0",
};
const responseEvidence = {
  run_id: runId,
  plan_revision_id: planRevisionId,
  recommendation: {
    recommendation_id: recommendation.recommendation_id,
    candidate_id: candidateId,
    candidate_sha256: candidate.candidate_sha256,
    rule_version: "linear_viscoelastic_bic@1.0.0",
  },
  artifact: {
    artifact_id: "37700000-0000-4000-8000-000000000052",
    sha256: "d".repeat(64),
    artifact_role: "response-residuals",
    schema_ref: "urn:cmp:modeling:linear-viscoelastic-calibration-response-residuals:1.0.0",
    media_type: "application/vnd.apache.parquet",
    size_bytes: 512,
  },
  rows: [
    { ordinal: 0, channel: "relaxation", observed: 3_000_000, predicted: 2_900_000, residual: 100_000, partition: "CALIBRATION" },
    { ordinal: 1, channel: "relaxation", observed: 2_000_000, predicted: 2_050_000, residual: -50_000, partition: "CALIBRATION" },
    { ordinal: 2, channel: "relaxation", observed: 1_000_000, predicted: 1_050_000, residual: -50_000, partition: "CALIBRATION" },
    { ordinal: 3, channel: "relaxation", observed: 800_000, predicted: 900_000, residual: -100_000, partition: "HOLDOUT" },
  ],
} as LinearViscoelasticResponseResidualEvidence;
const selection = {
  selection_id: "37700000-0000-4000-8000-000000000061",
  selection_revision_id: "37700000-0000-4000-8000-000000000062",
  plan_revision_id: planRevisionId,
  run_id: runId,
  candidate_id: candidateId,
  candidate_sha256: candidate.candidate_sha256,
  reason: "Use the lowest BIC with reviewed holdout residuals.",
  warning_acknowledgements: [],
  actor: "37700000-0000-4000-8000-000000000071",
  created_at: "2026-08-31T00:00:00Z",
} as LinearViscoelasticSelectionResponse;
const selectedModel = {
  material_model_id: "37700000-0000-4000-8000-000000000107",
  material_state_id: materialStateId,
  current_revision: {
    id: "37700000-0000-4000-8000-000000000108",
    revision_no: 1,
    content_hash: "e".repeat(64),
    classification: "internal",
    lifecycle_state: "draft",
    content: {
      material_id: materialId,
      material_revision_id: materialRevisionId,
      material_state_id: materialStateId,
      material_state_revision_id: materialStateRevisionId,
      property_set_id: propertySetId,
      property_set_revision_id: propertySetRevisionId,
      calibration_promotion_evidence: {
        plan: { id: planId, revision_id: planRevisionId, sha256: "a".repeat(64) },
        run: { id: runId, sha256: "b".repeat(64) },
        candidate: { id: candidateId, sha256: candidate.candidate_sha256 },
        selection: { id: selection.selection_id, revision_id: selection.selection_revision_id, sha256: "f".repeat(64) },
      },
    },
  },
  links: {},
} as LinearViscoelasticModelResponse;
const initialSelection = {
  id: selection.selection_id,
  revisionId: selection.selection_revision_id,
  revisionNo: 1,
  label: "Saved polymer model choice",
  calibrationPlanId: planId,
  calibrationRunId: runId,
  calibrationCandidateId: candidateId,
} as ModelingSessionRecordRef;
const initialSelectedModel = {
  id: selectedModel.material_model_id,
  revisionId: selectedModel.current_revision.id,
  revisionNo: 1,
  label: "Saved polymer model",
} as ModelingSessionRecordRef;

function result<T>(data: T) {
  return { data, response: new Response() } as never;
}

function options(overrides: Partial<UseLinearViscoelasticCalibrationOptions> = {}): UseLinearViscoelasticCalibrationOptions {
  return {
    config,
    sourceDocument,
    directSource: { id: sourceId, revisionId: sourceRevisionId },
    directAvailable: true,
    processedAvailable: false,
    catalogContext: {
      material: { id: materialId, revisionId: materialRevisionId },
      materialState: { id: materialStateId, revisionId: materialStateRevisionId },
      propertySet: { id: propertySetId, revisionId: propertySetRevisionId },
    },
    ...overrides,
  };
}

function completeExplicitPlanInputs(
  actions: ReturnType<typeof useLinearViscoelasticCalibration>["actions"],
): void {
  actions.markAllCalibration();
  for (const field of ["ramp", "sweep", "preconditioning", "linear_range"] as const) {
    actions.setAvailability(field, "NOT_PROVIDED");
  }
  actions.toggleTerm(1);
  const values = [
    [100_000, 900_000, 5_000_000],
    [100_000, 1_800_000, 5_000_000],
    [0.01, 0.4, 1],
  ];
  values.forEach((bound, index) => {
    (["lower", "start", "upper"] as const).forEach((key, valueIndex) => {
      actions.updateBound(1, index, key, String(bound[valueIndex]));
    });
  });
  const weights = {
    relaxation_weight: "1",
    dma_storage_weight: "0.5",
    dma_loss_weight: "0.5",
    relaxation_scale_pa: "3000000",
    dma_storage_scale_pa: "1",
    dma_loss_scale_pa: "1",
  } as const;
  for (const [key, value] of Object.entries(weights)) {
    actions.setWeight(key as keyof typeof weights, value);
  }
  actions.setOptimizer("ftol", "1e-8");
  actions.setOptimizer("xtol", "1e-8");
  actions.setOptimizer("gtol", "1e-8");
  actions.setOptimizer("max_nfev", "1000");
  actions.setSetupName("Approved relaxation setup");
  actions.setChangeReason("Create the exact reviewed calibration Plan.");
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("useLinearViscoelasticCalibration", () => {
  it("reloads a saved model only when its Selection, Plan, source, and catalog revisions match", async () => {
    vi.mocked(calibrationApi.getLinearViscoelasticSelection).mockResolvedValue(result(selection));
    vi.mocked(calibrationApi.getLinearViscoelasticPlan).mockResolvedValue(result(plan));
    vi.mocked(calibrationApi.getLinearViscoelasticRun).mockResolvedValue(result(run));
    vi.mocked(calibrationApi.listLinearViscoelasticCandidates).mockResolvedValue(result([candidate]));
    vi.mocked(calibrationApi.getLinearViscoelasticRecommendation).mockResolvedValue(result(recommendation));
    vi.mocked(calibrationApi.getLinearViscoelasticResponseResiduals).mockResolvedValue(result(responseEvidence));
    vi.mocked(calibrationApi.getLinearViscoelasticSelectedModel).mockResolvedValue(result(selectedModel));

    const { result: hook } = renderHook(() => useLinearViscoelasticCalibration(options({ initialSelection, initialSelectedModel })));

    await waitFor(() => expect(hook.current.state.phase).toBe("saved"));
    expect(hook.current.state.plan?.current_revision.id).toBe(planRevisionId);
    expect(hook.current.state.selection?.selection_revision_id).toBe(selection.selection_revision_id);
    expect(hook.current.state.selectedModel?.current_revision.id).toBe(selectedModel.current_revision.id);
    expect(hook.current.selectedCandidate?.candidate_sha256).toBe(candidate.candidate_sha256);
    expect(hook.current.state.responseEvidence?.artifact.sha256).toBe(responseEvidence.artifact.sha256);
    expect(hook.current.draft.bounds["1"][2].start).toBe(0.4);
    expect(hook.current.draft.partitions).toEqual(["CALIBRATION", "CALIBRATION", "CALIBRATION", "HOLDOUT"]);
    expect(hook.current.requestReady).toBe(true);
  });

  it("waits for delayed exact source hydration before reloading a saved Selection", async () => {
    vi.mocked(calibrationApi.getLinearViscoelasticSelection).mockResolvedValue(result(selection));
    vi.mocked(calibrationApi.getLinearViscoelasticPlan).mockResolvedValue(result(plan));
    vi.mocked(calibrationApi.getLinearViscoelasticRun).mockResolvedValue(result(run));
    vi.mocked(calibrationApi.listLinearViscoelasticCandidates).mockResolvedValue(result([candidate]));
    vi.mocked(calibrationApi.getLinearViscoelasticRecommendation).mockResolvedValue(result(recommendation));
    vi.mocked(calibrationApi.getLinearViscoelasticResponseResiduals).mockResolvedValue(result(responseEvidence));
    vi.mocked(calibrationApi.getLinearViscoelasticSelectedModel).mockResolvedValue(result(selectedModel));
    const initial = options({
      initialSelection,
      initialSelectedModel,
      sourceDocument: null,
      directSource: undefined,
      directAvailable: false,
    });
    const { result: hook, rerender } = renderHook(
      ({ value }: { value: UseLinearViscoelasticCalibrationOptions }) => useLinearViscoelasticCalibration(value),
      { initialProps: { value: initial } },
    );

    await act(async () => Promise.resolve());
    expect(calibrationApi.getLinearViscoelasticSelection).not.toHaveBeenCalled();

    rerender({
      value: options({
        initialSelection,
        initialSelectedModel,
        sourceDocument: null,
        directAvailable: false,
      }),
    });
    await act(async () => Promise.resolve());
    expect(calibrationApi.getLinearViscoelasticSelection).not.toHaveBeenCalled();

    rerender({ value: options({ initialSelection, initialSelectedModel }) });
    await waitFor(() => expect(hook.current.state.phase).toBe("saved"));
    expect(hook.current.state.selection?.selection_id).toBe(selection.selection_id);
    expect(hook.current.draft.partitions).toEqual(["CALIBRATION", "CALIBRATION", "CALIBRATION", "HOLDOUT"]);
    expect(hook.current.blockers.direct).toEqual([]);
    expect(hook.current.requestReady).toBe(true);

    rerender({
      value: options({
        initialSelection,
        initialSelectedModel,
        sourceDocument: {
          ...sourceDocument,
          channels: sourceDocument.channels.map((channel) => ({ ...channel })),
        },
      }),
    });

    await waitFor(() => expect(hook.current.state.phase).toBe("saved"));
    expect(hook.current.draft.partitions).toEqual(["CALIBRATION", "CALIBRATION", "CALIBRATION", "HOLDOUT"]);
    expect(hook.current.blockers.direct).toEqual([]);
    expect(hook.current.requestReady).toBe(true);
  });

  it("retries the same saved Selection reload after a transient read failure", async () => {
    vi.mocked(calibrationApi.getLinearViscoelasticSelection)
      .mockRejectedValueOnce(new Error("temporary read failure"))
      .mockResolvedValue(result(selection));
    vi.mocked(calibrationApi.getLinearViscoelasticPlan).mockResolvedValue(result(plan));
    vi.mocked(calibrationApi.getLinearViscoelasticRun).mockResolvedValue(result(run));
    vi.mocked(calibrationApi.listLinearViscoelasticCandidates).mockResolvedValue(result([candidate]));
    vi.mocked(calibrationApi.getLinearViscoelasticRecommendation).mockResolvedValue(result(recommendation));
    vi.mocked(calibrationApi.getLinearViscoelasticResponseResiduals).mockResolvedValue(result(responseEvidence));
    vi.mocked(calibrationApi.getLinearViscoelasticSelectedModel).mockResolvedValue(result(selectedModel));
    const { result: hook } = renderHook(() => useLinearViscoelasticCalibration(options({ initialSelection, initialSelectedModel })));

    await waitFor(() => expect(hook.current.state.phase).toBe("error"));
    expect(hook.current.state.recoveryHint).toContain("matching Test Data");
    act(() => hook.current.actions.retryAfterError());

    await waitFor(() => expect(hook.current.state.phase).toBe("saved"));
    expect(calibrationApi.getLinearViscoelasticSelection).toHaveBeenCalledTimes(2);
    expect(hook.current.state.selection?.selection_revision_id).toBe(selection.selection_revision_id);
  });

  it("preserves immutable evidence and becomes stale when the loaded source revision changes", async () => {
    vi.mocked(calibrationApi.createLinearViscoelasticPlan).mockResolvedValue(result(plan));
    const initial = options();
    const { result: hook, rerender } = renderHook(
      ({ value }: { value: UseLinearViscoelasticCalibrationOptions }) => useLinearViscoelasticCalibration(value),
      { initialProps: { value: initial } },
    );
    act(() => {
      completeExplicitPlanInputs(hook.current.actions);
    });
    await waitFor(() => expect(hook.current.requestReady).toBe(true));
    await act(async () => hook.current.actions.createPlan());
    await waitFor(() => expect(hook.current.state.phase).toBe("plan-ready"));

    rerender({
      value: options({
        directSource: { id: sourceId, revisionId: "37700000-0000-4000-8000-000000000099" },
      }),
    });

    await waitFor(() => expect(hook.current.state.phase).toBe("stale"));
    expect(hook.current.state.plan?.current_revision.id).toBe(planRevisionId);
    expect(hook.current.state.error).toContain("exact upstream source changed");
  });

  it("creates an Advanced setup as a new reviewed clone of the exact approved Plan", async () => {
    vi.mocked(calibrationApi.createLinearViscoelasticPlan).mockResolvedValue(result(plan));
    const { result: hook } = renderHook(() => useLinearViscoelasticCalibration(options()));

    act(() => {
      hook.current.actions.prepareApprovedPlan(plan, approvedSetup);
    });
    await waitFor(() => expect(hook.current.draft.setupName).toBe("Approved relaxation setup"));
    expect(hook.current.requestReady).toBe(false);
    act(() => {
      hook.current.actions.setSetupName("Approved relaxation setup · wider range");
      hook.current.actions.setOverrideReason("Expand the reviewed candidate comparison for this exact input.");
      hook.current.actions.setChangeReason("Create a new setup draft for separated review.");
    });
    await waitFor(() => expect(hook.current.requestReady).toBe(true));
    await act(async () => hook.current.actions.createPlan());

    expect(calibrationApi.createLinearViscoelasticPlan).toHaveBeenCalledWith(config, expect.objectContaining({
      setup_name: "Approved relaxation setup · wider range",
      material: { id: materialId, revision_id: materialRevisionId },
      material_state: { id: materialStateId, revision_id: materialStateRevisionId },
      input_mode: "relaxation",
      based_on_plan_id: planId,
      based_on_plan_revision_id: planRevisionId,
      override_reason: "Expand the reviewed candidate comparison for this exact input.",
    }));
  });

  it("creates a governed setup for an exact processed DMA input even when the original sweep is not a direct Fit mode", async () => {
    vi.mocked(calibrationApi.createProcessedLinearViscoelasticPlan).mockResolvedValue(result(plan));
    const processingOutputId = "37700000-0000-4000-8000-000000000071";
    const processingOutputRevisionId = "37700000-0000-4000-8000-000000000072";
    const { result: hook } = renderHook(() => useLinearViscoelasticCalibration(options({
      sourceDocument: null,
      directAvailable: false,
      processingSource: { id: processingOutputId, revisionId: processingOutputRevisionId },
      processedAvailable: true,
      processedCalibrationObservationCount: 42,
    })));

    act(() => {
      hook.current.actions.chooseSource("processing-output");
      completeExplicitPlanInputs(hook.current.actions);
    });
    await waitFor(() => expect(hook.current.requestReady).toBe(true));
    await act(async () => hook.current.actions.createPlan());

    expect(calibrationApi.createProcessedLinearViscoelasticPlan).toHaveBeenCalledWith(config, expect.objectContaining({
      processing_output: { id: processingOutputId, revision_id: processingOutputRevisionId },
      material: { id: materialId, revision_id: materialRevisionId },
      material_state: { id: materialStateId, revision_id: materialStateRevisionId },
      input_mode: "dma_frequency_master_curve",
      candidate_scope_mode: "manual",
      term_counts: [1],
    }));
  });

  it("polls the exact Run and retries model promotion without creating a second Selection", async () => {
    vi.mocked(calibrationApi.queueLinearViscoelasticRun).mockResolvedValue(result({
      run_id: runId,
      job_id: "37700000-0000-4000-8000-000000000081",
      run_url: `/api/v1/linear-viscoelastic-calibration-runs/${runId}`,
      job_url: "/api/v1/jobs/37700000-0000-4000-8000-000000000081",
      status: "queued",
    }));
    vi.mocked(calibrationApi.getLinearViscoelasticRun).mockResolvedValue(result(run));
    vi.mocked(calibrationApi.listLinearViscoelasticCandidates).mockResolvedValue(result([candidate]));
    vi.mocked(calibrationApi.getLinearViscoelasticRecommendation).mockResolvedValue(result(recommendation));
    vi.mocked(calibrationApi.getLinearViscoelasticResponseResiduals).mockResolvedValue(result(responseEvidence));
    vi.mocked(calibrationApi.createLinearViscoelasticSelection).mockResolvedValue(result(selection));
    vi.mocked(calibrationApi.promoteLinearViscoelasticSelection)
      .mockRejectedValueOnce(new Error("temporary model save failure"))
      .mockResolvedValue(result(selectedModel));
    vi.mocked(calibrationApi.getLinearViscoelasticSelectedModel).mockResolvedValue(result(selectedModel));
    const onSelectionSaved = vi.fn();
    const onSelectedModelSaved = vi.fn();
    const { result: hook } = renderHook(() => useLinearViscoelasticCalibration(options({ onSelectionSaved, onSelectedModelSaved })));
    act(() => {
      completeExplicitPlanInputs(hook.current.actions);
    });
    await waitFor(() => expect(hook.current.requestReady).toBe(true));
    await act(async () => hook.current.actions.runApprovedPlan(plan, approvedSetup));
    await waitFor(() => expect(hook.current.state.phase).toBe("succeeded"));
    act(() => {
      hook.current.actions.selectCandidate(candidateId);
      hook.current.actions.setSelectionReason(selection.reason);
    });

    let saved = true;
    await act(async () => {
      saved = await hook.current.actions.saveFit();
    });
    expect(saved).toBe(false);
    expect(hook.current.state.phase).toBe("error");
    expect(hook.current.state.selection?.selection_id).toBe(selection.selection_id);
    await act(async () => {
      saved = await hook.current.actions.saveFit();
    });
    expect(saved).toBe(true);

    expect(calibrationApi.queueLinearViscoelasticRun).toHaveBeenCalledWith(
      config,
      planId,
      expect.objectContaining({ plan_revision_id: planRevisionId }),
    );
    expect(calibrationApi.createLinearViscoelasticPlan).not.toHaveBeenCalled();
    expect(calibrationApi.createLinearViscoelasticSelection).toHaveBeenCalledWith(
      config,
      expect.objectContaining({
        plan_revision_id: planRevisionId,
        run_id: runId,
        candidate_id: candidateId,
        candidate_sha256: candidate.candidate_sha256,
        reason: selection.reason,
      }),
    );
    expect(calibrationApi.createLinearViscoelasticSelection).toHaveBeenCalledTimes(1);
    expect(hook.current.state.phase).toBe("saved");
    expect(onSelectionSaved).toHaveBeenCalledWith(expect.objectContaining({
      id: selection.selection_id,
      revisionId: selection.selection_revision_id,
      calibrationPlanId: planId,
      calibrationRunId: runId,
      calibrationCandidateId: candidateId,
    }));
    expect(calibrationApi.promoteLinearViscoelasticSelection).toHaveBeenCalledWith(
      config,
      selection.selection_id,
      expect.objectContaining({
        material: { id: materialId, revision_id: materialRevisionId },
        material_state: { id: materialStateId, revision_id: materialStateRevisionId },
        property_set: { id: propertySetId, revision_id: propertySetRevisionId },
      }),
    );
    expect(calibrationApi.promoteLinearViscoelasticSelection).toHaveBeenCalledTimes(2);
    expect(onSelectedModelSaved).toHaveBeenCalledWith(expect.objectContaining({
      id: selectedModel.material_model_id,
      revisionId: selectedModel.current_revision.id,
    }));
  });
});
