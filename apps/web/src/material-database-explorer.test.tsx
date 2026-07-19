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
const attributeId = "76000000-0000-4000-8000-000000000009";
const attributeRevisionId = "76000000-0000-4000-8000-00000000000a";
const layoutId = "76000000-0000-4000-8000-00000000000b";
const secondRecordId = "76000000-0000-4000-8000-00000000000d";
const secondRecordRevisionId = "76000000-0000-4000-8000-00000000000e";

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

const attribute = {
  attribute_definition_id: attributeId,
  table_id: tableId,
  current_revision: {
    ...revision(attributeRevisionId, attributeId),
    content: {
      table_revision_id: tableRevisionId,
      key: "material_code",
      name: "Material code",
      data_type: "text" as const,
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
};

const layout = {
  layout_id: layoutId,
  table_id: tableId,
  revision: revision("76000000-0000-4000-8000-00000000000c", layoutId),
  name: "Engineering datasheet",
  description: null,
  items: [{
    attribute_definition_id: attributeId,
    attribute_definition_revision_id: attributeRevisionId,
    section: "Identity",
    ordinal: 0,
  }],
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
      values: [{
        attribute_definition_id: attributeId,
        attribute_definition_revision_id: attributeRevisionId,
        data_type: "text" as const,
        value: "DP780",
      }],
    },
  },
};

const secondRecord = {
  ...record,
  record_id: secondRecordId,
  current_revision: {
    ...record.current_revision,
    id: secondRecordRevisionId,
    aggregate_id: secondRecordId,
    content: {
      ...record.current_revision.content,
      name: "DP600 Sheet Steel",
      external_key: "DP600",
      values: [{
        attribute_definition_id: attributeId,
        attribute_definition_revision_id: attributeRevisionId,
        data_type: "text" as const,
        value: "DP600",
      }],
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
  attributes: vi.fn(),
  layouts: vi.fn(),
  revisions: vi.fn(),
  compare: vi.fn(),
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
    listConfigurableCatalogAttributes: mocks.attributes,
    listConfigurableCatalogLayouts: mocks.layouts,
    listConfigurableCatalogRecordRevisions: mocks.revisions,
    compareConfigurableCatalogRecordRevisions: mocks.compare,
  };
});

describe("MaterialDatabaseExplorer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.sessionStorage.clear();
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
    mocks.attributes.mockResolvedValue({ data: { items: [attribute] }, etag: null });
    mocks.layouts.mockResolvedValue({ data: { items: [layout] }, etag: null });
    mocks.revisions.mockResolvedValue({ data: { items: [record.current_revision] }, etag: null });
    mocks.compare.mockResolvedValue({ data: null, etag: null });
  });

  it("opens Database, Profile, Table and a useful nested demo record on first entry", async () => {
    const user = userEvent.setup();
    render(<MaterialDatabaseExplorer config={{ baseUrl: "/api/v1", accessToken: "session" }} onNavigate={() => undefined} onRetry={() => undefined} />);

    expect(screen.getByText("CAE Material Database")).toBeTruthy();
    expect(screen.getByText("Engineering Materials Profile")).toBeTruthy();
    expect(await screen.findByRole("button", { name: /DP780 Sheet Steel/ })).toBeTruthy();
    expect(await screen.findByRole("heading", { name: "Record information" })).toBeTruthy();
    expect(mocks.children).toHaveBeenCalledWith(expect.anything(), tableId, null);
    expect(mocks.children).toHaveBeenCalledWith(expect.anything(), tableId, folderId);
    const metals = screen.getByRole("button", { name: /Metals/ });
    metals.focus();
    await user.keyboard("{ArrowLeft}");
    expect(screen.queryByRole("button", { name: /DP780 Sheet Steel/ })).toBeNull();
    await user.keyboard("{ArrowRight}");
    expect(await screen.findByRole("button", { name: /DP780 Sheet Steel/ })).toBeTruthy();
  });

  it("opens an exact record and renders its linked workflow hierarchy", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn();
    render(<MaterialDatabaseExplorer config={{ baseUrl: "/api/v1", accessToken: "session" }} onNavigate={navigate} onRetry={() => undefined} />);

    await screen.findByRole("heading", { name: "Record information" });
    await waitFor(() => expect(mocks.graph).toHaveBeenCalledWith(expect.anything(), recordId, recordRevisionId, 8));
    await user.click(screen.getByRole("button", { name: "Workflow" }));
    const linkedTest = screen.getAllByRole("button", { name: /Room-temperature tensile test/ });
    expect(linkedTest.length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "Catalog" }));
    await user.click(screen.getByRole("button", { name: /DP780 Sheet Steel/ }));
    expect(navigate).toHaveBeenCalledWith(`/database/records/${recordId}/revisions/${recordRevisionId}`);
    expect(screen.getByText("Engineering datasheet")).toBeTruthy();
    expect(screen.getByText("Material code")).toBeTruthy();
    expect(screen.getAllByText("DP780").length).toBeGreaterThan(0);
  });

  it("searches and compares multiple records with the configured Layout", async () => {
    const user = userEvent.setup();
    mocks.search.mockResolvedValue({ data: { items: [record, secondRecord], total_count: 2, offset: 0, limit: 100, facets: [] }, etag: null });
    render(<MaterialDatabaseExplorer config={{ baseUrl: "/api/v1", accessToken: "session" }} onNavigate={() => undefined} onRetry={() => undefined} />);

    await user.type(screen.getByLabelText("Search database"), "DP");
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByRole("heading", { name: "2 matching records" })).toBeTruthy();
    await user.click(screen.getByLabelText("Compare DP780 Sheet Steel"));
    await user.click(screen.getByLabelText("Compare DP600 Sheet Steel"));
    await user.click(screen.getByRole("button", { name: "Compare 2" }));

    expect(screen.getByRole("heading", { name: "Engineering datasheet" })).toBeTruthy();
    expect(screen.getByText("DP600 Sheet Steel")).toBeTruthy();
    expect(screen.getAllByText("DP780 Sheet Steel").length).toBeGreaterThan(0);
  });
});
