import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ActivityPage } from "./material-library";
import { clearModelingSession, saveModelingSession } from "./modeling-session-context";
import { recordDeliveryActivity } from "./solver-card-delivery";

describe("Activity Modeling resume", () => {
  afterEach(() => {
    cleanup();
    clearModelingSession();
    window.sessionStorage.clear();
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

  it("states explicitly when this browser has no Modeling session", () => {
    const navigate = vi.fn();

    render(<ActivityPage onNavigate={navigate} />);

    const empty = screen.getByRole("status", { name: "No recent Modeling session" });
    expect(empty.textContent).toContain("no local Data, Process, Fit, Validate, Review/Release, or Export session");
    expect(screen.queryByRole("button", { name: /^Resume / })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Start Modeling" }));
    expect(navigate).toHaveBeenCalledWith("/modeling");
  });

  it("reopens a Solver Card while retaining its exact revision in recent activity", () => {
    recordDeliveryActivity({
      action: "download",
      materialId: "material-1",
      materialRevisionId: "material-r2",
      materialLabel: "DP780",
      cardId: "card-1",
      cardRevisionId: "card-r3",
      cardLabel: "DP780 OpenRadioss native card",
      solver: "OpenRadioss",
      extension: ".rad",
    });
    const navigate = vi.fn();

    render(<ActivityPage onNavigate={navigate} />);

    expect(screen.getByTestId("recent-solver-card-activity").textContent).toContain("Downloaded · DP780 OpenRadioss native card");
    fireEvent.click(screen.getByRole("button", { name: "Open card" }));
    expect(navigate).toHaveBeenCalledWith("/materials/material-1/cards/card-1");
  });
});
