import type {
  ConfigurableAttributeResponse,
  ConfigurableAttributeRevision,
  ConfigurableCatalogRecordResponse,
  ConfigurableLayoutItem,
  ConfigurableRecordValue,
} from "../../catalog/contracts";
import { EngineeringPane, SemanticText } from "../../../design/semantic-ui";

export interface DatasheetLayoutPreviewValue {
  name: string;
  description: string | null;
  items: ConfigurableLayoutItem[];
}

function valueText(value: ConfigurableRecordValue | undefined): string {
  if (!value) return "—";
  if (value.data_type === "number") {
    const displayUnit = value.original_unit_string.trim();
    return displayUnit && displayUnit !== "1"
      ? `${value.original_value} ${displayUnit}`
      : value.original_value;
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
  layout: DatasheetLayoutPreviewValue | null;
  attributes: ConfigurableAttributeResponse[];
  attributeRevisions: ConfigurableAttributeRevision[];
  onClose: () => void;
  onOpenRecord?: () => void;
  onSelectRecord: (recordId: string) => void;
}) {
  const fields = layout
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
  const sections = fields.reduce<Array<{ name: string; fields: typeof fields }>>(
    (groups, field) => {
      const current = groups.at(-1);
      if (current?.name === field.item.section) {
        current.fields.push(field);
      } else {
        groups.push({ name: field.item.section, fields: [field] });
      }
      return groups;
    },
    [],
  );

  return (
    <EngineeringPane className="schema-record-preview" label="Datasheet preview">
      <header>
        <SemanticText semanticRole="sectionHeading" as="h3">
          {layout?.name ?? "Current Table fields"}
        </SemanticText>
        <button className="ux-button tertiary local-action" type="button" onClick={onClose}>
          Back to layout
        </button>
      </header>
      <label className="ux-field schema-preview-record-picker">
        Preview with
        <select className="ux-select" value={selectedRecordId} onChange={(event) => onSelectRecord(event.target.value)}>
          <option value="">Choose a saved Record</option>
          {records.map((item) => (
            <option key={item.record_id} value={item.record_id}>
              {item.current_revision.content.name} ({item.current_revision.lifecycle_state === "draft" ? "Draft" : "Published"}, revision {item.current_revision.revision_no})
            </option>
          ))}
        </select>
      </label>
      {record ? (
        <div className="schema-preview-fields" role="region" aria-label="Preview fields" tabIndex={0}>
          {sections.map((section, sectionIndex) => (
            <section
              className="schema-preview-section"
              aria-label={section.name}
              key={`${section.name}:${sectionIndex}`}
            >
              <SemanticText semanticRole="label" as="h3">{section.name}</SemanticText>
              <dl>
                {section.fields.map(({ definition, item }) => {
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
            </section>
          ))}
        </div>
      ) : (
        <div className="schema-preview-empty" role="status">
          <strong>{records.length ? "Choose a saved Record to preview." : "No saved Record is available for this Table."}</strong>
        </div>
      )}
      {record && onOpenRecord ? (
        <footer className="ux-action-row">
          <button className="ux-button local-action" onClick={onOpenRecord} type="button">
            Open in Records
          </button>
        </footer>
      ) : null}
    </EngineeringPane>
  );
}
