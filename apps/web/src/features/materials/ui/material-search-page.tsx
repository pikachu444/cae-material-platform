import { lazy, Suspense, type ReactNode, useState } from "react";

import {
  type ApiConfig,
} from "../../../shared/api";
import type { CatalogDataCategory } from "../../../types";
import { CATALOG_DATA_CATEGORIES } from "../../../catalog-data-categories";
import { MaterialsScrollRegion } from "../../../materials-scroll-rail";
import { ResizableSplitPane } from "../../../design/resizable-split-pane";
import { EngineeringColumnResizeHandle } from "../../../design/engineering-column-resize-handle";
import { EngineeringIcon } from "../../../design/icon";
import { useMaterialsSearchController } from "../controller/use-materials-search-controller";

const materialsBrowseTreeModule = import("../../../materials-browse-tree");
const MaterialsBrowseTree = lazy(() =>
  materialsBrowseTreeModule.then((module) => ({
    default: module.MaterialsBrowseTree,
  })),
);

interface Props {
  config: ApiConfig;
  onNavigate: (path: string) => void;
  locationSearch?: string;
}

function familyLabel(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase();
  if (normalized === "metal") return "Metal";
  if (normalized === "polymer") return "Polymer";
  if (normalized === "elastomer") return "Elastomer";
  return value?.trim() || "Unclassified";
}

function domainKindLabel(kind: string | null | undefined): string {
  if (!kind) return "Record";
  const labels: Record<string, string> = {
    material: "Material",
    material_state: "Material State",
    test_data: "Test Data",
    processing_output: "Processed curve",
    material_model: "Selected model",
    neutral_material: "Solver-neutral material",
    neutral_solver_card: "Solver card",
    solver_card: "Solver card",
  };
  return labels[kind] ?? kind.replaceAll("_", " ");
}

