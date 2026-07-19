import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";

import {
  ApiError,
  getCatalogWorkflowGraph,
  listCatalogExplorerChildren,
  listCatalogExplorerTables,
  listConfigurableCatalogSubsets,
  searchConfigurableCatalogRecords,
  type ApiConfig,
} from "./api";
import type {
  CatalogExplorerChildrenResponse,
  CatalogWorkflowGraphResponse,
  ConfigurableCatalogFolderResponse,
  ConfigurableCatalogRecordResponse,
  ConfigurableLinkEndpoint,
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
  const [searchTableId, setSearchTableId] = useState("");
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ConfigurableCatalogRecordResponse[] | null>(null);
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

  const loadBranch = useCallback(async (tableId: string, folderId: string | null) => {
    const branchKey = key(tableId, folderId);
    const result = await listCatalogExplorerChildren(config, tableId, folderId);
    setChildren((current) => ({ ...current, [branchKey]: result.data }));
    setExpanded((current) => new Set(current).add(branchKey));
  }, [config]);

  const loadGraph = useCallback(async (recordId: string, revisionId: string) => {
    try {
      const result = await getCatalogWorkflowGraph(config, recordId, revisionId, 8);
      setSelectedGraph(result.data);
      setError(null);
    } catch (caught) {
      setError(errorText(caught));
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
        const subsetPairs = await Promise.all(nextTables.map(async (table) => [
          table.table_id,
          (await listConfigurableCatalogSubsets(config, table.table_id)).data.items,
        ] as const));
        if (!active) return;
        setSubsets(Object.fromEntries(subsetPairs));
        if (nextTables[0]) await loadBranch(nextTables[0].table_id, null);
      })
      .catch((caught: unknown) => active && setError(errorText(caught)))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [config, loadBranch]);

  useEffect(() => {
    if (initialRecordId && initialRevisionId) void loadGraph(initialRecordId, initialRevisionId);
  }, [initialRecordId, initialRevisionId, loadGraph]);

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

  async function search(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!searchTableId) return;
    setLoading(true);
    try {
      const result = await searchConfigurableCatalogRecords(config, {
        table_id: searchTableId,
        text: query.trim() || null,
        folder_id: null,
        discrete_filters: [],
        number_filters: [],
        facet_attribute_ids: [],
        limit: 100,
      });
      setSearchResults(result.data.items);
      setError(null);
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setLoading(false);
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
          <p className="eyebrow">Material Database</p>
          <h1>Browse material knowledge</h1>
        </div>
        <form className="material-database-search" onSubmit={(event) => void search(event)}>
          <select aria-label="Search table" value={searchTableId} onChange={(event) => setSearchTableId(event.target.value)}>
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
          <div className="pane-heading"><span>CONTENTS</span><button type="button" aria-label="Database options">•••</button></div>
          <nav className="material-contents-tree" aria-label="Material Database contents">
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
          </nav>
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
              <div className="record-pane-heading"><div><p className="eyebrow">Search results</p><h2>{searchResults.length} matching records</h2></div><button className="text-button" type="button" onClick={() => setSearchResults(null)}>Close results</button></div>
              <div className="database-result-list">
                {searchResults.map((record) => (
                  <button type="button" key={record.record_id} onClick={() => openRecord(record)}>
                    <span className="database-node-icon record-icon" />
                    <span><strong>{record.current_revision.content.name}</strong><small>{record.current_revision.content.external_key ?? "Managed material record"}</small></span>
                    <span className="record-revision-badge">r{record.current_revision.revision_no}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : selected && selectedGraph ? (
            <div className="material-record-view">
              <nav className="database-breadcrumb" aria-label="Record breadcrumb">CAE Material Database <span>›</span> Engineering Materials Profile <span>›</span> {tableNames.get(selected.table_id)} <span>›</span> {selected.name}</nav>
              <div className="record-pane-heading">
                <div><p className="eyebrow">{recordType(selected, tableNames.get(selected.table_id))}</p><h2>{selected.name}</h2><p>{selectedRecord?.current_revision.content.description ?? "Linked material knowledge record"}</p></div>
                <div className="record-heading-actions"><span className="record-revision-badge">Revision {selected.revision_no}</span>{selected.domain_binding ? <button className="button primary" type="button" onClick={() => onNavigate(selected.domain_binding!.workbench_path)}>Open workbench</button> : null}</div>
              </div>
              <div className="record-view-tabs" role="tablist" aria-label="Record views"><button className="active" type="button">Workflow</button><button type="button" disabled>Datasheet</button><button type="button" disabled>Properties</button><button type="button" disabled>Curves</button><button type="button" disabled>CAE Cards</button></div>
              <section className="workflow-tree-card">
                <div><p className="eyebrow">Linked workflow</p><h3>From source material to CAE delivery</h3><p>Every node opens the exact linked record revision.</p></div>
                <ul className="material-workflow-tree">{workflowTree(selectedGraph.root)}</ul>
              </section>
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
          <div className="pane-heading"><span>RELATED DATA</span></div>
          {selected ? (
            <>
              <div className="related-record-summary"><span className="database-node-icon record-icon" /><div><strong>{selected.name}</strong><small>{selected.external_key ?? "Managed record"}</small></div></div>
              <section><h3>Linked records</h3><div className="related-link-list">
                {directLinks.map((link) => {
                  const forward = link.source.record_id === selected.record_id && link.source.record_revision_id === selected.record_revision_id;
                  const endpoint = forward ? link.target : link.source;
                  return <button type="button" key={link.record_link_id} onClick={() => openEndpoint(endpoint)}><span>{forward ? link.link_type_revision.content.forward_label : link.link_type_revision.content.reverse_label}</span><strong>{endpoint.name}</strong><small>{recordType(endpoint, tableNames.get(endpoint.table_id))} · r{endpoint.revision_no}</small></button>;
                })}
                {!directLinks.length ? <p className="muted">No linked records for this revision.</p> : null}
              </div></section>
              <section><h3>Revision</h3><dl className="record-facts"><div><dt>Current view</dt><dd>r{selected.revision_no}</dd></div><div><dt>Reference</dt><dd>{selected.record_revision_id.slice(0, 8)}…</dd></div></dl></section>
            </>
          ) : <p className="muted">Select a record to see linked tests, datasets, models and solver cards.</p>}
        </aside>
      </section>
    </div>
  );
}
