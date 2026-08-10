import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfigurableCatalogRecords } from "./configurable-catalog-records";

const revision = {
  id: "20000000-0000-4000-8000-000000000002",
  aggregate_id: "20000000-0000-4000-8000-000000000001",
  revision_no: 1,
  based_on_revision_id: null,
  schema_id: "urn:cmp:catalog:fixture:1.0.0",
  schema_version: "1.0.0",
  content_hash: "a".repeat(64),
  created_at: "2026-07-18T09:00:00Z",
  created_by: "20000000-0000-4000-8000-000000000003",
  change_reason: "fixture",
  organization_id: "20000000-0000-4000-8000-000000000004",
  project_id: "20000000-0000-4000-8000-000000000005",
  classification: "internal" as const,
  lifecycle_state: "draft" as const,
};

const table = {
  table_id: "20000000-0000-4000-8000-000000000001",
  current_revision: {
    ...revision,
    content: {
      key: "materials",
      name: "Engineering Materials",
      description: null,
    },
  },
};

const modulus = {
  attribute_definition_id: "20000000-0000-4000-8000-000000000006",
  table_id: table.table_id,
  current_revision: {
    ...revision,
    id: "20000000-0000-4000-8000-000000000007",
    aggregate_id: "20000000-0000-4000-8000-000000000006",
    content: {
      table_revision_id: revision.id,
      key: "youngs_modulus",
      name: "Young's modulus",
      data_type: "number" as const,
      required: true,
      quantity_semantics: "modulus.elastic.young",
      normalized_unit: "Pa",
      minimum_number: 0,
      maximum_number: null,
      minimum_length: null,
      maximum_length: null,
      pattern: null,
      allowed_values: [],
      reference_table_id: null,
      help_text: null,
    },
  },
};

const record = {
  record_id: "20000000-0000-4000-8000-000000000008",
  table_id: table.table_id,
  current_revision: {
    ...revision,
    id: "20000000-0000-4000-8000-000000000009",
    aggregate_id: "20000000-0000-4000-8000-000000000008",
    content: {
      table_revision_id: revision.id,
      name: "DP600 Sheet",
      external_key: "dp600",
      description: null,
      folder_id: null,
      folder_revision_id: null,
      values: [
        {
          data_type: "number" as const,
          attribute_definition_id: modulus.attribute_definition_id,
          attribute_definition_revision_id: modulus.current_revision.id,
          original_value: "210000",
          original_unit_string: "MPa",
          normalized_value: "210000000000",
          normalized_unit: "Pa",
          quantity_semantics: "modulus.elastic.young",
        },
      ],
    },
  },
};

