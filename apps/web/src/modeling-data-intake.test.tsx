import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { startTransition, Suspense, useState } from "react";

import {
  ModelingDataIntake,
  governedSourceFor,
  mappingBlockers,
  mappingUnitConsequence,
  profileMatchesPreview,
  unmatchedMappingNotice,
} from "./modeling-data-intake";
import { curveRailIdentity } from "./common-processing-workbench";
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

  it("blocks missing, duplicate, and unsupported Test Data mappings", () => {
    const quantities = ["engineering_strain", "engineering_stress"] as const;

    expect(mappingBlockers({
      independentColumn: "strain",
      dependentColumn: "",
      independentUnit: "%",
      dependentUnit: "MPa",
      quantities,
    })).toContain("Choose the required Engineering stress channel.");

    expect(mappingBlockers({
      independentColumn: "strain",
      dependentColumn: "strain",
      independentUnit: "%",
      dependentUnit: "MPa",
      quantities,
    })).toContain("Use different source columns for Independent and Dependent.");

    expect(mappingBlockers({
      independentColumn: "strain",
      dependentColumn: "stress",
      independentUnit: "%",
      dependentUnit: "%",
      quantities,
    })).toContain("Engineering stress cannot use “%”. Choose Pa, kPa, MPa, or GPa.");
  });

  it("explains original and normalized units in the mapping recovery decision", () => {
    expect(mappingUnitConsequence("engineering_strain", "engineering_stress"))
      .toBe("Stored units stay unchanged; preview uses 1 and Pa.");
  });

  it("does not repeat the no-approved-mapping notice below the recovery decision", () => {
    expect(unmatchedMappingNotice(0)).toBe("");
    expect(unmatchedMappingNotice(1)).toBe("");
    expect(unmatchedMappingNotice(2)).toBe("More than one approved mapping matches. Choose the intended profile.");
  });

  it("keeps curve rail specimen and exact revision as two readable identity lines", () => {
    expect(curveRailIdentity("S-03", 4, 4)).toEqual({
      specimen: "Specimen 03",
      revision: "Session revision r4",
    });
    expect(curveRailIdentity("Specimen 07", 2)).toEqual({
      specimen: "Specimen 07",
      revision: "Revision r2",
    });
  });

  it("keeps the Test Data Library in a keyboard-focusable local scroll region", () => {
    const onLayoutModeChange = vi.fn();
    const documents = Array.from({ length: 4 }, (_, index) => ({
      test_data_document_id: `document-${index + 1}`,
      current_revision: { ...revision, id: `revision-${index + 1}`, revision_no: 1 },
      document_key: `DP780-TENSILE-${index + 1}`,
      material_maker: "CMP Demo",
      material_grade: "DP780",
      lot_batch: null,
      test_date: "2026-07-18",
      operator: "Tester",
      laboratory: "Lab",
      method: "tensile",
      specimen_id: `S-${index + 1}`,
      point_count: 3,
      canonical_artifact_id: `canonical-${index + 1}`,
      canonical_sha256: "a".repeat(64),
      normalized_artifact_id: `normalized-${index + 1}`,
      normalized_sha256: "b".repeat(64),
      channels: [],
    }));

    const { container } = render(
      <ModelingDataIntake
        config={{ baseUrl: "/api/v1", accessToken: "" }}
        documents={documents as never}
        selectedDocumentId=""
        processingMappingProfileText="{}"
        onSelectDocument={() => undefined}
        onPreviewDocument={() => undefined}
        onImported={() => undefined}
        onLayoutModeChange={onLayoutModeChange}
      />,
    );

    const library = screen.getByRole("list", { name: "Saved Test Data revisions" });
    expect(library.getAttribute("tabindex")).toBe("0");
    expect(container.querySelector(".data-library-scroll-shell")).toBeTruthy();
    expect(screen.getByText("Saved Test Data", { exact: true })).toBeTruthy();
    expect(screen.getByText("4 exact revisions", { exact: true })).toBeTruthy();
    expect(screen.queryByText(/Test Data records available/)).toBeNull();
    expect(library.querySelectorAll("[role='listitem']")).toHaveLength(4);
    expect(onLayoutModeChange).toHaveBeenCalledWith("compact");
  });

  it("keeps exact observed-curve hydration alive across semantically identical reload churn", async () => {
    const document = {
      test_data_document_id: "document-1",
      current_revision: { ...revision, id: "revision-1", revision_no: 1 },
      document_key: "DP780-TENSILE-1",
      material_maker: "CMP Demo",
      material_grade: "DP780",
      lot_batch: null,
      test_date: "2026-07-18",
      operator: "Tester",
      laboratory: "Lab",
      method: "tensile",
      specimen_id: "Specimen 01",
      point_count: 3,
      canonical_artifact_id: "canonical-1",
      canonical_sha256: "a".repeat(64),
      normalized_artifact_id: "normalized-1",
      normalized_sha256: "b".repeat(64),
      channels: [],
    };
    const exactRef = {
      id: "document-1",
      revisionId: "revision-1",
      label: "DP780-TENSILE-1",
      revisionNo: 1,
    };
    let resolveContent!: (response: Response) => void;
    const contentPending = new Promise<Response>((resolve) => {
      resolveContent = resolve;
    });
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/test-data-documents/document-1/revisions/revision-1/content")) {
        return contentPending;
      }
      if (url.endsWith("/processing:preview")) {
        return jsonResponse({ stages: [], source: "exact-test" });
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const onObservedCurves = vi.fn();
    const renderIntake = () => (
      <ModelingDataIntake
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        documents={[{ ...document }] as never}
        selectedTestDataRefs={[{ ...exactRef }]}
        selectedDocumentId="document-1"
        visibleDocumentKeys={["document-1:revision-1"]}
        processingMappingProfileText={JSON.stringify({ profile_key: "test" })}
        onSelectDocument={() => undefined}
        onPreviewDocument={() => undefined}
        onImported={() => undefined}
        onObservedCurves={onObservedCurves}
      />
    );

    const { rerender } = render(renderIntake());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    rerender(renderIntake());
    resolveContent({
      ok: true,
      status: 200,
      headers: new Headers(),
      blob: async () => new Blob([JSON.stringify({ schema: "test" })]),
    } as Response);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls.filter(([input]) => String(input).includes("/content"))).toHaveLength(1);
    await waitFor(() => expect(onObservedCurves).toHaveBeenLastCalledWith([
      expect.objectContaining({ id: "document-1:revision-1" }),
    ]));
  });

  it("does not let an interrupted concurrent render invalidate committed curve hydration", async () => {
    const document = {
      test_data_document_id: "document-1",
      current_revision: { ...revision, id: "revision-1", revision_no: 1 },
      document_key: "DP780-TENSILE-1",
      material_maker: "CMP Demo",
      material_grade: "DP780",
      lot_batch: null,
      test_date: "2026-07-18",
      operator: "Tester",
      laboratory: "Lab",
      method: "tensile",
      specimen_id: "Specimen 01",
      point_count: 3,
      canonical_artifact_id: "canonical-1",
      canonical_sha256: "a".repeat(64),
      normalized_artifact_id: "normalized-1",
      normalized_sha256: "b".repeat(64),
      channels: [],
    };
    const exactRef = {
      id: "document-1",
      revisionId: "revision-1",
      label: "DP780-TENSILE-1",
      revisionNo: 1,
    };
    let resolveContent!: (response: Response) => void;
    const contentPending = new Promise<Response>((resolve) => {
      resolveContent = resolve;
    });
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/test-data-documents/document-1/revisions/revision-1/content")) {
        return contentPending;
      }
      if (url.endsWith("/processing:preview")) {
        return jsonResponse({ stages: [], source: "exact-test" });
      }
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    const onObservedCurves = vi.fn();
    const neverSettles = new Promise<never>(() => undefined);
    let suspendAfterIntake = false;

    function SuspendAfterIntake() {
      if (suspendAfterIntake) throw neverSettles;
      return null;
    }

    function Harness() {
      const [visible, setVisible] = useState(true);
      return <>
        <button type="button" onClick={() => {
          suspendAfterIntake = true;
          startTransition(() => setVisible(false));
        }}>Interrupt render</button>
        <Suspense fallback={<span>Pending alternate render</span>}>
          <ModelingDataIntake
            config={{ baseUrl: "/api/v1", accessToken: "token" }}
            documents={[{ ...document }] as never}
            selectedTestDataRefs={[{ ...exactRef }]}
            selectedDocumentId="document-1"
            visibleDocumentKeys={visible ? ["document-1:revision-1"] : []}
            processingMappingProfileText={JSON.stringify({ profile_key: "test" })}
            onSelectDocument={() => undefined}
            onPreviewDocument={() => undefined}
            onImported={() => undefined}
            onObservedCurves={onObservedCurves}
          />
          <SuspendAfterIntake />
        </Suspense>
      </>;
    }

    render(<Harness />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: "Interrupt render" }));
    expect(screen.queryByText("Pending alternate render")).toBeNull();

    await act(async () => {
      resolveContent({
        ok: true,
        status: 200,
        headers: new Headers(),
        blob: async () => new Blob([JSON.stringify({ schema: "test" })]),
      } as Response);
      await contentPending;
    });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(onObservedCurves).toHaveBeenLastCalledWith([
      expect.objectContaining({ id: "document-1:revision-1" }),
    ]));
  });

  it("renders unresolved mapping recovery as a direct full-width grid child", async () => {
    const testRun = {
      test_run_id: "test-run-1",
      specimen_id: "S-1",
      test_method_id: "method-1",
      current_revision: {
        ...revision,
        content: {
          run_label: "Reference tensile run",
          performed_at: "2026-07-18T00:00:00Z",
          specimen_id: "S-1",
        },
      },
      links: {},
    };
    const upload = {
      upload_id: "upload-1",
      expected_part_count: 1,
      part_size_bytes: 1024,
    };
    const preview: GovernedImportPreview = {
      preview_report_id: "preview-1",
      classification: "internal",
      raw_asset_id: "raw-1",
      raw_artifact_id: "artifact-1",
      raw_sha256: "b".repeat(64),
      file_format: "csv",
      sheet_names: [],
      selected_sheet_name: null,
      header_row: 1,
      encoding: "utf-8",
      delimiter: ",",
      decimal_separator: ".",
      header_columns: ["strain", "stress"],
      sample_rows: [["0", "0"]],
      status: "needs_input",
      report_sha256: "c".repeat(64),
    };
    const rawAsset = {
      raw_asset_id: "raw-1",
      organization_id: "org-1",
      project_id: "project-1",
      classification: "internal",
      sha256: "a".repeat(64),
      size_bytes: 15,
      media_type: "text/csv",
      original_filename: "source.csv",
      storage_state: "staged_verified",
    };
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/material-states/state-1/test-runs")) return jsonResponse({ items: [testRun] });
      if (url.endsWith("/import-profiles")) return jsonResponse({ items: [] });
      if (url.endsWith("/uploads") && init?.method === "POST") {
        return jsonResponse({ upload, upload_capability: "capability-1" });
      }
      if (url.endsWith("/uploads/upload-1/parts/1") && init?.method === "PUT") return jsonResponse(upload);
      if (url.endsWith("/uploads/upload-1:complete") && init?.method === "POST") {
        return jsonResponse({ upload, raw_asset: rawAsset, available_artifact_id: "artifact-1" });
      }
      if (url.endsWith("/tabular-import-previews") && init?.method === "POST") return jsonResponse(preview);
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(
      <ModelingDataIntake
        config={{ baseUrl: "/api/v1", accessToken: "token" }}
        state={{ material_state_id: "state-1" } as never}
        documents={[]}
        selectedDocumentId=""
        processingMappingProfileText="{}"
        onSelectDocument={() => undefined}
        onPreviewDocument={() => undefined}
        onImported={() => undefined}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "Local file" }));
    const testRunSelect = await screen.findByRole("combobox", { name: "Local file Test Run" });
    fireEvent.change(testRunSelect, { target: { value: "test-run-1" } });
    const file = new File(["strain,stress\n0,0\n"], "source.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText("Local test data file"), { target: { files: [file] } });
    fireEvent.click(await screen.findByRole("button", { name: "Inspect source" }));

    await waitFor(() => expect(container.querySelector(".data-source-decision-grid")).toBeTruthy());
    const grid = container.querySelector(".data-source-decision-grid");
    const mapping = container.querySelector(".data-mapping-decision");
    const recovery = container.querySelector(".data-mapping-recovery-row");
    expect(grid).toBeTruthy();
    expect(mapping).toBeTruthy();
    expect(recovery?.parentElement).toBe(grid);
    expect(recovery?.closest(".data-mapping-decision")).toBeNull();
    expect(grid?.firstElementChild?.classList.contains("data-source-evidence")).toBe(true);
    expect(grid?.children[1]).toBe(mapping);
  });

  it("builds governed local-file proof from exact Material, State, and Test Run revisions", () => {
    const proof = governedSourceFor(
      {
        material_id: "53000000-0000-4000-8000-000000000040",
        current_revision: {
          ...revision,
          id: "53000000-0000-4000-8000-000000000041",
        },
      } as never,
      {
        material_state_id: "53000000-0000-4000-8000-000000000042",
        current_revision: {
          ...revision,
          id: "53000000-0000-4000-8000-000000000043",
        },
      } as never,
      {
        test_run_id: "53000000-0000-4000-8000-000000000044",
        current_revision: {
          ...revision,
          id: "53000000-0000-4000-8000-000000000045",
        },
      } as never,
    );

    expect(proof).toEqual({
      material: {
        aggregate_id: "53000000-0000-4000-8000-000000000040",
        revision_id: "53000000-0000-4000-8000-000000000041",
      },
      material_state: {
        aggregate_id: "53000000-0000-4000-8000-000000000042",
        revision_id: "53000000-0000-4000-8000-000000000043",
      },
      test_run: {
        aggregate_id: "53000000-0000-4000-8000-000000000044",
        revision_id: "53000000-0000-4000-8000-000000000045",
      },
    });
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
    const registration = fetchMock.mock.calls.find(([input, init]) =>
      String(input).endsWith("/test-data-documents") && init?.method === "POST");
    expect(registration).toBeTruthy();
    const registrationBody = JSON.parse(String(registration?.[1]?.body)) as Record<string, unknown>;
    expect(registrationBody).not.toHaveProperty("governed_source");
  });
});
