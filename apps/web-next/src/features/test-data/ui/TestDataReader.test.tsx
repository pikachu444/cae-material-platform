import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router";
import type { ReactNode } from "react";
import { ReaderGatewayProvider, useReaderSession } from "../../../shared/api/ReaderGatewayProvider";
import { ReaderGatewayError, type DownloadArtifact, type ReaderGateway, type ReaderSearchResult } from "../../../shared/api/reader-gateway";
import type { SolverCard, TestDataRecord } from "../../../shared/model/reader-contracts";
import { createPrototypeReaderGateway } from "../../../prototype/prototype-gateway";
import { CardsReader } from "../../cards/ui/CardsReader";
import { TestDataReader } from "./TestDataReader";

function LocationProbe() { const location = useLocation(); return <output data-testid="location">{location.pathname}{location.search}</output>; }
function ScopeProbe() { const session = useReaderSession(); return <button type="button" onClick={() => void session.changeScope({ projectID: "changed-project" })}>Change scope</button>; }
function CardSwitchProbe() { const navigate = useNavigate(); return <button type="button" onClick={() => navigate("/cards/card-00002?layout=B")}>Switch card</button>; }

function makeGateway(overrides: Partial<ReaderGateway> = {}): ReaderGateway {
  const base = createPrototypeReaderGateway();
  return {
    mode: base.mode,
    scopeKey: base.scopeKey,
    searchTestData: base.searchTestData.bind(base),
    getTestData: base.getTestData.bind(base),
    searchCards: base.searchCards.bind(base),
    getCard: base.getCard.bind(base),
    downloadCard: base.downloadCard.bind(base),
    patchDisplayMetadata: base.patchDisplayMetadata.bind(base),
    ...overrides,
  };
}

function renderReader(initialEntry: string, gateway = createPrototypeReaderGateway(), probe?: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ReaderGatewayProvider gateway={gateway}><MemoryRouter initialEntries={[initialEntry]}><LocationProbe />{probe}<Routes><Route path="/test-data" element={<TestDataReader />} /><Route path="/test-data/:id" element={<TestDataReader />} /><Route path="/cards" element={<CardsReader />} /><Route path="/cards/:id" element={<CardsReader />} /></Routes></MemoryRouter></ReaderGatewayProvider></QueryClientProvider>);
}

function makeTestDataResult(title: string): ReaderSearchResult<TestDataRecord> {
  return {
    rows: [{
      id: "td-late",
      title,
      description: "Controlled lifecycle test row.",
      kind: "tensile",
      sourceLabel: "Test",
      sourceFilename: "test.csv",
      condition: { temperature: "23 °C", rate: "1 mm/min", environment: "Dry air" },
      materialContext: { label: "Reference steel", density: "7,850 kg/m³", youngsModulus: "210 GPa", poissonRatio: "0.30" },
      properties: [
        { key: "density", label: "Density", value: "7,850", unit: "kg/m³", conditionOrScope: "Reference" },
        { key: "youngs_modulus", label: "Young's modulus", value: "210", unit: "GPa", conditionOrScope: "Reference" },
        { key: "poisson_ratio", label: "Poisson ratio", value: "0.30", unit: null, conditionOrScope: "Reference" },
      ],
      sourcePointCount: 10,
      previewPointCount: 10,
      cardIds: [],
      relationLabel: "No stored card association",
      mappingStatus: "exact",
      updatedAt: "2026-01-01",
    }],
    total: 1,
    requestScopeKey: "controlled-scope",
  };
}

const controlledCard = (id: string, title: string, mappingStatus: SolverCard["mappingStatus"] = "exact"): SolverCard => ({
  id,
  title,
  description: "Controlled lifecycle test card.",
  testDataIds: [],
  relationLabel: "Explicitly associated Test Data",
  mappingStatus,
  mappingNote: "Controlled lifecycle test mapping.",
  properties: [{ key: "density", label: "Density", value: "7,850", unit: "kg/m³", conditionOrScope: "Reference" }],
  nativeFileName: `${id}.rad`,
  nativeByteLength: 1,
  nativeSha256: "0000000000000000000000000000000000000000000000000000000000000000",
  outputStatus: "complete",
  nativeBytes: new Uint8Array([7]),
});

