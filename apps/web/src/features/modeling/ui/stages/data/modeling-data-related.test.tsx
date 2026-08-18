import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  resolveCatalogDomainRevision: vi.fn(),
  getCatalogWorkflowGraph: vi.fn(),
}));

vi.mock("../../../../../api", async () => {
  const actual = await vi.importActual<typeof import("../../../../../api")>("../../../../../api");
  return { ...actual, ...apiMocks };
});

import { ModelingDataRelated } from "./modeling-data-related";

function binding(kind: string, recordId: string, revisionId: string, path: string) {
  return {
    binding_id: `${recordId}-binding`,
    record_id: recordId,
    record_revision_id: revisionId,
    kind,
    object_id: `${recordId}-object`,
    revision_id: `${revisionId}-object`,
    workbench_path: path,
  };
}

function node(name: string, recordId: string, revisionId: string, kind: string, path: string) {
  return {
    record_id: recordId,
    record_revision_id: revisionId,
    revision_no: 1,
    table_id: "table-1",
    name,
    external_key: null,
    data_category: null,
    domain_binding: binding(kind, recordId, revisionId, path),
  };
}

describe("Modeling Data related records", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows only real graph-linked records grouped by platform data category", async () => {
    const root = node("Tensile test 0001", "record-test", "record-test-r1", "test_data", "/test-data/1");
    apiMocks.resolveCatalogDomainRevision.mockResolvedValue({
      data: binding("test_data", "record-test", "record-test-r1", "/test-data/1"),
    });
    apiMocks.getCatalogWorkflowGraph.mockResolvedValue({
      data: {
        root,
        nodes: [
          root,
          node("CMP-DEMO-PA66-GF30 material reference", "record-material", "record-material-r1", "material", "/materials/1"),
          node("PA66-GF30 dry Material State", "record-state", "record-state-r1", "material_state", "/materials/states/1"),
          node("PA66-GF30 reference test", "record-reference", "record-reference-r1", "test_data", "/test-data/2"),
          node("PA66-GF30 reference test", "record-reference-copy", "record-reference-copy-r1", "test_data", "/test-data/3"),
          node("PA66-GF30 calibrated model Processing Output", "record-model", "record-model-r1", "material_model", "/models/1"),
          node("PA66-GF30 solver card", "record-card", "record-card-r1", "solver_card", "/solver-cards/1"),
        ],
        links: [],
      },
    });

    render(<ModelingDataRelated config={{ baseUrl: "/api/v1", accessToken: "token" }} documentId="document-1" revisionId="revision-1" label="Tensile test 0001" />);

    expect(await screen.findByRole("heading", { name: "Related data" })).toBeTruthy();
    expect(screen.getByText("Technical Data", { exact: true })).toBeTruthy();
    expect(screen.getByText("Test Data", { exact: true })).toBeTruthy();
    expect(screen.getByText("Simulation Data", { exact: true })).toBeTruthy();
    expect(screen.getByText("Solver Cards", { exact: true })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Tensile test 0001" })).toBeNull();
    expect(screen.getByRole("link", { name: "PA66-GF30 datasheet" }).getAttribute("href")).toBe("/materials/1");
    expect(screen.queryByRole("link", { name: /Material State/ })).toBeNull();
    expect(screen.getByRole("link", { name: "PA66-GF30 calibrated model" }).getAttribute("href")).toBe("/models/1");
    expect(screen.getAllByRole("link", { name: "PA66-GF30 reference test" })).toHaveLength(1);
    expect(apiMocks.getCatalogWorkflowGraph).toHaveBeenCalledWith(
      expect.anything(),
      "record-test",
      "record-test-r1",
      5,
    );
  });

  it("does not fabricate a Related section and offers a bounded retry after failure", async () => {
    apiMocks.resolveCatalogDomainRevision.mockRejectedValueOnce(new Error("offline"));
    apiMocks.resolveCatalogDomainRevision.mockResolvedValueOnce({ data: null });

    const { container } = render(<ModelingDataRelated config={{ baseUrl: "/api/v1", accessToken: "token" }} documentId="document-1" revisionId="revision-1" label="Tensile test 0001" />);

    expect((await screen.findByRole("alert")).textContent).toContain("Related data could not be loaded.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(apiMocks.resolveCatalogDomainRevision).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(container.querySelector(".modeling-data-related")).toBeNull());
  });
});
