import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CurveContractChart } from "./curve-contract-chart";
import type { CatalogCurvePreviewResponse } from "./types";

const source = {
  binding_id: "10000000-0000-4000-8000-000000000001",
  record_id: "10000000-0000-4000-8000-000000000002",
  record_revision_id: "10000000-0000-4000-8000-000000000003",
  kind: "test_data" as const,
  object_id: "10000000-0000-4000-8000-000000000004",
  revision_id: "10000000-0000-4000-8000-000000000005",
  workbench_path: "/modeling/test-data/10000000-0000-4000-8000-000000000004",
};

const declared: CatalogCurvePreviewResponse = {
  record_id: source.record_id,
  record_revision_id: source.record_revision_id,
  attribute_definition_id: "10000000-0000-4000-8000-000000000006",
  curve_available: true,
  modeling_use: "fit_input",
  modeling_source: source,
  curve_metadata: {
    contract_version: "1.0.0",
    metadata_state: "declared",
    definition_sha256: "a".repeat(64),
    definition: {
      definition_version: "1.0.0",
      channels: [{
        key: "strain.engineering",
        label: "Engineering strain",
        quantity_semantics: "strain.engineering",
        axis_role: "independent",
        unit_contract: "common",
        dimension: "strain",
        original_units: [{ unit: "%", scale_to_normalized: "0.01", offset_to_normalized: "0" }],
        normalized_unit: "1",
        display_unit: "%",
        display_scale: "100",
        display_offset: "0",
        value_basis: "normalized",
      }, {
        key: "stress.engineering",
        label: "Engineering stress",
        quantity_semantics: "stress.engineering",
        axis_role: "dependent",
        unit_contract: "common",
        dimension: "force_per_area",
        original_units: [{ unit: "MPa", scale_to_normalized: "1000000", offset_to_normalized: "0" }],
        normalized_unit: "Pa",
        display_unit: "MPa",
        display_scale: "0.000001",
        display_offset: "0",
        value_basis: "derived",
      }],
      deviations: [{
        key: "stress.mean_ci.lower",
        target_channel_key: "stress.engineering",
        scope: "pointwise",
        kind: "confidence_bound",
        method_id: "student_t.mean_two_sided",
        method_version: "1.0.0",
        unit: "Pa",
        bound_direction: "lower",
        band_group: "stress.mean_ci",
        scalar_value: null,
        series_key: "stress.mean_ci.lower.values",
        source_count: null,
        source_count_series_key: "stress.n.values",
        confidence_level: 0.95,
        coverage: "pointwise",
        ddof: 1,
        quantile_probability: null,
        quantile_method: null,
      }, {
        key: "stress.mean_ci.upper",
        target_channel_key: "stress.engineering",
        scope: "pointwise",
        kind: "confidence_bound",
        method_id: "student_t.mean_two_sided",
        method_version: "1.0.0",
        unit: "Pa",
        bound_direction: "upper",
        band_group: "stress.mean_ci",
        scalar_value: null,
        series_key: "stress.mean_ci.upper.values",
        source_count: null,
        source_count_series_key: "stress.n.values",
        confidence_level: 0.95,
        coverage: "pointwise",
        ddof: 1,
        quantile_probability: null,
        quantile_method: null,
      }],
    },
    owning_revision: { entity_type: "test_data_document", entity_id: source.object_id, revision_id: source.revision_id },
    artifact: { artifact_id: "10000000-0000-4000-8000-000000000007", sha256: "b".repeat(64), schema_ref: "urn:cmp:test-data:normalized-parquet:1.1.0", media_type: "application/vnd.apache.parquet" },
    sources: [{ entity_type: "test_run", entity_id: "10000000-0000-4000-8000-000000000008", revision_id: "10000000-0000-4000-8000-000000000009", artifact_id: null, artifact_sha256: null }],
    provenance: [{ kind: "input_usage", entity_id: "10000000-0000-4000-8000-000000000008", revision_id: "10000000-0000-4000-8000-000000000009" }],
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
    deviations: [
      { key: "stress.mean_ci.lower.values", values: [0, 190e6, 285e6] },
      { key: "stress.mean_ci.upper.values", values: [0, 210e6, 315e6] },
    ],
    source_counts: [{ key: "stress.n.values", values: [2, 3, 3] }],
  },
};

