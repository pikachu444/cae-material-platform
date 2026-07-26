import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createExactTargetPreview, deliverExactTargetPreview } from "./api";
import { ModelingTargetPreview } from "./modeling-target-preview";
import type { ExportPrerequisite } from "./modeling-export-eligibility";
import type { ModelingSessionSummary } from "./modeling-session-context";
import type { TargetPreviewResponse } from "./types";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  createExactTargetPreview: vi.fn(),
  deliverExactTargetPreview: vi.fn(),
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
const preview = {
  preview_identity: "a".repeat(64), filename: "REFERENCE.inp", native_text: "*MATERIAL, NAME=REFERENCE\n", native_sha256: "c".repeat(64), mapping_report_sha256: "d".repeat(64),
  mapping: { items: [{ name: "volumetric_response", ir_path: "/model", target_representation: "LAW82", status: "approximated" as const, detail: "Acknowledged approximation." }] },
  source: { processing_output_id: "output", processing_output_revision_id: "output-r1", processing_output_sha256: "b".repeat(64), material_id: "material", material_revision_id: "material-r1", material_state_id: "state", material_state_revision_id: "state-r1", material_model_ir_revision_id: "neutral-r1", neutral_material_id: "neutral", neutral_material_revision_id: "neutral-r1" },
  target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s", solver_material_id: 1, material_name: "REFERENCE" }, acknowledgement_identity: "a".repeat(64), non_production: true as const, delivery_status: "unavailable_pending_uxc_06c2" as const,
} satisfies TargetPreviewResponse;

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
  });

  it("requires an explicit target, sends only exact session refs, and never exposes Deliver", async () => {
    vi.mocked(createExactTargetPreview).mockResolvedValue({ data: preview, etag: null });
    const event = vi.fn();
    render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} onSessionEvent={event} />);

    expect((screen.getByRole("button", { name: "Generate preview" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: /deliver/i })).toBeNull();
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate preview" }));

    await waitFor(() => expect(createExactTargetPreview).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({
      processing_output_id: "output", processing_output_revision_id: "output-r1", neutral_material_id: "neutral", neutral_material_revision_id: "neutral-r1", target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s" },
    })));
    expect((await screen.findByLabelText("Native preview")).textContent).toContain("*MATERIAL");
    expect(await screen.findByText(/Acknowledgement required before delivery/)).toBeTruthy();
    expect(event).toHaveBeenCalledWith({ type: "CHANGE_EXPORT_TARGET" });
  });

  it("keeps target inputs after a failed request", async () => {
    vi.mocked(createExactTargetPreview).mockRejectedValueOnce(new Error("blocked"));
    render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} />);
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate preview" }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect((screen.getByLabelText("Solver target") as HTMLSelectElement).value).toBe("abaqus");
    expect((screen.getByLabelText("Native material name") as HTMLInputElement).value).toBe("REFERENCE");

  });

  it("delivers only the current preview and binds the required acknowledgement identity", async () => {
    vi.mocked(createExactTargetPreview).mockResolvedValue({ data: preview, etag: null });
    vi.mocked(deliverExactTargetPreview).mockResolvedValue({
      data: { delivery_status: "delivered", receipt_id: "receipt", delivery_identity: preview.preview_identity, solver_card_id: "card", solver_card_revision_id: "card-r1", filename: preview.filename, native_sha256: preview.native_sha256, mapping_report_sha256: preview.mapping_report_sha256, mapping_statuses: ["approximated"], source: preview.source, target: preview.target, occurred_at: "2026-07-26T00:00:00Z", recorded_by: "actor", links: { preview: "/cards/card", receipt: "/receipts/receipt" } }, etag: null,
    });
    render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} />);
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate preview" }));
    const acknowledgement = await screen.findByLabelText("Acknowledge mapped approximations");
    expect((screen.getByRole("button", { name: "Deliver native card" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(acknowledgement);
    fireEvent.click(screen.getByRole("button", { name: "Deliver native card" }));
    await waitFor(() => expect(deliverExactTargetPreview).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({
      preview_identity: preview.preview_identity,
      acknowledgement_identity: preview.acknowledgement_identity,
      target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s" },
    })));
    expect(await screen.findByText(/Solver card delivered/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Receipt" })).toBeTruthy();
    expect(screen.queryByText(/Activity receipt projection/)).toBeNull();
  });

  it("rejects a stale response and clears a successful preview when its exact source changes", async () => {
    vi.mocked(createExactTargetPreview)
      .mockResolvedValueOnce({ data: { ...preview, source: { ...preview.source, material_revision_id: "old-material-r1" } }, etag: null })
      .mockResolvedValueOnce({ data: preview, etag: null });
    const { rerender } = render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} />);
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate preview" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("current exact Export request"));
    expect(screen.queryByLabelText("Native preview")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Generate preview" }));
    await waitFor(() => expect(screen.getByLabelText("Native preview")).toBeTruthy());
    rerender(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={{ ...session, processingOutput: { ...session.processingOutput!, revisionId: "output-r2" } }} output={{ ...output, current_revision: { id: "output-r2" } } as never} prerequisites={prerequisites} />);
    expect(screen.queryByLabelText("Native preview")).toBeNull();
  });

  it("does not restore an in-flight preview after the target changes", async () => {
    const pending = deferred<{ data: TargetPreviewResponse; etag: null }>();
    vi.mocked(createExactTargetPreview).mockReturnValueOnce(pending.promise);
    render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} />);
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate preview" }));
    await waitFor(() => expect(createExactTargetPreview).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "openradioss" } });
    pending.resolve({ data: preview, etag: null });

    await waitFor(() => expect(screen.getByRole("button", { name: "Generate preview" })).toBeTruthy());
    expect(screen.queryByLabelText("Native preview")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("does not restore an in-flight preview after the exact source changes", async () => {
    const pending = deferred<{ data: TargetPreviewResponse; etag: null }>();
    vi.mocked(createExactTargetPreview).mockReturnValueOnce(pending.promise);
    const { rerender } = render(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={session} output={output as never} prerequisites={prerequisites} />);
    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate preview" }));
    await waitFor(() => expect(createExactTargetPreview).toHaveBeenCalledTimes(1));

    rerender(<ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={{ ...session, processingOutput: { ...session.processingOutput!, revisionId: "output-r2" } }} output={{ ...output, current_revision: { id: "output-r2" } } as never} prerequisites={prerequisites} />);
    pending.resolve({ data: preview, etag: null });

    await waitFor(() => expect(screen.getByRole("button", { name: "Generate preview" })).toBeTruthy());
    expect(screen.queryByLabelText("Native preview")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
