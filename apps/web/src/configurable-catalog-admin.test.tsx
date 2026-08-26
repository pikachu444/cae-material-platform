import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

const configuration = {
  profile_id: "41000000-0000-4000-8000-000000000001",
  current_revision: {
    ...table.current_revision,
    id: "41000000-0000-4000-8000-000000000002",
    aggregate_id: "41000000-0000-4000-8000-000000000001",
    content: {
      database_id: database.database_id,
      database_revision_id: database.current_revision.id,
      key: "general",
      name: "General configuration",
      description: null,
    },
  },
};

function layoutFor(
  sourceTable: typeof table,
  name: string,
  layoutId: string,
  items: Array<{
    attribute_definition_id: string;
    attribute_definition_revision_id: string;
    section: string;
    ordinal: number;
  }>,
) {
  return {
    layout_id: layoutId,
    table_id: sourceTable.table_id,
    table_revision_id: sourceTable.current_revision.id,
    revision: {
      ...sourceTable.current_revision,
      id: `${layoutId.slice(0, -1)}2`,
      aggregate_id: layoutId,
    },
    name,
    description: null,
    items,
  };
}

const exactTableSearch = `?table_id=${table.table_id}`
  + `&table_revision_id=${table.current_revision.id}`
  + `&object_kind=tables`
  + `&object_id=${table.table_id}`
  + `&object_revision_id=${table.current_revision.id}`;

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
        locationSearch={exactTableSearch}
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
        locationSearch={exactTableSearch}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    expect(
      await screen.findByRole("region", { name: "Database design" }),
    ).toBeTruthy();
    expect(screen.getByLabelText("Database objects")).toBeTruthy();
    expect(
      (screen.getByLabelText("Record type") as HTMLSelectElement).value,
    ).toBe(table.table_id);
    await user.click(screen.getByRole("button", { name: "Link Types" }));
    await user.click(screen.getByRole("button", { name: "Create Link Type" }));
    await user.selectOptions(screen.getByLabelText("From table"), table.table_id);
    await user.selectOptions(screen.getByLabelText("To table"), table.table_id);
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
        locationSearch={exactTableSearch}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    await screen.findByRole("region", { name: "Database design" });
    await user.click(screen.getByRole("button", { name: "Record type" }));
    const check = screen.getByRole("button", { name: "Validate draft" });
    const save = screen.getByRole("button", { name: "Save new Record type revision" });
    expect(check.className).toBe("ux-button");
    expect(save.className).toBe("ux-button primary");
    expect(screen.queryByRole("button", { name: "Publish — Not configured" })).toBeNull();
    expect(save.closest("footer")?.querySelectorAll(".ux-button.primary")).toHaveLength(1);
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
        locationSearch={exactTableSearch}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    const tableSelector = await screen.findByLabelText("Record type");
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

  it("keeps the empty Record type scope actionable without requiring a Configuration", async () => {
    const user = userEvent.setup();
    mocks.listTables.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.createTable.mockResolvedValue({ data: table, etag: null });

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        locationSearch={exactTableSearch}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    expect(await screen.findByText("No record types are available for this selection.")).toBeTruthy();
    expect((screen.getByLabelText("Database") as HTMLSelectElement).selectedOptions[0]?.textContent).toBe("No database selected");
    expect(screen.queryByLabelText("Configuration")).toBeNull();
    expect((screen.getByLabelText("Record type") as HTMLSelectElement).value).toBe("");
    await waitFor(() => expect(
      (screen.getByRole("button", { name: "Create Record type" }) as HTMLButtonElement).disabled,
    ).toBe(false));
    await user.click(screen.getByRole("button", { name: "Create Record type" }));
    await user.click(screen.getByRole("button", { name: "Save new Record type" }));
    await waitFor(() => expect(mocks.createTable).toHaveBeenCalledOnce());
    const createInput = mocks.createTable.mock.calls[0]![1] as Record<string, unknown>;
    expect("profile_id" in createInput).toBe(false);
    expect("profile_revision_id" in createInput).toBe(false);
  });

  it("queries Configurations from the exact selected Database instead of a first-item fallback", async () => {
    const user = userEvent.setup();
    mocks.listDatabases.mockResolvedValue({
      data: { items: [database, secondDatabase] },
      etag: null,
    });

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        locationSearch={`?database_id=${database.database_id}&database_revision_id=${database.current_revision.id}&object_kind=databases&object_id=${database.database_id}&object_revision_id=${database.current_revision.id}`}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    const databaseSelector = await screen.findByLabelText("Database");
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

  it.each([
    {
      label: "Database",
      locationSearch: `?database_id=${database.database_id}&object_kind=databases&object_id=${database.database_id}&object_revision_id=${database.current_revision.id}`,
      expected: "Choose the exact Database revision before using this link.",
    },
    {
      label: "Configuration",
      locationSearch: `?database_id=${database.database_id}&database_revision_id=${database.current_revision.id}&profile_id=${configuration.profile_id}&object_kind=profiles&object_id=${configuration.profile_id}&object_revision_id=${configuration.current_revision.id}`,
      expected: "Choose the exact Configuration revision before using this link.",
    },
  ])("rejects a $label identity link that omits its exact revision", async ({ locationSearch, expected }) => {
    mocks.listDatabases.mockResolvedValue({ data: { items: [database] }, etag: null });
    mocks.listProfiles.mockResolvedValue({ data: { items: [configuration] }, etag: null });

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        locationSearch={locationSearch}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    expect(await screen.findByText(expected)).toBeTruthy();
  });

  it("auto-selects one Configuration without blocking the Record type flow", async () => {
    mocks.listDatabases.mockResolvedValue({ data: { items: [database] }, etag: null });
    mocks.listProfiles.mockResolvedValue({ data: { items: [configuration] }, etag: null });

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        locationSearch={`?database_id=${database.database_id}&database_revision_id=${database.current_revision.id}&table_id=${table.table_id}&table_revision_id=${table.current_revision.id}&object_kind=tables&object_id=${table.table_id}&object_revision_id=${table.current_revision.id}`}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    const configurationSelector = await screen.findByLabelText("Configuration") as HTMLSelectElement;
    await waitFor(() => expect(configurationSelector.value).toBe(configuration.profile_id));
    expect(configurationSelector.disabled).toBe(true);
    expect((screen.getByLabelText("Record type") as HTMLSelectElement).value).toBe(table.table_id);
  });

  it("rejects a Record type identity link that omits its exact revision", async () => {
    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        locationSearch={`?table_id=${table.table_id}&object_kind=tables&object_id=${table.table_id}`}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    expect(
      await screen.findByText("Choose the exact Record type revision before using this link."),
    ).toBeTruthy();
    expect(mocks.listAttributes).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Save new Record type revision" })).toBeNull();
  });

  it("rejects a definition object identity link that omits its exact revision", async () => {
    const selectedLayout = layoutFor(
      table,
      "Material overview",
      "51000000-0000-4000-8000-000000000009",
      [],
    );
    mocks.listLayouts.mockResolvedValue({ data: { items: [selectedLayout] }, etag: null });

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        locationSearch={`?table_id=${table.table_id}&table_revision_id=${table.current_revision.id}&object_kind=layouts&object_id=${selectedLayout.layout_id}`}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    expect(
      await screen.findByText("Choose the exact definition object revision before using this link."),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Preview" })).toBeNull();
  });

  it("opens a reviewed datasheet editor without mutation and saves exact field versions in the chosen order", async () => {
    const user = userEvent.setup();
    const manufacturer = attributeFor(table, "Manufacturer", "61");
    const grade = attributeFor(table, "Grade", "62");
    const savedLayout = layoutFor(
      table,
      "Production datasheet",
      "63000000-0000-4000-8000-000000000001",
      [
        {
          attribute_definition_id: grade.attribute_definition_id,
          attribute_definition_revision_id: grade.current_revision.id,
          section: "General",
          ordinal: 0,
        },
        {
          attribute_definition_id: manufacturer.attribute_definition_id,
          attribute_definition_revision_id: manufacturer.current_revision.id,
          section: "General",
          ordinal: 1,
        },
      ],
    );
    const onNavigate = vi.fn();
    mocks.listAttributes.mockResolvedValue({
      data: { items: [manufacturer, grade] },
      etag: null,
    });
    mocks.listLayouts
      .mockResolvedValueOnce({ data: { items: [] }, etag: null })
      .mockResolvedValue({ data: { items: [savedLayout] }, etag: null });
    mocks.createLayout.mockResolvedValue({ data: savedLayout, etag: null });
    mocks.searchRecords.mockResolvedValue({
      data: {
        items: [{
          record_id: "63000000-0000-4000-8000-000000000010",
          table_id: table.table_id,
          current_revision: {
            ...table.current_revision,
            id: "63000000-0000-4000-8000-000000000011",
            aggregate_id: "63000000-0000-4000-8000-000000000010",
            revision_no: 2,
            content: {
              table_revision_id: table.current_revision.id,
              name: "DP780",
              external_key: null,
              description: null,
              folder_id: "63000000-0000-4000-8000-000000000020",
              folder_revision_id: "63000000-0000-4000-8000-000000000021",
              values: [
                {
                  attribute_definition_id: manufacturer.attribute_definition_id,
                  attribute_definition_revision_id: manufacturer.current_revision.id,
                  data_type: "text",
                  value: "North Mill",
                },
                {
                  attribute_definition_id: grade.attribute_definition_id,
                  attribute_definition_revision_id: grade.current_revision.id,
                  data_type: "text",
                  value: "DP780",
                },
              ],
            },
          },
        }],
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
        locationSearch={`?table_id=${table.table_id}&table_revision_id=${table.current_revision.id}&object_kind=layouts`}
        onOpenConnection={() => undefined}
        onNavigate={onNavigate}
        productMode
      />,
    );

    const newLayoutAction = await screen.findByRole("button", { name: "New layout" });
    expect(newLayoutAction.className).toContain("local-action");
    await user.click(newLayoutAction);
    expect(mocks.createLayout).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "New layout" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Datasheet fields" })).toBeTruthy();
    await user.type(screen.getByRole("textbox", { name: "Layout name" }), "Production datasheet");
    await user.type(screen.getByRole("textbox", { name: "Description (optional)" }), "Current local order");
    const gradeHandle = screen.getByRole("button", { name: "Reorder Grade, position 2 of 2" });
    fireEvent.keyDown(gradeHandle, { key: "ArrowUp", altKey: true });
    expect(screen.getByRole("button", { name: "Reorder Grade, position 1 of 2" })).toBeTruthy();
    expect(screen.getByText("Moved Grade to position 1 of 2.")).toBeTruthy();

    const previewAction = screen.getByRole("button", { name: "Preview" });
    expect(previewAction.className).toContain("local-action");
    await user.click(previewAction);
    expect(mocks.createLayout).not.toHaveBeenCalled();
    const preview = screen.getByLabelText("Datasheet preview");
    expect(within(preview).getByRole("heading", { name: "Production datasheet" })).toBeTruthy();
    expect(within(preview).queryByText("Current local order")).toBeNull();
    await user.selectOptions(
      within(preview).getByRole("combobox", { name: "Preview with" }),
      "63000000-0000-4000-8000-000000000010",
    );
    expect(within(preview).getByRole("option", { name: "DP780 (Draft, revision 2)" })).toBeTruthy();
    expect(within(preview).getByRole("heading", { name: "General" })).toBeTruthy();
    expect(within(preview).queryByText(/Record: Revision 2/)).toBeNull();
    expect(within(preview).queryByText(/Status: Draft/)).toBeNull();
    expect(
      [...preview.querySelectorAll("dt")].map((item) => item.textContent),
    ).toEqual(["Grade", "Manufacturer"]);
    await user.click(within(preview).getByRole("button", { name: "Open in Records" }));
    const recordsUrl = new URL(
      onNavigate.mock.calls.at(-1)?.[0] ?? "",
      "https://example.invalid",
    );
    expect(recordsUrl.pathname).toBe("/administration/records");
    expect(recordsUrl.searchParams.get("folder_id")).toBe(
      "63000000-0000-4000-8000-000000000020",
    );
    expect(recordsUrl.searchParams.get("folder_revision_id")).toBe(
      "63000000-0000-4000-8000-000000000021",
    );
    await user.click(within(preview).getByRole("button", { name: "Back to layout" }));
    expect(mocks.createLayout).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(mocks.createLayout).toHaveBeenCalledOnce());
    expect(mocks.createLayout).toHaveBeenCalledWith(
      expect.anything(),
      table.table_id,
      expect.objectContaining({
        table_revision_id: table.current_revision.id,
        name: "Production datasheet",
        items: [
          expect.objectContaining({
            attribute_definition_id: grade.attribute_definition_id,
            attribute_definition_revision_id: grade.current_revision.id,
            ordinal: 0,
          }),
          expect.objectContaining({
            attribute_definition_id: manufacturer.attribute_definition_id,
            attribute_definition_revision_id: manufacturer.current_revision.id,
            ordinal: 1,
          }),
        ],
      }),
    );
    await waitFor(() => expect(onNavigate).toHaveBeenLastCalledWith(
      expect.stringContaining(`object_id=${savedLayout.layout_id}&object_revision_id=${savedLayout.revision.id}`),
    ));
    expect(screen.getByRole("heading", { name: "Production datasheet" })).toBeTruthy();
    expect(screen.queryByText(/Status: Draft/)).toBeNull();
    expect(screen.getByText("Version 1")).toBeTruthy();
  });

  it("prefills a Layout copy without mutation and preserves the local form after an API failure", async () => {
    const user = userEvent.setup();
    const manufacturer = attributeFor(table, "Manufacturer", "64");
    const sourceLayout = layoutFor(
      table,
      "Material overview",
      "65000000-0000-4000-8000-000000000001",
      [{
        attribute_definition_id: manufacturer.attribute_definition_id,
        attribute_definition_revision_id: manufacturer.current_revision.id,
        section: "General",
        ordinal: 0,
      }],
    );
    mocks.listAttributes.mockResolvedValue({ data: { items: [manufacturer] }, etag: null });
    mocks.listLayouts.mockResolvedValue({ data: { items: [sourceLayout] }, etag: null });
    mocks.createLayout.mockRejectedValue(new Error("stale exact Record type version"));

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        locationSearch={`?table_id=${table.table_id}&table_revision_id=${table.current_revision.id}&object_kind=layouts&object_id=${sourceLayout.layout_id}&object_revision_id=${sourceLayout.revision.id}`}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    await screen.findByRole("heading", { name: "Material overview" });
    const moreAction = screen.getByLabelText("More actions for Material overview");
    expect(moreAction.className).toContain("local-action");
    await user.click(moreAction);
    await user.click(screen.getByRole("button", { name: "Duplicate layout" }));
    expect(mocks.createLayout).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "Duplicate layout" })).toBeTruthy();
    expect((screen.getByRole("textbox", { name: "Layout name" }) as HTMLInputElement).value).toBe("Material overview copy");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect((await screen.findByRole("alert")).textContent).toContain("stale exact Record type version");
    expect((screen.getByRole("textbox", { name: "Layout name" }) as HTMLInputElement).value).toBe("Material overview copy");
    expect(mocks.createLayout).toHaveBeenCalledWith(
      expect.anything(),
      table.table_id,
      expect.objectContaining({
        items: [expect.objectContaining({
          attribute_definition_id: manufacturer.attribute_definition_id,
          attribute_definition_revision_id: manufacturer.current_revision.id,
        })],
      }),
    );
  });

  it("offers contextual Retry only after a real definition load failure", async () => {
    const user = userEvent.setup();
    mocks.listLayouts
      .mockRejectedValueOnce(new Error("layout list unavailable"))
      .mockResolvedValue({ data: { items: [] }, etag: null });

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        locationSearch={`?table_id=${table.table_id}&table_revision_id=${table.current_revision.id}&object_kind=layouts`}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    expect((await screen.findByRole("alert")).textContent).toContain("layout list unavailable");
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(mocks.listLayouts).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  });

  it("shows a permission denial without opening or mutating a Layout form", async () => {
    const user = userEvent.setup();
    mocks.getDatabaseDesignAccess.mockResolvedValue({
      data: { feature_grants: [] },
      etag: null,
    });

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        locationSearch={`?table_id=${table.table_id}&table_revision_id=${table.current_revision.id}&object_kind=layouts`}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    await user.click(await screen.findByRole("button", { name: "New layout" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "schema configuration permission",
    );
    expect(screen.queryByRole("heading", { name: "New layout" })).toBeNull();
    expect(mocks.createLayout).not.toHaveBeenCalled();
  });

  it("opens an explicitly selected real Record in an adjacent read-only preview", async () => {
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
        locationSearch={`?table_id=${table.table_id}&table_revision_id=${table.current_revision.id}&object_kind=layouts&object_id=51000000-0000-4000-8000-000000000009&object_revision_id=${table.current_revision.id}&record_id=50000000-0000-4000-8000-000000000001&record_revision_id=50000000-0000-4000-8000-000000000002`}
        onOpenConnection={() => undefined}
        onNavigate={onNavigate}
        productMode
      />,
    );

    const preview = await screen.findByLabelText("Datasheet preview");
    expect(
      await within(preview).findByRole("heading", { name: "Original datasheet" }),
    ).toBeTruthy();
    expect(await screen.findByRole("option", { name: /DP780 \(Draft, revision 1\)/ })).toBeTruthy();
    expect(await screen.findByText("Manufacturer at capture")).toBeTruthy();
    expect(await screen.findByText("North Mill")).toBeTruthy();
    expect(mocks.getAttributeRevision).toHaveBeenCalledWith(
      expect.anything(),
      manufacturer.attribute_definition_id,
      historicalRevision.id,
    );
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("duplicates an exact Record type draft without Configuration placement and deletes only an unused Revision 1 draft", async () => {
    const user = userEvent.setup();
    mocks.createTable.mockResolvedValue({ data: table, etag: null });

    render(
      <ConfigurableCatalogAdmin
        config={{ baseUrl: "/api/v1", accessToken: "administrator-token" }}
        locationSearch={exactTableSearch}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    await screen.findByRole("heading", { name: "Materials" });
    await user.click(screen.getByRole("button", { name: "Duplicate as new draft" }));
    expect(
      (screen.getByRole("textbox", { name: "Reference key" }) as HTMLInputElement)
        .value,
    ).toBe("materials_copy");
    await user.click(screen.getByRole("button", { name: "Save new Record type" }));
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

    await user.click(screen.getByRole("button", { name: "Delete unused draft" }));
    expect(screen.getByRole("heading", { name: "Delete unused draft?" })).toBeTruthy();
    await user.click(
      screen.getByRole("button", { name: "Delete unused draft permanently" }),
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
        locationSearch={exactTableSearch}
        onOpenConnection={() => undefined}
        productMode
      />,
    );

    await screen.findByRole("heading", { name: "Materials" });
    await user.click(screen.getByRole("button", { name: "Delete unused draft" }));
    await user.click(
      screen.getByRole("button", { name: "Delete unused draft permanently" }),
    );
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Records, Links, references or dependencies",
    );
    expect(screen.getByRole("heading", { name: "Materials" })).toBeTruthy();
    expect(mocks.listTables).toHaveBeenCalledTimes(1);
  });
});
