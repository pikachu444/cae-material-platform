import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReferenceTensileWorkflow } from "./reference-tensile-workflow";

function jsonResponse(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

const state = {
  material_state_id: "00000000-0000-0000-0000-000000000001",
  material_id: "00000000-0000-0000-0000-000000000002",
  current_revision: {
    id: "00000000-0000-0000-0000-000000000003",
    aggregate_id: "00000000-0000-0000-0000-000000000001",
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:catalog:material-state:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-07-13T00:00:00Z",
    created_by: "00000000-0000-0000-0000-000000000004",
    change_reason: "demo",
    organization_id: "00000000-0000-0000-0000-000000000005",
    project_id: "00000000-0000-0000-0000-000000000006",
    classification: "internal" as const,
    lifecycle_state: "draft" as const,
    content: {
      material_id: "00000000-0000-0000-0000-000000000002",
      material_revision_id: "00000000-0000-0000-0000-000000000007",
      name: "As received",
      manufacturing_route: null,
      heat_treatment: null,
      lot_or_batch: null,
      description: null,
    },
    provenance: {
      entity_type: "catalog.material_state.revision",
      reference_type: "catalog.material_state.revision",
      revision_id: "00000000-0000-0000-0000-000000000003",
      content_sha256: "a".repeat(64),
      based_on_revision_id: null,
      recorded_at: "2026-07-13T00:00:00Z",
      recorded_by: "00000000-0000-0000-0000-000000000004",
    },
  },
  property_sets_url: "/api/v1/material-states/1/property-sets",
};

describe("Reference tensile Dataset workflow", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("keeps the test workflow lazy, then exposes explicit CSV mapping fields", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse({ items: [] }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ReferenceTensileWorkflow
        config={{ baseUrl: "/api/v1", accessToken: "tenant-token" }}
        state={state}
      />,
    );

    expect(screen.queryByText("1. Register a concrete Specimen")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Manage reference tensile data" }));

    expect(await screen.findByText("1. Register a concrete Specimen")).toBeTruthy();
    expect(screen.getByLabelText("Strain column")).toBeTruthy();
    expect(screen.getByLabelText("Stress column")).toBeTruthy();
    expect(screen.getByText(/Detection records header evidence only/)).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(6);
  });

  it("commits a pinned observed-point crop and renders the separate processed curve", async () => {
    const datasetId = "10000000-0000-4000-8000-000000000001";
    const rawRevisionId = "10000000-0000-4000-8000-000000000002";
    const normalizedRevisionId = "10000000-0000-4000-8000-000000000003";
    const selectionId = "10000000-0000-4000-8000-000000000004";
    const selectionRevisionId = "10000000-0000-4000-8000-000000000005";
    const recipeId = "10000000-0000-4000-8000-000000000006";
    const recipeRevisionId = "10000000-0000-4000-8000-000000000007";
    const runId = "10000000-0000-4000-8000-000000000008";
    const processedDatasetId = "10000000-0000-4000-8000-000000000009";
    const processedRevisionId = "10000000-0000-4000-8000-00000000000a";
    const revision = (id: string, representation: "raw" | "normalized" | "processed", revisionNo: number) => ({
      ...state.current_revision,
      id,
      aggregate_id: datasetId,
      revision_no: revisionNo,
      content: {
        test_run_id: "10000000-0000-4000-8000-00000000000b",
        test_run_revision_id: "10000000-0000-4000-8000-00000000000c",
        raw_asset_id: "10000000-0000-4000-8000-00000000000d",
        raw_artifact_id: "10000000-0000-4000-8000-00000000000e",
        data_artifact_id: "10000000-0000-4000-8000-00000000000f",
        data_sha256: "b".repeat(64),
        representation,
        source_dataset_revision_id: representation === "raw" ? null : rawRevisionId,
        processing_run_id: representation === "processed" ? runId : null,
        point_count: 4,
        mapping_sha256: "c".repeat(64),
        importer_id: "urn:cmp:datasets:reference-uniaxial-tensile-csv:1.0.0",
        importer_version: "1.0.0",
        reference_only: true as const,
        channels: [],
      },
    });
    const sourceDataset = {
      dataset_id: datasetId,
      test_run_id: "10000000-0000-4000-8000-00000000000b",
      current_revision: revision(normalizedRevisionId, "normalized", 2),
      links: {},
    };
    const selection = {
      selection_id: selectionId,
      selection_label: "Reference crop input",
      current_revision: {
        ...state.current_revision,
        id: selectionRevisionId,
        aggregate_id: selectionId,
        content: {
          selection_kind: "reference_curve_dataset_revision" as const,
          member_count: 1 as const,
          dataset_id: datasetId,
          dataset_revision_id: normalizedRevisionId,
        },
      },
      links: {},
    };
    const recipe = {
      recipe_id: recipeId,
      recipe_label: "Observed-point crop",
      current_revision: {
        ...state.current_revision,
        id: recipeRevisionId,
        aggregate_id: recipeId,
        content: {
          recipe_kind: "reference_tensile_inclusive_crop" as const,
          step_count: 1 as const,
          minimum_engineering_strain: 0,
          maximum_engineering_strain: 0.02,
          input_schema_ref: "urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0",
          output_schema_ref: "urn:cmp:datasets:reference-tensile-processed-parquet:1.0.0",
          diagnostics_schema_ref: "urn:cmp:processing:reference-tensile-crop-diagnostics:1.0.0",
          boundary_policy: "select_observed_points_inclusive_no_interpolation" as const,
        },
      },
      links: {},
    };
    const curve = (datasetRevisionId: string, representation: "normalized" | "processed") => ({
      dataset_id: representation === "processed" ? processedDatasetId : datasetId,
      dataset_revision_id: datasetRevisionId,
      representation,
      point_count: representation === "processed" ? 3 : 4,
      returned_point_count: representation === "processed" ? 3 : 4,
      sampled: false,
      strain_unit: "1",
      stress_unit: "Pa",
      points: [
        { engineering_strain: 0, engineering_stress: 0 },
        { engineering_strain: 0.01, engineering_stress: 100000000 },
        { engineering_strain: 0.02, engineering_stress: 120000000 },
      ],
    });
    const fetchMock = vi.fn<typeof fetch>((input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/dataset-revisions/") && url.includes("/curve")) {
        return Promise.resolve(jsonResponse(curve(
          url.includes(processedRevisionId) ? processedRevisionId : normalizedRevisionId,
          url.includes(processedRevisionId) ? "processed" : "normalized",
        )));
      }
      if (url.endsWith(`/datasets/${datasetId}/revisions`)) {
        return Promise.resolve(jsonResponse({
          dataset_id: datasetId,
          revisions: [revision(rawRevisionId, "raw", 1), revision(normalizedRevisionId, "normalized", 2)],
        }));
      }
      if (url.endsWith(`/dataset-revisions/${normalizedRevisionId}/selections`)) {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.endsWith("/processing-recipes") && method === "GET") {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.endsWith("/dataset-selections") && method === "POST") {
        return Promise.resolve(jsonResponse(selection));
      }
      if (url.endsWith("/processing-recipes/reference-tensile-crop") && method === "POST") {
        return Promise.resolve(jsonResponse(recipe));
      }
      if (url.endsWith("/processing-runs/reference-tensile-crop") && method === "POST") {
        return Promise.resolve(jsonResponse({
          processing_run_id: runId,
          classification: "internal",
          execution_mode: "committed",
          status: "succeeded",
          selection_id: selectionId,
          selection_revision_id: selectionRevisionId,
          recipe_id: recipeId,
          recipe_revision_id: recipeRevisionId,
          input_dataset_id: datasetId,
          input_dataset_revision_id: normalizedRevisionId,
          input_point_count: 4,
          output_point_count: 3,
          removed_point_count: 1,
          result_artifact_id: "10000000-0000-4000-8000-000000000010",
          result_sha256: "d".repeat(64),
          output_dataset_id: processedDatasetId,
          output_dataset_revision_id: processedRevisionId,
          failure_code: null,
          change_reason: "Create processed Dataset from pinned input and recipe",
          started_at: "2026-07-15T00:00:00Z",
          ended_at: "2026-07-15T00:00:00Z",
          links: {},
        }));
      }
      if (url.includes("/material-states/") && url.endsWith("/datasets")) {
        return Promise.resolve(jsonResponse({ items: [sourceDataset] }));
      }
      return Promise.resolve(jsonResponse({ items: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ReferenceTensileWorkflow
        config={{ baseUrl: "/api/v1", accessToken: "tenant-token" }}
        state={state}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Manage reference tensile data" }));

    await screen.findByText("6. Pin the normalized revision as a Processing Selection");
    fireEvent.click(await screen.findByRole("button", { name: "Create pinned Selection" }));
    await screen.findByRole(
      "combobox",
      { name: "Pinned Selection" },
      { timeout: 3_000 },
    );
    fireEvent.click(screen.getByRole("button", { name: "Create immutable Recipe" }));
    await screen.findByRole("combobox", { name: "Processing Recipe" });
    fireEvent.click(screen.getByRole("button", { name: "Commit crop Processing Run" }));

    await screen.findByText(new RegExp(`Run ${runId.slice(0, 8)}`));
    await screen.findByText("Committed processed SI curve");
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([input, init]) => (
        String(input).endsWith("/processing-runs/reference-tensile-crop")
        && init?.method === "POST"
      ))).toBe(true);
    });
  });

  it("pins two normalized selections, records QC, and scopes append-only outlier review", async () => {
    const firstDatasetId = "20000000-0000-4000-8000-000000000001";
    const secondDatasetId = "20000000-0000-4000-8000-000000000002";
    const firstRevisionId = "20000000-0000-4000-8000-000000000003";
    const secondRevisionId = "20000000-0000-4000-8000-000000000004";
    const firstSelectionId = "20000000-0000-4000-8000-000000000005";
    const secondSelectionId = "20000000-0000-4000-8000-000000000006";
    const firstSelectionRevisionId = "20000000-0000-4000-8000-000000000007";
    const secondSelectionRevisionId = "20000000-0000-4000-8000-000000000008";
    const planId = "20000000-0000-4000-8000-000000000009";
    const planRevisionId = "20000000-0000-4000-8000-00000000000a";
    const statisticalRunId = "20000000-0000-4000-8000-00000000000b";
    const resultId = "20000000-0000-4000-8000-00000000000c";
    const resultRevisionId = "20000000-0000-4000-8000-00000000000d";
    const outlierPlanId = "20000000-0000-4000-8000-000000000019";
    const outlierPlanRevisionId = "20000000-0000-4000-8000-00000000001a";
    const outlierRunId = "20000000-0000-4000-8000-00000000001b";
    const firstCandidateId = "20000000-0000-4000-8000-00000000001c";
    const secondCandidateId = "20000000-0000-4000-8000-00000000001d";
    const assessmentId = "20000000-0000-4000-8000-00000000001e";
    const assessmentRevisionId = "20000000-0000-4000-8000-00000000001f";
    const dataset = (datasetId: string, revisionId: string, testRunId: string) => ({
      dataset_id: datasetId,
      test_run_id: testRunId,
      current_revision: {
        ...state.current_revision,
        id: revisionId,
        aggregate_id: datasetId,
        content: {
          test_run_id: testRunId,
          test_run_revision_id: `${testRunId.slice(0, -1)}f`,
          raw_asset_id: "20000000-0000-4000-8000-00000000000e",
          raw_artifact_id: "20000000-0000-4000-8000-00000000000f",
          data_artifact_id: "20000000-0000-4000-8000-000000000010",
          data_sha256: "b".repeat(64),
          representation: "normalized" as const,
          source_dataset_revision_id: null,
          processing_run_id: null,
          point_count: 3,
          mapping_sha256: "c".repeat(64),
          importer_id: "urn:cmp:datasets:reference-uniaxial-tensile-csv:1.0.0",
          importer_version: "1.0.0",
          reference_only: true as const,
          channels: [],
        },
      },
      links: {},
    });
    const firstDataset = dataset(firstDatasetId, firstRevisionId, "20000000-0000-4000-8000-000000000011");
    const secondDataset = dataset(secondDatasetId, secondRevisionId, "20000000-0000-4000-8000-000000000012");
    const selection = (selectionId: string, revisionId: string, source: typeof firstDataset, label: string) => ({
      selection_id: selectionId,
      selection_label: label,
      current_revision: {
        ...state.current_revision,
        id: revisionId,
        aggregate_id: selectionId,
        content: {
          selection_kind: "reference_curve_dataset_revision" as const,
          member_count: 1 as const,
          dataset_id: source.dataset_id,
          dataset_revision_id: source.current_revision.id,
        },
      },
      links: {},
    });
    const firstSelection = selection(firstSelectionId, firstSelectionRevisionId, firstDataset, "Specimen A");
    const secondSelection = selection(secondSelectionId, secondSelectionRevisionId, secondDataset, "Specimen B");
    const plan = {
      statistical_plan_id: planId,
      plan_label: "Reference tensile pair statistics",
      current_revision: {
        ...state.current_revision,
        id: planRevisionId,
        aggregate_id: planId,
        content: {},
      },
      links: {},
    };
    const outlierPlan = {
      outlier_detection_plan_id: outlierPlanId,
      plan_label: "Review reference pair peak difference",
      current_revision: {
        ...state.current_revision,
        id: outlierPlanRevisionId,
        aggregate_id: outlierPlanId,
        content: {
          plan_kind: "reference_tensile_pair_peak_difference_review",
          detector: "relative_peak_engineering_stress_difference",
          formula_version: "1.0.0",
          statistical_result_id: resultId,
          statistical_result_revision_id: resultRevisionId,
          feature: "peak_engineering_stress_pa",
          relative_peak_difference_threshold: 0.2,
          candidate_policy: "flag_both_pair_members_for_human_review",
          automatic_exclusion: false,
          scope_kind: "reference_pair_analysis",
        },
      },
      links: {},
    };
    const candidate = (candidateId: string, pairPosition: "first" | "second") => ({
      outlier_candidate_id: candidateId,
      detection_run_id: outlierRunId,
      detection_plan_id: outlierPlanId,
      detection_plan_revision_id: outlierPlanRevisionId,
      statistical_result_id: resultId,
      statistical_result_revision_id: resultRevisionId,
      statistical_plan_id: planId,
      statistical_plan_revision_id: planRevisionId,
      selection_id: pairPosition === "first" ? firstSelectionId : secondSelectionId,
      selection_revision_id: pairPosition === "first"
        ? firstSelectionRevisionId
        : secondSelectionRevisionId,
      dataset_id: pairPosition === "first" ? firstDatasetId : secondDatasetId,
      dataset_revision_id: pairPosition === "first" ? firstRevisionId : secondRevisionId,
      pair_position: pairPosition,
      feature: "peak_engineering_stress_pa",
      peak_engineering_stress_pa: pairPosition === "first" ? 120000000 : 150000000,
      peer_peak_engineering_stress_pa: pairPosition === "first" ? 150000000 : 120000000,
      relative_peak_difference: 0.2,
      relative_peak_difference_threshold: 0.2,
      status: "review_required",
      automatic_exclusion: false,
      links: {},
    });
    const firstCandidate = candidate(firstCandidateId, "first");
    const secondCandidate = candidate(secondCandidateId, "second");
    const outlierRun = {
      outlier_detection_run_id: outlierRunId,
      classification: "internal",
      execution_mode: "committed",
      status: "succeeded",
      detection_plan_id: outlierPlanId,
      detection_plan_revision_id: outlierPlanRevisionId,
      statistical_result_id: resultId,
      statistical_result_revision_id: resultRevisionId,
      candidate_count: 2,
      failure_code: null,
      candidates: [firstCandidate, secondCandidate],
      change_reason: "Generate review candidates without deleting source data",
      started_at: "2026-07-17T00:00:00Z",
      ended_at: "2026-07-17T00:00:00Z",
      links: {},
    };
    const assessment = {
      outlier_assessment_id: assessmentId,
      current_revision: {
        ...state.current_revision,
        id: assessmentRevisionId,
        aggregate_id: assessmentId,
        content: {
          candidate_id: firstCandidateId,
          scope_kind: "reference_pair_analysis",
          statistical_plan_id: planId,
          statistical_plan_revision_id: planRevisionId,
          decision: "retained",
          assessment_reason: "Human review retains this candidate for the reference analysis.",
        },
      },
      links: {},
    };
    let assessmentRecorded = false;
    const fetchMock = vi.fn<typeof fetch>((input, init) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/dataset-revisions/") && url.includes("/curve")) {
        const revisionId = url.includes(secondRevisionId) ? secondRevisionId : firstRevisionId;
        return Promise.resolve(jsonResponse({
          dataset_id: revisionId === secondRevisionId ? secondDatasetId : firstDatasetId,
          dataset_revision_id: revisionId,
          representation: "normalized",
          point_count: 3,
          returned_point_count: 3,
          sampled: false,
          strain_unit: "1",
          stress_unit: "Pa",
          points: [
            { engineering_strain: 0, engineering_stress: 0 },
            { engineering_strain: 0.01, engineering_stress: 100000000 },
            { engineering_strain: 0.02, engineering_stress: 120000000 },
          ],
        }));
      }
      if (url.endsWith(`/datasets/${firstDatasetId}/revisions`)) {
        return Promise.resolve(jsonResponse({ dataset_id: firstDatasetId, revisions: [firstDataset.current_revision] }));
      }
      if (url.endsWith(`/dataset-revisions/${firstRevisionId}/selections`)) {
        return Promise.resolve(jsonResponse({ items: [firstSelection] }));
      }
      if (url.endsWith(`/dataset-revisions/${secondRevisionId}/selections`)) {
        return Promise.resolve(jsonResponse({ items: [secondSelection] }));
      }
      if (url.endsWith("/statistical-plans?limit=100") && method === "GET") {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.endsWith("/outlier-detection-plans?limit=100") && method === "GET") {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.endsWith("/statistical-plans/reference-tensile-pair") && method === "POST") {
        return Promise.resolve(jsonResponse(plan));
      }
      if (url.endsWith("/statistical-runs/reference-tensile-pair") && method === "POST") {
        return Promise.resolve(jsonResponse({
          statistical_run_id: statisticalRunId,
          classification: "internal",
          execution_mode: "committed",
          status: "succeeded",
          plan_id: planId,
          plan_revision_id: planRevisionId,
          first_selection_id: firstSelectionId,
          first_selection_revision_id: firstSelectionRevisionId,
          first_dataset_id: firstDatasetId,
          first_dataset_revision_id: firstRevisionId,
          second_selection_id: secondSelectionId,
          second_selection_revision_id: secondSelectionRevisionId,
          second_dataset_id: secondDatasetId,
          second_dataset_revision_id: secondRevisionId,
          sample_count: 2,
          result_id: resultId,
          result_revision_id: resultRevisionId,
          curve_artifact_id: "20000000-0000-4000-8000-000000000013",
          curve_sha256: "d".repeat(64),
          curve_point_count: 3,
          failure_code: null,
          qc_observations: [
            {
              check_code: "distinct_test_runs",
              outcome: "passed",
              detail: "Two distinct Test Run revisions are pinned.",
              expected_point_count: null,
              observed_point_count: null,
              mismatch_index: null,
            },
          ],
          change_reason: "Calculate reference pair scalar statistics and curve band",
          started_at: "2026-07-16T00:00:00Z",
          ended_at: "2026-07-16T00:00:00Z",
          links: {},
        }));
      }
      if (url.endsWith(`/statistical-results/${resultId}`)) {
        return Promise.resolve(jsonResponse({
          statistical_result_id: resultId,
          current_revision: {
            ...state.current_revision,
            id: resultRevisionId,
            aggregate_id: resultId,
            content: {
              scalar: {
                first_peak_engineering_stress_pa: 120000000,
                second_peak_engineering_stress_pa: 140000000,
                mean_engineering_stress_pa: 130000000,
                sample_standard_deviation_engineering_stress_pa: 14142135.6237,
                median_engineering_stress_pa: 130000000,
                median_absolute_deviation_engineering_stress_pa: 10000000,
                interquartile_range_engineering_stress_pa: 10000000,
                minimum_engineering_stress_pa: 120000000,
                maximum_engineering_stress_pa: 140000000,
                coefficient_of_variation: 0.108785658,
                confidence_interval_status: "not_provided_reference_pair",
                quantile_method: "linear_inclusive",
              },
            },
          },
          links: {},
        }));
      }
      if (url.includes(`/statistical-results/${resultId}/curve`)) {
        return Promise.resolve(jsonResponse({
          statistical_result_id: resultId,
          point_count: 3,
          returned_point_count: 3,
          sampled: false,
          strain_unit: "1",
          stress_unit: "Pa",
          points: [
            { engineering_strain: 0, mean_engineering_stress_pa: 0, sample_standard_deviation_engineering_stress_pa: 0, median_engineering_stress_pa: 0, minimum_engineering_stress_pa: 0, maximum_engineering_stress_pa: 0 },
            { engineering_strain: 0.01, mean_engineering_stress_pa: 105000000, sample_standard_deviation_engineering_stress_pa: 7071067.8119, median_engineering_stress_pa: 105000000, minimum_engineering_stress_pa: 100000000, maximum_engineering_stress_pa: 110000000 },
            { engineering_strain: 0.02, mean_engineering_stress_pa: 130000000, sample_standard_deviation_engineering_stress_pa: 14142135.6237, median_engineering_stress_pa: 130000000, minimum_engineering_stress_pa: 120000000, maximum_engineering_stress_pa: 140000000 },
          ],
        }));
      }
      if (url.endsWith("/outlier-detection-plans/reference-tensile-pair") && method === "POST") {
        return Promise.resolve(jsonResponse(outlierPlan));
      }
      if (url.endsWith("/outlier-detection-runs/reference-tensile-pair") && method === "POST") {
        return Promise.resolve(jsonResponse(outlierRun));
      }
      if (url.endsWith("/outlier-assessments/reference-tensile-pair") && method === "POST") {
        assessmentRecorded = true;
        return Promise.resolve(jsonResponse(assessment));
      }
      if (url.includes("/outlier-scope-comparisons/reference-tensile-pair")) {
        return Promise.resolve(jsonResponse({
          detection_plan: outlierPlan,
          statistical_result: {
            statistical_result_id: resultId,
            current_revision: {
              ...state.current_revision,
              id: resultRevisionId,
              aggregate_id: resultId,
              content: {},
            },
            links: {},
          },
          scope_kind: "reference_pair_analysis",
          entries: [
            {
              candidate: firstCandidate,
              assessment_history: assessmentRecorded ? [assessment] : [],
              latest_assessment: assessmentRecorded ? assessment : null,
            },
            {
              candidate: secondCandidate,
              assessment_history: [],
              latest_assessment: null,
            },
          ],
          source_mutation: false,
          derived_selection_created: false,
        }));
      }
      if (url.endsWith("/processing-recipes") && method === "GET") {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url.includes("/material-states/") && url.endsWith("/datasets")) {
        return Promise.resolve(jsonResponse({ items: [firstDataset, secondDataset] }));
      }
      return Promise.resolve(jsonResponse({ items: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ReferenceTensileWorkflow
        config={{ baseUrl: "/api/v1", accessToken: "tenant-token" }}
        state={state}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Manage reference tensile data" }));

    await screen.findByText("9. Compare two pinned selections with reference Statistics/QC");
    await screen.findByRole("button", { name: "Create immutable Statistical Plan" });
    fireEvent.click(screen.getByRole("button", { name: "Create immutable Statistical Plan" }));
    await screen.findByRole("combobox", { name: "Statistical Plan" });
    fireEvent.click(screen.getByRole("button", { name: "Commit Statistical Run" }));

    await screen.findByText("Mean engineering-stress curve");
    expect(screen.getByText(/distinct_test_runs/)).toBeTruthy();
    expect(screen.getByText(/not_provided_reference_pair/)).toBeTruthy();
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([input, init]) => (
        String(input).endsWith("/statistical-runs/reference-tensile-pair")
        && init?.method === "POST"
      ))).toBe(true);
    });
    await screen.findByText("10. Review pair-difference candidates without deleting data");
    fireEvent.click(screen.getByRole("button", { name: "Create immutable Outlier Detection Plan" }));
    await screen.findByRole("combobox", { name: "Outlier Detection Plan" });
    fireEvent.click(screen.getByRole("button", { name: "Commit Outlier Detection Run" }));
    await screen.findByRole("combobox", { name: "Outlier candidate" });
    fireEvent.click(screen.getByRole("button", { name: "Append human Assessment" }));
    await screen.findByText(/Human review retains this candidate for the reference analysis/);
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([input, init]) => (
        String(input).endsWith("/outlier-assessments/reference-tensile-pair")
        && init?.method === "POST"
      ))).toBe(true);
    });
  });
});
