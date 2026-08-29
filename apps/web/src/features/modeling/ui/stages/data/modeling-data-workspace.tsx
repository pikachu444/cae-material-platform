import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import {
  listTestRunsForMaterialState,
} from "../../../../test-data";
import {
  type ApiConfig,
} from "../../../../../shared/api";
import { ModelingWorkspaceLayout } from "../../../../../design/modeling-workspace-layout";
import type { ObservedCurveInput } from "../../../../../engineering-curve-plot";
import type {
  MaterialResponse,
  MaterialStateResponse,
} from "../../../../materials/contracts";
import type {
  CanonicalTestDataDocumentResponse,
  TestRunResponse,
} from "../../../../test-data/contracts";
import type { CommonProcessingPreview } from "../../../model/common-processing-contracts";
import type { ModelingSessionRecordRef } from "../../../model/session-controller";
import { ModelingDataIntake, type ModelingDataLayoutMode } from "./modeling-data-intake";
import {
  buildModelingDataLibraryRows,
  filterModelingDataLibraryRows,
  modelingDataFacetValues,
  modelingDataGraphTitle,
  MODELING_DATA_PAGE_SIZE,
} from "./modeling-data-library-model";
import { ModelingDataRelated } from "./modeling-data-related";

type ModelingDataSource = "library" | "import";
const MODELING_DATA_COMPARISON_LIMIT = 5;

interface ModelingDataWorkspaceProps {
  config: ApiConfig;
  material?: MaterialResponse;
  state?: MaterialStateResponse;
  documents: CanonicalTestDataDocumentResponse[];
  emptySession?: boolean;
  selectedTestDataRefs: ModelingSessionRecordRef[];
  selectedDocumentId: string;
  includedDocumentIds: string[];
  comparisonDocumentIds: string[];
  comparisonMode?: boolean;
  visibleDocumentKeys: string[];
  processingMappingProfileText: string;
  plot: ReactNode;
  technicalDetails?: ReactNode;
  ribbonOpen: boolean;
  onRibbonOpenChange: (open: boolean) => void;
  onSelectDocument: (id: string, revisionId?: string) => void;
  onToggleComparison: (id: string) => void;
  onComparisonModeChange?: (open: boolean) => void;
  onPreviewDocument: (document: Record<string, unknown>, preview: CommonProcessingPreview) => void;
  onImported: (document: CanonicalTestDataDocumentResponse) => void;
  onObservedCurves: (curves: ObservedCurveInput[]) => void;
  onContinue: () => void;
}

function clampPage(page: number, rowCount: number): number {
  return Math.max(0, Math.min(page, Math.max(0, Math.ceil(rowCount / MODELING_DATA_PAGE_SIZE) - 1)));
}

function moveBrowserTreeFocus(event: KeyboardEvent<HTMLDivElement>): void {
  if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
  const items = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="treeitem"]')];
  if (!items.length) return;
  const current = Math.max(0, items.indexOf(document.activeElement as HTMLButtonElement));
  const next = event.key === "Home"
    ? 0
    : event.key === "End"
      ? items.length - 1
      : event.key === "ArrowDown"
        ? Math.min(items.length - 1, current + 1)
        : Math.max(0, current - 1);
  event.preventDefault();
  items[next]?.focus();
}

