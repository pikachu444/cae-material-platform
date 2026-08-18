import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  listTestRunsForMaterialState: vi.fn(),
  listGovernedImportProfiles: vi.fn(),
  resolveCatalogDomainRevision: vi.fn(),
  getCatalogWorkflowGraph: vi.fn(),
}));

vi.mock("../../../../../api", async () => {
  const actual = await vi.importActual<typeof import("../../../../../api")>("../../../../../api");
  return { ...actual, ...apiMocks };
});

import { ModelingDataWorkspace } from "./modeling-data-workspace";

const revision = {
  id: "revision-1",
  aggregate_id: "document-1",
  revision_no: 1,
  based_on_revision_id: null,
  schema_id: "urn:cmp:test-data:1.0.0",
  schema_version: "1.0.0",
  content_hash: "a".repeat(64),
  created_at: "2026-08-01T00:00:00Z",
  created_by: "user-1",
  change_reason: "test",
  organization_id: "org-1",
  project_id: "project-1",
  classification: "internal",
  lifecycle_state: "draft",
};

function documentFixture(index: number) {
  const dma = index % 5 === 0;
  return {
    test_data_document_id: `document-${index}`,
    current_revision: { ...revision, id: `revision-${index}`, aggregate_id: `document-${index}` },
    document_key: `PA66-GF30-${dma ? "DMA" : "TENSILE"}-${index}`,
    material_maker: "Example",
    material_grade: "PA66-GF30",
    lot_batch: null,
    test_date: `2026-08-${String((index % 28) + 1).padStart(2, "0")}`,
    operator: "Engineer",
    laboratory: "Lab",
    method: dma ? "dma_frequency_temperature_sweep" : "tensile",
    specimen_id: `S-${index}`,
    point_count: 600 + index,
    canonical_artifact_id: `canonical-${index}`,
    canonical_sha256: "b".repeat(64),
    normalized_artifact_id: `normalized-${index}`,
    normalized_sha256: "c".repeat(64),
    channels: dma
      ? [{ key: "storage", name: "Storage modulus", quantity_semantics: "modulus.storage", axis_role: "dependent", original_unit_string: "MPa", normalized_unit: "Pa", point_count: 600 + index, missing_count: 0 }]
      : [
        { key: "strain", name: "Strain", quantity_semantics: "mechanics.strain.engineering", axis_role: "independent", original_unit_string: "%", normalized_unit: "1", point_count: 600 + index, missing_count: 0 },
        { key: "stress", name: "Stress", quantity_semantics: "mechanics.stress.engineering", axis_role: "dependent", original_unit_string: "MPa", normalized_unit: "Pa", point_count: 600 + index, missing_count: 0 },
      ],
    governed_source: {
      material: { aggregate_id: "material-1", revision_id: "material-revision-1" },
      material_state: { aggregate_id: "state-1", revision_id: "state-revision-1" },
      test_run: { aggregate_id: `run-${index}`, revision_id: `run-revision-${index}` },
    },
  };
}

