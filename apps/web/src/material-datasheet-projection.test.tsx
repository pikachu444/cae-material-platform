import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MaterialDatasheetProjection } from "./material-datasheet-projection";
import { clearModelingSession, loadModelingSession } from "./features/modeling";

const tableId = "91000000-0000-4000-8000-000000000001";
const recordId = "91000000-0000-4000-8000-000000000002";
const tableRevisionId = "91000000-0000-4000-8000-000000000003";
const densityId = "91000000-0000-4000-8000-000000000004";
const curveId = "91000000-0000-4000-8000-000000000005";
const technicalId = "91000000-0000-4000-8000-000000000010";
const materialClassId = "91000000-0000-4000-8000-000000000011";

function metadata(id: string, aggregateId: string) {
  return {
    id,
    aggregate_id: aggregateId,
    revision_no: 1,
    based_on_revision_id: null,
    schema_id: "urn:cmp:catalog:test:1.0.0",
    schema_version: "1.0.0",
    content_hash: "a".repeat(64),
    created_at: "2026-07-21T00:00:00Z",
    created_by: recordId,
    change_reason: "fixture",
    organization_id: recordId,
    project_id: recordId,
    classification: "internal" as const,
    lifecycle_state: "draft" as const,
  };
}

const densityAttribute = {
  attribute_definition_id: densityId,
  table_id: tableId,
  current_revision: {
    ...metadata("91000000-0000-4000-8000-000000000014", densityId),
    content: {
      table_revision_id: tableRevisionId,
      key: "density",
      name: "Density",
      data_type: "number" as const,
      required: true,
      quantity_semantics: "mass density",
      normalized_unit: "kg/m^3",
      minimum_number: null,
      maximum_number: null,
      minimum_length: null,
      maximum_length: null,
      pattern: null,
      allowed_values: [],
      reference_table_id: null,
      help_text: "Original and normalized quantity",
    },
  },
};

const curveAttribute = {
  attribute_definition_id: curveId,
  table_id: tableId,
  current_revision: {
    ...metadata("91000000-0000-4000-8000-000000000015", curveId),
    content: {
      ...densityAttribute.current_revision.content,
      key: "stress_strain",
      name: "Stress–strain curve",
      data_type: "curve" as const,
      required: false,
      quantity_semantics: null,
      normalized_unit: null,
      help_text: null,
    },
  },
};

const technicalAttribute = {
  attribute_definition_id: technicalId,
  table_id: tableId,
  current_revision: {
    ...metadata("91000000-0000-4000-8000-000000000016", technicalId),
    content: {
      ...densityAttribute.current_revision.content,
      key: "internal_note",
      name: "Internal note",
      data_type: "text" as const,
      required: false,
      quantity_semantics: null,
      normalized_unit: null,
      help_text: "Technical-only evidence",
    },
  },
};

const materialClassAttribute = {
  attribute_definition_id: materialClassId,
  table_id: tableId,
  current_revision: {
    ...metadata("91000000-0000-4000-8000-000000000017", materialClassId),
    content: {
      ...densityAttribute.current_revision.content,
      key: "material_class",
      name: "Material class",
      data_type: "discrete" as const,
      required: true,
      quantity_semantics: null,
      normalized_unit: null,
      allowed_values: ["metal", "polymer", "elastomer"],
      help_text: null,
    },
  },
};

