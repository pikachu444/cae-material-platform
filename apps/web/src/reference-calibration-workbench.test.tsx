import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReferenceCalibrationWorkbench } from "./reference-calibration-workbench";
import type { MaterialStateResponse } from "./features/materials/contracts";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

const materialStateId = "80000000-0000-4000-8000-000000000001";
const modelId = "80000000-0000-4000-8000-000000000002";
const modelRevisionId = "80000000-0000-4000-8000-000000000003";
const datasetId = "80000000-0000-4000-8000-000000000004";
const datasetRevisionId = "80000000-0000-4000-8000-000000000005";
const selectionId = "80000000-0000-4000-8000-000000000006";
const selectionRevisionId = "80000000-0000-4000-8000-000000000007";
const planId = "80000000-0000-4000-8000-000000000008";
const planRevisionId = "80000000-0000-4000-8000-000000000009";
const runId = "80000000-0000-4000-8000-00000000000a";
const attemptId = "80000000-0000-4000-8000-00000000000b";
const candidateId = "80000000-0000-4000-8000-00000000000c";
const candidateSelectionId = "80000000-0000-4000-8000-000000000016";
const candidateSelectionRevisionId = "80000000-0000-4000-8000-000000000017";
const promotedModelRevisionId = "80000000-0000-4000-8000-000000000018";

const state = {
  material_state_id: materialStateId,
  material_id: "80000000-0000-4000-8000-00000000000d",
  current_revision: {
    id: "80000000-0000-4000-8000-00000000000e",
    aggregate_id: materialStateId,
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:catalog:material-state:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-07-19T00:00:00Z",
    created_by: "80000000-0000-4000-8000-00000000000f",
    change_reason: "demo",
    organization_id: "80000000-0000-4000-8000-000000000010",
    project_id: "80000000-0000-4000-8000-000000000011",
    classification: "internal" as const,
    lifecycle_state: "draft" as const,
    content: {
      material_id: "80000000-0000-4000-8000-00000000000d",
      material_revision_id: "80000000-0000-4000-8000-000000000012",
      name: "As received",
      manufacturing_route: null,
      heat_treatment: null,
      lot_or_batch: null,
      description: null,
    },
    provenance: {
      entity_type: "catalog.material_state.revision",
      reference_type: "catalog.material_state.revision",
      revision_id: "80000000-0000-4000-8000-00000000000e",
      content_sha256: "a".repeat(64),
      based_on_revision_id: null,
      recorded_at: "2026-07-19T00:00:00Z",
      recorded_by: "80000000-0000-4000-8000-00000000000f",
    },
  },
  property_sets_url: "/api/v1/material-states/1/property-sets",
} satisfies MaterialStateResponse;

function fixtureRevision(id: string, aggregateId: string, content: object) {
  return {
    ...state.current_revision,
    id,
    aggregate_id: aggregateId,
    content,
  };
}

