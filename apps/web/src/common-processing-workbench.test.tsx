import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CommonProcessingWorkbench } from "./common-processing-workbench";

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json", ...headers }),
    json: async () => body,
  } as Response;
}

const revision = {
  id: "53000000-0000-4000-8000-000000000001",
  aggregate_id: "53000000-0000-4000-8000-000000000002",
  revision_no: 1,
  based_on_revision_id: null,
  schema_id: "urn:cmp:test-data:1.0.0",
  schema_version: "1.0.0",
  content_hash: "a".repeat(64),
  created_at: "2026-07-18T00:00:00Z",
  created_by: "53000000-0000-4000-8000-000000000003",
  change_reason: "demo",
  organization_id: "53000000-0000-4000-8000-000000000004",
  project_id: "53000000-0000-4000-8000-000000000005",
  classification: "internal",
  lifecycle_state: "draft",
};

const documentResource = {
  test_data_document_id: "53000000-0000-4000-8000-000000000002",
  current_revision: revision,
  document_key: "DP600-TENSILE-01",
  material_maker: "CMP Demo Metals",
  material_grade: "DP600",
  lot_batch: null,
  test_date: "2026-07-18",
  operator: "Tester",
  laboratory: "Lab",
  method: "tensile",
  specimen_id: "S-1",
  point_count: 3,
  canonical_artifact_id: "53000000-0000-4000-8000-000000000006",
  canonical_sha256: "b".repeat(64),
  normalized_artifact_id: "53000000-0000-4000-8000-000000000007",
  normalized_sha256: "c".repeat(64),
  channels: [
    {
      key: "engineering_strain",
      name: "Engineering strain",
      quantity_semantics: "mechanics.strain.engineering",
      axis_role: "independent",
      original_unit_string: "%",
      normalized_unit: "1",
      point_count: 3,
      missing_count: 0,
    },
    {
      key: "engineering_stress",
      name: "Engineering stress",
      quantity_semantics: "mechanics.stress.engineering",
      axis_role: "dependent",
      original_unit_string: "MPa",
      normalized_unit: "Pa",
      point_count: 3,
      missing_count: 0,
    },
  ],
};

const replicateResource = {
  ...documentResource,
  test_data_document_id: "53000000-0000-4000-8000-000000000012",
  current_revision: {
    ...revision,
    id: "53000000-0000-4000-8000-000000000011",
    aggregate_id: "53000000-0000-4000-8000-000000000012",
    content_hash: "f".repeat(64),
  },
  document_key: "DP600-TENSILE-02",
  specimen_id: "S-2",
  canonical_artifact_id: "53000000-0000-4000-8000-000000000016",
  canonical_sha256: "1".repeat(64),
  normalized_artifact_id: "53000000-0000-4000-8000-000000000017",
  normalized_sha256: "2".repeat(64),
};

const documentJson = {
  document_type: "cmp.test-data",
  schema_version: "1.0.0",
  document_id: "DP600-TENSILE-01",
};

const mappingProfileResource = {
  mapping_profile_id: "53000000-0000-4000-8000-000000000020",
  current_revision: {
    ...revision,
    id: "53000000-0000-4000-8000-000000000021",
    aggregate_id: "53000000-0000-4000-8000-000000000020",
    content_hash: "e".repeat(64),
  },
  content: {
    profile_key: "demo-metal-tensile",
    label: "Demo metal tensile mapping",
    independent_quantity: "strain.engineering",
    missing_data_policy: "drop_any",
    bindings: [
      {
        channel_key: "engineering_strain",
        target_quantity: "strain.engineering",
        accepted_normalized_units: ["1"],
        required: true,
        scale: 1,
        offset: 0,
      },
      {
        channel_key: "engineering_stress",
        target_quantity: "stress.engineering",
        accepted_normalized_units: ["Pa"],
        required: true,
        scale: 1,
        offset: 0,
      },
    ],
    attribute_bindings: [],
  },
};

