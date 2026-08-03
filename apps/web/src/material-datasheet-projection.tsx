import { useEffect, useMemo, useState } from "react";

import {
  getConfigurableCatalogRecord,
  listConfigurableCatalogAttributes,
  listConfigurableCatalogLayouts,
  listConfigurableCatalogRecordRevisions,
  type ApiConfig,
} from "./api";
import type {
  ConfigurableAttributeResponse,
  ConfigurableCatalogRecordResponse,
  ConfigurableLayoutResponse,
  ConfigurableRecordValue,
} from "./types";

type ProjectionMode = "properties" | "curves" | "evidence";

interface Props {
  config: ApiConfig;
  tableId: string;
  recordId: string;
  mode: ProjectionMode;
  revisionId?: string;
}

interface ProjectedValue {
  attribute: ConfigurableAttributeResponse;
  value: ConfigurableRecordValue | null;
  section: string;
  ordinal: number;
}

function familyLabel(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase();
  if (normalized === "metal") return "Metal";
  if (normalized === "polymer") return "Polymer";
  if (normalized === "elastomer") return "Elastomer";
  return value?.trim() || "Unclassified";
}

function valueText(value: ConfigurableRecordValue | null): { primary: string; secondary: string | null } {
  if (!value) return { primary: "—", secondary: null };
  if (value.data_type === "number") {
    return {
      primary: value.original_value,
      secondary: null,
    };
  }
  if (value.data_type === "file" || value.data_type === "curve") {
    return { primary: `${value.data_type === "curve" ? "Curve" : "File"} available`, secondary: null };
  }
  if (value.data_type === "record_reference") {
    return { primary: "Related Record", secondary: "Revision-pinned link" };
  }
  if (value.data_type === "boolean") return { primary: value.value ? "Yes" : "No", secondary: null };
  return { primary: String(value.value), secondary: null };
}

function included(mode: ProjectionMode, attribute: ConfigurableAttributeResponse): boolean {
  const type = attribute.current_revision.content.data_type;
  if (mode === "curves") return type === "curve";
  if (mode === "properties") return !["curve", "file", "record_reference"].includes(type);
  return true;
}

function csvCell(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value;
}

function projectedCsvValue(value: ConfigurableRecordValue | null): string {
  if (!value) return "";
  if (value.data_type === "number") {
    return value.original_value ?? "";
  }
  if (value.data_type === "record_reference") return "Related Record";
  if (value.data_type === "file" || value.data_type === "curve") return `${value.data_type} artifact`;
  return String(value.value);
}

