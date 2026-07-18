import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReferenceOgdenCalibrationWorkbench } from "./reference-ogden-calibration-workbench";
import type {
  MaterialStateResponse,
  OgdenPronyModelResponse,
  ScientificProfileResponse,
} from "./types";

const ids = Array.from({ length: 24 }, (_, index) =>
  `f4300000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
);
const metadata = {
  id: ids[1], aggregate_id: ids[0], revision_no: 1, based_on_revision_id: null,
  schema_id: "urn:cmp:test:1.0.0", schema_version: "1.0.0", content_hash: "a".repeat(64),
  created_at: "2026-08-20T00:00:00Z", created_by: ids[15], change_reason: "fixture",
  organization_id: ids[16], project_id: ids[17], classification: "internal" as const,
  lifecycle_state: "draft" as const,
};
const state: MaterialStateResponse = {
  material_state_id: ids[0], material_id: ids[2],
  current_revision: {
    ...metadata,
    content: { material_id: ids[2], material_revision_id: ids[3], name: "Elastomer State", manufacturing_route: null, heat_treatment: null, lot_or_batch: null, description: null },
    provenance: { entity_type: "catalog.revision", reference_type: "catalog.revision", revision_id: ids[1], content_sha256: metadata.content_hash, based_on_revision_id: null, recorded_at: metadata.created_at, recorded_by: metadata.created_by },
  },
  property_sets_url: "",
};
const model: OgdenPronyModelResponse = {
  material_model_id: ids[4], material_state_id: ids[0], links: {},
  current_revision: {
    ...metadata, id: ids[5], aggregate_id: ids[4],
    content: {
      model_family_id: "urn:cmp:reference:ogden-prony-hyperviscoelastic:1.0.0",
      material_state_revision_id: ids[1], property_set_revision_id: ids[6],
      density_kg_per_m3: 1100, ogden_terms: [{ ordinal: 1, mu_pa: 1.2e6, alpha: 2.4 }],
      prony_terms: [{ ordinal: 1, g_ratio: 0.2, k_ratio: 0, relaxation_time_s: 1 }],
      moduli_convention: "instantaneous", volumetric_response: "incompressible", non_production: true,
    },
  },
};
const profile: ScientificProfileResponse = {
  scientific_profile_id: ids[7], links: {},
  current_revision: {
    ...metadata, id: ids[8], aggregate_id: ids[7],
    content: {
      profile_label: "Reference multi-test Ogden", family: "elastomer_ogden_prony",
      model_family_id: model.current_revision.content.model_family_id,
      approval_status: "reference_unapproved", optimizer: "scipy_least_squares_trf",
      residual_definition: "normalized_weighted_least_squares",
      aggregation_order: "point_then_curve_then_mode", missing_data_policy: "reject",
      holdout_policy: "explicit_disjoint", uncertainty_policy: "jacobian_covariance_or_not_estimable",
      multistart_count: 2, seed: 43, status_note: "Reference only",
      parameters: { mu_lower_pa: 1e3, mu_upper_pa: 1e8, alpha_lower: 0.1, alpha_upper: 20 },
    },
  },
};

function response(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, headers: new Headers({ "content-type": "application/json" }), json: async () => body } as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ReferenceOgdenCalibrationWorkbench", () => {
  it("fits governed curves, records a human decision, and appends an IR revision", async () => {
    let promoted = false;
    const promotedModel: OgdenPronyModelResponse = {
      ...model,
      current_revision: {
        ...model.current_revision,
        id: ids[20],
        revision_no: 2,
        based_on_revision_id: model.current_revision.id,
        schema_version: "1.1.0",
        content_hash: "f".repeat(64),
        content: {
          ...model.current_revision.content,
          ogden_terms: [{ ordinal: 1, mu_pa: 2e6, alpha: 2 }],
          promotion_evidence: {
            selection_id: ids[18], selection_revision_id: ids[19],
            calibration_run_id: ids[6], calibration_candidate_id: ids[15],
            candidate_sha256: "c".repeat(64), diagnostics_artifact_id: ids[16],
            diagnostics_sha256: "d".repeat(64),
            promoted_from_model_revision_id: model.current_revision.id,
          },
        },
      },
    };
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.includes("/scientific-profiles?")) return response({ items: [profile] });
      if (url.endsWith(`/ogden-prony-models/${ids[4]}/revisions`)) {
        return response({ material_model_id: ids[4], items: promoted ? [promotedModel.current_revision, model.current_revision] : [model.current_revision] });
      }
      if (url.endsWith(`/material-states/${ids[0]}/test-runs`)) {
        return response({ items: [{ test_run_id: ids[9], specimen_id: ids[10], test_method_id: ids[11], current_revision: { ...metadata, id: ids[12], aggregate_id: ids[9], content: { specimen_id: ids[10], specimen_revision_id: ids[10], test_method_id: ids[11], test_method_revision_id: ids[11], run_label: "PLANAR-01", performed_at: metadata.created_at, test_temperature_k: 296.15, crosshead_speed_mm_per_min: 2, reference_only: true } }, links: {} }] });
      }
      if (url.includes("/governed-datasets?")) {
        return response({ items: [{ dataset_id: ids[13], current_revision: { ...metadata, id: ids[14], aggregate_id: ids[13] }, representation: "normalized", data_schema: "planar_tension", test_run_id: ids[9], test_run_revision_id: ids[12], raw_asset_id: ids[2], raw_artifact_id: ids[3], data_artifact_id: ids[6], data_sha256: "b".repeat(64), import_profile_id: ids[7], import_profile_revision_id: ids[8], source_dataset_revision_id: ids[3], row_count: 21, channels: [] }] });
      }
      if (url.endsWith("/ogden-calibration-plans") && init?.method === "POST") {
        return response({ ogden_calibration_plan_id: ids[2], current_revision: { ...metadata, id: ids[3], aggregate_id: ids[2], content: { plan_label: "Governed multi-test Ogden reference fit", scientific_profile_id: ids[7], scientific_profile_revision_id: ids[8], material_state_id: ids[0], material_state_revision_id: ids[1], baseline_model_id: ids[4], baseline_model_revision_id: ids[5], members: [{ ordinal: 0, role: "calibration", test_mode: "planar_tension", dataset_id: ids[13], dataset_revision_id: ids[14], weight: 1 }], evaluator: "one_term_incompressible_ogden_nominal", objective: "normalized_weighted_least_squares", aggregation_order: "point_then_curve_then_mode", holdout_policy: "explicit_disjoint", maximum_function_evaluations: 5000, non_production: true } }, links: {} }, 201);
      }
      if (url.includes("/ogden-calibration-plans/") && url.endsWith("/runs") && init?.method === "POST") {
        return response({ ogden_calibration_run_id: ids[6], status: "succeeded", plan_id: ids[2], plan_revision_id: ids[3], scientific_profile_id: ids[7], scientific_profile_revision_id: ids[8], material_state_id: ids[0], material_state_revision_id: ids[1], baseline_model_id: ids[4], baseline_model_revision_id: ids[5], environment_digest: `sha256:${"e".repeat(64)}`, calibration_curve_count: 1, holdout_curve_count: 0, test_mode_count: 1, attempt_count: 1, candidate_count: 1, candidates: [{ ogden_calibration_candidate_id: ids[15], attempt_ordinal: 0, status: "converged", candidate_sha256: `sha256:${"c".repeat(64)}`, initial_mu_pa: 1.2e6, initial_alpha: 2.4, mu_pa: 2e6, alpha: 2, objective_total: 1e-8, objective_by_mode: { uniaxial_tension: 0, planar_tension: 1e-8, biaxial_tension: 0 }, calibration_rmse_pa: 1200, calibration_normalized_rmse: 0.002, holdout_rmse_pa: null, holdout_normalized_rmse: null, convergence_status_code: 1, convergence_reason: "gtol satisfied", function_evaluations: 9, jacobian_evaluations: 9, optimality: 1e-10, parameter_at_bound: false, jacobian_rank: 2, jacobian_condition_number: 20, identifiability_status: "full_rank", uncertainty_status: "estimated_jacobian_covariance", mu_standard_error_pa: 200, alpha_standard_error: 0.01, mu_confidence_interval_pa: [1999608, 2000392], alpha_confidence_interval: [1.98, 2.02], warnings: ["insufficient_test_modes", "no_holdout_data"], diagnostics_artifact_id: ids[16], diagnostics_point_count: 2, links: {} }], family_candidate_count: 4, family_candidates: [{ hyperelastic_family_candidate_id: ids[20], family: "mooney_rivlin", parameters: [{ name: "c10_pa", value: 8e5, unit: "Pa" }, { name: "c01_pa", value: 3e5, unit: "Pa" }], objective_total: 2e-9, objective_by_mode: { uniaxial_tension: 0, planar_tension: 2e-9, biaxial_tension: 0 }, calibration_normalized_rmse: 0.001, holdout_normalized_rmse: null, function_evaluations: 12, convergence_reason: "gtol satisfied", stability_status: "monotonic_on_fitted_domain", warnings: ["no_holdout_data"], candidate_sha256: `sha256:${"f".repeat(64)}` }], links: {} }, 201);
      }
      if (url.includes("/ogden-calibration-candidates/")) {
        return response({ candidate_id: ids[15], points: [0, 1].map((point) => ({ member_ordinal: 0, role: "calibration", test_mode: "planar_tension", dataset_id: ids[13], dataset_revision_id: ids[14], point_ordinal: point, engineering_strain: point * 0.1, stretch: 1 + point * 0.1, observed_nominal_stress_pa: point * 1e6, predicted_nominal_stress_pa: point * 1.001e6, residual_pa: point * 1000, normalized_residual: point * 0.001, effective_weight: 0.5 })) });
      }
      if (url.endsWith("/ogden-candidate-selections") && init?.method === "POST") {
        return response({ ogden_candidate_selection_id: ids[18], current_revision: { ...metadata, id: ids[19], aggregate_id: ids[18], content: { selection_label: "Reviewed multi-test Ogden Candidate", ogden_calibration_run_id: ids[6], ogden_calibration_candidate_id: ids[15], candidate_sha256: `sha256:${"c".repeat(64)}`, diagnostics_artifact_id: ids[16], diagnostics_sha256: `sha256:${"d".repeat(64)}`, baseline_model_id: ids[4], baseline_model_revision_id: ids[5], selection_reason: "Reviewed fitted curves, residuals, convergence, bounds, and uncertainty evidence", selection_decision: "accepted_for_ogden_prony_ir_revision", non_production: true } }, links: {} }, 201);
      }
      if (url.endsWith(`/ogden-candidate-selections/${ids[18]}/promotions`) && init?.method === "POST") {
        expect(new Headers(init.headers).get("If-Match")).toBe(`"revision:1:sha256:${"a".repeat(64)}"`);
        promoted = true;
        return response(promotedModel, 201);
      }
      throw new Error(`unexpected request ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const onPromoted = vi.fn();
    render(<ReferenceOgdenCalibrationWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} state={state} model={model} onPromoted={onPromoted} />);
    expect(await screen.findByText(/1 scientific profile · 1 supported normalized curves/)).toBeTruthy();
    expect(screen.getByText(/PLANAR-01/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Create immutable calibration Plan" }));
    expect(await screen.findByText(/point → curve → mode aggregation/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Execute Ogden Calibration Run" }));
    expect(await screen.findByText(/1 candidates · 1 modes/)).toBeTruthy();
    expect(screen.getByRole("table", { name: "Hyperelastic family candidate comparison" })).toBeTruthy();
    expect(screen.getByText("mooney rivlin")).toBeTruthy();
    expect(screen.getByText(/estimated jacobian covariance/)).toBeTruthy();
    expect(screen.getAllByText(/no holdout data/).length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByRole("img", { name: "Multi-test Ogden fit and residual plot" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Record immutable Candidate Selection" }));
    expect(await screen.findByText(/Selection r1 recorded/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Promote into model r2" }));
    expect(await screen.findByText(/2 revisions/)).toBeTruthy();
    expect(screen.getAllByText(/Candidate f4300000/).length).toBeGreaterThanOrEqual(2);
    await waitFor(() => expect(onPromoted).toHaveBeenCalledWith(promotedModel));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(10));
    const planCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/ogden-calibration-plans"));
    expect(JSON.parse(String(planCall?.[1]?.body))).toMatchObject({ members: [{ role: "calibration", test_mode: "planar_tension", dataset_revision_id: ids[14] }] });
  });
});
