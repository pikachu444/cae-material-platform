import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ModelingStageShell } from "./modeling-stage-shell";
import type { ModelingSessionSummary } from "./modeling-session-context";

const session: ModelingSessionSummary = {
  version: 3,
  updatedAt: "2026-07-24T00:00:00Z",
  materialFamily: "metal",
  objective: "Calibrate",
  material: { id: "material", revisionId: "material-r1", label: "DP780", revisionNo: 1 },
  materialState: { id: "state", revisionId: "state-r1", label: "As received", revisionNo: 1 },
  testData: { id: "test", revisionId: "test-r1", label: "DP780 tensile", revisionNo: 1 },
  mappingProfile: { id: "mapping", revisionId: "mapping-r1", label: "Tensile mapping", revisionNo: 1 },
  processingOutput: { id: "output", revisionId: "output-r1", label: "Processed curves", revisionNo: 1 },
  workspace: { activeStage: "process", selectedDocumentIds: ["curve-1"], selectedStepIndex: 1, selectedStageOrdinal: 1, plotView: "ensemble", settingsOpen: true },
};

describe("ModelingStageShell", () => {
  it("shows truthful complete, warning and blocked state reasons and keeps navigation explicit", () => {
    const change = vi.fn();
    render(<ModelingStageShell session={session} activeStage="process" onStageChange={change} />);

    expect(screen.getByRole("button", { name: /Data.*Test data ready.*Exact Test Data/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Fit.*Choose a model.*decision is not yet pinned/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Validate|Review/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Export/ }));
    expect(change).toHaveBeenCalledWith("export");
  });

  it("blocks Fit without a current Processing Output and warns only when that source exists", () => {
    const change = vi.fn();
    const withoutProcessed = { ...session, processingOutput: undefined };
    const { rerender } = render(<ModelingStageShell session={withoutProcessed} activeStage="fit" onStageChange={change} />);

    expect(screen.getByRole("button", { name: /Fit.*Choose a model.*Save current processed curves/i })).toBeTruthy();
    rerender(<ModelingStageShell session={session} activeStage="fit" onStageChange={change} />);
    expect(screen.getByRole("button", { name: /Fit.*Choose a model.*decision is not yet pinned/i })).toBeTruthy();
  });

  it("warns for a pinned exact Export source and completes only for a delivered artifact", () => {
    const change = vi.fn();
    const { rerender } = render(<ModelingStageShell session={session} activeStage="export" onStageChange={change} />);

    expect(screen.getByRole("button", { name: /Export.*Ready to create card.*Exact session source pinned/i })).toBeTruthy();
    rerender(<ModelingStageShell session={{ ...session, exportArtifact: { id: "artifact", revisionId: "artifact-r1", label: "Abaqus card", revisionNo: 1 } }} activeStage="export" onStageChange={change} />);
    expect(screen.getByRole("button", { name: /Export.*Card ready.*Delivered artifact r1/i })).toBeTruthy();
  });
});
