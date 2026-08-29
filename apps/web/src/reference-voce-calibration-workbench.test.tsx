import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReferenceVoceCalibrationWorkbench } from "./reference-voce-calibration-workbench";
import type {
  MaterialStateResponse,
  PropertySetResponse,
} from "./features/materials/contracts";
import type {
  DatasetResponse,
  ReferenceCalibrationScopeResponse,
} from "./features/test-data/contracts";

const ids = Array.from({ length: 32 }, (_, index) => `a1000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`);

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

function textResponse(body: string): Response {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ "content-type": "text/plain" }),
    text: async () => body,
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
      source_member_count: 3, included_member_count: 3, excluded_member_count: 0,
      members: [0, 1, 2].map((ordinal) => ({
        ordinal, dataset_id: ids[ordinal], dataset_revision_id: ids[ordinal + 3],
        test_run_id: ids[ordinal + 20], test_run_revision_id: ids[ordinal + 23],
        disposition: "included" as const, candidate_id: null, assessment_id: null,
        assessment_revision_id: null,
      })),
    } satisfies ReferenceCalibrationScopeResponse;
    const holdout = {
      dataset_id: ids[18], test_run_id: ids[19],
      current_revision: revision(ids[20], ids[18], {
        test_run_id: ids[19], test_run_revision_id: ids[21], raw_asset_id: ids[22],
        raw_artifact_id: ids[23], data_artifact_id: ids[24], data_sha256: "9".repeat(64),
        representation: "normalized" as const, source_dataset_revision_id: ids[25],
        processing_run_id: null, point_count: 7, mapping_sha256: "8".repeat(64),
        importer_id: "cmp.reference.uniaxial_tensile_csv", importer_version: "1.0.0",
        reference_only: true as const, channels: [],
      }), links: {},
    } satisfies DatasetResponse;
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
    const selectionId = ids[12];
    const selectionRevisionId = ids[13];
    const modelId = ids[14];
    const modelRevisionId = ids[15];
    const cardId = ids[16];
    const selection = {
      voce_candidate_selection_id: selectionId,
      current_revision: revision(selectionRevisionId, selectionId, {
        selection_label: "Accepted Voce", voce_calibration_run_id: run.voce_calibration_run_id,
        voce_calibration_candidate_id: ids[1], candidate_sha256: `sha256:${"c".repeat(64)}`,
        selection_reason: "reviewed", selection_decision: "accepted_for_tabulated_ir_projection",
        non_production: true,
      }), links: {},
    };
    const model = {
      material_model_id: modelId, material_state_id: state.material_state_id,
      current_revision: revision(modelRevisionId, modelId, {
        model_family_id: "urn:cmp:reference:isotropic-tabulated-plasticity:1.1.0",
        model_schema_version: "1.1.0", model_schema_digest: "f".repeat(64),
        material_id: state.material_id, material_revision_id: state.current_revision.content.material_revision_id,
        material_state_id: state.material_state_id, material_state_revision_id: state.current_revision.id,
        property_set_id: propertySet.property_set_id, property_set_revision_id: propertySet.current_revision.id,
        source_dataset_id: null, source_dataset_revision_id: null, density_kg_per_m3: 7850,
        youngs_modulus_pa: 210e9, poisson_ratio: 0.3, initial_yield_stress_pa: 301e6,
        hardening_curve: { artifact_id: ids[17], sha256: "d".repeat(64), schema_ref: "curve", point_count: 52,
          independent_quantity: "true_plastic_strain", independent_unit: "1", dependent_quantity: "true_yield_stress", dependent_unit: "Pa" },
        source_point_count: null, pre_yield_excluded_point_count: null, post_necking_excluded_point_count: null,
        necking_source_point_index: null, transformation_profile_id: "voce-grid", transformation_profile_version: "1.0.0",
        transformation_profile_digest: "e".repeat(64), necking_engineering_strain: null,
        characterized_max_true_plastic_strain: 0.18, extension_max_true_plastic_strain: 0.5,
        post_necking_extension_policy: "approved_constant_true_stress", post_necking_approximation_acknowledged: true,
        applicability: { temperature_min_k: null, temperature_max_k: null, strain_rate_min_per_s: null, strain_rate_max_per_s: null, note: null },
        reference_temperature_k: 293.15, calibration_projection: { candidate_id: ids[1] }, non_production: true,
      }), links: {},
    };
    const mapping = {
      material_model_id: modelId, material_model_revision_id: modelRevisionId,
      model_schema_digest: "f".repeat(64), target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s" },
      exportable: true, requires_acknowledgement: true, mapping_report_sha256: "m".repeat(64),
      exporter_id: "cmp.reference.abaqus-isotropic-plasticity", exporter_version: "1.0.0", exporter_digest: "e".repeat(64),
      items: [{ name: "isotropic_hardening_curve", ir_path: "/hardening", target_representation: "*PLASTIC", status: "exact", detail: "Mapped from the shared IR." }],
      non_production: true,
    };
    const holdoutPlanId = ids[26];
    const holdoutPlanRevisionId = ids[27];
    const holdoutPlan = {
      voce_holdout_plan_id: holdoutPlanId,
      current_revision: revision(holdoutPlanRevisionId, holdoutPlanId, {
        plan_label: "Independent holdout", material_model_id: modelId,
        material_model_revision_id: modelRevisionId, holdout_dataset_id: holdout.dataset_id,
        holdout_dataset_revision_id: holdout.current_revision.id,
        metric_profile_id: "metric", threshold_profile_id: "threshold",
        relative_rmse_threshold: 0.05, overlap_policy: "reject_any_calibration_scope_dataset_or_test_run_overlap",
        evaluation_mode: "closed_form_curve", solver_execution: "not_used", non_production: true,
      }), links: {},
    };
    const holdoutResult = {
      voce_holdout_result_id: ids[28], voce_holdout_run_id: ids[29], plan_id: holdoutPlanId,
      plan_revision_id: holdoutPlanRevisionId, material_model_id: modelId,
      material_model_revision_id: modelRevisionId, calibration_input_scope_id: scope.scope_id,
      calibration_input_scope_revision_id: scope.current_revision.id,
      voce_calibration_run_id: run.voce_calibration_run_id,
      voce_calibration_candidate_id: ids[1], voce_candidate_selection_id: selectionId,
      voce_candidate_selection_revision_id: selectionRevisionId, holdout_dataset_id: holdout.dataset_id,
      holdout_dataset_revision_id: holdout.current_revision.id, holdout_test_run_id: ids[19],
      holdout_test_run_revision_id: ids[21], holdout_independence: "disjoint_dataset_and_test_run",
      source_data_artifact_id: ids[24], source_data_sha256: `sha256:${"9".repeat(64)}`,
      comparison_artifact_id: ids[30], comparison_sha256: `sha256:${"7".repeat(64)}`,
      comparison_point_count: 3, root_mean_squared_error_pa: 2e6,
      relative_root_mean_squared_error: 0.004, normalization_stress_scale_pa: 500e6,
      characterized_max_true_plastic_strain: 0.03, relative_rmse_threshold: 0.05,
      verdict: "passed", evaluation_mode: "closed_form_curve", solver_execution: "not_used",
      non_production: true, created_at: "2026-07-15T00:00:02Z", created_by: ids[9],
      points: [1, 2, 3].map((ordinal) => ({
        source_point_ordinal: ordinal, true_plastic_strain: ordinal * 0.01,
        observed_true_yield_stress_pa: 400e6 + ordinal * 20e6,
        predicted_true_yield_stress_pa: 402e6 + ordinal * 20e6,
        residual_true_yield_stress_pa: 2e6,
      })), links: {},
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
      if (url.endsWith("/voce-candidate-selections") && init?.method === "POST") return Promise.resolve(response(selection));
      if (url.endsWith(`/voce-candidate-selections/${selectionId}/tabulated-plasticity-models`) && init?.method === "POST") return Promise.resolve(response(model));
      if (url.endsWith(`/tabulated-plasticity-models/${modelId}/mapping-preflight`) && init?.method === "POST") return Promise.resolve(response(mapping, 200));
      if (url.endsWith(`/tabulated-plasticity-models/${modelId}/solver-cards`) && init?.method === "POST") return Promise.resolve(response({ card: { solver_card_id: cardId }, mapping_report: mapping }));
      if (url.endsWith(`/elastoplastic-solver-cards/${cardId}/preview`)) return Promise.resolve(textResponse("*MATERIAL, NAME=CALIBRATED_MATERIAL\n*PLASTIC"));
      if (url.endsWith("/voce-holdout-validation-plans") && init?.method === "POST") return Promise.resolve(response(holdoutPlan));
      if (url.endsWith(`/voce-holdout-validation-plans/${holdoutPlanId}/runs`) && init?.method === "POST") return Promise.resolve(response(holdoutResult));
      return Promise.resolve(response({ detail: "unexpected" }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ReferenceVoceCalibrationWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} state={state} propertySet={propertySet} scope={scope} datasets={[holdout]} />);
    fireEvent.click(screen.getByRole("button", { name: "Create immutable Voce Plan" }));
    await screen.findByText(/Plan a1000000/);
    fireEvent.click(screen.getByRole("button", { name: "Execute multi-curve Calibration Run" }));
    await screen.findByText("301.000 MPa");
    expect(screen.getByText(/3 curves · 3 starts/)).toBeTruthy();
    expect(screen.getAllByText(/objective 2.00000e-4/)).toHaveLength(3);
    expect(await screen.findByLabelText("Observed and fitted Voce curves")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Accept this converged Candidate" }));
    await screen.findByText(/Accepted Selection/);
    fireEvent.click(screen.getByLabelText(/Acknowledge constant extension approximation/));
    fireEvent.click(screen.getByRole("button", { name: "Create solver-neutral calibrated IR" }));
    await screen.findByText(/IR a1000000/);
    fireEvent.change(screen.getByLabelText("Target solver"), { target: { value: "abaqus" } });
    fireEvent.click(screen.getByRole("button", { name: "Run mapping preflight" }));
    await screen.findByText(/Mapped from the shared IR/);
    fireEvent.click(screen.getByRole("button", { name: "Generate Abaqus .inp" }));
    expect(await screen.findByText(/\*MATERIAL, NAME=CALIBRATED_MATERIAL/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Create immutable holdout Plan" }));
    await screen.findByRole("button", { name: "Evaluate closed-form holdout" });
    fireEvent.click(screen.getByRole("button", { name: "Evaluate closed-form holdout" }));
    expect(await screen.findByLabelText("Voce holdout observed and predicted curve")).toBeTruthy();
    expect(screen.getByText("Dataset + Test Run disjoint")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(10);
  });
});
