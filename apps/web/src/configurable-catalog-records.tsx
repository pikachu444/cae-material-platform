import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  compareConfigurableCatalogRecordRevisions,
  createConfigurableCatalogFolder,
  createConfigurableCatalogRecord,
  createConfigurableCatalogSubset,
  getConfigurableCatalogRecord,
  listConfigurableCatalogAttributes,
  listConfigurableCatalogFolders,
  listConfigurableCatalogLayouts,
  listConfigurableCatalogRecordRevisions,
  listConfigurableCatalogSubsets,
  listConfigurableCatalogTables,
  reviseConfigurableCatalogRecord,
  searchConfigurableCatalogRecords,
  type ApiConfig,
} from "./api";
import type {
  ConfigurableAttributeResponse,
  ConfigurableCatalogFolderResponse,
  ConfigurableCatalogRecordComparison,
  ConfigurableCatalogRecordContent,
  ConfigurableCatalogRecordResponse,
  ConfigurableCatalogRecordSearchResponse,
  ConfigurableLayoutResponse,
  ConfigurableRecordValue,
  ConfigurableSubsetResponse,
  ConfigurableTableResponse,
  DataClassification,
} from "./types";

interface DraftValue {
  enabled: boolean;
  primary: string;
  secondary: string;
  normalized: string;
}

function message(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "The configurable Catalog operation could not be completed.";
}

function valueLabel(value: ConfigurableRecordValue): string {
  if (value.data_type === "number") {
    return `${value.original_value} ${value.original_unit_string} → ${value.normalized_value} ${value.normalized_unit}`;
  }
  if (value.data_type === "file" || value.data_type === "curve") {
    return `artifact ${value.artifact_id.slice(0, 8)}… · ${value.artifact_sha256.slice(0, 12)}…`;
  }
  if (value.data_type === "record_reference") {
    return `record ${value.target_record_id.slice(0, 8)}… @ ${value.target_record_revision_id.slice(0, 8)}…`;
  }
  if (value.data_type === "boolean") {
    return value.value ? "Yes" : "No";
  }
  return String(value.value);
}

function emptyDraft(attribute: ConfigurableAttributeResponse): DraftValue {
  const content = attribute.current_revision.content;
  return {
    enabled: content.required,
    primary: content.data_type === "boolean" ? "false" : "",
    secondary: content.data_type === "number" ? (content.normalized_unit ?? "") : "",
    normalized: "",
  };
}

function valueDraft(value: ConfigurableRecordValue): DraftValue {
  if (value.data_type === "number") {
    return {
      enabled: true,
      primary: value.original_value,
      secondary: value.original_unit_string,
      normalized: value.normalized_value,
    };
  }
  if (value.data_type === "file" || value.data_type === "curve") {
    return {
      enabled: true,
      primary: value.artifact_id,
      secondary: value.artifact_sha256,
      normalized: "",
    };
  }
  if (value.data_type === "record_reference") {
    return {
      enabled: true,
      primary: value.target_record_id,
      secondary: value.target_record_revision_id,
      normalized: "",
    };
  }
  return { enabled: true, primary: String(value.value), secondary: "", normalized: "" };
}

