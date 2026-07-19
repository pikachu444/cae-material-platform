import { Fragment, useCallback, useEffect, useMemo, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";

import {
  ApiError,
  compareConfigurableCatalogRecordRevisions,
  getCatalogWorkflowGraph,
  listCatalogExplorerChildren,
  listCatalogExplorerTables,
  listConfigurableCatalogAttributes,
  listConfigurableCatalogLayouts,
  listConfigurableCatalogRecordRevisions,
  listConfigurableCatalogSubsets,
  searchConfigurableCatalogRecords,
  type ApiConfig,
} from "./api";
import type {
  CatalogExplorerChildrenResponse,
  CatalogWorkflowGraphResponse,
  ConfigurableAttributeResponse,
  ConfigurableCatalogFolderResponse,
  ConfigurableCatalogRecordComparison,
  ConfigurableCatalogRecordResponse,
  ConfigurableLayoutResponse,
  ConfigurableLinkEndpoint,
  ConfigurableRecordValue,
  ConfigurableSubsetResponse,
  ConfigurableTableResponse,
} from "./types";

interface Props {
  config: ApiConfig;
  initialRecordId?: string;
  initialRevisionId?: string;
  onNavigate: (path: string) => void;
  onRetry: () => void;
}

function key(tableId: string, folderId: string | null): string {
  return `${tableId}:${folderId ?? "root"}`;
}

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : "The Material Database could not be loaded.";
}

function recordType(endpoint: ConfigurableLinkEndpoint, tableName: string | undefined): string {
  return endpoint.domain_binding?.kind.replaceAll("_", " ") ?? tableName ?? "record";
}

function valueLabel(value: ConfigurableRecordValue): string {
  if (value.data_type === "number") {
    return `${value.original_value} ${value.original_unit_string} → ${value.normalized_value} ${value.normalized_unit}`;
  }
  if (value.data_type === "file" || value.data_type === "curve") {
    return `Artifact ${value.artifact_id.slice(0, 8)}… · SHA-256 ${value.artifact_sha256.slice(0, 12)}…`;
  }
  if (value.data_type === "record_reference") {
    return `Record ${value.target_record_id.slice(0, 8)}… @ ${value.target_record_revision_id.slice(0, 8)}…`;
  }
  if (value.data_type === "boolean") return value.value ? "Yes" : "No";
  return String(value.value);
}

interface TableDefinition {
  attributes: ConfigurableAttributeResponse[];
  layouts: ConfigurableLayoutResponse[];
}

type RecordTab = "overview" | "properties" | "curves" | "tests" | "models" | "cards" | "links";
type ExplorerProjection = "catalog" | "workflow";
type ContextTab = "related" | "revisions";

const DATABASE_VIEW_STATE_KEY = "cmp.material-database.view.v1";

function latestSiblingFolders(
  folders: ConfigurableCatalogFolderResponse[],
): ConfigurableCatalogFolderResponse[] {
  const latest = new Map<string, ConfigurableCatalogFolderResponse>();
  for (const folder of folders) {
    const current = latest.get(folder.content.name);
    if (
      !current
      || folder.current_revision.created_at > current.current_revision.created_at
    ) {
      latest.set(folder.content.name, folder);
    }
  }
  return [...latest.values()];
}

