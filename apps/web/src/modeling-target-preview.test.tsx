import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createExactTargetPreview, deliverExactTargetPreview, getReferenceElastoplasticExportCapabilities } from "./api";
import { ModelingTargetPreview } from "./modeling-target-preview";
import type { ExportPrerequisite } from "./modeling-export-eligibility";
import type { ModelingSessionSummary } from "./modeling-session-context";
import type { CommonProcessingPreview, ElastoplasticExportCapabilities, TargetDeliveryResponse, TargetPreviewResponse } from "./types";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  createExactTargetPreview: vi.fn(),
  deliverExactTargetPreview: vi.fn(),
  getReferenceElastoplasticExportCapabilities: vi.fn(),
}));

const session: ModelingSessionSummary = {
  version: 3, updatedAt: "2026-07-26T00:00:00Z", materialFamily: "metal", objective: "Card",
  material: { id: "material", revisionId: "material-r1", label: "Reference", revisionNo: 1 },
  materialState: { id: "state", revisionId: "state-r1", label: "As received", revisionNo: 1 },
  processingOutput: { id: "output", revisionId: "output-r1", label: "Processed", revisionNo: 1 },
  materialModelIr: { id: "ir", revisionId: "ir-r1", label: "IR", revisionNo: 1 },
  neutralModel: { id: "neutral", revisionId: "neutral-r1", label: "Neutral", revisionNo: 1 },
  workspace: { activeStage: "export", selectedDocumentIds: [], selectedStepIndex: 0, selectedStageOrdinal: 0, plotView: "pipeline", settingsOpen: false },
};
const output = { processing_output_id: "output", current_revision: { id: "output-r1" }, output_sha256: "b".repeat(64) };
const prerequisites: ExportPrerequisite[] = ["Material", "Material State", "Test Data", "Mapping Profile", "Processing Output", "Engineer selection", "Server provenance proof", "Material Model IR", "Neutral representation", "Ephemeral target preview producer"].map((label) => ({ label, status: "current", detail: "Current exact evidence" }));
const capabilities = {
  model_family_id: "urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0",
  model_schema_version: "1.0.0",
  model_schema_digest: "f".repeat(64),
  exporters: [
    { exporter_id: "cmp.reference.abaqus-isotropic-plasticity", exporter_version: "1.0.0", exporter_digest: "e".repeat(64), solver: "abaqus", version: "2025", unit_system: "kg_m_s", keywords: ["*ELASTIC", "*PLASTIC"] },
    { exporter_id: "cmp.reference.openradioss-law36", exporter_version: "1.0.0", exporter_digest: "d".repeat(64), solver: "openradioss", version: "2025", unit_system: "kg_m_s", keywords: ["/MAT/LAW36", "/FUNCT"] },
  ],
  mapping_statuses: ["exact", "transformed", "approximated", "ignored", "unsupported", "not_applicable"] as const,
  non_production: true as const,
} satisfies ElastoplasticExportCapabilities;
const preview = {
  preview_identity: "a".repeat(64), filename: "REFERENCE.inp", native_text: "*MATERIAL, NAME=REFERENCE\n", native_sha256: "c".repeat(64), mapping_report_sha256: "d".repeat(64),
  mapping: { items: [{ name: "volumetric_response", ir_path: "/model", target_representation: "LAW82", status: "approximated" as const, detail: "Acknowledged approximation." }] },
  source: { processing_output_id: "output", processing_output_revision_id: "output-r1", processing_output_sha256: "b".repeat(64), material_id: "material", material_revision_id: "material-r1", material_state_id: "state", material_state_revision_id: "state-r1", material_model_ir_revision_id: "ir-r1", neutral_material_id: "neutral", neutral_material_revision_id: "neutral-r1" },
  target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s", solver_material_id: 1, material_name: "REFERENCE" }, acknowledgement_identity: "a".repeat(64), non_production: true as const, delivery_status: "preview_only" as const,
} satisfies TargetPreviewResponse;

