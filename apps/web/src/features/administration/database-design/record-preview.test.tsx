import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  ConfigurableAttributeResponse,
  ConfigurableCatalogRecordResponse,
} from "../../../types";
import { RecordPreview } from "./record-preview";

describe("RecordPreview", () => {
  it("omits the dimensionless unit marker from the user value without changing the record", () => {
    const attribute = {
      attribute_definition_id: "attribute-poisson",
      current_revision: {
        id: "attribute-poisson-revision",
        aggregate_id: "attribute-poisson",
        content: { name: "Poisson's ratio" },
      },
    } as unknown as ConfigurableAttributeResponse;
    const record = {
      record_id: "record-dp780",
      current_revision: {
        revision_no: 2,
        lifecycle_state: "draft",
        content: {
          name: "DP780",
          values: [
            {
              attribute_definition_id: "attribute-poisson",
              attribute_definition_revision_id: "attribute-poisson-revision",
              data_type: "number",
              original_value: "0.30",
              original_unit_string: "1",
              normalized_value: "0.30",
              normalized_unit: "1",
            },
          ],
        },
      },
    } as unknown as ConfigurableCatalogRecordResponse;

    render(
      <RecordPreview
        record={record}
        records={[record]}
        selectedRecordId={record.record_id}
        layout={{
          name: "Material overview",
          description: null,
          items: [
            {
              attribute_definition_id: "attribute-poisson",
              attribute_definition_revision_id: "attribute-poisson-revision",
              ordinal: 0,
              section: "Elastic properties",
            },
          ],
        }}
        attributes={[attribute]}
        attributeRevisions={[attribute.current_revision]}
        onClose={() => undefined}
        onSelectRecord={() => undefined}
      />,
    );

    expect(screen.getByText("0.30")).toBeTruthy();
    expect(screen.queryByText("0.30 1")).toBeNull();
    const storedValue = record.current_revision.content.values[0];
    expect(storedValue?.data_type).toBe("number");
    if (storedValue?.data_type !== "number") throw new Error("Expected numeric fixture value.");
    expect(storedValue.original_unit_string).toBe("1");
  });
});
