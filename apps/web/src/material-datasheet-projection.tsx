import { useEffect, useMemo, useState } from "react";

import {
  getConfigurableCatalogRecord,
  listConfigurableCatalogAttributes,
  listConfigurableCatalogLayouts,
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
}

interface ProjectedValue {
  attribute: ConfigurableAttributeResponse;
  value: ConfigurableRecordValue | null;
  section: string;
  ordinal: number;
}

function valueText(value: ConfigurableRecordValue | null): { primary: string; secondary: string | null } {
  if (!value) return { primary: "—", secondary: null };
  if (value.data_type === "number") {
    return {
      primary: `${value.original_value} ${value.original_unit_string}`.trim(),
      secondary: `${value.normalized_value} ${value.normalized_unit} · ${value.quantity_semantics}`.trim(),
    };
  }
  if (value.data_type === "file" || value.data_type === "curve") {
    return { primary: `${value.data_type === "curve" ? "Curve" : "File"} artifact`, secondary: `SHA-256 ${value.artifact_sha256}` };
  }
  if (value.data_type === "record_reference") {
    return { primary: "Related Record", secondary: `Exact revision ${value.target_record_revision_id}` };
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

export function MaterialDatasheetProjection({ config, tableId, recordId, mode }: Props) {
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
    ]).then(([recordResult, attributeResult, layoutResult]) => {
      if (!active) return;
      setRecord(recordResult.data);
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
  }, [config, recordId, tableId]);

  const selectedLayout = layouts.find((layout) => layout.layout_id === layoutId) ?? layouts[0] ?? null;
  const values = useMemo(() => {
    if (!record) return [];
    const valuesByAttribute = new Map(record.current_revision.content.values.map((value) => [value.attribute_definition_id, value]));
    const layoutItems = new Map(selectedLayout?.items.map((item) => [item.attribute_definition_id, item]) ?? []);
    return attributes
      .filter((attribute) => included(mode, attribute))
      .map((attribute): ProjectedValue => {
        const item = layoutItems.get(attribute.attribute_definition_id);
        return {
          attribute,
          value: valuesByAttribute.get(attribute.attribute_definition_id) ?? null,
          section: item?.section ?? "Additional data",
          ordinal: item?.ordinal ?? Number.MAX_SAFE_INTEGER,
        };
      })
      .filter((item) => item.value !== null || mode === "evidence")
      .sort((left, right) => left.section.localeCompare(right.section) || left.ordinal - right.ordinal || left.attribute.current_revision.content.name.localeCompare(right.attribute.current_revision.content.name));
  }, [attributes, mode, record, selectedLayout]);

  if (loading) return <p className="ux-meta">Loading configured datasheet…</p>;
  if (!record || (!values.length && mode !== "evidence")) return null;

  const sections = [...new Set(values.map((item) => item.section))];
  const content = <div className="layout-projection-content">{sections.map((section) => <section key={section}><h3>{section}</h3><table className="ux-table layout-projection-table"><thead><tr><th>Attribute</th><th>Value</th><th>Type</th></tr></thead><tbody>{values.filter((item) => item.section === section).map((item) => {
    const text = valueText(item.value);
    const definition = item.attribute.current_revision.content;
    return <tr key={item.attribute.attribute_definition_id}><td><strong>{definition.name}</strong>{definition.help_text ? <small>{definition.help_text}</small> : null}</td><td><span>{text.primary}</span>{text.secondary ? <small title={text.secondary}>{text.secondary}</small> : null}</td><td>{definition.data_type.replaceAll("_", " ")}</td></tr>;
  })}</tbody></table></section>)}</div>;

  if (mode !== "evidence") {
    return <section className="layout-projection"><div className="detail-section-heading"><div><p className="ux-kicker">Configured datasheet</p><h2>{selectedLayout?.name ?? "Table attributes"}</h2></div></div>{content}</section>;
  }

  return <details className="ux-disclosure layout-projection"><summary>Additional Layout datasheets and typed values</summary><div className="layout-selector-row"><label className="ux-field">Layout<select className="ux-select" aria-label="Material Layout" value={selectedLayout?.layout_id ?? ""} onChange={(event) => setLayoutId(event.target.value)}>{layouts.map((layout) => <option key={layout.layout_id} value={layout.layout_id}>{layout.name}</option>)}</select></label><span className="ux-meta">{selectedLayout?.description ?? "Administrator-defined attribute order and sections"}</span></div>{content}</details>;
}
