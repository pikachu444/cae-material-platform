import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import {
  ApiError,
  getCatalogWorkflowGraph,
  getConfigurableCatalogRecord,
  listCatalogExplorerChildren,
  listCatalogExplorerTables,
  listConfigurableCatalogFolders,
  listConfigurableCatalogSubsets,
  searchConfigurableCatalogRecords,
  type ApiConfig,
} from "./api";
import type {
  CatalogExplorerChildrenResponse,
  CatalogWorkflowGraphResponse,
  ConfigurableCatalogFolderResponse,
  ConfigurableCatalogRecordResponse,
  ConfigurableSubsetResponse,
  ConfigurableTableResponse,
  ConfigurableLinkEndpoint,
} from "./types";

const ROW_HEIGHT = 26;
const TREE_OVERSCAN = 8;
const SEARCH_LIMIT = 100;

type TreeKind = "database" | "profile" | "table" | "folder" | "record" | "loading";

interface TreeRow {
  id: string;
  parentId: string | null;
  kind: TreeKind;
  label: string;
  depth: number;
  tableId?: string;
  folderId?: string | null;
  record?: ConfigurableCatalogRecordResponse;
  expandable: boolean;
  expanded: boolean;
  match: boolean;
}

interface RequestedRecord {
  record_id: string;
  record_revision_id: string;
  table_id: string;
  name: string;
}

interface Props {
  config: ApiConfig;
  subsetMode?: boolean;
  requestedRecord?: ConfigurableLinkEndpoint | null;
  onSelectRecord: (
    record: ConfigurableCatalogRecordResponse,
    graph: CatalogWorkflowGraphResponse,
  ) => void;
  onOpenRecord: (record: ConfigurableCatalogRecordResponse) => void;
}

function messageFor(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  return cause instanceof Error ? cause.message : "The governed Materials tree could not be loaded.";
}

function branchKey(tableId: string, folderId: string | null): string {
  return `${tableId}:${folderId ?? "root"}`;
}

function tableRowId(tableId: string): string {
  return `table:${tableId}`;
}

function folderRowId(folderId: string): string {
  return `folder:${folderId}`;
}

function recordRowId(recordId: string): string {
  return `record:${recordId}`;
}

function folderAncestors(
  folderId: string | null,
  foldersById: Map<string, ConfigurableCatalogFolderResponse>,
): ConfigurableCatalogFolderResponse[] {
  const ancestors: ConfigurableCatalogFolderResponse[] = [];
  const visited = new Set<string>();
  let currentId = folderId;
  while (currentId && !visited.has(currentId)) {
    visited.add(currentId);
    const folder = foldersById.get(currentId);
    if (!folder) break;
    ancestors.unshift(folder);
    currentId = folder.content.parent_folder_id;
  }
  return ancestors;
}

function rowGlyph(row: TreeRow): string {
  if (row.expandable) return row.expanded ? "▾" : "▸";
  if (row.kind === "record") return "·";
  if (row.kind === "loading") return "…";
  return "";
}