function downloadLayoutCsv(
  record: ConfigurableCatalogRecordResponse,
  layout: ConfigurableLayoutResponse | null,
  values: ProjectedValue[],
): void {
  const rows = [["Section", "Property", "Value", "Unit", "Condition", "Source"]];
  const contextValue = (keys: string[]): string => {
    const item = values.find((candidate) => keys.includes(candidate.attribute.current_revision.content.key));
    return item ? projectedCsvValue(item.value) : "";
  };
  const condition = contextValue(["condition_summary", "condition"]);
  const source = contextValue(["evidence_source", "provider", "manufacturer"]);
  for (const item of values) {
    const value = item.value;
    rows.push([
      item.section,
      item.attribute.current_revision.content.name,
      projectedCsvValue(value),
      value?.data_type === "number" ? value.original_unit_string ?? "" : "",
      condition,
      source,
    ]);
  }
  const csv = rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
  const blob = new Blob([`${csv}\r\n`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const safeName = (layout?.name ?? record.current_revision.content.name)
    .replace(/[^a-z0-9_-]+/gi, "-")
    .replace(/^-|-$/g, "") || "material-datasheet";
  anchor.href = url;
  anchor.download = `${safeName}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function MaterialDatasheetProjection({ config, tableId, recordId, mode, revisionId }: Props) {
  const [record, setRecord] = useState<ConfigurableCatalogRecordResponse | null>(null);
  const [attributes, setAttributes] = useState<ConfigurableAttributeResponse[]>([]);
  const [layouts, setLayouts] = useState<ConfigurableLayoutResponse[]>([]);
  const [layoutId, setLayoutId] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    void Promise.all([
      getConfigurableCatalogRecord(config, recordId),
      listConfigurableCatalogAttributes(config, tableId),
      listConfigurableCatalogLayouts(config, tableId),
      revisionId ? listConfigurableCatalogRecordRevisions(config, recordId) : Promise.resolve(null),
    ]).then(([recordResult, attributeResult, layoutResult, revisionResult]) => {
      if (!active) return;
      const exactRevision = revisionId && revisionResult
        ? revisionResult.data.items.find((item) => item.id === revisionId)
        : null;
      if (revisionId && !exactRevision) {
        throw new Error("The requested immutable record revision does not exist.");
      }
      setRecord(exactRevision ? { ...recordResult.data, current_revision: exactRevision } : recordResult.data);
      setAttributes(attributeResult.data.items);
      setLayouts(layoutResult.data.items);
      setLayoutId(layoutResult.data.items[0]?.layout_id ?? "");
    }).catch(() => {
      if (!active) return;
      setRecord(null);
      setAttributes([]);
      setLayouts([]);
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [config, recordId, revisionId, tableId]);

  const selectedLayout = layouts.find((layout) => layout.layout_id === layoutId) ?? null;
  const { layoutValues, technicalValues } = useMemo(() => {
    if (!record || !selectedLayout) return { layoutValues: [], technicalValues: [] };
    const valuesByAttribute = new Map(record.current_revision.content.values.map((value) => [value.attribute_definition_id, value]));
    const attributesById = new Map(attributes.map((attribute) => [attribute.attribute_definition_id, attribute]));
    const layoutAttributeIds = new Set(selectedLayout.items.map((item) => item.attribute_definition_id));
    const projectLayoutItem = (item: ConfigurableLayoutResponse["items"][number]): ProjectedValue | null => {
      const attribute = attributesById.get(item.attribute_definition_id);
      if (!attribute) return null;
      return {
        attribute,
        value: valuesByAttribute.get(item.attribute_definition_id) ?? null,
        section: item.section,
        ordinal: item.ordinal,
      };
    };
    const layout = selectedLayout.items
      .slice()
      .sort((left, right) => left.ordinal - right.ordinal || left.section.localeCompare(right.section))
      .map(projectLayoutItem)
      .filter((item): item is ProjectedValue => item !== null);
    const technical = attributes
      .filter((attribute) => !layoutAttributeIds.has(attribute.attribute_definition_id))
      .filter((attribute) => included("evidence", attribute))
      .map((attribute): ProjectedValue => ({
        attribute,
        value: valuesByAttribute.get(attribute.attribute_definition_id) ?? null,
        section: "Technical values",
        ordinal: Number.MAX_SAFE_INTEGER,
      }))
      .sort((left, right) => left.attribute.current_revision.content.name.localeCompare(right.attribute.current_revision.content.name));
    return { layoutValues: layout, technicalValues: technical };
  }, [attributes, record, selectedLayout]);

  const values = useMemo(() => {
    const projected = layoutValues.filter((item) => included(mode, item.attribute));
    return mode === "curves" ? projected.filter((item) => item.value !== null) : projected;
  }, [layoutValues, mode]);

  if (loading) return <p className="ux-meta">Loading configured datasheet…</p>;
  if (!record) return <div className="ux-empty"><strong>Material data is unavailable.</strong><p>Return to the selected Record and try again.</p></div>;
  if (!selectedLayout) return <div className="ux-empty"><strong>No saved datasheet layout is available.</strong><p>Ask an administrator to configure the Material display.</p></div>;
  if (!values.length && mode !== "evidence") return <div className="ux-empty"><strong>No {mode === "curves" ? "curve data" : "properties"} is included in this Layout.</strong></div>;

  const displayValues = mode === "evidence" ? [...values, ...technicalValues] : values;
  const sections = [...new Set(displayValues.map((item) => item.section))];
  const content = <div className="layout-projection-content">{sections.map((section) => <section key={section}><h3>{section}</h3><table className="ux-table layout-projection-table"><thead><tr><th>Property</th><th>Value</th><th>Unit</th></tr></thead><tbody>{displayValues.filter((item) => item.section === section).map((item) => {
    const text = valueText(item.value);
    const definition = item.attribute.current_revision.content;
    const primary = definition.key === "material_class" && item.value && "value" in item.value
      ? familyLabel(String(item.value.value))
      : text.primary;
    return <tr key={item.attribute.attribute_definition_id}><td><strong>{definition.name}</strong>{mode === "evidence" && definition.help_text ? <small>{definition.help_text}</small> : null}</td><td><span>{primary}</span>{text.secondary ? <small title={text.secondary}>{text.secondary}</small> : null}</td><td>{item.value?.data_type === "number" ? item.value.original_unit_string : ""}</td></tr>;
  })}</tbody></table></section>)}</div>;

  if (mode !== "evidence") {
    return <section className="layout-projection"><div className="detail-section-heading"><div><p className="ux-kicker">Material data</p><h2>{selectedLayout?.name ?? "Properties"}</h2></div><button className="ux-button tertiary" type="button" onClick={() => record && downloadLayoutCsv(record, selectedLayout, values)}>Download CSV</button></div>{content}</section>;
  }

  return <details className="ux-disclosure layout-projection"><summary>Additional data and technical values</summary><div className="layout-selector-row"><label className="ux-field">View<select className="ux-select" aria-label="Material data view" value={selectedLayout.layout_id} onChange={(event) => setLayoutId(event.target.value)}>{layouts.map((layout) => <option key={layout.layout_id} value={layout.layout_id}>{layout.name}</option>)}</select></label><span className="ux-meta">{selectedLayout.description ?? "Saved display order and sections"}</span><button className="ux-button tertiary" type="button" onClick={() => record && downloadLayoutCsv(record, selectedLayout, values)}>Download CSV</button></div>{content}</details>;
}
