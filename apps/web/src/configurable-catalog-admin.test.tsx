import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfigurableCatalogAdmin } from "./configurable-catalog-admin";

const table = {
  table_id: "10000000-0000-4000-8000-000000000001",
  current_revision: {
    id: "10000000-0000-4000-8000-000000000002",
    aggregate_id: "10000000-0000-4000-8000-000000000001",
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:catalog:configurable-table:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-07-17T09:00:00Z",
    created_by: "10000000-0000-4000-8000-000000000003",
    change_reason: "fixture",
    organization_id: "10000000-0000-4000-8000-000000000004",
    project_id: "10000000-0000-4000-8000-000000000005",
    classification: "internal" as const,
    lifecycle_state: "draft" as const,
    content: { key: "materials", name: "Materials", description: null },
  },
};

const mocks = vi.hoisted(() => ({
  listTables: vi.fn(),
  listAttributes: vi.fn(),
  listLayouts: vi.fn(),
  listSubsets: vi.fn(),
  createTable: vi.fn(),
  createAttribute: vi.fn(),
  createLayout: vi.fn(),
  createSubset: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return {
    ...original,
    listConfigurableCatalogTables: mocks.listTables,
    listConfigurableCatalogAttributes: mocks.listAttributes,
    listConfigurableCatalogLayouts: mocks.listLayouts,
    listConfigurableCatalogSubsets: mocks.listSubsets,
    createConfigurableCatalogTable: mocks.createTable,
    createConfigurableCatalogAttribute: mocks.createAttribute,
    createConfigurableCatalogLayout: mocks.createLayout,
    createConfigurableCatalogSubset: mocks.createSubset,
  };
});

describe("ConfigurableCatalogAdmin", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listTables.mockResolvedValue({ data: { items: [table] }, etag: null });
    mocks.listAttributes.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.listLayouts.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.listSubsets.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.createAttribute.mockResolvedValue({
      data: {
        attribute_definition_id: "10000000-0000-4000-8000-000000000006",
        table_id: table.table_id,
        current_revision: {
          ...table.current_revision,
          id: "10000000-0000-4000-8000-000000000007",
          aggregate_id: "10000000-0000-4000-8000-000000000006",
          content: {
            table_revision_id: table.current_revision.id,
            key: "manufacturer",
            name: "Manufacturer",
            data_type: "text",
            required: false,
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
      },
      etag: null,
    });
  });

  it("loads a Table and creates a typed Attribute through the actual API contract", async () => {
    const user = userEvent.setup();
    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Materials" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Add Attribute revision 1" }));

    await waitFor(() => expect(mocks.createAttribute).toHaveBeenCalledOnce());
    expect(mocks.createAttribute).toHaveBeenCalledWith(
      expect.anything(),
      table.table_id,
      expect.objectContaining({
        content: expect.objectContaining({
          table_revision_id: table.current_revision.id,
          key: "manufacturer",
          data_type: "text",
        }),
      }),
    );
  });
});
