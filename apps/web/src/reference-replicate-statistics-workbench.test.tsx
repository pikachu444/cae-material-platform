import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReferenceReplicateStatisticsWorkbench } from "./reference-replicate-statistics-workbench";
import type { TensileReplicateSelectionResponse } from "./types";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

const selectionId = "91000000-0000-4000-8000-000000000001";
const selectionRevisionId = "91000000-0000-4000-8000-000000000002";
const planId = "91000000-0000-4000-8000-000000000003";
const planRevisionId = "91000000-0000-4000-8000-000000000004";
const runId = "91000000-0000-4000-8000-000000000005";
const resultId = "91000000-0000-4000-8000-000000000006";
const artifactId = "91000000-0000-4000-8000-000000000007";
const revisionIds = [
  "91000000-0000-4000-8000-000000000011",
  "91000000-0000-4000-8000-000000000012",
  "91000000-0000-4000-8000-000000000013",
];

function revision<T extends object>(id: string, aggregateId: string, content: T) {
  return {
    id,
    aggregate_id: aggregateId,
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:test:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-07-30T00:00:00Z",
    created_by: "91000000-0000-4000-8000-000000000020",
    change_reason: "test",
    organization_id: "91000000-0000-4000-8000-000000000021",
    project_id: "91000000-0000-4000-8000-000000000022",
    classification: "internal" as const,
    lifecycle_state: "draft" as const,
    content,
  };
}

