import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DomainWorkflowLinks } from "./domain-workflow-links";

const binding = {
  binding_id: "66000000-0000-4000-8000-000000000001",
  record_id: "66000000-0000-4000-8000-000000000002",
  record_revision_id: "66000000-0000-4000-8000-000000000003",
  kind: "neutral_material" as const,
  object_id: "66000000-0000-4000-8000-000000000004",
  revision_id: "66000000-0000-4000-8000-000000000005",
  workbench_path: "/materials/demo/models?neutral_material_id=66000000-0000-4000-8000-000000000004",
};

const mocks = vi.hoisted(() => ({
  resolve: vi.fn(),
  graph: vi.fn(),
}));

vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return {
    ...actual,
    resolveCatalogDomainRevision: mocks.resolve,
    getCatalogWorkflowGraph: mocks.graph,
  };
});

describe("DomainWorkflowLinks", () => {
  beforeEach(() => {
    mocks.resolve.mockReset();
    mocks.graph.mockReset();
    mocks.resolve.mockResolvedValue({ data: binding });
    mocks.graph.mockResolvedValue({
      data: {
        root: {
          record_id: binding.record_id,
          record_revision_id: binding.record_revision_id,
          revision_no: 1,
          table_id: "66000000-0000-4000-8000-000000000010",
          name: "DP780 Neutral JSON",
          external_key: "dp780-neutral",
          domain_binding: binding,
        },
        nodes: [
          {
            record_id: binding.record_id,
            record_revision_id: binding.record_revision_id,
            revision_no: 1,
            table_id: "66000000-0000-4000-8000-000000000010",
            name: "DP780 Neutral JSON",
            external_key: "dp780-neutral",
            domain_binding: binding,
          },
          {
            record_id: "66000000-0000-4000-8000-000000000020",
            record_revision_id: "66000000-0000-4000-8000-000000000021",
            revision_no: 1,
            table_id: "66000000-0000-4000-8000-000000000010",
            name: "DP780 Abaqus card",
            external_key: "dp780-abaqus",
            domain_binding: {
              ...binding,
              binding_id: "66000000-0000-4000-8000-000000000022",
              record_id: "66000000-0000-4000-8000-000000000020",
              record_revision_id: "66000000-0000-4000-8000-000000000021",
              kind: "neutral_solver_card",
              object_id: "66000000-0000-4000-8000-000000000023",
              revision_id: "66000000-0000-4000-8000-000000000024",
              workbench_path: "/exports?solver_card_id=66000000-0000-4000-8000-000000000023",
            },
          },
        ],
        links: [],
      },
    });
  });

  it("resolves an exact domain revision and exposes both explorer and related workbench links", async () => {
    render(
      <DomainWorkflowLinks
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        target={{
          kind: "neutral_material",
          objectId: binding.object_id,
          revisionId: binding.revision_id,
          label: "Neutral Material JSON r1",
        }}
      />,
    );

    await waitFor(() => expect(mocks.resolve).toHaveBeenCalled());
    expect(screen.getByRole("link", { name: "Open Workflow Explorer" }).getAttribute("href")).toBe(
      `/catalog/explorer/records/${binding.record_id}/revisions/${binding.record_revision_id}`,
    );
    expect(screen.getByRole("link", { name: /DP780 Abaqus card/ }).getAttribute("href")).toBe(
      "/exports?solver_card_id=66000000-0000-4000-8000-000000000023",
    );
  });

  it("states when the exact revision has not been projected", async () => {
    mocks.resolve.mockResolvedValueOnce({ data: null });
    render(
      <DomainWorkflowLinks
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        target={{
          kind: "test_data",
          objectId: binding.object_id,
          revisionId: binding.revision_id,
          label: "Test JSON r1",
        }}
      />,
    );
    expect(await screen.findByText(/not yet projected/)).toBeTruthy();
    expect(mocks.graph).not.toHaveBeenCalled();
  });
});
