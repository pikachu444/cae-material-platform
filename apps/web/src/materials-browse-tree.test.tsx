import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MaterialsBrowseTree } from "./materials-browse-tree";

const tableId = "81000000-0000-4000-8000-000000000010";
const tableRevisionId = "81000000-0000-4000-8000-000000000011";
const metalFolderId = "81000000-0000-4000-8000-000000000020";
const steelFolderId = "81000000-0000-4000-8000-000000000021";
const recordId = "81000000-0000-4000-8000-000000000030";
const recordRevisionId = "81000000-0000-4000-8000-000000000031";
const testTableId = "81000000-0000-4000-8000-000000000060";

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
    created_by: "81000000-0000-4000-8000-000000000001",
    change_reason: "fixture",
    organization_id: "81000000-0000-4000-8000-000000000002",
    project_id: "81000000-0000-4000-8000-000000000003",
    classification: "internal" as const,
    lifecycle_state: "draft" as const,
  };
}

const table = {
  table_id: tableId,
  current_revision: {
    ...metadata(tableRevisionId, tableId),
    content: { key: "demo_material_records", name: "Material Records", description: null, data_category: "technical_data" as const },
  },
};

const testTable = {
  table_id: testTableId,
  current_revision: {
    ...metadata("81000000-0000-4000-8000-000000000061", testTableId),
    content: { key: "test_data", name: "Test Data Records", description: null, data_category: "test_data" as const },
  },
};

function folder(folderId: string, name: string, parentFolderId: string | null) {
  return {
    folder_id: folderId,
    table_id: tableId,
    current_revision: metadata(`${folderId.slice(0, -1)}9`, folderId),
    content: {
      table_revision_id: tableRevisionId,
      name,
      description: null,
      parent_folder_id: parentFolderId,
      parent_folder_revision_id: parentFolderId ? `${parentFolderId.slice(0, -1)}9` : null,
    },
  };
}

function record(id: string, name: string, folderId: string | null) {
  return {
    record_id: id,
    table_id: tableId,
    current_revision: {
      ...metadata(id === recordId ? recordRevisionId : `${id.slice(0, -1)}9`, id),
      content: {
        table_revision_id: tableRevisionId,
        name,
        external_key: name,
        description: null,
        folder_id: folderId,
        folder_revision_id: folderId ? `${folderId.slice(0, -1)}9` : null,
        values: [],
      },
    },
  };
}

const metalFolder = folder(metalFolderId, "Metal", null);
const steelFolder = folder(steelFolderId, "Steel", metalFolderId);
const dp780Record = record(recordId, "DP780 Sheet", steelFolderId);
const simulationRecord = record("81000000-0000-0000-0000-000000000080", "DP780 tabulated model", null);
const tensileRecord = {
  ...record("81000000-0000-4000-8000-000000000070", "Room-temperature tensile test", null),
  table_id: testTableId,
};
const graph = {
  root: {
    record_id: recordId,
    record_revision_id: recordRevisionId,
    revision_no: 1,
    table_id: tableId,
    name: "DP780 Sheet",
    external_key: "DP780",
    data_category: "technical_data" as const,
    domain_binding: {
      binding_id: "81000000-0000-4000-8000-000000000040",
      record_id: recordId,
      record_revision_id: recordRevisionId,
      kind: "material" as const,
      object_id: "81000000-0000-4000-8000-000000000041",
      revision_id: "81000000-0000-4000-8000-000000000042",
      workbench_path: "/materials/81000000-0000-4000-8000-000000000041",
    },
  },
  nodes: [],
  links: [],
};

const mocks = vi.hoisted(() => ({
  tables: vi.fn(),
  children: vi.fn(),
  folders: vi.fn(),
  subsets: vi.fn(),
  search: vi.fn(),
  graph: vi.fn(),
  record: vi.fn(),
}));

vi.mock("./features/catalog", async (importOriginal) => {
  const original = await importOriginal<typeof import("./features/catalog")>();
  return {
    ...original,
    listCatalogExplorerTables: mocks.tables,
    listCatalogExplorerChildren: mocks.children,
    listConfigurableCatalogFolders: mocks.folders,
    listConfigurableCatalogSubsets: mocks.subsets,
    searchConfigurableCatalogRecords: mocks.search,
    getCatalogWorkflowGraph: mocks.graph,
    getConfigurableCatalogRecord: mocks.record,
  };
});

