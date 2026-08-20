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

const database = {
  database_id: "30000000-0000-4000-8000-000000000001",
  current_revision: {
    ...table.current_revision,
    id: "30000000-0000-4000-8000-000000000002",
    aggregate_id: "30000000-0000-4000-8000-000000000001",
    content: { key: "materials", name: "Materials database", description: null },
  },
};

const secondDatabase = {
  ...database,
  database_id: "40000000-0000-4000-8000-000000000001",
  current_revision: {
    ...database.current_revision,
    id: "40000000-0000-4000-8000-000000000002",
    aggregate_id: "40000000-0000-4000-8000-000000000001",
    content: { key: "testing", name: "Testing database", description: null },
  },
};

function attributeFor(
  sourceTable: typeof table,
  name: string,
  idPrefix: string,
) {
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
  listDatabases: vi.fn(),
  listProfiles: vi.fn(),
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
  reviseTable: vi.fn(),
  reviseDatabase: vi.fn(),
  reviseProfile: vi.fn(),
  reviseAttribute: vi.fn(),
  reviseLayout: vi.fn(),
  reviseSubset: vi.fn(),
  reviseLinkType: vi.fn(),
  validatePublication: vi.fn(),
  getDatabaseDesignAccess: vi.fn(),
  getAttributeRevision: vi.fn(),
  searchRecords: vi.fn(),
  deleteDraft: vi.fn(),
}));

vi.mock("./features/administration/database-design/api", async (importOriginal) => {
  const original = await importOriginal<
    typeof import("./features/administration/database-design/api")
  >();
  return {
    ...original,
    listConfigurableCatalogTables: mocks.listTables,
    listConfigurableCatalogDatabases: mocks.listDatabases,
    listConfigurableCatalogProfiles: mocks.listProfiles,
    listConfigurableCatalogAttributes: mocks.listAttributes,
    listConfigurableCatalogLayouts: mocks.listLayouts,
    listConfigurableCatalogSubsets: mocks.listSubsets,
    listConfigurableCatalogLinkTypes: mocks.listLinkTypes,
    createConfigurableCatalogTable: mocks.createTable,
    createConfigurableCatalogAttribute: mocks.createAttribute,
    createConfigurableCatalogLayout: mocks.createLayout,
    createConfigurableCatalogSubset: mocks.createSubset,
    createConfigurableCatalogLinkType: mocks.createLinkType,
    reviseConfigurableCatalogTable: mocks.reviseTable,
    reviseConfigurableCatalogDatabase: mocks.reviseDatabase,
    reviseConfigurableCatalogProfile: mocks.reviseProfile,
    reviseConfigurableCatalogAttribute: mocks.reviseAttribute,
    reviseConfigurableCatalogLayout: mocks.reviseLayout,
    reviseConfigurableCatalogSubset: mocks.reviseSubset,
    reviseConfigurableCatalogLinkType: mocks.reviseLinkType,
    validateConfigurableCatalogPublication: mocks.validatePublication,
    getDatabaseDesignAccess: mocks.getDatabaseDesignAccess,
    getConfigurableCatalogAttributeRevision: mocks.getAttributeRevision,
    searchConfigurableCatalogRecords: mocks.searchRecords,
    deleteConfigurableCatalogDraft: mocks.deleteDraft,
  };
});

