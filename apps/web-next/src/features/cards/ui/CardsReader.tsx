import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createColumnHelper, rowPaginationFeature, rowSortingFeature, tableFeatures, useTable, type PaginationState, type SortingState, type Updater } from "@tanstack/react-table";
import { AlertCircle, ArrowLeft, ArrowRight, Download, ExternalLink, FileCode2, Search, ShieldAlert } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router";
import { useReaderGateway, useReaderScope, useReaderSession } from "../../../shared/api/ReaderGatewayProvider";
import { isGatewayError, ReaderGatewayError, type ReaderSearchResult, type DownloadArtifact } from "../../../shared/api/reader-gateway";
import { isSolverCardMetadata, type PrototypeScenario, type ReaderQueryParams, type SolverCard } from "../../../shared/model/reader-contracts";
import { Button } from "../../../shared/ui/Button";
import { PropertyTable } from "../../../shared/ui/EngineeringValue";
import { ReaderState } from "../../../shared/ui/ReaderState";
import { RenameDialog } from "../../../shared/ui/RenameDialog";
import { StatusTag } from "../../../shared/ui/StatusTag";
import styles from "./CardsReader.module.css";

const cardFeatures = tableFeatures({ rowSortingFeature, rowPaginationFeature });
const cardColumnHelper = createColumnHelper<typeof cardFeatures, SolverCard>();
const cardColumns = cardColumnHelper.columns([
  cardColumnHelper.accessor("id", { id: "id", header: "ID", cell: (info) => <code>{info.getValue()}</code>, enableSorting: false }),
  cardColumnHelper.accessor("title", { id: "title", header: "Solver Card", cell: (info) => <span className={styles.titleCell} title={info.getValue()}>{info.getValue()}</span> }),
  cardColumnHelper.accessor("mappingStatus", { id: "mappingStatus", header: "Mapping", cell: (info) => <MappingTag status={info.getValue()} />, enableSorting: false }),
]);
const PAGE_SIZE = 50;
const scenarios: PrototypeScenario[] = ["normal", "dense", "empty", "error", "unsupported", "long-name"];