const record = {
  record_id: recordId,
  table_id: tableId,
  current_revision: {
    ...metadata("91000000-0000-4000-8000-000000000006", recordId),
    content: {
      table_revision_id: tableRevisionId,
      name: "DP780",
      external_key: "DP780",
      description: null,
      folder_id: null,
      folder_revision_id: null,
      values: [{
        attribute_definition_id: densityId,
        attribute_definition_revision_id: densityAttribute.current_revision.id,
        data_type: "number" as const,
        original_value: "7.85",
        original_unit_string: "g/cm^3",
        normalized_value: "7850",
        normalized_unit: "kg/m^3",
        quantity_semantics: "mass density",
      }, {
        attribute_definition_id: materialClassId,
        attribute_definition_revision_id: materialClassAttribute.current_revision.id,
        data_type: "discrete" as const,
        value: "metal",
      }, {
        attribute_definition_id: curveId,
        attribute_definition_revision_id: curveAttribute.current_revision.id,
        data_type: "curve" as const,
        artifact_id: "91000000-0000-4000-8000-000000000007",
        artifact_sha256: "b".repeat(64),
      }, {
        attribute_definition_id: technicalId,
        attribute_definition_revision_id: technicalAttribute.current_revision.id,
        data_type: "text" as const,
        value: "Technical fixture outside the active Layout",
      }],
    },
  },
};

const layout = {
  layout_id: "91000000-0000-4000-8000-000000000008",
  table_id: tableId,
  revision: metadata("91000000-0000-4000-8000-000000000009", "91000000-0000-4000-8000-000000000008"),
  name: "Material datasheet",
  description: "Administrator-defined material layout",
  items: [{ attribute_definition_id: materialClassId, attribute_definition_revision_id: materialClassAttribute.current_revision.id, section: "Identity", ordinal: 1 }, { attribute_definition_id: densityId, attribute_definition_revision_id: densityAttribute.current_revision.id, section: "Physical", ordinal: 2 }, { attribute_definition_id: curveId, attribute_definition_revision_id: curveAttribute.current_revision.id, section: "Curves", ordinal: 3 }],
};

const mocks = vi.hoisted(() => ({ record: vi.fn(), attributes: vi.fn(), layouts: vi.fn(), previewCurve: vi.fn() }));

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return {
    ...original,
    getConfigurableCatalogRecord: mocks.record,
    listConfigurableCatalogAttributes: mocks.attributes,
    listConfigurableCatalogLayouts: mocks.layouts,
    previewExactCatalogCurveValue: mocks.previewCurve,
  };
});