describe("ConfigurableCatalogAdmin", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    HTMLDialogElement.prototype.showModal = function showModal() {
      this.setAttribute("open", "");
    };
    HTMLDialogElement.prototype.close = function close() {
      this.removeAttribute("open");
    };
    mocks.listTables.mockResolvedValue({
      data: { items: [table] },
      etag: null,
    });
    mocks.listDatabases.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.listProfiles.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.listAttributes.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.listLayouts.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.listSubsets.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.listLinkTypes.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.getDatabaseDesignAccess.mockResolvedValue({
      data: { feature_grants: ["schema_configuration"] },
      etag: null,
    });
    mocks.searchRecords.mockResolvedValue({
      data: { items: [], total: 0, facets: [] },
      etag: null,
    });
    mocks.deleteDraft.mockResolvedValue({ data: undefined, etag: null });
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
    mocks.reviseTable.mockResolvedValue({ data: table, etag: null });
    mocks.validatePublication.mockResolvedValue({
      data: {
        aggregate_type: "catalog.configurable_table",
        aggregate_id: table.table_id,
        revision_id: table.current_revision.id,
        valid: true,
        errors: [],
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

    expect(
      await screen.findByRole("heading", { name: "Materials" }),
    ).toBeTruthy();
    await user.type(
      screen.getAllByRole("textbox", { name: "Description" })[1]!,
      "Supplier display value used in datasheets.",
    );
    await user.click(
      screen.getByRole("button", { name: "Add Attribute revision 1" }),
    );

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

    expect(
      await screen.findByRole("heading", { name: "Database design" }),
    ).toBeTruthy();
    expect(screen.getByLabelText("Database objects")).toBeTruthy();
    expect(
      (screen.getByLabelText("Current table") as HTMLSelectElement).value,
    ).toBe(table.table_id);
    await user.click(screen.getByRole("button", { name: "Link Types" }));
    await user.click(screen.getByRole("button", { name: "Add Link Type" }));
    await user.click(
      screen.getByRole("button", { name: "Save new Link Type" }),
    );

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

  it("edits and checks the selected Table revision while publication stays unavailable", async () => {
    const user = userEvent.setup();
    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    await screen.findByRole("heading", { name: "Database design" });
    await user.click(screen.getByRole("button", { name: "Tables" }));
    const check = screen.getByRole("button", { name: "Check" });
    const save = screen.getByRole("button", { name: "Save draft" });
    const publish = screen.getByRole("button", { name: "Publish — Not configured" });
    expect(check.className).toBe("ux-button");
    expect(save.className).toBe("ux-button");
    expect((publish as HTMLButtonElement).disabled).toBe(true);
    expect(publish.closest("footer")?.querySelectorAll(".ux-button.primary")).toHaveLength(1);
    const name = screen.getByRole("textbox", { name: "Display name" });
    await user.clear(name);
    await user.type(name, "Engineering materials");
    await user.click(save);
    await waitFor(() => expect(mocks.reviseTable).toHaveBeenCalledOnce());
    expect(mocks.reviseTable).toHaveBeenCalledWith(
      expect.anything(),
      table.table_id,
      table.current_revision,
      expect.objectContaining({
        content: expect.objectContaining({ name: "Engineering materials" }),
      }),
    );

    await user.click(check);
    await waitFor(() =>
      expect(mocks.validatePublication).toHaveBeenCalledOnce(),
    );
  });

  it("keeps the newest Table definitions when an older request resolves late", async () => {
    const user = userEvent.setup();
    let resolveFirstTable!: (value: {
      data: { items: ReturnType<typeof attributeFor>[] };
      etag: null;
    }) => void;
    const firstTableRequest = new Promise<{
      data: { items: ReturnType<typeof attributeFor>[] };
      etag: null;
    }>((resolve) => {
      resolveFirstTable = resolve;
    });
    const firstAttribute = attributeFor(table, "Material family", "31");
    const secondAttribute = attributeFor(secondTable, "Test method", "32");
    mocks.listTables.mockResolvedValue({
      data: { items: [table, secondTable] },
      etag: null,
    });
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
    await waitFor(() =>
      expect(mocks.listAttributes).toHaveBeenCalledWith(
        expect.anything(),
        table.table_id,
      ),
    );
    await user.selectOptions(tableSelector, secondTable.table_id);
    await user.click(screen.getByRole("button", { name: "Attributes" }));
    expect((await screen.findAllByText("Test method")).length).toBeGreaterThan(
      0,
    );

    await act(async () => {
      resolveFirstTable({ data: { items: [firstAttribute] }, etag: null });
      await firstTableRequest;
    });

    expect(screen.getAllByText("Test method").length).toBeGreaterThan(0);
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
    expect(
      (screen.getByRole("button", { name: "Add Table" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });

  it("queries Profiles from the exact selected Database instead of a first-item fallback", async () => {
    const user = userEvent.setup();
    mocks.listDatabases.mockResolvedValue({
      data: { items: [database, secondDatabase] },
      etag: null,
    });

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    const databaseSelector = await screen.findByLabelText("Current database");
    await waitFor(() =>
      expect(mocks.listProfiles).toHaveBeenCalledWith(
        expect.anything(),
        database.database_id,
      ),
    );
    await user.selectOptions(databaseSelector, secondDatabase.database_id);
    await waitFor(() =>
      expect(mocks.listProfiles).toHaveBeenCalledWith(
        expect.anything(),
        secondDatabase.database_id,
      ),
    );
  });

  it("opens the first authorized real Record in an adjacent read-only preview", async () => {
    const user = userEvent.setup();
    const originalManufacturer = attributeFor(table, "Manufacturer at capture", "51");
    const historicalRevision = originalManufacturer.current_revision;
    const manufacturer = {
      ...originalManufacturer,
      current_revision: {
        ...historicalRevision,
        id: "51000000-0000-4000-8000-000000000008",
        revision_no: 2,
        based_on_revision_id: historicalRevision.id,
        content: { ...historicalRevision.content, name: "Current Manufacturer" },
      },
    };
    const onNavigate = vi.fn();
    mocks.listAttributes.mockResolvedValue({
      data: { items: [manufacturer] },
      etag: null,
    });
    mocks.listLayouts.mockResolvedValue({
      data: {
        items: [
          {
            layout_id: "51000000-0000-4000-8000-000000000009",
            table_id: table.table_id,
            table_revision_id: table.current_revision.id,
            revision: table.current_revision,
            name: "Original datasheet",
            description: null,
            items: [
              {
                attribute_definition_id: manufacturer.attribute_definition_id,
                attribute_definition_revision_id: historicalRevision.id,
                section: "General",
                ordinal: 0,
              },
            ],
          },
        ],
      },
      etag: null,
    });
    mocks.getAttributeRevision.mockResolvedValue({ data: historicalRevision, etag: null });
    mocks.searchRecords.mockResolvedValue({
      data: {
        items: [
          {
            record_id: "50000000-0000-4000-8000-000000000001",
            table_id: table.table_id,
            current_revision: {
              ...table.current_revision,
              id: "50000000-0000-4000-8000-000000000002",
              aggregate_id: "50000000-0000-4000-8000-000000000001",
              content: {
                table_revision_id: table.current_revision.id,
                name: "DP780",
                external_key: null,
                description: null,
                folder_id: null,
                folder_revision_id: null,
                values: [
                  {
                    attribute_definition_id:
                      manufacturer.attribute_definition_id,
                    attribute_definition_revision_id:
                      historicalRevision.id,
                    data_type: "text",
                    value: "North Mill",
                  },
                ],
              },
            },
          },
        ],
        total_count: 1,
        offset: 0,
        limit: 1,
        facets: [],
      },
      etag: null,
    });

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
        onNavigate={onNavigate}
        productMode
      />,
    );

    await screen.findByRole("heading", { name: "Materials" });
    await user.click(screen.getByRole("button", { name: "Preview datasheet" }));
    expect(screen.getByLabelText("Adjacent datasheet preview")).toBeTruthy();
    expect(screen.getByText("DP780")).toBeTruthy();
    expect(screen.getByText("Manufacturer at capture")).toBeTruthy();
    expect(screen.getByText("North Mill")).toBeTruthy();
    expect(mocks.getAttributeRevision).toHaveBeenCalledWith(
      expect.anything(),
      manufacturer.attribute_definition_id,
      historicalRevision.id,
    );
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("duplicates an exact Table draft without Profile placement and can permanently delete an unused r1 draft", async () => {
    const user = userEvent.setup();
    mocks.createTable.mockResolvedValue({ data: table, etag: null });

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    await screen.findByRole("heading", { name: "Materials" });
    await user.click(screen.getByRole("button", { name: "Duplicate" }));
    expect(
      (screen.getByRole("textbox", { name: "Reference key" }) as HTMLInputElement)
        .value,
    ).toBe("materials_copy");
    await user.click(screen.getByRole("button", { name: "Save new Table" }));
    await waitFor(() => expect(mocks.createTable).toHaveBeenCalledOnce());
    expect(mocks.createTable).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({
        content: expect.objectContaining({ key: "materials_copy" }),
      }),
    );
    const duplicateInput = mocks.createTable.mock.calls[0]![1] as Record<
      string,
      unknown
    >;
    expect("profile_id" in duplicateInput).toBe(false);
    expect("profile_revision_id" in duplicateInput).toBe(false);

    await user.click(screen.getByRole("button", { name: "Delete draft" }));
    expect(screen.getByRole("heading", { name: "Delete unpublished draft?" })).toBeTruthy();
    await user.click(
      screen.getByRole("button", { name: "Delete draft permanently" }),
    );
    await waitFor(() => expect(mocks.deleteDraft).toHaveBeenCalledOnce());
    expect(mocks.deleteDraft).toHaveBeenCalledWith(
      expect.anything(),
      "table",
      table.table_id,
      table.current_revision,
    );
  });

  it("keeps the selection and explains a server-blocked draft deletion", async () => {
    const user = userEvent.setup();
    mocks.deleteDraft.mockRejectedValue(
      new Error(
        "Draft deletion is blocked because Records, Links, references or dependencies still use it.",
      ),
    );

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    await screen.findByRole("heading", { name: "Materials" });
    await user.click(screen.getByRole("button", { name: "Delete draft" }));
    await user.click(
      screen.getByRole("button", { name: "Delete draft permanently" }),
    );
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Records, Links, references or dependencies",
    );
    expect(screen.getByRole("heading", { name: "Materials" })).toBeTruthy();
    expect(mocks.listTables).toHaveBeenCalledTimes(1);
  });
});