describe("Test Data reader journey", () => {
  it("starts with a neutral choose-result state and carries an explicit association to Cards", async () => {
    renderReader("/test-data");
    await waitFor(() => expect(screen.getByRole("heading", { name: "Select a Test Data row" })).toBeTruthy());
    expect(screen.queryByText(/Test Data unavailable/)).toBeNull();
  });

  it("keeps the same ordinary ID across A/B detail and does not reuse TestData q as Cards q", async () => {
    renderReader("/test-data?selection=td-00042&q=td-00042&layout=B");
    await waitFor(() => expect(screen.getByRole("heading", { name: /Reference tensile coupon/ })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /OpenRadioss linear elastic reference card/ }));
    await waitFor(() => expect(screen.getByRole("heading", { name: /OpenRadioss linear elastic reference card/ })).toBeTruthy());
    expect(screen.getByTestId("location").textContent).toContain("/cards/card-00001");
    expect(screen.getByTestId("location").textContent).not.toContain("q=td-00042");
    expect(screen.getByRole("heading", { name: "Native preview" })).toBeTruthy();
  });

  it("uses the direct path ID when a conflicting selection query is supplied", async () => {
    renderReader("/test-data/td-00042?selection=td-00037&layout=B");
    await waitFor(() => expect(screen.getByRole("heading", { name: /Reference tensile coupon/ })).toBeTruthy());
    expect(screen.getByTestId("location").textContent).toContain("/test-data/td-00042");
    expect(screen.getByTestId("location").textContent).toContain("selection=td-00042");

    cleanup();
    renderReader("/cards/card-00001?selection=card-00002&layout=B", makeGateway());
    await waitFor(() => expect(screen.getByRole("heading", { name: /OpenRadioss linear elastic reference card/ })).toBeTruthy());
    expect(screen.getByTestId("location").textContent).toContain("/cards/card-00001");
    expect(screen.getByTestId("location").textContent).toContain("selection=card-00001");
  });

  it("renders session recovery and never leaves protected rows visible after a 401", async () => {
    const gateway = makeGateway({
      searchTestData: async () => {
        throw new ReaderGatewayError(401, "SESSION_EXPIRED", "The reader session expired.");
      },
    });
    renderReader("/test-data", gateway);
    await waitFor(() => expect(screen.getByRole("heading", { name: "Session recovery required" })).toBeTruthy());
    expect(screen.queryByText(/late protected row/i)).toBeNull();
  });

  it("drops a late result from the previous scope instead of rendering it", async () => {
    let callCount = 0;
    let resolveFirst!: (result: ReaderSearchResult<TestDataRecord>) => void;
    const firstRequest = new Promise<ReaderSearchResult<TestDataRecord>>((resolve) => { resolveFirst = resolve; });
    const gateway = makeGateway({
      searchTestData: async () => {
        callCount += 1;
        if (callCount === 1) return await firstRequest;
        return { rows: [], total: 0, requestScopeKey: "changed-scope" };
      },
    });
    renderReader("/test-data", gateway, <ScopeProbe />);
    await waitFor(() => expect(callCount).toBe(1));
    fireEvent.click(screen.getByRole("button", { name: "Change scope" }));
    await waitFor(() => expect(callCount).toBe(2));
    await waitFor(() => expect(screen.getByRole("heading", { name: "No Test Data matches" })).toBeTruthy());
    await act(async () => { resolveFirst(makeTestDataResult("Late old row")); });
    expect(screen.queryByText("Late old row")).toBeNull();
  });

  it("ignores a delayed download after the selected card changes", async () => {
    const firstCard = controlledCard("card-00001", "First controlled card");
    const secondCard = controlledCard("card-00002", "Second controlled card", "approximated");
    const artifact: DownloadArtifact = { fileName: firstCard.nativeFileName, bytes: new Uint8Array([7]), sha256: firstCard.nativeSha256, byteLength: 1 };
    let resolveDownload!: (value: DownloadArtifact) => void;
    let downloadSignal: AbortSignal | undefined;
    const downloadPromise = new Promise<DownloadArtifact>((resolve) => { resolveDownload = resolve; });
    const gateway = makeGateway({
      searchCards: async () => ({ rows: [firstCard, secondCard], total: 2, requestScopeKey: "cards-scope" }),
      getCard: async (id) => id === secondCard.id ? secondCard : firstCard,
      downloadCard: async (_id, _params, signal) => { downloadSignal = signal; return await downloadPromise; },
    });
    renderReader("/cards/card-00001?layout=B", gateway, <CardSwitchProbe />);
    await waitFor(() => expect(screen.getByRole("heading", { name: "First controlled card" })).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Download native card" }));
    await waitFor(() => expect(downloadSignal).toBeDefined());
    fireEvent.click(screen.getByRole("button", { name: "Switch card" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Second controlled card" })).toBeTruthy());
    expect(downloadSignal?.aborted).toBe(true);
    await act(async () => { resolveDownload(artifact); });
    expect(screen.queryByText(/Downloaded/)).toBeNull();
  });

  it("retains a malformed card identity while blocking its preview and download", async () => {
    const malformedCard = { ...controlledCard("card-malformed", "Malformed card metadata"), mappingStatus: "unknown" as SolverCard["mappingStatus"] };
    const gateway = makeGateway({
      searchCards: async () => ({ rows: [malformedCard], total: 1, requestScopeKey: "cards-scope" }),
      getCard: async () => malformedCard,
    });
    renderReader("/cards/card-malformed?layout=B", gateway);
    await waitFor(() => expect(screen.getByRole("heading", { name: "Malformed card metadata" })).toBeTruthy());
    expect(screen.getByText(/Native preview is unavailable/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Download native card" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
