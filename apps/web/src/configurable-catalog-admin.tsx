import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  createConfigurableCatalogAttribute,
  createConfigurableCatalogLayout,
  createConfigurableCatalogSubset,
  createConfigurableCatalogTable,
  listConfigurableCatalogAttributes,
  listConfigurableCatalogLayouts,
  listConfigurableCatalogSubsets,
  listConfigurableCatalogTables,
  type ApiConfig,
} from "./api";
import type {
  ConfigurableAttributeDataType,
  ConfigurableAttributeResponse,
  ConfigurableLayoutResponse,
  ConfigurableSubsetResponse,
  ConfigurableTableResponse,
  DataClassification,
} from "./types";

const dataTypes: Array<{ value: ConfigurableAttributeDataType; label: string }> = [
  { value: "number", label: "Number with unit" },
  { value: "integer", label: "Integer" },
  { value: "text", label: "Text" },
  { value: "boolean", label: "Boolean" },
  { value: "date", label: "Date" },
  { value: "discrete", label: "Discrete choice" },
  { value: "file", label: "File artifact" },
  { value: "curve", label: "Curve/table artifact" },
  { value: "record_reference", label: "Record reference" },
];

function message(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "The Catalog schema operation could not be completed.";
}

export function ConfigurableCatalogAdmin({
  config,
  onOpenConnection,
}: {
  config: ApiConfig;
  onOpenConnection: () => void;
}) {
  const [tables, setTables] = useState<ConfigurableTableResponse[]>([]);
  const [selectedTableId, setSelectedTableId] = useState("");
  const [attributes, setAttributes] = useState<ConfigurableAttributeResponse[]>([]);
  const [layouts, setLayouts] = useState<ConfigurableLayoutResponse[]>([]);
  const [subsets, setSubsets] = useState<ConfigurableSubsetResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [tableKey, setTableKey] = useState("materials");
  const [tableName, setTableName] = useState("Materials");
  const [tableDescription, setTableDescription] = useState(
    "Configurable material datasheets and linked engineering records.",
  );
  const [classification, setClassification] = useState<DataClassification>("internal");

  const [attributeKey, setAttributeKey] = useState("manufacturer");
  const [attributeName, setAttributeName] = useState("Manufacturer");
  const [attributeType, setAttributeType] = useState<ConfigurableAttributeDataType>("text");
  const [required, setRequired] = useState(false);
  const [quantitySemantics, setQuantitySemantics] = useState("");
  const [normalizedUnit, setNormalizedUnit] = useState("");
  const [allowedValues, setAllowedValues] = useState("");
  const [referenceTableId, setReferenceTableId] = useState("");

  const selectedTable = useMemo(
    () => tables.find((item) => item.table_id === selectedTableId) ?? null,
    [selectedTableId, tables],
  );

  const loadTables = useCallback(async () => {
    if (!config.accessToken.trim()) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await listConfigurableCatalogTables(config);
      setTables(result.data.items);
      setSelectedTableId((current) =>
        result.data.items.some((item) => item.table_id === current)
          ? current
          : (result.data.items[0]?.table_id ?? ""),
      );
    } catch (caught) {
      setError(message(caught));
    } finally {
      setLoading(false);
    }
  }, [config]);

  const loadDefinition = useCallback(async () => {
    if (!selectedTableId || !config.accessToken.trim()) {
      setAttributes([]);
      setLayouts([]);
      setSubsets([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [attributeResult, layoutResult, subsetResult] = await Promise.all([
        listConfigurableCatalogAttributes(config, selectedTableId),
        listConfigurableCatalogLayouts(config, selectedTableId),
        listConfigurableCatalogSubsets(config, selectedTableId),
      ]);
      setAttributes(attributeResult.data.items);
      setLayouts(layoutResult.data.items);
      setSubsets(subsetResult.data.items);
    } catch (caught) {
      setError(message(caught));
    } finally {
      setLoading(false);
    }
  }, [config, selectedTableId]);

  useEffect(() => {
    void loadTables();
  }, [loadTables]);

  useEffect(() => {
    void loadDefinition();
  }, [loadDefinition]);

  async function createTable(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const result = await createConfigurableCatalogTable(config, {
        classification,
        content: {
          key: tableKey.trim(),
          name: tableName.trim(),
          description: tableDescription.trim() || null,
        },
        change_reason: "Create administrator-defined Catalog Table",
      });
      setNotice(`${result.data.current_revision.content.name} Table revision 1 created.`);
      await loadTables();
      setSelectedTableId(result.data.table_id);
    } catch (caught) {
      setError(message(caught));
    } finally {
      setSaving(false);
    }
  }

  async function createAttribute(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTable) {
      return;
    }
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const choices = allowedValues
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      const result = await createConfigurableCatalogAttribute(config, selectedTable.table_id, {
        content: {
          table_revision_id: selectedTable.current_revision.id,
          key: attributeKey.trim(),
          name: attributeName.trim(),
          data_type: attributeType,
          required,
          quantity_semantics: quantitySemantics.trim() || null,
          normalized_unit: normalizedUnit.trim() || null,
          minimum_number: null,
          maximum_number: null,
          minimum_length: null,
          maximum_length: null,
          pattern: null,
          allowed_values: attributeType === "discrete" ? choices : [],
          reference_table_id:
            attributeType === "record_reference" ? referenceTableId || null : null,
          help_text: null,
        },
        change_reason: "Add typed Attribute Definition",
      });
      setNotice(`${result.data.current_revision.content.name} Attribute revision 1 created.`);
      await loadDefinition();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setSaving(false);
    }
  }

  async function createDefaultLayout() {
    if (!selectedTable || !attributes.length) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createConfigurableCatalogLayout(config, selectedTable.table_id, {
        table_revision_id: selectedTable.current_revision.id,
        name: "Engineering datasheet",
        description: "Default administrator-defined datasheet layout.",
        items: attributes.map((attribute, ordinal) => ({
          attribute_definition_id: attribute.attribute_definition_id,
          attribute_definition_revision_id: attribute.current_revision.id,
          section: "General",
          ordinal,
        })),
        change_reason: "Create default Catalog datasheet Layout",
      });
      setNotice("Engineering datasheet Layout created from the current Attribute revisions.");
      await loadDefinition();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setSaving(false);
    }
  }

  async function createAllRecordsSubset() {
    if (!selectedTable) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createConfigurableCatalogSubset(config, selectedTable.table_id, {
        table_revision_id: selectedTable.current_revision.id,
        name: "All records",
        description: "Unfiltered starting subset for this Table.",
        filter_definition: {},
        change_reason: "Create initial saved Catalog Subset",
      });
      setNotice("All records Subset revision 1 created.");
      await loadDefinition();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setSaving(false);
    }
  }

  if (!config.accessToken.trim()) {
    return (
      <section className="hero-card">
        <p className="eyebrow">Catalog administration</p>
        <h1>Connect an Administrator identity</h1>
        <p>Create configurable Tables, typed Attributes, datasheet Layouts and saved Subsets.</p>
        <button className="button primary" type="button" onClick={onOpenConnection}>
          Open connection
        </button>
      </section>
    );
  }

  return (
    <div className="catalog-schema-workbench">
      <section className="hero-card compact-hero">
        <p className="eyebrow">T-49 · Configurable Material Information System</p>
        <h1>Catalog schema designer</h1>
        <p>
          Add governed record types and typed attributes without a database migration. Published
          definitions remain immutable revisions.
        </p>
      </section>

      {error ? <div className="error-banner">{error}</div> : null}
      {notice ? <div className="success-banner">{notice}</div> : null}

      <div className="detail-grid">
        <section className="content-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Table definitions</p>
              <h2>{tables.length} configurable Tables</h2>
            </div>
            <button className="text-button" type="button" onClick={() => void loadTables()}>
              Refresh
            </button>
          </div>
          {loading && !tables.length ? <p className="muted">Loading schema…</p> : null}
          <div className="schema-table-list">
            {tables.map((table) => (
              <button
                className={table.table_id === selectedTableId ? "schema-table-row active" : "schema-table-row"}
                type="button"
                key={table.table_id}
                onClick={() => setSelectedTableId(table.table_id)}
              >
                <strong>{table.current_revision.content.name}</strong>
                <span>{table.current_revision.content.key}</span>
                <small>r{table.current_revision.revision_no}</small>
              </button>
            ))}
            {!tables.length ? <p className="muted">Create the first record Table.</p> : null}
          </div>

          <form className="form-stack" onSubmit={(event) => void createTable(event)}>
            <h3>Create Table</h3>
            <div className="form-grid">
              <label>
                Stable key
                <input value={tableKey} onChange={(event) => setTableKey(event.target.value)} required />
              </label>
              <label>
                Display name
                <input value={tableName} onChange={(event) => setTableName(event.target.value)} required />
              </label>
              <label>
                Classification
                <select value={classification} onChange={(event) => setClassification(event.target.value as DataClassification)}>
                  <option value="internal">Internal</option>
                  <option value="confidential">Confidential</option>
                  <option value="restricted">Restricted</option>
                </select>
              </label>
            </div>
            <label>
              Description
              <textarea value={tableDescription} onChange={(event) => setTableDescription(event.target.value)} />
            </label>
            <button className="button primary" type="submit" disabled={saving}>
              Create Table revision 1
            </button>
          </form>
        </section>

        <section className="content-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Typed definitions</p>
              <h2>{selectedTable?.current_revision.content.name ?? "Select a Table"}</h2>
            </div>
          </div>
          {selectedTable ? (
            <>
              <div className="schema-metrics">
                <span><strong>{attributes.length}</strong> Attributes</span>
                <span><strong>{layouts.length}</strong> Layouts</span>
                <span><strong>{subsets.length}</strong> Subsets</span>
              </div>
              <div className="attribute-list">
                {attributes.map((attribute) => (
                  <article key={attribute.attribute_definition_id} className="attribute-card">
                    <div>
                      <strong>{attribute.current_revision.content.name}</strong>
                      <small>{attribute.current_revision.content.key}</small>
                    </div>
                    <span className="status-badge neutral">{attribute.current_revision.content.data_type}</span>
                    <p>
                      {attribute.current_revision.content.quantity_semantics ?? "No quantity semantic"}
                      {attribute.current_revision.content.normalized_unit
                        ? ` · ${attribute.current_revision.content.normalized_unit}`
                        : ""}
                    </p>
                  </article>
                ))}
              </div>

              <form className="form-stack" onSubmit={(event) => void createAttribute(event)}>
                <h3>Add Attribute</h3>
                <div className="form-grid">
                  <label>
                    Stable key
                    <input value={attributeKey} onChange={(event) => setAttributeKey(event.target.value)} required />
                  </label>
                  <label>
                    Display name
                    <input value={attributeName} onChange={(event) => setAttributeName(event.target.value)} required />
                  </label>
                  <label>
                    Data type
                    <select value={attributeType} onChange={(event) => setAttributeType(event.target.value as ConfigurableAttributeDataType)}>
                      {dataTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={required} onChange={(event) => setRequired(event.target.checked)} />
                    Required value
                  </label>
                  {attributeType === "number" ? (
                    <>
                      <label>
                        Quantity semantic
                        <input value={quantitySemantics} onChange={(event) => setQuantitySemantics(event.target.value)} placeholder="density.mass" />
                      </label>
                      <label>
                        Normalized unit
                        <input value={normalizedUnit} onChange={(event) => setNormalizedUnit(event.target.value)} placeholder="kg/m3" />
                      </label>
                    </>
                  ) : null}
                  {attributeType === "discrete" ? (
                    <label>
                      Allowed values (comma separated)
                      <input value={allowedValues} onChange={(event) => setAllowedValues(event.target.value)} required />
                    </label>
                  ) : null}
                  {attributeType === "record_reference" ? (
                    <label>
                      Target Table
                      <select value={referenceTableId} onChange={(event) => setReferenceTableId(event.target.value)} required>
                        <option value="">Select target…</option>
                        {tables.map((table) => <option key={table.table_id} value={table.table_id}>{table.current_revision.content.name}</option>)}
                      </select>
                    </label>
                  ) : null}
                </div>
                <button className="button primary" type="submit" disabled={saving}>
                  Add Attribute revision 1
                </button>
              </form>

              <div className="schema-actions">
                <button className="button secondary" type="button" disabled={saving || !attributes.length} onClick={() => void createDefaultLayout()}>
                  Create datasheet Layout
                </button>
                <button className="button secondary" type="button" disabled={saving} onClick={() => void createAllRecordsSubset()}>
                  Create All records Subset
                </button>
              </div>
            </>
          ) : (
            <p className="muted">Select or create a Table before adding Attribute Definitions.</p>
          )}
        </section>
      </div>
    </div>
  );
}
