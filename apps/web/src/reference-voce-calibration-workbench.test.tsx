import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReferenceVoceCalibrationWorkbench } from "./reference-voce-calibration-workbench";
import type { MaterialStateResponse, PropertySetResponse, ReferenceCalibrationScopeResponse } from "./types";

const ids = Array.from({ length: 12 }, (_, index) => `a1000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`);

function revision<T extends object>(id: string, aggregateId: string, content: T) {
  return {
    id, aggregate_id: aggregateId, revision_no: 1, based_on_revision_id: null,
    schema_id: "urn:cmp:test:1.0.0", schema_version: "1.0.0", content_hash: "a".repeat(64),
    created_at: "2026-07-15T00:00:00Z", created_by: ids[9], change_reason: "test",
    organization_id: ids[10], project_id: ids[11], classification: "internal" as const,
    lifecycle_state: "draft" as const,
    provenance: {
      entity_type: "revision", reference_type: "revision", revision_id: id,
      content_sha256: "a".repeat(64), based_on_revision_id: null,
      recorded_at: "2026-07-15T00:00:00Z", recorded_by: ids[9],
    },
    content,
  };
}

function response(body: unknown, status = 201): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

describe("Reference Voce calibration workbench", () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it("pins a reviewed Scope, executes multistart, and renders per-curve diagnostics", async () => {
    const state = {
      material_state_id: ids[0], material_id: ids[1],
      current_revision: revision(ids[2], ids[0], { material_id: ids[1], material_revision_id: ids[3], name: "Normalized", manufacturing_route: null, heat_treatment: null, lot_or_batch: null, description: null }),
      property_sets_url: `/material-states/${ids[0]}/property-sets`,
    } satisfies MaterialStateResponse;
    const propertySet = {
      property_set_id: ids[4], material_state_id: ids[0],
      current_revision: revision(ids[5], ids[4], {
        material_state_id: ids[0], material_state_revision_id: ids[2], density_kg_per_m3: 7850,
        density_source: { kind: "manual", reference: null }, youngs_modulus_pa: 210e9,
        youngs_modulus_source: { kind: "manual", reference: null }, poisson_ratio: 0.3,
        poisson_ratio_source: { kind: "manual", reference: null }, yield_stress_pa: 300e6,
        yield_stress_source: { kind: "manual", reference: null }, applicability: {
          temperature_min_k: null, temperature_max_k: null, strain_rate_min_per_s: null,
          strain_rate_max_per_s: null, note: null,
        },
      }),
    } satisfies PropertySetResponse;
    const scope = {
      scope_id: ids[6], scope_label: "Reviewed scope", current_revision: revision(ids[7], ids[6], {}),
      source_selection_id: ids[8], source_selection_revision_id: ids[9], statistical_result_id: ids[1],
      statistical_result_revision_id: ids[2], detection_plan_id: ids[3], detection_plan_revision_id: ids[4],
      source_member_count: 3, included_member_count: 3, excluded_member_count: 0, members: [],
    } satisfies ReferenceCalibrationScopeResponse;
    const planId = ids[8];
    const planRevisionId = ids[9];
    const plan = {
      voce_calibration_plan_id: planId,
      current_revision: revision(planRevisionId, planId, {
        plan_kind: "reference_multi_curve_voce_saturation", plan_label: "Reviewed Voce",
        calibration_input_scope_id: scope.scope_id, calibration_input_scope_revision_id: scope.current_revision.id,
        material_state_id: state.material_state_id, material_state_revision_id: state.current_revision.id,
        property_set_id: propertySet.property_set_id, property_set_revision_id: propertySet.current_revision.id,
        youngs_modulus_pa: 210e9, parameters: [], normalization_stress_scale_pa: 100e6,
        multistart_count: 3, random_seed: 20260715, maximum_function_evaluations: 2000,
        ftol: 1e-10, xtol: 1e-10, gtol: 1e-10, model_family_id: "voce",
        test_mode_adapter_id: "adapter", evaluator_id: "evaluator", objective_engine_id: "objective",
        optimizer_adapter_id: "scipy", evaluation_mode: "closed_form_curve",
        residual_definition: "predicted_minus_observed_true_yield_stress", specimen_weighting: "equal_specimen",
        point_weighting: "uniform_within_specimen", objective_aggregation: "mean",
        x_domain_policy: "observed", missing_data_policy: "reject", optimizer_method: "trf",
        rng_algorithm: "numpy.random.PCG64", non_production: true,
      }),
    };
    const run = {
      voce_calibration_run_id: ids[0], classification: "internal", plan_id: planId,
      plan_revision_id: planRevisionId, calibration_input_scope_id: scope.scope_id,
      calibration_input_scope_revision_id: scope.current_revision.id, property_set_id: propertySet.property_set_id,
      property_set_revision_id: propertySet.current_revision.id, source_curve_count: 3,
      execution_mode: "reference_inline_scipy", reproducibility_level: "R3", environment_digest: `sha256:${"e".repeat(64)}`,
      status: "succeeded", attempt_count: 3, candidate_count: 3, failure_code: null,
      change_reason: "fit", started_at: "2026-07-15T00:00:00Z", ended_at: "2026-07-15T00:00:01Z",
      attempts: [], candidates: [{
        voce_calibration_candidate_id: ids[1], attempt_ordinal: 1, status: "converged",
        candidate_sha256: `sha256:${"c".repeat(64)}`, sigma_0_pa: 301e6, q_pa: 159e6, b: 12.1,
        objective_total: 0.0002, residual_root_mean_square_pa: 1.2e6, residual_mean_pa: 0,
        bound_sticking_parameters: [], convergence_status_code: 1, convergence_reason: "gtol satisfied",
        function_evaluations: 18, jacobian_evaluations: 16, optimality: 1e-9, warnings: [],
        identifiability_status: "not_assessed_reference", uncertainty_status: "not_provided_reference",
        diagnostics_artifact_id: ids[2], diagnostics_sha256: `sha256:${"d".repeat(64)}`,
        diagnostics_point_count: 15, objective_terms: [0, 1, 2].map((ordinal) => ({
          member_ordinal: ordinal, dataset_id: ids[ordinal], dataset_revision_id: ids[ordinal + 3],
          point_count: 5, mean_normalized_squared_residual: 0.0002,
        })),
      }],
    };
    const fetchMock = vi.fn<typeof fetch>((input, init) => {
      const url = String(input);
      if (url.endsWith("/voce-calibration-plans") && init?.method === "POST") return Promise.resolve(response(plan));
      if (url.endsWith(`/voce-calibration-plans/${planId}/runs`) && init?.method === "POST") return Promise.resolve(response(run));
      if (url.includes(`/voce-calibration-candidates/${ids[1]}/diagnostics-preview`)) {
        return Promise.resolve(response({
          calibration_candidate_id: ids[1], point_count: 6, returned_point_count: 6,
          sampled: false, points: [0, 1, 2, 3, 4, 5].map((point, index) => ({
            member_ordinal: index < 3 ? 0 : 1, dataset_revision_id: ids[index < 3 ? 3 : 4],
            point_ordinal: point % 3, true_plastic_strain: 0.01 * (point % 3 + 1),
            observed_true_yield_stress_pa: 320e6 + point * 10e6,
            predicted_true_yield_stress_pa: 321e6 + point * 10e6,
            residual_true_yield_stress_pa: 1e6, normalized_residual: 0.01,
            effective_weight: 1 / 6,
          })),
        }, 200));
      }
      return Promise.resolve(response({ detail: "unexpected" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ReferenceVoceCalibrationWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} state={state} propertySet={propertySet} scope={scope} />);
    fireEvent.click(screen.getByRole("button", { name: "Create immutable Voce Plan" }));
    await screen.findByText(/Plan a1000000/);
    fireEvent.click(screen.getByRole("button", { name: "Execute multi-curve Calibration Run" }));
    await screen.findByText("301.000 MPa");
    expect(screen.getByText(/3 curves · 3 starts/)).toBeTruthy();
    expect(screen.getAllByText(/objective 2.00000e-4/)).toHaveLength(3);
    expect(await screen.findByLabelText("Observed and fitted Voce curves")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