function buildValue(
  attribute: ConfigurableAttributeResponse,
  draft: DraftValue,
): ConfigurableRecordValue | null {
  if (!draft.enabled) {
    return null;
  }
  const definition = attribute.current_revision.content;
  const common = {
    attribute_definition_id: attribute.attribute_definition_id,
    attribute_definition_revision_id: attribute.current_revision.id,
  };
  if (definition.data_type === "number") {
    return {
      ...common,
      data_type: "number",
      original_value: draft.primary,
      original_unit_string: draft.secondary,
      normalized_value: draft.normalized || draft.primary,
      normalized_unit: definition.normalized_unit ?? "",
      quantity_semantics: definition.quantity_semantics ?? "",
    };
  }
  if (definition.data_type === "integer") {
    return { ...common, data_type: "integer", value: Number(draft.primary) };
  }
  if (definition.data_type === "boolean") {
    return { ...common, data_type: "boolean", value: draft.primary === "true" };
  }
  if (definition.data_type === "date") {
    return { ...common, data_type: "date", value: draft.primary };
  }
  if (definition.data_type === "discrete") {
    return { ...common, data_type: "discrete", value: draft.primary };
  }
  if (definition.data_type === "file" || definition.data_type === "curve") {
    return {
      ...common,
      data_type: definition.data_type,
      artifact_id: draft.primary,
      artifact_sha256: draft.secondary,
    };
  }
  if (definition.data_type === "record_reference") {
    return {
      ...common,
      data_type: "record_reference",
      target_record_id: draft.primary,
      target_record_revision_id: draft.secondary,
    };
  }
  return { ...common, data_type: "text", value: draft.primary };
}