function readParams(searchParams: URLSearchParams): ReaderQueryParams {
  const offset = Number(searchParams.get("offset") ?? 0);
  const scenario = searchParams.get("scenario");
  return {
    q: searchParams.get("q") ?? "",
    kind: "all",
    sort: searchParams.get("sort") === "updatedAt" ? "updatedAt" : "title",
    direction: searchParams.get("direction") === "asc" ? "asc" : "desc",
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

function resolveUpdater<T>(updater: Updater<T>, current: T): T { return typeof updater === "function" ? (updater as (old: T) => T)(current) : updater; }

export function CardsReader() {
  const gateway = useReaderGateway();
  const scope = useReaderScope();
  const session = useReaderSession();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const params = useMemo(() => readParams(searchParams), [searchParams]);
  const pathSelection = location.pathname.startsWith("/cards/") ? decodeURIComponent(location.pathname.split("/").at(-1) ?? "") : "";
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
  const lastValid = useRef<{ scopeKey: string; queryFingerprint: string; data: ReaderSearchResult<SolverCard> } | undefined>(undefined);
  const resultQuery = useQuery({
    queryKey: [scope.mode, scope.actorID, scope.orgID, scope.projectID, scope.effectiveAccessFingerprint, scope.authEpoch, "cards", params],
    queryFn: async ({ signal }) => {
      try { return await gateway.searchCards(params, signal); }
      catch (error) { if (isGatewayError(error) && (error.status === 401 || error.status === 403)) await session.handleAuthFailure(error.status); throw error; }
    },
    enabled: session.canRead,
    retry: false,
  });
  if (resultQuery.data && session.canRead) lastValid.current = { scopeKey: session.scopeKey, queryFingerprint, data: resultQuery.data };
  const result = lastValid.current?.scopeKey === session.scopeKey && lastValid.current.queryFingerprint === queryFingerprint ? (resultQuery.data ?? lastValid.current.data) : undefined;
  const selectedQuery = useQuery({
    queryKey: [scope.mode, scope.actorID, scope.orgID, scope.projectID, scope.effectiveAccessFingerprint, scope.authEpoch, "card-detail", selectionId, params.scenario],
    queryFn: async ({ signal }) => {
      try { return await gateway.getCard(selectionId, { scenario: params.scenario }, signal); }
      catch (error) { if (isGatewayError(error) && (error.status === 401 || error.status === 403)) await session.handleAuthFailure(error.status); throw error; }
    },
    enabled: Boolean(selectionId) && session.canRead,
    retry: false,
  });
  const selected = selectedQuery.data;
  const visibleSelected = session.canRead && selected?.id === selectionId ? selected : session.canRead ? result?.rows.find((row) => row.id === selectionId) : undefined;
  const listError = resultQuery.error as ReaderGatewayError | null;
  const detailError = selectedQuery.error as ReaderGatewayError | null;
  const updateParams = (changes: Record<string, string | number | undefined>) => setSearchParams(writeParams(searchParams, changes));
  const selectCard = (id: string) => navigate(`/cards/${encodeURIComponent(id)}?${writeParams(searchParams, { selection: id, view: undefined }).toString()}`);
  const returnToResults = () => navigate(`/cards/${encodeURIComponent(selectionId)}?${writeParams(searchParams, { selection: selectionId, view: "results" }).toString()}`);
  const openTestData = (id: string) => {
    const next = new URLSearchParams();
    for (const key of ["layout", "scenario"]) { const value = searchParams.get(key); if (value) next.set(key, value); }
    next.set("selection", id); next.set("from", "cards"); next.set("sourceSelection", selectionId);
    const sourceQuery = searchParams.get("q");
    const sourceOffset = searchParams.get("offset");
    if (sourceQuery) next.set("sourceCardQuery", sourceQuery);
    if (sourceOffset) next.set("sourceCardOffset", sourceOffset);
    navigate(`/test-data/${encodeURIComponent(id)}?${next.toString()}`);
  };

  return <div className={styles.page}>
    <header className={styles.pageHeader}><h1>Solver Cards</h1><Link className={styles.backLink} to="/test-data"><ArrowLeft size={16} /> Test Data</Link></header>
    <section className={styles.searchBar} aria-label="Solver Card search and controls"><form className={styles.searchForm} onSubmit={(event) => { event.preventDefault(); updateParams({ q: draftQuery.trim(), offset: 0 }); }}><label htmlFor="card-search" className="sr-only">Search Solver Cards</label><Search size={17} aria-hidden="true" /><input id="card-search" value={draftQuery} onChange={(event) => setDraftQuery(event.target.value)} placeholder="Search card title or ID" /><Button size="sm" type="submit" variant="primary">Search</Button></form><span className={styles.scopeNote}>{result?.total.toLocaleString() ?? "—"} results</span></section>
    {layout === "B" && selectionId && !resultsView ? <div className={styles.resultsReturn}><Button size="sm" variant="quiet" onClick={returnToResults}><ArrowLeft size={15} /> Results</Button></div> : null}
    {layout === "B" && selectionId && !resultsView ? <div className={styles.layoutB}><CardDetail card={visibleSelected} error={detailError} loading={selectedQuery.isPending} result={result} selectionId={selectionId} scenario={params.scenario} onRetry={() => void selectedQuery.refetch()} onOpenTestData={openTestData} /></div> : <div className={styles.layoutA}><section className={styles.resultsPane} aria-labelledby="cards-results-title"><div className={styles.sectionHeading}><div><h2 id="cards-results-title">Results</h2><span>{result?.total.toLocaleString() ?? "—"} items · page {Math.floor(params.offset / PAGE_SIZE) + 1}</span></div></div>{!session.canRead ? <ReaderState tone="error" title={session.availability === "session-recovery" ? "Session recovery required" : session.availability === "logged-out" ? "Sign in to read Solver Cards" : "Library access changed"} description={session.availability === "session-recovery" ? "Your session expired. Return to sign in before reading this card." : session.availability === "logged-out" ? "This reader is paused until a workspace session is restored." : "This result is no longer available in the current library scope."} /> : listError && !result ? <ReaderState tone="error" title="Cards reader unavailable" description={listError.message} onAction={() => void resultQuery.refetch()} /> : resultQuery.isPending && !result ? <ReaderState title="Loading Solver Cards" description="Reading the current result set…" /> : result?.rows.length === 0 ? <ReaderState tone="empty" title="No Solver Cards match" description="Clear the filters or search again." /> : <>{listError ? <p className={styles.staleNotice} role="status">Showing the last valid result. Retry to revalidate.</p> : null}<CardTable rows={result?.rows ?? []} total={result?.total ?? 0} params={params} selectionId={selectionId} onSelect={selectCard} onSort={(sort, direction) => updateParams({ sort, direction, offset: 0 })} onPage={(offset) => updateParams({ offset })} /></>}</section><section className={styles.detailPane}><CardDetail card={visibleSelected} error={detailError} loading={selectedQuery.isPending} result={result} selectionId={selectionId} scenario={params.scenario} onRetry={() => void selectedQuery.refetch()} onOpenTestData={openTestData} /></section></div>}
  </div>;
}

function CardTable({ rows, total, params, selectionId, onSelect, onSort, onPage }: { rows: SolverCard[]; total: number; params: ReaderQueryParams; selectionId: string; onSelect: (id: string) => void; onSort: (sort: "title" | "updatedAt" | "kind", direction: "asc" | "desc") => void; onPage: (offset: number) => void }) {
  const pagination: PaginationState = { pageIndex: params.offset / params.pageSize, pageSize: params.pageSize };
  const sorting: SortingState = [{ id: params.sort, desc: params.direction === "desc" }];
  const table = useTable({
    features: cardFeatures,
    columns: cardColumns,
    data: rows,
    state: { sorting, pagination },
    onSortingChange: (updater) => { const first = resolveUpdater(updater, sorting)[0]; if (first && (first.id === "title" || first.id === "updatedAt" || first.id === "kind")) onSort(first.id, first.desc ? "desc" : "asc"); },
    onPaginationChange: (updater) => onPage(resolveUpdater(updater, pagination).pageIndex * params.pageSize),
    manualSorting: true,
    manualPagination: true,
    enableSortingRemoval: false,
    rowCount: total,
  });
  return <>
    <div className={styles.tableWrap}><table className={styles.table}><thead>{table.getHeaderGroups().map((group) => <tr key={group.id}>{group.headers.map((header) => <th key={header.id} scope="col">{header.isPlaceholder ? null : <button className={styles.sortButton} type="button" onClick={() => { if (!header.column.getCanSort()) return; const current = header.column.getIsSorted(); onSort(header.column.id as "title" | "updatedAt" | "kind", current === "asc" ? "desc" : "asc"); }}>{table.FlexRender({ header })}{header.column.getIsSorted() === "asc" ? " ↑" : header.column.getIsSorted() === "desc" ? " ↓" : ""}</button>}</th>)}</tr>)}</thead><tbody>{table.getRowModel().rows.map((row) => <tr key={row.id} className={row.original.id === selectionId ? styles.selectedRow : ""} aria-selected={row.original.id === selectionId}>{row.getAllCells().map((cell) => <td key={cell.id} className={cell.column.id === "id" ? styles.idCell : cell.column.id === "title" ? styles.titleColumn : undefined}>{cell.column.id === "id" ? <button className={styles.rowSelect} type="button" aria-label={`Select ${row.original.title} (${row.original.id})`} title={row.original.title} onClick={() => onSelect(row.original.id)}>{table.FlexRender({ cell })}</button> : table.FlexRender({ cell })}</td>)}</tr>)}</tbody></table></div>
    <div className={styles.pagination}><span>{total === 0 ? "0" : `${params.offset + 1}–${Math.min(params.offset + params.pageSize, total)}`} of {total.toLocaleString()}</span><div><Button size="sm" disabled={params.offset === 0} onClick={() => onPage(Math.max(0, params.offset - params.pageSize))}><ArrowLeft size={14} /> Previous</Button><Button size="sm" disabled={!table.getCanNextPage()} onClick={() => onPage(params.offset + params.pageSize)}>Next <ArrowRight size={14} /></Button></div></div>
  </>;
}

function CardDetail({ card, error, loading, result, selectionId, scenario, onRetry, onOpenTestData }: { card?: SolverCard; error: ReaderGatewayError | null; loading: boolean; result?: ReaderSearchResult<SolverCard>; selectionId: string; scenario: PrototypeScenario; onRetry: () => void; onOpenTestData: (id: string) => void }) {
  const gateway = useReaderGateway();
  const session = useReaderSession();
  const queryClient = useQueryClient();
  const [acknowledgedCardId, setAcknowledgedCardId] = useState<string | null>(null);
  const [downloadState, setDownloadState] = useState<"idle" | "working" | "done" | "error">("idle");
  const [downloadError, setDownloadError] = useState("");
  const downloadAbortRef = useRef<AbortController | null>(null);
  const scopeKeyRef = useRef(session.scopeKey);
  const cardIdRef = useRef(card?.id ?? selectionId);
  useEffect(() => {
    scopeKeyRef.current = session.scopeKey;
    cardIdRef.current = card?.id ?? selectionId;
    downloadAbortRef.current?.abort();
    setAcknowledgedCardId(null); setDownloadState("idle"); setDownloadError("");
  }, [card?.id, selectionId, session.scopeKey]);
  if (!selectionId) return <div className={styles.detailEmpty}><FileCode2 size={26} /><h2>Select a stored Solver Card</h2><p>Open a card from the task navigation or an associated Test Data record.</p></div>;
  if (!session.canRead) return <ReaderState tone="error" title={session.availability === "session-recovery" ? "Session recovery required" : session.availability === "logged-out" ? "Sign in to read this Solver Card" : "Library access changed"} description={session.availability === "session-recovery" ? "Return to sign in before reading the selected card." : session.availability === "logged-out" ? "This card is paused until a workspace session is restored." : "Return to the library with an authorized scope before reading this card."} />;
  if (loading && !card) return <div className={styles.detailEmpty}><p>Loading selected Solver Card…</p></div>;
  if (error) return <ReaderState tone="error" title={error.status === 404 ? "Selected Solver Card unavailable" : error.status === 503 ? "Selected Solver Card is stale" : "Could not load selected Solver Card"} description={error.message} actionLabel="Retry selected card" onAction={onRetry} />;
  if (!card) return <div className={styles.detailEmpty}><AlertCircle size={25} /><h2>Selected card is unavailable</h2><p>{selectionId} could not be read.</p></div>;
  const metadataValid = isSolverCardMetadata(card);
  const artifactValid = metadataValid && card.nativeBytes instanceof Uint8Array && card.nativeBytes.byteLength === card.nativeByteLength;
  const outputComplete = metadataValid && card.outputStatus === "complete";
  const needsAck = metadataValid && (card.mappingStatus === "approximated" || card.mappingStatus === "ignored");
  const cardId = typeof card.id === "string" && card.id.length > 0 ? card.id : selectionId;
  const canDownload = Boolean(artifactValid && outputComplete && card.mappingStatus !== "unsupported" && (!needsAck || acknowledgedCardId === cardId));
  const cardTitle = typeof card.title === "string" && card.title.trim() ? card.title : `Stored Solver Card ${selectionId}`;
  const cardDescription = typeof card.description === "string" ? card.description : "Card metadata is incomplete.";
  const relatedTestDataIds = metadataValid ? card.testDataIds : [];
  const nativeFileName = metadataValid ? card.nativeFileName : "native artifact unavailable";
  const nativeByteLength = metadataValid ? card.nativeByteLength : 0;
  const nativeSha256 = metadataValid ? card.nativeSha256 : "metadata unavailable";
  const outsideResult = !result?.rows.some((row) => row.id === cardId);
  const applyPatch = async (value: { title: string; description?: string }) => { await gateway.patchDisplayMetadata("card", cardId, value); await queryClient.invalidateQueries({ queryKey: [gateway.mode] }); };
  const download = async () => {
    const requestedCardId = cardId;
    const requestedScopeKey = session.scopeKey;
    const controller = new AbortController();
    downloadAbortRef.current?.abort(); downloadAbortRef.current = controller;
    setDownloadState("working"); setDownloadError("");
    try {
      const artifact: DownloadArtifact = await gateway.downloadCard(requestedCardId, { scenario }, controller.signal);
      if (controller.signal.aborted || scopeKeyRef.current !== requestedScopeKey || cardIdRef.current !== requestedCardId) return;
      if (!metadataValid || !(artifact.bytes instanceof Uint8Array) || typeof artifact.byteLength !== "number" || typeof artifact.sha256 !== "string" || artifact.byteLength !== artifact.bytes.byteLength || artifact.sha256.toUpperCase() !== nativeSha256.toUpperCase()) throw new ReaderGatewayError(503, "ARTIFACT_METADATA_INVALID", "Native artifact metadata could not be verified.");
      const artifactBuffer = artifact.bytes.buffer.slice(artifact.bytes.byteOffset, artifact.bytes.byteOffset + artifact.bytes.byteLength) as ArrayBuffer;
      const blob = new Blob([artifactBuffer], { type: "application/octet-stream" });
      const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = artifact.fileName; anchor.click(); URL.revokeObjectURL(url);
      setDownloadState("done");
    } catch (downloadFailure) {
      if (controller.signal.aborted || scopeKeyRef.current !== requestedScopeKey || cardIdRef.current !== requestedCardId) return;
      if (isGatewayError(downloadFailure) && (downloadFailure.status === 401 || downloadFailure.status === 403)) { await session.handleAuthFailure(downloadFailure.status); return; }
      setDownloadState("error"); setDownloadError(downloadFailure instanceof Error ? downloadFailure.message : "Download is blocked.");
    }
  };
  return <article className={styles.detail}>
    <div className={styles.detailTop}><div className={styles.objectIdentity}><h2 title={cardTitle}>{cardTitle}</h2><code>{cardId}</code></div><div className={styles.detailTopActions}><MappingTag status={metadataValid ? card.mappingStatus : undefined} /><Button variant="primary" disabled={!canDownload || downloadState === "working"} onClick={() => void download()}><Download size={16} />{downloadState === "working" ? "Preparing…" : "Download native card"}</Button><RenameDialog currentTitle={cardTitle} currentDescription={cardDescription} onApply={applyPatch} /></div></div>
    {card.metadataApplied ? <p className={styles.appliedNotice} role="status">Display name saved.</p> : null}
    {outsideResult ? <p className={styles.outsideNotice} role="status">This selection is outside the current results.</p> : null}
    <p className={styles.mappingImplication}>{metadataValid ? card.mappingNote : "Mapping metadata is unavailable."}</p>
    <section className={styles.propertiesSection} aria-labelledby="card-properties-title">{metadataValid ? <PropertyTable rows={card.properties} caption="Stored card properties" /> : <p className={styles.invalid} role="alert">Card properties are unavailable until metadata is validated.</p>}</section>
    <section className={styles.nativeSection} aria-labelledby="native-preview-title"><div className={styles.nativeHeading}><div><h3 id="native-preview-title">Native preview</h3></div><StatusTag tone={outputComplete ? "success" : "error"}>{outputComplete ? "Output complete" : "Output incomplete"}</StatusTag></div>{artifactValid && card.nativeBytes instanceof Uint8Array ? <pre data-testid="native-preview" className={styles.nativePreview}><code>{new TextDecoder().decode(card.nativeBytes)}</code></pre> : <p className={styles.invalid} role="alert">Native preview is unavailable until the card artifact passes validation.</p>}</section>
    {needsAck ? <label className={styles.acknowledge}><input type="checkbox" checked={acknowledgedCardId === cardId} onChange={(event) => setAcknowledgedCardId(event.target.checked ? cardId : null)} /> I acknowledge the approximation for this exact card ID ({cardId}).</label> : null}
    {!metadataValid || !artifactValid || card.mappingStatus === "unsupported" || card.outputStatus !== "complete" ? <div className={styles.blocked} role="alert"><ShieldAlert size={18} /><span>{!metadataValid || !artifactValid ? "Download blocked until card metadata and native bytes are validated." : "Download blocked until required mapping and complete output are available."}</span></div> : null}
    <div className={styles.downloadRow}>{downloadState === "done" ? <span className={styles.successText} role="status">Downloaded {nativeFileName} · SHA verified.</span> : null}{downloadState === "error" ? <span className={styles.errorText} role="alert">{downloadError}</span> : null}</div>
    <details className={styles.evidence}><summary>Evidence details</summary><div className={styles.summaryGrid}><Summary label="Native file" value={`${nativeFileName} · ${nativeByteLength.toLocaleString()} bytes`} /><Summary label="SHA-256" value={nativeSha256} /><Summary label="Mapping status" value={metadataValid ? card.mappingStatus.replaceAll("_", " ") : "mapping unavailable"} /></div></details>
    <section className={styles.association} aria-labelledby="card-test-data-title"><div className={styles.associationHeading}><div><h3 id="card-test-data-title">Associated Test Data</h3></div></div><div className={styles.links}>{relatedTestDataIds.map((id) => { const linked = Array.isArray(card.associatedTestData) ? card.associatedTestData.find((item) => item.id === id) : undefined; return <button className={styles.objectLink} key={id} type="button" onClick={() => onOpenTestData(id)}><span><strong title={linked?.title}>{linked?.title ?? "Test Data"}</strong><small>{id}</small></span><ExternalLink size={16} /></button>; })}</div></section>
  </article>;
}

function Summary({ label, value }: { label: string; value: string }) { return <div className={styles.summary}><span>{label}</span><strong>{value}</strong></div>; }
function MappingTag({ status }: { status: SolverCard["mappingStatus"] | undefined }) { const tone = status === "exact" ? "success" : status === "unsupported" ? "error" : status === "approximated" || status === "ignored" ? "warning" : "info"; return <StatusTag tone={tone}>{status ? status.replaceAll("_", " ") : "mapping unavailable"}</StatusTag>; }
