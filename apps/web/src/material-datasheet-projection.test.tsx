import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MaterialDatasheetProjection } from "./material-datasheet-projection";

const tableId = "91000000-0000-4000-8000-000000000001";
const recordId = "91000000-0000-4000-8000-000000000002";
const tableRevisionId = "91000000-0000-4000-8000-000000000003";
const densityId = "91000000-0000-4000-8000-000000000004";
const curveId = "91000000-0000-4000-8000-000000000005";

function metadata(id: string, aggregateId: string) {
  return {
    id,
    aggregate_id: aggregateId,
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:catalog:test:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-07-21T00:00:00Z",
    created_by: recordId,
    change_reason: "fixture",
    organization_id: recordId,
    project_id: recordId,
    classification: "internal" as const,
    lifecycle_state: "draft" as const,
  };
}

const densityAttribute = {
  attribute_definition_id: densityId,
  table_id: tableId,
  current_revision: {
    ...metadata("91000000-0000-4000-8000-000000000014", densityId),
    content: {
      table_revision_id: tableRevisionId,
      key: "density",
      name: "Density",
      data_type: "number" as const,
      required: true,
      quantity_semantics: "mass density",
      normalized_unit: "kg/m^3",
      minimum_number: null,
      maximum_number: null,
      minimum_length: null,
      maximum_length: null,
      pattern: null,
      allowed_values: [],
      reference_table_id: null,
      help_text: "Original and normalized quantity",
    },
  },
};

const curveAttribute = {
  attribute_definition_id: curveId,
  table_id: tableId,
  current_revision: {
    ...metadata("91000000-0000-4000-8000-000000000015", curveId),
    content: {
      ...densityAttribute.current_revision.content,
      key: "stress_strain",
      name: "Stress–strain curve",
      data_type: "curve" as const,
      required: false,
      quantity_semantics: null,
      normalized_unit: null,
      help_text: null,
    },
  },
};

const record = {
  record_id: recordId,
  table_id: tableId,
  current_revision: {
    ...metadata("91000000-0000-4000-8000-000000000006", recordId),
    content: {
      table_revision_id: tableRevisionId,
      name: "DP780",
      external_key: "DP780",
      description: null,
      folder_id: null,
      folder_revision_id: null,
      values: [{
        attribute_definition_id: densityId,
        attribute_definition_revision_id: densityAttribute.current_revision.id,
        data_type: "number" as const,
        original_value: "7.85",
        original_unit_string: "g/cm^3",
        normalized_value: "7850",
        normalized_unit: "kg/m^3",
        quantity_semantics: "mass density",
      }, {
        attribute_definition_id: curveId,
        attribute_definition_revision_id: curveAttribute.current_revision.id,
        data_type: "curve" as const,
        artifact_id: "91000000-0000-4000-8000-000000000007",
        artifact_sha256: "b".repeat(64),
      }],
    },
  },
};

const layout = {
  layout_id: "91000000-0000-4000-8000-000000000008",
  table_id: tableId,
  revision: metadata("91000000-0000-4000-8000-000000000009", "91000000-0000-4000-8000-000000000008"),
  name: "Material datasheet",
  description: "Administrator-defined material layout",
  items: [{ attribute_definition_id: densityId, attribute_definition_revision_id: densityAttribute.current_revision.id, section: "Physical", ordinal: 1 }, { attribute_definition_id: curveId, attribute_definition_revision_id: curveAttribute.current_revision.id, section: "Curves", ordinal: 2 }],
};

const mocks = vi.hoisted(() => ({ record: vi.fn(), attributes: vi.fn(), layouts: vi.fn() }));

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return {
    ...original,
    getConfigurableCatalogRecord: mocks.record,
    listConfigurableCatalogAttributes: mocks.attributes,
    listConfigurableCatalogLayouts: mocks.layouts,
  };
});

describe("MaterialDatasheetProjection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.record.mockResolvedValue({ data: record, etag: null });
    mocks.attributes.mockResolvedValue({ data: { items: [densityAttribute, curveAttribute] }, etag: null });
    mocks.layouts.mockResolvedValue({ data: { items: [layout] }, etag: null });
  });

  it("projects administrator Layout order while preserving original and normalized quantity text", async () => {
    render(<MaterialDatasheetProjection config={{ baseUrl: "/api/v1", accessToken: "test" }} tableId={tableId} recordId={recordId} mode="properties"/>);

    expect(await screen.findByRole("heading", { name: "Material datasheet" })).toBeTruthy();
    expect(screen.getByText("7.85 g/cm^3")).toBeTruthy();
    expect(screen.getByTitle("7850 kg/m^3 · mass density")).toBeTruthy();
    expect(screen.queryByText("Stress–strain curve")).toBe(null);
  });

  it("keeps all typed Attribute data in the Evidence Layout disclosure", async () => {
    render(<MaterialDatasheetProjection config={{ baseUrl: "/api/v1", accessToken: "test" }} tableId={tableId} recordId={recordId} mode="evidence"/>);

    expect(await screen.findByRole("combobox", { name: "Material Layout" })).toBeTruthy();
    expect(screen.getByText("Stress–strain curve")).toBeTruthy();
    expect(screen.getByText("Curve artifact")).toBeTruthy();
    expect(screen.getByTitle(/SHA-256/).textContent).toContain("b".repeat(64));
  });
});