describe("MaterialsBrowseTree", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.tables.mockResolvedValue({ data: { items: [table, testTable] }, etag: null });
    mocks.children.mockImplementation((_config, _tableId: string, parentFolderId: string | null) => Promise.resolve({
      data: parentFolderId === null
        ? { table, folders: [metalFolder], records: [] }
        : parentFolderId === metalFolderId
          ? { table, folders: [steelFolder], records: [] }
          : { table, folders: [], records: [dp780Record] },
      etag: null,
    }));
    mocks.folders.mockResolvedValue({ data: { items: [metalFolder, steelFolder] }, etag: null });
    mocks.subsets.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.search.mockImplementation((_config, input: { data_category?: string | null; text?: string | null }) => Promise.resolve({
      data: {
        items: input.text === "DP780"
          ? input.data_category === "technical_data"
            ? [dp780Record]
            : input.data_category === "test_data"
              ? [tensileRecord]
              : input.data_category === "simulation_data"
                ? [simulationRecord]
                : []
          : input.data_category === "technical_data"
            ? [dp780Record]
            : input.data_category === "test_data"
              ? [tensileRecord]
              : input.data_category === "solver_cards"
                ? [simulationRecord]
              : [],
        total_count: input.text === "DP780"
            ? input.data_category === "technical_data"
            ? 2
            : input.data_category === "test_data"
              ? 3
              : input.data_category === "simulation_data"
                ? 1
                : 0
          : input.data_category === "technical_data" || input.data_category === "test_data" || input.data_category === "solver_cards" ? 1 : 0,
        offset: 0,
        limit: 100,
        facets: [],
      },
      etag: null,
    }));
    mocks.graph.mockResolvedValue({ data: graph, etag: null });
    mocks.record.mockResolvedValue({ data: dp780Record, etag: null });
  });

  it("uses the four user-facing categories, server-backed find, and exact data selection", async () => {
    const user = userEvent.setup();
    const selectRecord = vi.fn();
    const openRecord = vi.fn();
    const onResultsChange = vi.fn();
    render(<MaterialsBrowseTree config={{ baseUrl: "/api/v1", accessToken: "test" }} onResultsChange={onResultsChange} onSelectRecord={selectRecord} onOpenRecord={openRecord}/>);

    const tree = await screen.findByRole("tree", { name: "Database contents" });
    expect(within(tree).queryByRole("treeitem", { name: /Materials Database/ })).toBeNull();
    expect(within(tree).queryByRole("treeitem", { name: /Engineering Materials/ })).toBeNull();
    expect(within(tree).getByRole("treeitem", { name: /Technical Data/ })).toBeTruthy();
    expect(within(tree).getByRole("treeitem", { name: /Test Data/ })).toBeTruthy();
    expect(within(tree).getByRole("treeitem", { name: /Simulation Data/ })).toBeTruthy();
    expect(within(tree).getByRole("treeitem", { name: /Solver Cards/ })).toBeTruthy();
    expect(within(tree).getByRole("treeitem", { name: /DP780 Sheet/ })).toBeTruthy();
    expect(within(tree).queryByRole("treeitem", { name: /Material Records/ })).toBeNull();
    expect(screen.queryByText("Expand a category to browse its data.")).toBeNull();

    await user.click(within(tree).getByRole("treeitem", { name: /Test Data/ }));
    expect(await within(tree).findByRole("treeitem", { name: /Room-temperature tensile test/ })).toBeTruthy();
    expect(within(tree).getByRole("treeitem", { name: /DP780 Sheet/ })).toBeTruthy();
    expect(selectRecord).not.toHaveBeenCalled();

    expect(within(tree).queryByRole("treeitem", { name: /Catalog placement/ })).toBeNull();
    expect(within(tree).queryByRole("treeitem", { name: /Material Records/ })).toBeNull();
    expect(screen.queryByRole("combobox", { name: "Database" })).toBeNull();
    expect(screen.queryByRole("combobox", { name: "Profile" })).toBeNull();
    expect(screen.queryByRole("combobox", { name: "Browse table" })).toBeNull();

    const recordRow = within(tree).getByRole("treeitem", { name: /DP780 Sheet/ });
    await user.click(recordRow);
    await waitFor(() => expect(selectRecord).toHaveBeenCalledWith(dp780Record, graph));

    recordRow.focus();
    await user.keyboard("{ArrowUp}");
    await waitFor(() => expect(document.activeElement?.getAttribute("title")).toBe("Technical Data"));
    await user.dblClick(recordRow);
    expect(openRecord).toHaveBeenCalledWith(dp780Record);

    await user.clear(screen.getByRole("textbox", { name: "Find in tree" }));
    await user.type(screen.getByRole("textbox", { name: "Find in tree" }), "DP780");
    await user.click(screen.getByRole("button", { name: "Find" }));
    await waitFor(() => expect(mocks.search.mock.calls.filter(([, input]) => input.text === "DP780")).toHaveLength(4));
    const findInputs = mocks.search.mock.calls
      .map(([, input]) => input as { data_category?: string | null; table_id?: string | null; text?: string | null; published_only?: boolean })
      .filter((input) => input.text === "DP780");
    expect(findInputs.map((input) => input.data_category)).toEqual([
      "technical_data",
      "test_data",
      "simulation_data",
      "solver_cards",
    ]);
    for (const input of findInputs) {
      expect(input).toMatchObject({ table_id: null, text: "DP780", published_only: false });
      expect(input).toHaveProperty("data_category");
    }
    expect(await screen.findByText("6 data matches · 3 loaded")).toBeTruthy();
    expect(screen.getByRole("treeitem", { name: /DP780 Sheet/ })).toBeTruthy();
    expect(screen.getByRole("treeitem", { name: /DP780 tabulated model/ })).toBeTruthy();
    await waitFor(() => expect(onResultsChange).toHaveBeenLastCalledWith(expect.objectContaining({ query: "DP780", totalCount: 6 })));
    expect(onResultsChange.mock.calls.at(-1)?.[0].items.map(({ category }: { category: string }) => category)).toEqual([
      "technical_data",
      "test_data",
      "simulation_data",
    ]);

    // Choosing a category after a Find is an explicit return to browsing. The
    // category branch must load and render even when the active query had no
    // match there.
    await user.click(screen.getByRole("treeitem", { name: /Solver Cards/ }));
    expect(await screen.findByRole("treeitem", { name: /DP780 tabulated model/ })).toBeTruthy();
  });

  it("fails closed when one category-scoped Find request fails", async () => {
    const onResultsChange = vi.fn();
    const searchOnlyRecord = record("81000000-0000-0000-0000-000000000081", "Search-only result", null);
    mocks.search.mockImplementation((_config, input: { data_category?: string | null; text?: string | null }) => {
      if (input.text === "DP780" && input.data_category === "simulation_data") {
        return Promise.reject(new Error("simulation search unavailable"));
      }
      return Promise.resolve({
        data: {
          items: input.text === "DP780" ? [searchOnlyRecord] : [],
          total_count: input.text === "DP780" ? 1 : 0,
          offset: 0,
          limit: 100,
          facets: [],
        },
        etag: null,
      });
    });
    const user = userEvent.setup();
    render(<MaterialsBrowseTree config={{ baseUrl: "/api/v1", accessToken: "test" }} onResultsChange={onResultsChange} onSelectRecord={() => undefined} onOpenRecord={() => undefined}/>);

    const find = await screen.findByRole("textbox", { name: "Find in tree" });
    await user.type(find, "DP780");
    await user.click(screen.getByRole("button", { name: "Find" }));
    await waitFor(() => expect(mocks.search.mock.calls.filter(([, input]) => input.text === "DP780")).toHaveLength(4));
    expect(await screen.findByText("Search unavailable.")).toBeTruthy();
    expect(screen.queryByRole("treeitem", { name: /Search-only result/ })).toBeNull();
    expect(onResultsChange).toHaveBeenLastCalledWith({ category: null, query: "DP780", items: [], totalCount: 0 });
  });

  it("keeps a 10,000-Record branch below 150 mounted treeitems", async () => {
    const manyRecords = Array.from({ length: 10_000 }, (_, index) => record(
      `82000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
      `Material ${String(index).padStart(5, "0")}`,
      null,
    ));
    mocks.search.mockImplementation((_config, input: { data_category?: string | null }) => Promise.resolve({
      data: input.data_category === "technical_data"
        ? { items: manyRecords, total_count: manyRecords.length, offset: 0, limit: 100, facets: [] }
        : { items: [], total_count: 0, offset: 0, limit: 100, facets: [] },
      etag: null,
    }));

    render(<MaterialsBrowseTree config={{ baseUrl: "/api/v1", accessToken: "test" }} onSelectRecord={() => undefined} onOpenRecord={() => undefined}/>);

    expect(await screen.findByRole("treeitem", { name: /Material 00000/ })).toBeTruthy();
    const mounted = screen.getAllByRole("treeitem");
    expect(mounted.length).toBeLessThan(150);
    expect(screen.queryByRole("treeitem", { name: /Material 09999/ })).toBe(null);
  });

  it("searches data without exposing the internal folder structure", async () => {
    mocks.folders.mockResolvedValue({ data: { items: [folder("81000000-0000-4000-8000-000000000022", "Material Library", null)] }, etag: null });
    mocks.search.mockResolvedValue({ data: { items: [], total_count: 0, offset: 0, limit: 100, facets: [] }, etag: null });
    const user = userEvent.setup();
    render(<MaterialsBrowseTree config={{ baseUrl: "/api/v1", accessToken: "test" }} onSelectRecord={() => undefined} onOpenRecord={() => undefined}/>);

    const find = await screen.findByRole("textbox", { name: "Find in tree" });
    await user.type(find, "Material Library");
    await user.click(screen.getByRole("button", { name: "Find" }));
    expect(await screen.findByText("0 data matches")).toBeTruthy();
    expect(mocks.folders).not.toHaveBeenCalled();
  });

  it("uses user-facing copy for an empty saved subset description", async () => {
    mocks.subsets.mockResolvedValue({ data: { items: [{
      subset_id: "81000000-0000-4000-8000-000000000050",
      table_id: tableId,
      revision: metadata("81000000-0000-4000-8000-000000000051", "81000000-0000-4000-8000-000000000050"),
      name: "DP780 saved subset",
      description: null,
      filter_definition: null,
    }] }, etag: null });
    render(<MaterialsBrowseTree config={{ baseUrl: "/api/v1", accessToken: "test" }} subsetMode onSelectRecord={() => undefined} onOpenRecord={() => undefined}/>);

    expect(await screen.findByText("Reusable saved filter")).toBeTruthy();
    expect(screen.queryByText("Reusable governed filter")).toBeNull();
  });

  it("keeps a saved subset Find as one table-scoped request", async () => {
    mocks.subsets.mockResolvedValue({ data: { items: [{
      subset_id: "81000000-0000-0000-0000-000000000082",
      table_id: tableId,
      revision: metadata("81000000-0000-0000-0000-000000000083", "81000000-0000-0000-0000-000000000082"),
      name: "DP780 saved subset",
      description: "Saved filter",
      filter_definition: { text: "DP780" },
    }] }, etag: null });
    const user = userEvent.setup();
    render(<MaterialsBrowseTree config={{ baseUrl: "/api/v1", accessToken: "test" }} subsetMode onSelectRecord={() => undefined} onOpenRecord={() => undefined}/>);

    await user.click(await screen.findByRole("button", { name: /DP780 saved subset/ }));
    await waitFor(() => expect(mocks.search.mock.calls.filter(([, input]) => input.text === "DP780")).toHaveLength(1));
    const [, input] = mocks.search.mock.calls.find(([, candidate]) => candidate.text === "DP780")!;
    expect(input).toMatchObject({ table_id: tableId, text: "DP780", published_only: false });
    expect(input).not.toHaveProperty("data_category");
  });

  it("selects the exact Materials table when another table is listed first", async () => {
    const workflowTable = {
      ...table,
      table_id: "81000000-0000-4000-8000-000000000099",
      current_revision: {
        ...table.current_revision,
        aggregate_id: "81000000-0000-4000-8000-000000000099",
        content: { key: "workflow_runs", name: "Workflow runs", description: null },
      },
    };
    mocks.tables.mockResolvedValue({ data: { items: [workflowTable, table] }, etag: null });
    const availability = vi.fn();

    render(<MaterialsBrowseTree config={{ baseUrl: "/api/v1", accessToken: "test" }} onScopeAvailabilityChange={availability} onSelectRecord={() => undefined} onOpenRecord={() => undefined}/>);

    await waitFor(() => expect(mocks.children).toHaveBeenCalledWith(expect.anything(), tableId, null));
    expect(screen.queryByRole("combobox", { name: "Browse table" })).toBeNull();
    expect(mocks.children).not.toHaveBeenCalledWith(expect.anything(), workflowTable.table_id, null);
    expect(availability).toHaveBeenLastCalledWith("ready");
  });

  it("retries the same published Record revision after an exact graph failure", async () => {
    mocks.graph
      .mockRejectedValueOnce(new Error("workflow graph unavailable"))
      .mockResolvedValueOnce({ data: graph, etag: null });
    const selectRecord = vi.fn();
    const user = userEvent.setup();

    render(<MaterialsBrowseTree
      config={{ baseUrl: "/api/v1", accessToken: "test" }}
      publishedOnly
      onSelectRecord={selectRecord}
      onOpenRecord={() => undefined}
    />);

    const recordRow = await screen.findByRole("treeitem", { name: /DP780 Sheet/ });
    await user.click(recordRow);
    expect(await screen.findByRole("button", { name: "Retry exact Materials graph" })).toBeTruthy();
    expect(selectRecord).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Retry exact Materials graph" }));
    await waitFor(() => expect(selectRecord).toHaveBeenCalledWith(dp780Record, graph));
    expect(mocks.graph).toHaveBeenNthCalledWith(
      1,
      expect.anything(),
      recordId,
      recordRevisionId,
      5,
      true,
    );
    expect(mocks.graph).toHaveBeenNthCalledWith(
      2,
      expect.anything(),
      recordId,
      recordRevisionId,
      5,
      true,
    );
    expect(screen.queryByRole("button", { name: "Retry exact Materials graph" })).toBeNull();
  });

  it("reports an unavailable Materials scope when the exact table is absent", async () => {
    const workflowTable = {
      ...table,
      current_revision: {
        ...table.current_revision,
        content: { key: "workflow_runs", name: "Workflow runs", description: null },
      },
    };
    mocks.tables.mockResolvedValue({ data: { items: [workflowTable] }, etag: null });
    const availability = vi.fn();

    render(<MaterialsBrowseTree config={{ baseUrl: "/api/v1", accessToken: "test" }} onScopeAvailabilityChange={availability} onSelectRecord={() => undefined} onOpenRecord={() => undefined}/>);

    expect(await screen.findByText("Materials are not available in this workspace.")).toBeTruthy();
    expect(availability).toHaveBeenLastCalledWith("unavailable");
    expect(mocks.children).not.toHaveBeenCalled();
    expect(mocks.search).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({
      table_id: null,
      data_category: "technical_data",
    }));
  });

  it("restores an exact Record by expanding its governed ancestor path", async () => {
    const startedAt = performance.now();
    render(<MaterialsBrowseTree config={{ baseUrl: "/api/v1", accessToken: "test" }} requestedRecord={graph.root} onSelectRecord={() => undefined} onOpenRecord={() => undefined}/>);

    const restored = await screen.findAllByRole("treeitem", { name: /DP780 Sheet/ });
    expect(restored.some((row) => row.getAttribute("aria-selected") === "true")).toBe(true);
    expect(performance.now() - startedAt).toBeLessThan(1_000);
    expect(mocks.record).toHaveBeenCalledWith(expect.anything(), recordId);
    expect(mocks.folders).toHaveBeenCalledWith(expect.anything(), tableId);
  });
});