describe("Common Processing Workbench", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("loads exact Test Data and renders server stage overlays", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource, replicateResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: [] });
      if (url.endsWith("/common-processing-recipes")) return jsonResponse({ items: [] });
      if (url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-ensemble-methods")) {
        return jsonResponse({
          items: [
            {
              method_id: "curves.align_linear_intersection",
              version: "1.0.0",
              label: "Align curves on observed intersection",
              description: "Linear interpolation without extrapolation",
              option_schema: {},
              deterministic: true,
              allows_extrapolation: false,
            },
            {
              method_id: "curves.pointwise_statistics",
              version: "1.0.0",
              label: "Pointwise replicate statistics",
              description: "Mean, median, sample SD, MAD, IQR, and 95% mean CI",
              option_schema: {},
              deterministic: true,
              allows_extrapolation: false,
            },
          ],
        });
      }
      if (url.endsWith("/processing-methods")) {
        return jsonResponse({
          items: [
            {
              method_id: "rows.sort_unique",
              version: "1.0.0",
              label: "Sort and resolve duplicate x values",
              description: "Explicit duplicate policy",
              option_schema: {},
              deterministic: true,
              allows_extrapolation: false,
            },
          ],
        });
      }
      if (url.includes("/content")) {
        return {
          ok: true,
          status: 200,
          headers: new Headers({
            "content-type": "application/vnd.cmp.test-data+json",
            "content-disposition": 'attachment; filename="demo.json"',
          }),
          blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
        } as Response;
      }
      if (url.endsWith("/processing:preview") && init?.method === "POST") {
        return jsonResponse({
          execution_mode: "preview",
          promotable: false,
          source_document_sha256: "d".repeat(64),
          mapping_profile_sha256: "e".repeat(64),
          independent_quantity: "strain.engineering",
          stages: [
            {
              ordinal: 0,
              method_id: "mapping",
              method_version: "1.0.0",
              point_count: 3,
              series: [
                { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
              ],
              diagnostics: ["canonical normalized values mapped"],
              scalar_results: [],
            },
            {
              ordinal: 1,
              method_id: "rows.sort_unique",
              method_version: "1.0.0",
              point_count: 3,
              series: [
                { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
              ],
              diagnostics: ["input rows sorted by independent quantity"],
              scalar_results: [
                {
                  key: "youngs_modulus",
                  quantity_semantics: "modulus.young",
                  value: 210e9,
                  unit: "Pa",
                },
              ],
            },
            {
              ordinal: 2,
              method_id: "metal.elastic_modulus",
              method_version: "1.0.0",
              point_count: 3,
              series: [
                { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
              ],
              diagnostics: ["robust elastic fit calculated"],
              scalar_results: [],
            },
            {
              ordinal: 3,
              method_id: "metal.proof_stress",
              method_version: "1.0.0",
              point_count: 3,
              series: [
                { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
              ],
              diagnostics: [],
              scalar_results: [],
            },
            {
              ordinal: 4,
              method_id: "metal.necking_candidate",
              method_version: "1.0.0",
              point_count: 3,
              series: [
                { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
              ],
              diagnostics: [],
              scalar_results: [],
            },
            {
              ordinal: 5,
              method_id: "metal.engineering_to_true_plastic",
              method_version: "1.0.0",
              point_count: 3,
              series: [
                { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
              ],
              diagnostics: [],
              scalar_results: [],
            },
            {
              ordinal: 6,
              method_id: "metal.hardening_fit_extrapolate",
              method_version: "1.0.0",
              point_count: 3,
              series: [
                { quantity: "strain.true_plastic", unit: "1", values: [0, 0.25, 0.5] },
                { quantity: "stress.hardening.voce", unit: "Pa", values: [3e8, 5e8, 5.5e8] },
                { quantity: "stress.hardening.swift", unit: "Pa", values: [3.1e8, 5.2e8, 6e8] },
                { quantity: "stress.hardening.selected", unit: "Pa", values: [3.05e8, 5.1e8, 5.75e8] },
              ],
              diagnostics: ["extrapolated domain (0.1, 0.5] is not observed"],
              scalar_results: [
                {
                  key: "voce.relative_rmse",
                  quantity_semantics: "statistics.relative_rmse",
                  value: 0.012,
                  unit: "1",
                },
              ],
            },
          ],
        });
      }
      if (url.endsWith("/processing:preview-ensemble") && init?.method === "POST") {
        return jsonResponse({
          execution_mode: "preview",
          promotable: false,
          mapping_profile_sha256: "e".repeat(64),
          independent_quantity: "strain.engineering",
          grid_unit: "1",
          grid: [0, 0.001, 0.002],
          members: [
            {
              ordinal: 0,
              source_document_sha256: "d".repeat(64),
              stage: {
                ordinal: 1,
                method_id: "curves.align_linear_intersection",
                method_version: "1.0.0",
                point_count: 3,
                series: [
                  { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                  { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
                ],
                diagnostics: [],
              },
            },
            {
              ordinal: 1,
              source_document_sha256: "3".repeat(64),
              stage: {
                ordinal: 1,
                method_id: "curves.align_linear_intersection",
                method_version: "1.0.0",
                point_count: 3,
                series: [
                  { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
                  { quantity: "stress.engineering", unit: "Pa", values: [0, 2.2e8, 3.2e8] },
                ],
                diagnostics: [],
              },
            },
          ],
          statistics: [
            {
              quantity: "stress.engineering",
              unit: "Pa",
              mean: [0, 2.1e8, 3.1e8],
              median: [0, 2.1e8, 3.1e8],
              standard_deviation: [0, 1.414e7, 1.414e7],
              mad: [0, 1e7, 1e7],
              q1: [0, 2.05e8, 3.05e8],
              q3: [0, 2.15e8, 3.15e8],
              confidence_95_lower: [0, 1.904e8, 2.904e8],
              confidence_95_upper: [0, 2.296e8, 3.296e8],
            },
          ],
          diagnostics: ["2 member curves retained", "sample standard deviation uses n - 1"],
        });
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Test curves to material model" })).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Material Modeling steps" })).toBeTruthy();
    expect(screen.getByRole("tablist", { name: "Material modeling family" })).toBeTruthy();
    expect(await screen.findByRole("img", { name: "Hardening candidate and selected extrapolation curves" })).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: /Polymer/ }));
    expect((screen.getByLabelText("Mapping Profile JSON") as HTMLTextAreaElement).value).toContain(
      '"profile_key": "polymer-shear-relaxation"',
    );
    expect((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value).toContain(
      '"method_id": "polymer.prony_fit_compare"',
    );
    fireEvent.click(screen.getByRole("tab", { name: /Metal/ }));
    expect((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value).toContain(
      '"method_id": "metal.hardening_fit_extrapolate"',
    );
    fireEvent.click(screen.getByRole("button", { name: /Recipe/ }));
    expect(screen.getByLabelText("Saved Processing Recipe")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Batch/ }));
    expect(screen.getByLabelText("Processing Batch label")).toBeTruthy();
    expect((await screen.findAllByText("DP600-TENSILE-01 · r1")).length).toBeGreaterThanOrEqual(2);
    fireEvent.change(screen.getByLabelText("Test Data revision"), {
      target: { value: documentResource.test_data_document_id },
    });
    fireEvent.click(screen.getByRole("button", { name: "Load exact JSON" }));
    expect(await screen.findByText(/Loaded exact Test Data revision 1/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    expect(await screen.findByText("Preview only · not committed")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Hardening candidate and selected extrapolation curves" })).toBeTruthy();
    expect(screen.getByText("Selected combination")).toBeTruthy();
    expect(screen.getByText("voce relative rmse")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /1rows\.sort_unique/ }));
    expect(screen.getByRole("img", { name: "Mapped and selected processing stage curve overlay" })).toBeTruthy();
    expect(screen.getByText("input rows sorted by independent quantity")).toBeTruthy();
    expect(screen.getByText("210.000 GPa")).toBeTruthy();

    fireEvent.click(screen.getAllByRole("button", { name: /metal\.elastic_modulus/ })[0]);
    const elasticPlot = screen.getByRole("img", { name: "Mapped and selected processing stage curve overlay" });
    Object.defineProperty(elasticPlot, "getBoundingClientRect", {
      value: () => ({ left: 0, top: 0, right: 760, bottom: 420, width: 760, height: 420, x: 0, y: 0, toJSON: () => ({}) }),
    });
    fireEvent.click(screen.getByRole("button", { name: "Select range" }));
    fireEvent.pointerDown(elasticPlot, { button: 0, pointerId: 2, clientX: 100, clientY: 200 });
    fireEvent.pointerMove(elasticPlot, { pointerId: 2, clientX: 160, clientY: 200 });
    fireEvent.pointerUp(elasticPlot, { pointerId: 2, clientX: 160, clientY: 200 });
    fireEvent.click(screen.getByRole("button", { name: "Apply selection" }));
    const appliedSteps = JSON.parse((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value) as Array<{ method_id: string; options: Record<string, number> }>;
    expect(appliedSteps[1].method_id).toBe("metal.elastic_modulus");
    expect(appliedSteps[1].options.minimum_strain).not.toBe(0.0002);
    expect(screen.getByText(/Applied the graph range to metal.elastic_modulus/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Align and calculate" }));
    expect(await screen.findByRole("img", { name: "Aligned replicate curves with pointwise mean and confidence interval" })).toBeTruthy();
    expect(screen.getByText("Members (2)")).toBeTruthy();
    expect(screen.getByText("sample standard deviation uses n - 1")).toBeTruthy();
  });
});
