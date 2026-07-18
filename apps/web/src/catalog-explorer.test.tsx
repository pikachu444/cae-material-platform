import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CatalogExplorer } from "./catalog-explorer";

const orgId = "51000000-0000-4000-8000-000000000001";
const projectId = "51000000-0000-4000-8000-000000000002";
const actorId = "51000000-0000-4000-8000-000000000003";
const materialTableId = "51000000-0000-4000-8000-000000000010";
const testTableId = "51000000-0000-4000-8000-000000000020";
const materialTableRevisionId = "51000000-0000-4000-8000-000000000011";
const testTableRevisionId = "51000000-0000-4000-8000-000000000021";
const materialRecordId = "51000000-0000-4000-8000-000000000030";
const materialRecordRevisionId = "51000000-0000-4000-8000-000000000031";
const testRecordId = "51000000-0000-4000-8000-000000000040";
const testRecordRevisionId = "51000000-0000-4000-8000-000000000041";

function metadata(id: string, aggregateId: string) {
  return {
    id,
    aggregate_id: aggregateId,
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:catalog:fixture:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-07-18T09:00:00Z",
    created_by: actorId,
    change_reason: "fixture",
    organization_id: orgId,
    project_id: projectId,
    classification: "internal" as const,
    lifecycle_state: "draft" as const,
  };
}

const materialTable = {
  table_id: materialTableId,
  current_revision: {
    ...metadata(materialTableRevisionId, materialTableId),
    content: { key: "materials", name: "Engineering Materials", description: null },
  },
};

const testTable = {
  table_id: testTableId,
  current_revision: {
    ...metadata(testTableRevisionId, testTableId),
    content: { key: "tests", name: "Test Records", description: null },
  },
};

const materialRecord = {
  record_id: materialRecordId,
  table_id: materialTableId,
  current_revision: {
    ...metadata(materialRecordRevisionId, materialRecordId),
    content: {
      table_revision_id: materialTableRevisionId,
      name: "DP780 Sheet",
      external_key: "dp780",
      description: null,
      folder_id: null,
      folder_revision_id: null,
      values: [],
    },
  },
};

const graph = {
  root: {
    record_id: materialRecordId,
    record_revision_id: materialRecordRevisionId,
    revision_no: 1,
    table_id: materialTableId,
    name: "DP780 Sheet",
    external_key: "dp780",
    domain_binding: null,
  },
  nodes: [
    {
      record_id: materialRecordId,
      record_revision_id: materialRecordRevisionId,
      revision_no: 1,
      table_id: materialTableId,
      name: "DP780 Sheet",
      external_key: "dp780",
      domain_binding: null,
    },
    {
      record_id: testRecordId,
      record_revision_id: testRecordRevisionId,
      revision_no: 1,
      table_id: testTableId,
      name: "Tensile Test 01",
      external_key: "tensile-01",
      domain_binding: {
        binding_id: "51000000-0000-4000-8000-000000000050",
        record_id: testRecordId,
        record_revision_id: testRecordRevisionId,
        kind: "test_run" as const,
        object_id: "51000000-0000-4000-8000-000000000051",
        revision_id: "51000000-0000-4000-8000-000000000052",
        workbench_path: "/tests?object_id=51000000-0000-4000-8000-000000000051&revision_id=51000000-0000-4000-8000-000000000052",
      },
    },
  ],
  links: [],
};

const mocks = vi.hoisted(() => ({
  tables: vi.fn(),
  children: vi.fn(),
  linkTypes: vi.fn(),
  graph: vi.fn(),
  search: vi.fn(),
  createLink: vi.fn(),
  reviseLink: vi.fn(),
  createLinkType: vi.fn(),
  bindDomain: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return {
    ...original,
    listCatalogExplorerTables: mocks.tables,
    listCatalogExplorerChildren: mocks.children,
    listConfigurableCatalogLinkTypes: mocks.linkTypes,
    getCatalogWorkflowGraph: mocks.graph,
    searchConfigurableCatalogRecords: mocks.search,
    createConfigurableRecordLink: mocks.createLink,
    reviseConfigurableRecordLink: mocks.reviseLink,
    createConfigurableCatalogLinkType: mocks.createLinkType,
    bindCatalogRecordDomainRevision: mocks.bindDomain,
  };
});

describe("CatalogExplorer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.tables.mockResolvedValue({ data: { items: [materialTable, testTable] }, etag: null });
    mocks.linkTypes.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.children.mockResolvedValue({
      data: { table: materialTable, folders: [], records: [materialRecord] },
      etag: null,
    });
    mocks.graph.mockResolvedValue({ data: graph, etag: null });
  });

  it("opens lazy Catalog nodes as an exact-revision Workflow graph", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn();
    render(
      <CatalogExplorer
        config={{ baseUrl: "/api/v1", accessToken: "catalog-token" }}
        onNavigate={navigate}
        onOpenConnection={() => undefined}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /Engineering Materials/ }));
    expect(await screen.findByRole("button", { name: /DP780 Sheet/ })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: /DP780 Sheet/ }));

    await waitFor(() => expect(mocks.graph).toHaveBeenCalledWith(
      expect.anything(),
      materialRecordId,
      materialRecordRevisionId,
    ));
    expect(screen.getByText(/exact revision 51000000/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Tensile Test 01/ })).toBeTruthy();
    expect(navigate).toHaveBeenCalledWith(
      `/catalog/explorer/records/${materialRecordId}/revisions/${materialRecordRevisionId}`,
    );
  });

  it("opens a bound governed domain revision from a Workflow node", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn();
    render(
      <CatalogExplorer
        config={{ baseUrl: "/api/v1", accessToken: "catalog-token" }}
        initialRecordId={materialRecordId}
        initialRevisionId={materialRecordRevisionId}
        onNavigate={navigate}
        onOpenConnection={() => undefined}
      />,
    );

    const node = await screen.findByRole("button", { name: /Tensile Test 01/ });
    await user.click(node);
    expect(navigate).toHaveBeenCalledWith(
      "/tests?object_id=51000000-0000-4000-8000-000000000051&revision_id=51000000-0000-4000-8000-000000000052",
    );
  });
});
