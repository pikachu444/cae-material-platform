import { act, render, screen, waitFor } from "@testing-library/react";
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

const secondTable = {
  ...table,
  table_id: "20000000-0000-4000-8000-000000000001",
  current_revision: {
    ...table.current_revision,
    id: "20000000-0000-4000-8000-000000000002",
    aggregate_id: "20000000-0000-4000-8000-000000000001",
    content: { key: "test_data", name: "Test Data", description: null },
  },
};

function attributeFor(sourceTable: typeof table, name: string, idPrefix: string) {
  return {
    attribute_definition_id: `${idPrefix}0000-0000-4000-8000-000000000006`,
    table_id: sourceTable.table_id,
    current_revision: {
      ...sourceTable.current_revision,
      id: `${idPrefix}0000-0000-4000-8000-000000000007`,
      aggregate_id: `${idPrefix}0000-0000-4000-8000-000000000006`,
      content: {
        table_revision_id: sourceTable.current_revision.id,
        key: name.toLowerCase().replaceAll(" ", "_"),
        name,
        data_type: "text" as const,
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
  };
}

const mocks = vi.hoisted(() => ({
  listTables: vi.fn(),
  listAttributes: vi.fn(),
  listLayouts: vi.fn(),
  listSubsets: vi.fn(),
  listLinkTypes: vi.fn(),
  createTable: vi.fn(),
  createAttribute: vi.fn(),
  createLayout: vi.fn(),
  createSubset: vi.fn(),
  createLinkType: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return {
    ...original,
    listConfigurableCatalogTables: mocks.listTables,
    listConfigurableCatalogAttributes: mocks.listAttributes,
    listConfigurableCatalogLayouts: mocks.listLayouts,
    listConfigurableCatalogSubsets: mocks.listSubsets,
    listConfigurableCatalogLinkTypes: mocks.listLinkTypes,
    createConfigurableCatalogTable: mocks.createTable,
    createConfigurableCatalogAttribute: mocks.createAttribute,
    createConfigurableCatalogLayout: mocks.createLayout,
    createConfigurableCatalogSubset: mocks.createSubset,
    createConfigurableCatalogLinkType: mocks.createLinkType,
  };
});

describe("ConfigurableCatalogAdmin", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listTables.mockResolvedValue({ data: { items: [table] }, etag: null });
    mocks.listAttributes.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.listLayouts.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.listSubsets.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.listLinkTypes.mockResolvedValue({ data: { items: [] }, etag: null });
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
    mocks.createLinkType.mockResolvedValue({
      data: {
        link_type_id: "10000000-0000-4000-8000-000000000008",
        current_revision: {
          ...table.current_revision,
          id: "10000000-0000-4000-8000-000000000009",
          aggregate_id: "10000000-0000-4000-8000-000000000008",
          content: {
            key: "has_test_data",
            name: "Test evidence",
            source_table_id: table.table_id,
            source_table_revision_id: table.current_revision.id,
            target_table_id: table.table_id,
            target_table_revision_id: table.current_revision.id,
            forward_label: "has test evidence",
            reverse_label: "tests material",
            source_cardinality: "many",
            target_cardinality: "many",
            description: null,
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
    await user.type(screen.getAllByRole("textbox", { name: "Description" })[1]!, "Supplier display value used in datasheets.");
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
          help_text: "Supplier display value used in datasheets.",
        }),
      }),
    );
  });

  it("keeps table-scoped objects in a three-pane editor and creates an exact-revision Link Type", async () => {
    const user = userEvent.setup();
    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    expect(await screen.findByRole("heading", { name: "Database design" })).toBeTruthy();
    expect(screen.getByLabelText("Database objects")).toBeTruthy();
    expect((screen.getByLabelText("Current table") as HTMLSelectElement).value).toBe(table.table_id);
    await user.click(screen.getByRole("button", { name: "Link Types" }));
    await user.click(screen.getByRole("button", { name: "Add Link Type" }));
    await user.click(screen.getByRole("button", { name: "Save new Link Type" }));

    await waitFor(() => expect(mocks.createLinkType).toHaveBeenCalledOnce());
    expect(mocks.createLinkType).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        content: expect.objectContaining({
          source_table_revision_id: table.current_revision.id,
          target_table_revision_id: table.current_revision.id,
          source_cardinality: "many",
          target_cardinality: "many",
        }),
      }),
    );
  });

  it("keeps the newest Table definitions when an older request resolves late", async () => {
    const user = userEvent.setup();
    let resolveFirstTable!: (value: { data: { items: ReturnType<typeof attributeFor>[] }; etag: null }) => void;
    const firstTableRequest = new Promise<{ data: { items: ReturnType<typeof attributeFor>[] }; etag: null }>((resolve) => {
      resolveFirstTable = resolve;
    });
    const firstAttribute = attributeFor(table, "Material family", "31");
    const secondAttribute = attributeFor(secondTable, "Test method", "32");
    mocks.listTables.mockResolvedValue({ data: { items: [table, secondTable] }, etag: null });
    mocks.listAttributes.mockImplementation((_config, tableId: string) =>
      tableId === table.table_id
        ? firstTableRequest
        : Promise.resolve({ data: { items: [secondAttribute] }, etag: null }),
    );

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    const tableSelector = await screen.findByLabelText("Current table");
    await waitFor(() => expect(mocks.listAttributes).toHaveBeenCalledWith(expect.anything(), table.table_id));
    await user.selectOptions(tableSelector, secondTable.table_id);
    await user.click(screen.getByRole("button", { name: "Attributes" }));
    expect(await screen.findByText("Test method")).toBeTruthy();

    await act(async () => {
      resolveFirstTable({ data: { items: [firstAttribute] }, etag: null });
      await firstTableRequest;
    });

    expect(screen.getByText("Test method")).toBeTruthy();
    expect(screen.queryByText("Material family")).toBeNull();
  });

  it("shows an actionable empty state instead of an empty Current table selector", async () => {
    mocks.listTables.mockResolvedValue({ data: { items: [] }, etag: null });

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    expect(await screen.findByText("No tables yet")).toBeTruthy();
    expect(screen.queryByLabelText("Current table")).toBeNull();
    expect((screen.getByRole("button", { name: "Add Table" }) as HTMLButtonElement).disabled).toBe(false);
  });
});
