import { describe, expect, it } from "vitest";

import {
  buildModelingDataLibraryRows,
  filterModelingDataLibraryRows,
  modelingDataFacetValues,
  modelingDataGraphTitle,
  modelingTestConditionLabel,
  modelingTestRunDisplayLabel,
} from "./modeling-data-library-model";

const revision = {
  id: "document-revision-1",
  aggregate_id: "document-1",
  revision_no: 2,
  based_on_revision_id: null,
  schema_id: "urn:cmp:test-data:1.0.0",
  schema_version: "1.0.0",
  content_hash: "a".repeat(64),
  created_at: "2026-08-01T00:00:00Z",
  created_by: "user-1",
  change_reason: "test",
  organization_id: "org-1",
  project_id: "project-1",
  classification: "internal",
  lifecycle_state: "draft",
};

function documentFixture(overrides: Record<string, unknown> = {}) {
  return {
    test_data_document_id: "document-1",
    current_revision: revision,
    document_key: "PA66-GF30-TENSILE-1",
    material_maker: "Example",
    material_grade: "PA66-GF30",
    lot_batch: null,
    test_date: "2026-08-12",
    operator: "Engineer",
    laboratory: "Lab",
    method: "tensile",
    specimen_id: "S-1",
    point_count: 617,
    canonical_artifact_id: "canonical-1",
    canonical_sha256: "b".repeat(64),
    normalized_artifact_id: "normalized-1",
    normalized_sha256: "c".repeat(64),
    channels: [
      { key: "strain", name: "Strain", quantity_semantics: "mechanics.strain.engineering", axis_role: "independent", original_unit_string: "%", normalized_unit: "1", point_count: 617, missing_count: 0 },
      { key: "stress", name: "Stress", quantity_semantics: "mechanics.stress.engineering", axis_role: "dependent", original_unit_string: "MPa", normalized_unit: "Pa", point_count: 617, missing_count: 0 },
    ],
    governed_source: {
      material: { aggregate_id: "material-1", revision_id: "material-revision-1" },
      material_state: { aggregate_id: "state-1", revision_id: "state-revision-1" },
      test_run: { aggregate_id: "run-1", revision_id: "run-revision-1" },
    },
    ...overrides,
  };
}

function runFixture(revisionId = "run-revision-1", label = "Tensile test 0001") {
  return {
    test_run_id: "run-1",
    specimen_id: "specimen-1",
    test_method_id: "method-1",
    current_revision: {
      ...revision,
      id: revisionId,
      aggregate_id: "run-1",
      content: {
        specimen_id: "specimen-1",
        specimen_revision_id: "specimen-revision-1",
        test_method_id: "method-1",
        test_method_revision_id: "method-revision-1",
        run_label: label,
        performed_at: "2026-08-12T00:00:00Z",
        test_temperature_k: 296.15,
        crosshead_speed_mm_per_min: 2,
        reference_only: true,
      },
    },
    links: {},
  };
}

describe("Modeling Data library model", () => {
  it("shows human test identity and condition only from the exact governed Test Run revision", () => {
    const rows = buildModelingDataLibraryRows(
      [documentFixture()] as never,
      [],
      [runFixture()] as never,
      { material_id: "material-1", current_revision: { ...revision, content: { name: "PA66-GF30 reference", material_code: "CMP-DEMO-PA66-GF30" } } } as never,
    );

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      recordLabel: "Tensile test 0001",
      testType: "Tensile",
      materialLabel: "PA66-GF30",
      conditionLabel: "23 °C",
      pointCount: 617,
      historical: false,
    });

    const wrongRevision = buildModelingDataLibraryRows(
      [documentFixture()] as never,
      [],
      [runFixture("run-revision-2")] as never,
    );
    expect(wrongRevision[0].conditionLabel).toBe("Not recorded");
  });

  it("keeps an older pinned revision visible without exposing a raw document key as its name", () => {
    const rows = buildModelingDataLibraryRows(
      [documentFixture()] as never,
      [{ id: "document-1", revisionId: "document-revision-1-old", revisionNo: 1, label: "PA66-GF30-TENSILE-1" }],
      [runFixture("run-revision-1", "S-1")] as never,
    );

    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({ recordLabel: "Tensile test 0001", historical: true });
    expect(rows[1]).toMatchObject({ recordLabel: "Tensile test 0001", historical: false });
    expect(rows.map((row) => row.recordLabel)).not.toContain("PA66-GF30-TENSILE-1");
  });

  it("keeps source-system demo labels off the normal surface", () => {
    const rows = buildModelingDataLibraryRows(
      [documentFixture()] as never,
      [],
      [runFixture("run-revision-1", "CMP demo tensile replicate 1")] as never,
    );

    expect(rows[0].recordLabel).toBe("Tensile test 0001");
    expect(rows[0].recordLabel).not.toMatch(/CMP|demo/i);
    expect(modelingTestRunDisplayLabel(runFixture("run-revision-1", "CMP demo tensile replicate 1") as never))
      .toBe("Tensile test 0001");
  });

  it("never turns an internal Specimen UUID suffix into a user-facing test number", () => {
    const document = documentFixture({
      document_key: "CMP-DEMO-POLYMER-FIT-RELAXATION-CSV",
      specimen_id: "CMP-DEMO-POLYMER-FIT-SR-01",
      method: "synthetic shear relaxation reference",
    });
    const run = runFixture(
      "run-revision-1",
      "CMP demo Polymer Fit shear relaxation",
    );
    run.current_revision.content.specimen_id = "511499c2-6a4c-4235-ba9c-ffdb34caf6dc";

    const rows = buildModelingDataLibraryRows(
      [document] as never,
      [],
      [run] as never,
    );

    expect(rows[0].recordLabel).toBe("Relaxation test 0001");
    expect(rows[0].recordLabel).not.toContain("0085");
  });

  it("filters the same rows used by the Browser and derives truthful graph titles", () => {
    const tensile = buildModelingDataLibraryRows([documentFixture()] as never, [], [runFixture()] as never)[0];
    const dma = buildModelingDataLibraryRows([
      documentFixture({
        test_data_document_id: "document-2",
        document_key: "PA66-GF30-DMA-2",
        specimen_id: "S-2",
        method: "dma_frequency_temperature_sweep",
        channels: [{ key: "storage", name: "Storage modulus", quantity_semantics: "modulus.storage", axis_role: "dependent", original_unit_string: "MPa", normalized_unit: "Pa", point_count: 20, missing_count: 0 }],
        governed_source: undefined,
      }),
    ] as never, [], [] as never)[0];

    expect(filterModelingDataLibraryRows([tensile, dma], { query: "PA66", testType: "DMA", condition: "" }))
      .toEqual([dma]);
    expect(modelingDataFacetValues([tensile, dma]).testTypes).toEqual(["DMA", "Tensile"]);
    expect(modelingDataGraphTitle(tensile)).toBe("Stress–strain curves");
    expect(modelingDataGraphTitle(dma)).toBe("DMA curves");
    expect(modelingTestConditionLabel(undefined)).toBe("Not recorded");
  });
});
