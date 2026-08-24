import type {
  ConfigurableAttributeResponse,
  ConfigurableAttributeRevision,
  ConfigurableCatalogRecordResponse,
  ConfigurableLayoutResponse,
  ConfigurableRecordValue,
} from "../../../types";

function valueText(value: ConfigurableRecordValue | undefined): string {
  if (!value) return "—";
  if (value.data_type === "number") {
    return `${value.original_value} ${value.original_unit_string}`;
  }
  if (value.data_type === "file" || value.data_type === "curve") {
    return value.data_type === "curve" ? "Saved curve" : "Saved file";
  }
  if (value.data_type === "record_reference") {
    return `Record ${value.target_record_id.slice(0, 8)} · exact revision ${value.target_record_revision_id.slice(0, 8)}`;
  }
  if (value.data_type === "boolean") return value.value ? "Yes" : "No";
  return String(value.value);
}

export function RecordPreview({
  record,
  records,
  selectedRecordId,
  layout,
  attributes,
  attributeRevisions,
  onClose,
  onOpenRecord,
  onSelectRecord,
}: {
  record: ConfigurableCatalogRecordResponse | null;
  records: ConfigurableCatalogRecordResponse[];
  selectedRecordId: string;
  layout: ConfigurableLayoutResponse | null;
  attributes: ConfigurableAttributeResponse[];
  attributeRevisions: ConfigurableAttributeRevision[];
  onClose: () => void;
  onOpenRecord?: () => void;
  onSelectRecord: (recordId: string) => void;
}) {
  const fields = layout?.items.length
    ? layout.items.map((item) => ({
        definition: attributeRevisions.find(
          (revision) =>
            revision.aggregate_id === item.attribute_definition_id
            && revision.id === item.attribute_definition_revision_id,
        ),
        item,
      }))
    : attributes.map((definition, ordinal) => ({
        definition: definition.current_revision,
        item: {
          attribute_definition_id: definition.attribute_definition_id,
          attribute_definition_revision_id: definition.current_revision.id,
          ordinal,
          section: "General",
        },
      }));

  return (
    <aside className="schema-record-preview" aria-label="Adjacent datasheet preview">
      <header>
        <h3>{layout?.name ?? "Current Table fields"}</h3>
        <button className="ux-button tertiary" type="button" onClick={onClose}>
          Close preview
        </button>
      </header>
      <label className="schema-preview-record-picker">
        Record
        <select value={selectedRecordId} onChange={(event) => onSelectRecord(event.target.value)}>
          <option value="">Choose a saved Record</option>
          {records.map((item) => (
            <option key={item.record_id} value={item.record_id}>
              {item.current_revision.content.name} · r{item.current_revision.revision_no}
            </option>
          ))}
        </select>
      </label>
      {record ? (
        <>
          <div className="schema-preview-identity">
            <strong>{record.current_revision.content.name}</strong>
            <span>Record r{record.current_revision.revision_no}</span>
          </div>
          <dl className="schema-preview-fields">
            {fields.map(({ definition, item }) => {
              const value = record.current_revision.content.values.find(
                (candidate) =>
                  candidate.attribute_definition_id === item.attribute_definition_id
                  && candidate.attribute_definition_revision_id
                    === item.attribute_definition_revision_id,
              );
              return (
                <div key={`${item.attribute_definition_id}:${item.attribute_definition_revision_id}`}>
                  <dt>
                    {definition?.content.name ?? "Unavailable Attribute revision"}
                  </dt>
                  <dd>{valueText(value)}</dd>
                </div>
              );
            })}
          </dl>
        </>
      ) : (
        <div className="schema-preview-empty" role="status">
          <strong>{records.length ? "Choose a saved Record to preview." : "No saved Record is available for this Table."}</strong>
        </div>
      )}
      <footer>
        <span>
          {layout
            ? `Layout r${layout.revision.revision_no} · ${fields.length} exact Attribute revision pins`
            : `${fields.length} current Attribute definitions`}
        </span>
        {record && onOpenRecord ? (
          <button className="ux-button" onClick={onOpenRecord} type="button">
            Open in Records
          </button>
        ) : null}
      </footer>
    </aside>
  );
}