describe("Modeling Data workspace", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("keeps large libraries searchable and paged while comparison stays optional", async () => {
    apiMocks.listTestRunsForMaterialState.mockResolvedValue({ data: { items: [] } });
    apiMocks.listGovernedImportProfiles.mockResolvedValue({ data: [] });
    apiMocks.resolveCatalogDomainRevision.mockResolvedValue({ data: null });
    apiMocks.getCatalogWorkflowGraph.mockResolvedValue({ data: { root: {}, nodes: [], links: [] } });
    const documents = Array.from({ length: 1_000 }, (_, index) => documentFixture(index + 1));
    const onSelectDocument = vi.fn();
    const onToggleComparison = vi.fn();
    const onContinue = vi.fn();

    render(
      <ModelingDataWorkspace
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        material={{ material_id: "material-1", current_revision: { ...revision, id: "material-revision-1", content: { name: "PA66-GF30" } } } as never}
        state={{ material_state_id: "state-1", current_revision: { ...revision, id: "state-revision-1", content: { name: "Dry as molded" } } } as never}
        documents={documents as never}
        selectedTestDataRefs={[]}
        selectedDocumentId=""
        includedDocumentIds={[]}
        comparisonDocumentIds={[]}
        visibleDocumentKeys={[]}
        processingMappingProfileText="{}"
        plot={<div role="img" aria-label="Test graph" />}
        technicalDetails={<div>Exact identity</div>}
        ribbonOpen
        onRibbonOpenChange={() => undefined}
        onSelectDocument={onSelectDocument}
        onToggleComparison={onToggleComparison}
        onPreviewDocument={() => undefined}
        onImported={() => undefined}
        onObservedCurves={() => undefined}
        onContinue={onContinue}
      />,
    );

    expect(await screen.findByRole("region", { name: "Test Data results" })).toBeTruthy();
    const sourceTabs = screen.getByRole("tablist", { name: "Test data source" });
    expect(sourceTabs.parentElement?.classList.contains("modeling-data-workspace")).toBe(true);
    expect(sourceTabs.nextElementSibling?.classList.contains("modeling-split-workspace")).toBe(true);
    expect(screen.getAllByRole("button", { name: /test 00\d\d$/ })).toHaveLength(25);
    expect(screen.getByText("1–25 of 1,000", { exact: true })).toBeTruthy();
    expect(screen.queryByRole("columnheader", { name: "Compare" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Add comparison" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Continue to Process" })).toBeNull();
    expect(screen.queryByText(/Revision r\d+/)).toBeNull();
    expect(screen.queryByText("PA66-GF30-TENSILE-1", { exact: true })).toBeNull();

    const browserTree = screen.getByRole("tree", { name: "Test Data by material and test type" });
    const browserItems = within(browserTree).getAllByRole("treeitem");
    browserItems[0].focus();
    fireEvent.keyDown(browserTree, { key: "ArrowDown" });
    expect(document.activeElement).toBe(browserItems[1]);
    fireEvent.keyDown(browserTree, { key: "End" });
    expect(document.activeElement).toBe(browserItems.at(-1));

    fireEvent.click(screen.getByRole("button", { name: "Next Test Data page" }));
    expect(await screen.findByRole("button", { name: "Tensile test 0026" })).toBeTruthy();
    expect(screen.getByText("26–50 of 1,000", { exact: true })).toBeTruthy();

    fireEvent.change(screen.getByRole("searchbox", { name: "Find Test Data" }), { target: { value: "0030" } });
    fireEvent.click(screen.getByRole("button", { name: "Find" }));
    expect(await screen.findByText("1 results", { exact: true })).toBeTruthy();
    expect(screen.getByRole("button", { name: "DMA test 0030" })).toBeTruthy();

    fireEvent.change(screen.getByRole("searchbox", { name: "Find Test Data" }), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Find" }));
    fireEvent.click(screen.getByRole("treeitem", { name: "DMA, 200 Test Data records" }));
    expect(await screen.findByText("200 results", { exact: true })).toBeTruthy();

    const firstDma = screen.getByRole("button", { name: "DMA test 0005" });
    fireEvent.click(firstDma);
    expect(onSelectDocument).toHaveBeenLastCalledWith("document-5", "revision-5");
    expect(onToggleComparison).not.toHaveBeenCalled();
    expect(onContinue).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("tab", { name: "Local file" }));
    expect(screen.getByLabelText("Import Test Data file")).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Test Data results" })).toBeNull();
    expect(screen.queryByRole("tree", { name: "Test Data by material and test type" })).toBeNull();
  });

  it("starts a pin-free session at Local file but lets the engineer switch to Library", async () => {
    apiMocks.listTestRunsForMaterialState.mockResolvedValue({ data: { items: [] } });
    apiMocks.listGovernedImportProfiles.mockResolvedValue({ data: [] });
    apiMocks.resolveCatalogDomainRevision.mockResolvedValue({ data: null });
    apiMocks.getCatalogWorkflowGraph.mockResolvedValue({ data: { root: {}, nodes: [], links: [] } });
    const document = documentFixture(1);

    render(
      <ModelingDataWorkspace
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        documents={[document] as never}
        emptySession
        selectedTestDataRefs={[]}
        selectedDocumentId=""
        includedDocumentIds={[]}
        comparisonDocumentIds={[]}
        visibleDocumentKeys={[]}
        processingMappingProfileText="{}"
        plot={<div role="img" aria-label="Empty graph" />}
        ribbonOpen
        onRibbonOpenChange={() => undefined}
        onSelectDocument={() => undefined}
        onToggleComparison={() => undefined}
        onPreviewDocument={() => undefined}
        onImported={() => undefined}
        onObservedCurves={() => undefined}
        onContinue={() => undefined}
      />,
    );

    expect(screen.getByRole("tab", { name: "Local file" }).getAttribute("aria-selected")).toBe("true");
    fireEvent.click(screen.getByRole("tab", { name: "Library" }));
    expect(await screen.findByRole("region", { name: "Test Data results" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Library" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.queryByRole("button", { name: "Continue to Process" })).toBeNull();
  });

  it("bounds deliberate graph comparison without changing the current input", async () => {
    apiMocks.listTestRunsForMaterialState.mockResolvedValue({ data: { items: [] } });
    apiMocks.listGovernedImportProfiles.mockResolvedValue({ data: [] });
    apiMocks.resolveCatalogDomainRevision.mockResolvedValue({ data: null });
    const documents = Array.from({ length: 6 }, (_, index) => documentFixture(index + 1));

    render(
      <ModelingDataWorkspace
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        documents={documents as never}
        selectedTestDataRefs={documents.slice(0, 5).map((item) => ({
          id: item.test_data_document_id,
          revisionId: item.current_revision.id,
          revisionNo: 1,
          label: item.document_key,
        }))}
        selectedDocumentId="document-1"
        includedDocumentIds={["document-1"]}
        comparisonDocumentIds={documents.slice(1, 5).map((item) => item.test_data_document_id)}
        visibleDocumentKeys={documents.slice(0, 5).map((item) => `${item.test_data_document_id}:${item.current_revision.id}`)}
        processingMappingProfileText="{}"
        plot={<div role="img" aria-label="Test graph" />}
        ribbonOpen
        onRibbonOpenChange={() => undefined}
        onSelectDocument={() => undefined}
        onToggleComparison={() => undefined}
        onPreviewDocument={() => undefined}
        onImported={() => undefined}
        onObservedCurves={() => undefined}
        onContinue={() => undefined}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Add comparison" }));
    expect(screen.getByText("Remove one curve before adding another.", { exact: true })).toBeTruthy();
    expect((screen.getByRole("checkbox", { name: "Add Tensile test 0006 to comparison" }) as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByText("Input", { exact: true })).toBeTruthy();
  });

  it("places the current exact selection in the result table and keeps the primary action with the graph", async () => {
    apiMocks.listTestRunsForMaterialState.mockResolvedValue({ data: { items: [] } });
    apiMocks.listGovernedImportProfiles.mockResolvedValue({ data: [] });
    apiMocks.resolveCatalogDomainRevision.mockResolvedValue({ data: null });
    const selected = documentFixture(1);
    const onContinue = vi.fn();

    render(
      <ModelingDataWorkspace
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        material={{ material_id: "material-1", current_revision: { ...revision, id: "material-revision-1", content: { name: "PA66-GF30" } } } as never}
        state={{ material_state_id: "state-1", current_revision: { ...revision, id: "state-revision-1", content: { name: "Dry as molded" } } } as never}
        documents={[selected] as never}
        selectedTestDataRefs={[{ id: "document-1", revisionId: "revision-1", revisionNo: 1, label: "PA66-GF30-TENSILE-1" }]}
        selectedDocumentId="document-1"
        includedDocumentIds={["document-1"]}
        comparisonDocumentIds={[]}
        visibleDocumentKeys={["document-1:revision-1"]}
        processingMappingProfileText="{}"
        plot={<div role="img" aria-label="Stress–strain plot" />}
        ribbonOpen
        onRibbonOpenChange={() => undefined}
        onSelectDocument={() => undefined}
        onToggleComparison={() => undefined}
        onPreviewDocument={() => undefined}
        onImported={() => undefined}
        onObservedCurves={() => undefined}
        onContinue={onContinue}
      />,
    );

    const selectedButton = await screen.findByRole("button", { name: "Tensile test 0001" });
    expect(selectedButton.getAttribute("aria-current")).toBe("true");
    expect(screen.getByRole("heading", { name: "Stress–strain curves" })).toBeTruthy();
    const continueButton = screen.getByRole("button", { name: "Continue to Process" });
    expect(continueButton.closest(".modeling-data-plot-actions")).toBeTruthy();
    fireEvent.click(continueButton);
    expect(onContinue).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(apiMocks.resolveCatalogDomainRevision).toHaveBeenCalledWith(
      expect.anything(),
      "test_data",
      "document-1",
      "revision-1",
    ));
  });
});
