import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ScalarDistributionWorkbench } from "./scalar-distribution-workbench";
import type {
  MaterialStateResponse,
  ScalarDistributionCandidate,
  ScalarDistributionSelectionResponse,
} from "./types";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

const ids = {
  state: "21000000-0000-4000-8000-000000000001",
  selection: "21000000-0000-4000-8000-000000000002",
  selectionRevision: "21000000-0000-4000-8000-000000000003",
  plan: "21000000-0000-4000-8000-000000000004",
  planRevision: "21000000-0000-4000-8000-000000000005",
  run: "21000000-0000-4000-8000-000000000006",
  descriptiveResult: "21000000-0000-4000-8000-000000000007",
  descriptiveRevision: "21000000-0000-4000-8000-000000000008",
  result: "21000000-0000-4000-8000-000000000009",
  resultRevision: "21000000-0000-4000-8000-000000000010",
  artifact: "21000000-0000-4000-8000-000000000011",
  decision: "21000000-0000-4000-8000-000000000012",
  decisionRevision: "21000000-0000-4000-8000-000000000013",
};

function revision(id: string, aggregateId: string, revisionNo = 1) {
  return {
    id,
    aggregate_id: aggregateId,
    revision_no: revisionNo,
    based_on_revision_id: revisionNo === 1 ? null : ids.decisionRevision,
    schema_id: "urn:cmp:test:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-08-12T00:00:00Z",
    created_by: "21000000-0000-4000-8000-000000000020",
    change_reason: "test",
    organization_id: "21000000-0000-4000-8000-000000000021",
    project_id: "21000000-0000-4000-8000-000000000022",
    classification: "internal" as const,
    lifecycle_state: "draft" as const,
  };
}

function candidate(
  family: ScalarDistributionCandidate["family"],
  aicc: number,
  digest: string,
  recommended: boolean,
): ScalarDistributionCandidate {
  return {
    family,
    status: "succeeded",
    support: family === "normal" ? "real" : "positive",
    estimator: `${family}_two_parameter_mle_v1`,
    parameter_count: 2,
    parameters: family === "normal"
      ? [
          { name: "location", estimate: 612_000_000, unit_id: "Pa" },
          { name: "scale", estimate: 18_000_000, unit_id: "Pa" },
        ]
      : [
          { name: "shape", estimate: family === "lognormal" ? 0.03 : 34.2, unit_id: null },
          { name: "scale", estimate: 612_000_000, unit_id: "Pa" },
        ],
    log_likelihood: -165.2,
    aicc,
    bic: aicc + 0.7,
    anderson_darling: 0.21,
    bootstrap_p_value: 0.48,
    bootstrap_success_count: 999,
    bootstrap_failure_count: 0,
    delta_aicc: aicc - 334,
    recommended,
    reason_codes: ["fit_succeeded"],
    warnings: ["small_sample_n_8_to_19_interpret_with_caution"],
    candidate_sha256: digest.repeat(64),
  };
}

