import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ExactRecordDatasheetPage } from "./material-library";
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
    expect(datasheetText).toContain("Test Data");
    expect(datasheetText).toContain("Room tensile test");
    expect(datasheetText).toContain("Solver Cards");
    expect(datasheetText).toContain("OpenRadioss material card");
    expect(datasheetText).not.toContain("Transitive viscoelastic model");
    expect(screen.queryByRole("button", { name: /record context pane/i })).toBeNull();
  });
});