export function MaterialsBrowseTree({ config, subsetMode = false, requestedRecord, onSelectRecord, onOpenRecord }: Props) {
  const [tables, setTables] = useState<ConfigurableTableResponse[]>([]);
  const [children, setChildren] = useState<Record<string, CatalogExplorerChildrenResponse>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set(["database", "profile"]));
  const [expandedBeforeSearch, setExpandedBeforeSearch] = useState<Set<string> | null>(null);
  const [selectedTableId, setSelectedTableId] = useState("");
  const [selectedRecordId, setSelectedRecordId] = useState("");
  const [draftFind, setDraftFind] = useState("");
  const [activeFind, setActiveFind] = useState("");
  const [searchFolders, setSearchFolders] = useState<ConfigurableCatalogFolderResponse[]>([]);
  const [searchRecords, setSearchRecords] = useState<ConfigurableCatalogRecordResponse[] | null>(null);
  const [searchTotal, setSearchTotal] = useState(0);
  const [subsets, setSubsets] = useState<ConfigurableSubsetResponse[]>([]);
  const [selectedSubsetId, setSelectedSubsetId] = useState("");
  const [loadingKey, setLoadingKey] = useState<string | null>("roots");
  const [error, setError] = useState<string | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(420);
  const [focusIndex, setFocusIndex] = useState(0);
  const [matchCursor, setMatchCursor] = useState(-1);
  const [pendingFocusRecordId, setPendingFocusRecordId] = useState<string | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const rowRefs = useRef(new Map<string, HTMLDivElement>());

  const loadChildren = useCallback(async (tableId: string, folderId: string | null) => {
    const key = branchKey(tableId, folderId);
    if (children[key]) return;
    setLoadingKey(key);
    try {
      const result = await listCatalogExplorerChildren(config, tableId, folderId);
      setChildren((current) => ({ ...current, [key]: result.data }));
      setError(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setLoadingKey((current) => current === key ? null : current);
    }
  }, [children, config]);

  useEffect(() => {
    let active = true;
    setLoadingKey("roots");
    void listCatalogExplorerTables(config).then(async (result) => {
      if (!active) return;
      const items = Array.isArray(result.data.items) ? result.data.items : [];
      setTables(items);
      const firstTableId = items[0]?.table_id ?? "";
      setSelectedTableId((current) => current || firstTableId);
      if (firstTableId) {
        setExpanded((current) => new Set(current).add(branchKey(firstTableId, null)));
        const [childResult, subsetResult] = await Promise.all([
          listCatalogExplorerChildren(config, firstTableId, null),
          listConfigurableCatalogSubsets(config, firstTableId),
        ]);
        if (!active) return;
        setChildren((current) => ({ ...current, [branchKey(firstTableId, null)]: childResult.data }));
        setSubsets(Array.isArray(subsetResult.data.items) ? subsetResult.data.items : []);
      }
      setError(null);
    }).catch((cause: unknown) => {
      if (!active) return;
      setError(messageFor(cause));
    }).finally(() => {
      if (active) setLoadingKey(null);
    });
    return () => { active = false; };
  }, [config]);

  const selectTable = useCallback(async (tableId: string) => {
    setSelectedTableId(tableId);
    setSelectedSubsetId("");
    setActiveFind("");
    setDraftFind("");
    setSearchRecords(null);
    setSearchFolders([]);
    setExpandedBeforeSearch(null);
    setExpanded((current) => new Set(current).add(branchKey(tableId, null)));
    setLoadingKey(branchKey(tableId, null));
    try {
      const [childResult, subsetResult] = await Promise.all([
        children[branchKey(tableId, null)]
          ? Promise.resolve({ data: children[branchKey(tableId, null)] })
          : listCatalogExplorerChildren(config, tableId, null),
        listConfigurableCatalogSubsets(config, tableId),
      ]);
      setChildren((current) => ({ ...current, [branchKey(tableId, null)]: childResult.data }));
      setSubsets(subsetResult.data.items);
      setError(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setLoadingKey(null);
    }
  }, [children, config]);

  const runSearch = useCallback(async (
    tableId: string,
    text: string,
    subset?: ConfigurableSubsetResponse,
  ) => {
    if (!tableId) return;
    const definition = subset?.filter_definition ?? {};
    const discreteDefinition = definition.discrete_filters && typeof definition.discrete_filters === "object"
      ? definition.discrete_filters as Record<string, unknown>
      : {};
    const numberAttributeId = typeof definition.number_attribute_id === "string"
      ? definition.number_attribute_id
      : null;
    const normalizedText = text.trim();
    if (!normalizedText && !subset) {
      setActiveFind("");
      setSearchRecords(null);
      setSearchFolders([]);
      setSearchTotal(0);
      setMatchCursor(-1);
      if (expandedBeforeSearch) setExpanded(expandedBeforeSearch);
      setExpandedBeforeSearch(null);
      return;
    }
    setExpandedBeforeSearch((current) => current ?? new Set(expanded));
    setLoadingKey("search");
    try {
      const [folderResult, recordResult] = await Promise.all([
        listConfigurableCatalogFolders(config, tableId),
        searchConfigurableCatalogRecords(config, {
          table_id: tableId,
          text: normalizedText || (typeof definition.text === "string" ? definition.text : null),
          folder_id: typeof definition.folder_id === "string" ? definition.folder_id : null,
          discrete_filters: Object.entries(discreteDefinition).flatMap(([attribute_definition_id, value]) =>
            typeof value === "string" ? [{ attribute_definition_id, values: [value] }] : []),
          number_filters: numberAttributeId ? [{
            attribute_definition_id: numberAttributeId,
            minimum: typeof definition.number_minimum === "string" ? definition.number_minimum : null,
            maximum: typeof definition.number_maximum === "string" ? definition.number_maximum : null,
          }] : [],
          facet_attribute_ids: [],
          limit: SEARCH_LIMIT,
        }),
      ]);
      setActiveFind(normalizedText || (typeof definition.text === "string" ? definition.text : subset?.name ?? "Subset"));
      setSearchFolders(folderResult.data.items);
      setSearchRecords(recordResult.data.items);
      setSearchTotal(recordResult.data.total_count);
      setMatchCursor(-1);
      setError(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setLoadingKey(null);
    }
  }, [config, expanded, expandedBeforeSearch]);

  function submitFind(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setSelectedSubsetId("");
    void runSearch(selectedTableId, draftFind);
  }

  function applySubset(subsetId: string): void {
    setSelectedSubsetId(subsetId);
    const subset = subsets.find((item) => item.subset_id === subsetId);
    if (!subset) {
      void runSearch(selectedTableId, "");
      return;
    }
    const definition = subset.filter_definition ?? {};
    const text = typeof definition.text === "string" ? definition.text : "";
    setDraftFind(text);
    void runSearch(subset.table_id, text, subset);
  }

  const toggleRow = useCallback(async (row: TreeRow) => {
    if (!row.expandable) return;
    const key = row.kind === "database" || row.kind === "profile"
      ? row.id
      : row.kind === "table"
        ? branchKey(row.tableId!, null)
        : branchKey(row.tableId!, row.folderId ?? null);
    if (expanded.has(key)) {
      setExpanded((current) => {
        const next = new Set(current);
        next.delete(key);
        return next;
      });
      return;
    }
    setExpanded((current) => new Set(current).add(key));
    if (row.kind === "table") {
      setSelectedTableId(row.tableId!);
      await loadChildren(row.tableId!, null);
    } else if (row.kind === "folder") {
      await loadChildren(row.tableId!, row.folderId ?? null);
    }
  }, [expanded, loadChildren]);

  const normalRows = useMemo(() => {
    const rows: TreeRow[] = [];
    const databaseExpanded = expanded.has("database");
    const profileExpanded = expanded.has("profile");
    rows.push({ id: "database", parentId: null, kind: "database", label: "Materials Database", depth: 0, expandable: true, expanded: databaseExpanded, match: false });
    if (!databaseExpanded) return rows;
    rows.push({ id: "profile", parentId: "database", kind: "profile", label: "Engineering Materials", depth: 1, expandable: true, expanded: profileExpanded, match: false });
    if (!profileExpanded) return rows;

    const appendChildren = (tableId: string, folderId: string | null, depth: number, parentId: string) => {
      const key = branchKey(tableId, folderId);
      const branch = children[key];
      if (!branch && loadingKey === key) {
        rows.push({ id: `loading:${key}`, parentId, kind: "loading", label: "Loading…", depth, expandable: false, expanded: false, match: false });
        return;
      }
      for (const folder of branch?.folders ?? []) {
        const id = folderRowId(folder.folder_id);
        const isExpanded = expanded.has(branchKey(tableId, folder.folder_id));
        rows.push({ id, parentId, kind: "folder", label: folder.content.name, depth, tableId, folderId: folder.folder_id, expandable: true, expanded: isExpanded, match: false });
        if (isExpanded) appendChildren(tableId, folder.folder_id, depth + 1, id);
      }
      for (const record of branch?.records ?? []) {
        rows.push({ id: recordRowId(record.record_id), parentId, kind: "record", label: record.current_revision.content.name, depth, tableId, record, expandable: false, expanded: false, match: false });
      }
    };

    for (const table of tables) {
      const id = tableRowId(table.table_id);
      const isExpanded = expanded.has(branchKey(table.table_id, null));
      rows.push({ id, parentId: "profile", kind: "table", label: table.current_revision.content.name, depth: 2, tableId: table.table_id, expandable: true, expanded: isExpanded, match: false });
      if (isExpanded) appendChildren(table.table_id, null, 3, id);
    }
    return rows;
  }, [children, expanded, loadingKey, tables]);

  const searchedRows = useMemo(() => {
    if (!searchRecords) return null;
    const rows: TreeRow[] = [
      { id: "database", parentId: null, kind: "database", label: "Materials Database", depth: 0, expandable: true, expanded: true, match: false },
      { id: "profile", parentId: "database", kind: "profile", label: "Engineering Materials", depth: 1, expandable: true, expanded: true, match: false },
    ];
    const table = tables.find((item) => item.table_id === selectedTableId);
    if (!table) return rows;
    const tableId = table.table_id;
    const tableIdForRow = tableRowId(tableId);
    rows.push({ id: tableIdForRow, parentId: "profile", kind: "table", label: table.current_revision.content.name, depth: 2, tableId, expandable: true, expanded: true, match: false });

    const foldersById = new Map(searchFolders.map((folder) => [folder.folder_id, folder]));
    const query = activeFind.toLocaleLowerCase();
    const matchedFolderIds = new Set(searchFolders.filter((folder) => folder.content.name.toLocaleLowerCase().includes(query)).map((folder) => folder.folder_id));
    const includedFolderIds = new Set<string>();
    for (const folderId of matchedFolderIds) {
      for (const ancestor of folderAncestors(folderId, foldersById)) includedFolderIds.add(ancestor.folder_id);
    }
    for (const record of searchRecords) {
      for (const ancestor of folderAncestors(record.current_revision.content.folder_id, foldersById)) includedFolderIds.add(ancestor.folder_id);
    }
    const childrenByParent = new Map<string | null, ConfigurableCatalogFolderResponse[]>();
    for (const folder of searchFolders) {
      if (!includedFolderIds.has(folder.folder_id)) continue;
      const parent = folder.content.parent_folder_id;
      const bucket = childrenByParent.get(parent) ?? [];
      bucket.push(folder);
      childrenByParent.set(parent, bucket);
    }
    for (const bucket of childrenByParent.values()) bucket.sort((left, right) => left.content.name.localeCompare(right.content.name));
    const recordsByFolder = new Map<string | null, ConfigurableCatalogRecordResponse[]>();
    for (const record of searchRecords) {
      const folderId = record.current_revision.content.folder_id;
      const bucket = recordsByFolder.get(folderId) ?? [];
      bucket.push(record);
      recordsByFolder.set(folderId, bucket);
    }
    for (const bucket of recordsByFolder.values()) bucket.sort((left, right) => left.current_revision.content.name.localeCompare(right.current_revision.content.name));

    const append = (folderId: string | null, depth: number, parentId: string) => {
      for (const folder of childrenByParent.get(folderId) ?? []) {
        const id = folderRowId(folder.folder_id);
        rows.push({ id, parentId, kind: "folder", label: folder.content.name, depth, tableId, folderId: folder.folder_id, expandable: true, expanded: true, match: matchedFolderIds.has(folder.folder_id) });
        append(folder.folder_id, depth + 1, id);
      }
      for (const record of recordsByFolder.get(folderId) ?? []) {
        rows.push({ id: recordRowId(record.record_id), parentId, kind: "record", label: record.current_revision.content.name, depth, tableId, record, expandable: false, expanded: false, match: record.current_revision.content.name.toLocaleLowerCase().includes(query) || Boolean(selectedSubsetId) });
      }
    };
    append(null, 3, tableIdForRow);
    return rows;
  }, [activeFind, searchFolders, searchRecords, selectedSubsetId, selectedTableId, tables]);

  const rows = searchedRows ?? normalRows;
  const matchIndexes = useMemo(() => rows.flatMap((row, index) => row.match ? [index] : []), [rows]);
  const start = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - TREE_OVERSCAN);
  const visibleCount = Math.ceil(viewportHeight / ROW_HEIGHT) + TREE_OVERSCAN * 2;
  const end = Math.min(rows.length, start + visibleCount);
  const visibleRows = rows.slice(start, end);

  const focusRow = useCallback((index: number) => {
    if (!rows.length) return;
    const nextIndex = Math.max(0, Math.min(index, rows.length - 1));
    const viewport = viewportRef.current;
    if (viewport) {
      const top = nextIndex * ROW_HEIGHT;
      if (top < viewport.scrollTop) viewport.scrollTop = top;
      else if (top + ROW_HEIGHT > viewport.scrollTop + viewport.clientHeight) viewport.scrollTop = top + ROW_HEIGHT - viewport.clientHeight;
    }
    setFocusIndex(nextIndex);
    requestAnimationFrame(() => rowRefs.current.get(rows[nextIndex].id)?.focus());
  }, [rows]);

  function findNext(): void {
    if (!matchIndexes.length) return;
    const nextCursor = (matchCursor + 1) % matchIndexes.length;
    setMatchCursor(nextCursor);
    focusRow(matchIndexes[nextCursor]);
  }

  const selectRecord = useCallback(async (record: ConfigurableCatalogRecordResponse) => {
    setSelectedRecordId(record.record_id);
    setLoadingKey(`record:${record.record_id}`);
    try {
      const graph = await getCatalogWorkflowGraph(config, record.record_id, record.current_revision.id, 5);
      onSelectRecord(record, graph.data);
      setError(null);
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setLoadingKey(null);
    }
  }, [config, onSelectRecord]);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>, row: TreeRow, index: number): void {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusRow(index + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      focusRow(index - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusRow(0);
    } else if (event.key === "End") {
      event.preventDefault();
      focusRow(rows.length - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      if (row.expandable && !row.expanded) void toggleRow(row);
      else focusRow(index + 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      if (row.expandable && row.expanded) void toggleRow(row);
      else if (row.parentId) {
        const parentIndex = rows.findIndex((candidate) => candidate.id === row.parentId);
        if (parentIndex >= 0) focusRow(parentIndex);
      }
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (row.record) void selectRecord(row.record);
      else void toggleRow(row);
    }
  }

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setViewportHeight(entry.contentRect.height));
    observer.observe(viewport);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!requestedRecord?.record_id) return;
    let active = true;
    const requested: RequestedRecord = requestedRecord;
    setLoadingKey(`reveal:${requested.record_id}`);
    void Promise.all([
      getConfigurableCatalogRecord(config, requested.record_id),
      listConfigurableCatalogFolders(config, requested.table_id),
    ]).then(async ([recordResult, folderResult]) => {
      if (!active) return;
      const record = recordResult.data;
      const foldersById = new Map(folderResult.data.items.map((folder) => [folder.folder_id, folder]));
      const ancestors = folderAncestors(record.current_revision.content.folder_id, foldersById);
      const parentIds: Array<string | null> = [null, ...ancestors.map((folder) => folder.folder_id)];
      const loaded = await Promise.all(parentIds.map((folderId) => listCatalogExplorerChildren(config, requested.table_id, folderId)));
      if (!active) return;
      setChildren((current) => {
        const next = { ...current };
        loaded.forEach((result, index) => { next[branchKey(requested.table_id, parentIds[index])] = result.data; });
        return next;
      });
      setSelectedTableId(requested.table_id);
      setSelectedRecordId(record.record_id);
      setExpanded((current) => {
        const next = new Set(current);
        next.add("database");
        next.add("profile");
        next.add(branchKey(requested.table_id, null));
        for (const folder of ancestors) next.add(branchKey(requested.table_id, folder.folder_id));
        return next;
      });
      setActiveFind("");
      setDraftFind("");
      setSearchRecords(null);
      setSearchFolders([]);
      setError(null);
      setPendingFocusRecordId(record.record_id);
    }).catch((cause: unknown) => {
      if (active) setError(messageFor(cause));
    }).finally(() => {
      if (active) setLoadingKey(null);
    });
    return () => { active = false; };
  }, [config, requestedRecord?.record_id, requestedRecord?.table_id]);

  useEffect(() => {
    if (!pendingFocusRecordId || searchRecords) return;
    const index = normalRows.findIndex((row) => row.id === recordRowId(pendingFocusRecordId));
    if (index < 0) return;
    focusRow(index);
    setPendingFocusRecordId(null);
  }, [focusRow, normalRows, pendingFocusRecordId, searchRecords]);

  return (
    <div className="materials-explorer">
      <div className="materials-explorer-heading">
        <h2>Browse</h2>
        <span className="ux-meta">{loadingKey === "roots" ? "Loading…" : `${tables.length} tables`}</span>
      </div>
      <div className="materials-explorer-scope">
        <label className="ux-field">Database<select className="ux-select" aria-label="Database"><option>Materials Database</option></select></label>
        <label className="ux-field">Profile<select className="ux-select" aria-label="Profile"><option>Engineering Materials</option></select></label>
        <label className="ux-field">Table<select className="ux-select" aria-label="Browse table" value={selectedTableId} onChange={(event) => void selectTable(event.target.value)}>{tables.map((table) => <option key={table.table_id} value={table.table_id}>{table.current_revision.content.name}</option>)}</select></label>
      </div>
      {subsetMode ? <div className="tree-subset-list" aria-label="Saved Subsets"><p>Saved Subsets</p>{subsets.length ? subsets.map((subset) => <button key={subset.subset_id} type="button" className={selectedSubsetId === subset.subset_id ? "active" : ""} onClick={() => applySubset(subset.subset_id)}><strong>{subset.name}</strong><span>{subset.description ?? "Reusable governed filter"}</span></button>) : <span className="ux-meta">No saved Subsets exist for this Table.</span>}</div> : <form className="tree-find" role="search" aria-label="Find in Materials tree" onSubmit={submitFind}>
        <input className="ux-input" aria-label="Find in tree" value={draftFind} onChange={(event) => setDraftFind(event.target.value)} placeholder="Find folder or record" />
        <button className="ux-button tertiary" type="submit">Find</button>
      </form>}
      <div className="tree-search-status" aria-live="polite">
        {searchRecords ? <span>{new Intl.NumberFormat().format(searchTotal)} record matches{searchTotal > SEARCH_LIMIT ? ` · first ${SEARCH_LIMIT}` : ""}</span> : <span>Expand a Table or Folder to load its children.</span>}
        {searchRecords ? <button type="button" onClick={findNext} disabled={!matchIndexes.length}>Find next</button> : null}
      </div>
      {error ? <div className="ux-notice error" role="alert">{error}</div> : null}
      <div
        className="materials-tree-scroll"
        ref={viewportRef}
        role="tree"
        aria-label="Database contents"
        aria-busy={Boolean(loadingKey)}
        onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
      >
        <div className="materials-tree-spacer" style={{ height: rows.length * ROW_HEIGHT }}>
          {visibleRows.map((row, offset) => {
            const index = start + offset;
            return (
              <div
                key={row.id}
                ref={(node) => { if (node) rowRefs.current.set(row.id, node); else rowRefs.current.delete(row.id); }}
                className={`materials-tree-row kind-${row.kind}${row.match ? " match" : ""}${row.record?.record_id === selectedRecordId ? " selected" : ""}`}
                style={{ top: index * ROW_HEIGHT, paddingInlineStart: 8 + row.depth * 12 }}
                role="treeitem"
                aria-level={row.depth + 1}
                aria-expanded={row.expandable ? row.expanded : undefined}
                aria-selected={row.record ? row.record.record_id === selectedRecordId : undefined}
                tabIndex={focusIndex === index ? 0 : -1}
                title={row.label}
                onFocus={() => setFocusIndex(index)}
                onKeyDown={(event) => handleKeyDown(event, row, index)}
                onClick={() => row.record ? void selectRecord(row.record) : void toggleRow(row)}
                onDoubleClick={() => { if (row.record) onOpenRecord(row.record); }}
              >
                <span className="tree-disclosure" aria-hidden="true">{rowGlyph(row)}</span>
                <span className="tree-kind" aria-hidden="true">{row.kind === "database" ? "DB" : row.kind === "profile" ? "P" : row.kind === "table" ? "T" : row.kind === "folder" ? "▱" : row.kind === "record" ? "R" : ""}</span>
                <span className="tree-label">{row.label}</span>
              </div>
            );
          })}
        </div>
      </div>
      {!subsetMode ? <label className="ux-field tree-subset">Saved Subset<select className="ux-select" aria-label="Saved Subset" value={selectedSubsetId} onChange={(event) => applySubset(event.target.value)}><option value="">None</option>{subsets.map((subset) => <option key={subset.subset_id} value={subset.subset_id}>{subset.name}</option>)}</select></label> : null}
      <div className="materials-explorer-help ux-meta">Click selects a Record. Double-click opens its exact revision datasheet.</div>
    </div>
  );
}
