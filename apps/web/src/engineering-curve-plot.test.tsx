import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EngineeringCurvePlot, paddedPlotBounds, plotPoints } from "./engineering-curve-plot";
import type { CommonCurveStage, CommonProcessingPreview } from "./types";

const baseStage: CommonCurveStage = {
  ordinal: 0,
  method_id: "mapping",
  method_version: "1.0.0",
  point_count: 3,
  series: [
    { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
    { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8] },
  ],
  diagnostics: ["mapped source retained"],
  scalar_results: [],
};

const activeStage: CommonCurveStage = {
  ordinal: 1,
  method_id: "curve.resample_linear",
  method_version: "1.0.0",
  point_count: 4,
  series: [
    { quantity: "strain.engineering", unit: "1", values: [0, 0.0007, 0.0014, 0.002] },
    { quantity: "stress.engineering", unit: "Pa", values: [0, 1.5e8, 2.5e8, 3e8] },
  ],
  diagnostics: ["processed result has its own sampling grid"],
  scalar_results: [],
};

const preview: CommonProcessingPreview = {
  execution_mode: "preview",
  promotable: false,
  source_document_sha256: "a".repeat(64),
  mapping_profile_sha256: "b".repeat(64),
  independent_quantity: "strain.engineering",
  stages: [baseStage, activeStage],
};

describe("EngineeringCurvePlot", () => {
  afterEach(cleanup);

  it("keeps source and processed series on their own sampling grids", () => {
    const { container } = render(
      <EngineeringCurvePlot preview={preview} activeStage={activeStage} baseStage={baseStage} width={760} height={420} />,
    );

    const plotted = Array.from(container.querySelectorAll("polyline.curve-line"));
    expect(plotted).toHaveLength(2);
    expect(plotted[0].getAttribute("points")?.split(" ")).toHaveLength(3);
    expect(plotted[1].getAttribute("points")?.split(" ")).toHaveLength(4);
    expect(screen.getByText("stress.engineering [MPa]")).toBeTruthy();
  });

  it("supports legend visibility and explicit zoom reset controls", () => {
    const { container } = render(
      <EngineeringCurvePlot preview={preview} activeStage={activeStage} baseStage={baseStage} width={760} height={420} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Mapped input" }));
    expect(screen.getByRole("button", { name: "Mapped input" }).getAttribute("aria-pressed")).toBe("false");
    expect(container.querySelectorAll("polyline.curve-line")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    fireEvent.click(screen.getByRole("button", { name: "Reset view" }));
    expect(screen.getByText("Wheel to zoom · drag to pan")).toBeTruthy();
  });

  it("keeps graph range selection ephemeral until the user applies it", () => {
    const onApplySelection = vi.fn();
    render(
      <EngineeringCurvePlot preview={preview} activeStage={activeStage} baseStage={baseStage} width={760} height={420} onApplySelection={onApplySelection} />,
    );
    const plot = screen.getByRole("img", { name: "Mapped and selected processing stage curve overlay" });
    Object.defineProperty(plot, "getBoundingClientRect", {
      value: () => ({ left: 0, top: 0, right: 760, bottom: 420, width: 760, height: 420, x: 0, y: 0, toJSON: () => ({}) }),
    });

    fireEvent.click(screen.getByRole("button", { name: "Select range" }));
    fireEvent.pointerDown(plot, { button: 0, pointerId: 1, clientX: 200, clientY: 200 });
    fireEvent.pointerMove(plot, { pointerId: 1, clientX: 420, clientY: 200 });
    fireEvent.pointerUp(plot, { pointerId: 1, clientX: 420, clientY: 200 });
    expect(screen.getByText(/Selected .* – .* 1/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Apply selection" }));
    expect(onApplySelection).toHaveBeenCalledWith(expect.objectContaining({
      kind: "range",
      x_quantity: "strain.engineering",
      x_unit: "1",
    }));
  });

  it("rejects mismatched arrays and pads constant ranges", () => {
    expect(plotPoints([0, 1], [2], 100, 100, { xMin: 0, xMax: 1, yMin: 0, yMax: 2 })).toBe("");
    const bounds = paddedPlotBounds([1, 1], [5, 5]);
    expect(bounds.xMin).toBeLessThan(1);
    expect(bounds.xMax).toBeGreaterThan(1);
    expect(bounds.yMin).toBeLessThan(5);
    expect(bounds.yMax).toBeGreaterThan(5);
  });
});