describe("MaterialDatasheetProjection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.record.mockResolvedValue({ data: record, etag: null });
    mocks.attributes.mockResolvedValue({ data: { items: [densityAttribute, materialClassAttribute, curveAttribute, technicalAttribute] }, etag: null });
    mocks.layouts.mockResolvedValue({ data: { items: [layout] }, etag: null });
    mocks.previewCurve.mockResolvedValue({
      data: {
        record_id: recordId,
        record_revision_id: record.current_revision.id,
        attribute_definition_id: curveId,
        curve_available: true,
        modeling_use: "unavailable",
        modeling_source: null,
        curve_metadata: {
          contract_version: "1.0.0",
          metadata_state: "absent",
          definition_sha256: null,
          definition: null,
          owning_revision: { entity_type: "catalog_record", entity_id: recordId, revision_id: record.current_revision.id },
          artifact: { artifact_id: "91000000-0000-4000-8000-000000000007", sha256: "b".repeat(64), schema_ref: null, media_type: "application/vnd.apache.parquet" },
          sources: [],
          provenance: [],
        },
        curve_series: null,
      },
      etag: null,
    });
  });

  it("projects the active Layout order with separate displayed values and units", async () => {
    render(<MaterialDatasheetProjection config={{ baseUrl: "/api/v1", accessToken: "test" }} tableId={tableId} recordId={recordId} mode="properties"/>);

    expect(await screen.findByRole("heading", { name: "Material datasheet" })).toBeTruthy();
    expect(screen.getByText("7.85")).toBeTruthy();
    expect(screen.getByText("g/cm^3")).toBeTruthy();
    expect(screen.getByText("Metal")).toBeTruthy();
    expect(screen.queryByText("metal")).toBeNull();
    expect(screen.queryByText(/mass density/)).toBeNull();
    expect(screen.queryByText("Original and normalized quantity")).toBeNull();
    expect(screen.queryByText("Stress–strain curve")).toBe(null);
    expect(screen.queryByText("Internal note")).toBeNull();
  });

  it("keeps all typed Attribute data in the Evidence Layout disclosure", async () => {
    render(<MaterialDatasheetProjection config={{ baseUrl: "/api/v1", accessToken: "test" }} tableId={tableId} recordId={recordId} mode="evidence"/>);

    expect(await screen.findByRole("combobox", { name: "Material data view" })).toBeTruthy();
    expect(screen.getByText("Stress–strain curve")).toBeTruthy();
    expect(screen.getByText("Curve available")).toBeTruthy();
    expect(screen.getByText("Internal note")).toBeTruthy();
    expect(screen.getByText("Technical-only evidence")).toBeTruthy();
    expect(screen.queryByText(/SHA-256/)).toBeNull();
  });

  it("loads a curve only through its exact Record revision and reports absent legacy metadata honestly", async () => {
    render(<MaterialDatasheetProjection config={{ baseUrl: "/api/v1", accessToken: "test" }} tableId={tableId} recordId={recordId} mode="curves"/>);

    expect(await screen.findByText("This revision has no recorded channel or deviation metadata.")).toBeTruthy();
    expect(mocks.previewCurve).toHaveBeenCalledWith(
      expect.anything(),
      recordId,
      record.current_revision.id,
      curveId,
    );
    expect(screen.getByText("Curve available")).toBeTruthy();
    expect(screen.getByText("Metadata not recorded")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Open in Modeling" })).toBeNull();
  });

  it("keeps Test Data view-only until exact Material and State context qualifies Process handoff", async () => {
    clearModelingSession();
    const onNavigate = vi.fn();
    const source = {
      binding_id: "92000000-0000-4000-8000-000000000001",
      record_id: recordId,
      record_revision_id: record.current_revision.id,
      kind: "test_data" as const,
      object_id: "92000000-0000-4000-8000-000000000002",
      revision_id: "92000000-0000-4000-8000-000000000003",
      workbench_path: "/modeling",
    };
    mocks.previewCurve.mockResolvedValue({
      data: {
        record_id: recordId,
        record_revision_id: record.current_revision.id,
        attribute_definition_id: curveId,
        curve_available: true,
        modeling_use: "fit_input",
        modeling_source: source,
        curve_metadata: {
          contract_version: "1.0.0",
          metadata_state: "declared",
          definition_sha256: "c".repeat(64),
          definition: {
            definition_version: "1.0.0",
            channels: [
              {
                key: "strain.engineering",
                label: "Engineering strain",
                quantity_semantics: "strain.engineering",
                axis_role: "independent",
                unit_contract: "common",
                dimension: "strain",
                original_units: [
                  {
                    unit: "1",
                    scale_to_normalized: "1",
                    offset_to_normalized: "0",
                  },
                ],
                normalized_unit: "1",
                display_unit: "1",
                display_scale: "1",
                display_offset: "0",
                value_basis: "normalized",
              },
              {
                key: "stress.engineering",
                label: "Engineering stress",
                quantity_semantics: "stress.engineering",
                axis_role: "dependent",
                unit_contract: "common",
                dimension: "force_per_area",
                original_units: [
                  {
                    unit: "Pa",
                    scale_to_normalized: "1",
                    offset_to_normalized: "0",
                  },
                ],
                normalized_unit: "Pa",
                display_unit: "MPa",
                display_scale: "0.000001",
                display_offset: "0",
                value_basis: "derived",
              },
            ],
            deviations: [],
          },
          owning_revision: {
            entity_type: "test_data_document",
            entity_id: source.object_id,
            revision_id: source.revision_id,
          },
          artifact: {
            artifact_id: "92000000-0000-4000-8000-000000000004",
            sha256: "d".repeat(64),
            schema_ref: "urn:cmp:test-data:normalized-parquet:1.1.0",
            media_type: "application/vnd.apache.parquet",
          },
          sources: [],
          provenance: [],
        },
        curve_series: {
          point_count: 3,
          returned_point_count: 3,
          sampled: false,
          indices: [0, 1, 2],
          channels: [
            { key: "strain.engineering", values: [0, 0.01, 0.02] },
            { key: "stress.engineering", values: [0, 200e6, 300e6] },
          ],
          deviations: [],
          source_counts: [],
        },
      },
      etag: null,
    });

    const unqualified = render(
      <MaterialDatasheetProjection
        config={{ baseUrl: "/api/v1", accessToken: "test" }}
        tableId={tableId}
        recordId={recordId}
        mode="curves"
        onNavigate={onNavigate}
      />,
    );
    expect(
      await screen.findByText(
        "Exact Material and State context is required to continue.",
      ),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Open in Modeling" })).toBeNull();
    expect(onNavigate).not.toHaveBeenCalled();
    expect(loadModelingSession()).toBeNull();
    unqualified.unmount();

    render(
      <MaterialDatasheetProjection
        config={{ baseUrl: "/api/v1", accessToken: "test" }}
        tableId={tableId}
        recordId={recordId}
        mode="curves"
        onNavigate={onNavigate}
        modelingContext={{
          material: {
            id: "material-1",
            revisionId: "material-r2",
            revisionNo: 2,
            label: "DP780",
          },
          materialState: {
            id: "state-1",
            revisionId: "state-r3",
            revisionNo: 3,
            label: "Room temperature",
          },
        }}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Open in Modeling" }),
    );
    expect(onNavigate).toHaveBeenCalledWith(
      `/modeling?stage=process&family=metal&material_id=material-1&material_revision_id=material-r2&material_state_id=state-1&material_state_revision_id=state-r3&source_document_id=${source.object_id}&source_revision_id=${source.revision_id}`,
    );
    expect(loadModelingSession()).toMatchObject({
      contextSelectionRequired: false,
      material: { id: "material-1", revisionId: "material-r2" },
      materialState: { id: "state-1", revisionId: "state-r3" },
      testData: { id: source.object_id, revisionId: source.revision_id },
      workspace: { activeStage: "process" },
    });
  });

  it("downloads human-readable active Layout CSV without internal identifiers", async () => {
    const createObjectURL = vi.fn((value: Blob) => {
      void value;
      return "blob:layout";
    });
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL: vi.fn() });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    render(<MaterialDatasheetProjection config={{ baseUrl: "/api/v1", accessToken: "test" }} tableId={tableId} recordId={recordId} mode="properties"/>);

    fireEvent.click(await screen.findByRole("button", { name: "Download CSV" }));
    expect(createObjectURL).toHaveBeenCalledOnce();
    const csv = await (createObjectURL.mock.calls[0][0] as Blob).text();
    expect(csv).toContain("Section,Property,Value,Unit,Condition,Source");
    expect(csv).toContain("Identity,Material class,metal,,,");
    expect(csv).toContain("Physical,Density,7.85,g/cm^3,,");
    expect(csv).not.toContain(densityId);
    expect(csv).not.toContain("attribute_definition_id");
    expect(csv).not.toContain("b".repeat(64));
    expect(csv).not.toContain("Internal note");
    expect(csv).not.toContain("Technical fixture outside the active Layout");
    expect(click).toHaveBeenCalled();
  });

  it("shows a truthful empty state when no active Layout exists", async () => {
    mocks.layouts.mockResolvedValue({ data: { items: [] }, etag: null });
    render(<MaterialDatasheetProjection config={{ baseUrl: "/api/v1", accessToken: "test" }} tableId={tableId} recordId={recordId} mode="properties"/>);

    expect(await screen.findByText("No saved datasheet layout is available.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Download CSV" })).toBeNull();
  });
});