describe("Reference replicate statistics workbench", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("explicitly pins aligned outputs, runs typed statistics, and renders QC and CI", async () => {
    const selection = {
      selection_id: selectionId,
      selection_label: "Aligned inputs",
      current_revision: revision(selectionRevisionId, selectionId, {
        selection_kind: "reference_tensile_replicate_set" as const,
        material_state_id: "91000000-0000-4000-8000-000000000030",
        member_count: 3,
        members: revisionIds.map((datasetRevisionId, index) => ({
          ordinal: index + 1,
          dataset_id: `91000000-0000-4000-8000-00000000004${index}`,
          dataset_revision_id: datasetRevisionId,
          test_run_id: `91000000-0000-4000-8000-00000000005${index}`,
          test_run_revision_id: `91000000-0000-4000-8000-00000000006${index}`,
        })),
      }),
      links: {},
    };
    const plan = {
      statistical_plan_id: planId,
      plan_label: "Replicate statistics",
      current_revision: revision(planRevisionId, planId, {
        plan_kind: "reference_tensile_replicate_scalar_and_curve",
        selection_id: selectionId,
        selection_revision_id: selectionRevisionId,
        sample_count: 3,
        required_input_representation: "processed",
        scalar_feature: "peak_engineering_stress_pa",
        curve_grid_policy: "exact_processed_grid_match_no_alignment",
        quantile_method: "linear_inclusive",
        confidence_interval_method: "student_t_95_two_sided",
        curve_output_schema_ref: "urn:cmp:statistics:reference-tensile-replicates:1.0.0",
      }),
      links: {},
    };
    const scalar = {
      sample_count: 3,
      mean: 622_066_666.67,
      sample_standard_deviation: 21_773_684.42,
      median: 625_000_000,
      median_absolute_deviation: 20_000_000,
      interquartile_range: 21_500_000,
      minimum: 598_000_000,
      maximum: 643_200_000,
      coefficient_of_variation: 0.034999,
      mean_confidence_interval_lower_95: 567_977_241.83,
      mean_confidence_interval_upper_95: 676_156_091.50,
    };
    const run = {
      statistical_run_id: runId,
      classification: "internal",
      execution_mode: "committed",
      status: "succeeded",
      plan_id: planId,
      plan_revision_id: planRevisionId,
      selection_id: selectionId,
      selection_revision_id: selectionRevisionId,
      sample_count: 3,
      members: [],
      result_id: resultId,
      result_revision_id: "91000000-0000-4000-8000-000000000008",
      curve_artifact_id: artifactId,
      curve_sha256: "b".repeat(64),
      curve_point_count: 2,
      failure_code: null,
      qc_observations: [
        { check_code: "distinct_test_runs", outcome: "passed", detail: "All inputs are independent.", expected_point_count: null, observed_point_count: null, mismatch_index: null },
        { check_code: "identical_observed_engineering_strain_grid", outcome: "passed", detail: "All grids match.", expected_point_count: 2, observed_point_count: 2, mismatch_index: null },
      ],
      change_reason: "test",
      started_at: "2026-07-30T00:00:00Z",
      ended_at: "2026-07-30T00:00:01Z",
      links: {},
    };
    const result = {
      statistical_result_id: resultId,
      current_revision: revision(run.result_revision_id, resultId, {}),
      statistical_run_id: runId,
      plan_id: planId,
      plan_revision_id: planRevisionId,
      selection_id: selectionId,
      selection_revision_id: selectionRevisionId,
      curve_artifact_id: artifactId,
      curve_sha256: "b".repeat(64),
      curve_point_count: 2,
      peak_engineering_stress_pa: scalar,
      methods: {
        grid: "exact_processed_grid_match_no_alignment",
        quantile: "linear_inclusive",
        confidence_interval: "student_t_95_two_sided",
      },
      links: {},
    };
    const fetchMock = vi.fn<typeof fetch>((input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/dataset-selections/reference-tensile-replicates") && method === "POST") {
        return Promise.resolve(jsonResponse(selection, 201));
      }
      if (url.endsWith("/replicate-statistical-plans") && method === "POST") {
        return Promise.resolve(jsonResponse(plan, 201));
      }
      if (url.endsWith("/replicate-statistical-runs") && method === "POST") {
        return Promise.resolve(jsonResponse(run, 201));
      }
      if (url.endsWith(`/replicate-statistical-results/${resultId}`)) {
        return Promise.resolve(jsonResponse(result));
      }
      if (url.includes(`/replicate-statistical-results/${resultId}/curve`)) {
        return Promise.resolve(jsonResponse({
          result_id: resultId,
          grid_policy: "exact_processed_grid_match_no_alignment",
          points: [
            { engineering_strain: 0, statistics: { ...scalar, mean: 0, minimum: 0, maximum: 0, mean_confidence_interval_lower_95: 0, mean_confidence_interval_upper_95: 0 } },
            { engineering_strain: 0.02, statistics: scalar },
          ],
        }));
      }
      return Promise.resolve(jsonResponse({ detail: `Unexpected ${method} ${url}` }, 404));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ReferenceReplicateStatisticsWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "tenant-token" }}
        classification="internal"
        alignedDatasetRevisionIds={revisionIds}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Pin aligned outputs" }));
    await screen.findByText(/Selection 91000000/);
    fireEvent.click(screen.getByRole("button", { name: "Create Statistical Plan" }));
    await screen.findByText(/Plan 91000000/);
    fireEvent.click(screen.getByRole("button", { name: "Commit Statistics\/QC Run" }));

    await screen.findByText("Replicate scalar statistics");
    expect(screen.getByText(/Student-t two-sided 95% CI/)).toBeTruthy();
    expect(screen.getByLabelText("Multi-replicate quality-control observations").textContent).toContain("distinct_test_runs");
    expect(screen.getByLabelText("Replicate statistical curve band")).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
  });

  it("reuses an existing processed replicate Selection without duplicate alignment or pinning", async () => {
    const pinnedSelection = {
      selection_id: selectionId,
      selection_label: "Existing processed inputs",
      current_revision: revision(selectionRevisionId, selectionId, {
        selection_kind: "reference_tensile_replicate_set" as const,
        material_state_id: "91000000-0000-4000-8000-000000000030",
        member_count: 3,
        members: revisionIds.map((datasetRevisionId, index) => ({
          ordinal: index + 1,
          dataset_id: `91000000-0000-4000-8000-00000000004${index}`,
          dataset_revision_id: datasetRevisionId,
          test_run_id: `91000000-0000-4000-8000-00000000005${index}`,
          test_run_revision_id: `91000000-0000-4000-8000-00000000006${index}`,
        })),
      }),
      links: {},
    } satisfies TensileReplicateSelectionResponse;
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ReferenceReplicateStatisticsWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "tenant-token" }}
        classification="internal"
        alignedDatasetRevisionIds={revisionIds}
        pinnedSelection={pinnedSelection}
      />,
    );

    await screen.findByText("6C. Use the pinned processed Selection as the Statistics input");
    expect(screen.queryByRole("button", { name: "Pin aligned outputs" })).toBeNull();
    expect(screen.getByRole("button", { name: "Create Statistical Plan" })).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
