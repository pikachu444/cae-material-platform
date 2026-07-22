import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ActivityPage } from "./material-library";
import { clearModelingSession, saveModelingSession } from "./modeling-session-context";

describe("Activity Modeling resume", () => {
  afterEach(() => {
    cleanup();
    clearModelingSession();
  });

  it("resumes the exact stage, family, Test Data revision, and curve selection", () => {
    saveModelingSession({
      materialFamily: "metal",
      objective: "Calibrate DP780",
      material: { id: "material-1", revisionId: "material-r1", label: "DP780", revisionNo: 1 },
      testData: { id: "test-1", revisionId: "test-r3", label: "DP780 tensile", revisionNo: 3 },
      workspace: {
        activeStage: "fit",
        selectedDocumentIds: ["curve-1", "curve-2"],
        selectedStepIndex: 4,
        selectedStageOrdinal: 5,
        plotView: "pipeline",
        settingsOpen: true,
      },
    });
    const navigate = vi.fn();

    render(<ActivityPage onNavigate={navigate} />);

    expect(screen.getByTestId("recent-modeling-session").textContent).toContain("metal · Fit · DP780 tensile r3 · 2 selected curves");
    fireEvent.click(screen.getByRole("button", { name: "Resume Fit" }));
    expect(navigate).toHaveBeenCalledWith("/modeling?stage=fit&family=metal");
  });
});
