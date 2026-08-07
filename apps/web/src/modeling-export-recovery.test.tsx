import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createExactTargetPreview,
  promoteModelToNeutralMaterial,
  promoteProcessingOutputToTabulatedPlasticity,
} from "./api";
import { ModelingExportPrerequisites } from "./modeling-export-prerequisites";
import { ModelingTargetPreview } from "./modeling-target-preview";
import { reduceModelingSession, type ModelingSessionSummary } from "./modeling-session-context";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  createExactTargetPreview: vi.fn(),
  promoteModelToNeutralMaterial: vi.fn(),
  promoteProcessingOutputToTabulatedPlasticity: vi.fn(),
}));

const session: ModelingSessionSummary = {
  version: 3, updatedAt: "2026-07-26T00:00:00Z", materialFamily: "metal", objective: "Card",
  material: { id: "material", revisionId: "material-r1", label: "Reference", revisionNo: 1 },
  materialState: { id: "state", revisionId: "state-r1", label: "As received", revisionNo: 1 },
  testData: { id: "data", revisionId: "data-r1", label: "Test Data", revisionNo: 1 },
  mappingProfile: { id: "mapping", revisionId: "mapping-r1", label: "Mapping", revisionNo: 1 },
  processingOutput: { id: "output", revisionId: "output-r1", label: "Selected Output", revisionNo: 1 },
  selection: { id: "output", revisionId: "output-r1", label: "Selected Output", revisionNo: 1 },
  workspace: { activeStage: "export", selectedDocumentIds: [], selectedStepIndex: 0, selectedStageOrdinal: 0, plotView: "pipeline", settingsOpen: false },
};
const output = {
  processing_output_id: "output", current_revision: { id: "output-r1" }, output_sha256: "b".repeat(64),
};
const propertySet = {
  property_set_id: "properties", material_state_id: "state",
  current_revision: { id: "properties-r1", content: { material_state_revision_id: "state-r1" } },
};
const sourcePrerequisites = ["Material", "Material State", "Test Data", "Mapping Profile", "Processing Output", "Engineer selection", "Server provenance proof"]
  .map((label) => ({ label, status: "current" as const, detail: "Current exact evidence" }));
const preview = {
  preview_identity: "a".repeat(64), filename: "REFERENCE.inp", native_text: "*MATERIAL, NAME=REFERENCE\n", native_sha256: "c".repeat(64), mapping_report_sha256: "d".repeat(64),
  mapping: { items: [] },
  source: { processing_output_id: "output", processing_output_revision_id: "output-r1", processing_output_sha256: "b".repeat(64), material_id: "material", material_revision_id: "material-r1", material_state_id: "state", material_state_revision_id: "state-r1", material_model_ir_revision_id: "ir-r1", neutral_material_id: "neutral", neutral_material_revision_id: "neutral-r1" },
  target: { solver: "abaqus", version: "2025", unit_system: "kg_m_s", solver_material_id: 1, material_name: "REFERENCE" }, acknowledgement_identity: null, non_production: true as const, delivery_status: "preview_only" as const,
};
const capabilityManifest = {
  model_family_id: "urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0",
  model_schema_version: "1.0.0",
  model_schema_digest: "f".repeat(64),
  exporters: [
    { exporter_id: "cmp.reference.abaqus-isotropic-plasticity", exporter_version: "1.0.0", exporter_digest: "e".repeat(64), solver: "abaqus", version: "2025", unit_system: "kg_m_s", keywords: ["*ELASTIC", "*PLASTIC"] },
  ],
  mapping_statuses: ["exact", "transformed", "approximated", "ignored", "unsupported", "not_applicable"] as const,
  non_production: true as const,
};

function RecoveryFlow() {
  const [current, setCurrent] = useState(session);
  const prerequisites = [...sourcePrerequisites,
    { label: "Material Model IR", status: current.materialModelIr ? "current" as const : "missing" as const, detail: "Exact session model" },
    { label: "Neutral representation", status: current.neutralModel ? "current" as const : "missing" as const, detail: "Exact Neutral" },
    { label: "Ephemeral target preview producer", status: "current" as const, detail: "Server only" },
  ];
  const onSessionEvent = (event: Parameters<typeof reduceModelingSession>[1]) => setCurrent((value) => reduceModelingSession(value, event));
  return <>
    <output aria-label="Current session pins">{`${current.materialModelIr?.revisionId ?? "none"}/${current.neutralModel?.revisionId ?? "none"}`}</output>
    {!current.materialModelIr || !current.neutralModel
      ? <ModelingExportPrerequisites config={{ baseUrl: "http://test", accessToken: "test" }} session={current} output={output as never} propertySet={propertySet as never} prerequisites={prerequisites} onSessionEvent={onSessionEvent} />
      : <ModelingTargetPreview config={{ baseUrl: "http://test", accessToken: "test" }} session={current} output={output as never} prerequisites={prerequisites} capabilityManifest={capabilityManifest} onSessionEvent={onSessionEvent} />}
  </>;
}