export function ConfigurableCatalogRecords({
  config,
  onNavigate,
  onOpenConnection,
}: {
  config: ApiConfig;
  onNavigate: (path: string) => void;
  onOpenConnection: () => void;
}) {
  const [tables, setTables] = useState<ConfigurableTableResponse[]>([]);
  const [tableId, setTableId] = useState("");
  const [attributes, setAttributes] = useState<ConfigurableAttributeResponse[]>([]);
  const [layouts, setLayouts] = useState<ConfigurableLayoutResponse[]>([]);
  const [layoutId, setLayoutId] = useState("");
  const [folders, setFolders] = useState<ConfigurableCatalogFolderResponse[]>([]);
  const [subsets, setSubsets] = useState<ConfigurableSubsetResponse[]>([]);
  const [results, setResults] = useState<ConfigurableCatalogRecordSearchResponse | null>(null);
  const [selected, setSelected] = useState<ConfigurableCatalogRecordResponse | null>(null);
  const [selectedEtag, setSelectedEtag] = useState("");
  const [revisionCount, setRevisionCount] = useState(0);
  const [comparison, setComparison] = useState<ConfigurableCatalogRecordComparison | null>(null);
  const [query, setQuery] = useState("");
  const [folderFilter, setFolderFilter] = useState("");
  const [facetFilters, setFacetFilters] = useState<Record<string, string>>({});
  const [numberAttributeId, setNumberAttributeId] = useState("");
  const [numberMinimum, setNumberMinimum] = useState("");
  const [numberMaximum, setNumberMaximum] = useState("");
  const [recordName, setRecordName] = useState("");
  const [externalKey, setExternalKey] = useState("");
  const [description, setDescription] = useState("");
  const [recordFolderId, setRecordFolderId] = useState("");
  const [classification, setClassification] = useState<DataClassification>("internal");
  const [drafts, setDrafts] = useState<Record<string, DraftValue>>({});
  const [folderName, setFolderName] = useState("");
  const [folderParentId, setFolderParentId] = useState("");
  const [subsetName, setSubsetName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const table = useMemo(
    () => tables.find((item) => item.table_id === tableId) ?? null,
    [tableId, tables],
  );
  const layout = useMemo(
    () => layouts.find((item) => item.layout_id === layoutId) ?? layouts[0] ?? null,
    [layoutId, layouts],
  );
  const orderedAttributes = useMemo(() => {
    if (!layout) {
      return attributes;
    }
    const positions = new Map(
      layout.items.map((item) => [item.attribute_definition_id, item.ordinal]),
    );
    return [...attributes].sort(
      (left, right) =>
        (positions.get(left.attribute_definition_id) ?? Number.MAX_SAFE_INTEGER) -
        (positions.get(right.attribute_definition_id) ?? Number.MAX_SAFE_INTEGER),
    );
  }, [attributes, layout]);
  const numberAttributes = useMemo(
    () =>
      attributes.filter(
        (attribute) => attribute.current_revision.content.data_type === "number",
      ),
    [attributes],
  );
  const discreteAttributes = useMemo(
    () =>
      attributes.filter(
        (attribute) => attribute.current_revision.content.data_type === "discrete",
      ),
    [attributes],
  );

  const loadTables = useCallback(async () => {
    if (!config.accessToken.trim()) return;
    try {
      const response = await listConfigurableCatalogTables(config);
      setTables(response.data.items);
      setTableId((current) =>
        response.data.items.some((item) => item.table_id === current)
          ? current
          : (response.data.items[0]?.table_id ?? ""),
      );
    } catch (caught) {
      setError(message(caught));
    }
  }, [config]);

  const loadDefinition = useCallback(async () => {
    if (!tableId || !config.accessToken.trim()) return;
    setBusy(true);
    try {
      const [attributeResponse, layoutResponse, folderResponse, subsetResponse] =
        await Promise.all([
          listConfigurableCatalogAttributes(config, tableId),
          listConfigurableCatalogLayouts(config, tableId),
          listConfigurableCatalogFolders(config, tableId),
          listConfigurableCatalogSubsets(config, tableId),
        ]);
      setAttributes(attributeResponse.data.items);
      setLayouts(layoutResponse.data.items);
      setLayoutId((current) =>
        layoutResponse.data.items.some((item) => item.layout_id === current)
          ? current
          : (layoutResponse.data.items[0]?.layout_id ?? ""),
      );
      setFolders(folderResponse.data.items);
      setSubsets(subsetResponse.data.items);
      setDrafts(
        Object.fromEntries(
          attributeResponse.data.items.map((attribute) => [
            attribute.attribute_definition_id,
            emptyDraft(attribute),
          ]),
        ),
      );
      setSelected(null);
      setComparison(null);
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }, [config, tableId]);

  const search = useCallback(async () => {
    if (!tableId || !config.accessToken.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const response = await searchConfigurableCatalogRecords(config, {
        table_id: tableId,
        text: query.trim() || null,
        folder_id: folderFilter || null,
        discrete_filters: Object.entries(facetFilters).map(([attributeId, value]) => ({
          attribute_definition_id: attributeId,
          values: [value],
        })),
        number_filters:
          numberAttributeId && (numberMinimum || numberMaximum)
            ? [
                {
                  attribute_definition_id: numberAttributeId,
                  minimum: numberMinimum || null,
                  maximum: numberMaximum || null,
                },
              ]
            : [],
        facet_attribute_ids: discreteAttributes.map(
          (attribute) => attribute.attribute_definition_id,
        ),
        limit: 50,
      });
      setResults(response.data);
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }, [
    config,
    discreteAttributes,
    facetFilters,
    folderFilter,
    numberAttributeId,
    numberMaximum,
    numberMinimum,
    query,
    tableId,
  ]);

  useEffect(() => void loadTables(), [loadTables]);
  useEffect(() => void loadDefinition(), [loadDefinition]);
  useEffect(() => void search(), [search]);

  function resetEditor() {
    setSelected(null);
    setSelectedEtag("");
    setRevisionCount(0);
    setComparison(null);
    setRecordName("");
    setExternalKey("");
    setDescription("");
    setRecordFolderId("");
    setDrafts(
      Object.fromEntries(
        attributes.map((attribute) => [attribute.attribute_definition_id, emptyDraft(attribute)]),
      ),
    );
  }

  async function selectRecord(recordId: string) {
    setBusy(true);
    try {
      const [detail, revisions] = await Promise.all([
        getConfigurableCatalogRecord(config, recordId),
        listConfigurableCatalogRecordRevisions(config, recordId),
      ]);
      const record = detail.data;
      setSelected(record);
      setSelectedEtag(detail.etag ?? "");
      setRevisionCount(revisions.data.items.length);
      setComparison(null);
      setRecordName(record.current_revision.content.name);
      setExternalKey(record.current_revision.content.external_key ?? "");
      setDescription(record.current_revision.content.description ?? "");
      setRecordFolderId(record.current_revision.content.folder_id ?? "");
      const valueMap = new Map(
        record.current_revision.content.values.map((value) => [
          value.attribute_definition_id,
          value,
        ]),
      );
      setDrafts(
        Object.fromEntries(
          attributes.map((attribute) => {
            const value = valueMap.get(attribute.attribute_definition_id);
            return [
              attribute.attribute_definition_id,
              value ? valueDraft(value) : emptyDraft(attribute),
            ];
          }),
        ),
      );
      if (revisions.data.items.length > 1) {
        const compared = await compareConfigurableCatalogRecordRevisions(
          config,
          recordId,
          revisions.data.items[0].id,
          revisions.data.items.at(-1)?.id ?? revisions.data.items[0].id,
        );
        setComparison(compared.data);
      }
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  function updateDraft(attributeId: string, patch: Partial<DraftValue>) {
    setDrafts((current) => ({
      ...current,
      [attributeId]: {
        ...(current[attributeId] ?? {
          enabled: false,
          primary: "",
          secondary: "",
          normalized: "",
        }),
        ...patch,
      },
    }));
  }

  async function saveRecord(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!table) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const folder = folders.find((item) => item.folder_id === recordFolderId) ?? null;
      const values = orderedAttributes
        .map((attribute) => buildValue(attribute, drafts[attribute.attribute_definition_id]))
        .filter((value): value is ConfigurableRecordValue => value !== null);
      const content: ConfigurableCatalogRecordContent = {
        table_revision_id: table.current_revision.id,
        name: recordName.trim(),
        external_key: externalKey.trim() || null,
        description: description.trim() || null,
        folder_id: folder?.folder_id ?? null,
        folder_revision_id: folder?.current_revision.id ?? null,
        values,
      };
      const result = selected
        ? await reviseConfigurableCatalogRecord(config, selected.record_id, selectedEtag, {
            content,
            change_reason: "Revise configurable Catalog datasheet",
          })
        : await createConfigurableCatalogRecord(config, table.table_id, {
            classification,
            content,
            change_reason: "Create configurable Catalog record",
          });
      setNotice(
        `${result.data.current_revision.content.name} revision ${result.data.current_revision.revision_no} saved.`,
      );
      await search();
      await selectRecord(result.data.record_id);
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  async function createFolder(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!table) return;
    setBusy(true);
    try {
      const parent = folders.find((item) => item.folder_id === folderParentId) ?? null;
      await createConfigurableCatalogFolder(config, table.table_id, {
        classification,
        content: {
          table_revision_id: table.current_revision.id,
          name: folderName.trim(),
          description: null,
          parent_folder_id: parent?.folder_id ?? null,
          parent_folder_revision_id: parent?.current_revision.id ?? null,
        },
        change_reason: "Create Catalog Folder",
      });
      setFolderName("");
      setNotice("Folder revision created.");
      await loadDefinition();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  async function saveSubset() {
    if (!table || !subsetName.trim()) return;
    setBusy(true);
    try {
      await createConfigurableCatalogSubset(config, table.table_id, {
        table_revision_id: table.current_revision.id,
        name: subsetName.trim(),
        description: "Saved from Catalog record search",
        filter_definition: {
          text: query.trim() || null,
          folder_id: folderFilter || null,
          discrete_filters: facetFilters,
          number_attribute_id: numberAttributeId || null,
          number_minimum: numberMinimum || null,
          number_maximum: numberMaximum || null,
        },
        change_reason: "Save Catalog record search as Subset",
      });
      setSubsetName("");
      setNotice("Search saved as an immutable Subset revision.");
      await loadDefinition();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  function applySubset(subset: ConfigurableSubsetResponse) {
    const filter = subset.filter_definition ?? {};
    setQuery(typeof filter.text === "string" ? filter.text : "");
    setFolderFilter(typeof filter.folder_id === "string" ? filter.folder_id : "");
    setFacetFilters(
      filter.discrete_filters && typeof filter.discrete_filters === "object"
        ? (filter.discrete_filters as Record<string, string>)
        : {},
    );
    setNumberAttributeId(
      typeof filter.number_attribute_id === "string" ? filter.number_attribute_id : "",
    );
    setNumberMinimum(typeof filter.number_minimum === "string" ? filter.number_minimum : "");
    setNumberMaximum(typeof filter.number_maximum === "string" ? filter.number_maximum : "");
  }

  if (!config.accessToken.trim()) {
    return (
      <section className="hero-card">
        <p className="eyebrow">Configurable Catalog</p>
        <h1>Connect a Catalog user identity</h1>
        <button className="button primary" type="button" onClick={onOpenConnection}>
          Open connection
        </button>
      </section>
    );
  }

  return (
    <div className="catalog-record-workbench">
      <section className="hero-card compact-hero catalog-record-hero">
        <div>
          <p className="eyebrow">T-50 · Configurable Material Information System</p>
          <h1>Catalog records</h1>
          <p>Search typed records, edit Layout-driven datasheets and compare exact revisions.</p>
        </div>
        <div className="hero-actions">
          <button className="button secondary" type="button" onClick={() => onNavigate("/catalog/explorer")}>
            Explorer
          </button>
          <button className="button secondary" type="button" onClick={() => onNavigate("/catalog/schema")}>
            Schema designer
          </button>
        </div>
      </section>
      {error ? <div className="error-banner">{error}</div> : null}
      {notice ? <div className="success-banner">{notice}</div> : null}

      <section className="content-card catalog-search-panel">
        <div className="form-grid">
          <label>
            Table
            <select value={tableId} onChange={(event) => setTableId(event.target.value)}>
              {tables.map((item) => (
                <option key={item.table_id} value={item.table_id}>{item.current_revision.content.name}</option>
              ))}
            </select>
          </label>
          <label>
            Full-text and Attribute text
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="name, key, description, maker…" />
          </label>
          <label>
            Folder
            <select value={folderFilter} onChange={(event) => setFolderFilter(event.target.value)}>
              <option value="">All folders</option>
              {folders.map((folder) => <option key={folder.folder_id} value={folder.folder_id}>{folder.content.name}</option>)}
            </select>
          </label>
          <label>
            Layout
            <select value={layoutId} onChange={(event) => setLayoutId(event.target.value)}>
              {layouts.map((item) => <option key={item.layout_id} value={item.layout_id}>{item.name}</option>)}
            </select>
          </label>
        </div>
        <div className="range-filter-row">
          <select value={numberAttributeId} onChange={(event) => setNumberAttributeId(event.target.value)}>
            <option value="">No numeric range</option>
            {numberAttributes.map((attribute) => <option key={attribute.attribute_definition_id} value={attribute.attribute_definition_id}>{attribute.current_revision.content.name}</option>)}
          </select>
          <input value={numberMinimum} onChange={(event) => setNumberMinimum(event.target.value)} placeholder="Normalized min" />
          <input value={numberMaximum} onChange={(event) => setNumberMaximum(event.target.value)} placeholder="Normalized max" />
          <button className="button primary" type="button" onClick={() => void search()} disabled={busy}>Search</button>
        </div>
        <div className="saved-subset-row">
          <span>Saved Subsets</span>
          {subsets.map((subset) => <button className="filter-chip" type="button" key={subset.subset_id} onClick={() => applySubset(subset)}>{subset.name}</button>)}
          <input value={subsetName} onChange={(event) => setSubsetName(event.target.value)} placeholder="Save current search as…" />
          <button className="text-button" type="button" onClick={() => void saveSubset()}>Save</button>
        </div>
      </section>

      <div className="catalog-record-grid">
        <aside className="content-card catalog-facets">
          <div className="section-heading"><div><p className="eyebrow">Facets</p><h2>{results?.total_count ?? 0} records</h2></div></div>
          {discreteAttributes.map((attribute) => {
            const buckets = results?.facets.filter((item) => item.attribute_definition_id === attribute.attribute_definition_id) ?? [];
            return <div className="facet-group" key={attribute.attribute_definition_id}><strong>{attribute.current_revision.content.name}</strong>{buckets.map((bucket) => <button className={facetFilters[attribute.attribute_definition_id] === bucket.value ? "facet-row active" : "facet-row"} type="button" key={bucket.value} onClick={() => setFacetFilters((current) => current[attribute.attribute_definition_id] === bucket.value ? Object.fromEntries(Object.entries(current).filter(([key]) => key !== attribute.attribute_definition_id)) : { ...current, [attribute.attribute_definition_id]: bucket.value })}><span>{bucket.value}</span><small>{bucket.count}</small></button>)}</div>;
          })}
          <div className="folder-maker">
            <h3>New Folder</h3>
            <form className="form-stack" onSubmit={(event) => void createFolder(event)}>
              <input value={folderName} onChange={(event) => setFolderName(event.target.value)} placeholder="Folder name" required />
              <select value={folderParentId} onChange={(event) => setFolderParentId(event.target.value)}><option value="">Root folder</option>{folders.map((folder) => <option value={folder.folder_id} key={folder.folder_id}>{folder.content.name}</option>)}</select>
              <button className="button secondary" type="submit" disabled={busy}>Create Folder</button>
            </form>
          </div>
        </aside>

        <section className="content-card catalog-record-list">
          <div className="section-heading"><div><p className="eyebrow">Search results</p><h2>{table?.current_revision.content.name ?? "Select a Table"}</h2></div><button className="button secondary" type="button" onClick={resetEditor}>New record</button></div>
          <div className="record-result-table">
            {results?.items.map((record) => <button className={selected?.record_id === record.record_id ? "record-result active" : "record-result"} type="button" key={record.record_id} onClick={() => void selectRecord(record.record_id)}><span><strong>{record.current_revision.content.name}</strong><small>{record.current_revision.content.external_key ?? "No external key"}</small></span><span>r{record.current_revision.revision_no}</span></button>)}
            {!results?.items.length ? <p className="muted">No records match this typed query.</p> : null}
          </div>
        </section>

        <section className="content-card catalog-datasheet">
          <div className="section-heading"><div><p className="eyebrow">{layout?.name ?? "Datasheet"}</p><h2>{selected ? `Edit revision ${selected.current_revision.revision_no + 1}` : "Create Record"}</h2></div>{selected ? <small>{revisionCount} revisions</small> : null}</div>
          <form className="form-stack" onSubmit={(event) => void saveRecord(event)}>
            <div className="form-grid">
              <label>Name<input value={recordName} onChange={(event) => setRecordName(event.target.value)} required /></label>
              <label>External key<input value={externalKey} onChange={(event) => setExternalKey(event.target.value)} /></label>
              <label>Folder<select value={recordFolderId} onChange={(event) => setRecordFolderId(event.target.value)}><option value="">Unfiled</option>{folders.map((folder) => <option key={folder.folder_id} value={folder.folder_id}>{folder.content.name}</option>)}</select></label>
              {!selected ? <label>Classification<select value={classification} onChange={(event) => setClassification(event.target.value as DataClassification)}><option value="internal">Internal</option><option value="confidential">Confidential</option><option value="restricted">Restricted</option></select></label> : null}
            </div>
            <label>Description<textarea value={description} onChange={(event) => setDescription(event.target.value)} /></label>
            <div className="datasheet-fields">
              {orderedAttributes.map((attribute) => {
                const definition = attribute.current_revision.content;
                const draft = drafts[attribute.attribute_definition_id] ?? emptyDraft(attribute);
                return <fieldset key={attribute.attribute_definition_id} className="datasheet-field"><legend>{definition.name}{definition.required ? " *" : ""}</legend><label className="checkbox-label"><input type="checkbox" checked={draft.enabled} disabled={definition.required} onChange={(event) => updateDraft(attribute.attribute_definition_id, { enabled: event.target.checked })} />Include value</label>{draft.enabled ? <AttributeEditor attribute={attribute} draft={draft} update={(patch) => updateDraft(attribute.attribute_definition_id, patch)} /> : null}<small>{definition.quantity_semantics ?? definition.data_type}{definition.normalized_unit ? ` · normalized ${definition.normalized_unit}` : ""}</small></fieldset>;
              })}
            </div>
            <button className="button primary" type="submit" disabled={busy || !recordName.trim()}>{selected ? "Save new immutable revision" : "Create Record revision 1"}</button>
          </form>
          {selected ? <div className="revision-summary"><h3>Current exact values</h3>{selected.current_revision.content.values.map((value) => { const attribute = attributes.find((item) => item.attribute_definition_id === value.attribute_definition_id); return <div className="revision-value-row" key={value.attribute_definition_id}><strong>{attribute?.current_revision.content.name ?? value.attribute_definition_id}</strong><span>{valueLabel(value)}</span></div>; })}</div> : null}
          {comparison ? <div className="comparison-panel"><h3>Revision 1 → {comparison.to_revision.revision_no}</h3>{comparison.value_differences.filter((item) => item.status !== "unchanged").map((difference) => { const attribute = attributes.find((item) => item.attribute_definition_id === difference.attribute_definition_id); return <div className="comparison-row" key={difference.attribute_definition_id}><strong>{attribute?.current_revision.content.name ?? "Attribute"}</strong><span className={`status-badge ${difference.status === "changed" ? "warning" : "neutral"}`}>{difference.status}</span><small>{difference.before ? valueLabel(difference.before) : "—"} → {difference.after ? valueLabel(difference.after) : "—"}</small></div>; })}</div> : null}
        </section>
      </div>
    </div>
  );
}

function AttributeEditor({
  attribute,
  draft,
  update,
}: {
  attribute: ConfigurableAttributeResponse;
  draft: DraftValue;
  update: (patch: Partial<DraftValue>) => void;
}) {
  const definition = attribute.current_revision.content;
  if (definition.data_type === "boolean") {
    return <select value={draft.primary} onChange={(event) => update({ primary: event.target.value })}><option value="false">No</option><option value="true">Yes</option></select>;
  }
  if (definition.data_type === "discrete") {
    return <select value={draft.primary} onChange={(event) => update({ primary: event.target.value })} required={definition.required}><option value="">Select…</option>{definition.allowed_values.map((value) => <option value={value} key={value}>{value}</option>)}</select>;
  }
  if (definition.data_type === "number") {
    return <div className="number-value-grid"><input type="number" step="any" value={draft.primary} onChange={(event) => update({ primary: event.target.value })} placeholder="Original value" required={definition.required} /><input value={draft.secondary} onChange={(event) => update({ secondary: event.target.value })} placeholder="Original unit string" required={definition.required} /><input type="number" step="any" value={draft.normalized} onChange={(event) => update({ normalized: event.target.value })} placeholder={`Normalized value (${definition.normalized_unit ?? "unit"})`} required={definition.required} /></div>;
  }
  if (definition.data_type === "file" || definition.data_type === "curve") {
    return <div className="number-value-grid"><input value={draft.primary} onChange={(event) => update({ primary: event.target.value })} placeholder="Artifact UUID" required={definition.required} /><input value={draft.secondary} onChange={(event) => update({ secondary: event.target.value })} placeholder="Artifact SHA-256" required={definition.required} /></div>;
  }
  if (definition.data_type === "record_reference") {
    return <div className="number-value-grid"><input value={draft.primary} onChange={(event) => update({ primary: event.target.value })} placeholder="Target Record UUID" required={definition.required} /><input value={draft.secondary} onChange={(event) => update({ secondary: event.target.value })} placeholder="Exact target revision UUID" required={definition.required} /></div>;
  }
  return <input type={definition.data_type === "date" ? "date" : definition.data_type === "integer" ? "number" : "text"} value={draft.primary} onChange={(event) => update({ primary: event.target.value })} required={definition.required} />;
}