describe("CurveContractChart", () => {
  afterEach(cleanup);

  it("uses declared labels and transforms while keyboard and pointer share exact point evidence", () => {
    const onOpenModeling = vi.fn();
    const { container } = render(<CurveContractChart preview={declared} title="Observed tensile" onOpenModeling={onOpenModeling}/>);

    const plot = screen.getByRole("img", { name: "Observed tensile: Engineering stress by Engineering strain" });
    expect(screen.getByText("Fit input")).toBeTruthy();
    expect(screen.getByText("Engineering strain [%]")).toBeTruthy();
    expect(screen.getByText("Engineering stress [MPa]")).toBeTruthy();
    expect(container.querySelector(".contract-curve-heading")?.textContent).not.toContain(
      declared.record_revision_id.slice(0, 8),
    );
    const channelUnits = screen.getByText(/original % · normalized 1 · display %/);
    expect(channelUnits.closest("details")?.open).toBe(false);
    expect(screen.getAllByText(/student_t\.mean_two_sided/).length).toBeGreaterThanOrEqual(2);
    fireEvent.keyDown(plot, { key: "ArrowRight" });
    expect(screen.getByText(/Engineering strain: 1 %/)).toBeTruthy();
    expect(screen.getByText(/lower 190 · upper 210 MPa · n=3/)).toBeTruthy();
    fireEvent.keyDown(plot, { key: "Escape" });
    expect(screen.queryByText(/lower 190 · upper 210 MPa · n=3/)).toBeNull();

    const lineToggle = screen.getByRole("button", { name: "Engineering stress" });
    fireEvent.click(lineToggle);
    expect(lineToggle.getAttribute("aria-pressed")).toBe("false");
    expect(container.querySelector("path.contract-curve-line")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Open in Modeling" }));
    expect(onOpenModeling).toHaveBeenCalledWith(source);
    fireEvent.click(screen.getByText("Curve source and technical details"));
    expect(channelUnits.closest("details")?.open).toBe(true);
    expect(screen.queryByText("Evidence")).toBeNull();
    expect(screen.getByText("urn:cmp:test-data:normalized-parquet:1.1.0")).toBeTruthy();
    expect(screen.getByText("b".repeat(64))).toBeTruthy();
  });

  it("keeps statistical envelopes view-only and does not infer metadata for an absent legacy curve", () => {
    const statistical: CatalogCurvePreviewResponse = { ...declared, modeling_use: "view_only", modeling_source: null };
    const { rerender } = render(<CurveContractChart preview={statistical} title="Replicate statistics"/>);
    expect(screen.queryByText("View only")).toBeNull();
    expect(screen.queryByText("Declared curve contract")).toBeNull();
    expect(screen.queryByText("Statistical and envelope curves are view-only.")).toBeNull();
    expect(screen.queryByText("No deviation recorded")).toBeNull();
    expect(screen.queryByRole("button", { name: "Open in Modeling" })).toBeNull();

    const absent: CatalogCurvePreviewResponse = {
      ...declared,
      modeling_use: "unavailable",
      modeling_source: null,
      curve_metadata: { ...declared.curve_metadata, metadata_state: "absent", definition_sha256: null, definition: null },
      curve_series: null,
    };
    rerender(<CurveContractChart preview={absent} title="Historical curve"/>);
    expect(screen.queryByText("View only")).toBeNull();
    expect(screen.queryByText("Curve available")).toBeNull();
    expect(screen.getByText("This revision has no recorded channel or deviation metadata.")).toBeTruthy();
    expect(screen.queryByRole("img")).toBeNull();
  });
});