describe("Reference calibration workbench", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("pins immutable selection/model revisions, runs calibration, and renders diagnostics", async () => {
    const model = {
      material_model_id: modelId,
      material_state_id: materialStateId,
      current_revision: fixtureRevision(modelRevisionId, modelId, {
        model_family_id: "reference_isotropic_linear_elasticity",
        model_schema_version: "1.0.0",
        model_schema_digest: "b".repeat(64),
        material_state_id: materialStateId,
        non_production: true,
      }),
      links: {},
    };
    const dataset = {
      dataset_id: datasetId,
      test_run_id: "80000000-0000-4000-8000-000000000013",
      current_revision: fixtureRevision(datasetRevisionId, datasetId, {
        representation: "processed",
      }),
      links: {},
    };
    const selection = {
      selection_id: selectionId,
      selection_label: "Processed tensile crop",
      current_revision: fixtureRevision(selectionRevisionId, selectionId, {
        selection_kind: "reference_curve_dataset_revision",
        member_count: 1,
        dataset_id: datasetId,
        dataset_revision_id: datasetRevisionId,
      }),
      links: {},
    };
    const plan = {
      calibration_plan_id: planId,
      current_revision: fixtureRevision(planRevisionId, planId, {
        plan_kind: "reference_uniaxial_linear_elasticity",
      }),
      links: {},
    };
    const candidate = {
      calibration_candidate_id: candidateId,
      calibration_run_id: runId,
      calibration_attempt_id: attemptId,
      attempt_ordinal: 1,
      status: "converged",
      candidate_sha256: `sha256:${"c".repeat(64)}`,
      youngs_modulus_pa: 210_000_000_000,
      objective_total: 0.001,
      residual_root_mean_square_pa: 1234,
      residual_mean_pa: 0,
      bound_sticking: false,
      convergence_reason: "analytic_bounded_solution",
      identifiability_status: "not_assessed_reference_one_parameter",
      uncertainty_status: "not_estimated_reference",
      diagnostics_artifact_id: "80000000-0000-4000-8000-000000000014",
      diagnostics_sha256: "d".repeat(64),
      diagnostics_point_count: 3,
      created_at: "2026-07-19T00:00:00Z",
      created_by: "80000000-0000-4000-8000-00000000000f",
      links: {},
    };
    const run = {
      calibration_run_id: runId,
      classification: "internal",
      calibration_plan_id: planId,
      calibration_plan_revision_id: planRevisionId,
      selection_id: selectionId,
      selection_revision_id: selectionRevisionId,
      dataset_id: datasetId,
      dataset_revision_id: datasetRevisionId,
      material_model_id: modelId,
      material_model_revision_id: modelRevisionId,
      execution_mode: "reference_inline",
      reproducibility_level: "R3",
      environment_digest: `sha256:${"e".repeat(64)}`,
      status: "succeeded",
      attempt_count: 1,
      candidate_count: 1,
      failure_code: null,
      change_reason: "Execute deterministic reference linear elastic calibration",
      started_at: "2026-07-19T00:00:00Z",
      ended_at: "2026-07-19T00:00:01Z",
      created_by: "80000000-0000-4000-8000-00000000000f",
      request_id: "80000000-0000-4000-8000-000000000015",
      trace_id: "00-00000000000000000000000000000080-0000000000000080-01",
      attempts: [{
        calibration_attempt_id: attemptId,
        calibration_run_id: runId,
        attempt_ordinal: 1,
        initial_youngs_modulus_pa: 210_000_000_000,
        random_seed: 20260719,
        status: "succeeded",
        candidate_id: candidateId,
        failure_code: null,
        started_at: "2026-07-19T00:00:00Z",
        ended_at: "2026-07-19T00:00:01Z",
      }],
      candidates: [candidate],
      links: {},
    };
    const candidateSelection = {
      calibration_candidate_selection_id: candidateSelectionId,
      current_revision: fixtureRevision(candidateSelectionRevisionId, candidateSelectionId, {
        selection_label: "Accepted reference elastic candidate",
        calibration_run_id: runId,
        calibration_candidate_id: candidateId,
        candidate_sha256: `sha256:${"c".repeat(64)}`,
        selection_reason: "Human review accepts this converged candidate for a non-production reference IR",
        selection_decision: "accepted_for_reference_ir_promotion",
        domain_acceptance_status: "accepted_by_human_for_reference_ir_promotion",
        non_production: true,
      }),
      links: {},
    };
    const promotedModel = {
      ...model,
      current_revision: fixtureRevision(promotedModelRevisionId, modelId, {
        model_family_id: "reference_isotropic_linear_elasticity",
        model_schema_version: "1.0.0",
        model_schema_digest: "b".repeat(64),
        material_state_id: materialStateId,
        youngs_modulus_pa: 210_000_000_000,
        calibration_evidence: {
          calibration_selection_id: candidateSelectionId,
          calibration_selection_revision_id: candidateSelectionRevisionId,
          calibration_run_id: runId,
          calibration_candidate_id: candidateId,
          calibration_candidate_sha256: `sha256:${"c".repeat(64)}`,
          diagnostics_artifact_id: "80000000-0000-4000-8000-000000000014",
          diagnostics_sha256: `sha256:${"d".repeat(64)}`,
        },
        non_production: true,
      }),
    };
    const fetchMock = vi.fn<typeof fetch>((input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith(`/material-states/${materialStateId}/material-models`)) {
        return Promise.resolve(jsonResponse({ items: [model] }));
      }
      if (url.endsWith(`/material-states/${materialStateId}/datasets`)) {
        return Promise.resolve(jsonResponse({ items: [dataset] }));
      }
      if (url.endsWith(`/dataset-revisions/${datasetRevisionId}/selections`)) {
        return Promise.resolve(jsonResponse({ items: [selection] }));
      }
      if (url.endsWith("/calibration-plans") && method === "POST") {
        return Promise.resolve(jsonResponse(plan, 201));
      }
      if (url.endsWith("/calibration-runs") && method === "POST") {
        return Promise.resolve(jsonResponse(run, 201));
      }
      if (url.endsWith("/calibration-candidate-selections") && method === "POST") {
        return Promise.resolve(jsonResponse(candidateSelection, 201));
      }
      if (url.endsWith(`/calibration-candidate-selections/${candidateSelectionId}/promote-material-model`) && method === "POST") {
        return Promise.resolve(jsonResponse({
          calibration_candidate_selection_id: candidateSelectionId,
          calibration_candidate_selection_revision_id: candidateSelectionRevisionId,
          material_model: promotedModel,
        }, 201));
      }
      if (url.includes(`/calibration-candidates/${candidateId}/diagnostics-preview`)) {
        return Promise.resolve(jsonResponse({
          calibration_candidate_id: candidateId,
          point_count: 3,
          returned_point_count: 3,
          sampled: false,
          points: [
            { engineering_strain: 0, observed_engineering_stress_pa: 0, predicted_engineering_stress_pa: 0, residual_engineering_stress_pa: 0, normalized_residual: 0 },
            { engineering_strain: 0.01, observed_engineering_stress_pa: 2_100_000_000, predicted_engineering_stress_pa: 2_100_000_000, residual_engineering_stress_pa: 0, normalized_residual: 0 },
            { engineering_strain: 0.02, observed_engineering_stress_pa: 4_200_000_000, predicted_engineering_stress_pa: 4_200_000_000, residual_engineering_stress_pa: 0, normalized_residual: 0 },
          ],
        }));
      }
      return Promise.resolve(jsonResponse({ items: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ReferenceCalibrationWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "tenant-token" }}
        state={state}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Open calibration workbench" }));
    await screen.findByText("1. Pin Calibration Plan inputs and numerical conventions");
    fireEvent.click(screen.getByRole("button", { name: "Create immutable Calibration Plan" }));
    await screen.findByText(/Plan 80000000/);
    fireEvent.click(screen.getByRole("button", { name: "Execute Calibration Run" }));

    await screen.findByText("Observed and fitted engineering-stress curve");
    expect(screen.getByText("2.1000000e+11")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Record human Candidate acceptance" }));
    await screen.findByText(/Human acceptance recorded as Selection r1/);
    fireEvent.click(screen.getByRole("button", { name: "Promote accepted Candidate to new IR revision" }));
    await screen.findByText(/Promoted Material Model IR r1/);
    await waitFor(() => {
      const createPlanCall = fetchMock.mock.calls.find(([url, init]) => (
        String(url).endsWith("/calibration-plans") && init?.method === "POST"
      ));
      expect(createPlanCall).toBeTruthy();
      expect(JSON.parse(String(createPlanCall?.[1]?.body))).toMatchObject({
        selection_id: selectionId,
        selection_revision_id: selectionRevisionId,
        material_model_id: modelId,
        material_model_revision_id: modelRevisionId,
      });
      const candidateSelectionCall = fetchMock.mock.calls.find(([url, init]) => (
        String(url).endsWith("/calibration-candidate-selections") && init?.method === "POST"
      ));
      expect(candidateSelectionCall).toBeTruthy();
      expect(JSON.parse(String(candidateSelectionCall?.[1]?.body))).toMatchObject({
        classification: "internal",
        calibration_run_id: runId,
        calibration_candidate_id: candidateId,
      });
      const promotionCall = fetchMock.mock.calls.find(([url, init]) => (
        String(url).endsWith(`/calibration-candidate-selections/${candidateSelectionId}/promote-material-model`)
        && init?.method === "POST"
      ));
      expect(promotionCall).toBeTruthy();
      expect(JSON.parse(String(promotionCall?.[1]?.body))).toMatchObject({
        selection_revision_id: candidateSelectionRevisionId,
        expected_material_model_revision_id: modelRevisionId,
      });
    });
  });
});