describe("Scalar distribution workbench", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("compares every saved candidate and reloads an explicit selection separately", async () => {
    const processedMembers = Array.from({ length: 8 }, (_, ordinal) => ({
      ordinal,
      dataset_id: `21000000-0000-4000-8000-${String(100 + ordinal).padStart(12, "0")}`,
      dataset_revision_id: `21000000-0000-4000-8000-${String(200 + ordinal).padStart(12, "0")}`,
      test_run_id: `21000000-0000-4000-8000-${String(300 + ordinal).padStart(12, "0")}`,
      test_run_revision_id: `21000000-0000-4000-8000-${String(400 + ordinal).padStart(12, "0")}`,
    }));
    const datasets = processedMembers.map((member) => ({
      dataset_id: member.dataset_id,
      test_run_id: member.test_run_id,
      current_revision: {
        id: member.dataset_revision_id,
        revision_no: 1,
        content: { representation: "processed", point_count: 31 },
      },
    }));
    const selection = {
      selection_id: ids.selection,
      selection_label: "Eight processed replicates",
      current_revision: {
        ...revision(ids.selectionRevision, ids.selection),
        content: {
          selection_kind: "reference_tensile_replicate_set" as const,
          member_count: 8,
          members: processedMembers,
        },
      },
      links: {},
    };
    const normalizedSelection = {
      ...selection,
      selection_id: "21000000-0000-4000-8000-000000000030",
      selection_label: "Normalized alignment source",
      current_revision: {
        ...selection.current_revision,
        id: "21000000-0000-4000-8000-000000000031",
        content: {
          ...selection.current_revision.content,
          members: [{
            ...processedMembers[0],
            dataset_revision_id: "21000000-0000-4000-8000-000000000032",
          }],
        },
      },
    };
    const plan = {
      statistical_plan_id: ids.plan,
      plan_label: "Peak engineering stress distribution comparison",
      current_revision: {
        ...revision(ids.planRevision, ids.plan),
        content: {
          plan_kind: "reference_tensile_replicate_scalar_and_curve" as const,
          selection_id: ids.selection,
          selection_revision_id: ids.selectionRevision,
          sample_count: 8,
          required_input_representation: "processed" as const,
          scalar_feature: "peak_engineering_stress_pa" as const,
          curve_grid_policy: "exact_processed_grid_match_no_alignment" as const,
          quantile_method: "linear_inclusive" as const,
          confidence_interval_method: "student_t_95_two_sided" as const,
          curve_output_schema_ref: "urn:cmp:statistics:reference-tensile-replicates:1.1.0",
          scalar_distribution: { seed: 210, bootstrap_samples: 999 as const, unit_profile: null },
        },
      },
      links: {},
    };
    const run = {
      statistical_run_id: ids.run,
      classification: "internal" as const,
      execution_mode: "committed" as const,
      status: "succeeded" as const,
      plan_id: ids.plan,
      plan_revision_id: ids.planRevision,
      selection_id: ids.selection,
      selection_revision_id: ids.selectionRevision,
      sample_count: 8,
      members: [],
      result_id: ids.descriptiveResult,
      result_revision_id: ids.descriptiveRevision,
      curve_artifact_id: ids.artifact,
      curve_sha256: "9".repeat(64),
      curve_point_count: 3,
      scalar_distribution_result_id: ids.result,
      scalar_distribution_result_revision_id: ids.resultRevision,
      scalar_distribution_artifact_id: ids.artifact,
      scalar_distribution_sha256: "d".repeat(64),
      failure_code: null,
      qc_observations: [],
      change_reason: "test",
      started_at: "2026-08-12T00:00:00Z",
      ended_at: "2026-08-12T00:00:01Z",
      links: {},
    };
    const candidates = [
      candidate("normal", 334, "1", true),
      candidate("lognormal", 335.2, "2", true),
      candidate("weibull", 341, "3", false),
    ];
    const result = {
      scalar_distribution_result_id: ids.result,
      current_revision: revision(ids.resultRevision, ids.result),
      statistical_run_id: ids.run,
      statistical_result_id: ids.descriptiveResult,
      statistical_result_revision_id: ids.descriptiveRevision,
      plan_id: ids.plan,
      plan_revision_id: ids.planRevision,
      selection_id: ids.selection,
      selection_revision_id: ids.selectionRevision,
      scalar_feature: "peak_engineering_stress_pa",
      sample_count: 8,
      minimum_sample_count: 8,
      small_sample_warning_below: 20,
      observations: [],
      candidates,
      recommended_families: ["normal", "lognormal"],
      recommendation_method: "aicc_delta_le_2_at_least_two_successful_candidates_v1",
      artifact_id: ids.artifact,
      artifact_sha256: "d".repeat(64),
      seed: 210,
      bootstrap_samples: 999,
      unit_profile: null,
      unit_applications: [],
      runtime_manifest: {
        algorithm_version: "scalar_distribution_fitting_v1",
        schema_ref: "urn:cmp:statistics:scalar-distribution-result:1.0.0",
        python_version: "3.13.7",
        numpy_version: "2.3.4",
        scipy_version: "1.16.3",
        rng: "numpy.random.PCG64",
        source_sha256: "4".repeat(64),
        lock_sha256: "5".repeat(64),
        environment_sha256: "6".repeat(64),
      },
      links: {},
    };
    let savedDecision: ScalarDistributionSelectionResponse | null = null;
    const fetchMock = vi.fn<typeof fetch>((input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith(`/material-states/${ids.state}/datasets`)) return Promise.resolve(jsonResponse({ items: datasets }));
      if (url.includes("/dataset-selections/reference-tensile-replicates?")) return Promise.resolve(jsonResponse({ items: [selection, normalizedSelection] }));
      if (url.includes("/replicate-statistical-plans?")) return Promise.resolve(jsonResponse({ items: [plan] }));
      if (url.includes("/replicate-statistical-runs?")) return Promise.resolve(jsonResponse({ items: [run] }));
      if (url.endsWith("/replicate-statistical-runs") && method === "POST") {
        return Promise.resolve(jsonResponse(run, 201));
      }
      if (url.endsWith(`/scalar-distribution-results/${ids.result}/selections`) && method === "GET") {
        return Promise.resolve(jsonResponse({ items: savedDecision ? [savedDecision] : [] }));
      }
      if (url.endsWith(`/scalar-distribution-results/${ids.result}`)) return Promise.resolve(jsonResponse(result));
      if (url.endsWith(`/scalar-distribution-results/${ids.result}/selections`) && method === "POST") {
        const body = JSON.parse(String(init?.body)) as { selected_family: "normal"; selection_reason: string };
        savedDecision = {
          distribution_selection_id: ids.decision,
          current_revision: revision(ids.decisionRevision, ids.decision),
          content: {
            distribution_result_id: ids.result,
            distribution_result_revision_id: ids.resultRevision,
            selected_family: body.selected_family,
            candidate_sha256: candidates[0].candidate_sha256,
            selection_reason: body.selection_reason,
          },
          links: {},
        };
        return Promise.resolve(jsonResponse(savedDecision, 201));
      }
      return Promise.resolve(jsonResponse({ detail: `Unexpected ${method} ${url}` }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    const state = { material_state_id: ids.state } as MaterialStateResponse;
    const props = {
      config: { baseUrl: "/api/v1", accessToken: "tenant-token" },
      classification: "internal" as const,
      state,
      onClose: vi.fn(),
    };
    const first = render(<ScalarDistributionWorkbench {...props} />);

    await screen.findByRole("table");
    expect(document.activeElement?.id).toBe("scalar-distribution-dock");
    expect(screen.queryByRole("option", { name: /Normalized alignment source/ })).toBeNull();
    expect(screen.getByText("Normal + Lognormal")).toBeTruthy();
    expect(screen.getByRole("row", { name: /Weibull/ }).textContent).toContain("341.000");
    fireEvent.change(screen.getByLabelText("Successful candidate"), { target: { value: "normal" } });
    fireEvent.change(screen.getByLabelText("Selection reason"), {
      target: { value: "Normal is retained for this bounded engineering review." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save selection" }));
    await screen.findByText("Selected model and reason saved as an exact immutable revision.");
    expect(screen.getByText(
      "Normal is retained for this bounded engineering review.",
      { selector: ".distribution-saved-decision span" },
    )).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Fit and save candidates" }));
    await screen.findByText("Comparison saved. All source observations and descriptive statistics remain unchanged.");
    expect(fetchMock.mock.calls.some(([input, init]) =>
      String(input).endsWith("/replicate-statistical-plans")
        && (init?.method ?? "GET") === "POST",
    )).toBe(false);

    first.unmount();
    render(<ScalarDistributionWorkbench {...props} />);
    await screen.findByText(
      "Normal is retained for this bounded engineering review.",
      { selector: ".distribution-saved-decision span" },
    );
    expect((screen.getByLabelText("Successful candidate") as HTMLSelectElement).value).toBe("normal");
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  });
});
