import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  MaterialStateResponse,
  RevisionMetadata,
  ShearRelaxationDatasetResponse,
  TestRunResponse,
} from "./types";
import { ViscoelasticMasterWorkbench } from "./viscoelastic-master-workbench";

const ids = Array.from({ length: 20 }, (_, index) =>
  `e2000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
);

function metadata(id: string, aggregate = id): RevisionMetadata {
  return {
    id,
    aggregate_id: aggregate,
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:test:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-08-18T00:00:00Z",
    created_by: ids[18],
    change_reason: "fixture",
    organization_id: ids[16],
    project_id: ids[17],
    classification: "internal",
    lifecycle_state: "draft",
  };
}

const state = {
  material_state_id: ids[0],
  material_id: ids[1],
  current_revision: {
    ...metadata(ids[2], ids[0]),
    content: {
      material_id: ids[1],
      material_revision_id: ids[3],
      name: "Polymer state",
      manufacturing_route: null,
      heat_treatment: null,
      lot_or_batch: null,
      description: null,
    },
    provenance: {
      entity_type: "catalog.material_state.revision",
      reference_type: "catalog.material_state.revision",
      revision_id: ids[2],
      content_sha256: "a".repeat(64),
      based_on_revision_id: null,
      recorded_at: "2026-08-18T00:00:00Z",
      recorded_by: ids[18],
    },
  },
  property_sets_url: `/api/v1/material-states/${ids[0]}/property-sets`,
} satisfies MaterialStateResponse;

function run(index: number, temperature: number): TestRunResponse {
  const runId = ids[4 + index * 2];
  const revisionId = ids[5 + index * 2];
  return {
    test_run_id: runId,
    specimen_id: ids[12 + index],
    test_method_id: ids[15],
    current_revision: {
      ...metadata(revisionId, runId),
      content: {
        specimen_id: ids[12 + index],
        specimen_revision_id: ids[14 + index],
        test_method_id: ids[15],
        test_method_revision_id: ids[19],
        run_label: `${temperature} K replicate`,
        performed_at: "2026-08-18T00:00:00Z",
        test_temperature_k: temperature,
        crosshead_speed_mm_per_min: null,
        reference_only: true,
      },
    },
    links: {},
  };
}

const runs = [run(0, 293.15), run(1, 313.15)];

function dataset(index: number): ShearRelaxationDatasetResponse {
  const datasetId = ids[8 + index * 2];
  const revisionId = ids[9 + index * 2];
  const testRun = runs[index];
  return {
    dataset_id: datasetId,
    material_state_id: ids[0],
    current_revision: {
      ...metadata(revisionId, datasetId),
      content: {
        material_state_id: ids[0],
        material_state_revision_id: ids[2],
        test_run_id: testRun.test_run_id,
        test_run_revision_id: testRun.current_revision.id,
        raw_asset_id: ids[12],
        raw_artifact_id: ids[13],
        data_artifact_id: ids[14],
        data_sha256: "b".repeat(64),
        representation: "normalized",
        source_dataset_revision_id: ids[3],
        processing_run_id: null,
        point_count: 31,
        time_column: "time",
        shear_modulus_column: "modulus",
        time_original_unit: "s",
        shear_modulus_original_unit: "Pa",
        normalized_time_unit: "s",
        normalized_shear_modulus_unit: "Pa",
        importer_id: "fixture",
        importer_version: "1.0.0",
      },
    },
    links: {},
  };
}

function response(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("Viscoelastic master-curve workbench", () => {
  it("pins replicates and displays shift, n, band and master-curve evidence", async () => {
    const selection = {
      selection_id: ids[1],
      current_revision: metadata(ids[2], ids[1]),
    };
    const plan = {
      plan_id: ids[3],
      current_revision: metadata(ids[4], ids[3]),
    };
    const runResponse = {
      processing_run_id: ids[5],
      status: "succeeded",
    };
    const preview = {
      run: {
        ...runResponse,
        classification: "internal",
        plan_id: ids[3],
        plan_revision_id: ids[4],
        selection_id: ids[1],
        selection_revision_id: ids[2],
        source_curve_count: 2,
        temperature_count: 2,
        aligned_row_count: 62,
        statistics_row_count: 62,
        master_row_count: 31,
        aligned_dataset_id: ids[6],
        aligned_dataset_revision_id: ids[7],
        statistics_dataset_id: ids[8],
        statistics_dataset_revision_id: ids[9],
        master_dataset_id: ids[10],
        master_dataset_revision_id: ids[11],
        wlf_c1: null,
        wlf_c2_k: null,
        shift_factors: [
          { temperature_k: 293.15, log10_a_t: 0, source: "reference", observed_log10_a_t: null, residual_log10_a_t: null, alignment_rmse_pa: null },
          { temperature_k: 313.15, log10_a_t: -1, source: "manual", observed_log10_a_t: null, residual_log10_a_t: null, alignment_rmse_pa: null },
        ],
        failure_code: null,
        started_at: "2026-08-18T00:00:00Z",
        ended_at: "2026-08-18T00:00:01Z",
        links: {},
      },
      reference_temperature_k: 293.15,
      aligned_curves: [293.15, 313.15].map((temperature, index) => ({
        member_ordinal: index,
        dataset_revision_id: dataset(index).current_revision.id,
        test_run_revision_id: runs[index].current_revision.id,
        temperature_k: temperature,
        outlier_status: "not_assessed",
        points: [{ time_s: 1, shear_modulus_pa: 10_000_000 - index * 100_000 }, { time_s: 10, shear_modulus_pa: 8_000_000 - index * 100_000 }],
      })),
      temperature_statistics: [293.15, 313.15].map((temperature) => ({
        temperature_k: temperature,
        replicate_count: 1,
        points: [{ time_s: 1, replicate_count: 1, mean_shear_modulus_pa: 10_000_000, sample_standard_deviation_pa: null, median_shear_modulus_pa: 10_000_000, minimum_shear_modulus_pa: 10_000_000, maximum_shear_modulus_pa: 10_000_000 }],
      })),
      master_curve: [{ reduced_time_s: 1, contributing_curve_count: 2, mean_shear_modulus_pa: 10_000_000, sample_standard_deviation_pa: 100_000, minimum_shear_modulus_pa: 9_900_000, maximum_shear_modulus_pa: 10_100_000 }, { reduced_time_s: 10, contributing_curve_count: 2, mean_shear_modulus_pa: 8_000_000, sample_standard_deviation_pa: 100_000, minimum_shear_modulus_pa: 7_900_000, maximum_shear_modulus_pa: 8_100_000 }],
      policy: { interpolation: "piecewise_linear_log_time", domain: "common_intersection_no_extrapolation", reduced_time: "time_divided_by_a_t" },
    };
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (url) => {
      const path = String(url);
      if (path.endsWith("/viscoelastic-selections")) return response(selection);
      if (path.endsWith("/processing-plans/viscoelastic-master-curve")) return response(plan);
      if (path.endsWith("/processing-runs/viscoelastic-master-curve")) return response(runResponse);
      return response(preview);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ViscoelasticMasterWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        state={state}
        datasets={[dataset(0), dataset(1)]}
        runs={runs}
      />,
    );
    screen.getAllByRole("checkbox").forEach((checkbox) => fireEvent.click(checkbox));
    fireEvent.change(screen.getByLabelText("Reference temperature (K)"), {
      target: { value: "293.15" },
    });
    fireEvent.change(screen.getByLabelText("log10(aT) · 313.15 K"), {
      target: { value: "-1" },
    });
    fireEvent.click(
      screen.getByRole("button", {
        name: "Create Selection, process statistics and master curve",
      }),
    );

    expect(await screen.findByTestId("viscoelastic-master-result")).toBeTruthy();
    expect(screen.getByText(/Three immutable outputs committed/i)).toBeTruthy();
    expect(screen.getByRole("img", { name: /shifted shear relaxation/i })).toBeTruthy();
    expect(screen.getAllByText("not assessed").length).toBeGreaterThan(0);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
  });
});
