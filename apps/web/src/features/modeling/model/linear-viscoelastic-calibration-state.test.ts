import { describe, expect, it } from "vitest";

import {
  INITIAL_LINEAR_VISCOELASTIC_CALIBRATION_STATE,
  reduceLinearViscoelasticCalibration,
} from "./linear-viscoelastic-calibration-state";
import type {
  LinearViscoelasticCandidate,
  LinearViscoelasticPlanResponse,
  LinearViscoelasticResponseResidualEvidence,
  LinearViscoelasticRunResponse,
  LinearViscoelasticSelectionResponse,
} from "./linear-viscoelastic-calibration-contracts";
import type { LinearViscoelasticModelResponse } from "./modeling-resource-contracts";

const plan = {
  plan_id: "37700000-0000-4000-8000-000000000001",
  current_revision: {
    id: "37700000-0000-4000-8000-000000000002",
    content_hash: "a".repeat(64),
    content: { input_semantics: { source_kind: "test_data" } },
  },
  links: {},
} as LinearViscoelasticPlanResponse;

const run = {
  run_id: "37700000-0000-4000-8000-000000000003",
  plan_revision_id: plan.current_revision.id,
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
  candidate_id: "37700000-0000-4000-8000-000000000004",
  candidate_sha256: "c".repeat(64),
  attempt_ordinal: 1,
  term_count: 1,
  physical_parameters: [1, 2, 0.1],
  transformed_parameters: [0, 0.69, -2.3],
  rss: 1,
  bic: 2,
  calibration_residuals: [1, -1],
  holdout_residuals: [2],
  rank: {},
  warnings: [],
  uncertainty_status: "NOT_PROVIDED",
} as LinearViscoelasticCandidate;

const responseEvidence = {
  run_id: run.run_id,
  plan_revision_id: plan.current_revision.id,
  recommendation: {
    recommendation_id: "37700000-0000-4000-8000-000000000008",
    candidate_id: candidate.candidate_id,
    candidate_sha256: candidate.candidate_sha256,
    rule_version: "linear_viscoelastic_bic@1.0.0",
  },
  artifact: {
    artifact_id: "37700000-0000-4000-8000-000000000009",
    sha256: "d".repeat(64),
    artifact_role: "response-residuals",
    schema_ref: "urn:cmp:modeling:linear-viscoelastic-calibration-response-residuals:1.0.0",
    media_type: "application/vnd.apache.parquet",
    size_bytes: 512,
  },
  rows: [{
    ordinal: 0,
    channel: "relaxation",
    observed: 3,
    predicted: 2.9,
    residual: 0.1,
    partition: "CALIBRATION",
  }],
} as LinearViscoelasticResponseResidualEvidence;

const selection = {
  selection_id: "37700000-0000-4000-8000-000000000005",
  selection_revision_id: "37700000-0000-4000-8000-000000000006",
  plan_revision_id: plan.current_revision.id,
  run_id: run.run_id,
  candidate_id: candidate.candidate_id,
  candidate_sha256: candidate.candidate_sha256,
  reason: "Engineer selected the lower holdout residual.",
  warning_acknowledgements: [],
  actor: "37700000-0000-4000-8000-000000000007",
  created_at: "2026-08-31T00:00:00Z",
} as LinearViscoelasticSelectionResponse;

const selectedModel = {
  material_model_id: "37700000-0000-4000-8000-000000000010",
  material_state_id: "37700000-0000-4000-8000-000000000011",
  current_revision: {
    id: "37700000-0000-4000-8000-000000000012",
    revision_no: 1,
    content: { calibration_promotion_evidence: { selection: { id: selection.selection_id, revision_id: selection.selection_revision_id } } },
  },
  links: {},
} as LinearViscoelasticModelResponse;

describe("linear-viscoelastic calibration state", () => {
  it("keeps Recommendation, Selection, and stale evidence distinct", () => {
    let state = reduceLinearViscoelasticCalibration(INITIAL_LINEAR_VISCOELASTIC_CALIBRATION_STATE, { type: "PLAN_READY", plan });
    state = reduceLinearViscoelasticCalibration(state, { type: "RUN_ACCEPTED", run });
    state = reduceLinearViscoelasticCalibration(state, {
      type: "RUN_SUCCEEDED",
      run,
      candidates: [candidate],
      recommendation: {
        recommendation_id: "37700000-0000-4000-8000-000000000008",
        candidate_id: candidate.candidate_id,
        candidate_digest: candidate.candidate_sha256,
        rule_version: "lowest_bic_then_term_count_then_attempt_ordinal@1.0.0",
      },
      responseEvidence,
    });

    expect(state.phase).toBe("succeeded");
    expect(state.recommendation?.candidate_id).toBe(candidate.candidate_id);
    expect(state.selection).toBeNull();
    expect(state.responseEvidence).toBe(responseEvidence);

    state = reduceLinearViscoelasticCalibration(state, { type: "SELECT_CANDIDATE", candidateId: candidate.candidate_id });
    state = reduceLinearViscoelasticCalibration(state, { type: "SET_REASON", reason: selection.reason });
    state = reduceLinearViscoelasticCalibration(state, { type: "SELECTION_RECORDED", selection });
    expect(state.phase).toBe("selection-saved");
    expect(state.selection?.candidate_sha256).toBe(candidate.candidate_sha256);
    expect(state.selectedModel).toBeNull();
    state = reduceLinearViscoelasticCalibration(state, { type: "MODEL_SAVED", model: selectedModel });
    expect(state.phase).toBe("saved");
    expect(state.selectedModel?.current_revision.id).toBe(selectedModel.current_revision.id);

    const stale = reduceLinearViscoelasticCalibration(state, { type: "STALE", error: "The source revision changed." });
    expect(stale.phase).toBe("stale");
    expect(stale.plan).toBe(plan);
    expect(stale.run).toBe(run);
    expect(stale.candidates).toEqual([candidate]);
    expect(stale.responseEvidence).toBe(responseEvidence);
    expect(stale.selection).toBe(selection);
    expect(stale.selectedModel).toBe(selectedModel);
  });
});
