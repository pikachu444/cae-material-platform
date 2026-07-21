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
    content: { key: "materials", name: "Material Records", description: null },
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
const graph = {
  root: {
    record_id: recordId,
    record_revision_id: recordRevisionId,
    revision_no: 1,
    table_id: tableId,
    name: "DP780 Sheet",
    external_key: "DP780",
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

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
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
    mocks.tables.mockResolvedValue({ data: { items: [table] }, etag: null });
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
    mocks.search.mockResolvedValue({ data: { items: [dp780Record], total_count: 1, offset: 0, limit: 100, facets: [] }, etag: null });
    mocks.graph.mockResolvedValue({ data: graph, etag: null });
    mocks.record.mockResolvedValue({ data: dp780Record, etag: null });
  });

  it("uses the governed hierarchy, server-backed find, and exact Record selection", async () => {
    const user = userEvent.setup();
    const selectRecord = vi.fn();
    const openRecord = vi.fn();
    render(<MaterialsBrowseTree config={{ baseUrl: "/api/v1", accessToken: "test" }} onSelectRecord={selectRecord} onOpenRecord={openRecord}/>);

    const tree = await screen.findByRole("tree", { name: "Database contents" });
    expect(within(tree).getByRole("treeitem", { name: /Materials Database/ })).toBeTruthy();
    expect(within(tree).getByRole("treeitem", { name: /Engineering Materials/ })).toBeTruthy();
    expect(within(tree).getByRole("treeitem", { name: /Material Records/ })).toBeTruthy();
    expect(within(tree).getByRole("treeitem", { name: /Metal/ })).toBeTruthy();

    await user.click(screen.getByRole("treeitem", { name: /Metal/ }));
    await user.click(await screen.findByRole("treeitem", { name: /Steel/ }));
    const recordRow = await screen.findByRole("treeitem", { name: /DP780 Sheet/ });
    await user.click(recordRow);
    await waitFor(() => expect(selectRecord).toHaveBeenCalledWith(dp780Record, graph));

    recordRow.focus();
    await user.keyboard("{ArrowUp}");
    await waitFor(() => expect(document.activeElement?.getAttribute("title")).toBe("Steel"));
    await user.dblClick(screen.getByRole("treeitem", { name: /DP780 Sheet/ }));
    expect(openRecord).toHaveBeenCalledWith(dp780Record);

    await user.clear(screen.getByRole("textbox", { name: "Find in tree" }));
    await user.type(screen.getByRole("textbox", { name: "Find in tree" }), "DP780");
    await user.click(screen.getByRole("button", { name: "Find" }));
    await waitFor(() => expect(mocks.search).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ table_id: tableId, text: "DP780", limit: 100 })));
    expect(await screen.findByText("1 record matches")).toBeTruthy();
    expect(screen.getByRole("treeitem", { name: /Metal/ })).toBeTruthy();
    expect(screen.getByRole("treeitem", { name: /Steel/ })).toBeTruthy();
    expect(screen.getByRole("treeitem", { name: /DP780 Sheet/ })).toBeTruthy();
  });

  it("keeps a 10,000-Record branch below 150 mounted treeitems", async () => {
    const manyRecords = Array.from({ length: 10_000 }, (_, index) => record(
      `82000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
      `Material ${String(index).padStart(5, "0")}`,
      null,
    ));
    mocks.children.mockResolvedValue({ data: { table, folders: [], records: manyRecords }, etag: null });

    render(<MaterialsBrowseTree config={{ baseUrl: "/api/v1", accessToken: "test" }} onSelectRecord={() => undefined} onOpenRecord={() => undefined}/>);

    expect(await screen.findByRole("treeitem", { name: /Material 00000/ })).toBeTruthy();
    const mounted = screen.getAllByRole("treeitem");
    expect(mounted.length).toBeLessThan(150);
    expect(screen.queryByRole("treeitem", { name: /Material 09999/ })).toBe(null);
  });

  it("restores an exact Record by expanding its governed ancestor path", async () => {
    const startedAt = performance.now();
    render(<MaterialsBrowseTree config={{ baseUrl: "/api/v1", accessToken: "test" }} requestedRecord={graph.root} onSelectRecord={() => undefined} onOpenRecord={() => undefined}/>);

    const restored = await screen.findByRole("treeitem", { name: /DP780 Sheet/ });
    expect(restored.getAttribute("aria-selected")).toBe("true");
    expect(performance.now() - startedAt).toBeLessThan(1_000);
    expect(mocks.record).toHaveBeenCalledWith(expect.anything(), recordId);
    expect(mocks.folders).toHaveBeenCalledWith(expect.anything(), tableId);
  });
});