export function ModelingDataWorkspace({
  config,
  material,
  state,
  documents,
  emptySession = false,
  selectedTestDataRefs,
  selectedDocumentId,
  includedDocumentIds,
  comparisonDocumentIds,
  comparisonMode: controlledComparisonMode,
  visibleDocumentKeys,
  processingMappingProfileText,
  plot,
  technicalDetails,
  ribbonOpen,
  onRibbonOpenChange,
  onSelectDocument,
  onToggleComparison,
  onComparisonModeChange,
  onPreviewDocument,
  onImported,
  onObservedCurves,
  onContinue,
}: ModelingDataWorkspaceProps) {
  const stableConfig = useMemo<ApiConfig>(() => ({
    baseUrl: config.baseUrl,
    accessToken: config.accessToken,
  }), [config.accessToken, config.baseUrl]);
  const [source, setSource] = useState<ModelingDataSource>(emptySession ? "import" : "library");
  const [layoutMode, setLayoutMode] = useState<ModelingDataLayoutMode>("compact");
  const [testRuns, setTestRuns] = useState<TestRunResponse[]>([]);
  const [testRunError, setTestRunError] = useState("");
  const [testRunAttempt, setTestRunAttempt] = useState(0);
  const [draftQuery, setDraftQuery] = useState("");
  const [query, setQuery] = useState("");
  const [testType, setTestType] = useState("");
  const [condition, setCondition] = useState("");
  const [page, setPage] = useState(0);
  const [internalComparisonMode, setInternalComparisonMode] = useState(false);
  const comparisonMode = controlledComparisonMode ?? internalComparisonMode;

  useEffect(() => {
    if (emptySession) setSource("import");
  }, [emptySession]);

  useEffect(() => {
    if (!state || !stableConfig.accessToken) {
      setTestRuns([]);
      return;
    }
    let active = true;
    setTestRunError("");
    void listTestRunsForMaterialState(stableConfig, state.material_state_id)
      .then((result) => {
        if (active) setTestRuns(result.data.items);
      })
      .catch(() => {
        if (active) setTestRunError("Test Run details could not be loaded.");
      });
    return () => { active = false; };
  }, [stableConfig, state, testRunAttempt]);

  const rows = useMemo(
    () => buildModelingDataLibraryRows(documents, selectedTestDataRefs, testRuns, material),
    [documents, material, selectedTestDataRefs, testRuns],
  );
  const facets = useMemo(() => modelingDataFacetValues(rows), [rows]);
  const rowsForBrowser = useMemo(
    () => filterModelingDataLibraryRows(rows, { query, testType: "", condition }),
    [condition, query, rows],
  );
  const filteredRows = useMemo(
    () => filterModelingDataLibraryRows(rows, { query, testType, condition }),
    [condition, query, rows, testType],
  );
  const pageCount = Math.max(1, Math.ceil(filteredRows.length / MODELING_DATA_PAGE_SIZE));
  const currentPage = clampPage(page, filteredRows.length);
  const pageRows = filteredRows.slice(
    currentPage * MODELING_DATA_PAGE_SIZE,
    (currentPage + 1) * MODELING_DATA_PAGE_SIZE,
  );
  const refsById = useMemo(
    () => new Map(selectedTestDataRefs.map((ref) => [ref.id, ref])),
    [selectedTestDataRefs],
  );
  const selectedRef = refsById.get(selectedDocumentId);
  const selectedRow = rows.find((row) => row.document.test_data_document_id === selectedDocumentId
    && (!selectedRef || row.revisionId === selectedRef.revisionId));
  const hasCurrentInput = Boolean(selectedRow
    && includedDocumentIds.includes(selectedRow.document.test_data_document_id));
  const materialLabel = rows[0]?.materialLabel
    || material?.current_revision.content.name
    || "Current material";
  const comparisonLimitReached = 1 + comparisonDocumentIds.length >= MODELING_DATA_COMPARISON_LIMIT;
  const testTypeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const row of rowsForBrowser) counts.set(row.testType, (counts.get(row.testType) ?? 0) + 1);
    return [...counts.entries()].sort(([left], [right]) => left.localeCompare(right));
  }, [rowsForBrowser]);
  const selectedTestTypeInBrowser = testTypeCounts.some(([label]) => label === testType);

  useEffect(() => {
    setPage((current) => clampPage(current, filteredRows.length));
  }, [filteredRows.length]);

  useEffect(() => {
    if (!selectedRow) return;
    const index = filteredRows.findIndex((row) => row.key === selectedRow.key);
    if (index >= 0) setPage(Math.floor(index / MODELING_DATA_PAGE_SIZE));
  }, [filteredRows, selectedRow]);

  function applySearch(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setQuery(draftQuery);
    setPage(0);
  }

  function selectSource(next: ModelingDataSource): void {
    setSource(next);
    if (next === "library") setLayoutMode("compact");
  }

  function toggleComparisonMode(): void {
    const next = !comparisonMode;
    if (controlledComparisonMode === undefined) setInternalComparisonMode(next);
    onComparisonModeChange?.(next);
  }

  const navigator = source === "library" ? (
    <div className={`modeling-data-browser${selectedRow ? " has-related" : ""}`}>
      <form className="modeling-data-search" role="search" onSubmit={applySearch}>
        <label htmlFor="modeling-test-data-query">Find Test Data</label>
        <div>
          <input
            id="modeling-test-data-query"
            name="modeling-test-data-query"
            type="search"
            autoComplete="off"
            value={draftQuery}
            onChange={(event) => setDraftQuery(event.target.value)}
          />
          <button type="submit" className="text-button">Find</button>
        </div>
      </form>
      <div className="modeling-data-filters">
        <label htmlFor="modeling-test-type-filter">Test type</label>
        <select
          id="modeling-test-type-filter"
          name="modeling-test-type-filter"
          value={testType}
          onChange={(event) => { setTestType(event.target.value); setPage(0); }}
        >
          <option value="">All tests</option>
          {facets.testTypes.map((value) => <option key={value}>{value}</option>)}
        </select>
        <label htmlFor="modeling-test-condition-filter">Condition</label>
        <select
          id="modeling-test-condition-filter"
          name="modeling-test-condition-filter"
          value={condition}
          onChange={(event) => { setCondition(event.target.value); setPage(0); }}
        >
          <option value="">All conditions</option>
          {facets.conditions.map((value) => <option key={value}>{value}</option>)}
        </select>
      </div>
      {testRunError ? (
        <div className="modeling-data-filter-error" role="alert">
          <span>{testRunError}</span>
          <button type="button" className="text-button" onClick={() => setTestRunAttempt((current) => current + 1)}>Retry</button>
        </div>
      ) : null}
      <section className="modeling-data-tree" aria-labelledby="modeling-data-browser-heading">
        <div className="modeling-data-rail-heading">
          <h3 id="modeling-data-browser-heading">Browser</h3>
          <span>{rowsForBrowser.length.toLocaleString()}</span>
        </div>
        <div role="tree" aria-label="Test Data by material and test type" onKeyDown={moveBrowserTreeFocus}>
          <button
             type="button"
             role="treeitem"
             aria-level={1}
              aria-label={`${materialLabel}, ${rowsForBrowser.length.toLocaleString()} Test Data records`}
              aria-selected={!testType}
             tabIndex={!testType || !selectedTestTypeInBrowser ? 0 : -1}
            className={!testType ? "active root" : "root"}
            onClick={() => { setTestType(""); setPage(0); }}
          >
            <span>{materialLabel}</span><span>{rowsForBrowser.length.toLocaleString()}</span>
          </button>
          {testTypeCounts.map(([label, count]) => (
            <button
               type="button"
               role="treeitem"
               aria-level={2}
               aria-label={`${label}, ${count.toLocaleString()} Test Data records`}
               aria-selected={testType === label}
               tabIndex={testType === label ? 0 : -1}
              className={testType === label ? "active child" : "child"}
              key={label}
              onClick={() => { setTestType(label); setPage(0); }}
            >
              <span>{label}</span><span>{count.toLocaleString()}</span>
            </button>
          ))}
        </div>
      </section>
      {selectedRow ? (
        <div className="modeling-data-related-slot">
          <ModelingDataRelated
            config={stableConfig}
            documentId={selectedRow.document.test_data_document_id}
            revisionId={selectedRow.revisionId}
            label={selectedRow.recordLabel}
          />
        </div>
      ) : null}
    </div>
  ) : undefined;

  const resultStart = filteredRows.length ? currentPage * MODELING_DATA_PAGE_SIZE + 1 : 0;
  const resultEnd = Math.min(filteredRows.length, (currentPage + 1) * MODELING_DATA_PAGE_SIZE);
  const libraryContent = (
    <section className="modeling-data-results" aria-labelledby="modeling-data-results-heading">
      <div className="modeling-data-results-heading">
        <h3 id="modeling-data-results-heading">Test Data</h3>
        <span aria-live="polite">{filteredRows.length.toLocaleString()} results</span>
      </div>
      <div className="modeling-data-results-scroll" role="region" aria-label="Test Data results" tabIndex={0}>
        <table>
          <thead>
            <tr>
               {comparisonMode ? <th className="modeling-data-compare-column">Graph</th> : null}
               <th className="modeling-data-record-column">Test record</th>
               <th className="modeling-data-material-column">Material</th>
               <th className="modeling-data-condition-column">Condition</th>
               <th className="modeling-data-date-column">Test date</th>
               <th className="modeling-data-points-column numeric">Data points</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row) => {
              const exactRef = refsById.get(row.document.test_data_document_id);
              const active = selectedDocumentId === row.document.test_data_document_id
                && (!exactRef || exactRef.revisionId === row.revisionId);
              const compared = comparisonDocumentIds.includes(row.document.test_data_document_id)
                && exactRef?.revisionId === row.revisionId;
              return (
                 <tr
                   className={active ? "active" : ""}
                   data-document-key={row.document.document_key}
                   data-revision-id={row.revisionId}
                   key={row.key}
                 >
                  {comparisonMode ? (
                    <td className="modeling-data-compare-column">
                      {active ? <span className="modeling-data-primary-label">Input</span> : <label>
                        <input
                          type="checkbox"
                          name="modeling-data-comparison"
                          value={row.key}
                          aria-label={`${compared ? "Remove" : "Add"} ${row.recordLabel} ${compared ? "from" : "to"} comparison`}
                          checked={compared}
                          disabled={!compared && comparisonLimitReached}
                          onChange={() => onToggleComparison(row.document.test_data_document_id)}
                        />
                        <span className="visually-hidden">Compare {row.recordLabel}</span>
                      </label>}
                    </td>
                  ) : null}
                  <td>
                     <button type="button" className="modeling-data-record-button" aria-current={active ? "true" : undefined} onClick={() => onSelectDocument(row.document.test_data_document_id, row.revisionId)}>
                      <span>{row.recordLabel}</span>
                      {row.historical ? <small>Earlier saved version</small> : null}
                    </button>
                  </td>
                   <td>{row.materialLabel}</td>
                  <td>{row.conditionLabel}</td>
                  <td><time dateTime={row.historical ? undefined : row.document.test_date}>{row.testDateLabel}</time></td>
                  <td className="numeric">{row.pointCount === null ? "\u2014" : row.pointCount.toLocaleString()}</td>
                </tr>
              );
            })}
             {!pageRows.length ? <tr><td colSpan={comparisonMode ? 6 : 5} className="modeling-data-empty-result">No Test Data matches the current search.</td></tr> : null}
          </tbody>
        </table>
      </div>
      <footer className="modeling-data-pagination">
         <span>{resultStart.toLocaleString()}{"\u2013"}{resultEnd.toLocaleString()} of {filteredRows.length.toLocaleString()}</span>
        <div>
           <button type="button" aria-label="Previous Test Data page" disabled={currentPage === 0} onClick={() => setPage((current) => Math.max(0, current - 1))}>{"\u2039"}</button>
          <span>Page {currentPage + 1} of {pageCount}</span>
           <button type="button" aria-label="Next Test Data page" disabled={currentPage >= pageCount - 1} onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))}>{"\u203a"}</button>
        </div>
      </footer>
    </section>
  );

  const plotSurface = (
    <article className="persistent-modeling-plot modeling-data-plot" id="modeling-fit">
      <div className="section-heading">
        <div className="modeling-data-plot-heading">
          <h2>{modelingDataGraphTitle(selectedRow)}</h2>
          {selectedRow ? <span>{selectedRow.materialLabel} · {selectedRow.recordLabel}</span> : null}
        </div>
        {hasCurrentInput ? <button
          type="button"
          className="text-button modeling-data-comparison-action"
          aria-pressed={comparisonMode}
          onClick={toggleComparisonMode}
        >
          {comparisonMode ? "Close comparison" : "Add comparison"}
        </button> : null}
      </div>
      {comparisonMode && comparisonLimitReached ? (
        <p className="modeling-data-comparison-limit" role="status">Remove one curve before adding another.</p>
      ) : null}
      {plot}
      <footer className="modeling-data-plot-actions">
        {hasCurrentInput ? <button type="button" className="button primary" onClick={onContinue}>Continue to Process</button> : null}
      </footer>
    </article>
  );

  return (
    <div className={`modeling-data-workspace source-${source} layout-${layoutMode}`}>
      <div className="data-source-tabs modeling-data-workspace-tabs" role="tablist" aria-label="Test data source">
        <button type="button" role="tab" aria-selected={source === "library"} onClick={() => selectSource("library")}>Library</button>
        <button type="button" role="tab" aria-selected={source === "import"} onClick={() => selectSource("import")}>Local file</button>
      </div>
      <ModelingWorkspaceLayout
        navigator={navigator}
        ribbon={(
          <ModelingDataIntake
            config={stableConfig}
            material={material}
            state={state}
            documents={documents}
            emptySession={emptySession}
            selectedTestDataRefs={selectedTestDataRefs}
            selectedDocumentId={selectedDocumentId}
            visibleDocumentKeys={visibleDocumentKeys}
            processingMappingProfileText={processingMappingProfileText}
            source={source}
            showSourceTabs={false}
            testRuns={testRuns}
            libraryContent={libraryContent}
            onSourceChange={selectSource}
            onSelectDocument={onSelectDocument}
            onPreviewDocument={onPreviewDocument}
            onImported={(document) => { onImported(document); selectSource("library"); }}
            onObservedCurves={onObservedCurves}
            onLayoutModeChange={setLayoutMode}
          />
        )}
        plot={plotSurface}
        dataLayoutMode={layoutMode}
        ribbonOpen={ribbonOpen}
        onRibbonOpenChange={onRibbonOpenChange}
      />
      {technicalDetails ? (
        <details className="modeling-data-technical-details">
          <summary>Technical details</summary>
          <div>{technicalDetails}</div>
        </details>
      ) : null}
    </div>
  );
}
