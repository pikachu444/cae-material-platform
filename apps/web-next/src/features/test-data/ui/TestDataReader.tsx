import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createColumnHelper,
  rowPaginationFeature,
  rowSortingFeature,
  tableFeatures,
  useTable,
  type PaginationState,
  type SortingState,
  type Updater,
} from "@tanstack/react-table";
import { AlertCircle, ArrowLeft, ArrowRight, ExternalLink, FileText, Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router";
import { useReaderGateway, useReaderScope, useReaderSession } from "../../../shared/api/ReaderGatewayProvider";
import { isGatewayError, type ReaderGatewayError, type ReaderSearchResult } from "../../../shared/api/reader-gateway";
import { ConditionSummary, PropertyTable } from "../../../shared/ui/EngineeringValue";
import { Button } from "../../../shared/ui/Button";
import { CurvePreview } from "../../../shared/ui/CurvePreview";
import { RenameDialog } from "../../../shared/ui/RenameDialog";
import { ReaderState } from "../../../shared/ui/ReaderState";
import { StatusTag } from "../../../shared/ui/StatusTag";
import type { PrototypeScenario, ReaderQueryParams, TestDataRecord } from "../../../shared/model/reader-contracts";
import styles from "./TestDataReader.module.css";

const readerFeatures = tableFeatures({ rowSortingFeature, rowPaginationFeature });
const testDataColumnHelper = createColumnHelper<typeof readerFeatures, TestDataRecord>();
const testDataColumns = testDataColumnHelper.columns([
  testDataColumnHelper.accessor("id", { id: "id", header: "ID", cell: (info) => <code>{info.getValue()}</code>, enableSorting: false }),
  testDataColumnHelper.accessor("title", { id: "title", header: "Test Data", cell: (info) => <span className={styles.titleCell} title={info.getValue()}>{info.getValue()}</span> }),
  testDataColumnHelper.accessor((row) => row.condition.temperature, { id: "condition", header: "Temperature", cell: (info) => <span className={styles.numeric}>{info.getValue()}</span>, enableSorting: false }),
  testDataColumnHelper.accessor("updatedAt", { id: "updatedAt", header: "Updated", cell: (info) => <span className={styles.numeric}>{info.getValue()}</span> }),
]);

const PAGE_SIZE = 50;
const scenarios: PrototypeScenario[] = ["normal", "dense", "empty", "error", "unsupported", "long-name"];

function readParams(searchParams: URLSearchParams): ReaderQueryParams {
  const kind = searchParams.get("kind");
  const sort = searchParams.get("sort");
  const direction = searchParams.get("direction");
  const scenario = searchParams.get("scenario");
  const offset = Number(searchParams.get("offset") ?? 0);
  return {
    q: searchParams.get("q") ?? "",
    kind: kind === "tensile" ? "tensile" : "all",
    sort: sort === "updatedAt" || sort === "kind" ? sort : "title",
    direction: direction === "asc" ? "asc" : "desc",
    offset: Number.isFinite(offset) && offset >= 0 ? Math.floor(offset / PAGE_SIZE) * PAGE_SIZE : 0,
    pageSize: PAGE_SIZE,
    scenario: scenarios.includes(scenario as PrototypeScenario) ? (scenario as PrototypeScenario) : "normal",
  };
}

function writeParams(current: URLSearchParams, changes: Record<string, string | number | undefined>): URLSearchParams {
  const next = new URLSearchParams(current);
  for (const [key, value] of Object.entries(changes)) {
    if (value === undefined || value === "") next.delete(key);
    else next.set(key, String(value));
  }
  return next;
}

function resolveUpdater<T>(updater: Updater<T>, current: T): T {
  return typeof updater === "function" ? (updater as (old: T) => T)(current) : updater;
}

export function TestDataReader() {
  const gateway = useReaderGateway();
  const scope = useReaderScope();
  const session = useReaderSession();
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const params = useMemo(() => readParams(searchParams), [searchParams]);
  const pathSelection = location.pathname.startsWith("/test-data/") ? decodeURIComponent(location.pathname.split("/").at(-1) ?? "") : "";
  const requestedSelection = searchParams.get("selection") ?? "";
  const selectionId = pathSelection || requestedSelection;
  const layout = searchParams.get("layout") === "B" ? "B" : "A";
  const resultsView = searchParams.get("view") === "results";

  useEffect(() => {
    if (!pathSelection || !requestedSelection || pathSelection === requestedSelection) return;
    const next = new URLSearchParams(searchParams);
    next.set("selection", pathSelection);
    setSearchParams(next, { replace: true });
  }, [pathSelection, requestedSelection, searchParams, setSearchParams]);

  const [draftQuery, setDraftQuery] = useState(params.q);
  const queryFingerprint = JSON.stringify(params);
  const lastValid = useRef<{ scopeKey: string; queryFingerprint: string; data: ReaderSearchResult<TestDataRecord> } | undefined>(undefined);
  const resultQuery = useQuery({
    queryKey: [scope.mode, scope.actorID, scope.orgID, scope.projectID, scope.effectiveAccessFingerprint, scope.authEpoch, "test-data", params],
    queryFn: async ({ signal }) => {
      try {
        return await gateway.searchTestData(params, signal);
      } catch (error) {
        if (isGatewayError(error) && (error.status === 401 || error.status === 403)) await session.handleAuthFailure(error.status);
        throw error;
      }
    },
    enabled: session.canRead,
    retry: false,
  });
  if (resultQuery.data && session.canRead) lastValid.current = { scopeKey: session.scopeKey, queryFingerprint, data: resultQuery.data };
  const result = lastValid.current?.scopeKey === session.scopeKey && lastValid.current.queryFingerprint === queryFingerprint
    ? (resultQuery.data ?? lastValid.current.data)
    : undefined;
  const selectedQuery = useQuery({
    queryKey: [scope.mode, scope.actorID, scope.orgID, scope.projectID, scope.effectiveAccessFingerprint, scope.authEpoch, "test-data-detail", selectionId, params.scenario],
    queryFn: async ({ signal }) => {
      try {
        return await gateway.getTestData(selectionId, { scenario: params.scenario }, signal);
      } catch (error) {
        if (isGatewayError(error) && (error.status === 401 || error.status === 403)) await session.handleAuthFailure(error.status);
        throw error;
      }
    },
    enabled: Boolean(selectionId) && session.canRead,
    retry: false,
  });

  const selectRecord = (id: string) => {
    const next = writeParams(searchParams, { selection: id, view: undefined });
    navigate(`/test-data/${encodeURIComponent(id)}?${next.toString()}`);
  };
  const returnToResults = () => {
    const next = writeParams(searchParams, { view: "results", selection: selectionId });
    navigate(`/test-data/${encodeURIComponent(selectionId)}?${next.toString()}`);
  };
  const updateReaderParams = (changes: Record<string, string | number | undefined>) => setSearchParams(writeParams(searchParams, changes));
  const selected = selectedQuery.data;
  const visibleSelected = session.canRead && selected?.id === selectionId ? selected : session.canRead ? result?.rows.find((row) => row.id === selectionId) : undefined;
  const listError = resultQuery.error as ReaderGatewayError | null;
  const detailError = selectedQuery.error as ReaderGatewayError | null;

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <h1>Test Data</h1>
        <div className={styles.headerActions}><Link className={styles.adminLink} to="/cards"><FileText size={16} /> Solver Cards</Link></div>
      </header>
      <section className={styles.searchBar} aria-label="Test Data search and controls">
        <form className={styles.searchForm} onSubmit={(event) => { event.preventDefault(); updateReaderParams({ q: draftQuery.trim(), offset: 0 }); }}>
          <label htmlFor="test-data-search" className="sr-only">Search Test Data</label>
          <Search size={17} aria-hidden="true" />
          <input id="test-data-search" value={draftQuery} onChange={(event) => setDraftQuery(event.target.value)} placeholder="Search title, ID, or source" />
          <Button type="submit" size="sm" variant="primary">Search</Button>
        </form>
        <label className={styles.filterLabel}>Kind<select aria-label="Test Data kind" value={params.kind} onChange={(event) => updateReaderParams({ kind: event.target.value, offset: 0 })}><option value="all">All Test Data</option><option value="tensile">Tensile</option></select></label>
        <span className={styles.scopeNote}><SlidersHorizontal size={15} /> {result?.total.toLocaleString() ?? "—"} results</span>
      </section>

      {layout === "B" && selectionId && !resultsView ? <div className={styles.resultsReturn}><Button size="sm" variant="quiet" onClick={returnToResults}><ArrowLeft size={15} /> Results</Button></div> : null}
      {layout === "B" && selectionId && !resultsView ? (
        <div className={styles.layoutB}><DetailPane record={visibleSelected} error={detailError} loading={selectedQuery.isPending} result={result} selectionId={selectionId} onRetry={() => void selectedQuery.refetch()} onOpenCard={(id) => openCard(navigate, id, selectionId, searchParams)} /></div>
      ) : (
        <div className={styles.layoutA}>
          <section className={styles.resultsPane} aria-labelledby="test-data-results-title">
            <div className={styles.sectionHeading}><div><h2 id="test-data-results-title">Results</h2><span>{result?.total.toLocaleString() ?? "—"} items · page {Math.floor(params.offset / PAGE_SIZE) + 1}</span></div></div>
            {!session.canRead ? <ReaderState tone="error" title={session.availability === "session-recovery" ? "Session recovery required" : session.availability === "logged-out" ? "Sign in to read Test Data" : "Library access changed"} description={session.availability === "session-recovery" ? "Your session expired. Return to sign in before reading this result." : session.availability === "logged-out" ? "This reader is paused until a workspace session is restored." : "This result is no longer available in the current library scope."} /> : listError && !result ? <ReaderState tone="error" title={listError.status === 503 ? "Reader unavailable" : "Could not load Test Data"} description={listError.message} onAction={() => void resultQuery.refetch()} /> : resultQuery.isPending && !result ? <ReaderState title="Loading Test Data" description="Reading the current result set…" /> : result?.rows.length === 0 ? <ReaderState tone="empty" title="No Test Data matches" description="Clear the filters or search again." /> : <>{listError ? <p className={styles.staleNotice} role="status">Showing the last valid result. Retry to revalidate.</p> : null}<TestDataTable rows={result?.rows ?? []} total={result?.total ?? 0} params={params} selectionId={selectionId} onSelect={selectRecord} onSort={(sort, direction) => updateReaderParams({ sort, direction, offset: 0 })} onPage={(offset) => updateReaderParams({ offset })} /></>}
          </section>
          <section className={styles.detailPane} aria-labelledby="test-data-detail-title"><DetailPane record={visibleSelected} error={detailError} loading={selectedQuery.isPending} result={result} selectionId={selectionId} onRetry={() => void selectedQuery.refetch()} onOpenCard={(id) => openCard(navigate, id, selectionId, searchParams)} /></section>
        </div>
      )}
    </div>
  );
}

