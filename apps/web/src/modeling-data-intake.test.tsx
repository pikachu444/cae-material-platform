import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ModelingDataIntake, profileMatchesPreview } from "./modeling-data-intake";
import type { GovernedImportPreview, GovernedImportProfileResponse } from "./types";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
  } as Response;
}

const revision = {
  id: "53000000-0000-4000-8000-000000000001",
  aggregate_id: "53000000-0000-4000-8000-000000000002",
  revision_no: 1,
  based_on_revision_id: null,
  schema_id: "urn:cmp:test-data:1.0.0",
  schema_version: "1.0.0",
  content_hash: "a".repeat(64),
  created_at: "2026-07-18T00:00:00Z",
  created_by: "53000000-0000-4000-8000-000000000003",
  change_reason: "demo",
  organization_id: "53000000-0000-4000-8000-000000000004",
  project_id: "53000000-0000-4000-8000-000000000005",
  classification: "internal",
  lifecycle_state: "draft",
} as const;

describe("Modeling data intake", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("matches only an exact approved file contract", () => {
    const preview: GovernedImportPreview = {
      preview_report_id: "53000000-0000-4000-8000-000000000010",
      classification: "internal",
      raw_asset_id: "53000000-0000-4000-8000-000000000011",
      raw_artifact_id: "53000000-0000-4000-8000-000000000012",
      raw_sha256: "b".repeat(64),
      file_format: "xlsx",
      sheet_names: ["Data"],
      selected_sheet_name: "Data",
      header_row: 1,
      encoding: "binary",
      delimiter: null,
      decimal_separator: ".",
      header_columns: ["strain", "stress"],
      sample_rows: [["0", "0"]],
      status: "needs_input",
      report_sha256: "c".repeat(64),
    };
    const profile = {
      import_profile_id: "53000000-0000-4000-8000-000000000020",
      current_revision: revision,
      content: {
        profile_label: "Approved tensile mapping",
        data_schema: "monotonic_tension",
        file_format: "xlsx",
        sheet_name: "Data",
        header_row: 1,
        encoding: "binary",
        delimiter: null,
        decimal_separator: ".",
        channels: [
          { ordinal: 0, source_column: "strain", source_quantity: "engineering_strain", original_unit: "%", axis_role: "independent" },
          { ordinal: 1, source_column: "stress", source_quantity: "engineering_stress", original_unit: "MPa", axis_role: "dependent" },
        ],
        initial_gauge_length_m: null,
        initial_cross_section_area_m2: null,
        approval_kind: "human_confirmed",
        profile_sha256: "d".repeat(64),
      },
    } satisfies GovernedImportProfileResponse;

    expect(profileMatchesPreview(profile, preview)).toBe(true);
    expect(profileMatchesPreview(
      { ...profile, content: { ...profile.content, sheet_name: "Repeat" } },
      preview,
    )).toBe(false);
  });

  it("validates JSON on the graph before explicit registration", async () => {
    const canonicalDocument = {
      document_type: "cmp.test-data",
      schema_version: "1.0.0",
      document_id: "DP600-JSON-02",
    };
    const preview = {
      status: "valid",
      document_sha256: "d".repeat(64),
      canonical_size_bytes: 400,
      point_count: 3,
      condition_count: 0,
      material_maker: "CMP Demo",
      material_grade: "DP600",
      test_date: "2026-07-18",
      operator: "Tester",
      laboratory: "Lab",
      method: "reference",
      specimen_id: "S-2",
      channels: [],
      canonical_document: canonicalDocument,
    };
    const imported = {
      test_data_document_id: "53000000-0000-4000-8000-000000000030",
      current_revision: revision,
      document_key: "DP600-JSON-02",
      material_maker: "CMP Demo",
      material_grade: "DP600",
      lot_batch: null,
      test_date: "2026-07-18",
      operator: "Tester",
      laboratory: "Lab",
      method: "reference",
      specimen_id: "S-2",
      point_count: 3,
      canonical_artifact_id: "53000000-0000-4000-8000-000000000031",
      canonical_sha256: "d".repeat(64),
      normalized_artifact_id: "53000000-0000-4000-8000-000000000032",
      normalized_sha256: "e".repeat(64),
      channels: [],
    };
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/test-data:validate") && init?.method === "POST") {
        return jsonResponse(preview);
      }
      if (url.endsWith("/processing:preview") && init?.method === "POST") {
        return jsonResponse({
          execution_mode: "preview",
          promotable: false,
          source_document_sha256: "d".repeat(64),
          mapping_profile_sha256: "e".repeat(64),
          independent_quantity: "strain.engineering",
          stages: [{
            ordinal: 0,
            method_id: "mapping",
            method_version: "1.0.0",
            point_count: 3,
            series: [],
            diagnostics: ["canonical normalized values mapped"],
            scalar_results: [],
          }],
        });
      }
      if (url.endsWith("/test-data-documents") && init?.method === "POST") {
        return jsonResponse(imported, 201);
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const onPreviewDocument = vi.fn();
    const onImported = vi.fn();

    render(
      <ModelingDataIntake
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        documents={[]}
        selectedDocumentId=""
        processingMappingProfileText={JSON.stringify({
          profile_key: "test",
          label: "Test",
          independent_quantity: "strain.engineering",
          missing_data_policy: "drop_any",
          bindings: [],
          attribute_bindings: [],
        })}
        onSelectDocument={() => undefined}
        onPreviewDocument={onPreviewDocument}
        onImported={onImported}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "Test Data JSON" }));
    const file = new File([JSON.stringify(canonicalDocument)], "test-data.json", {
      type: "application/json",
    });
    Object.defineProperty(file, "text", {
      value: async () => JSON.stringify(canonicalDocument),
    });
    fireEvent.change(screen.getByLabelText("Test Data JSON file"), {
      target: { files: [file] },
    });

    expect(await screen.findByText(/3 points · 0 channels · valid/)).toBeTruthy();
    expect(onPreviewDocument).toHaveBeenCalledWith(
      canonicalDocument,
      expect.objectContaining({ execution_mode: "preview" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save dataset" }));
    await waitFor(() => expect(onImported).toHaveBeenCalledWith(imported));
  });
});
