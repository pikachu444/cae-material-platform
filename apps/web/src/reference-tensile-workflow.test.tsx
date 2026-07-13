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
    expect(screen.getByText(/Column names are never inferred/)).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(4);
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
          selection_kind: "reference_normalized_dataset_revision" as const,
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
    await screen.findByRole("combobox", { name: "Pinned Selection" });
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
});