function TestDataTable({ rows, total, params, selectionId, onSelect, onSort, onPage }: {
  rows: TestDataRecord[];
  total: number;
  params: ReaderQueryParams;
  selectionId: string;
  onSelect: (id: string) => void;
  onSort: (sort: "title" | "updatedAt" | "kind", direction: "asc" | "desc") => void;
  onPage: (offset: number) => void;
}) {
  const pagination: PaginationState = { pageIndex: params.offset / params.pageSize, pageSize: params.pageSize };
  const sorting: SortingState = [{ id: params.sort, desc: params.direction === "desc" }];
  const table = useTable({
    features: readerFeatures,
    columns: testDataColumns,
    data: rows,
    state: { sorting, pagination },
    onSortingChange: (updater) => {
      const first = resolveUpdater(updater, sorting)[0];
      if (first && (first.id === "title" || first.id === "updatedAt" || first.id === "kind")) onSort(first.id, first.desc ? "desc" : "asc");
    },
    onPaginationChange: (updater) => onPage(resolveUpdater(updater, pagination).pageIndex * params.pageSize),
    manualSorting: true,
    manualPagination: true,
    enableSortingRemoval: false,
    rowCount: total,
  });
  return <>
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>{table.getHeaderGroups().map((headerGroup) => <tr key={headerGroup.id}>{headerGroup.headers.map((header) => <th key={header.id} scope="col">{header.isPlaceholder ? null : <button className={styles.sortButton} type="button" onClick={() => { if (!header.column.getCanSort()) return; const current = header.column.getIsSorted(); onSort(header.column.id as "title" | "updatedAt" | "kind", current === "asc" ? "desc" : "asc"); }}>{table.FlexRender({ header })}{header.column.getIsSorted() === "asc" ? " ↑" : header.column.getIsSorted() === "desc" ? " ↓" : ""}</button>}</th>)}</tr>)}</thead>
        <tbody>{table.getRowModel().rows.map((row) => <tr key={row.id} className={row.original.id === selectionId ? styles.selectedRow : ""} aria-selected={row.original.id === selectionId}>{row.getAllCells().map((cell) => <td key={cell.id} className={cell.column.id === "id" ? styles.idCell : cell.column.id === "title" ? styles.titleColumn : undefined}>{cell.column.id === "id" ? <button type="button" className={styles.rowSelect} aria-label={`Select ${row.original.title} (${row.original.id})`} title={row.original.title} onClick={() => onSelect(row.original.id)}>{table.FlexRender({ cell })}</button> : table.FlexRender({ cell })}</td>)}</tr>)}</tbody>
      </table>
    </div>
    <div className={styles.pagination}><span>{total === 0 ? "0" : `${params.offset + 1}–${Math.min(params.offset + params.pageSize, total)}`} of {total.toLocaleString()}</span><div><Button size="sm" disabled={params.offset === 0} onClick={() => onPage(Math.max(0, params.offset - params.pageSize))}><ArrowLeft size={14} /> Previous</Button><Button size="sm" disabled={!table.getCanNextPage()} onClick={() => onPage(params.offset + params.pageSize)}>Next <ArrowRight size={14} /></Button></div></div>
  </>;
}

