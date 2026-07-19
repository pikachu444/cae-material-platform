import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MaterialDatabaseExplorer } from "./material-database-explorer";

const tableId = "76000000-0000-4000-8000-000000000001";
const tableRevisionId = "76000000-0000-4000-8000-000000000002";
const recordId = "76000000-0000-4000-8000-000000000003";
const recordRevisionId = "76000000-0000-4000-8000-000000000004";
const testRecordId = "76000000-0000-4000-8000-000000000005";
const testRevisionId = "76000000-0000-4000-8000-000000000006";
const folderId = "76000000-0000-4000-8000-000000000007";
const folderRevisionId = "76000000-0000-4000-8000-000000000008";

function revision(id: string, aggregateId: string) {
  return {
    id,
    aggregate_id: aggregateId,
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:test:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-07-19T00:00:00Z",
    created_by: "76000000-0000-4000-8000-000000000010",
    change_reason: "fixture",
    organization_id: "76000000-0000-4000-8000-000000000011",
    project_id: "76000000-0000-4000-8000-000000000012",
    classification: "internal" as const,
    lifecycle_state: "draft" as const,
  };
}

const table = {
  table_id: tableId,
  current_revision: {
    ...revision(tableRevisionId, tableId),
    content: { key: "materials", name: "Engineering Materials", description: null },
  },
};

const folder = {
  folder_id: folderId,
  table_id: tableId,
  current_revision: {
    ...revision(folderRevisionId, folderId),
    content: {
      table_revision_id: tableRevisionId,
      name: "Metals",
      parent_folder_id: null,
      parent_folder_revision_id: null,
      sort_order: 10,
    },
  },
  content: {
    table_revision_id: tableRevisionId,
    name: "Metals",
    parent_folder_id: null,
    parent_folder_revision_id: null,
    sort_order: 10,
  },
};

const record = {
  record_id: recordId,
  table_id: tableId,
  current_revision: {
    ...revision(recordRevisionId, recordId),
    content: {
      table_revision_id: tableRevisionId,
      name: "DP780 Sheet Steel",
      external_key: "DP780",
      description: "Automotive dual-phase sheet steel",
      folder_id: folderId,
      folder_revision_id: folderRevisionId,
      values: [],
    },
  },
};

const rootEndpoint = {
  record_id: recordId,
  record_revision_id: recordRevisionId,
  revision_no: 1,
  table_id: tableId,
  name: "DP780 Sheet Steel",
  external_key: "DP780",
  domain_binding: null,
};

const testEndpoint = {
  record_id: testRecordId,
  record_revision_id: testRevisionId,
  revision_no: 1,
  table_id: tableId,
  name: "Room-temperature tensile test",
  external_key: "DP780-TENSILE-01",
  domain_binding: {
    binding_id: "76000000-0000-4000-8000-000000000020",
    record_id: testRecordId,
    record_revision_id: testRevisionId,
    kind: "test_data" as const,
    object_id: "76000000-0000-4000-8000-000000000021",
    revision_id: "76000000-0000-4000-8000-000000000022",
    workbench_path: "/datasets/test-json?document_id=76000000-0000-4000-8000-000000000021",
  },
};

const graph = {
  root: rootEndpoint,
  nodes: [rootEndpoint, testEndpoint],
  links: [{
    record_link_id: "76000000-0000-4000-8000-000000000030",
    current_revision: {
      ...revision("76000000-0000-4000-8000-000000000031", "76000000-0000-4000-8000-000000000030"),
      content: {
        link_type_id: "76000000-0000-4000-8000-000000000032",
        link_type_revision_id: "76000000-0000-4000-8000-000000000033",
        source_record_id: recordId,
        source_record_revision_id: recordRevisionId,
        target_record_id: testRecordId,
        target_record_revision_id: testRevisionId,
        active: true,
        note: null,
      },
    },
    link_type_revision: {
      ...revision("76000000-0000-4000-8000-000000000033", "76000000-0000-4000-8000-000000000032"),
      content: {
        key: "has_test_data",
        name: "Test evidence",
        source_table_id: tableId,
        source_table_revision_id: tableRevisionId,
        target_table_id: tableId,
        target_table_revision_id: tableRevisionId,
        forward_label: "has test evidence",
        reverse_label: "tests material",
        source_cardinality: "many" as const,
        target_cardinality: "many" as const,
        description: null,
      },
    },
    source: rootEndpoint,
    target: testEndpoint,
  }],
};

const mocks = vi.hoisted(() => ({
  tables: vi.fn(),
  children: vi.fn(),
  subsets: vi.fn(),
  graph: vi.fn(),
  search: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return {
    ...original,
    listCatalogExplorerTables: mocks.tables,
    listCatalogExplorerChildren: mocks.children,
    listConfigurableCatalogSubsets: mocks.subsets,
    getCatalogWorkflowGraph: mocks.graph,
    searchConfigurableCatalogRecords: mocks.search,
  };
});

describe("MaterialDatabaseExplorer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.tables.mockResolvedValue({ data: { items: [table] }, etag: null });
    mocks.children.mockImplementation((_config, _tableId, selectedFolderId) => Promise.resolve({
      data: selectedFolderId === null
        ? { table, folders: [folder], records: [] }
        : { table, folders: [], records: [record] },
      etag: null,
    }));
    mocks.subsets.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.graph.mockResolvedValue({ data: graph, etag: null });
    mocks.search.mockResolvedValue({ data: { items: [record], total_count: 1, offset: 0, limit: 100, facets: [] }, etag: null });
  });

  it("lazily expands Database, Profile, Table and nested Folder contents", async () => {
    const user = userEvent.setup();
    render(<MaterialDatabaseExplorer config={{ baseUrl: "/api/v1", accessToken: "session" }} onNavigate={() => undefined} onRetry={() => undefined} />);

    expect(screen.getByText("CAE Material Database")).toBeTruthy();
    expect(screen.getByText("Engineering Materials Profile")).toBeTruthy();
    await user.click(await screen.findByRole("button", { name: /Metals/ }));
    expect(await screen.findByRole("button", { name: /DP780 Sheet Steel/ })).toBeTruthy();
    expect(mocks.children).toHaveBeenCalledWith(expect.anything(), tableId, null);
    expect(mocks.children).toHaveBeenCalledWith(expect.anything(), tableId, folderId);
  });

  it("opens an exact record and renders its linked workflow hierarchy", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn();
    render(<MaterialDatabaseExplorer config={{ baseUrl: "/api/v1", accessToken: "session" }} onNavigate={navigate} onRetry={() => undefined} />);

    await user.click(await screen.findByRole("button", { name: /Metals/ }));
    await user.click(await screen.findByRole("button", { name: /DP780 Sheet Steel/ }));
    await waitFor(() => expect(mocks.graph).toHaveBeenCalledWith(expect.anything(), recordId, recordRevisionId, 8));
    expect(screen.getByRole("heading", { name: "From source material to CAE delivery" })).toBeTruthy();
    const linkedTest = screen.getAllByRole("button", { name: /Room-temperature tensile test/ });
    expect(linkedTest.length).toBeGreaterThan(0);
    expect(navigate).toHaveBeenCalledWith(`/database/records/${recordId}/revisions/${recordRevisionId}`);
  });
});
