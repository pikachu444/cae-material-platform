import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listAllMaterials, readMaterial, type MaterialDetail } from "../../materials/api";
import { listModelsForMaterials, type MaterialModelRow } from "../api";
import { ModelsReader } from "./ModelsReader";

vi.mock("../../materials/api", () => ({ listAllMaterials: vi.fn(), readMaterial: vi.fn() }));
vi.mock("../api", () => ({ listModelsForMaterials: vi.fn(), readMaterialModel: vi.fn(), modelProcessingRelation: vi.fn() }));

const detail: MaterialDetail = {
  material: {
    id: "material", revisionId: "material-pin", name: "DP780", code: "DP780", family: "steel",
    description: null, materialClass: "metal",
    revision: { id: "material-pin", revision_no: 1, content_hash: "hash", schema_id: "material", schema_version: "1", created_at: "2026-09-08T00:00:00Z" },
  },
  states: [{ id: "state", revisionId: "state-pin", materialId: "material", name: "열처리" }],
  propertySets: [],
};
const model: MaterialModelRow = {
  id: "model", revisionId: "model-pin", family: "elastic", schemaId: "elastic", resourcePath: "material-models",
  stateId: "state", stateRevisionId: "state-pin", content: { youngs_modulus_pa: 210e9 }, ir: {},
};

describe("model-list recovery", () => {
  beforeEach(() => {
    vi.mocked(listAllMaterials).mockReset().mockResolvedValue([detail.material]);
    vi.mocked(readMaterial).mockReset().mockResolvedValue(detail);
    vi.mocked(listModelsForMaterials).mockReset().mockResolvedValue([model]);
  });

  it.each(["materials", "details", "models"])("retries a failed %s request and preserves search", async stage => {
    const failed = stage === "materials" ? vi.mocked(listAllMaterials) : stage === "details" ? vi.mocked(readMaterial) : vi.mocked(listModelsForMaterials);
    failed.mockRejectedValueOnce(new Error("일시적인 조회 실패"));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/models?q=DP780"]}><ModelsReader /></MemoryRouter></QueryClientProvider>);

    const retry = await screen.findByRole("button", { name: "다시 시도" });
    const search = screen.getByLabelText("모델 검색") as HTMLInputElement;
    expect(search.value).toBe("DP780");
    fireEvent.change(search, { target: { value: "DP780 steel" } });
    fireEvent.click(retry);

    expect(await screen.findByText("열처리")).toBeTruthy();
    expect(search.value).toBe("DP780 steel");
    expect(failed).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("alert")).toBeNull();
    client.clear();
  });
});