function deliveryResponse(): TargetDeliveryResponse {
  return {
    delivery_status: "delivered",
    receipt_id: "receipt",
    delivery_identity: preview.preview_identity,
    solver_card_id: "card",
    solver_card_revision_id: "card-r1",
    filename: preview.filename,
    native_sha256: preview.native_sha256,
    mapping_report_sha256: preview.mapping_report_sha256,
    mapping_statuses: ["approximated"],
    source: preview.source,
    target: preview.target,
    occurred_at: "2026-07-26T00:00:00Z",
    recorded_by: "actor",
    links: {
      solver_card: "/api/v1/neutral-solver-cards/card",
      preview: "/api/v1/neutral-solver-cards/card/preview",
      download: "/api/v1/neutral-solver-cards/card/download",
      receipt: "/api/v1/exporting/target-deliveries/receipt",
    },
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

describe("ModelingTargetPreview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getReferenceElastoplasticExportCapabilities).mockResolvedValue({ data: capabilities, etag: null });
  });

  it("loads solver, version, and unit choices from the metal elastoplastic capability", async () => {
    render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} />);

    expect(await screen.findByRole("option", { name: "abaqus 2025 · kg-m-s" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "openradioss 2025 · kg-m-s" })).toBeTruthy();
    expect(getReferenceElastoplasticExportCapabilities).toHaveBeenCalledTimes(1);

    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "openradioss/2025/kg_m_s" } });
    expect((screen.getByLabelText("Output unit system") as HTMLSelectElement).value).toBe("kg_m_s");
  });

  it("shows the exact human Fit selection on the normal setup surface", () => {
    render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} capabilityManifest={capabilities} fitSelection={{ displayLabel: "Voce hardening fit", mode: "single", primaryLaw: "voce" } as never} />);
    expect(screen.getAllByText("Voce hardening fit").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("Neutral", { exact: true })).toBeNull();
  });

  it("plots independently sampled persisted pairs on one shared domain without resampling", () => {
    const fitPreview: CommonProcessingPreview = {
      execution_mode: "preview",
      promotable: false,
      source_document_sha256: "d".repeat(64),
      mapping_profile_sha256: "m".repeat(64),
      independent_quantity: "strain.engineering",
      stages: [
        {
          ordinal: 5,
          method_id: "metal.engineering_to_true_plastic",
          method_version: "1.0.0",
          point_count: 3,
          series: [
            { quantity: "strain.true_plastic", unit: "1", values: [0, 0.1, 0.2] },
            { quantity: "stress.true", unit: "Pa", values: [3e8, 4e8, 5e8] },
          ],
          diagnostics: [],
          scalar_results: [],
          fit_candidates: [],
        },
        {
          ordinal: 6,
          method_id: "metal.hardening_fit_extrapolate",
          method_version: "1.0.0",
          point_count: 4,
          series: [
            { quantity: "strain.true_plastic", unit: "1", values: [0, 0.1, 0.2, 0.3] },
            { quantity: "stress.hardening.voce", unit: "Pa", values: [3.1e8, 4.1e8, 5.1e8, 5.8e8] },
          ],
          diagnostics: [],
          scalar_results: [],
          fit_candidates: [],
        },
      ],
    };
    const { container } = render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} capabilityManifest={capabilities} fitPreview={fitPreview} fitSelection={{ candidateKey: "voce", displayLabel: "Voce", mode: "single", primaryLaw: "voce", reason: "fixture", warningAcknowledged: false, fitRange: "0–1 measured; to 1 extrapolated" }} />);
    const observed = container.querySelector<SVGPolylineElement>(".fit-source-observed");
    const selected = container.querySelector<SVGPolylineElement>(".fit-source-selected");
    expect(observed?.getAttribute("points")?.trim().split(/\s+/)).toHaveLength(3);
    expect(selected?.getAttribute("points")?.trim().split(/\s+/)).toHaveLength(4);
    const graph = container.querySelector<SVGSVGElement>("svg.fit-source-graph");
    expect(graph?.getAttribute("viewBox")).toBe("0 0 320 210");
    expect(graph?.getAttribute("preserveAspectRatio")).toBe("xMidYMid meet");
    expect(container.querySelector(".fit-source-frame")).toBeTruthy();
    expect(container.querySelector(".fit-source-grid line")).toBeTruthy();
    expect(container.querySelector(".fit-source-tick")).toBeTruthy();
    expect(container.querySelector(".fit-source-axis-title")).toBeTruthy();
    expect(container.querySelector(".fit-source-svg-legend")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Solver Card preview" })).toBeTruthy();
    expect(screen.getByText("Reference target · synthetic reference", { exact: true })).toBeTruthy();
    expect(screen.getAllByText("Voce").length).toBeGreaterThanOrEqual(1);
  });

  it("requires an explicit target, sends only exact session refs, and never exposes Deliver", async () => {
    vi.mocked(createExactTargetPreview).mockResolvedValue({ data: preview, etag: null });
    const event = vi.fn();
    const { container } = render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} capabilityManifest={capabilities} onSessionEvent={event} />);

    expect((screen.getByRole("button", { name: "Run Export check" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: /deliver/i })).toBeNull();
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus/2025/kg_m_s" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Run Export check" }));

    await waitFor(() => expect(createExactTargetPreview).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({
      processing_output_id: "output", processing_output_revision_id: "output-r1", neutral_material_id: "neutral", neutral_material_revision_id: "neutral-r1", target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s" },
    })));
    const nativePreview = await screen.findByLabelText("Native preview");
    expect(nativePreview.textContent).toContain("*MATERIAL");
    expect(nativePreview.className).toContain("native-preview");
    expect(nativePreview.className).toContain("preview-scroll");
    expect(nativePreview.className).toContain("export-native-preview-viewport");
    expect(nativePreview.className).not.toContain("persistent-modeling-plot");
    expect(nativePreview.id).toBe("modeling-export-native-preview-viewport");
    expect(nativePreview.getAttribute("tabindex")).toBe("0");
    expect(nativePreview.parentElement?.className).toContain("modeling-target-preview-native-scroll-shell");
    expect(nativePreview.parentElement?.className).toContain("materials-scroll-shell");
    expect(nativePreview.parentElement?.querySelector(".materials-scroll-rail-y")).toBeNull();
    expect(screen.getByRole("heading", { name: "Solver Card preview" })).toBeTruthy();
    expect(screen.getByText(/synthetic reference$/, { exact: false })).toBeTruthy();
    expect(container.querySelector(".export-preview-state")?.textContent).toBe("Current preview · not created");
    expect(screen.queryByRole("heading", { name: "Current preview · not created" })).toBeNull();
    expect(container.querySelector(".export-divider")).toBeTruthy();
    expect(container.querySelector(".export-mapping-list")).toBeTruthy();
    const mappingViewport = container.querySelector<HTMLElement>(".export-mapping-viewport");
    expect(mappingViewport).toBeTruthy();
    expect(mappingViewport?.id).toBe("modeling-export-mapping-viewport");
    expect(mappingViewport?.getAttribute("aria-label")).toBe("Mapping details");
    expect(mappingViewport?.tabIndex).toBe(0);
    expect(mappingViewport?.parentElement?.className).toContain("modeling-target-preview-mapping-scroll-shell");
    expect(mappingViewport?.parentElement?.className).toContain("materials-scroll-shell");
    expect(mappingViewport?.parentElement?.querySelector(".materials-scroll-rail-y")).toBeNull();
    expect(container.querySelector("details.export-advanced-input")?.getAttribute("open")).toBeNull();
    expect(screen.queryByText("Review & deliver solver card", { exact: true })).toBeNull();
    expect(screen.getByText("Selected model", { exact: true })).toBeTruthy();
    expect(screen.getByText("Model", { exact: true })).toBeTruthy();
    expect(screen.queryByText("Reference / non-production", { exact: true })).toBeNull();
    expect(await screen.findByText(/Acknowledgement required before delivery/)).toBeTruthy();
    expect(screen.getAllByText("Review required", { exact: true })).toHaveLength(1);
    expect(screen.getAllByText("Reviewed", { exact: true })).toHaveLength(1);
    const acknowledgement = screen.getByLabelText("Acknowledge mapped approximations");
    const createButton = screen.getByRole("button", { name: "Create solver card" }) as HTMLButtonElement;
    expect(createButton.disabled).toBe(true);
    fireEvent.click(acknowledgement);
    expect(await screen.findByText("Ready to create", { exact: true })).toBeTruthy();
    expect(screen.queryAllByText("Review required", { exact: true })).toHaveLength(0);
    expect(createButton.disabled).toBe(false);
    expect(event).toHaveBeenCalledWith({ type: "CHANGE_EXPORT_TARGET" });
  });

  it("keeps target inputs after a failed request", async () => {
    vi.mocked(createExactTargetPreview).mockRejectedValueOnce(new Error("blocked"));
    render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} capabilityManifest={capabilities} />);
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus/2025/kg_m_s" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Run Export check" }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect((screen.getByLabelText("Solver target") as HTMLSelectElement).value).toBe("abaqus/2025/kg_m_s");
    expect((screen.getByLabelText("Native material name") as HTMLInputElement).value).toBe("REFERENCE");

  });

  it("uses concise normal-surface mapping states and keeps technical detail in Advanced", async () => {
    const statuses = ["exact", "transformed", "approximated", "ignored", "unsupported", "not_applicable"] as const;
    vi.mocked(createExactTargetPreview).mockResolvedValue({
      data: {
        ...preview,
        mapping: { items: statuses.map((status, index) => ({
          name: `quantity_${index}`,
          ir_path: `/model/${index}`,
          target_representation: `TARGET_${index}`,
          status,
          detail: `Recorded ${status}`,
        })) },
      },
      etag: null,
    });
    const { container } = render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} capabilityManifest={capabilities} />);
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus/2025/kg_m_s" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Run Export check" }));
    await screen.findByText("Quantity 1", { exact: true });
    expect(container.querySelector(".export-mapping-list")?.textContent).toContain("Exact");
    expect(container.querySelector(".export-mapping-list")?.textContent).toContain("Converted");
    expect(container.querySelector(".export-mapping-list")?.textContent).toContain("Reviewed");
    expect(container.querySelector(".export-mapping-list")?.textContent).toContain("Blocked");
    expect(container.querySelector(".export-mapping-list")?.textContent).toContain("N/A");
    expect(container.querySelector(".export-mapping > details")).toBeTruthy();
  });

  it("delivers only the current preview and binds the required acknowledgement identity", async () => {
    vi.mocked(createExactTargetPreview).mockResolvedValue({ data: preview, etag: null });
    vi.mocked(deliverExactTargetPreview).mockResolvedValue({
      data: { delivery_status: "delivered", receipt_id: "receipt", delivery_identity: preview.preview_identity, solver_card_id: "card", solver_card_revision_id: "card-r1", filename: preview.filename, native_sha256: preview.native_sha256, mapping_report_sha256: preview.mapping_report_sha256, mapping_statuses: ["approximated"], source: preview.source, target: preview.target, occurred_at: "2026-07-26T00:00:00Z", recorded_by: "actor", links: { solver_card: "/api/v1/neutral-solver-cards/card", preview: "/api/v1/neutral-solver-cards/card/preview", download: "/api/v1/neutral-solver-cards/card/download", receipt: "/api/v1/exporting/target-deliveries/receipt" } }, etag: null,
    });
    const event = vi.fn();
    render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} capabilityManifest={capabilities} onSessionEvent={event} />);
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus/2025/kg_m_s" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Run Export check" }));
    const acknowledgement = await screen.findByLabelText("Acknowledge mapped approximations");
    expect((screen.getByRole("button", { name: "Create solver card" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(acknowledgement);
    fireEvent.click(screen.getByRole("button", { name: "Create solver card" }));
    await waitFor(() => expect(deliverExactTargetPreview).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({
      preview_identity: preview.preview_identity,
      acknowledgement_identity: preview.acknowledgement_identity,
      target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s" },
    })));
    expect(await screen.findByText(/Solver card created/)).toBeTruthy();
    expect(event).toHaveBeenCalledWith({
      type: "SET_CURRENT",
      key: "exportArtifact",
      value: { id: "card", revisionId: "card-r1", label: preview.filename, revisionNo: 1 },
    });
    expect(screen.queryByRole("link", { name: "Receipt" })).toBeNull();
    fireEvent.click(screen.getByText("Delivery details", { exact: true }));
    expect(screen.getByRole("link", { name: "receipt" })).toBeTruthy();
    expect(screen.queryByText(/Activity receipt projection/)).toBeNull();
  });

  it("rejects a stale response and clears a successful preview when its exact source changes", async () => {
    vi.mocked(createExactTargetPreview)
      .mockResolvedValueOnce({ data: { ...preview, source: { ...preview.source, material_model_ir_revision_id: "neutral-r1", neutral_material_revision_id: "ir-r1" } }, etag: null })
      .mockResolvedValueOnce({ data: preview, etag: null });
    const { rerender } = render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} capabilityManifest={capabilities} />);
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus/2025/kg_m_s" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Run Export check" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("current exact Export request"));
    expect(screen.getByLabelText("Native preview").textContent).not.toContain("*MATERIAL");

    fireEvent.click(screen.getByRole("button", { name: "Retry Export check" }));
    await waitFor(() => expect(screen.getByLabelText("Native preview")).toBeTruthy());
    rerender(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={{ ...session, processingOutput: { ...session.processingOutput!, revisionId: "output-r2" } }} output={{ ...output, current_revision: { id: "output-r2" } } as never} prerequisites={prerequisites} capabilityManifest={capabilities} />);
    expect(screen.getByLabelText("Native preview").textContent).not.toContain("*MATERIAL");
  });

  it("does not restore an in-flight preview after the target changes", async () => {
    const pending = deferred<{ data: TargetPreviewResponse; etag: null }>();
    vi.mocked(createExactTargetPreview).mockReturnValueOnce(pending.promise);
    render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} capabilityManifest={capabilities} />);
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus/2025/kg_m_s" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Run Export check" }));
    await waitFor(() => expect(createExactTargetPreview).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "openradioss/2025/kg_m_s" } });
    pending.resolve({ data: preview, etag: null });

    await waitFor(() => expect(screen.getByRole("button", { name: "Run Export check" })).toBeTruthy());
    expect(screen.getByLabelText("Native preview").textContent).not.toContain("*MATERIAL");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("does not restore an in-flight preview after the exact source changes", async () => {
    const pending = deferred<{ data: TargetPreviewResponse; etag: null }>();
    vi.mocked(createExactTargetPreview).mockReturnValueOnce(pending.promise);
    const { rerender } = render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} capabilityManifest={capabilities} />);
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus/2025/kg_m_s" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Run Export check" }));
    await waitFor(() => expect(createExactTargetPreview).toHaveBeenCalledTimes(1));

    rerender(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={{ ...session, processingOutput: { ...session.processingOutput!, revisionId: "output-r2" } }} output={{ ...output, current_revision: { id: "output-r2" } } as never} prerequisites={prerequisites} capabilityManifest={capabilities} />);
    pending.resolve({ data: preview, etag: null });

    await waitFor(() => expect(screen.getByRole("button", { name: "Run Export check" })).toBeTruthy());
    expect(screen.getByLabelText("Native preview").textContent).not.toContain("*MATERIAL");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("derives destinations from the capability response and presents undeclared alternatives as unavailable", () => {
    const abaqusOnly = { ...capabilities, exporters: [capabilities.exporters[0]] };
    render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} capabilityManifest={abaqusOnly} />);
    expect(screen.getByRole("option", { name: "abaqus 2025 · kg-m-s" })).toBeTruthy();
    expect(screen.queryByRole("option", { name: "openradioss 2025 · kg-m-s" })).toBeNull();
    expect(screen.getByRole("option", { name: "Other unit systems — unavailable (not declared by this exporter capability)." })).toHaveProperty("disabled", true);
  });

  it("offers Retry Export check after a failed C1 request", async () => {
    vi.mocked(createExactTargetPreview).mockRejectedValueOnce(new Error("temporary preview failure"));
    render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} capabilityManifest={capabilities} />);
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus/2025/kg_m_s" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Run Export check" }));
    await screen.findAllByRole("alert");
    expect(screen.getByRole("button", { name: "Retry Export check" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Create solver card" })).toBeNull();
    expect(screen.queryByRole("link", { name: "receipt" })).toBeNull();
  });

  it("keeps the exact C1 preview and acknowledgement through a C2 service failure, then retries the same request", async () => {
    vi.mocked(createExactTargetPreview).mockResolvedValue({ data: preview, etag: null });
    vi.mocked(deliverExactTargetPreview)
      .mockRejectedValueOnce(new Error("C2 service unavailable"))
      .mockResolvedValueOnce({ data: deliveryResponse(), etag: null });
    const event = vi.fn();
    const navigate = vi.fn();
    render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} capabilityManifest={capabilities} onSessionEvent={event} onNavigate={navigate} />);
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus/2025/kg_m_s" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Run Export check" }));
    const acknowledgement = await screen.findByLabelText("Acknowledge mapped approximations");
    fireEvent.click(acknowledgement);
    fireEvent.click(screen.getByRole("button", { name: "Create solver card" }));
    await screen.findAllByRole("alert");

    expect(screen.getByRole("button", { name: "Retry create" })).toBeTruthy();
    expect((screen.getByLabelText("Solver target") as HTMLSelectElement).value).toBe("abaqus/2025/kg_m_s");
    expect((screen.getByLabelText("Native material name") as HTMLInputElement).value).toBe("REFERENCE");
    expect((screen.getByLabelText("Acknowledge mapped approximations") as HTMLInputElement).checked).toBe(true);
    expect(screen.getByLabelText("Native preview").textContent).toContain("*MATERIAL");
    expect(event.mock.calls.some(([value]) => (value as { type?: string }).type === "SET_CURRENT")).toBe(false);
    expect(navigate).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Retry create" }));
    await waitFor(() => expect(deliverExactTargetPreview).toHaveBeenCalledTimes(2));
    expect(vi.mocked(deliverExactTargetPreview).mock.calls[0][1]).toEqual(
      vi.mocked(deliverExactTargetPreview).mock.calls[1][1],
    );
    expect(await screen.findByText(/Solver card created/)).toBeTruthy();
  });

  it.each([
    {
      name: "a missing typed link",
      mutate: (value: TargetDeliveryResponse) => ({ ...value, links: { ...value.links, receipt: undefined } }),
    },
    {
      name: "an unexpected typed link",
      mutate: (value: TargetDeliveryResponse) => ({ ...value, links: { ...value.links, extra: "/extra" } }),
    },
    {
      name: "a mismatched source revision",
      mutate: (value: TargetDeliveryResponse) => ({ ...value, source: { ...value.source, neutral_material_revision_id: "neutral-r2" } }),
    },
    {
      name: "an unexpected source identity field",
      mutate: (value: TargetDeliveryResponse) => ({ ...value, source: { ...value.source, extra: "unexpected" } }),
    },
    {
      name: "a mismatched target identity",
      mutate: (value: TargetDeliveryResponse) => ({ ...value, target: { ...value.target, material_name: "OTHER" } }),
    },
    {
      name: "an unexpected target identity field",
      mutate: (value: TargetDeliveryResponse) => ({ ...value, target: { ...value.target, extra: "unexpected" } }),
    },
    {
      name: "a mismatched delivery identity",
      mutate: (value: TargetDeliveryResponse) => ({ ...value, delivery_identity: "f".repeat(64) }),
    },
  ])("keeps the last good C1 and exposes Retry create for $name", async ({ mutate }) => {
    vi.mocked(createExactTargetPreview).mockResolvedValue({ data: preview, etag: null });
    vi.mocked(deliverExactTargetPreview).mockResolvedValue({ data: mutate(deliveryResponse()) as TargetDeliveryResponse, etag: null });
    const event = vi.fn();
    const navigate = vi.fn();
    render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} capabilityManifest={capabilities} onSessionEvent={event} onNavigate={navigate} />);
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus/2025/kg_m_s" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Run Export check" }));
    const acknowledgement = await screen.findByLabelText("Acknowledge mapped approximations");
    fireEvent.click(acknowledgement);
    fireEvent.click(screen.getByRole("button", { name: "Create solver card" }));
    await screen.findAllByRole("alert");
    expect(screen.getByRole("button", { name: "Retry create" })).toBeTruthy();
    expect((screen.getByLabelText("Acknowledge mapped approximations") as HTMLInputElement).checked).toBe(true);
    expect(screen.getByLabelText("Native preview").textContent).toContain("*MATERIAL");
    expect(screen.queryByText(/Solver card created/)).toBeNull();
    expect(event.mock.calls.some(([value]) => (value as { type?: string }).type === "SET_CURRENT")).toBe(false);
    expect(navigate).not.toHaveBeenCalled();
  });
});