export function MaterialSearchPage({
  config,
  onNavigate,
  locationSearch,
}: Props) {
  const controller = useMaterialsSearchController(
    config,
    onNavigate,
    locationSearch,
  );
  const {
    browseResults,
    browseSelection,
    changeScope,
    changeScopeAvailability,
    changeSort,
    clearComparison,
    clearFilters,
    clearSearch,
    compareIds,
    comparedMaterials,
    draftQuery,
    error,
    evidenceSource,
    evidenceSourceFacets,
    familyFacets,
    leftMode,
    loading,
    materialClass,
    materials,
    offset,
    openBrowseTree,
    openExactRecord,
    openMaterial,
    provider,
    providerFacets,
    requestedRecord,
    retry,
    selectedId,
    selectBrowseRecord,
    selectBrowseResult,
    setBrowseResults,
    setDraftQuery,
    setEvidenceSource,
    setLeftMode,
    setMaterialClass,
    setOffset,
    setProvider,
    sortDirection,
    sortKey,
    submit,
    toggleCompare,
    totalCount,
  } = controller;
  const [columnWidths, setColumnWidths] = useState({
    compare: 68,
    material: 260,
    code: 150,
    materialClass: 160,
    summary: 210,
  });

  function sortIndicator(column: "name" | "material_class"): ReactNode {
    if (sortKey !== column) return null;
    return (
      <EngineeringIcon
        name={
          sortDirection === "ascending" ? "sort-ascending" : "sort-descending"
        }
      />
    );
  }

  const navigator = (
    <aside className="materials-left-pane" aria-label="Materials navigator">
      <nav
        className="materials-navigator-modes"
        aria-label="Materials navigator modes"
      >
        <button
          type="button"
          className={leftMode === "browse" ? "active" : ""}
          aria-current={leftMode === "browse" ? "page" : undefined}
          onClick={() => openBrowseTree(undefined)}
        >
          Browse
        </button>
        <button
          type="button"
          className={leftMode === "filters" ? "active" : ""}
          aria-current={leftMode === "filters" ? "page" : undefined}
          onClick={() => setLeftMode("filters")}
        >
          Filters
        </button>
        <button
          type="button"
          className={leftMode === "subsets" ? "active" : ""}
          aria-current={leftMode === "subsets" ? "page" : undefined}
          onClick={() => setLeftMode("subsets")}
        >
          Subsets
        </button>
      </nav>
      {leftMode === "filters" ? (
        <div className="materials-filters">
          <label className="ux-field">
            Material class
            <select
              className="ux-select"
              name="material-class"
              value={materialClass}
              onChange={(event) => setMaterialClass(event.target.value)}
            >
              <option value="">All classes</option>
              {familyFacets.map((facet) => (
                <option
                  key={facet.material_class}
                  value={facet.material_class}
                >{`${familyLabel(facet.material_class)} (${facet.count.toLocaleString()})`}</option>
              ))}
            </select>
          </label>
          <label className="ux-field">
            Provider
            <select
              className="ux-select"
              name="provider"
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
            >
              <option value="">All providers</option>
              {providerFacets.map((facet) => (
                <option
                  key={facet.provider}
                  value={facet.provider}
                >{`${facet.provider} (${facet.count.toLocaleString()})`}</option>
              ))}
            </select>
          </label>
          <label className="ux-field">
            Evidence source
            <select
              className="ux-select"
              name="evidence-source"
              value={evidenceSource}
              onChange={(event) => setEvidenceSource(event.target.value)}
            >
              <option value="">All sources</option>
              {evidenceSourceFacets.map((facet) => (
                <option
                  key={facet.evidence_source}
                  value={facet.evidence_source}
                >{`${facet.evidence_source} (${facet.count.toLocaleString()})`}</option>
              ))}
            </select>
          </label>
          <button
            className="ux-button tertiary"
            type="button"
            onClick={clearFilters}
          >
            Clear filters
          </button>
        </div>
      ) : (
        <Suspense
          fallback={<p className="loading-state">Loading Browse tree…</p>}
        >
          <MaterialsBrowseTree
            config={config}
            subsetMode={leftMode === "subsets"}
            publishedOnly
            requestedRecord={requestedRecord}
            onSelectRecord={selectBrowseRecord}
            onOpenRecord={openExactRecord}
            onScopeChange={changeScope}
            onScopeAvailabilityChange={changeScopeAvailability}
            onResultsChange={
              leftMode === "browse" ? setBrowseResults : undefined
            }
          />
        </Suspense>
      )}
    </aside>
  );

  const results = (
    <section
      className="materials-results"
      aria-labelledby="material-results-title"
      aria-busy={loading}
    >
      <div className="materials-results-header">
        <div>
          <h2 id="material-results-title">Materials</h2>
          <p className="ux-meta">
            {loading
              ? "Loading…"
              : `${totalCount ? `${offset + 1}–${Math.min(offset + materials.length, totalCount)} of ` : ""}${new Intl.NumberFormat().format(totalCount)} matches`}
          </p>
        </div>
      </div>
      {error ? (
        <div className="ux-notice error" role="alert">
          {error}
          <button className="ux-button tertiary" type="button" onClick={retry}>
            Retry
          </button>
        </div>
      ) : null}
      {!loading && !error && !materials.length ? (
        <div className="ux-empty">
          <strong>No materials match this search.</strong>
          <p>Clear the search to return to the available Materials.</p>
          <button
            className="ux-button tertiary"
            type="button"
            onClick={clearSearch}
          >
            Clear search
          </button>
        </div>
      ) : null}
      {comparedMaterials.length > 1 ? (
        <div className="material-compare-strip">
          <strong>Comparing {comparedMaterials.length} materials</strong>
          {comparedMaterials.map((material) => (
            <dl key={material.material_id}>
              <dt>{material.name}</dt>
              <dd>{material.material_family ?? material.material_class}</dd>
              <dd>r{material.record_revision_no}</dd>
            </dl>
          ))}
          <button
            className="ux-button tertiary"
            type="button"
            onClick={clearComparison}
          >
            Clear comparison
          </button>
        </div>
      ) : null}
      {browseSelection ? (
        <div className="browse-selection-bar">
          <span>
            <strong>
              {browseSelection.record.current_revision.content.name}
            </strong>
            <small>
              {domainKindLabel(browseSelection.graph.root.domain_binding?.kind)}{" "}
              · exact revision{" "}
              {browseSelection.record.current_revision.revision_no}
            </small>
          </span>
          <button
            className="ux-button tertiary"
            type="button"
            onClick={() => openExactRecord(browseSelection.record)}
          >
            Open datasheet
          </button>
        </div>
      ) : null}
      <MaterialsScrollRegion
        id="materials-result-scroll"
        className="materials-result-table-wrap"
        shellClassName="materials-result-scroll-shell"
        aria-label="Scrollable material results"
      >
        {materials.length ? (
          <table
            className="materials-result-table material-search-result-table"
            aria-label="Material results"
          >
            <colgroup>
              {Object.entries(columnWidths).map(([key, width]) => (
                <col key={key} style={{ width }} />
              ))}
            </colgroup>
            <thead>
              <tr>
                <th>
                  Compare
                  <EngineeringColumnResizeHandle
                    label="Compare"
                    width={columnWidths.compare}
                    min={60}
                    max={100}
                    onChange={(width) =>
                      setColumnWidths((current) => ({
                        ...current,
                        compare: width,
                      }))
                    }
                  />
                </th>
                <th aria-sort={sortKey === "name" ? sortDirection : undefined}>
                  <button type="button" onClick={() => changeSort("name")}>
                    Material {sortIndicator("name")}
                  </button>
                  <EngineeringColumnResizeHandle
                    label="Material"
                    width={columnWidths.material}
                    min={180}
                    max={420}
                    onChange={(width) =>
                      setColumnWidths((current) => ({
                        ...current,
                        material: width,
                      }))
                    }
                  />
                </th>
                <th>
                  Material code
                  <EngineeringColumnResizeHandle
                    label="Material code"
                    width={columnWidths.code}
                    min={110}
                    max={260}
                    onChange={(width) =>
                      setColumnWidths((current) => ({
                        ...current,
                        code: width,
                      }))
                    }
                  />
                </th>
                <th
                  aria-sort={
                    sortKey === "material_class" ? sortDirection : undefined
                  }
                >
                  <button
                    type="button"
                    onClick={() => changeSort("material_class")}
                  >
                    Family {sortIndicator("material_class")}
                  </button>
                  <EngineeringColumnResizeHandle
                    label="Family"
                    width={columnWidths.materialClass}
                    min={120}
                    max={280}
                    onChange={(width) =>
                      setColumnWidths((current) => ({
                        ...current,
                        materialClass: width,
                      }))
                    }
                  />
                </th>
                <th>
                  Description
                  <EngineeringColumnResizeHandle
                    label="Description"
                    width={columnWidths.summary}
                    min={160}
                    max={420}
                    onChange={(width) =>
                      setColumnWidths((current) => ({
                        ...current,
                        summary: width,
                      }))
                    }
                  />
                </th>
              </tr>
            </thead>
            <tbody>
              {materials.map((material) => {
                return (
                  <tr
                    key={material.material_id}
                    className={
                      selectedId === material.material_id ? "selected" : ""
                    }
                    tabIndex={0}
                    aria-selected={selectedId === material.material_id}
                    onClick={() => openMaterial(material)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") openMaterial(material);
                    }}
                  >
                    <td>
                      <input
                        type="checkbox"
                        aria-label={`Compare ${material.name}`}
                        checked={compareIds.has(material.material_id)}
                        disabled={
                          !compareIds.has(material.material_id) &&
                          compareIds.size >= 3
                        }
                        onClick={(event) => event.stopPropagation()}
                        onChange={() => toggleCompare(material.material_id)}
                      />
                    </td>
                    <td>
                      <button
                        className="material-result-name"
                        type="button"
                        aria-current={
                          selectedId === material.material_id
                            ? "true"
                            : undefined
                        }
                        title={material.name}
                        onClick={(event) => {
                          event.stopPropagation();
                          openMaterial(material);
                        }}
                      >
                        <span>{material.name}</span>
                      </button>
                    </td>
                    <td>{material.material_code ?? "—"}</td>
                    <td title={material.material_class}>
                      {familyLabel(material.material_class)}
                    </td>
                    <td>{material.description ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : null}
      </MaterialsScrollRegion>
      {!loading && totalCount > materials.length ? (
        <nav
          className="materials-pagination"
          aria-label="Material result pages"
        >
          <button
            className="ux-button tertiary"
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 50))}
          >
            Previous
          </button>
          <span className="ux-meta">
            Rows {totalCount ? offset + 1 : 0}–
            {Math.min(offset + materials.length, totalCount)}
          </span>
          <button
            className="ux-button tertiary"
            type="button"
            disabled={offset + materials.length >= totalCount}
            onClick={() => setOffset(offset + 50)}
          >
            Next
          </button>
        </nav>
      ) : null}
    </section>
  );

  const browseCategoryLabel = (category: CatalogDataCategory): string =>
    CATALOG_DATA_CATEGORIES.find((item) => item.key === category)?.label ??
    "Data";
  const browseResultList = (
    <section
      className="materials-results"
      aria-labelledby="browse-results-title"
    >
      <div className="materials-results-header">
        <div>
          <h2 id="browse-results-title">
            {browseResults?.category
              ? browseCategoryLabel(browseResults.category)
              : browseResults?.query
                ? `Results for “${browseResults.query}”`
                : "Browse results"}
          </h2>
          <p className="ux-meta">
            {new Intl.NumberFormat().format(browseResults?.totalCount ?? 0)}{" "}
            data items
          </p>
        </div>
      </div>
      {browseResults?.items.length ? (
        <MaterialsScrollRegion
          id="materials-browse-result-scroll"
          className="materials-result-table-wrap"
          shellClassName="materials-result-scroll-shell"
          aria-label="Browse results"
        >
          <table
            className="materials-result-table materials-browse-result-table"
            aria-label="Data results"
          >
            <thead>
              <tr>
                <th>Name</th>
                <th>Material code</th>
                <th>Category</th>
                <th>Description</th>
                <th>Revision</th>
              </tr>
            </thead>
            <tbody>
              {browseResults.items.map(({ record, category }) => (
                <tr
                  key={record.record_id}
                  tabIndex={0}
                  onClick={() => void selectBrowseResult(record)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") void selectBrowseResult(record);
                  }}
                >
                  <td>
                    <button
                      className="material-result-name"
                      type="button"
                      onClick={() => void selectBrowseResult(record)}
                    >
                      <span>{record.current_revision.content.name}</span>
                    </button>
                  </td>
                  <td>{record.current_revision.content.external_key ?? "—"}</td>
                  <td>{browseCategoryLabel(category)}</td>
                  <td>{record.current_revision.content.description ?? "—"}</td>
                  <td>r{record.current_revision.revision_no}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </MaterialsScrollRegion>
      ) : (
        <div className="ux-empty">
          <strong>No data is available here.</strong>
          <p>Choose another category or change the tree search.</p>
        </div>
      )}
    </section>
  );

  return (
    <div className="ux-page materials-page">
      {leftMode !== "browse" ? (
        <header className="materials-page-header" aria-label="Material query">
          <form
            className="materials-search-form"
            role="search"
            onSubmit={submit}
          >
            <label className="ux-field" style={{ flex: 1 }}>
              <span className="sr-only">
                Material name, grade, code, or family
              </span>
              <input
                className="ux-input"
                aria-label="Search materials"
                name="materials-query"
                autoComplete="off"
                value={draftQuery}
                onChange={(event) => setDraftQuery(event.target.value)}
                placeholder="Search material name, grade, code, or family…"
              />
            </label>
            <button className="ux-button primary" type="submit">
              Find
            </button>
          </form>
        </header>
      ) : null}
      <ResizableSplitPane
        id="cmp-materials-results"
        navigator={navigator}
        main={
          leftMode === "browse" && browseResults ? browseResultList : results
        }
        navigatorLabel={leftMode === "filters" ? "filters" : "navigator"}
      />
    </div>
  );
}
