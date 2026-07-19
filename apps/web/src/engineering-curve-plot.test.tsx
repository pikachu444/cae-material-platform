import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EngineeringCurvePlot, paddedPlotBounds, plotPoints } from "./engineering-curve-plot";
import type { CommonCurveStage, CommonEnsemblePreview, CommonProcessingPreview } from "./types";

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

  it("renders every replicate, the pointwise mean, and the confidence band in the primary plot", () => {
    const ensemblePreview: CommonEnsemblePreview = {
      execution_mode: "preview",
      promotable: false,
      mapping_profile_sha256: "c".repeat(64),
      independent_quantity: "strain.engineering",
      grid_unit: "1",
      grid: [0, 0.001, 0.002],
      members: [
        { ordinal: 1, source_document_sha256: "d".repeat(64), stage: baseStage },
        { ordinal: 2, source_document_sha256: "e".repeat(64), stage: { ...baseStage, series: [baseStage.series[0], { quantity: "stress.engineering", unit: "Pa", values: [0, 2.2e8, 3.2e8] }] } },
      ],
      statistics: [{
        quantity: "stress.engineering",
        unit: "Pa",
        mean: [0, 2.1e8, 3.1e8],
        median: [0, 2.1e8, 3.1e8],
        standard_deviation: [0, 1.4e7, 1.4e7],
        mad: [0, 1e7, 1e7],
        q1: [0, 2.05e8, 3.05e8],
        q3: [0, 2.15e8, 3.15e8],
        confidence_95_lower: [0, 1.9e8, 2.9e8],
        confidence_95_upper: [0, 2.3e8, 3.3e8],
      }],
      diagnostics: ["2 exact members retained"],
    };
    const { container } = render(
      <EngineeringCurvePlot preview={preview} activeStage={activeStage} baseStage={baseStage} width={760} height={420} ensemblePreview={ensemblePreview} />,
    );

    expect(screen.getByRole("img", { name: "Aligned replicate curves with pointwise mean and confidence interval" })).toBeTruthy();
    expect(container.querySelectorAll("polyline.curve-line")).toHaveLength(3);
    expect(container.querySelector("polygon.ensemble-confidence-band")).toBeTruthy();
    expect(screen.getByText("Pointwise mean")).toBeTruthy();
    expect(screen.getByText("95% mean confidence interval")).toBeTruthy();
  });

  it("renders the evaluated elastic line from server scalars and exact Recipe bounds", () => {
    const elasticStage: CommonCurveStage = {
      ...activeStage,
      method_id: "metal.elastic_modulus",
      scalar_results: [
        { key: "youngs_modulus", quantity_semantics: "modulus.young", value: 200e9, unit: "Pa" },
        { key: "elastic_intercept", quantity_semantics: "stress.intercept", value: 1e6, unit: "Pa" },
      ],
    };
    const { container } = render(
      <EngineeringCurvePlot
        preview={{ ...preview, stages: [baseStage, elasticStage] }}
        activeStage={elasticStage}
        baseStage={baseStage}
        activeStep={{
          method_id: "metal.elastic_modulus",
          method_version: "1.0.0",
          options: { minimum_strain: 0.0002, maximum_strain: 0.0018 },
        }}
        width={760}
        height={420}
      />,
    );

    expect(screen.getByText("Elastic fit")).toBeTruthy();
    expect(container.querySelector("polyline.engineering-fit")?.getAttribute("points")?.split(" ")).toHaveLength(2);
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
