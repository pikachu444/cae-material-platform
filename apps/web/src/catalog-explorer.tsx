import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import {
  ApiError,
  bindCatalogRecordDomainRevision,
  createConfigurableCatalogLinkType,
  createConfigurableRecordLink,
  getCatalogWorkflowGraph,
  listCatalogExplorerChildren,
  listCatalogExplorerTables,
  listConfigurableCatalogLinkTypes,
  reviseConfigurableRecordLink,
  searchConfigurableCatalogRecords,
  type ApiConfig,
} from "./api";
import type {
  CatalogExplorerChildrenResponse,
  CatalogWorkflowGraphResponse,
  ConfigurableCatalogRecordResponse,
  ConfigurableLinkEndpoint,
  ConfigurableLinkTypeResponse,
  ConfigurableRecordLinkView,
  ConfigurableTableResponse,
  DomainBindingKind,
} from "./types";

interface CatalogExplorerProps {
  config: ApiConfig;
  initialRecordId?: string;
  initialRevisionId?: string;
  onNavigate: (path: string) => void;
  onOpenConnection: () => void;
}

function message(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "The Catalog Explorer operation could not be completed.";
}

function etag(link: ConfigurableRecordLinkView): string {
  const revision = link.current_revision;
  return `"revision:${revision.revision_no}:sha256:${revision.content_hash}"`;
}

function cacheKey(tableId: string, folderId: string | null): string {
  return `${tableId}:${folderId ?? "root"}`;
}

function shortRevision(value: string): string {
  return value.slice(0, 8);
}

