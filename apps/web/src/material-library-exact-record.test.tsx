import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ExactRecordDatasheetPage } from "./features/materials";
import type { RevisionMetadata } from "./types";

const metadata = (id: string, revisionNo: number): RevisionMetadata => ({
  id,
  aggregate_id: "record-1",
  revision_no: revisionNo,
  based_on_revision_id: revisionNo === 1 ? null : "revision-1",
  schema_id: "cmp.catalog-record",
  schema_version: "1.0.0",
  content_hash: `hash-${revisionNo}`,
  created_at: "2026-07-22T00:00:00Z",
  created_by: "test-user",
  change_reason: `revision ${revisionNo}`,
  organization_id: "org-1",
  project_id: "project-1",
  classification: "internal",
  lifecycle_state: "draft",
});

function response(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(digest)).map((item) => item.toString(16).padStart(2, "0")).join("");
}

describe("ExactRecordDatasheetPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("renders the requested immutable revision instead of the record head", async () => {
    vi.spyOn(window, "innerWidth", "get").mockReturnValue(1440);
    const revision1 = {
      ...metadata("revision-1", 1),
      content: {
        table_revision_id: "table-revision-1",
        name: "Requested exact revision",
        external_key: null,
        description: "Immutable requested content",
        folder_id: null,
        folder_revision_id: null,
        values: [{
          attribute_definition_id: "attribute-1",
          attribute_definition_revision_id: "attribute-revision-1",
          data_type: "number" as const,
          original_value: "450",
          original_unit_string: "MPa",
          normalized_value: "450000000",
          normalized_unit: "Pa",
          quantity_semantics: "stress",
        }],
      },
    };
    const revision2 = {
      ...metadata("revision-2", 2),
      content: { ...revision1.content, name: "Current head must not render", values: [] },
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/catalog/records/record-1")) return response({ record_id: "record-1", table_id: "table-1", current_revision: revision2 });
      if (url.endsWith("/catalog/records/record-1/revisions")) return response({ items: [revision2, revision1] });
      if (url.endsWith("/catalog/tables/table-1/attributes")) return response({
        items: [{
          attribute_definition_id: "attribute-1",
          table_id: "table-1",
          current_revision: {
            ...metadata("attribute-revision-1", 1),
            content: {
              table_revision_id: "table-revision-1",
              key: "yield_strength",
              name: "Yield strength",
              data_type: "number",
              required: false,
              quantity_semantics: "stress",
              normalized_unit: "Pa",
              minimum_number: null,
              maximum_number: null,
              minimum_length: null,
              maximum_length: null,
              pattern: null,
              allowed_values: [],
              reference_table_id: null,
              help_text: null,
            },
          },
        }],
      });
      if (url.endsWith("/catalog/tables/table-1/layouts")) return response({ items: [{
        layout_id: "layout-1", table_id: "table-1", revision: metadata("layout-revision-1", 1), name: "Material properties", description: null,
        items: [{ attribute_definition_id: "attribute-1", attribute_definition_revision_id: "attribute-revision-1", section: "Mechanical", ordinal: 1 }],
      }] });
      if (url.includes("/catalog/explorer/tables")) return response({ items: [] });
      if (url.includes("/catalog/workflow-explorer/")) {
        const root = {
          record_id: "record-1",
          record_revision_id: "revision-1",
          revision_no: 1,
          table_id: "table-1",
          name: "Requested exact revision",
          external_key: null,
          data_category: "technical_data",
          domain_binding: {
            binding_id: "binding-1",
            record_id: "record-1",
            record_revision_id: "revision-1",
            kind: "material",
            object_id: "material-1",
            revision_id: "material-revision-1",
            workbench_path: "/materials/material-1",
          },
        };
        const endpoint = (recordId: string, revisionId: string, name: string, kind: "test_run" | "material_model" | "neutral_solver_card") => ({
          record_id: recordId,
          record_revision_id: revisionId,
          revision_no: 1,
          table_id: `table-${kind}`,
          name,
          external_key: null,
          data_category: kind === "test_run" ? "test_data" : kind === "material_model" ? "simulation_data" : null,
          domain_binding: {
            binding_id: `binding-${recordId}`,
            record_id: recordId,
            record_revision_id: revisionId,
            kind,
            object_id: `object-${recordId}`,
            revision_id: `object-revision-${recordId}`,
            workbench_path: "/modeling",
          },
        });
        const tensile = {
          ...endpoint("record-test", "revision-test", "Room tensile test", "test_run"),
          domain_binding: null,
          domain_bindings: [],
        };
        const model = endpoint("record-model", "revision-model", "Transitive viscoelastic model", "material_model");
        const card = endpoint("record-card", "revision-card", "OpenRadioss material card", "neutral_solver_card");
        const link = (id: string, source: typeof root | typeof tensile, target: typeof tensile | typeof model | typeof card) => ({
          record_link_id: id,
          current_revision: { ...metadata(`revision-${id}`, 1), content: {} },
          link_type_revision: {
            ...metadata(`link-type-${id}`, 1),
            content: {
              key: id,
              name: id,
              source_table_id: source.table_id,
              source_table_revision_id: "source-table-revision",
              target_table_id: target.table_id,
              target_table_revision_id: "target-table-revision",
              forward_label: "uses",
              reverse_label: "used by",
              source_cardinality: "many",
              target_cardinality: "many",
              description: null,
            },
          },
          source,
          target,
        });
        return response({
          root,
          nodes: [root, tensile, model, card],
          links: [
            link("root-test", root, tensile),
            link("test-model", tensile, model),
            link("root-card", root, card),
          ],
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    }));

    render(<ExactRecordDatasheetPage config={{ baseUrl: "/api/v1", accessToken: "test-token" }} recordId="record-1" revisionId="revision-1" onNavigate={vi.fn()} />);

    expect(await screen.findByRole("heading", { name: "Requested exact revision", level: 1 })).toBeTruthy();
    expect(await screen.findByText("450")).toBeTruthy();
    expect(screen.getByText("MPa")).toBeTruthy();
    expect(screen.queryByText(/450000000 Pa/)).toBeNull();
    expect(screen.queryByText("Current head must not render")).toBe(null);
    const datasheetText = document.querySelector(".exact-record-datasheet")?.textContent ?? "";
    expect(datasheetText).not.toMatch(/\bdraft\b/i);
    expect(datasheetText).toContain("revision 1");
    expect(datasheetText).toContain("Related data");
    expect(datasheetText).toContain("Type Material");
    expect(datasheetText).toContain("Test Data");
    expect(datasheetText).toContain("Room tensile test");
    expect(datasheetText).toContain("Test Data · uses · r1");
    expect(datasheetText).toContain("Solver Cards");
    expect(datasheetText).toContain("OpenRadioss material card");
    expect(datasheetText).toContain("Solver Card · uses · r1");
    expect(datasheetText).not.toContain("Transitive viscoelastic model");
    expect(screen.queryByRole("button", { name: /record context pane/i })).toBeNull();
  });

  it("loads only the exact bound canonical Test Data revision and keeps its summary through retry", async () => {
    const testRevision = {
      ...metadata("record-test-revision-1", 1),
      aggregate_id: "record-test",
      content: {
        table_revision_id: "table-test-revision-1",
        name: "Room-temperature tensile test",
        external_key: "CMP-TEST-DP780",
        description: null,
        folder_id: null,
        folder_revision_id: null,
        values: [{
          attribute_definition_id: "attribute-test-kind",
          attribute_definition_revision_id: "attribute-test-kind-revision-1",
          data_type: "text" as const,
          value: "Tensile",
        }],
      },
    };
    const root = {
      record_id: "record-test",
      record_revision_id: "record-test-revision-1",
      revision_no: 1,
      table_id: "table-test",
      name: "Room-temperature tensile test",
      external_key: "CMP-TEST-DP780",
      data_category: "test_data",
      domain_binding: {
        binding_id: "binding-test-data",
        record_id: "record-test",
        record_revision_id: "record-test-revision-1",
        kind: "test_data",
        object_id: "test-document-1",
        revision_id: "test-document-revision-3",
        workbench_path: "/datasets/test-json",
      },
    };
    const canonical = {
      document_type: "cmp.test-data",
      schema_version: "1.0.0",
      document_id: "CMP-TEST-DP780-ROOM",
      material: { maker: "CMP", grade: "DP780", lot_batch: null },
      test: {
        date: "2026-08-14",
        operator: "Demo engineer",
        laboratory: "CMP laboratory",
        method: "Tensile",
        equipment_maker: null,
        equipment_model: null,
      },
      specimen: { specimen_id: "DP780-T-01", description: null },
      conditions: [],
      channels: [
        {
          key: "engineering_strain",
          name: "Engineering strain",
          quantity_semantics: "mechanics.strain.engineering",
          axis_role: "independent",
          original_unit_string: "1",
          normalized_unit: "1",
          normalization: { scale: "1", offset: "0" },
          original_values: ["0", "0.001", "0.01", "0.14"],
          normalized_values: ["0", "0.001", "0.01", "0.14"],
          missing_reasons: [null, null, null, null],
        },
        {
          key: "engineering_stress",
          name: "Engineering stress",
          quantity_semantics: "mechanics.stress.engineering",
          axis_role: "dependent",
          original_unit_string: "Pa",
          normalized_unit: "Pa",
          normalization: { scale: "1", offset: "0" },
          original_values: ["0", "210000000", "575000000", "775000000"],
          normalized_values: ["0", "210000000", "575000000", "775000000"],
          missing_reasons: [null, null, null, null],
        },
      ],
      source: {
        file_name: "cmp-test-dp780-room.json",
        media_type: "application/json",
        sha256: "a".repeat(64),
      },
    };
    let contentAttempts = 0;
    const requests: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      requests.push(url);
      if (url.endsWith("/catalog/records/record-test")) {
        return response({
          record_id: "record-test",
          table_id: "table-test",
          current_revision: testRevision,
        });
      }
      if (url.endsWith("/catalog/records/record-test/revisions")) {
        return response({ items: [testRevision] });
      }
      if (url.includes("/catalog/workflow-explorer/")) {
        return response({ root, nodes: [root], links: [] });
      }
      if (url.endsWith("/catalog/records/record-test/revisions/record-test-revision-1/source-availability?published_only=true")) {
        return response({ available: true, published: true, ready: true });
      }
      if (url.endsWith("/catalog/tables/table-test/attributes")) {
        return response({ items: [{
          attribute_definition_id: "attribute-test-kind",
          table_id: "table-test",
          current_revision: {
            ...metadata("attribute-test-kind-revision-1", 1),
            content: {
              table_revision_id: "table-test-revision-1",
              key: "test_kind",
              name: "Test kind",
              data_type: "text",
              required: true,
              quantity_semantics: null,
              normalized_unit: null,
              minimum_number: null,
              maximum_number: null,
              minimum_length: null,
              maximum_length: null,
              pattern: null,
              allowed_values: [],
              reference_table_id: null,
              help_text: null,
            },
          },
        }] });
      }
      if (url.endsWith("/catalog/tables/table-test/layouts")) {
        return response({ items: [{
          layout_id: "layout-test",
          table_id: "table-test",
          revision: metadata("layout-test-revision-1", 1),
          name: "Test Data summary",
          description: null,
          items: [{
            attribute_definition_id: "attribute-test-kind",
            attribute_definition_revision_id: "attribute-test-kind-revision-1",
            section: "Test setup",
            ordinal: 1,
          }],
        }] });
      }
      if (url.endsWith("/catalog/tables/table-test/folders")) {
        return response({ items: [] });
      }
      if (url.endsWith("/catalog/tables/table-test/records")) {
        return response({ items: [] });
      }
      if (url.includes("/catalog/explorer/tables")) return response({ items: [] });
      if (
        url.endsWith(
          "/test-data-documents/test-document-1/revisions/test-document-revision-3/content",
        )
      ) {
        contentAttempts += 1;
        return contentAttempts === 1
          ? response({ detail: "Temporary exact content failure" }, 503)
          : response(canonical);
      }
      throw new Error(`Unexpected request: ${url}`);
    }));

    render(
      <ExactRecordDatasheetPage
        config={{ baseUrl: "/api/v1", accessToken: "test-token" }}
        recordId="record-test"
        revisionId="record-test-revision-1"
        onNavigate={vi.fn()}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Test Data", level: 1 })).toBeTruthy();
    expect(await screen.findByText("Temporary exact content failure")).toBeTruthy();
    expect(await screen.findByRole("heading", { name: "Test Data summary" })).toBeTruthy();
    expect(screen.getByText("Tensile")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Retry exact Test Data" }));

    expect(await screen.findByRole("heading", { name: "Exact measurements" })).toBeTruthy();
    expect(
      screen.getByRole("img", {
        name: "Engineering stress by Engineering strain exact Test Data curve",
      }),
    ).toBeTruthy();
    const points = screen.getByRole("table", { name: "Exact Test Data points" });
    expect(points.textContent).toContain("Engineering strain (1)");
    expect(points.textContent).toContain("Engineering stress (Pa)");
    expect(points.textContent).toContain("210,000,000");
    expect(points.textContent).toContain("775,000,000");
    expect(screen.getByRole("button", { name: "Download exact Test Data JSON" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download summary CSV" })).toBeTruthy();
    expect(await screen.findByRole("button", { name: "Download JSON" })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Download CSV" }).length).toBeGreaterThan(0);
    expect(contentAttempts).toBe(2);
    expect(
      requests.filter((url) => url.includes("/test-data-documents/")),
    ).toEqual([
      expect.stringContaining(
        "/test-data-documents/test-document-1/revisions/test-document-revision-3/content",
      ),
      expect.stringContaining(
        "/test-data-documents/test-document-1/revisions/test-document-revision-3/content",
      ),
    ]);
    expect(requests.some((url) => /latest/i.test(url))).toBe(false);
  });

  it("shows exact Solver Card target, release, actions, and source evidence", async () => {
    const cardRevision = {
      ...metadata("record-card-revision-1", 1),
      aggregate_id: "record-card",
      content: {
        table_revision_id: "table-card-revision-1",
        name: "DP780 OpenRadioss native card",
        external_key: "CMP-CARD-DP780",
        description: "Released solver-ready target artifact.",
        folder_id: null,
        folder_revision_id: null,
        values: [],
      },
    };
    const root = {
      record_id: "record-card",
      record_revision_id: "record-card-revision-1",
      revision_no: 1,
      table_id: "table-card",
      name: "DP780 OpenRadioss native card",
      external_key: "CMP-CARD-DP780",
      data_category: "simulation_data",
      domain_binding: {
        binding_id: "binding-card",
        record_id: "record-card",
        record_revision_id: "record-card-revision-1",
        kind: "neutral_solver_card",
        object_id: "card-1",
        revision_id: "card-revision-2",
        workbench_path: "/exports",
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/catalog/records/record-card"))
          return response({
            record_id: "record-card",
            table_id: "table-card",
            current_revision: cardRevision,
          });
        if (url.endsWith("/catalog/records/record-card/revisions"))
          return response({ items: [cardRevision] });
        if (url.endsWith("/catalog/tables/table-card/attributes"))
          return response({ items: [] });
        if (url.endsWith("/catalog/tables/table-card/layouts"))
          return response({ items: [] });
        if (url.endsWith("/catalog/tables/table-card/folders"))
          return response({ items: [] });
        if (url.endsWith("/catalog/tables/table-card/records"))
          return response({ items: [] });
        if (url.includes("/catalog/explorer/tables")) return response({ items: [] });
        if (url.includes("/catalog/workflow-explorer/"))
          return response({ root, nodes: [root], links: [] });
        if (url.includes("/neutral-solver-cards/card-1/mapping-report?revision_id=card-revision-2"))
          return response({
            mapping_report_sha256: "b".repeat(64),
            exportable: true,
            report: {
              items: [{
                name: "post_necking_extension",
                ir_path: "/properties/post_necking_extension",
                target_representation: "*PLASTIC extrapolation",
                status: "approximated",
                detail: "Review the bounded extension.",
              }],
            },
          });
        if (url.includes("/neutral-solver-cards/card-1?revision_id=card-revision-2"))
          return response({
            solver_card_id: "card-1",
            neutral_material_id: "neutral-1",
            target: {
              solver: "openradioss",
              version: "2025",
              unit_system: "kg_m_s",
            },
            current_revision: {
              ...metadata("card-revision-2", 2),
              aggregate_id: "card-1",
              lifecycle_state: "published",
              content: {
                neutral_material_revision_id: "neutral-revision-3",
                card_sha256: "a".repeat(64),
                mapping_statuses: {},
                solver_material_id: 301,
                material_name: "DP780",
              },
            },
          });
        if (url.includes("/neutral-solver-cards/card-1/preview?revision_id=card-revision-2"))
          return new Response("*MATERIAL, NAME=CMP_DEMO_DP780_NEUTRAL\n*ELASTIC\n210000., 0.3\n");
        throw new Error(`Unexpected request: ${url}`);
      }),
    );

    render(
      <ExactRecordDatasheetPage
        config={{ baseUrl: "/api/v1", accessToken: "test-token" }}
        recordId="record-card"
        revisionId="record-card-revision-1"
        onNavigate={vi.fn()}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Solver Card", level: 1 })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Simulation Data", level: 1 })).toBeNull();
    expect(screen.queryByText("Type Solver Card")).toBeNull();
    expect(screen.queryByText("Code CMP-CARD-DP780")).toBeNull();
    expect(await screen.findByRole("heading", { name: "Solver Card details" })).toBeTruthy();
    expect(screen.queryByText("Released solver-ready target artifact.")).toBeNull();
    expect(screen.getByLabelText("Native solver card preview").textContent).toContain("*MATERIAL");
    expect(await screen.findByText("OpenRadioss 2025")).toBeTruthy();
    expect(screen.getByText("Native ASCII .rad")).toBeTruthy();
    expect(screen.getByText("kg · m · s")).toBeTruthy();
    expect(screen.getByText("published")).toBeTruthy();
    expect(screen.getByText("r2")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Preview .rad" })).toBeNull();
    expect(screen.getByText("Review required")).toBeTruthy();
    expect(screen.getByText("Post-necking extension")).toBeTruthy();
    expect(screen.queryByText("Review Post-necking extension before download.")).toBeNull();
    expect(screen.getByText("Exact source and technical details").closest("details")?.open).toBe(false);
    expect(screen.queryByText("Exact source evidence")).toBeNull();
    const reviewed = screen.getByRole("checkbox", { name: "Reviewed" });
    const download = screen.getByRole("button", { name: "Download .rad" }) as HTMLButtonElement;
    expect(download.disabled).toBe(true);
    fireEvent.click(reviewed);
    expect(download.disabled).toBe(false);
    const delivery = document.querySelector(".exact-solver-card-delivery");
    expect(delivery?.classList.contains("preview-expanded")).toBe(false);
    const expand = screen.getByRole("button", { name: "Expand preview" });
    expect(expand.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(expand);
    expect(screen.getByRole("button", { name: "Collapse preview" }).getAttribute("aria-expanded")).toBe("true");
    expect(delivery?.classList.contains("preview-expanded")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Collapse preview" }));
    expect(screen.getByRole("button", { name: "Expand preview" }).getAttribute("aria-expanded")).toBe("false");
    expect(delivery?.classList.contains("preview-expanded")).toBe(false);
    expect(screen.getByText("Neutral Material")).toBeTruthy();
    expect(screen.getByText("neutral-revision-3")).toBeTruthy();
  });

  it("reads the exact bound Processing Output artifact into a result-dominant Simulation Data view", async () => {
    const processingRevision = {
      ...metadata("processing-record-revision-1", 1),
      aggregate_id: "processing-record",
      content: {
        table_revision_id: "processing-table-revision-1",
        name: "Internal processing output label",
        external_key: "CMP-PROCESS-DP780",
        description: "Catalog projection helper must not replace output content.",
        folder_id: null,
        folder_revision_id: null,
        values: [],
      },
    };
    const workupStage = {
      ordinal: 1,
      method_id: "metal.engineering_to_true_plastic",
      method_version: "1.0.0",
      point_count: 3,
      series: [
        { quantity: "strain.true_plastic", unit: "1", values: [0.001, 0.05, 0.1] },
        { quantity: "stress.true", unit: "Pa", values: [450_000_000, 580_000_000, 620_000_000] },
      ],
      diagnostics: [],
      scalar_results: [
        { key: "necking_engineering_strain", quantity_semantics: "strain.engineering.necking", value: 0.1, unit: "1" },
        { key: "necking_engineering_stress", quantity_semantics: "stress.engineering.necking", value: 620_000_000, unit: "Pa" },
      ],
    };
    const candidate = {
      family: "voce",
      response: [450_000_000, 600_000_000, 680_000_000],
      residual: [0, 0, 0],
      tangent: [null, null, null],
      parameter_names: ["sigma_0_pa", "q_pa", "b"],
      parameter_units: ["Pa", "Pa", "1"],
      lower: [45_000_000, 0, 0.000001],
      initial: [450_000_000, 200_000_000, 100],
      fitted: [455_000_000, 223_000_000, 41.2],
      upper: [1_300_000_000, 6_800_000_000, 1000],
      rmse_pa: 970_000,
      relative_rmse: 0.009274,
      objective: 0.01,
      scipy_cost: 0.005,
      convergence: true,
      nfev: 12,
      active_bound: [],
      jacobian_rank: 3,
      jacobian_tolerance: 0.00001,
      jacobian_condition: 19.5,
      identifiability: "identifiable",
      uncertainty: "not_provided",
      objective_history: [0.1, 0.01],
    };
    const fitStage = {
      ordinal: 2,
      method_id: "metal.hardening_fit_extrapolate",
      method_version: "1.0.0",
      point_count: 3,
      series: [
        { quantity: "strain.true_plastic", unit: "1", values: [0, 0.5, 1] },
        { quantity: "stress.hardening.selected", unit: "Pa", values: [455_000_000, 660_000_000, 680_000_000] },
      ],
      diagnostics: [],
      scalar_results: [
        { key: "fit.observed_maximum_strain", quantity_semantics: "strain.domain.observed.maximum", value: 0.1, unit: "1" },
      ],
      fit_candidates: [candidate],
    };
    const fitDecision = {
      candidate_key: "voce",
      mode: "single",
      primary_law: "voce",
      secondary_law: null,
      primary_weight: null,
      parameter_sets: [{
        law: "voce",
        parameters: [
          { name: "sigma_0_pa", value: 455_000_000, unit: "Pa", lower: 45_000_000, upper: 1_300_000_000 },
          { name: "q_pa", value: 223_000_000, unit: "Pa", lower: 0, upper: 6_800_000_000 },
          { name: "b", value: 41.2, unit: "1", lower: 0.000001, upper: 1000 },
        ],
      }],
      fit_minimum: 0,
      fit_maximum: 0.1,
      extrapolation_maximum: 1,
      extrapolation_policy: "bounded",
      metric_definition: "relative_rmse",
      metric_value: 0.0017717888019071902,
      requested_term_policy: null,
      actual_term_count: null,
      selection_reason: "Selected exact server result.",
      warning_acknowledged: true,
    };
    const artifact = JSON.stringify({
      document_type: "cmp.processing-output",
      document_version: "1.5.0",
      output_id: "processing-output-1",
      source_document: { aggregate_id: "test-data-1", revision_id: "test-data-revision-1" },
      source_canonical_artifact_sha256: "source-canonical-sha",
      mapping_profile: { aggregate_id: "mapping-1", revision_id: "mapping-revision-1" },
      source_processing_output: null,
      source_processing_output_sha256: null,
      steps: [
        { method_id: "metal.engineering_to_true_plastic", method_version: "1.0.0", options: {} },
        { method_id: "metal.hardening_fit_extrapolate", method_version: "1.0.0", options: {} },
      ],
      workup_overrides: [{
        kind: "necking_boundary",
        original_value: 10,
        original_unit: "observed-point-index",
        canonical_value: 10,
        canonical_unit: "observed-point-index",
        reason: "Exact reviewed decision.",
      }],
      fit_decision: fitDecision,
      result: {
        execution_mode: "preview",
        promotable: false,
        source_document_sha256: "source-document-sha",
        mapping_profile_sha256: "mapping-profile-sha",
        independent_quantity: "strain.engineering",
        stages: [workupStage, fitStage],
      },
    });
    const outputDigest = await sha256(artifact);
    const root = {
      record_id: "processing-record",
      record_revision_id: "processing-record-revision-1",
      revision_no: 1,
      table_id: "processing-table",
      name: "Internal processing output label",
      external_key: "CMP-PROCESS-DP780",
      data_category: "simulation_data",
      domain_binding: {
        binding_id: "processing-binding",
        record_id: "processing-record",
        record_revision_id: "processing-record-revision-1",
        kind: "processing_output",
        object_id: "processing-output-1",
        revision_id: "processing-output-revision-1",
        workbench_path: "/modeling",
      },
    };
    const testData = {
      record_id: "test-record",
      record_revision_id: "test-record-revision-1",
      revision_no: 1,
      table_id: "test-table",
      name: "Qualified tensile result",
      external_key: "CMP-TEST-DP780",
      data_category: "test_data",
      domain_binding: {
        binding_id: "test-binding",
        record_id: "test-record",
        record_revision_id: "test-record-revision-1",
        kind: "test_data",
        object_id: "test-data-1",
        revision_id: "test-data-revision-1",
        workbench_path: "/modeling",
      },
    };
    const link = {
      record_link_id: "processing-source-link",
      current_revision: { ...metadata("link-revision-1", 1), content: {} },
      link_type_revision: {
        ...metadata("link-type-revision-1", 1),
        content: {
          key: "uses-test-data",
          name: "uses test data",
          source_table_id: "test-table",
          source_table_revision_id: "test-table-revision-1",
          target_table_id: "processing-table",
          target_table_revision_id: "processing-table-revision-1",
          forward_label: "produces",
          reverse_label: "uses",
          source_cardinality: "many",
          target_cardinality: "many",
          description: null,
        },
      },
      source: testData,
      target: root,
    };
    const outputSummary = {
      processing_output_id: "processing-output-1",
      current_revision: { ...metadata("processing-output-revision-1", 1), aggregate_id: "processing-output-1" },
      label: "Stored processing result",
      source_document: { aggregate_id: "test-data-1", revision_id: "test-data-revision-1" },
      source_document_sha256: "source-document-sha",
      source_canonical_artifact_sha256: "source-canonical-sha",
      mapping_profile: { aggregate_id: "mapping-1", revision_id: "mapping-revision-1" },
      mapping_profile_sha256: "mapping-profile-sha",
      steps: [
        { method_id: "metal.engineering_to_true_plastic", method_version: "1.0.0", options: {} },
        { method_id: "metal.hardening_fit_extrapolate", method_version: "1.0.0", options: {} },
      ],
      independent_quantity: "strain.engineering",
      stage_count: 2,
      final_point_count: 3,
      output_artifact_id: "artifact-1",
      output_sha256: outputDigest,
      source_processing_output: null,
      source_processing_output_sha256: null,
      workup_overrides: [],
      fit_decision: fitDecision,
      export_provenance: null,
    };
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/catalog/records/processing-record")) return response({ record_id: "processing-record", table_id: "processing-table", current_revision: processingRevision });
      if (url.endsWith("/catalog/records/processing-record/revisions")) return response({ items: [processingRevision] });
      if (url.includes("/catalog/workflow-explorer/")) return response({ root, nodes: [root, testData], links: [link] });
      if (url.endsWith("/processing-outputs")) return response({ items: [outputSummary] });
      if (url.endsWith("/processing-outputs/processing-output-1/content")) return new Response(artifact, { headers: { "Content-Type": "application/vnd.cmp.processing-output+json" } });
      if (url.includes("/catalog/explorer/tables")) return response({ items: [] });
      if (url.endsWith("/catalog/tables/processing-table/folders")) return response({ items: [] });
      if (url.endsWith("/catalog/tables/processing-table/records")) return response({ items: [] });
      throw new Error(`Unexpected request: ${url}`);
    }));
    const onNavigate = vi.fn();

    render(
      <ExactRecordDatasheetPage
        config={{ baseUrl: "/api/v1", accessToken: "test-token" }}
        recordId="processing-record"
        revisionId="processing-record-revision-1"
        onNavigate={onNavigate}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Simulation Data", level: 1 })).toBeTruthy();
    expect(await screen.findByRole("img", { name: "Selected true stress in MPa by True plastic strain in 1" })).toBeTruthy();
    expect(screen.queryByText("Type Processing Output")).toBeNull();
    expect(screen.queryByText("Code CMP-PROCESS-DP780")).toBeNull();
    const processingStages = screen.getByRole("heading", { name: "Processing stages" });
    expect(processingStages.closest("details")?.open).toBe(false);
    expect(screen.getByRole("heading", { name: "True stress–plastic strain result" })).toBeTruthy();
    expect(screen.getAllByText("Voce").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Converged").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Identifiable").length).toBeGreaterThan(0);
    expect(screen.getByText("Relative rmse 0.1772 %")).toBeTruthy();
    expect(screen.queryByText("Relative rmse 0.9274 %")).toBeNull();
    expect(screen.getByText("Manual necking boundary · point 10")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Linked records" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "CMP-TEST-DP780" }));
    expect(onNavigate).toHaveBeenCalledWith("/materials/records/test-record/revisions/test-record-revision-1");
    expect(screen.queryByText("Catalog projection helper must not replace output content.")).toBeNull();
    expect(document.querySelector(".layout-projection")).toBeNull();
    const technicalDetails = screen.getByText("Revision history and technical details").closest("details");
    expect(technicalDetails?.open).toBe(false);
    fireEvent.click(screen.getByText("Revision history and technical details"));
    expect(screen.getByRole("heading", { name: "Processing stages" })).toBeTruthy();
    expect(screen.getByText("0.9274 %")).toBeTruthy();
  });
});