function DetailPane({ record, error, loading, result, selectionId, onRetry, onOpenCard }: {
  record?: TestDataRecord;
  error: ReaderGatewayError | null;
  loading: boolean;
  result?: ReaderSearchResult<TestDataRecord>;
  selectionId: string;
  onRetry: () => void;
  onOpenCard: (id: string) => void;
}) {
  const gateway = useReaderGateway();
  const session = useReaderSession();
  const queryClient = useQueryClient();
  if (!selectionId) return <div className={styles.detailEmpty}><FileText size={26} /><h2 id="test-data-detail-title">Select a Test Data row</h2><p>Conditions, properties, curve and associations appear here.</p></div>;
  if (!session.canRead) return <ReaderState tone="error" title={session.availability === "session-recovery" ? "Session recovery required" : session.availability === "logged-out" ? "Sign in to read this Test Data" : "Library access changed"} description={session.availability === "session-recovery" ? "Return to sign in before reading the selected Test Data." : session.availability === "logged-out" ? "This result is paused until a workspace session is restored." : "Return to the library with an authorized scope before reading this result."} />;
  if (loading && !record) return <div className={styles.detailEmpty}><p>Loading selected Test Data…</p></div>;
  if (error) return <ReaderState tone="error" title={error.status === 404 ? "Selected Test Data unavailable" : error.status === 503 ? "Selected Test Data is stale" : "Could not load selected Test Data"} description={error.message} actionLabel="Retry selected Test Data" onAction={onRetry} />;
  if (!record) return <div className={styles.detailEmpty}><AlertCircle size={25} /><h2 id="test-data-detail-title">Selected object is unavailable</h2><p>{selectionId} could not be read.</p></div>;
  const outsideResult = !result?.rows.some((row) => row.id === record.id);
  return <article className={styles.detail}>
    <div data-testid="test-data-detail-header" className={styles.detailTop}><div className={styles.objectIdentity}><h2 id="test-data-detail-title" title={record.title}>{record.title}</h2><code>{record.id}</code></div><div className={styles.detailTopActions}><StatusTag tone="success">Test Data</StatusTag><RenameDialog currentTitle={record.title} currentDescription={record.description} onApply={async (value) => { await gateway.patchDisplayMetadata("test-data", record.id, value); await queryClient.invalidateQueries({ queryKey: [gateway.mode] }); }} /></div></div>
    {record.metadataApplied ? <p className={styles.appliedNotice} role="status">Display name saved.</p> : null}
    {outsideResult ? <p className={styles.outsideNotice} role="status">This selection is outside the current results.</p> : null}
    <section className={styles.association} aria-labelledby="associated-card-title"><div className={styles.associationHeading}><div><h3 id="associated-card-title">Associated Solver Cards</h3></div>{record.cardIds.length ? <StatusTag tone="info">{record.cardIds.length}</StatusTag> : null}</div>{record.cardIds.length === 0 ? <p className={styles.muted}>No Solver Card is associated.</p> : <div className={styles.cardLinks}>{record.cardIds.map((id) => { const linked = record.associatedCards?.find((card) => card.id === id); return <button type="button" key={id} className={styles.cardLink} onClick={() => onOpenCard(id)}><span><strong title={linked?.title}>{linked?.title ?? "Solver Card"}</strong><small>{id}</small></span><ExternalLink size={16} /></button>; })}</div>}</section>
    <div className={styles.informationGrid}><section className={styles.infoSection} aria-labelledby="test-conditions-title"><h3 id="test-conditions-title">Test conditions</h3><ConditionSummary condition={record.condition} /></section><section className={styles.infoSection} aria-labelledby="reference-properties-title"><PropertyTable rows={record.properties} caption="Reference material properties" /></section></div>
    {record.curve && record.curvePreview ? <CurvePreview definition={record.curve} preview={record.curvePreview} /> : <p className={styles.invalid}>Curve metadata is incomplete; preview is blocked.</p>}
    <details className={styles.sourceDetails}><summary>Source and fixture evidence</summary><div className={styles.summaryGrid}><Summary label="Source" value={`${record.sourceLabel} · ${record.sourceFilename}`} /><Summary label="Point counts" value={`${record.sourcePointCount.toLocaleString()} source · ${record.previewPointCount.toLocaleString()} preview`} /><Summary label="Fixture" value={record.description} /></div></details>
  </article>;
}

function Summary({ label, value }: { label: string; value: string }) { return <div className={styles.summary}><span>{label}</span><strong>{value}</strong></div>; }

function openCard(navigate: ReturnType<typeof useNavigate>, id: string, sourceId: string, searchParams: URLSearchParams) {
  const params = new URLSearchParams();
  for (const key of ["layout", "scenario"]) { const value = searchParams.get(key); if (value) params.set(key, value); }
  params.set("selection", id);
  params.set("from", "test-data");
  params.set("sourceSelection", sourceId);
  const sourceQuery = searchParams.get("q");
  const sourceOffset = searchParams.get("offset");
  const sourceSort = searchParams.get("sort");
  const sourceDirection = searchParams.get("direction");
  if (sourceQuery) params.set("sourceQuery", sourceQuery);
  if (sourceOffset) params.set("sourceOffset", sourceOffset);
  if (sourceSort) params.set("sourceSort", sourceSort);
  if (sourceDirection) params.set("sourceDirection", sourceDirection);
  navigate(`/cards/${encodeURIComponent(id)}?${params.toString()}`);
}