export function MaterialDatabaseExplorer({
  config,
  initialRecordId,
  initialRevisionId,
  onNavigate,
  onRetry,
}: Props) {
  const [tables, setTables] = useState<ConfigurableTableResponse[]>([]);
  const [subsets, setSubsets] = useState<Record<string, ConfigurableSubsetResponse[]>>({});
  const [children, setChildren] = useState<Record<string, CatalogExplorerChildrenResponse>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedGraph, setSelectedGraph] = useState<CatalogWorkflowGraphResponse | null>(null);
  const [tableDefinitions, setTableDefinitions] = useState<Record<string, TableDefinition>>({});
  const [selectedRevision, setSelectedRevision] = useState<ConfigurableCatalogRecordResponse["current_revision"] | null>(null);
  const [selectedRevisions, setSelectedRevisions] = useState<ConfigurableCatalogRecordResponse["current_revision"][]>([]);
  const [revisionComparison, setRevisionComparison] = useState<ConfigurableCatalogRecordComparison | null>(null);
  const [activeTab, setActiveTab] = useState<RecordTab>("overview");
  const [projection, setProjection] = useState<ExplorerProjection>("catalog");
  const [contextTab, setContextTab] = useState<ContextTab>("related");
  const [selectedLayoutId, setSelectedLayoutId] = useState("");
  const [searchTableId, setSearchTableId] = useState("");
  const [searchLayoutId, setSearchLayoutId] = useState("");
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ConfigurableCatalogRecordResponse[] | null>(null);
  const [searchFacets, setSearchFacets] = useState<Array<{ attribute_definition_id: string; value: string; count: number }>>([]);
  const [facetFilters, setFacetFilters] = useState<Record<string, string>>({});
  const [numberAttributeId, setNumberAttributeId] = useState("");
  const [numberMinimum, setNumberMinimum] = useState("");
  const [numberMaximum, setNumberMaximum] = useState("");
  const [compareRecordIds, setCompareRecordIds] = useState<Set<string>>(new Set());
  const [showRecordCompare, setShowRecordCompare] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const tableNames = useMemo(
    () => new Map(tables.map((table) => [table.table_id, table.current_revision.content.name])),
    [tables],
  );
  const selected = selectedGraph?.root ?? null;
  const loadedRecords = useMemo(
    () => Object.values(children).flatMap((branch) => branch.records),
    [children],
  );
  const selectedRecord = useMemo(
    () => selected
      ? [...loadedRecords, ...(searchResults ?? [])].find((item) => item.record_id === selected.record_id) ?? null
      : null,
    [loadedRecords, searchResults, selected],
  );
  const selectedDefinition = selected ? tableDefinitions[selected.table_id] : undefined;
  const selectedLayout = selectedDefinition?.layouts.find((layout) => layout.layout_id === selectedLayoutId)
    ?? selectedDefinition?.layouts[0]
    ?? null;
  const selectedAttributes = selectedDefinition?.attributes ?? [];
  const selectedValues = selectedRevision?.content.values ?? selectedRecord?.current_revision.content.values ?? [];
  const selectedValueMap = useMemo(
    () => new Map(selectedValues.map((value) => [value.attribute_definition_id, value])),
    [selectedValues],
  );
  const selectedAttributeMap = useMemo(
    () => new Map(selectedAttributes.map((attribute) => [attribute.attribute_definition_id, attribute])),
    [selectedAttributes],
  );
  const orderedAttributes = useMemo(() => {
    if (!selectedDefinition) return [];
    const positions = new Map(
      (selectedLayout?.items ?? []).map((item) => [item.attribute_definition_id, item.ordinal]),
    );
    return [...selectedDefinition.attributes].sort((left, right) => (
      (positions.get(left.attribute_definition_id) ?? Number.MAX_SAFE_INTEGER)
      - (positions.get(right.attribute_definition_id) ?? Number.MAX_SAFE_INTEGER)
    ));
  }, [selectedDefinition, selectedLayout]);
  const searchDefinition = tableDefinitions[searchTableId];
  const searchLayout = searchDefinition?.layouts.find((layout) => layout.layout_id === searchLayoutId)
    ?? searchDefinition?.layouts[0]
    ?? null;
  const searchDiscreteAttributes = searchDefinition?.attributes.filter(
    (attribute) => attribute.current_revision.content.data_type === "discrete",
  ) ?? [];
  const searchNumberAttributes = searchDefinition?.attributes.filter(
    (attribute) => attribute.current_revision.content.data_type === "number",
  ) ?? [];
  const searchComparedAttributes = useMemo(() => {
    if (!searchDefinition) return [];
    const positions = new Map(
      (searchLayout?.items ?? []).map((item) => [item.attribute_definition_id, item.ordinal]),
    );
    return [...searchDefinition.attributes].sort((left, right) => (
      (positions.get(left.attribute_definition_id) ?? Number.MAX_SAFE_INTEGER)
      - (positions.get(right.attribute_definition_id) ?? Number.MAX_SAFE_INTEGER)
    ));
  }, [searchDefinition, searchLayout]);
  const comparedRecords = (searchResults ?? []).filter((record) => compareRecordIds.has(record.record_id));

  const loadBranch = useCallback(async (tableId: string, folderId: string | null) => {
    const branchKey = key(tableId, folderId);
    const result = await listCatalogExplorerChildren(config, tableId, folderId);
    setChildren((current) => ({ ...current, [branchKey]: result.data }));
    setExpanded((current) => new Set(current).add(branchKey));
  }, [config]);

  const loadGraph = useCallback(async (recordId: string, revisionId: string): Promise<boolean> => {
    try {
      const [graphResult, revisionResult] = await Promise.all([
        getCatalogWorkflowGraph(config, recordId, revisionId, 8),
        listConfigurableCatalogRecordRevisions(config, recordId),
      ]);
      const exactRevision = revisionResult.data.items.find((item) => item.id === revisionId) ?? null;
      setSelectedGraph(graphResult.data);
      setSelectedRevision(exactRevision);
      setSelectedRevisions(revisionResult.data.items);
      if (exactRevision && revisionResult.data.items.length > 1) {
        const firstRevision = revisionResult.data.items[0];
        const comparison = await compareConfigurableCatalogRecordRevisions(
          config,
          recordId,
          firstRevision.id,
          exactRevision.id,
        );
        setRevisionComparison(comparison.data);
      } else {
        setRevisionComparison(null);
      }
      try {
        window.sessionStorage.setItem(DATABASE_VIEW_STATE_KEY, JSON.stringify({ recordId, revisionId }));
      } catch {
        // Session restoration is a convenience; database access must still work when storage is disabled.
      }
      setError(null);
      return true;
    } catch (caught) {
      setError(errorText(caught));
      return false;
    }
  }, [config]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    void listCatalogExplorerTables(config)
      .then(async (tableResult) => {
        if (!active) return;
        const nextTables = tableResult.data.items;
        setTables(nextTables);
        setSearchTableId(nextTables[0]?.table_id ?? "");
        const metadata = await Promise.all(nextTables.map(async (table) => {
          const [subsetResult, attributeResult, layoutResult] = await Promise.all([
            listConfigurableCatalogSubsets(config, table.table_id),
            listConfigurableCatalogAttributes(config, table.table_id),
            listConfigurableCatalogLayouts(config, table.table_id),
          ]);
          return {
            tableId: table.table_id,
            subsets: subsetResult.data.items,
            definition: {
              attributes: attributeResult.data.items,
              layouts: layoutResult.data.items,
            },
          };
        }));
        if (!active) return;
        setSubsets(Object.fromEntries(metadata.map((item) => [item.tableId, item.subsets])));
        setTableDefinitions(Object.fromEntries(metadata.map((item) => [item.tableId, item.definition])));
        setSearchLayoutId(metadata[0]?.definition.layouts[0]?.layout_id ?? "");
        const restored = (() => {
          if (initialRecordId && initialRevisionId) return { recordId: initialRecordId, revisionId: initialRevisionId };
          try {
            return JSON.parse(window.sessionStorage.getItem(DATABASE_VIEW_STATE_KEY) ?? "null") as { recordId: string; revisionId: string } | null;
          } catch {
            return null;
          }
        })();
        const discoverRecord = async (
          table: ConfigurableTableResponse,
          folderId: string | null,
          depth: number,
        ): Promise<ConfigurableCatalogRecordResponse | null> => {
          if (depth > 6) return null;
          const branchResult = await listCatalogExplorerChildren(config, table.table_id, folderId);
          const branchKey = key(table.table_id, folderId);
          setChildren((current) => ({ ...current, [branchKey]: branchResult.data }));
          setExpanded((current) => new Set(current).add(branchKey));
          const preferred = branchResult.data.records.find((record) => /synthetic demo steel|sheet steel|demo material(?! state)/i.test(record.current_revision.content.name));
          if (preferred) return preferred;
          if (branchResult.data.records[0]) return branchResult.data.records[0];
          for (const folder of latestSiblingFolders(branchResult.data.folders)) {
            const found = await discoverRecord(table, folder.folder_id, depth + 1);
            if (found) return found;
          }
          return null;
        };
        let discoveredRecord: ConfigurableCatalogRecordResponse | null = null;
        for (const table of nextTables) {
          const defaultRecord = await discoverRecord(table, null, 0);
          if (defaultRecord) {
            discoveredRecord = defaultRecord;
            break;
          }
        }
        const restoredLoaded = restored ? await loadGraph(restored.recordId, restored.revisionId) : false;
        if (!restoredLoaded && discoveredRecord) {
          await loadGraph(discoveredRecord.record_id, discoveredRecord.current_revision.id);
        }
      })
      .catch((caught: unknown) => active && setError(errorText(caught)))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [config, initialRecordId, initialRevisionId, loadGraph]);

  useEffect(() => {
    if (initialRecordId && initialRevisionId) void loadGraph(initialRecordId, initialRevisionId);
  }, [initialRecordId, initialRevisionId, loadGraph]);

  useEffect(() => {
    if (!selectedDefinition?.layouts.some((layout) => layout.layout_id === selectedLayoutId)) {
      setSelectedLayoutId(selectedDefinition?.layouts[0]?.layout_id ?? "");
    }
  }, [selectedDefinition, selectedLayoutId]);

  async function toggle(tableId: string, folderId: string | null): Promise<void> {
    const branchKey = key(tableId, folderId);
    if (expanded.has(branchKey)) {
      setExpanded((current) => {
        const next = new Set(current);
        next.delete(branchKey);
        return next;
      });
      return;
    }
    try {
      await loadBranch(tableId, folderId);
      setError(null);
    } catch (caught) {
      setError(errorText(caught));
    }
  }

  function openRecord(record: ConfigurableCatalogRecordResponse): void {
    const revisionId = record.current_revision.id;
    setSearchResults(null);
    setShowRecordCompare(false);
    setActiveTab("overview");
    onNavigate(`/database/records/${record.record_id}/revisions/${revisionId}`);
    void loadGraph(record.record_id, revisionId);
  }

  function openEndpoint(endpoint: ConfigurableLinkEndpoint): void {
    if (endpoint.domain_binding) {
      onNavigate(endpoint.domain_binding.workbench_path);
      return;
    }
    onNavigate(`/database/records/${endpoint.record_id}/revisions/${endpoint.record_revision_id}`);
    void loadGraph(endpoint.record_id, endpoint.record_revision_id);
  }

  function toggleRecordCompare(recordId: string): void {
    setCompareRecordIds((current) => {
      const next = new Set(current);
      if (next.has(recordId)) next.delete(recordId);
      else next.add(recordId);
      return next;
    });
  }

  async function performSearch(
    nextFacetFilters = facetFilters,
    range = { attributeId: numberAttributeId, minimum: numberMinimum, maximum: numberMaximum },
  ): Promise<void> {
    if (!searchTableId) return;
    setLoading(true);
    try {
      const result = await searchConfigurableCatalogRecords(config, {
        table_id: searchTableId,
        text: query.trim() || null,
        folder_id: null,
        discrete_filters: Object.entries(nextFacetFilters).map(([attributeDefinitionId, value]) => ({
          attribute_definition_id: attributeDefinitionId,
          values: [value],
        })),
        number_filters: range.attributeId && (range.minimum || range.maximum) ? [{
          attribute_definition_id: range.attributeId,
          minimum: range.minimum || null,
          maximum: range.maximum || null,
        }] : [],
        facet_attribute_ids: searchDiscreteAttributes.map(
          (attribute) => attribute.attribute_definition_id,
        ),
        limit: 100,
      });
      setSearchResults(result.data.items);
      setSearchFacets(result.data.facets);
      setCompareRecordIds(new Set());
      setShowRecordCompare(false);
      setError(null);
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setLoading(false);
    }
  }

  function search(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void performSearch();
  }

  function navigateCatalogTree(event: KeyboardEvent<HTMLElement>): void {
    if (!(event.target instanceof HTMLButtonElement) || !event.target.classList.contains("database-tree-node")) return;
    const nodes = [...event.currentTarget.querySelectorAll<HTMLButtonElement>("button.database-tree-node:not(:disabled)")];
    const currentIndex = nodes.indexOf(event.target);
    if (currentIndex < 0) return;
    const moveTo = event.key === "ArrowDown" ? currentIndex + 1
      : event.key === "ArrowUp" ? currentIndex - 1
        : event.key === "Home" ? 0
          : event.key === "End" ? nodes.length - 1
            : null;
    if (moveTo !== null) {
      event.preventDefault();
      nodes[Math.max(0, Math.min(nodes.length - 1, moveTo))]?.focus();
      return;
    }
    const disclosure = event.target.firstElementChild?.textContent;
    if (event.key === "ArrowRight" && disclosure === "▸") {
      event.preventDefault();
      event.target.click();
    } else if (event.key === "ArrowLeft" && disclosure === "▾") {
      event.preventDefault();
      event.target.click();
    }
  }

  function renderBranch(tableId: string, folderId: string | null): ReactNode {
    const branchKey = key(tableId, folderId);
    if (!expanded.has(branchKey)) return null;
    const branch = children[branchKey];
    if (!branch) return <p className="database-tree-status">Loading…</p>;
    return (
      <div className="database-tree-children">
        {latestSiblingFolders(branch.folders).map((folder) => {
          const folderKey = key(tableId, folder.folder_id);
          return (
            <div key={folder.folder_id}>
              <button className="database-tree-node folder" type="button" onClick={() => void toggle(tableId, folder.folder_id)}>
                <span aria-hidden="true">{expanded.has(folderKey) ? "▾" : "▸"}</span>
                <span className="database-node-icon folder-icon" aria-hidden="true" />
                <span>{folder.content.name}</span>
              </button>
              {renderBranch(tableId, folder.folder_id)}
            </div>
          );
        })}
        {branch.records.map((record) => (
          <button
            className={selected?.record_id === record.record_id ? "database-tree-node record selected" : "database-tree-node record"}
            type="button"
            key={record.record_id}
            onClick={() => openRecord(record)}
          >
            <span />
            <span className="database-node-icon record-icon" aria-hidden="true" />
            <span>{record.current_revision.content.name}</span>
            <small>r{record.current_revision.revision_no}</small>
          </button>
        ))}
        {!branch.folders.length && !branch.records.length ? <p className="database-tree-status">Empty folder</p> : null}
      </div>
    );
  }

  function workflowTree(node: ConfigurableLinkEndpoint, visited: ReadonlySet<string> = new Set()): ReactNode {
    if (!selectedGraph) return null;
    const nodeKey = `${node.record_id}:${node.record_revision_id}`;
    if (visited.has(nodeKey)) return null;
    const nextVisited = new Set(visited).add(nodeKey);
    const adjacent = selectedGraph.links.flatMap((link) => {
      const sourceKey = `${link.source.record_id}:${link.source.record_revision_id}`;
      const targetKey = `${link.target.record_id}:${link.target.record_revision_id}`;
      if (sourceKey === nodeKey) return [{ endpoint: link.target, label: link.link_type_revision.content.forward_label }];
      if (targetKey === nodeKey) return [{ endpoint: link.source, label: link.link_type_revision.content.reverse_label }];
      return [];
    }).filter(({ endpoint }) => !nextVisited.has(`${endpoint.record_id}:${endpoint.record_revision_id}`));

    return (
      <li className="material-workflow-tree-item" key={nodeKey}>
        <button
          type="button"
          className={nodeKey === `${selected?.record_id}:${selected?.record_revision_id}` ? "material-workflow-node current" : "material-workflow-node"}
          onClick={() => openEndpoint(node)}
        >
          <span className="workflow-kind-icon" aria-hidden="true" />
          <span>
            <small>{recordType(node, tableNames.get(node.table_id))}</small>
            <strong>{node.name}</strong>
            <em>{node.external_key ?? "Managed record"}</em>
          </span>
          <span className="record-revision-badge">r{node.revision_no}</span>
        </button>
        {adjacent.length ? (
          <ul>
            {adjacent.map(({ endpoint, label }) => (
              <li className="material-workflow-edge" key={`${nodeKey}:${endpoint.record_id}`}>
                <span>{label}</span>
                <ul>{workflowTree(endpoint, nextVisited)}</ul>
              </li>
            ))}
          </ul>
        ) : null}
      </li>
    );
  }

  const directLinks = selectedGraph?.links.filter((link) => (
    `${link.source.record_id}:${link.source.record_revision_id}` === `${selected?.record_id}:${selected?.record_revision_id}`
    || `${link.target.record_id}:${link.target.record_revision_id}` === `${selected?.record_id}:${selected?.record_revision_id}`
  )) ?? [];

  return (
    <div className="material-database-page">
      <header className="material-database-toolbar">
        <div>
          <p className="eyebrow">Engineering material intelligence</p>
          <h1>Material Database</h1>
          <p className="database-toolbar-context">Explore governed records, exact relationships and CAE-ready evidence.</p>
        </div>
        <form className="material-database-search" onSubmit={(event) => void search(event)}>
          <select aria-label="Search table" value={searchTableId} onChange={(event) => {
            const nextTableId = event.target.value;
            setSearchTableId(nextTableId);
            setSearchLayoutId(tableDefinitions[nextTableId]?.layouts[0]?.layout_id ?? "");
            setFacetFilters({});
            setNumberAttributeId("");
            setNumberMinimum("");
            setNumberMaximum("");
          }}>
            {tables.map((table) => <option value={table.table_id} key={table.table_id}>{table.current_revision.content.name}</option>)}
          </select>
          <input aria-label="Search database" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search materials, grades, tests or models" />
          <button className="button primary" type="submit">Search</button>
        </form>
        <button className="button secondary" type="button" onClick={() => onNavigate("/materials/new")}>New material</button>
      </header>

      {error ? <div className="error-banner" role="alert">{error}<button type="button" onClick={onRetry}>Retry</button></div> : null}

      <section className="material-database-workspace">
        <aside className="material-contents-pane">
          <div className="pane-heading"><span>CONTENTS</span><span className="database-live-indicator"><i />LIVE</span></div>
          <div className="database-projection-switch" role="group" aria-label="Explorer projection">
            <button type="button" className={projection === "catalog" ? "active" : ""} onClick={() => setProjection("catalog")}>Catalog</button>
            <button type="button" className={projection === "workflow" ? "active" : ""} disabled={!selectedGraph} onClick={() => setProjection("workflow")}>Workflow</button>
          </div>
          {projection === "catalog" ? <nav className="material-contents-tree" aria-label="Material Database contents" onKeyDown={navigateCatalogTree}>
            <div className="database-tree-node database-root"><span>▾</span><span className="database-node-icon database-icon" /><strong>CAE Material Database</strong></div>
            <div className="database-tree-children root-level">
              <div className="database-tree-node profile-root"><span>▾</span><span className="database-node-icon profile-icon" /><strong>Engineering Materials Profile</strong></div>
              <div className="database-tree-children profile-level">
                {tables.map((table) => {
                  const rootKey = key(table.table_id, null);
                  return (
                    <div key={table.table_id}>
                      <button className="database-tree-node table" type="button" onClick={() => void toggle(table.table_id, null)}>
                        <span>{expanded.has(rootKey) ? "▾" : "▸"}</span>
                        <span className="database-node-icon table-icon" />
                        <span>{table.current_revision.content.name}</span>
                      </button>
                      {renderBranch(table.table_id, null)}
                    </div>
                  );
                })}
              </div>
            </div>
          </nav> : <nav className="material-contents-tree database-workflow-projection" aria-label="Material workflow contents">
            <div className="workflow-projection-heading"><small>EXACT REVISION GRAPH</small><strong>{selected?.name}</strong><span>{selectedGraph?.nodes.length ?? 0} records · {selectedGraph?.links.length ?? 0} links</span></div>
            {selectedGraph ? <ul className="material-workflow-tree compact">{workflowTree(selectedGraph.root)}</ul> : null}
          </nav>}
          <div className="saved-subset-section">
            <span>SAVED SUBSETS</span>
            {Object.values(subsets).flat().map((subset) => (
              <button type="button" key={subset.subset_id} onClick={() => {
                setSearchTableId(subset.table_id);
                setQuery(typeof subset.filter_definition?.text === "string" ? subset.filter_definition.text : "");
                void searchConfigurableCatalogRecords(config, {
                  table_id: subset.table_id,
                  text: typeof subset.filter_definition?.text === "string" ? subset.filter_definition.text : null,
                  folder_id: null, discrete_filters: [], number_filters: [], facet_attribute_ids: [], limit: 100,
                }).then((result) => setSearchResults(result.data.items));
              }}><span aria-hidden="true">☆</span>{subset.name}</button>
            ))}
          </div>
        </aside>

        <section className="material-record-pane">
          {searchResults !== null ? (
            <div className="database-result-view">
              <div className="record-pane-heading"><div><p className="eyebrow">Search results</p><h2>{searchResults.length} matching records</h2></div><div className="record-heading-actions"><button className="button secondary" type="button" disabled={compareRecordIds.size < 2} onClick={() => setShowRecordCompare(true)}>Compare {compareRecordIds.size || ""}</button><button className="text-button" type="button" onClick={() => setSearchResults(null)}>Close results</button></div></div>
              {showRecordCompare && comparedRecords.length > 1 ? (
                <div className="material-record-compare">
                  <div className="compare-toolbar"><div><p className="eyebrow">Layout comparison</p><h3>{searchLayout?.name ?? "Default datasheet"}</h3></div><div className="layout-picker-actions">{(searchDefinition?.layouts.length ?? 0) > 1 ? <label>Layout<select aria-label="Comparison layout" value={searchLayout?.layout_id ?? ""} onChange={(event) => setSearchLayoutId(event.target.value)}>{searchDefinition?.layouts.map((layout) => <option value={layout.layout_id} key={layout.layout_id}>{layout.name}</option>)}</select></label> : null}<button className="text-button" type="button" onClick={() => setShowRecordCompare(false)}>Back to results</button></div></div>
                  <div className="record-compare-grid" style={{ gridTemplateColumns: `minmax(180px, .8fr) repeat(${comparedRecords.length}, minmax(190px, 1fr))` }}>
                    <strong>Attribute</strong>
                    {comparedRecords.map((record) => <strong key={record.record_id}>{record.current_revision.content.name}<small>r{record.current_revision.revision_no}</small></strong>)}
                    {searchComparedAttributes.map((attribute) => (
                      <Fragment key={attribute.attribute_definition_id}>
                        <span>{attribute.current_revision.content.name}<small>{attribute.current_revision.content.quantity_semantics ?? attribute.current_revision.content.data_type}</small></span>
                        {comparedRecords.map((record) => {
                          const value = record.current_revision.content.values.find((item) => item.attribute_definition_id === attribute.attribute_definition_id);
                          return <span key={`${record.record_id}:${attribute.attribute_definition_id}`}>{value ? valueLabel(value) : "—"}</span>;
                        })}
                      </Fragment>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="database-result-list">
                  {searchResults.map((record) => (
                    <div className="database-result-row" key={record.record_id}>
                      <label className="compare-check"><input aria-label={`Compare ${record.current_revision.content.name}`} type="checkbox" checked={compareRecordIds.has(record.record_id)} onChange={() => toggleRecordCompare(record.record_id)} /><span>Compare</span></label>
                      <button type="button" onClick={() => openRecord(record)}>
                        <span className="database-node-icon record-icon" />
                        <span><strong>{record.current_revision.content.name}</strong><small>{record.current_revision.content.external_key ?? "Managed material record"}</small></span>
                        <span className="record-revision-badge">r{record.current_revision.revision_no}</span>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : selected && selectedGraph ? (
            <div className="material-record-view">
              <nav className="database-breadcrumb" aria-label="Record breadcrumb">CAE Material Database <span>›</span> Engineering Materials Profile <span>›</span> {tableNames.get(selected.table_id)} <span>›</span> {selected.name}</nav>
              <div className="record-pane-heading database-record-heading">
                <div><p className="eyebrow">{recordType(selected, tableNames.get(selected.table_id))}</p><h2>{selected.name}</h2><p>{selectedRecord?.current_revision.content.description ?? "Linked material knowledge record"}</p></div>
                <div className="record-heading-actions"><span className="database-status-pill"><i />GOVERNED</span><span className="record-revision-badge">Revision {selected.revision_no}</span>{selected.domain_binding ? <button className="button primary" type="button" onClick={() => onNavigate(selected.domain_binding!.workbench_path)}>Open workbench</button> : null}</div>
              </div>
              <div className="record-view-tabs" role="tablist" aria-label="Record views">
                {(["overview", "properties", "curves", "tests", "models", "cards", "links"] as const).map((tab) => <button role="tab" aria-selected={activeTab === tab} className={activeTab === tab ? "active" : ""} type="button" key={tab} onClick={() => setActiveTab(tab)}>{tab === "tests" ? "Test Data" : tab === "cards" ? "CAE Cards" : tab[0].toUpperCase() + tab.slice(1)}</button>)}
              </div>
              {activeTab === "overview" ? <section className="layout-datasheet-card">
                <div className="datasheet-title"><div><p className="eyebrow">{selectedLayout?.name ?? "Default datasheet"}</p><h3>Record information</h3></div><div className="layout-picker-actions">{(selectedDefinition?.layouts.length ?? 0) > 1 ? <label>Layout<select aria-label="Datasheet layout" value={selectedLayout?.layout_id ?? ""} onChange={(event) => setSelectedLayoutId(event.target.value)}>{selectedDefinition?.layouts.map((layout) => <option value={layout.layout_id} key={layout.layout_id}>{layout.name}</option>)}</select></label> : null}<span className="record-revision-badge">Exact r{selected.revision_no}</span></div></div>
                <dl className="datasheet-metadata"><div><dt>Name</dt><dd>{selected.name}</dd></div><div><dt>External key</dt><dd>{selected.external_key ?? "—"}</dd></div><div><dt>Record revision</dt><dd>r{selected.revision_no} · immutable</dd></div></dl>
                <div className="layout-attribute-grid">
                  {orderedAttributes.map((attribute) => {
                    const definition = attribute.current_revision.content;
                    const value = selectedValueMap.get(attribute.attribute_definition_id);
                    const section = selectedLayout?.items.find((item) => item.attribute_definition_id === attribute.attribute_definition_id)?.section ?? "Properties";
                    return <div className="layout-attribute-row" key={attribute.attribute_definition_id}><span><small>{section}</small><strong>{definition.name}</strong><em>{definition.quantity_semantics ?? definition.data_type}</em></span><span>{value ? valueLabel(value) : "Not set"}</span></div>;
                  })}
                  {!orderedAttributes.length ? <p className="muted">No Attributes are assigned to this Table yet.</p> : null}
                </div>
                {revisionComparison ? <div className="datasheet-history"><h3>Revision changes</h3>{revisionComparison.value_differences.filter((item) => item.status !== "unchanged").map((difference) => <div key={difference.attribute_definition_id}><strong>{selectedAttributeMap.get(difference.attribute_definition_id)?.current_revision.content.name ?? "Attribute"}</strong><span>{difference.before ? valueLabel(difference.before) : "—"} → {difference.after ? valueLabel(difference.after) : "—"}</span><em>{difference.status}</em></div>)}</div> : null}
              </section> : null}
              {activeTab === "properties" ? <section className="layout-datasheet-card"><div className="datasheet-title"><div><p className="eyebrow">Typed values</p><h3>Properties and units</h3></div></div><div className="property-tile-grid">{orderedAttributes.filter((attribute) => !["curve", "file", "record_reference"].includes(attribute.current_revision.content.data_type)).map((attribute) => { const value = selectedValueMap.get(attribute.attribute_definition_id); return <article key={attribute.attribute_definition_id}><small>{attribute.current_revision.content.quantity_semantics ?? attribute.current_revision.content.data_type}</small><h4>{attribute.current_revision.content.name}</h4><strong>{value ? valueLabel(value) : "Not set"}</strong></article>; })}</div></section> : null}
              {activeTab === "curves" ? <section className="layout-datasheet-card"><div className="datasheet-title"><div><p className="eyebrow">Curve data</p><h3>Test and property curves</h3></div></div>{selectedValues.filter((value) => value.data_type === "curve").map((value) => <div className="curve-artifact-row" key={value.attribute_definition_id}><strong>{selectedAttributeMap.get(value.attribute_definition_id)?.current_revision.content.name ?? "Curve"}</strong><span>{valueLabel(value)}</span></div>)}{!selectedValues.some((value) => value.data_type === "curve") ? <div className="empty-tab-state"><p>No curve Attribute is stored on this record revision.</p><p>Open the linked Test Data record to inspect raw and normalized curves.</p></div> : null}</section> : null}
              {activeTab === "tests" ? <section className="layout-datasheet-card"><div className="datasheet-title"><div><p className="eyebrow">Experimental evidence</p><h3>Test data and datasets</h3></div></div><div className="linked-delivery-grid">{selectedGraph.nodes.filter((node) => ["test_data", "dataset", "processing_output"].includes(node.domain_binding?.kind ?? "")).map((node) => <button type="button" key={`${node.record_id}:${node.record_revision_id}`} onClick={() => openEndpoint(node)}><small>{node.domain_binding?.kind.replaceAll("_", " ")}</small><strong>{node.name}</strong><span>Exact revision {node.revision_no}</span></button>)}</div></section> : null}
              {activeTab === "models" ? <section className="layout-datasheet-card"><div className="datasheet-title"><div><p className="eyebrow">Modeling evidence</p><h3>Processing and material models</h3></div></div><div className="linked-delivery-grid">{selectedGraph.nodes.filter((node) => ["processing_output", "neutral_material", "material_model_ir"].includes(node.domain_binding?.kind ?? "")).map((node) => <button type="button" key={`${node.record_id}:${node.record_revision_id}`} onClick={() => openEndpoint(node)}><small>{node.domain_binding?.kind.replaceAll("_", " ")}</small><strong>{node.name}</strong><span>Exact revision {node.revision_no}</span></button>)}</div></section> : null}
              {activeTab === "cards" ? <section className="layout-datasheet-card"><div className="datasheet-title"><div><p className="eyebrow">CAE delivery</p><h3>Linked solver cards</h3></div></div><div className="linked-delivery-grid">{selectedGraph.nodes.filter((node) => ["solver_card", "neutral_solver_card"].includes(node.domain_binding?.kind ?? "")).map((node) => <button type="button" key={`${node.record_id}:${node.record_revision_id}`} onClick={() => openEndpoint(node)}><small>{node.domain_binding?.kind.replaceAll("_", " ")}</small><strong>{node.name}</strong><span>Exact revision {node.revision_no}</span></button>)}</div></section> : null}
              {activeTab === "links" ? <section className="layout-datasheet-card"><div className="datasheet-title"><div><p className="eyebrow">Exact relationships</p><h3>Forward and reverse links</h3></div></div><div className="linked-delivery-grid">{directLinks.map((link) => { const forward = link.source.record_id === selected.record_id && link.source.record_revision_id === selected.record_revision_id; const endpoint = forward ? link.target : link.source; return <button type="button" key={link.record_link_id} onClick={() => openEndpoint(endpoint)}><small>{forward ? link.link_type_revision.content.forward_label : link.link_type_revision.content.reverse_label}</small><strong>{endpoint.name}</strong><span>Exact r{endpoint.revision_no}</span></button>; })}</div></section> : null}
            </div>
          ) : (
            <div className="database-welcome-view">
              <span className="database-welcome-icon" aria-hidden="true">▦</span>
              <p className="eyebrow">Material Database</p>
              <h2>Select a record from the Contents Tree</h2>
              <p>Expand a Table or Folder to inspect its Datasheet and follow linked test, processing, model and solver-card records.</p>
              {loading ? <p className="muted">Loading material knowledge…</p> : null}
            </div>
          )}
        </section>

        <aside className="material-related-pane">
          <div className="pane-heading"><span>{searchResults !== null ? "FILTER RESULTS" : "CONTEXT"}</span></div>
          {searchResults !== null ? <div className="database-search-filters">
            <section><h3>Material facets</h3>{searchDiscreteAttributes.map((attribute) => {
              const buckets = searchFacets.filter((facet) => facet.attribute_definition_id === attribute.attribute_definition_id);
              return <div className="database-facet-group" key={attribute.attribute_definition_id}><strong>{attribute.current_revision.content.name}</strong>{buckets.map((bucket) => <button className={facetFilters[attribute.attribute_definition_id] === bucket.value ? "active" : ""} type="button" key={bucket.value} onClick={() => { const next = facetFilters[attribute.attribute_definition_id] === bucket.value ? Object.fromEntries(Object.entries(facetFilters).filter(([key]) => key !== attribute.attribute_definition_id)) : { ...facetFilters, [attribute.attribute_definition_id]: bucket.value }; setFacetFilters(next); void performSearch(next); }}><span>{bucket.value}</span><small>{bucket.count}</small></button>)}</div>;
            })}{!searchDiscreteAttributes.length ? <p className="muted">No discrete facets are defined for this Table.</p> : null}</section>
            <section><h3>Numeric range</h3><label>Property<select value={numberAttributeId} onChange={(event) => setNumberAttributeId(event.target.value)}><option value="">No range filter</option>{searchNumberAttributes.map((attribute) => <option key={attribute.attribute_definition_id} value={attribute.attribute_definition_id}>{attribute.current_revision.content.name}</option>)}</select></label><div className="database-range-inputs"><input aria-label="Normalized minimum" value={numberMinimum} onChange={(event) => setNumberMinimum(event.target.value)} placeholder="Minimum" /><input aria-label="Normalized maximum" value={numberMaximum} onChange={(event) => setNumberMaximum(event.target.value)} placeholder="Maximum" /></div><button className="button secondary" type="button" onClick={() => void performSearch()}>Apply range</button></section>
            <button className="text-button" type="button" onClick={() => { setFacetFilters({}); setNumberAttributeId(""); setNumberMinimum(""); setNumberMaximum(""); void performSearch({}, { attributeId: "", minimum: "", maximum: "" }); }}>Clear filters</button>
          </div> : selected ? (
            <>
              <div className="related-record-summary"><span className="database-node-icon record-icon" /><div><strong>{selected.name}</strong><small>{selected.external_key ?? "Managed record"}</small></div></div>
              <div className="database-context-tabs" role="tablist" aria-label="Record context"><button type="button" role="tab" aria-selected={contextTab === "related"} className={contextTab === "related" ? "active" : ""} onClick={() => setContextTab("related")}>Related</button><button type="button" role="tab" aria-selected={contextTab === "revisions"} className={contextTab === "revisions" ? "active" : ""} onClick={() => setContextTab("revisions")}>Revisions</button></div>
              {contextTab === "related" ? <section><h3>Linked records</h3><div className="related-link-list">
                {directLinks.map((link) => {
                  const forward = link.source.record_id === selected.record_id && link.source.record_revision_id === selected.record_revision_id;
                  const endpoint = forward ? link.target : link.source;
                  return <button type="button" key={link.record_link_id} onClick={() => openEndpoint(endpoint)}><span>{forward ? link.link_type_revision.content.forward_label : link.link_type_revision.content.reverse_label}</span><strong>{endpoint.name}</strong><small>{recordType(endpoint, tableNames.get(endpoint.table_id))} · r{endpoint.revision_no}</small></button>;
                })}
                {!directLinks.length ? <p className="muted">No linked records for this revision.</p> : null}
              </div></section> : <section><h3>Immutable history</h3><div className="database-revision-list">{selectedRevisions.map((revision) => <button type="button" className={revision.id === selected.record_revision_id ? "active" : ""} key={revision.id} onClick={() => void loadGraph(selected.record_id, revision.id)}><span><strong>Revision {revision.revision_no}</strong><small>{new Date(revision.created_at).toLocaleDateString()}</small></span><em>{revision.id === selected.record_revision_id ? "Viewing" : "Open"}</em></button>)}</div></section>}
              <section><h3>Record facts</h3><dl className="record-facts"><div><dt>Current view</dt><dd>r{selected.revision_no}</dd></div><div><dt>Relationships</dt><dd>{directLinks.length}</dd></div><div><dt>Reference</dt><dd>{selected.record_revision_id.slice(0, 8)}…</dd></div></dl></section>
            </>
          ) : <p className="muted">Select a record to see linked tests, datasets, models and solver cards.</p>}
        </aside>
      </section>
    </div>
  );
}