export function CatalogExplorer({
  config,
  initialRecordId,
  initialRevisionId,
  onNavigate,
  onOpenConnection,
}: CatalogExplorerProps) {
  const [tables, setTables] = useState<ConfigurableTableResponse[]>([]);
  const [children, setChildren] = useState<Record<string, CatalogExplorerChildrenResponse>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [linkTypes, setLinkTypes] = useState<ConfigurableLinkTypeResponse[]>([]);
  const [graph, setGraph] = useState<CatalogWorkflowGraphResponse | null>(null);
  const [targetRecords, setTargetRecords] = useState<ConfigurableCatalogRecordResponse[]>([]);
  const [selectedLinkTypeId, setSelectedLinkTypeId] = useState("");
  const [selectedTargetId, setSelectedTargetId] = useState("");
  const [linkNote, setLinkNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [bindingDraft, setBindingDraft] = useState({
    kind: "material" as DomainBindingKind,
    objectId: "",
    revisionId: "",
  });
  const [typeDraft, setTypeDraft] = useState({
    key: "",
    name: "",
    sourceTableId: "",
    targetTableId: "",
    forwardLabel: "has related record",
    reverseLabel: "is related to",
    sourceCardinality: "many" as "one" | "many",
    targetCardinality: "many" as "one" | "many",
  });

  const selected = graph?.root ?? null;
  const selectedLinkType = useMemo(
    () => linkTypes.find((item) => item.link_type_id === selectedLinkTypeId) ?? null,
    [linkTypes, selectedLinkTypeId],
  );
  const tableNames = useMemo(
    () => new Map(tables.map((table) => [table.table_id, table.current_revision.content.name])),
    [tables],
  );

  const loadRoots = useCallback(async () => {
    try {
      const [tableResult, typeResult] = await Promise.all([
        listCatalogExplorerTables(config),
        listConfigurableCatalogLinkTypes(config),
      ]);
      setTables(tableResult.data.items);
      setLinkTypes(typeResult.data.items);
      setError(null);
    } catch (caught) {
      setError(message(caught));
    }
  }, [config]);

  const loadGraph = useCallback(
    async (recordId: string, revisionId: string) => {
      setBusy("graph");
      try {
        const result = await getCatalogWorkflowGraph(config, recordId, revisionId);
        setGraph(result.data);
        setSelectedLinkTypeId("");
        setSelectedTargetId("");
        setError(null);
      } catch (caught) {
        setError(message(caught));
      } finally {
        setBusy(null);
      }
    },
    [config],
  );

  useEffect(() => void loadRoots(), [loadRoots]);
  useEffect(() => {
    if (initialRecordId && initialRevisionId) {
      void loadGraph(initialRecordId, initialRevisionId);
    }
  }, [initialRecordId, initialRevisionId, loadGraph]);

  const toggleBranch = useCallback(
    async (tableId: string, folderId: string | null) => {
      const key = cacheKey(tableId, folderId);
      if (expanded.has(key)) {
        setExpanded((current) => {
          const next = new Set(current);
          next.delete(key);
          return next;
        });
        return;
      }
      setBusy(key);
      try {
        if (!children[key]) {
          const result = await listCatalogExplorerChildren(config, tableId, folderId);
          setChildren((current) => ({ ...current, [key]: result.data }));
        }
        setExpanded((current) => new Set(current).add(key));
        setError(null);
      } catch (caught) {
        setError(message(caught));
      } finally {
        setBusy(null);
      }
    },
    [children, config, expanded],
  );

  function openRecord(record: ConfigurableCatalogRecordResponse): void {
    const revisionId = record.current_revision.id;
    onNavigate(`/catalog/explorer/records/${record.record_id}/revisions/${revisionId}`);
    void loadGraph(record.record_id, revisionId);
  }

  function openEndpoint(endpoint: ConfigurableLinkEndpoint): void {
    if (endpoint.domain_binding) {
      onNavigate(endpoint.domain_binding.workbench_path);
      return;
    }
    onNavigate(
      `/catalog/explorer/records/${endpoint.record_id}/revisions/${endpoint.record_revision_id}`,
    );
    void loadGraph(endpoint.record_id, endpoint.record_revision_id);
  }

  async function bindDomainRevision(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selected) return;
    setBusy("binding");
    try {
      await bindCatalogRecordDomainRevision(config, selected.record_id, selected.record_revision_id, {
        kind: bindingDraft.kind,
        object_id: bindingDraft.objectId,
        revision_id: bindingDraft.revisionId,
      });
      await loadGraph(selected.record_id, selected.record_revision_id);
      setNotice("The Catalog Record revision now pins an exact governed domain revision.");
      setError(null);
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(null);
    }
  }

  function renderBranch(tableId: string, folderId: string | null, depth: number) {
    const key = cacheKey(tableId, folderId);
    if (!expanded.has(key)) return null;
    const branch = children[key];
    if (!branch) return <p className="tree-loading">Loading exact nodes…</p>;
    return (
      <div className="catalog-tree-branch" style={{ paddingLeft: `${depth * 16}px` }}>
        {branch.folders.map((folder) => {
          const folderKey = cacheKey(tableId, folder.folder_id);
          return (
            <div key={folder.folder_id}>
              <button
                className="tree-node folder-node"
                type="button"
                onClick={() => void toggleBranch(tableId, folder.folder_id)}
              >
                <span>{expanded.has(folderKey) ? "▾" : "▸"}</span>
                <span>{folder.content.name}</span>
                <small>r{folder.current_revision.revision_no}</small>
              </button>
              {renderBranch(tableId, folder.folder_id, depth + 1)}
            </div>
          );
        })}
        {branch.records.map((record) => (
          <button
            className={`tree-node record-node ${selected?.record_id === record.record_id ? "selected" : ""}`}
            type="button"
            key={record.record_id}
            onClick={() => openRecord(record)}
          >
            <span>◆</span>
            <span>{record.current_revision.content.name}</span>
            <small>r{record.current_revision.revision_no}</small>
          </button>
        ))}
        {!branch.folders.length && !branch.records.length ? (
          <p className="tree-empty">No direct child nodes.</p>
        ) : null}
      </div>
    );
  }

  async function chooseLinkType(linkTypeId: string): Promise<void> {
    setSelectedLinkTypeId(linkTypeId);
    setSelectedTargetId("");
    const definition = linkTypes.find((item) => item.link_type_id === linkTypeId);
    if (!definition) {
      setTargetRecords([]);
      return;
    }
    setBusy("targets");
    try {
      const result = await searchConfigurableCatalogRecords(config, {
        table_id: definition.current_revision.content.target_table_id,
        text: null,
        folder_id: null,
        discrete_filters: [],
        number_filters: [],
        facet_attribute_ids: [],
        limit: 100,
      });
      setTargetRecords(result.data.items);
      setError(null);
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(null);
    }
  }

  async function createLink(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!selected || !selectedLinkType || !selectedTargetId) return;
    const target = targetRecords.find((item) => item.record_id === selectedTargetId);
    if (!target) return;
    setBusy("link");
    try {
      await createConfigurableRecordLink(config, {
        classification: "internal",
        content: {
          link_type_id: selectedLinkType.link_type_id,
          link_type_revision_id: selectedLinkType.current_revision.id,
          source_record_id: selected.record_id,
          source_record_revision_id: selected.record_revision_id,
          target_record_id: target.record_id,
          target_record_revision_id: target.current_revision.id,
          active: true,
          note: linkNote.trim() || null,
        },
        change_reason: "Create revision-pinned Record Link in Workflow Explorer",
      });
      await loadGraph(selected.record_id, selected.record_revision_id);
      setNotice("Exact Record Link created. Neither endpoint follows latest.");
      setLinkNote("");
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(null);
    }
  }

  async function deactivateLink(link: ConfigurableRecordLinkView): Promise<void> {
    setBusy(link.record_link_id);
    try {
      await reviseConfigurableRecordLink(config, link.record_link_id, etag(link), {
        content: { ...link.current_revision.content, active: false },
        change_reason: "Deactivate Record Link without deleting exact revision history",
      });
      if (selected) await loadGraph(selected.record_id, selected.record_revision_id);
      setNotice("Link deactivated by appending a new immutable revision.");
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(null);
    }
  }

  async function createLinkType(event: FormEvent): Promise<void> {
    event.preventDefault();
    const source = tables.find((item) => item.table_id === typeDraft.sourceTableId);
    const target = tables.find((item) => item.table_id === typeDraft.targetTableId);
    if (!source || !target) return;
    setBusy("link-type");
    try {
      await createConfigurableCatalogLinkType(config, {
        classification: "internal",
        content: {
          key: typeDraft.key.trim(),
          name: typeDraft.name.trim(),
          source_table_id: source.table_id,
          source_table_revision_id: source.current_revision.id,
          target_table_id: target.table_id,
          target_table_revision_id: target.current_revision.id,
          forward_label: typeDraft.forwardLabel.trim(),
          reverse_label: typeDraft.reverseLabel.trim(),
          source_cardinality: typeDraft.sourceCardinality,
          target_cardinality: typeDraft.targetCardinality,
          description: null,
        },
        change_reason: "Create administrator-defined Catalog Link Type",
      });
      await loadRoots();
      setNotice("Link Type revision 1 created with exact Table revisions.");
      setTypeDraft((current) => ({ ...current, key: "", name: "" }));
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(null);
    }
  }

  const applicableTypes = selected
    ? linkTypes.filter(
        (item) => item.current_revision.content.source_table_id === selected.table_id,
      )
    : [];

  return (
    <main className="catalog-explorer-page">
      <section className="page-hero compact-hero">
        <div>
          <p className="eyebrow">T-51 · Material Information System navigation</p>
          <h1>Catalog &amp; Workflow Explorer</h1>
          <p>Browse lazy Table/Folder/Record nodes and follow links pinned to exact revisions.</p>
        </div>
        <div className="hero-actions">
          <button className="button secondary" type="button" onClick={() => onNavigate("/catalog/records")}>Records</button>
          <button className="button secondary" type="button" onClick={() => onNavigate("/catalog/schema")}>Schema</button>
        </div>
      </section>

      {error ? <div className="error-banner" role="alert">{error}<button type="button" onClick={onOpenConnection}>Connection</button></div> : null}
      {notice ? <div className="success-banner">{notice}</div> : null}

      <section className="dual-explorer-grid">
        <aside className="explorer-panel catalog-tree-panel">
          <p className="eyebrow">Catalog Explorer</p>
          <h2>Workspace</h2>
          <p className="muted">Table → Folder → Record</p>
          <div className="catalog-tree" aria-label="Catalog Explorer tree">
            {tables.map((table) => {
              const key = cacheKey(table.table_id, null);
              return (
                <div key={table.table_id}>
                  <button className="tree-node table-node" type="button" onClick={() => void toggleBranch(table.table_id, null)}>
                    <span>{expanded.has(key) ? "▾" : "▸"}</span>
                    <span>{table.current_revision.content.name}</span>
                    <small>r{table.current_revision.revision_no}</small>
                  </button>
                  {renderBranch(table.table_id, null, 1)}
                </div>
              );
            })}
          </div>
        </aside>

        <section className="explorer-panel workflow-panel">
          <p className="eyebrow">Material Workflow Explorer</p>
          {selected && graph ? (
            <>
              <nav className="record-breadcrumb" aria-label="Record breadcrumb">
                Workspace / {tableNames.get(selected.table_id) ?? "Table"} / {selected.name} / r{selected.revision_no}
              </nav>
              <div className="workflow-title-row">
                <div><h2>{selected.name}</h2><p className="muted">exact revision {shortRevision(selected.record_revision_id)}…</p></div>
                <span className="revision-chip">r{selected.revision_no}</span>
              </div>
              <div className="workflow-node-list">
                {graph.nodes.map((node) => (
                  <button type="button" className={`workflow-node ${node.record_id === selected.record_id && node.record_revision_id === selected.record_revision_id ? "root" : ""}`} key={`${node.record_id}:${node.record_revision_id}`} onClick={() => openEndpoint(node)}>
                    <span>{tableNames.get(node.table_id) ?? "Record"}</span>
                    <strong>{node.name}</strong>
                    <small>r{node.revision_no} · {shortRevision(node.record_revision_id)}…</small>
                    {node.domain_binding ? (
                      <small className="mapping-note">
                        {node.domain_binding.kind} · exact {shortRevision(node.domain_binding.revision_id)}…
                      </small>
                    ) : null}
                  </button>
                ))}
              </div>
              <h3>Forward and reverse links</h3>
              <div className="record-link-list">
                {graph.links.map((link) => {
                  const forward = link.source.record_id === selected.record_id && link.source.record_revision_id === selected.record_revision_id;
                  const other = forward ? link.target : link.source;
                  const label = forward ? link.link_type_revision.content.forward_label : link.link_type_revision.content.reverse_label;
                  return (
                    <article className="record-link-card" key={link.record_link_id}>
                      <div><span>{label}</span><strong>{other.name}</strong><small>exact r{other.revision_no} · {shortRevision(other.record_revision_id)}…</small></div>
                      <div className="link-card-actions">
                        <button type="button" className="button secondary" onClick={() => openEndpoint(other)}>Open</button>
                        <button type="button" className="button danger" disabled={busy === link.record_link_id} onClick={() => void deactivateLink(link)}>Deactivate</button>
                      </div>
                    </article>
                  );
                })}
                {!graph.links.length ? <p className="muted">No active exact-revision links.</p> : null}
              </div>
            </>
          ) : (
            <div className="empty-workflow"><h2>Select a Record</h2><p>Expand a Table and Folder to open its exact current revision.</p>{busy === "graph" ? <p>Loading workflow…</p> : null}</div>
          )}
        </section>

        <aside className="explorer-panel link-editor-panel">
          <p className="eyebrow">Domain revision binding</p>
          <h2>Open the real workbench</h2>
          {selected?.domain_binding ? (
            <div className="mapping-note">
              <strong>{selected.domain_binding.kind}</strong>
              <p>Exact revision {selected.domain_binding.revision_id}</p>
              <button
                type="button"
                className="button secondary"
                onClick={() => onNavigate(selected.domain_binding!.workbench_path)}
              >
                Open governed object
              </button>
            </div>
          ) : (
            <form onSubmit={(event) => void bindDomainRevision(event)}>
              <label>
                Domain object type
                <select
                  value={bindingDraft.kind}
                  onChange={(event) => setBindingDraft({ ...bindingDraft, kind: event.target.value as DomainBindingKind })}
                >
                  {(["material", "material_state", "specimen", "test_run", "test_data", "processing_output", "material_model", "neutral_material", "solver_card", "neutral_solver_card", "release"] as DomainBindingKind[]).map((kind) => (
                    <option value={kind} key={kind}>{kind.replaceAll("_", " ")}</option>
                  ))}
                </select>
              </label>
              <label>
                Stable object UUID
                <input required value={bindingDraft.objectId} onChange={(event) => setBindingDraft({ ...bindingDraft, objectId: event.target.value })} />
              </label>
              <label>
                Exact revision UUID
                <input required value={bindingDraft.revisionId} onChange={(event) => setBindingDraft({ ...bindingDraft, revisionId: event.target.value })} />
              </label>
              <button className="button primary" disabled={!selected || busy === "binding"}>
                {busy === "binding" ? "Binding…" : "Pin exact domain revision"}
              </button>
            </form>
          )}
          <hr />
          <p className="eyebrow">Typed link editor</p>
          <h2>Create exact link</h2>
          <form onSubmit={(event) => void createLink(event)}>
            <label>Link Type<select value={selectedLinkTypeId} onChange={(event) => void chooseLinkType(event.target.value)}><option value="">Select…</option>{applicableTypes.map((item) => <option value={item.link_type_id} key={item.link_type_id}>{item.current_revision.content.name}</option>)}</select></label>
            <label>Target exact revision<select value={selectedTargetId} onChange={(event) => setSelectedTargetId(event.target.value)}><option value="">Select…</option>{targetRecords.map((record) => <option value={record.record_id} key={record.record_id}>{record.current_revision.content.name} · r{record.current_revision.revision_no}</option>)}</select></label>
            <label>Note<textarea value={linkNote} onChange={(event) => setLinkNote(event.target.value)} /></label>
            {selectedLinkType ? <p className="mapping-note">{selectedLinkType.current_revision.content.forward_label} · source {selectedLinkType.current_revision.content.source_cardinality} / target {selectedLinkType.current_revision.content.target_cardinality}</p> : null}
            <button className="button primary" disabled={!selected || !selectedLinkType || !selectedTargetId || busy === "link"}>{busy === "link" ? "Linking…" : "Create revision-pinned link"}</button>
          </form>
        </aside>
      </section>

      <details className="admin-drawer">
        <summary>Administrator · define Link Type</summary>
        <form className="link-type-form" onSubmit={(event) => void createLinkType(event)}>
          <label>Stable key<input required pattern="[a-z][a-z0-9_]*" value={typeDraft.key} onChange={(event) => setTypeDraft({ ...typeDraft, key: event.target.value })} /></label>
          <label>Name<input required value={typeDraft.name} onChange={(event) => setTypeDraft({ ...typeDraft, name: event.target.value })} /></label>
          <label>Source Table<select required value={typeDraft.sourceTableId} onChange={(event) => setTypeDraft({ ...typeDraft, sourceTableId: event.target.value })}><option value="">Select…</option>{tables.map((table) => <option value={table.table_id} key={table.table_id}>{table.current_revision.content.name}</option>)}</select></label>
          <label>Target Table<select required value={typeDraft.targetTableId} onChange={(event) => setTypeDraft({ ...typeDraft, targetTableId: event.target.value })}><option value="">Select…</option>{tables.map((table) => <option value={table.table_id} key={table.table_id}>{table.current_revision.content.name}</option>)}</select></label>
          <label>Forward label<input required value={typeDraft.forwardLabel} onChange={(event) => setTypeDraft({ ...typeDraft, forwardLabel: event.target.value })} /></label>
          <label>Reverse label<input required value={typeDraft.reverseLabel} onChange={(event) => setTypeDraft({ ...typeDraft, reverseLabel: event.target.value })} /></label>
          <label>Outgoing per source<select value={typeDraft.sourceCardinality} onChange={(event) => setTypeDraft({ ...typeDraft, sourceCardinality: event.target.value as "one" | "many" })}><option value="many">Many</option><option value="one">One</option></select></label>
          <label>Incoming per target<select value={typeDraft.targetCardinality} onChange={(event) => setTypeDraft({ ...typeDraft, targetCardinality: event.target.value as "one" | "many" })}><option value="many">Many</option><option value="one">One</option></select></label>
          <button className="button primary" disabled={busy === "link-type"}>Create Link Type revision 1</button>
        </form>
      </details>
    </main>
  );
}