const mocks = vi.hoisted(() => ({
  tables: vi.fn(),
  attributes: vi.fn(),
  layouts: vi.fn(),
  folders: vi.fn(),
  subsets: vi.fn(),
  search: vi.fn(),
  createRecord: vi.fn(),
  getRecord: vi.fn(),
  revisions: vi.fn(),
  compare: vi.fn(),
  createFolder: vi.fn(),
  createSubset: vi.fn(),
  reviseRecord: vi.fn(),
  materials: vi.fn(),
  materialDetail: vi.fn(),
  upload: vi.fn(),
  previewRegistration: vi.fn(),
  publishRegistration: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const original = await importOriginal<typeof import("./api")>();
  return {
    ...original,
    listConfigurableCatalogTables: mocks.tables,
    listConfigurableCatalogAttributes: mocks.attributes,
    listConfigurableCatalogLayouts: mocks.layouts,
    listConfigurableCatalogFolders: mocks.folders,
    listConfigurableCatalogSubsets: mocks.subsets,
    searchConfigurableCatalogRecords: mocks.search,
    createConfigurableCatalogRecord: mocks.createRecord,
    getConfigurableCatalogRecord: mocks.getRecord,
    listConfigurableCatalogRecordRevisions: mocks.revisions,
    compareConfigurableCatalogRecordRevisions: mocks.compare,
    createConfigurableCatalogFolder: mocks.createFolder,
    createConfigurableCatalogSubset: mocks.createSubset,
    reviseConfigurableCatalogRecord: mocks.reviseRecord,
    listMaterials: mocks.materials,
    getMaterialDetail: mocks.materialDetail,
    uploadGovernedTabularFile: mocks.upload,
    previewConfigurableCatalogRecordRegistration: mocks.previewRegistration,
    publishConfigurableCatalogRecordRegistration: mocks.publishRegistration,
  };
});

describe("ConfigurableCatalogRecords", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.tables.mockResolvedValue({ data: { items: [table] }, etag: null });
    mocks.attributes.mockResolvedValue({
      data: { items: [modulus] },
      etag: null,
    });
    mocks.layouts.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.folders.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.subsets.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.search.mockResolvedValue({
      data: { items: [], total_count: 0, offset: 0, limit: 50, facets: [] },
      etag: null,
    });
    mocks.createRecord.mockResolvedValue({
      data: record,
      etag: '"revision:1:sha256:a"',
    });
    mocks.getRecord.mockResolvedValue({
      data: record,
      etag: '"revision:1:sha256:a"',
    });
    mocks.revisions.mockResolvedValue({
      data: { items: [record.current_revision] },
      etag: null,
    });
    mocks.materials.mockResolvedValue({ data: { items: [] }, etag: null });
    mocks.publishRegistration.mockResolvedValue({
      data: { records: [] },
      etag: null,
    });
  });

  it("sends the entered value and unit while leaving standard-value derivation to the service", async () => {
    const user = userEvent.setup();
    render(
      <ConfigurableCatalogRecords
        config={{ baseUrl: "/api/v1", accessToken: "catalog-token" }}
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Create Record" }),
    ).toBeTruthy();
    await user.type(screen.getByLabelText("Name"), "DP600 Sheet");
    const original = screen.getByRole("spinbutton", { name: "Entered value" });
    const unit = screen.getByRole("textbox", { name: "Entered unit" });
    await user.type(original, "210000");
    await user.clear(unit);
    await user.type(unit, "MPa");
    await user.click(screen.getByRole("button", { name: "Create record" }));

    await waitFor(() => expect(mocks.createRecord).toHaveBeenCalledOnce());
    expect(mocks.createRecord).toHaveBeenCalledWith(
      expect.anything(),
      table.table_id,
      expect.objectContaining({
        content: expect.objectContaining({
          values: [
            expect.objectContaining({
              data_type: "number",
              original_value: "210000",
              original_unit_string: "MPa",
              normalized_value: "210000",
              normalized_unit: "Pa",
              quantity_semantics: "modulus.elastic.young",
            }),
          ],
        }),
      }),
    );
  });

  it("rechecks a corrected immutable file before registering every row", async () => {
    mocks.upload.mockResolvedValue({
      data: {
        raw_asset: { raw_asset_id: "30000000-0000-4000-8000-000000000001" },
        available_artifact_id: "30000000-0000-4000-8000-000000000002",
      },
      etag: null,
    });
    const columns = [
      "Record name",
      "Record code",
      "Material code",
      "State name",
      "Elastic modulus",
    ];
    mocks.previewRegistration
      .mockResolvedValueOnce({
        data: {
          token: "preview-one",
          valid: false,
          rows: [{ row: 2, valid: false }],
          errors: [
            {
              row: 2,
              column: "Elastic modulus",
              message: "Enter a number.",
              action: "Correct the source value.",
            },
          ],
          source_columns: columns,
          sample_rows: [
            {
              "Record name": "Steel B",
              "Record code": "B",
              "Material code": "MAT-B",
              "State name": "Annealed",
              "Elastic modulus": "bad",
            },
          ],
        },
        etag: null,
      })
      .mockResolvedValueOnce({
        data: {
          token: "preview-two",
          valid: true,
          rows: [{ row: 2, valid: true, material_state: "Annealed" }],
          errors: [],
          source_columns: columns,
          sample_rows: [],
        },
        etag: null,
      });
    const user = userEvent.setup();
    render(
      <ConfigurableCatalogRecords
        config={{ baseUrl: "/api/v1", accessToken: "catalog-token" }}
        onNavigate={() => undefined}
        onOpenConnection={() => undefined}
      />,
    );

    await screen.findByRole("heading", { name: "Create Record" });
    await user.click(screen.getByRole("button", { name: "Multiple rows" }));
    const readColumns = screen.getByRole("button", { name: "Read columns" });
    const registerRows = screen.getByRole("button", { name: "Register checked rows" });
    expect(readColumns.className).toBe("ux-button");
    expect(registerRows.className).toBe("ux-button primary");
    expect((registerRows as HTMLButtonElement).disabled).toBe(true);
    await user.upload(
      screen.getByLabelText("Source file"),
      new File(["Record name;Record code\nSteel B;B"], "records.csv", {
        type: "text/csv",
      }),
    );
    await user.click(readColumns);
    expect(await screen.findByText("Rows to correct")).toBeTruthy();
    await user.selectOptions(
      screen.getByLabelText("Elastic modulus field"),
      "youngs_modulus",
    );
    const unit = screen.getByLabelText("Elastic modulus original unit");
    await user.clear(unit);
    await user.type(unit, "GPa");
    await user.type(
      screen.getByLabelText("Correction for row 2, Elastic modulus"),
      "205,0",
    );
    await user.click(screen.getByRole("button", { name: "Check rows" }));
    expect(await screen.findByText("All rows are valid.")).toBeTruthy();
    expect((registerRows as HTMLButtonElement).disabled).toBe(false);
    expect(mocks.previewRegistration).toHaveBeenLastCalledWith(
      expect.anything(),
      expect.objectContaining({
        corrections: { 2: { "Elastic modulus": "205,0" } },
        mapping: expect.objectContaining({
          "Material code": "existing_material_code",
          "State name": "existing_state_name",
          "Elastic modulus": { attribute: "youngs_modulus", unit: "GPa" },
        }),
      }),
    );
    await user.click(registerRows);
    await waitFor(() =>
      expect(mocks.publishRegistration).toHaveBeenCalledOnce(),
    );
  });
});
