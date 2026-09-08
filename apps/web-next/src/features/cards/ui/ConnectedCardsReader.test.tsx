import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConnectedCardsReader } from "./ConnectedCardsReader";
import { listProjectCards, type SolverCardRow } from "../api";

vi.mock("../api", () => ({
  cardFamilyPaths: { reference_elastic: "solver-cards", tabulated_plasticity: "elastoplastic-solver-cards" },
  downloadCard: vi.fn(),
  listProjectCards: vi.fn(),
  readCard: vi.fn(),
  readCardByIdentity: vi.fn(),
}));

function LocationProbe() { const location = useLocation(); return <output data-testid="location">{location.pathname}{location.search}</output>; }

const rows: SolverCardRow[] = [
  { id: "card-a", revisionId: "card-a-revision", revisionNo: 1, family: "tabulated_plasticity", title: "Tabulated card", schemaId: "schema-a", contentSha256: "hash-a", cardSha256: "native-a", materialId: "material-a", materialModelId: null, materialModelRevisionId: null, neutralMaterialId: null, neutralMaterialRevisionId: null, target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" }, solverMaterialId: 1, exporterId: null, modelFamily: null, neutralFamily: null, unsupportedReason: null, links: { self: "/self-a", preview: "/preview-a", download: "/download-a" } },
  { id: "card-b", revisionId: "card-b-revision", revisionNo: 1, family: "reference_elastic", title: "Elastic card", schemaId: "schema-b", contentSha256: "hash-b", cardSha256: "native-b", materialId: "material-b", materialModelId: null, materialModelRevisionId: null, neutralMaterialId: null, neutralMaterialRevisionId: null, target: { solver: "openradioss", version: "2025", unit_system: "kg_m_s" }, solverMaterialId: 2, exporterId: null, modelFamily: null, neutralFamily: null, unsupportedReason: null, links: { self: "/self-b", preview: "/preview-b", download: "/download-b" } },
];

function renderReader(initialEntry = "/cards") { const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[initialEntry]}><LocationProbe /><Routes><Route path="/cards" element={<ConnectedCardsReader />} /></Routes></MemoryRouter></QueryClientProvider>); }

describe("connected Solver Card workspace layout and filters", () => {
  beforeEach(() => { vi.mocked(listProjectCards).mockReset(); vi.mocked(listProjectCards).mockResolvedValue(rows); });

  it("does not reserve an unused preview column before a card is selected", async () => {
    renderReader();
    expect(await screen.findByText("Elastic card")).toBeTruthy();
    expect(document.querySelector(".resultsWithPreview")).toBeNull();
  });

  it("updates URL-backed family sorting without selecting a card", async () => {
    renderReader();
    expect(await screen.findByText("Elastic card")).toBeTruthy();
    const sort = screen.getByRole("combobox", { name: "솔버 카드 정렬" });
    await waitFor(() => expect(sort).toBeTruthy());
    fireEvent.change(sort, { target: { value: "family:descending" } });
    await waitFor(() => expect(screen.getByTestId("location").textContent).toContain("sort=family"));
  });
  it("combines solver and unit filters and clears them without requiring a material selection", async () => {
    vi.mocked(listProjectCards).mockResolvedValue([...rows, { ...rows[0], id: "abaqus-mm", title: "Abaqus mm card", target: { solver: "abaqus", version: "2025", unit_system: "tonne_mm_s" } }]);
    renderReader();
    await screen.findByText("Abaqus mm card");
    fireEvent.change(screen.getByRole("combobox", { name: "솔버" }), { target: { value: "abaqus" } });
    expect(screen.queryByText("Elastic card")).toBeNull();
    fireEvent.change(screen.getByRole("combobox", { name: "단위계" }), { target: { value: "kg_m_s" } });
    expect(screen.getByText("조건에 맞는 솔버 카드가 없습니다.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "조건 초기화" }));
    expect(screen.getByText("Elastic card")).toBeTruthy();
    expect(screen.getByText("Abaqus mm card")).toBeTruthy();
  });
});
