import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listTestData, type TestDataRow } from "../../test-data/api";
import { listModelsForState } from "../../models";
import { listProcessingOutputs, readProcessingOutput, type ProcessingOutputDetail, type ProcessingOutputRow } from "../api";
import { ProcessingOutputsReader } from "./ProcessingOutputsReader";

vi.mock("../api", () => ({
  downloadProcessingOutput: vi.fn(),
  listProcessingOutputs: vi.fn(),
  readProcessingOutput: vi.fn(),
}));

vi.mock("../../test-data/api", () => ({
  listTestData: vi.fn(),
}));

vi.mock("../../models", () => ({
  listModelsForState: vi.fn(),
  modelProcessingRelation: vi.fn(),
}));

const row: ProcessingOutputRow = {
  id: "output-1",
  revisionId: "output-revision-1",
  revision: { id: "output-revision-1", revision_no: 1, schema_id: "cmp.processing-output", schema_version: "1.0.0", content_hash: "output-hash", created_at: "2026-01-01T00:00:00Z" },
  label: "Saved tensile output",
  sourceDocument: { aggregate_id: "source-1", revision_id: "source-revision-old" },
  sourceDocumentSha256: "source-hash",
  mappingProfile: null,
  mappingProfileSha256: null,
  steps: [],
  independentQuantity: "strain.true_plastic",
  stageCount: 0,
  finalPointCount: 0,
  outputSha256: "output-bytes-hash",
  exportProvenance: null,
};

const source: TestDataRow = {
  id: "source-1",
  revisionId: "source-revision-current",
  revision: { id: "source-revision-current", revision_no: 2, schema_id: "cmp.test-data", schema_version: "1.0.0", content_hash: "source-current-hash", created_at: "2026-02-01T00:00:00Z" },
  documentKey: "Primary source",
  materialMaker: "CMP",
  materialGrade: "DP780",
  lotBatch: null,
  testDate: "2026-01-01",
  operator: "Operator",
  laboratory: "Lab",
  method: "tensile",
  specimenId: "specimen-1",
  pointCount: 3,
  channels: [],
  materialId: "material-1",
};

const detail: ProcessingOutputDetail = { row, stages: [], outputBytes: new Uint8Array([1, 2, 3]) };

function renderReader(initialEntry = "/processing-outputs") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[initialEntry]}><Routes><Route path="/processing-outputs" element={<ProcessingOutputsReader />} /></Routes></MemoryRouter></QueryClientProvider>);
}

describe("connected Processing Output reader boundaries", () => {
  beforeEach(() => {
    vi.mocked(listProcessingOutputs).mockReset();
    vi.mocked(readProcessingOutput).mockReset();
    vi.mocked(listTestData).mockReset();
    vi.mocked(listModelsForState).mockReset();
    vi.mocked(listProcessingOutputs).mockResolvedValue([row]);
    vi.mocked(readProcessingOutput).mockResolvedValue(detail);
    vi.mocked(listModelsForState).mockResolvedValue([]);
    vi.mocked(listTestData).mockResolvedValue([]);
  });

  it("keeps an authorized output visible when the optional Test Data reader is denied", async () => {
    vi.mocked(listTestData).mockRejectedValue(new Error("403 Test Data read denied"));
    renderReader();

    expect(await screen.findByText("Saved tensile output")).toBeTruthy();
    expect(screen.queryByText("처리 데이터를 불러올 수 없습니다")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(document.querySelector(".resultsWithPreview")).toBeNull();
  });

  it("filters by stored stage and keeps the result count in the local page scope", async () => {
    const rows = [
      row,
      { ...row, id: "output-2", revisionId: "output-revision-2", label: "Saved DMA output", steps: [{ method_id: "polymer.dma_prony_fit_compare", method_version: "1", options: {} }], finalPointCount: 24 },
    ];
    vi.mocked(listProcessingOutputs).mockResolvedValue(rows);
    renderReader();

    expect(await screen.findByText("1–2 / 2")).toBeTruthy();
    fireEvent.change(screen.getByRole("combobox", { name: "처리 단계" }), { target: { value: "polymer.dma_prony_fit_compare" } });
    await waitFor(() => expect(screen.getByText("1–1 / 1")).toBeTruthy());
    expect(screen.getByText("Saved DMA output")).toBeTruthy();
    expect(screen.queryByText("Saved tensile output")).toBeNull();
  });

  it("marks a saved output as older when its source has advanced", async () => {
    vi.mocked(listTestData).mockResolvedValue([source]);
    renderReader("/processing-outputs?id=output-1&revision_id=output-revision-1");

    expect(await screen.findByText(/이 결과는 변경 전 실험 데이터를 사용했습니다/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "상세 ↗" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "확대 상세" })).toBeTruthy();
  });
});
