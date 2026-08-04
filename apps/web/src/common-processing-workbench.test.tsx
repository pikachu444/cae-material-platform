import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

function isFitMethodInRequest(methodId: string | undefined): boolean {
  return Boolean(methodId && (methodId.includes("hardening_fit") || methodId.includes("prony_fit") || methodId.includes("fit_compare")));
}

function reverseJsonObjectKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(reverseJsonObjectKeys);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .reverse()
        .map(([key, nested]) => [key, reverseJsonObjectKeys(nested)]),
    );
  }
  return value;
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
  governed_source: {
    material: { aggregate_id: "material-a", revision_id: "material-a-r1" },
    material_state: { aggregate_id: "state-a", revision_id: "state-a-r1" },
    test_run: { aggregate_id: "run-a", revision_id: "run-a-r1" },
  },
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
    const seededFitOutput: Record<string, unknown> = {
      processing_output_id: "53000000-0000-4000-8000-000000000029",
      current_revision: {
        ...revision,
        id: "53000000-0000-4000-8000-000000000028",
        aggregate_id: "53000000-0000-4000-8000-000000000029",
      },
      label: "DP600 · seeded fit baseline",
      source_document: {
        aggregate_id: replicateResource.test_data_document_id,
        revision_id: replicateResource.current_revision.id,
      },
      source_document_sha256: "0".repeat(64),
      source_canonical_artifact_sha256: "1".repeat(64),
      mapping_profile: {
        aggregate_id: mappingProfileResource.mapping_profile_id,
        revision_id: mappingProfileResource.current_revision.id,
      },
      mapping_profile_sha256: "2".repeat(64),
      steps: [{
        method_id: "metal.hardening_fit_extrapolate",
        method_version: "1.0.0",
        options: { primary_family: "swift" },
      }],
      independent_quantity: "strain.engineering",
      stage_count: 1,
      final_point_count: 3,
      output_artifact_id: "53000000-0000-4000-8000-000000000027",
      output_sha256: "3".repeat(64),
      workup_overrides: [],
      fit_decision: null,
      export_provenance: null,
    };
    let failNextPreview = false;
    let invalidArtifactId: string | null = null;
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource, replicateResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-outputs") && init?.method === "POST") {
        const body = JSON.parse(String(init.body ?? "{}")) as {
          label?: string;
          source_document?: unknown;
          mapping_profile?: unknown;
          steps?: unknown;
        };
        const outputNumber = 30 + committedOutputs.length;
        const outputId = `53000000-0000-4000-8000-${String(outputNumber).padStart(12, "0")}`;
        const output = {
          processing_output_id: outputId,
          current_revision: {
            ...revision,
            id: `53000000-0000-4000-8000-${String(outputNumber + 1).padStart(12, "0")}`,
            aggregate_id: outputId,
          },
          label: committedOutputs.length === 0 ? "DP600 · swift selected fit" : body.label ?? "Processed result",
          source_document: body.source_document ?? {
            aggregate_id: documentResource.test_data_document_id,
            revision_id: revision.id,
          },
          mapping_profile: body.mapping_profile ?? {
            aggregate_id: mappingProfileResource.mapping_profile_id,
            revision_id: mappingProfileResource.current_revision.id,
          },
          steps: body.steps ?? [],
          output_sha256: String(outputNumber).repeat(64),
          final_point_count: 3,
          stage_count: 6,
        };
        committedOutputs.push(output);
        return jsonResponse(output, 201);
      }
      if (url.includes("/processing-outputs/") && url.endsWith("/content")) {
        const outputId = decodeURIComponent(url.split("/processing-outputs/")[1].split("/content")[0]);
        const output = [seededFitOutput, ...committedOutputs].find((item) => item.processing_output_id === outputId);
        const modulusStep = (output?.steps as Array<{ method_id?: string; options?: { method?: string } }> | undefined)
          ?.find((step) => step.method_id === "metal.elastic_modulus");
        const scalarPa = modulusStep?.options?.method === "chord" ? 120e9 : 210e9;
        const artifact = {
          document_type: "cmp.processing-output",
          output_id: invalidArtifactId === outputId ? "wrong-output" : outputId,
          source_document: output?.source_document,
          mapping_profile: output?.mapping_profile,
          // The released artifact is canonically key-sorted, while the list
          // response preserves request insertion order.  Keep the same
          // structure and array order to exercise order-independent validation.
          steps: reverseJsonObjectKeys(output?.steps),
          result: { stages: [{ scalar_results: [{ key: "youngs_modulus", value: scalarPa, unit: "Pa" }] }] },
        };
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/vnd.cmp.processing-output+json" }),
          blob: async () => new Blob([JSON.stringify(artifact)], { type: "application/json" }),
        } as Response;
      }
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: [seededFitOutput, ...committedOutputs] });
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
        if (failNextPreview) {
          failNextPreview = false;
          throw new Error("preview failed");
        }
        const body = JSON.parse(String(init.body ?? "{}")) as {
          steps?: Array<{ method_id?: string; options?: { method?: string } }>;
        };
        const modulusPa = body.steps?.find((step) => step.method_id === "metal.elastic_modulus")?.options?.method === "chord"
          ? 120e9
          : 210e9;
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
                  value: modulusPa,
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
    expect(screen.getByRole("heading", { name: "Select Test Data" })).toBeTruthy();
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
    await waitFor(() => expect((screen.getByLabelText("Test Data revision") as HTMLSelectElement).value).toBe(documentResource.test_data_document_id));
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
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    expect(screen.getByRole("img", { name: "Hardening candidate and selected extrapolation curves" })).toBeTruthy();
    expect(screen.getByText("Preview Swift/Voce blend")).toBeTruthy();
    const fitRail = document.querySelector(".configured-step-list");
    expect(fitRail?.querySelector(".rail-title")?.textContent).toContain("Process");
    expect(fitRail?.querySelectorAll("button")).toHaveLength(4);
    expect(screen.getByRole("button", { name: /Sort duplicate x/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /True\/plastic conversion/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Necking boundary/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Hardening fit/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /Step 4 · Hardening fit and extrapolation/ })).toBeTruthy();
    expect(screen.getByText("Candidate equations")).toBeTruthy();
    expect(screen.getByText("Fit domain")).toBeTruthy();
    expect(screen.getByText("Selected blend")).toBeTruthy();
    expect(screen.getByText("Primary contribution")).toBeTruthy();
    expect(screen.getByText("Extrapolation")).toBeTruthy();
    expect(screen.getByText("Graph interaction")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Apply" })).toBeNull();
    expect(screen.getByLabelText("Output points").closest("fieldset")).toBeTruthy();
    expect(screen.getByLabelText("Secondary hardening law").closest("fieldset")?.className).toContain("selected-blend-group");
    expect(screen.getByText("Stress response · observed evidence and hardening candidates")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Select range" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Select fit range" }));
    expect(screen.getByRole("button", { name: "Select fit range" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("Candidate parameters")).toBeTruthy();
    fireEvent.click(screen.getByText("Candidate parameters"));
    expect(screen.getByText("voce relative rmse")).toBeTruthy();
    expect(await screen.findByRole("columnheader", { name: "Recommendation" })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Save fit & continue" })).toHaveLength(1);
    expect((screen.getByRole("button", { name: "Save fit & continue" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByText("Reference hardening projection")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Select swift candidate/i }));
    expect(screen.getAllByText("Selected · swift").length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText("Candidate selection reason"), {
      target: { value: "Select Swift after comparing response, residual and tangent stability." },
    });
    expect((screen.getByRole("button", { name: "Save fit & continue" }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole("checkbox", { name: "Include Specimen 01 in processing and fit" }));
    expect((screen.getByRole("button", { name: "Save fit & continue" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByLabelText("Candidate selection reason")).toBeNull();
    fireEvent.click(screen.getByRole("checkbox", { name: "Include Specimen 01 in processing and fit" }));
    fireEvent.click(screen.getByRole("button", { name: /Select swift candidate/i }));
    fireEvent.change(screen.getByLabelText("Candidate selection reason"), {
      target: { value: "Re-select Swift after changing input scope." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => {
      expect((screen.getByRole("button", { name: "Save fit & continue" }) as HTMLButtonElement).disabled).toBe(true);
      expect(screen.queryByLabelText("Candidate selection reason")).toBeNull();
    });
    fireEvent.click(screen.getByRole("button", { name: /Select swift candidate/i }));
    fireEvent.change(screen.getByLabelText("Candidate selection reason"), {
      target: { value: "Re-select Swift after the successful candidate recomputation." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save fit & continue" }));
    expect(await screen.findByRole("heading", { name: "Review & deliver solver card" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Exact target preview is gated" })).toBeTruthy();
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
    expect(screen.getByRole("status", { name: "Loading Process controls" })).toBeTruthy();
    expect(await screen.findByRole("button", { name: "Save processed curves" })).toBeTruthy();
    expect(screen.queryByRole("status", { name: "Loading Process controls" })).toBeNull();
    fireEvent.click(screen.getByTitle("DP600-TENSILE-01 · S-1 · revision r1"));
    await waitFor(() => expect(document.querySelector(".persistent-modeling-plot > .modeling-plot-empty")).toBeTruthy());
    expect(await screen.findByText("No Process preview is active. Select Preview changes to preview the current Process settings.")).toBeTruthy();
    expect(screen.queryByText("Choose a saved Test Data revision. The graph compares real curves without changing saved data.")).toBeNull();
    expect(document.querySelector('[data-modeling-process-panel="ready"]')).toBeTruthy();
    const processSave = screen.getByRole("button", { name: "Save processed curves" }) as HTMLButtonElement;
    fireEvent.click(screen.getByTitle("DP600-TENSILE-02 · S-2 · revision r1"));
    expect(onSessionEvent).toHaveBeenCalledWith({
      type: "PIN_TEST_DATA",
      testData: {
        id: replicateResource.test_data_document_id,
        revisionId: replicateResource.current_revision.id,
        label: replicateResource.document_key,
        revisionNo: replicateResource.current_revision.revision_no,
      },
    });
    onSessionEvent.mockClear();
    fireEvent.click(screen.getByRole("checkbox", { name: "Include Specimen 02 in processing and fit" }));
    expect(onSessionEvent).toHaveBeenNthCalledWith(1, {
      type: "PIN_TEST_DATA",
      testData: {
        id: documentResource.test_data_document_id,
        revisionId: documentResource.current_revision.id,
        label: documentResource.document_key,
        revisionNo: documentResource.current_revision.revision_no,
      },
    });
    expect(onSessionEvent).toHaveBeenNthCalledWith(2, {
      type: "SET_TEST_DATA_SELECTION",
      selectedTestDataRefs: [{
        id: documentResource.test_data_document_id,
        revisionId: documentResource.current_revision.id,
        label: documentResource.document_key,
        revisionNo: documentResource.current_revision.revision_no,
      }],
    });
    onSessionEvent.mockClear();
    fireEvent.click(screen.getByRole("checkbox", { name: "Include Specimen 01 in processing and fit" }));
    expect(onSessionEvent).toHaveBeenNthCalledWith(1, { type: "PIN_TEST_DATA" });
    expect(onSessionEvent).toHaveBeenNthCalledWith(2, { type: "SET_TEST_DATA_SELECTION", selectedTestDataRefs: [] });
    expect(screen.getByRole("img", { name: "Blocked engineering curve plot" })).toBeTruthy();
    const blockedPlot = document.querySelector('.engineering-curve-plot-empty-frame[data-plot-state="blocked"]');
    expect(blockedPlot?.querySelectorAll(".chart-axis").length).toBeGreaterThanOrEqual(2);
    expect(blockedPlot?.querySelectorAll(".chart-grid").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole("button", { name: "Back to Data" })).toBeTruthy();
    expect((screen.getByRole("button", { name: "Preview changes" }) as HTMLButtonElement).disabled).toBe(true);
    expect(processSave.disabled).toBe(true);
    expect(document.querySelector('.method-library > summary[aria-disabled="true"]')).toBeTruthy();
    const blockedMethodButtons = Array.from(document.querySelectorAll<HTMLButtonElement>(".method-library .method-pill"));
    const blockedRailButtons = Array.from(document.querySelectorAll<HTMLButtonElement>(".configured-step-list button"));
    const blockedRangeInputs = Array.from(document.querySelectorAll<HTMLInputElement>(".process-band-controls input"));
    expect(blockedMethodButtons.length).toBeGreaterThan(0);
    expect(blockedRailButtons.length).toBeGreaterThan(0);
    expect(blockedRangeInputs.length).toBeGreaterThan(0);
    expect(blockedMethodButtons.every((button) => button.disabled)).toBe(true);
    expect(blockedRailButtons.every((button) => button.disabled)).toBe(true);
    expect(blockedRangeInputs.every((input) => input.matches(":disabled"))).toBe(true);
    fireEvent.click(screen.getByRole("checkbox", { name: "Include Specimen 01 in processing and fit" }));
    fireEvent.click(screen.getByTitle("DP600-TENSILE-01 · S-1 · revision r1"));
    fireEvent.click(screen.getByRole("checkbox", { name: "Include Specimen 02 in processing and fit" }));
    fireEvent.click(screen.getByTitle("DP600-TENSILE-02 · S-2 · revision r1"));
    await waitFor(() => expect((screen.getByRole("button", { name: "Preview changes" }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole("button", { name: /\+ Sort and resolve duplicate/ }));
    expect(processSave.disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(screen.getByText(/Preview ready/)).toBeTruthy());
    const processPreviewRequest = fetchMock.mock.calls
      .filter(([input, init]) => String(input).endsWith("/processing:preview") && init?.method === "POST")
      .at(-1);
    const processPreviewBody = JSON.parse(String(processPreviewRequest?.[1]?.body ?? "{}")) as {
      steps?: Array<{ method_id?: string; options?: Record<string, unknown> }>;
    };
    expect(processPreviewBody.steps?.map((step) => step.method_id)).toEqual([
      "rows.sort_unique",
      "metal.elastic_modulus",
      "metal.proof_stress",
      "metal.necking_candidate",
      "metal.engineering_to_true_plastic",
      "rows.sort_unique",
    ]);
    expect(processPreviewBody.steps?.some((step) => isFitMethodInRequest(step.method_id))).toBe(false);
    expect(screen.getByRole("img", { name: /(?:mapped and selected processing stage curve overlay|candidate and selected .*curves)/i })).toBeTruthy();
    const processPanel = () => document.querySelector('[data-modeling-process-panel="ready"]') as HTMLElement;
    await waitFor(() => expect(screen.getByText("Step 2 · Process · Young's modulus", { exact: true })).toBeTruthy());
    expect(screen.getByRole("button", { name: "Auto robust" })).toBeTruthy();
    expect(screen.getByLabelText("Elastic range start")).toBeTruthy();
    expect(screen.getByLabelText("Elastic range end")).toBeTruthy();
    expect(screen.queryByText("Candidate equations")).toBeNull();
    expect(screen.queryByText("Fit domain")).toBeNull();
    expect(screen.queryByText("Selected blend")).toBeNull();
    const robustResult = processPanel().querySelector(".process-band-result");
    expect(robustResult?.textContent ?? "").toMatch(/210\.0 GPa/);
    expect(processPanel().querySelector(".guided-step-options")?.textContent ?? "").not.toMatch(/Auto\/calculated value preview/);
    expect((screen.getByRole("button", { name: "Save processed curves" }) as HTMLButtonElement).disabled).toBe(false);
    failNextPreview = true;
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(screen.getByText("The Processing Workbench operation failed.")).toBeTruthy());
    expect(screen.getByRole("img", { name: /(?:mapped and selected processing stage curve overlay|candidate and selected .*curves)/i })).toBeTruthy();
    const processLabel = screen.getByRole("textbox", { name: "Processed curve label" });
    const processReason = screen.getByRole("textbox", { name: "Save reason" });
    fireEvent.change(processLabel, { target: { value: "Robust elastic" } });
    fireEvent.change(processReason, { target: { value: "Capture deterministic saved-result sibling one" } });
    fireEvent.click(processSave);
    await waitFor(() => expect(committedOutputs).toHaveLength(2));
    const firstProcessOutput = String(committedOutputs[1].processing_output_id);
    const firstCommitBody = JSON.parse(String(fetchMock.mock.calls.filter(([input, init]) => String(input).endsWith("/processing-outputs") && init?.method === "POST").at(-1)?.[1]?.body ?? "{}")) as {
      source_document?: { aggregate_id?: string; revision_id?: string };
      mapping_profile?: { aggregate_id?: string; revision_id?: string };
      steps?: Array<{ method_id?: string; options?: Record<string, unknown> }>;
    };
    expect(firstCommitBody.source_document).toEqual({ aggregate_id: replicateResource.test_data_document_id, revision_id: replicateResource.current_revision.id });
    expect(firstCommitBody.mapping_profile).toEqual({ aggregate_id: mappingProfileResource.mapping_profile_id, revision_id: mappingProfileResource.current_revision.id });
    expect(firstCommitBody.steps?.map((step) => step.method_id)).toEqual([
      "rows.sort_unique",
      "metal.elastic_modulus",
      "metal.proof_stress",
      "metal.necking_candidate",
      "metal.engineering_to_true_plastic",
      "rows.sort_unique",
    ]);
    expect(firstCommitBody.steps?.some((step) => isFitMethodInRequest(step.method_id))).toBe(false);
    expect(firstCommitBody.steps?.find((step) => step.method_id === "metal.elastic_modulus")?.options).toMatchObject({ method: "robust_huber", minimum_strain: 0.0002, maximum_strain: 0.002 });
    fireEvent.click(screen.getByRole("button", { name: "Chord" }));
    fireEvent.change(screen.getByLabelText("Elastic range start"), { target: { value: "0.001" } });
    fireEvent.change(screen.getByLabelText("Elastic range end"), { target: { value: "0.003" } });
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(screen.getByText(/Preview ready/)).toBeTruthy());
    const chordResult = processPanel().querySelector(".process-band-result");
    expect(chordResult?.textContent ?? "").toMatch(/120\.0 GPa/);
    expect(processPanel().querySelector(".guided-step-options")?.textContent ?? "").not.toMatch(/Auto\/calculated value preview/);
    fireEvent.change(processLabel, { target: { value: "Chord elastic" } });
    fireEvent.change(processReason, { target: { value: "Capture deterministic saved-result sibling two" } });
    fireEvent.click(processSave);
    await waitFor(() => expect(committedOutputs).toHaveLength(3));
    const secondProcessOutput = String(committedOutputs[2].processing_output_id);
    expect(firstProcessOutput).not.toBe(secondProcessOutput);
    const savedDetails = document.querySelector("details.process-saved-results") as HTMLDetailsElement;
    expect(screen.getAllByText("DP600-TENSILE-02 · r1").length).toBeGreaterThan(0);
    await waitFor(() => expect(savedDetails.querySelector("summary")?.textContent).toContain("Saved results (2)"));
    fireEvent.click(savedDetails.querySelector(":scope > summary")!);
    await waitFor(() => expect(savedDetails.querySelectorAll(".process-comparison-row")).toHaveLength(2));
    await waitFor(() => expect(Array.from(savedDetails.querySelectorAll(".process-comparison-row"), (row) => row.textContent ?? "").join(" ")).toContain("210.0 GPa"));
    const savedRowText = Array.from(savedDetails.querySelectorAll(".process-comparison-row"), (row) => row.textContent ?? "");
    expect(savedRowText.some((text) => text.includes("seeded fit baseline"))).toBe(false);
    expect(savedRowText).toEqual(expect.arrayContaining([
      expect.stringContaining("Robust elastic"),
      expect.stringContaining("Chord elastic"),
    ]));
    expect(savedRowText.every((text) => text.includes("Specimen 02 · r1"))).toBe(true);
    expect(savedRowText.every((text) => text.includes("output r1"))).toBe(true);
    expect(savedRowText.find((text) => text.includes("Robust elastic"))).toContain("210.0 GPa");
    expect(savedRowText.find((text) => text.includes("Robust elastic"))).toContain("history");
    expect(savedRowText.find((text) => text.includes("Chord elastic"))).toContain("120.0 GPa");
    expect(savedRowText.find((text) => text.includes("Chord elastic"))).toContain("current");
    const firstRow = savedDetails.querySelectorAll(".process-comparison-row")[0] as HTMLElement;
    expect(within(firstRow).getByRole("button", { name: "Use settings" })).toBeTruthy();
    invalidArtifactId = firstProcessOutput;
    fireEvent.click(savedDetails.querySelector(":scope > summary")!);
    fireEvent.click(savedDetails.querySelector(":scope > summary")!);
    await waitFor(() => expect(savedDetails.querySelectorAll(".process-comparison-row")[0]?.textContent).toContain("Saved result unavailable"));
    const invalidRow = savedDetails.querySelectorAll(".process-comparison-row")[0] as HTMLElement;
    fireEvent.click(within(invalidRow).getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(invalidRow.textContent).toContain("Saved result unavailable"));
    invalidArtifactId = null;
    fireEvent.click(within(invalidRow).getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(invalidRow.textContent).toContain("210.0 GPa"));
    fireEvent.click(within(invalidRow).getByRole("button", { name: "Use settings" }));
    expect(await screen.findByText(/Saved Process settings restored as a new draft/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Save processed curves" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(screen.getByText(/Preview ready/)).toBeTruthy());
    expect(screen.getByText("Curves")).toBeTruthy();
    expect(screen.getByText("2 curves · 2 included")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Tensile tests" })).toBeTruthy();
    const curveGroup = document.querySelector(".curve-tree-group > details");
    expect(curveGroup?.hasAttribute("open")).toBe(true);
    const groupSummary = curveGroup?.querySelector("summary");
    expect(groupSummary?.textContent).toContain("Tensile tests");
    fireEvent.click(groupSummary!);
    expect(curveGroup?.hasAttribute("open")).toBe(false);
    fireEvent.click(groupSummary!);
    expect(curveGroup?.hasAttribute("open")).toBe(true);
    expect(document.querySelector(".curve-group-row > span")).toBeNull();
    const curveKey = document.querySelector(".dataset-curve-swatch");
    expect(curveKey).toBeTruthy();
    expect(curveKey?.className).toBe("dataset-curve-swatch");
    expect(curveKey?.getAttribute("role")).toBe("img");
    expect(curveKey?.getAttribute("aria-label")).toBe("Plot color for Specimen 01");
    expect(curveKey?.previousElementSibling?.className).toBe("curve-include-toggle");
    expect(curveKey?.nextElementSibling?.className).toBe("curve-row-label");
    expect(Array.from(curveKey?.parentElement?.children ?? []).map((child) => child.className)).toEqual([
      "curve-include-toggle",
      "dataset-curve-swatch",
      "curve-row-label",
      "curve-visibility-toggle",
    ]);
    const curveRow = screen.getByTitle("DP600-TENSILE-01 · S-1 · revision r1");
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
      name: /1Sort and resolve duplicate x values1\.0\.0/,
    }));
    expect(screen.getByRole("img", { name: /(?:mapped and selected processing stage curve overlay|candidate and selected .*curves)/i })).toBeTruthy();
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
    await screen.findByRole("img", { name: /(?:mapped and selected processing stage curve overlay|candidate and selected .*curves)/i });
    fireEvent.click(screen.getByRole("button", { name: /2Young's modulus1\.0\.0/ }));
    const elasticPlot = screen.getByRole("img", { name: /(?:mapped and selected processing stage curve overlay|candidate and selected .*curves)/i });
    Object.defineProperty(elasticPlot, "getBoundingClientRect", {
      value: () => ({ left: 0, top: 0, right: 760, bottom: 420, width: 760, height: 420, x: 0, y: 0, toJSON: () => ({}) }),
      configurable: true,
    });
    fireEvent.click(screen.getByRole("button", { name: "Select range" }));
    fireEvent.pointerDown(elasticPlot, { button: 0, pointerId: 2, clientX: 100, clientY: 200 });
    fireEvent.pointerMove(elasticPlot, { pointerId: 2, clientX: 160, clientY: 200 });
    fireEvent.pointerUp(elasticPlot, { pointerId: 2, clientX: 160, clientY: 200 });
    fireEvent.click(screen.getByRole("button", { name: "Apply selection" }));
    const appliedSteps = JSON.parse((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value) as Array<{ method_id: string; options: Record<string, number> }>;
    expect(appliedSteps[1].method_id).toBe("metal.elastic_modulus");
    expect(appliedSteps[1].options.minimum_strain).not.toBe(0.0002);
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await screen.findByText(/Preview ready/);
    await screen.findByRole("img", { name: /(?:mapped and selected processing stage curve overlay|candidate and selected .*curves)/i });
    fireEvent.click(screen.getByRole("button", { name: /4Necking candidate1\.0\.0/ }));
    await waitFor(() => expect(screen.getByText("Step 4 · Process · Necking candidate", { exact: true })).toBeTruthy());
    const neckingPlot = screen.getByRole("img", { name: /(?:mapped and selected processing stage curve overlay|candidate and selected .*curves)/i });
    Object.defineProperty(neckingPlot, "getBoundingClientRect", {
      value: () => ({ left: 0, top: 0, right: 760, bottom: 420, width: 760, height: 420, x: 0, y: 0, toJSON: () => ({}) }),
      configurable: true,
    });
    fireEvent.click(screen.getByRole("button", { name: "Pick point" }));
    fireEvent.pointerDown(neckingPlot, { button: 0, pointerId: 3, clientX: 620, clientY: 180 });
    fireEvent.pointerUp(neckingPlot, { pointerId: 3, clientX: 620, clientY: 180 });
    fireEvent.click(screen.getByRole("button", { name: "Apply selection" }));
    const neckingSteps = JSON.parse((screen.getByLabelText("Ordered processing steps") as HTMLTextAreaElement).value) as Array<{ method_id: string; options: Record<string, unknown> }>;
    expect(neckingSteps[4].method_id).toBe("metal.engineering_to_true_plastic");
    expect(neckingSteps[4].options.necking_policy).toBe("manual_index");
    expect(Number(neckingSteps[4].options.manual_necking_index)).toBeGreaterThanOrEqual(1);

    fireEvent.click(screen.getByRole("button", { name: "Align and calculate" }));
    expect(await screen.findByRole("img", { name: "Aligned replicate curves with pointwise mean and confidence interval" })).toBeTruthy();
    expect(screen.getByText("Members (2)")).toBeTruthy();
    expect(screen.getByText("sample standard deviation uses n - 1")).toBeTruthy();
    const ensembleRequest = fetchMock.mock.calls.find(([input]) => String(input).endsWith("/processing:preview-ensemble"));
    const ensembleBody = JSON.parse(String(ensembleRequest?.[1]?.body)) as { preprocessing_steps: Array<{ method_id: string }> };
    expect(ensembleBody.preprocessing_steps.map((step) => step.method_id)).toEqual(["rows.sort_unique", "rows.sort_unique"]);
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:export" } }));
    expect(screen.getByRole("heading", { name: "Review & deliver solver card" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Exact target preview is gated" })).toBeTruthy();
    expect(screen.queryByText("Test data")).toBeNull();
    expect(screen.queryByLabelText("Resize curve and process navigator")).toBeNull();
    expect(screen.queryByRole("button", { name: "Mean & band" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Replicate statistics" })).toBeNull();
    expect(document.querySelector(".persistent-modeling-plot")).toBeTruthy();
    const exportGraph = await screen.findByRole("img", { name: "Test data and selected model response" });
    expect(exportGraph.textContent).toContain("Engineering strain [1]");
    expect(exportGraph.textContent).toContain("Engineering stress [MPa]");
    expect(exportGraph.textContent).not.toContain("True plastic strain [1]");
    expect(exportGraph.textContent).not.toContain("Hardening stress [MPa]");
    expect(exportGraph.textContent).not.toContain("strain.true_plastic");
    expect(exportGraph.textContent).not.toContain("stress.hardening");
    expect(screen.queryByRole("tab", { name: "Stress response" })).toBeNull();
    expect(screen.queryByText("Calculation notes")).toBeNull();
    expect(screen.queryByText("Exact Neutral and solver delivery fixture")).toBeNull();
    expect(document.querySelector("#modeling-process:not([hidden]) .persistent-modeling-plot")).toBeTruthy();
    expect(screen.getByText("Saved source revision")).toBeTruthy();
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

  it("keeps restored exact Data refs while documents resolve before Material context", async () => {
    const thirdResource = {
      ...replicateResource,
      test_data_document_id: "53000000-0000-4000-8000-000000000022",
      current_revision: {
        ...replicateResource.current_revision,
        id: "53000000-0000-4000-8000-000000000023",
        aggregate_id: "53000000-0000-4000-8000-000000000022",
      },
      document_key: "DP600-TENSILE-03",
      specimen_id: "S-3",
    };
    const documents = [documentResource, replicateResource, thirdResource];
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: documents });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-methods") || url.endsWith("/processing-outputs")
        || url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes")
        || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.includes("/content")) {
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
        } as Response;
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const refs = documents.map((item) => ({
      id: item.test_data_document_id,
      revisionId: item.current_revision.id,
      label: item.document_key,
      revisionNo: item.current_revision.revision_no,
    }));
    const initialSession = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Keep exact Data sources",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: refs[0],
      workspace: {
        activeStage: "data",
        selectedDocumentIds: refs.map((ref) => ref.id),
        selectedTestDataRefs: refs,
        visibleTestDataKeys: refs.map((ref) => `${ref.id}:${ref.revisionId}`),
        selectedStepIndex: 0,
        selectedStageOrdinal: 0,
        plotView: "pipeline",
        settingsOpen: true,
      },
    };
    const onSessionChange = vi.fn();
    const material = {
      material_id: "material-a",
      current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } },
    };
    const materialState = {
      material_state_id: "state-a",
      current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } },
    };
    const view = render(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={initialSession as never}
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
      />,
    );
    await waitFor(() => expect(
      fetchMock.mock.calls.some(([input]) => String(input).endsWith("/test-data-documents")),
    ).toBe(true));
    await new Promise((resolve) => window.setTimeout(resolve, 0));

    view.rerender(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={initialSession as never}
        material={material as never}
        materialState={materialState as never}
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
      />,
    );
    await waitFor(() => expect(document.querySelectorAll(".data-library-row")).toHaveLength(3));
    await waitFor(() => {
      const workspacePatches = onSessionChange.mock.calls
        .map(([patch]) => (patch as Record<string, unknown>).workspace)
        .filter((workspace): workspace is Record<string, unknown> => Boolean(workspace));
      const latest = workspacePatches.at(-1);
      expect(latest?.selectedTestDataRefs).toHaveLength(3);
      expect(latest?.selectedDocumentIds).toHaveLength(3);
      expect(latest?.visibleTestDataKeys).toHaveLength(3);
    });
  });

  it("defers Process reconciliation until Material context resolves without empty workspace patches", async () => {
    const thirdResource = {
      ...replicateResource,
      test_data_document_id: "53000000-0000-4000-8000-000000000022",
      current_revision: {
        ...replicateResource.current_revision,
        id: "53000000-0000-4000-8000-000000000023",
        aggregate_id: "53000000-0000-4000-8000-000000000022",
      },
      document_key: "DP600-TENSILE-03",
      specimen_id: "S-3",
    };
    const documents = [documentResource, replicateResource, thirdResource];
    // The persisted workspace order is not the restored source focus. This
    // mirrors the live reload where refs arrive as 03, 02, base while
    // session.testData remains pinned to base.
    const refs = [thirdResource, replicateResource, documentResource].map((item) => ({
      id: item.test_data_document_id,
      revisionId: item.current_revision.id,
      label: item.document_key,
      revisionNo: item.current_revision.revision_no,
    }));
    const baseRef = refs[2];
    const replicateRef = refs[1];
    const robustOutput = {
      processing_output_id: "53000000-0000-4000-8000-000000000030",
      current_revision: { ...revision, id: "53000000-0000-4000-8000-000000000031", aggregate_id: "53000000-0000-4000-8000-000000000030" },
      label: "Robust 210",
      source_document: { aggregate_id: baseRef.id, revision_id: baseRef.revisionId },
      mapping_profile: { aggregate_id: mappingProfileResource.mapping_profile_id, revision_id: mappingProfileResource.current_revision.id },
      steps: [{ method_id: "metal.elastic_modulus", method_version: "1.0.0", options: { method: "robust_huber", minimum_strain: 0.0002, maximum_strain: 0.002 } }],
      output_sha256: "3".repeat(64),
      final_point_count: 3,
      stage_count: 2,
    };
    const chordOutput = {
      ...robustOutput,
      processing_output_id: "53000000-0000-4000-8000-000000000032",
      current_revision: { ...revision, id: "53000000-0000-4000-8000-000000000033", aggregate_id: "53000000-0000-4000-8000-000000000032" },
      label: "Chord 120",
      steps: [{ method_id: "metal.elastic_modulus", method_version: "1.0.0", options: { method: "chord", minimum_strain: 0.001, maximum_strain: 0.003 } }],
      output_sha256: "4".repeat(64),
    };
    const outputItems = [robustOutput, chordOutput];
    const workspacePatches = (onSessionChange: ReturnType<typeof vi.fn>) => onSessionChange.mock.calls
      .map(([patch]) => (patch as Record<string, unknown>).workspace)
      .filter((workspace): workspace is Record<string, unknown> => Boolean(workspace));
    let resolveDocuments: ((response: Response) => void) | undefined;
    const documentsResponse = new Promise<Response>((resolve) => { resolveDocuments = resolve; });
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return documentsResponse;
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-outputs") && init?.method !== "POST") return jsonResponse({ items: outputItems });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: [
        "rows.sort_unique", "metal.elastic_modulus", "metal.proof_stress", "metal.necking_candidate", "metal.engineering_to_true_plastic",
      ].map((methodId) => ({ method_id: methodId, version: "1.0.0", label: methodId, description: methodId, option_schema: {}, deterministic: true, allows_extrapolation: false })) });
      if (url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.includes("/processing-outputs/") && url.endsWith("/content")) {
        const outputId = decodeURIComponent(url.split("/processing-outputs/")[1].split("/content")[0]);
        const output = outputItems.find((item) => item.processing_output_id === outputId);
        const scalarPa = outputId === chordOutput.processing_output_id ? 120e9 : 210e9;
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/vnd.cmp.processing-output+json" }),
          blob: async () => new Blob([JSON.stringify({
            document_type: "cmp.processing-output",
            output_id: outputId,
            source_document: output?.source_document,
            mapping_profile: output?.mapping_profile,
            steps: output?.steps,
            result: { stages: [{ scalar_results: [{ key: "youngs_modulus", value: scalarPa, unit: "Pa" }] }] },
          })], { type: "application/json" }),
        } as Response;
      }
      if (url.includes("/content")) return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
      } as Response;
      if (url.endsWith("/processing:preview") && init?.method === "POST") {
        const body = JSON.parse(String(init.body ?? "{}")) as { steps?: Array<{ method_id?: string; options?: { method?: string } }> };
        const scalarPa = body.steps?.find((step) => step.method_id === "metal.elastic_modulus")?.options?.method === "chord" ? 120e9 : 210e9;
        return jsonResponse({
          execution_mode: "preview",
          promotable: false,
          source_document_sha256: "d".repeat(64),
          mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
          independent_quantity: "strain.engineering",
          stages: [
            { ordinal: 0, method_id: "mapping", method_version: "1.0.0", point_count: 3, series: [{ quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] }, { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] }], diagnostics: [], scalar_results: [] },
            { ordinal: 1, method_id: "rows.sort_unique", method_version: "1.0.0", point_count: 3, series: [{ quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] }, { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] }], diagnostics: [], scalar_results: [] },
            { ordinal: 2, method_id: "metal.elastic_modulus", method_version: "1.0.0", point_count: 3, series: [{ quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] }, { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] }], diagnostics: [], scalar_results: [{ key: "youngs_modulus", quantity_semantics: "modulus.young", value: scalarPa, unit: "Pa" }] },
          ],
        });
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const initialSession = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Restore Process exact revisions",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: baseRef,
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      processingOutput: { id: chordOutput.processing_output_id, revisionId: chordOutput.current_revision.id, label: chordOutput.label, revisionNo: 1 },
      workspace: {
        activeStage: "process",
        selectedDocumentIds: [baseRef.id, replicateRef.id],
        selectedTestDataRefs: refs,
        visibleTestDataKeys: refs.map((ref) => `${ref.id}:${ref.revisionId}`),
        selectedStepIndex: 1,
        selectedStageOrdinal: 2,
        plotView: "pipeline",
        settingsOpen: true,
      },
    };
    const material = { material_id: "material-a", current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } } };
    const materialState = { material_state_id: "state-a", current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } } };
    const onSessionChange = vi.fn();
    const view = render(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={initialSession as never}
        locationSearch="?stage=process&family=metal"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
      />,
    );
    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/test-data-documents"))).toBe(true));
    resolveDocuments?.(jsonResponse({ items: documents }));
    await waitFor(() => expect(document.querySelector(".method-library summary")?.textContent).toContain("5"));
    expect(workspacePatches(onSessionChange).length).toBeGreaterThan(0);
    const expectedRefKeys = refs.map((ref) => `${ref.id}:${ref.revisionId}`).join("|");
    const expectedIncludedIds = [baseRef.id, replicateRef.id].join("|");
    const assertRestoredWorkspace = () => expect(workspacePatches(onSessionChange).every((workspace) => {
      const refsInPatch = workspace.selectedTestDataRefs as Array<{ id: string; revisionId: string }> | undefined;
      const includedIds = workspace.selectedDocumentIds as string[] | undefined;
      return refsInPatch?.length === 3
        && refsInPatch.map((ref) => `${ref.id}:${ref.revisionId}`).join("|") === expectedRefKeys
        && includedIds?.length === 2
        && includedIds.join("|") === expectedIncludedIds;
    })).toBe(true);
    assertRestoredWorkspace();
    expect(onSessionChange.mock.calls.map(([patch]) => (patch as Record<string, unknown>).testData).filter(Boolean)).toEqual([]);

    view.rerender(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={initialSession as never}
        material={material as never}
        materialState={materialState as never}
        locationSearch="?stage=process&family=metal"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
        onSessionChange={onSessionChange}
      />,
    );
    await waitFor(() => expect(document.querySelectorAll(".curve-row-label")).toHaveLength(3));
    await screen.findByRole("button", { name: "Save processed curves" });
    assertRestoredWorkspace();
    expect(onSessionChange.mock.calls.map(([patch]) => (patch as Record<string, unknown>).testData).filter(Boolean)).toEqual([]);
    expect(await screen.findByText("No Process preview is active. Choose Use settings for a saved result, then select Preview changes to preview the draft.")).toBeTruthy();
    expect(screen.queryByText("Choose a saved Test Data revision. The graph compares real curves without changing saved data.")).toBeNull();
    expect(document.querySelector(".persistent-modeling-plot > .modeling-plot-toolbar")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await waitFor(() => expect(screen.getByText(/Preview ready\./)).toBeTruthy(), { timeout: 5000 });
    expect(document.querySelector(".process-band-source")?.textContent).toBe("Specimen 01 · r1");
    expect(document.querySelector(".process-band-result")?.textContent).toContain("210.0 GPa");
    const savedDetails = document.querySelector("details.process-saved-results") as HTMLDetailsElement;
    expect(savedDetails.querySelector("summary")?.textContent).toContain("Saved results (2)");
    fireEvent.click(savedDetails.querySelector(":scope > summary")!);
    await waitFor(() => expect(savedDetails.querySelectorAll(".process-comparison-row")).toHaveLength(2));
    await waitFor(() => {
      const rows = Array.from(savedDetails.querySelectorAll(".process-comparison-row"), (row) => row.textContent ?? "");
      expect(rows.find((text) => text.includes("Robust 210"))).toContain("210.0 GPa");
      expect(rows.find((text) => text.includes("Chord 120"))).toContain("120.0 GPa");
      expect(rows.every((text) => text.includes("Specimen 01 · r1"))).toBe(true);
      expect(rows.every((text) => text.includes("output r1"))).toBe(true);
    });
    expect(Array.from(savedDetails.querySelectorAll(".process-comparison-row"), (row) => row.textContent ?? "").find((text) => text.includes("Chord 120"))).toContain("current");
    expect(fetchMock.mock.calls.filter(([input, init]) => String(input).endsWith("/processing-outputs") && init?.method !== "POST").length).toBeLessThanOrEqual(2);
    expect(screen.queryByText(/ERR_INSUFFICIENT_RESOURCES|Maximum update depth exceeded/)).toBeNull();
  });

  it("preserves older exact refs, membership, visibility and focus when Data enters Process", async () => {
    const currentRevision = {
      ...revision,
      id: "53000000-0000-4000-8000-000000000101",
      aggregate_id: documentResource.test_data_document_id,
      revision_no: 2,
    };
    const historicalDocuments = [
      { ...documentResource, current_revision: currentRevision },
      {
        ...replicateResource,
        current_revision: {
          ...currentRevision,
          id: "53000000-0000-4000-8000-000000000102",
          aggregate_id: replicateResource.test_data_document_id,
        },
      },
      {
        ...replicateResource,
        test_data_document_id: "53000000-0000-4000-8000-000000000022",
        current_revision: {
          ...currentRevision,
          id: "53000000-0000-4000-8000-000000000103",
          aggregate_id: "53000000-0000-4000-8000-000000000022",
        },
        document_key: "DP600-TENSILE-03",
        specimen_id: "S-3",
      },
    ];
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: historicalDocuments });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-outputs") || url.endsWith("/processing-ensemble-methods")
        || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: [
        "rows.sort_unique", "metal.elastic_modulus", "metal.proof_stress", "metal.necking_candidate",
        "metal.engineering_to_true_plastic", "metal.hardening_fit_extrapolate",
      ].map((methodId) => ({ method_id: methodId, version: "1.0.0", label: methodId, description: methodId, option_schema: {}, deterministic: true, allows_extrapolation: false })) });
      if (url.endsWith("/processing:preview") && init?.method === "POST") return jsonResponse({
        execution_mode: "preview",
        promotable: false,
        source_document_sha256: "d".repeat(64),
        mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
        independent_quantity: "strain.engineering",
        stages: [{
          ordinal: 0,
          method_id: "mapping",
          method_version: "1.0.0",
          point_count: 2,
          series: [
            { quantity: "strain.engineering", unit: "1", values: [0, 0.001] },
            { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8] },
          ],
          diagnostics: [],
          scalar_results: [],
        }],
      });
      if (url.includes("/content")) return {
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
      } as Response;
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const historicalRevisionIds = [revision.id, replicateResource.current_revision.id, "53000000-0000-4000-8000-000000000023"];
    const refs = historicalDocuments.map((item, index) => ({
      id: item.test_data_document_id,
      revisionId: historicalRevisionIds[index],
      label: item.document_key,
      revisionNo: 1,
    }));
    const initialSession = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Process exact older revisions",
      material: { id: "material-a", revisionId: "material-a-r2", label: "DP600", revisionNo: 2 },
      materialState: { id: "state-a", revisionId: "state-a-r2", label: "As received", revisionNo: 2 },
      testData: refs[0],
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      workspace: {
        activeStage: "data",
        selectedDocumentIds: refs.slice(0, 2).map((ref) => ref.id),
        selectedTestDataRefs: refs,
        visibleTestDataKeys: refs.map((ref) => `${ref.id}:${ref.revisionId}`),
        selectedStepIndex: 0,
        selectedStageOrdinal: 0,
        plotView: "pipeline",
        settingsOpen: true,
      },
    };
    const material = {
      material_id: "material-a",
      current_revision: { id: "material-a-r2", revision_no: 2, content: { name: "DP600" } },
    };
    const materialState = {
      material_state_id: "state-a",
      current_revision: { id: "state-a-r2", revision_no: 2, content: { name: "As received" } },
    };
    render(
      <CommonProcessingWorkbench
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        initialSession={initialSession as never}
        material={material as never}
        materialState={materialState as never}
        locationSearch="?stage=data&family=metal"
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
      />,
    );
    await waitFor(() => expect(document.querySelectorAll(".curve-row-label")).toHaveLength(3));
    fireEvent(window, new CustomEvent("cmp:workspace-command", { detail: { command: "modeling:process" } }));
    await screen.findByRole("button", { name: "Save processed curves" });
    await waitFor(() => expect(document.querySelectorAll(".curve-row-label")).toHaveLength(3));
    expect(document.querySelector(".process-band-source")?.textContent).toContain("r1");
    expect(screen.getByText("3 curves · 2 included")).toBeTruthy();
    expect(screen.getAllByRole("checkbox", { name: /Include .* in processing and fit/ }).filter((input) => (input as HTMLInputElement).checked)).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /Show .* on plot|Hide .* on plot/ }).filter((button) => button.getAttribute("aria-pressed") === "true")).toHaveLength(3);
    expect(document.querySelectorAll(".modeling-dataset-list article.active")).toHaveLength(1);
    expect((screen.getByRole("button", { name: "Preview changes" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("settles one failed exact read, exposes explicit retry, and never falls back to stale bytes", async () => {
    const sourceId = documentResource.test_data_document_id;
    const missingId = replicateResource.test_data_document_id;
    const sourceRef = { id: sourceId, revisionId: revision.id, label: documentResource.document_key, revisionNo: 1 };
    const missingRef = { id: missingId, revisionId: replicateResource.current_revision.id, label: replicateResource.document_key, revisionNo: 1 };
    const session = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Exact read recovery",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: sourceRef,
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      workspace: {
        activeStage: "process",
        selectedDocumentIds: [sourceId],
        selectedTestDataRefs: [sourceRef, missingRef],
        visibleTestDataKeys: [`${sourceId}:${revision.id}`, `${missingId}:${replicateResource.current_revision.id}`],
        selectedStepIndex: 1,
        selectedStageOrdinal: 0,
        plotView: "pipeline",
        settingsOpen: true,
      },
    };
    let failedRead = true;
    let contentGets = 0;
    let previewPosts = 0;
    let outputPosts = 0;
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource, replicateResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-outputs") && init?.method === "POST") {
        outputPosts += 1;
        return jsonResponse({}, 201);
      }
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: [] });
      if (url.includes("/test-data-documents/") && url.endsWith("/content")) {
        contentGets += 1;
        const requestedId = decodeURIComponent(url.split("/test-data-documents/")[1].split("/")[0]);
        if (requestedId === missingId && failedRead) return jsonResponse({ detail: "missing exact source" }, 404);
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
        } as Response;
      }
      if (url.endsWith("/processing:preview") && init?.method === "POST") {
        previewPosts += 1;
        return jsonResponse({
          execution_mode: "preview",
          promotable: false,
          source_document_sha256: "d".repeat(64),
          mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
          independent_quantity: "strain.engineering",
          stages: [{
            ordinal: 0,
            method_id: "mapping",
            method_version: "1.0.0",
            point_count: 2,
            series: [
              { quantity: "strain.engineering", unit: "1", values: [0, 0.001] },
              { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8] },
            ],
            diagnostics: [],
            scalar_results: [{ key: "youngs_modulus", quantity_semantics: "modulus.young", value: 210e9, unit: "Pa" }],
          }],
        });
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const material = { material_id: "material-a", current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } } };
    const materialState = { material_state_id: "state-a", current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } } };
    const view = render(<CommonProcessingWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} initialSession={session as never} material={material as never} materialState={materialState as never} locationSearch="?stage=process&family=metal" onNavigate={() => undefined} onOpenConnection={() => undefined} />);
    await screen.findByRole("button", { name: "Save processed curves" });
    await waitFor(() => expect(contentGets).toBe(1));
    await waitFor(() => expect(screen.getByTitle("DP600-TENSILE-02 · S-2 · revision r1")).toBeTruthy());
    const previewPostsBeforeFailure = previewPosts;
    fireEvent.click(screen.getByTitle("DP600-TENSILE-02 · S-2 · revision r1"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Retry exact source" })).toBeTruthy());
    expect(contentGets).toBe(2);
    expect(screen.getByText("Exact source unavailable · r1")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Preview changes" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Save processed curves" }) as HTMLButtonElement).disabled).toBe(true);
    const blockedProcessPanel = document.querySelector('[data-modeling-process-panel="ready"]');
    expect(blockedProcessPanel?.textContent ?? "").not.toMatch(/(?:210|120)\.0 GPa/);
    expect(screen.getByRole("img", { name: "Blocked engineering curve plot" })).toBeTruthy();
    expect(previewPosts).toBe(previewPostsBeforeFailure);
    view.rerender(<CommonProcessingWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} initialSession={session as never} material={material as never} materialState={materialState as never} locationSearch="?stage=process&family=metal" onNavigate={() => undefined} onOpenConnection={() => undefined} />);
    await new Promise((resolve) => setTimeout(resolve, 350));
    expect(contentGets).toBe(2);
    failedRead = false;
    fireEvent.click(screen.getByRole("button", { name: "Retry exact source" }));
    await waitFor(() => expect(screen.getByText("Specimen 02 · r1")).toBeTruthy());
    expect((screen.getByRole("button", { name: "Preview changes" }) as HTMLButtonElement).disabled).toBe(false);
    expect(outputPosts).toBe(0);
  });

  it.each(["success", "failure"] as const)("re-reads A after an explicit A→B→A selection when B %s", async (outcome) => {
    const sourceId = documentResource.test_data_document_id;
    const nextId = replicateResource.test_data_document_id;
    const sourceRef = { id: sourceId, revisionId: revision.id, label: documentResource.document_key, revisionNo: 1 };
    const nextRef = { id: nextId, revisionId: replicateResource.current_revision.id, label: replicateResource.document_key, revisionNo: 1 };
    const contentRequests: string[] = [];
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource, replicateResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: [] });
      if (url.includes("/test-data-documents/") && url.endsWith("/content")) {
        const requestedId = decodeURIComponent(url.split("/test-data-documents/")[1].split("/")[0]);
        contentRequests.push(requestedId);
        if (requestedId === nextId && outcome === "failure") return jsonResponse({ detail: "B unavailable" }, 404);
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
        } as Response;
      }
      if (url.endsWith("/processing:preview") && init?.method === "POST") return jsonResponse({
        execution_mode: "preview",
        promotable: false,
        source_document_sha256: "d".repeat(64),
        mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
        independent_quantity: "strain.engineering",
        stages: [{ ordinal: 0, method_id: "mapping", method_version: "1.0.0", point_count: 2, series: [], diagnostics: [], scalar_results: [] }],
      });
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const session = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Exact A B A selection",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: sourceRef,
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      workspace: { activeStage: "process", selectedDocumentIds: [sourceId], selectedTestDataRefs: [sourceRef, nextRef], visibleTestDataKeys: [`${sourceId}:${revision.id}`, `${nextId}:${replicateResource.current_revision.id}`], selectedStepIndex: 0, selectedStageOrdinal: 0, plotView: "pipeline", settingsOpen: true },
    };
    const material = { material_id: "material-a", current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } } };
    const materialState = { material_state_id: "state-a", current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } } };
    render(<CommonProcessingWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} initialSession={session as never} material={material as never} materialState={materialState as never} locationSearch="?stage=process&family=metal" onNavigate={() => undefined} onOpenConnection={() => undefined} />);
    await waitFor(() => expect(contentRequests).toEqual([sourceId]));
    await screen.findByText("Specimen 01 · r1");
    fireEvent.click(await screen.findByTitle("DP600-TENSILE-02 · S-2 · revision r1"));
    await waitFor(() => expect(contentRequests).toEqual([sourceId, nextId]));
    if (outcome === "success") await screen.findByText("Specimen 02 · r1");
    else await screen.findByRole("button", { name: "Retry exact source" });
    fireEvent.click(screen.getByTitle("DP600-TENSILE-01 · S-1 · revision r1"));
    await waitFor(() => expect(contentRequests).toEqual([sourceId, nextId, sourceId]));
    await screen.findByText("Specimen 01 · r1");
    expect(screen.queryByText("Exact source unavailable · r1")).toBeNull();
  });

  it.each(["success", "failure"] as const)("keeps the newest exact request authoritative when A is pending and B %s", async (outcome) => {
    const sourceId = documentResource.test_data_document_id;
    const nextId = replicateResource.test_data_document_id;
    const sourceRef = { id: sourceId, revisionId: revision.id, label: documentResource.document_key, revisionNo: 1 };
    const nextRef = { id: nextId, revisionId: replicateResource.current_revision.id, label: replicateResource.document_key, revisionNo: 1 };
    let contentGets = 0;
    let resolveA: ((response: Response) => void) | undefined;
    let rejectA: ((reason?: unknown) => void) | undefined;
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data-documents")) return jsonResponse({ items: [documentResource, replicateResource] });
      if (url.endsWith("/mapping-profiles")) return jsonResponse({ items: [mappingProfileResource] });
      if (url.endsWith("/processing-methods")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-ensemble-methods") || url.endsWith("/common-processing-recipes") || url.endsWith("/common-processing-batches")) return jsonResponse({ items: [] });
      if (url.endsWith("/processing-outputs")) return jsonResponse({ items: [] });
      if (url.includes("/test-data-documents/") && url.endsWith("/content")) {
        contentGets += 1;
        const requestedId = decodeURIComponent(url.split("/test-data-documents/")[1].split("/")[0]);
        if (requestedId === sourceId) {
          return new Promise<Response>((resolve, reject) => { resolveA = resolve; rejectA = reject; });
        }
        if (outcome === "failure") return jsonResponse({ detail: "B unavailable" }, 404);
        return {
          ok: true,
          status: 200,
          headers: new Headers({ "content-type": "application/json" }),
          blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
        } as Response;
      }
      if (url.endsWith("/processing:preview") && init?.method === "POST") return jsonResponse({
        execution_mode: "preview",
        promotable: false,
        source_document_sha256: "d".repeat(64),
        mapping_profile_sha256: mappingProfileResource.current_revision.content_hash,
        independent_quantity: "strain.engineering",
        stages: [{ ordinal: 0, method_id: "mapping", method_version: "1.0.0", point_count: 2, series: [], diagnostics: [], scalar_results: [] }],
      });
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const session = {
      version: 4,
      updatedAt: "2026-07-24T00:00:00Z",
      materialFamily: "metal",
      objective: "Exact request race",
      material: { id: "material-a", revisionId: "material-a-r1", label: "DP600", revisionNo: 1 },
      materialState: { id: "state-a", revisionId: "state-a-r1", label: "As received", revisionNo: 1 },
      testData: sourceRef,
      mappingProfile: { id: mappingProfileResource.mapping_profile_id, revisionId: mappingProfileResource.current_revision.id, label: mappingProfileResource.content.label, revisionNo: 1 },
      workspace: { activeStage: "process", selectedDocumentIds: [sourceId], selectedTestDataRefs: [sourceRef, nextRef], visibleTestDataKeys: [`${sourceId}:${revision.id}`, `${nextId}:${replicateResource.current_revision.id}`], selectedStepIndex: 0, selectedStageOrdinal: 0, plotView: "pipeline", settingsOpen: true },
    };
    const material = { material_id: "material-a", current_revision: { id: "material-a-r1", revision_no: 1, content: { name: "DP600" } } };
    const materialState = { material_state_id: "state-a", current_revision: { id: "state-a-r1", revision_no: 1, content: { name: "As received" } } };
    render(<CommonProcessingWorkbench config={{ baseUrl: "/api/v1", accessToken: "token" }} initialSession={session as never} material={material as never} materialState={materialState as never} locationSearch="?stage=process&family=metal" onNavigate={() => undefined} onOpenConnection={() => undefined} />);
    await waitFor(() => expect(contentGets).toBe(1));
    fireEvent.click(await screen.findByTitle("DP600-TENSILE-02 · S-2 · revision r1"));
    await waitFor(() => expect(contentGets).toBe(2));
    if (outcome === "success") await waitFor(() => expect(screen.getByText("Specimen 02 · r1")).toBeTruthy());
    else await waitFor(() => expect(screen.getByRole("button", { name: "Retry exact source" })).toBeTruthy());
    resolveA?.({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      blob: async () => new Blob([JSON.stringify(documentJson)], { type: "application/json" }),
    } as Response);
    await new Promise((resolve) => setTimeout(resolve, 250));
    expect(contentGets).toBe(2);
    if (outcome === "success") {
      expect(screen.getByText("Specimen 02 · r1")).toBeTruthy();
      expect(screen.queryByText("Specimen 01 · r1")).toBeNull();
    } else {
      expect(screen.getByText("Exact source unavailable · r1")).toBeTruthy();
      expect(screen.getByRole("button", { name: "Retry exact source" })).toBeTruthy();
    }
    rejectA?.(new Error("late A failure"));
  });
});
