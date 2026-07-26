import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  CommonProcessingWorkbench,
  manualModulusDisplayValue,
  manualModulusPascals,
} from "./common-processing-workbench";

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

describe("manual Young's modulus unit conversion", () => {
  it("stores GPa input in canonical Pa", () => {
    expect(manualModulusPascals(205, "GPa")).toBe(205_000_000_000);
    expect(manualModulusDisplayValue(205_000_000_000, "GPa")).toBe(205);
  });

  it("stores MPa input in the same canonical Pa", () => {
    expect(manualModulusPascals(205_000, "MPa")).toBe(205_000_000_000);
    expect(manualModulusDisplayValue(205_000_000_000, "MPa")).toBe(205_000);
  });
});

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
    const committedOutputs: Array<Record<string, unknown>> = [];
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource, replicateResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-outputs") && init?.method === "POST") {
        const output = {
          processing_output_id: "53000000-0000-4000-8000-000000000030",
          current_revision: {
            ...revision,
            id: "53000000-0000-4000-8000-000000000031",
            aggregate_id: "53000000-0000-4000-8000-000000000030",
          },
          label: "DP600 · swift selected fit",
          source_document: {
            aggregate_id: documentResource.test_data_document_id,
            revision_id: revision.id,
          },
          mapping_profile: {
            aggregate_id: mappingProfileResource.mapping_profile_id,
            revision_id: mappingProfileResource.current_revision.id,
          },
          steps: [{
            method_id: "metal.hardening_fit_extrapolate",
            method_version: "1.0.0",
            options: { primary_family: "swift" },
          }],
          output_sha256: "9".repeat(64),
          final_point_count: 3,
          stage_count: 6,
        };
        committedOutputs.splice(0, committedOutputs.length, output);
        return jsonResponse(output, 201);
      }
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: committedOutputs });
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
                { key: "swift.relative_rmse", quantity_semantics: "statistics.relative_rmse", value: 0.01, unit: "1" },
                { key: "swift.parameter.K", quantity_semantics: "model.parameter.K", value: 5e8, unit: "Pa" },
                { key: "swift.parameter.K.lower", quantity_semantics: "model.parameter.bound.lower.K", value: 1, unit: "Pa" },
                { key: "swift.parameter.K.upper", quantity_semantics: "model.parameter.bound.upper.K", value: 1e9, unit: "Pa" },
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

    const onSessionChange = vi.fn();
    const onSessionEvent = vi.fn();
    const onNewSession = vi.fn();
    const onNavigate = vi.fn();
    const materialA = {
      material_id: "material-a",
      current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } },
    };
    const stateA = {
      material_state_id: "state-a",
      current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } },
    };
    const sessionA = {
      version: 3,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Create a card",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: { id: documentResource.test_data_document_id, revisionId: revision.id, label: documentResource.document_key, revisionNo: 1 },
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      workspace: { activeStage: "data", selectedDocumentIds: [], selectedStepIndex: 0, selectedStageOrdinal: 0, plotView: "pipeline", settingsOpen: true },
    };
    const view = render(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        onNavigate={onNavigate}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
        onSessionEvent={onSessionEvent}
        onNewSession={onNewSession}
        initialSession={sessionA as never}
        material={materialA as never}
        materialState={stateA as never}
        familyWorkbench={<div>Exact Neutral and solver delivery fixture</div>}
      />,
    );

    expect(await screen.findByRole("banner", { name: "Modeling context" })).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Material Modeling steps" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Card" })).toBeNull();
    expect(screen.getByRole("tablist", { name: "Material modeling family" })).toBeTruthy();
    expect(await screen.findByRole(
      "img",
      { name: "Hardening candidate and selected extrapolation curves" },
      { timeout: 5000 },
    )).toBeTruthy();
    expect(screen.queryByText("Test data")).toBeNull();
    const settingsControl = screen.getByRole("button", { name: /current-stage settings/ });
    expect(settingsControl).toBeTruthy();
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:data" } }));
    expect(await screen.findByRole("tablist", { name: "Test data source" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Library" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Local file" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Test Data JSON" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Verify source & channel mapping" })).toBeTruthy();
    expect(screen.queryByText("Metal hardening candidates")).toBeNull();
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:validate" } }));
    expect(await screen.findByRole("heading", { name: "Validation, review and release" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Submit · Not configured" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Release · Not configured" }).hasAttribute("disabled")).toBe(true);
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:data" } }));
    fireEvent.click(screen.getByRole("tab", { name: /Polymer/ }));
    expect((screen.getByLabelText("Mapping Profile JSON") as HTMLTextAreaElement).value).toContain(
      '"profile_key": "polymer-shear-relaxation"',
    );
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:fit" } }));
    expect((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value).toContain(
      '"method_id": "polymer.prony_fit_compare"',
    );
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:data" } }));
    fireEvent.click(screen.getByRole("tab", { name: /Metal/ }));
    fireEvent.change(screen.getByLabelText("Test Data revision"), {
      target: { value: documentResource.test_data_document_id },
    });
    fireEvent.click(screen.getByRole("button", { name: "Load exact JSON" }));
    expect(await screen.findByText(/Loaded exact Test Data revision 1/)).toBeTruthy();
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:fit" } }));
    expect(await screen.findByRole(
      "img",
      { name: "Hardening candidate and selected extrapolation curves" },
      { timeout: 5000 },
    )).toBeTruthy();
    expect((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value).toContain(
      '"method_id": "metal.hardening_fit_extrapolate"',
    );
    if (settingsControl.getAttribute("aria-expanded") === "false") fireEvent.click(settingsControl);
    fireEvent.click(screen.getByText("Advanced · Recipe and Batch"));
    fireEvent.click(screen.getByRole("button", { name: /Recipe/ }));
    expect(screen.getByLabelText("Saved Processing Recipe")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Batch/ }));
    expect(screen.getByLabelText("Processing Batch label")).toBeTruthy();
    expect((await screen.findAllByText("DP600-TENSILE-01 · r1")).length).toBeGreaterThanOrEqual(1);
    fireEvent.click(screen.getByRole("button", { name: "Update candidates" }));
    expect(await screen.findByText("Preview only · not committed")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Hardening candidate and selected extrapolation curves" })).toBeTruthy();
    expect(screen.getByText("Preview blend · swift + voce · fitted domain")).toBeTruthy();
    expect(screen.getByText("voce relative rmse")).toBeTruthy();
    expect(await screen.findByRole("columnheader", { name: "Recommendation" })).toBeTruthy();
    expect((screen.getByRole("button", { name: "Save selected candidate" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: /Select swift candidate/i }));
    expect(screen.getByText("Selected · swift · fitted domain")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Candidate selection reason"), {
      target: { value: "Select Swift after comparing response, residual and tangent stability." },
    });
    expect((screen.getByRole("button", { name: "Save selected candidate" }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Update candidates" }));
    await waitFor(() => {
      expect((screen.getByRole("button", { name: "Save selected candidate" }) as HTMLButtonElement).disabled).toBe(true);
      expect(screen.queryByLabelText("Candidate selection reason")).toBeNull();
    });
    fireEvent.click(screen.getByRole("button", { name: /Select swift candidate/i }));
    fireEvent.change(screen.getByLabelText("Candidate selection reason"), {
      target: { value: "Re-select Swift after the successful candidate recomputation." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save selected candidate" }));
    expect(await screen.findByRole("heading", { name: "Inspect exact source & solver export" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Export is unavailable" })).toBeTruthy();
    expect(screen.getByText("Server provenance proof")).toBeTruthy();
    expect(screen.getByText(/stale, different-material, or unverified output is never used as a fallback/i)).toBeTruthy();
    expect(onSessionChange).toHaveBeenCalledWith({
      processingOutput: {
        id: "53000000-0000-4000-8000-000000000030",
        revisionId: "53000000-0000-4000-8000-000000000031",
        label: "DP600 · swift selected fit",
        revisionNo: 1,
      },
    });
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:process" } }));
    expect(screen.getByRole("heading", { name: "Prepare observed curves" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save processed curves" })).toBeTruthy();
    expect(screen.getByText("Test data")).toBeTruthy();
    expect(screen.getByText("2 curves · 2 included")).toBeTruthy();
    const curveRow = screen.getByTitle("DP600-TENSILE-01 · S-1 · exact revision r1");
    expect(curveRow.getAttribute("title")).toContain("DP600-TENSILE-01");
    const includeSpecimen = screen.getByRole("checkbox", { name: "Include Specimen 01 in processing and fit" });
    const plotVisibility = screen.getByRole("button", { name: "Hide Specimen 01 on plot" });
    expect(plotVisibility.getAttribute("aria-pressed")).toBe("true");
    expect(screen.queryByText(/^Hide$/)).toBeNull();
    fireEvent.click(plotVisibility);
    expect(screen.getByRole("button", { name: "Show Specimen 01 on plot" }).getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(includeSpecimen);
    expect((includeSpecimen as HTMLInputElement).checked).toBe(false);
    expect(onSessionEvent).toHaveBeenCalledWith({ type: "CHANGE_SELECTION" });
    fireEvent.click(includeSpecimen);
    expect((includeSpecimen as HTMLInputElement).checked).toBe(true);
    expect(screen.queryByText("Fit evidence")).toBeNull();
    fireEvent.click(screen.getByRole("button", {
      name: /1Sort and resolve duplicate x values3 points/,
    }));
    expect(screen.getByRole("img", { name: "Mapped and selected processing stage curve overlay" })).toBeTruthy();
    expect(screen.getByText("input rows sorted by independent quantity")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /2Young's modulus1\.0\.0/ }));
    expect(screen.getByRole("button", { name: "Auto robust" }).className).toContain("active");
    fireEvent.click(screen.getByRole("button", { name: "Manual slope" }));
    fireEvent.change(screen.getByLabelText("Manual Young's modulus"), { target: { value: "205" } });
    expect(screen.getByLabelText("Manual Young's modulus unit")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Manual Young's modulus reason"), { target: { value: "Reconcile the measured elastic range." } });
    expect(onSessionEvent).toHaveBeenCalledWith({ type: "CHANGE_PROCESS" });
    const guidedSteps = JSON.parse((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value) as Array<{ method_id: string; options: Record<string, unknown> }>;
    expect(guidedSteps[1].options.method).toBe("manual");
    expect(guidedSteps[1].options.manual_modulus_pa).toBe(205_000_000_000);
    await screen.findByRole("img", { name: "Mapped and selected processing stage curve overlay" });
    fireEvent.click(screen.getByRole("button", { name: /2Young's modulus1\.0\.0/ }));
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

    fireEvent.click(screen.getByRole("button", { name: "Update preview" }));
    await screen.findByRole("img", { name: "Mapped and selected processing stage curve overlay" });
    fireEvent.click(screen.getByRole("button", { name: /4Necking candidate1\.0\.0/ }));
    const neckingPlot = screen.getByRole("img", { name: "Mapped and selected processing stage curve overlay" });
    Object.defineProperty(neckingPlot, "getBoundingClientRect", {
      value: () => ({ left: 0, top: 0, right: 760, bottom: 420, width: 760, height: 420, x: 0, y: 0, toJSON: () => ({}) }),
    });
    fireEvent.click(screen.getByRole("button", { name: "Pick point" }));
    fireEvent.pointerDown(neckingPlot, { button: 0, pointerId: 3, clientX: 620, clientY: 180 });
    fireEvent.pointerUp(neckingPlot, { pointerId: 3, clientX: 620, clientY: 180 });
    fireEvent.click(screen.getByRole("button", { name: "Apply selection" }));
    const neckingSteps = JSON.parse((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value) as Array<{ method_id: string; options: Record<string, unknown> }>;
    expect(neckingSteps[4].method_id).toBe("metal.engineering_to_true_plastic");
    expect(neckingSteps[4].options.necking_policy).toBe("manual_index");
    expect(Number(neckingSteps[4].options.manual_necking_index)).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Applied the graph point to the downstream plastic Workup/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Align and calculate" }));
    expect(await screen.findByRole("img", { name: "Aligned replicate curves with pointwise mean and confidence interval" })).toBeTruthy();
    expect(screen.getByText("Members (2)")).toBeTruthy();
    expect(screen.getByText("sample standard deviation uses n - 1")).toBeTruthy();
    const ensembleRequest = fetchMock.mock.calls.find(([input]) => String(input).endsWith("/processing:preview-ensemble"));
    const ensembleBody = JSON.parse(String(ensembleRequest?.[1]?.body)) as { preprocessing_steps: Array<{ method_id: string }> };
    expect(ensembleBody.preprocessing_steps.map((step) => step.method_id)).toEqual(["rows.sort_unique"]);
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:export" } }));
    expect(screen.getByRole("heading", { name: "Inspect exact source & solver export" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Export is unavailable" })).toBeTruthy();
    expect(screen.queryByText("Test data")).toBeNull();
    expect(screen.queryByLabelText("Resize curve and process navigator")).toBeNull();
    expect(screen.queryByRole("button", { name: "Mean & band" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Replicate statistics" })).toBeNull();
    expect(document.querySelector(".persistent-modeling-plot")).toBeTruthy();
    expect(screen.queryByText("Exact Neutral and solver delivery fixture")).toBeNull();
    expect(document.querySelector("#modeling-process:not([hidden]) .persistent-modeling-plot")).toBeTruthy();
    expect(screen.getByText("Selection reason")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Back to Fit" }));
    expect(screen.queryByRole("img", { name: "Aligned replicate curves with pointwise mean and confidence interval" })).toBeNull();
    onSessionChange.mockClear();
    view.rerender(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        onNavigate={onNavigate}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
        onNewSession={onNewSession}
        initialSession={{
          ...sessionA,
          material: { id: "material-b", revisionId: "material-b-r1", label: "DP600 B", revisionNo: 1 },
          materialState: { id: "state-b", revisionId: "state-b-r1", label: "Aged", revisionNo: 1 },
          testData: undefined,
          mappingProfile: undefined,
          recipe: undefined,
          processingOutput: undefined,
        } as never}
        material={{ ...materialA, material_id: "material-b", current_revision: { ...materialA.current_revision, id: "material-b-r1", content: { name: "DP600 B" } } } as never}
        materialState={{ ...stateA, material_state_id: "state-b", current_revision: { ...stateA.current_revision, id: "state-b-r1", content: { name: "Aged" } } } as never}
        familyWorkbench={<div>Exact Neutral and solver delivery fixture</div>}
      />,
    );
    await screen.findByText(/Material context changed\. Choose an exact Test Data revision/i);
    await waitFor(() => {
      const repinned = onSessionChange.mock.calls.filter(([patch]) => {
        const candidate = patch as Record<string, unknown>;
        return candidate.testData !== undefined
          || candidate.mappingProfile !== undefined
          || candidate.recipe !== undefined
          || candidate.processingOutput !== undefined;
      });
      expect(repinned).toEqual([]);
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:new" } }));
    expect(onNewSession).toHaveBeenCalledWith("metal");
    expect(onNavigate).toHaveBeenLastCalledWith("/modeling?stage=data&family=metal");
  }, 20_000);
});