describe("metal Export recovery", () => {
  beforeEach(() => vi.clearAllMocks());

  it("creates exact server-backed pins through normal UI actions before mounting target preview", async () => {
    vi.mocked(promoteProcessingOutputToTabulatedPlasticity).mockResolvedValue({ data: {
      material_model_id: "upstream-model", current_revision: { id: "upstream-model-r1", revision_no: 3, content: {
        material_id: "material", material_revision_id: "material-r1", material_state_id: "state", material_state_revision_id: "state-r1", property_set_id: "properties", property_set_revision_id: "properties-r1",
        processing_projection: { output_id: "output", output_revision_id: "output-r1", output_sha256: `sha256:${"b".repeat(64)}` },
      } },
    } as never, etag: null });
    vi.mocked(promoteModelToNeutralMaterial).mockResolvedValue({ data: {
      neutral_material_id: "neutral", neutral_material_revision_id: "neutral-r1", revision_no: 4,
      document: { sources: { material: { id: "material", revision_id: "material-r1" }, material_state: { id: "state", revision_id: "state-r1" } }, candidate_selection: { processing_output: { id: "output", revision_id: "output-r1" } }, material_model_ir: { model: { id: "neutral", revision_id: "neutral-r1" } } },
    } as never, etag: null });
    vi.mocked(createExactTargetPreview).mockResolvedValue({ data: preview, etag: null });

    const { container } = render(<RecoveryFlow />);
    expect(screen.getByLabelText("Current session pins").textContent).toBe("none/none");
    expect(container.querySelector(".export-properties > .export-pane-heading")?.textContent?.trim()).toBe("Export setup");
    expect(screen.getByText("Selected model", { exact: true })).toBeTruthy();
    expect(screen.getByText("Model", { exact: true })).toBeTruthy();
    const evidence = container.querySelector<HTMLDetailsElement>("details.export-prerequisite-evidence");
    expect(evidence).toBeTruthy();
    expect(evidence?.open).toBe(false);
    expect(screen.getByRole("heading", { name: "Prepare exact metal source" })).toBeTruthy();
    expect(screen.getByRole("checkbox", { name: /acknowledge the selected bounded extrapolation/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Prepare exact model and Neutral" })).toBeTruthy();
    fireEvent.click(screen.getByLabelText(/acknowledge the selected bounded extrapolation/i));
    fireEvent.click(screen.getByRole("button", { name: "Prepare exact model and Neutral" }));

    await waitFor(() => expect(screen.getByLabelText("Current session pins").textContent).toBe("upstream-model-r1/neutral-r1"));
    expect(promoteProcessingOutputToTabulatedPlasticity).toHaveBeenCalledWith(expect.anything(), "output", expect.objectContaining({
      material_state_id: "state", property_set_revision_id: "properties-r1", processing_output_revision_id: "output-r1", acknowledge_bounded_extrapolation: true,
    }));
    expect(promoteModelToNeutralMaterial).toHaveBeenCalledWith(expect.anything(), "metal", expect.objectContaining({ material_model_id: "upstream-model", material_model_revision_id: "upstream-model-r1" }));

    fireEvent.change(screen.getByLabelText("Solver target"), { target: { value: "abaqus/2025/kg_m_s" } });
    fireEvent.change(screen.getByLabelText("Native material name"), { target: { value: "REFERENCE" } });
    await waitFor(() => expect((screen.getByRole("button", { name: "Run Export check" }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole("button", { name: "Run Export check" }));
    await waitFor(() => expect(screen.getByLabelText("Native preview")).toBeTruthy());
    expect(createExactTargetPreview).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({
      processing_output_id: "output", processing_output_revision_id: "output-r1", neutral_material_id: "neutral", neutral_material_revision_id: "neutral-r1",
    }));
    expect(vi.mocked(createExactTargetPreview).mock.calls[0][1]).not.toHaveProperty("material_model_ir_revision_id");
  });

  it("pins a successful model and retries only Neutral promotion after a partial failure", async () => {
    vi.mocked(promoteProcessingOutputToTabulatedPlasticity).mockResolvedValue({ data: {
      material_model_id: "upstream-model", current_revision: { id: "upstream-model-r1", revision_no: 3, content: {
        material_id: "material", material_revision_id: "material-r1", material_state_id: "state", material_state_revision_id: "state-r1", property_set_id: "properties", property_set_revision_id: "properties-r1",
        processing_projection: { output_id: "output", output_revision_id: "output-r1", output_sha256: `sha256:${"b".repeat(64)}` },
      } },
    } as never, etag: null });
    vi.mocked(promoteModelToNeutralMaterial)
      .mockRejectedValueOnce(new Error("Neutral unavailable"))
      .mockResolvedValueOnce({ data: {
        neutral_material_id: "neutral", neutral_material_revision_id: "neutral-r1", revision_no: 4,
        document: { sources: { material: { id: "material", revision_id: "material-r1" }, material_state: { id: "state", revision_id: "state-r1" } }, candidate_selection: { processing_output: { id: "output", revision_id: "output-r1" } }, material_model_ir: { model: { id: "neutral", revision_id: "neutral-r1" } } },
      } as never, etag: null });

    render(<RecoveryFlow />);
    fireEvent.click(screen.getByLabelText(/acknowledge the selected bounded extrapolation/i));
    fireEvent.click(screen.getByRole("button", { name: "Prepare exact model and Neutral" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("Neutral unavailable"));
    expect(screen.getByLabelText("Current session pins").textContent).toBe("upstream-model-r1/none");
    fireEvent.click(screen.getByRole("button", { name: "Retry Neutral promotion" }));
    await waitFor(() => expect(screen.getByLabelText("Current session pins").textContent).toBe("upstream-model-r1/neutral-r1"));
    expect(promoteProcessingOutputToTabulatedPlasticity).toHaveBeenCalledTimes(1);
    expect(promoteModelToNeutralMaterial).toHaveBeenCalledTimes(2);
  });
});
