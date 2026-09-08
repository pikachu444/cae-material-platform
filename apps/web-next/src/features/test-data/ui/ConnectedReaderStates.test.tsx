import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConnectedTestDataReader } from "./ConnectedTestDataReader";
import type { TestDataDetail, TestDataRow } from "../api";
import { listTestData, readTestData } from "../api";

vi.mock("../api", () => ({
  downloadTestData: vi.fn(),
  listTestData: vi.fn(),
  readTestData: vi.fn(),
}));

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}</output>;
}

const row: TestDataRow = {
  id: "source-1",
  revisionId: "source-revision-1",
  revision: { id: "source-revision-1", revision_no: 1, schema_id: "cmp.test-data", schema_version: "1.0.0", content_hash: "source-hash", created_at: "2026-01-01T00:00:00Z" },
  documentKey: "Primary document",
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

const detail: TestDataDetail = {
  row,
  conditions: [],
  channels: [],
  curve: null,
  canonicalBytes: new Uint8Array([1]),
};

function listRows(count = 13): TestDataRow[] {
  return Array.from({ length: count }, (_, index) => {
    const number = index + 1;
    const revisionId = `source-revision-${number}`;
    return {
      ...row,
      id: `source-${number}`,
      revisionId,
      revision: { ...row.revision, id: revisionId, content_hash: `source-hash-${number}` },
      documentKey: `Document ${String(number).padStart(2, "0")}`,
      testDate: `2026-01-${String(number).padStart(2, "0")}`,
      method: number % 2 ? "tensile" : "compression",
    };
  });
}

function renderReader(initialEntry: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[initialEntry]}><LocationProbe /><Routes><Route path="/test-data" element={<ConnectedTestDataReader />} /></Routes></MemoryRouter></QueryClientProvider>);
}

describe("connected Test Data direct reader recovery", () => {
  beforeEach(() => {
    vi.mocked(listTestData).mockReset();
    vi.mocked(readTestData).mockReset();
    vi.mocked(listTestData).mockResolvedValue([]);
  });

  it("reads the requested revision even when it is absent from the list", async () => {
    vi.mocked(readTestData).mockResolvedValue(detail);
    renderReader("/test-data?id=source-1&revision_id=source-revision-1");

    expect(await screen.findByText("Primary document")).toBeTruthy();
    expect(vi.mocked(readTestData)).toHaveBeenCalledWith("source-1", "source-revision-1", expect.anything());
    expect(screen.getByRole("button", { name: "실험 미리보기 접기" })).toBeTruthy();
  });

  it("keeps a missing exact identity actionable instead of leaving the reader loading", async () => {
    vi.mocked(readTestData).mockRejectedValue(new Error("Test Data document revision is not visible"));
    renderReader("/test-data?id=missing-source&revision_id=missing-revision");

    expect((await screen.findByRole("alert")).textContent).toContain("Test Data document revision is not visible");
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "실험 미리보기 접기" }));
    await waitFor(() => expect(screen.getByTestId("location").textContent).toBe("/test-data"));
  });

  it("pages the complete local scope and closes an off-page preview when filters change", async () => {
    vi.mocked(listTestData).mockResolvedValue(listRows());
    vi.mocked(readTestData).mockResolvedValue({ ...detail, row: listRows()[12] });
    renderReader("/test-data?page=1");

    expect(await within(await screen.findByRole("region", { name: "실험 데이터" })).findByText("Document 13")).toBeTruthy();
    expect(screen.getByText("13–13 / 13")).toBeTruthy();
    fireEvent.change(screen.getByRole("searchbox", { name: "실험 데이터 검색" }), { target: { value: "Document 01" } });
    fireEvent.click(screen.getByRole("button", { name: "검색" }));

    await waitFor(() => {
      const location = screen.getByTestId("location").textContent ?? "";
      expect(location).toContain("q=Document+01");
      expect(location).toContain("page=0");
    });
    expect(screen.queryByRole("button", { name: "실험 미리보기 접기" })).toBeNull();
    expect(await within(screen.getByRole("region", { name: "실험 데이터" })).findByText("Document 01")).toBeTruthy();
  });

  it("keeps stable sort order and restores the selected row after expanded return", async () => {
    const rows = listRows();
    vi.mocked(listTestData).mockResolvedValue(rows);
    vi.mocked(readTestData).mockImplementation(async (id, revisionId) => ({ ...detail, row: rows.find((item) => item.id === id && item.revisionId === revisionId) ?? rows[0] }));
    renderReader("/test-data?sort=date&direction=descending&page=0");

    expect(await within(await screen.findByRole("region", { name: "실험 데이터" })).findByText("Document 13")).toBeTruthy();
    const selected = within(screen.getByRole("region", { name: "실험 데이터" })).getByRole("button", { name: /Document 13/ });
    fireEvent.keyDown(selected, { key: "Enter" });
    await waitFor(() => expect(screen.getByTestId("location").textContent).toContain("expanded=1"));
    fireEvent.click(screen.getByRole("button", { name: "‹ 목록 보기" }));
    await waitFor(() => expect(screen.getByTestId("location").textContent).not.toContain("expanded=1"));
    await waitFor(() => expect(document.activeElement).toBe(within(screen.getByRole("region", { name: "실험 데이터" })).getByRole("button", { name: /Document 13/ })));
  });

  it("ignores a late detail response after selection changes and the preview closes", async () => {
    const rows = listRows(2);
    let resolveFirst: (value: TestDataDetail) => void = () => undefined;
    let resolveSecond: (value: TestDataDetail) => void = () => undefined;
    const first = new Promise<TestDataDetail>((resolve) => { resolveFirst = resolve; });
    const second = new Promise<TestDataDetail>((resolve) => { resolveSecond = resolve; });
    vi.mocked(listTestData).mockResolvedValue(rows);
    vi.mocked(readTestData).mockImplementation((id) => id === rows[0]?.id ? first : second);
    renderReader(`/test-data?id=${rows[0]?.id}&revision_id=${rows[0]?.revisionId}`);

    expect(await within(screen.getByRole("region", { name: "실험 데이터" })).findByRole("button", { name: /Document 01/ })).toBeTruthy();
    fireEvent.click(within(screen.getByRole("region", { name: "실험 데이터" })).getByRole("button", { name: /Document 02/ }));
    expect(await screen.findByRole("heading", { name: "Document 02" })).toBeTruthy();
    resolveFirst({ ...detail, row: rows[0] as TestDataRow });
    await waitFor(() => expect(screen.getByRole("heading", { name: "Document 02" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "실험 미리보기 접기" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "실험 미리보기 접기" })).toBeNull());
    resolveSecond({ ...detail, row: rows[1] as TestDataRow });
    await waitFor(() => expect(screen.queryByRole("button", { name: "실험 미리보기 접기" })).toBeNull());
  });
});
