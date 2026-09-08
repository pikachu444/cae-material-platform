import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MaterialsReader } from "./MaterialsReader";
import { listMaterials, readMaterial, type MaterialDetail, type MaterialRow } from "../api";
import { listTestData, type TestDataRow } from "../../test-data/api";

vi.mock("../api", () => ({ listMaterials: vi.fn(), readMaterial: vi.fn() }));
vi.mock("../../test-data/api", () => ({ listTestData: vi.fn() }));

const material: MaterialRow = { id: "material-1", revisionId: "material-revision-1", revision: { id: "material-revision-1", revision_no: 1, schema_id: "cmp.material", schema_version: "1", content_hash: "material-hash", created_at: "2026-01-01" }, name: "DP780 reference steel", code: "CMP-DP780", family: "dual-phase steel", description: "Reference", materialClass: "metal" };
const detail: MaterialDetail = { material, states: [{ id: "state-1", materialId: material.id, revisionId: "state-revision-1", name: "Room temperature state", stateCode: "RT", status: "stored" }], propertySets: [{ id: "property-1", stateId: "state-1", revisionId: "property-revision-1", content: { density_kg_per_m3: 7800, youngs_modulus_pa: 210000000000, poisson_ratio: 0.3, yield_stress_pa: 450000000 } }] };
const testData: TestDataRow = { id: "test-1", revisionId: "test-revision-1", revision: { id: "test-revision-1", revision_no: 1, schema_id: "cmp.test-data", schema_version: "1", content_hash: "test-hash", created_at: "2026-01-01" }, documentKey: "DP780 tensile", materialMaker: "CMP", materialGrade: "DP780", lotBatch: null, testDate: "2026-01-01", operator: "Operator", laboratory: "Lab", method: "uniaxial tension", specimenId: "Specimen 01", pointCount: 12, channels: [], materialId: material.id, materialStateId: "state-1", materialStateRevisionId: "state-revision-1" };

function renderReader() { const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/materials"]}><Routes><Route path="/materials" element={<MaterialsReader />} /></Routes></MemoryRouter></QueryClientProvider>); }

describe("connected Material hierarchy", () => {
  beforeEach(() => { vi.mocked(listMaterials).mockReset(); vi.mocked(readMaterial).mockReset(); vi.mocked(listTestData).mockReset(); vi.mocked(listMaterials).mockResolvedValue({ items: [material], totalCount: 1, offset: 0, limit: 12, facets: [{ materialClass: "metal", count: 1 }] }); vi.mocked(readMaterial).mockResolvedValue(detail); vi.mocked(listTestData).mockResolvedValue([testData]); });

  it("does not reserve a preview before selection and expands only stored state/specimen relations", async () => {
    renderReader();
    await waitFor(() => expect(screen.getAllByText("DP780 reference steel").length).toBeGreaterThan(0));
    const materialLabel = screen.getAllByText("DP780 reference steel")[0];
    expect(materialLabel).toBeTruthy();
    expect(document.querySelector(".resultsWithPreview")).toBeNull();
    fireEvent.click(materialLabel);
    await waitFor(() => expect(screen.getAllByText("Room temperature state")[0]).toBeTruthy());
    fireEvent.click(screen.getAllByText("Room temperature state")[0]);
    expect(screen.getByText(/Specimen 01/)).toBeTruthy();
    expect(screen.getByText("모델 →")).toBeTruthy();
  });
});
