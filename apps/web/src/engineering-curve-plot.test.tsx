import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { dataObservedPlotBounds, derivativeValues, engineeringCurveXAxisScale, EngineeringCurvePlot, EngineeringCurvePlotEmpty, isGhoshTailDisplayTrim, linearInterpolate, paddedPlotBounds, plotPoints, readableAxisTicks, residualValues, responsiveYAxisTicks } from "./engineering-curve-plot";
import type { CommonCurveStage, CommonEnsemblePreview, CommonProcessingPreview } from "./features/modeling";

const tensileDefinition = {
  definition_version: "1.0.0" as const,
  channels: [{
    key: "strain.engineering",
    label: "Engineering strain",
    quantity_semantics: "strain.engineering",
    axis_role: "independent" as const,
    unit_contract: "common" as const,
    dimension: "strain",
    original_units: [{ unit: "1", scale_to_normalized: "1", offset_to_normalized: "0" }],
    normalized_unit: "1",
    display_unit: "1",
    display_scale: "1",
    display_offset: "0",
    value_basis: "normalized" as const,
  }, {
    key: "stress.engineering",
    label: "Engineering stress",
    quantity_semantics: "stress.engineering",
    axis_role: "dependent" as const,
    unit_contract: "common" as const,
    dimension: "force_per_area",
    original_units: [{ unit: "MPa", scale_to_normalized: "1000000", offset_to_normalized: "0" }],
    normalized_unit: "Pa",
    display_unit: "MPa",
    display_scale: "0.000001",
    display_offset: "0",
    value_basis: "normalized" as const,
  }],
  deviations: [],
};

function tensileSeries(xValues: number[], yValues: number[]) {
  return {
    point_count: xValues.length,
    returned_point_count: xValues.length,
    sampled: false,
    indices: xValues.map((_, index) => index),
    channels: [
      { key: "strain.engineering", values: xValues },
      { key: "stress.engineering", values: yValues },
    ],
    deviations: [],
    source_counts: [],
  };
}

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
  metadata_state: "declared",
  curve_definition_sha256: "f".repeat(64),
  curve_definition: tensileDefinition,
  curve_series: tensileSeries([0, 0.001, 0.002], [0, 2e8, 3e8]),
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
  metadata_state: "declared",
  curve_definition_sha256: "e".repeat(64),
  curve_definition: tensileDefinition,
  curve_series: tensileSeries([0, 0.0007, 0.0014, 0.002], [0, 1.5e8, 2.5e8, 3e8]),
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
  it("uses a log axis for wide positive time or frequency inputs only", () => {
    expect(engineeringCurveXAxisScale("time", [1e-6, 1, 1e6])).toBe("log10");
    expect(engineeringCurveXAxisScale("frequency", [0.01, 1, 100])).toBe("log10");
    expect(engineeringCurveXAxisScale("time", [1, 2, 10])).toBe("linear");
    expect(engineeringCurveXAxisScale("strain.engineering", [1e-6, 1])).toBe("linear");
    expect(engineeringCurveXAxisScale("time", [0, 1, 100])).toBe("linear");
  });

  it("reduces y-axis tick density when a bounded dock leaves a short graph", () => {
    expect(responsiveYAxisTicks(0, 10, 154)).toEqual([0, 5, 10]);
    expect(responsiveYAxisTicks(0, 10, 207)).toHaveLength(6);
  });

  it("keeps Data review y-axis values separate at the rendered 1366 graph height", () => {
    let callback: ResizeObserverCallback | undefined;
    class ResizeObserverMock {
      constructor(next: ResizeObserverCallback) { callback = next; }
      observe() {}
      disconnect() {}
      unobserve() {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
    const { container } = render(
      <EngineeringCurvePlot
        preview={preview}
        activeStage={activeStage}
        baseStage={baseStage}
        width={1348}
        height={133}
        observedCurves={[{ id: "doc-1:r1", label: "Specimen 01 · r1", preview }]}
        reviewOnly
      />,
    );

    act(() => {
      callback?.([{ contentRect: { width: 1348, height: 133 } } as ResizeObserverEntry], {} as ResizeObserver);
    });

    const yTickLabels = [...container.querySelectorAll<SVGTextElement>(".chart-tick")]
      .filter((label) => label.getAttribute("x") === "72")
      .map((label) => ({ text: label.textContent, y: Number(label.getAttribute("y")) }));
    expect(yTickLabels.map((label) => label.text)).toEqual(["0", "200"]);
    expect(yTickLabels[0].y - yTickLabels[1].y).toBeGreaterThan(24);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("keeps an engineering SVG frame without duplicating the Data source action", () => {
    const { container } = render(<EngineeringCurvePlotEmpty width={760} height={420} />);

    const plot = screen.getByRole("img", { name: "Empty engineering curve plot" });
    expect(plot.getAttribute("viewBox")).toBe("0 0 760 420");
    expect(container.querySelectorAll(".chart-grid")).toHaveLength(11);
    expect(container.querySelectorAll(".chart-axis")).toHaveLength(2);
    expect(container.querySelectorAll(".curve-line, polyline, path")).toHaveLength(0);
    expect(screen.getByText("Engineering strain [1]")).toBeTruthy();
    expect(screen.getByText("Engineering stress [MPa]")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Import file" })).toBeNull();
  });

  it("lets an empty or blocked graph follow a constrained semantic frame", () => {
    let callback: ResizeObserverCallback | undefined;
    class ResizeObserverMock {
      constructor(next: ResizeObserverCallback) { callback = next; }
      observe() {}
      disconnect() {}
      unobserve() {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
    const { container } = render(<EngineeringCurvePlotEmpty width={760} height={420} blocked />);
    const plot = screen.getByRole("img", { name: "Blocked engineering curve plot" });

    act(() => {
      callback?.([{ contentRect: { width: 702, height: 185 } } as ResizeObserverEntry], {} as ResizeObserver);
    });

    expect(plot.getAttribute("viewBox")).toBe("0 0 702 185");
    expect(container.querySelector(".chart-axis")?.getAttribute("y1")).toBe("133");
    expect(screen.getByText("Engineering strain [1]").getAttribute("y")).toBe("177");
  });

  it("renders an exact-prerequisite blocked frame with a Data recovery action", () => {
    const onBackToData = vi.fn();
    const { container } = render(
      <EngineeringCurvePlotEmpty
        width={760}
        height={420}
        blocked
        title="Processing is blocked"
        message="Choose the exact Test Data revision in Data."
        onBackToData={onBackToData}
      />,
    );

    expect(container.querySelector('[data-plot-state="blocked"]')).toBeTruthy();
    expect(screen.getByRole("img", { name: "Blocked engineering curve plot" })).toBeTruthy();
    expect(screen.getByText("Processing is blocked")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Back to Data" }));
    expect(onBackToData).toHaveBeenCalledOnce();
  });

  it("keeps source and processed series on their own sampling grids", () => {
    const { container } = render(
      <EngineeringCurvePlot preview={preview} activeStage={activeStage} baseStage={baseStage} width={760} height={420} />,
    );

    const plotted = Array.from(container.querySelectorAll("polyline.curve-line"));
    expect(plotted).toHaveLength(2);
    expect(plotted[0].getAttribute("points")?.split(" ")).toHaveLength(3);
    expect(plotted[1].getAttribute("points")?.split(" ")).toHaveLength(4);
    const curveClipGroup = container.querySelector("g.curve-series-clip");
    const curveClipReference = curveClipGroup?.getAttribute("clip-path");
    const curveClipId = curveClipReference?.match(/^url\(#(.+)\)$/)?.[1];
    const curveClipPath = Array.from(container.querySelectorAll("clipPath")).find((node) => node.id === curveClipId);
    const curveClipRect = curveClipPath?.querySelector("rect");
    expect(curveClipGroup).toBeTruthy();
    expect(curveClipReference).toMatch(/^url\(#.+\)$/);
    expect(container.querySelectorAll("clipPath")).toHaveLength(1);
    expect(curveClipPath?.getAttribute("clipPathUnits")).toBe("userSpaceOnUse");
    expect(Number(curveClipRect?.getAttribute("x"))).toBe(80);
    expect(Number(curveClipRect?.getAttribute("y"))).toBe(24);
    expect(Number(curveClipRect?.getAttribute("width"))).toBe(656);
    expect(Number(curveClipRect?.getAttribute("height"))).toBe(344);
    expect(plotted.every((line) => curveClipGroup?.contains(line))).toBe(true);
    expect(screen.getByText("Engineering stress [MPa]")).toBeTruthy();
  });

  it("overlays every visible real Data-stage curve with its own legend entry", () => {
    const secondPreview: CommonProcessingPreview = {
      ...preview,
      source_document_sha256: "c".repeat(64),
      stages: [{
        ...baseStage,
        series: [
          { quantity: "strain.engineering", unit: "1", values: [0, 0.001, 0.002] },
          { quantity: "stress.engineering", unit: "Pa", values: [0, 2.2e8, 3.2e8] },
        ],
      }, activeStage],
    };
    const { container } = render(
      <EngineeringCurvePlot
        preview={preview}
        activeStage={activeStage}
        baseStage={baseStage}
        width={760}
        height={420}
        observedCurves={[
          { id: "doc-1:r1", label: "Specimen 01 · r1", preview },
          { id: "doc-2:r1", label: "Specimen 02 · r1", preview: secondPreview },
        ]}
      />,
    );
    expect(container.querySelectorAll("polyline.data-observed")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Specimen 01 · r1" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Specimen 02 · r1" })).toBeTruthy();
  });

  it("keeps observed curves as a separate Process overlay layer", () => {
    const { container } = render(
      <EngineeringCurvePlot
        preview={preview}
        activeStage={activeStage}
        baseStage={baseStage}
        width={760}
        height={420}
        processOverlay
        observedCurves={[{ id: "doc-1:r1", label: "Specimen 01 · r1", preview }]}
      />,
    );

    expect(container.querySelector("polyline.process-observed")).toBeTruthy();
    expect(screen.getByText("Focused mapped input")).toBeTruthy();
    expect(screen.getByText("Selected stage")).toBeTruthy();
    expect(screen.getByText("Calculation notes")).toBeTruthy();
  });

  it("supports legend visibility and explicit zoom reset controls", () => {
    const { container } = render(
      <EngineeringCurvePlot preview={preview} activeStage={activeStage} baseStage={baseStage} width={760} height={420} />,
    );

    expect(screen.getByRole("button", { name: "Reset view" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Mapped input" }));
    expect(screen.getByRole("button", { name: "Mapped input" }).getAttribute("aria-pressed")).toBe("false");
    expect(container.querySelectorAll("polyline.curve-line")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    fireEvent.click(screen.getByRole("button", { name: "Reset view" }));
    expect(screen.queryByText("Wheel to zoom · drag to pan")).toBeNull();
  });

  it("recalculates the Data, Process, and Fit frame, axes, labels, legend, and hit region after pane resize", () => {
    let callback: ResizeObserverCallback | undefined;
    class ResizeObserverMock {
      constructor(next: ResizeObserverCallback) { callback = next; }
      observe() {}
      disconnect() {}
      unobserve() {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
    const { container } = render(
      <EngineeringCurvePlot preview={preview} activeStage={activeStage} baseStage={baseStage} width={760} height={420} />,
    );
    const plot = container.querySelector("svg");
    const axisLabelsBefore = [...container.querySelectorAll(".chart-axis-label")].map((label) => label.textContent);
    const legendCountBefore = container.querySelectorAll(".curve-legend button").length;
    const horizontalAxis = container.querySelector(".chart-axis");
    expect(plot?.getAttribute("viewBox")).toBe("0 0 760 420");
    expect(horizontalAxis?.getAttribute("x2")).toBe("736");
    expect(container.querySelector(".chart-axis-label")?.getAttribute("x")).toBe("408");
    act(() => {
      callback?.([{ contentRect: { width: 920, height: 310 } } as ResizeObserverEntry], {} as ResizeObserver);
    });
    expect(plot?.getAttribute("viewBox")).toBe("0 0 920 310");
    expect(horizontalAxis?.getAttribute("x2")).toBe("896");
    expect(container.querySelector(".chart-axis-label")?.getAttribute("x")).toBe("488");
    expect([...container.querySelectorAll(".chart-axis-label")].map((label) => label.textContent)).toEqual(axisLabelsBefore);
    expect(container.querySelectorAll(".curve-legend button")).toHaveLength(legendCountBefore);
    expect(plot?.getAttribute("role")).toBe("img");
    act(() => {
      callback?.([{ contentRect: { width: 702, height: 185 } } as ResizeObserverEntry], {} as ResizeObserver);
    });
    expect(plot?.getAttribute("viewBox")).toBe("0 0 702 185");
    expect(horizontalAxis?.getAttribute("y1")).toBe("133");
    expect(container.querySelector(".chart-axis-label")?.getAttribute("y")).toBe("177");
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
    expect(screen.getByRole("button", { name: "Pan" }).getAttribute("aria-pressed")).toBe("true");
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
        metadata_state: "declared",
        curve_definition_sha256: "9".repeat(64),
        curve_definition: {
          ...tensileDefinition,
          deviations: [{
            key: "stress.engineering.mean_ci_95_lower",
            target_channel_key: "stress.engineering",
            scope: "pointwise",
            kind: "confidence_bound",
            method_id: "normal_approximation.mean_two_sided",
            method_version: "1.0.0",
            unit: "Pa",
            bound_direction: "lower",
            band_group: "stress.engineering.mean_ci_95",
            scalar_value: null,
            series_key: "stress.engineering.mean_ci_95_lower.values",
            source_count: 2,
            source_count_series_key: null,
            confidence_level: 0.95,
            coverage: "pointwise",
            ddof: 1,
            quantile_probability: null,
            quantile_method: null,
          }, {
            key: "stress.engineering.mean_ci_95_upper",
            target_channel_key: "stress.engineering",
            scope: "pointwise",
            kind: "confidence_bound",
            method_id: "normal_approximation.mean_two_sided",
            method_version: "1.0.0",
            unit: "Pa",
            bound_direction: "upper",
            band_group: "stress.engineering.mean_ci_95",
            scalar_value: null,
            series_key: "stress.engineering.mean_ci_95_upper.values",
            source_count: 2,
            source_count_series_key: null,
            confidence_level: 0.95,
            coverage: "pointwise",
            ddof: 1,
            quantile_probability: null,
            quantile_method: null,
          }],
        },
        curve_series: {
          point_count: 3,
          returned_point_count: 3,
          sampled: false,
          indices: [0, 1, 2],
          channels: [
            { key: "strain.engineering", values: [0, 0.001, 0.002] },
            { key: "stress.engineering", values: [0, 2.1e8, 3.1e8] },
          ],
          deviations: [
            { key: "stress.engineering.mean_ci_95_lower.values", values: [0, 1.9e8, 2.9e8] },
            { key: "stress.engineering.mean_ci_95_upper.values", values: [0, 2.3e8, 3.3e8] },
          ],
          source_counts: [],
        },
      }],
      diagnostics: ["2 exact members retained"],
    };
    const { container } = render(
      <EngineeringCurvePlot preview={preview} activeStage={activeStage} baseStage={baseStage} width={760} height={420} ensemblePreview={ensemblePreview} />,
    );

    const plot = screen.getByRole("img", { name: "Aligned replicate curves with declared pointwise statistics" });
    expect(plot).toBeTruthy();
    expect(container.querySelectorAll("polyline.curve-line")).toHaveLength(3);
    expect(container.querySelector("polygon.ensemble-confidence-band")).toBeTruthy();
    expect(screen.getByText("Pointwise mean")).toBeTruthy();
    expect(screen.getByText("95% · pointwise · confidence interval · normal_approximation.mean_two_sided v1.0.0 · ddof 1")).toBeTruthy();
    fireEvent.keyDown(plot, { key: "ArrowRight" });
    expect(screen.getAllByText(/normal_approximation\.mean_two_sided/).length).toBeGreaterThan(1);
    expect(screen.getByText(/n=2/)).toBeTruthy();
    fireEvent.keyDown(plot, { key: "Escape" });
    expect(screen.queryByText(/n=2/)).toBeNull();
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

  it("overlays source, toe-corrected response, and the evaluated estimation line", () => {
    const toeStage: CommonCurveStage = {
      ...activeStage,
      method_id: "tensile.toe_zero_intercept",
      series: [
        { quantity: "strain.engineering", unit: "1", values: [-0.0003, 0.0007, 0.0017, 0.0027] },
        { quantity: "stress.engineering", unit: "Pa", values: [0, 2e8, 3e8, 4e8] },
      ],
      scalar_results: [
        { key: "toe_estimated_slope", quantity_semantics: "modulus.young", value: 200e9, unit: "Pa" },
        { key: "toe_intercept", quantity_semantics: "stress.intercept", value: -60e6, unit: "Pa" },
        { key: "toe_strain_offset", quantity_semantics: "strain.offset", value: 0.0003, unit: "1" },
      ],
    };
    const { container } = render(
      <EngineeringCurvePlot
        preview={{ ...preview, stages: [baseStage, toeStage] }}
        activeStage={toeStage}
        baseStage={baseStage}
        activeStep={{
          method_id: "tensile.toe_zero_intercept",
          method_version: "1.0.0",
          options: { minimum_strain: 0.0003, maximum_strain: 0.0023 },
        }}
        width={760}
        height={420}
      />,
    );

    expect(screen.getByText("Mapped input")).toBeTruthy();
    expect(screen.getByText("Selected stage")).toBeTruthy();
    expect(screen.getByText("Toe estimation fit")).toBeTruthy();
    expect(container.querySelectorAll("polyline.curve-line")).toHaveLength(3);
    expect(container.querySelector("polyline.toe-estimation-fit")?.getAttribute("points")?.split(" ")).toHaveLength(2);
  });

  it("rejects mismatched arrays and pads constant ranges", () => {
    expect(plotPoints([0, 1], [2], 100, 100, { xMin: 0, xMax: 1, yMin: 0, yMax: 2 })).toBe("");
    const bounds = paddedPlotBounds([1, 1], [5, 5]);
    expect(bounds.xMin).toBeLessThan(1);
    expect(bounds.xMax).toBeGreaterThan(1);
    expect(bounds.yMin).toBeLessThan(5);
    expect(bounds.yMax).toBeGreaterThan(5);
  });

  it("anchors non-negative observed engineering axes at zero without changing generic padding", () => {
    const bounds = dataObservedPlotBounds(
      [0, 0.001, 0.002],
      [0, 2e8, 3e8],
      "strain.engineering",
      "stress.engineering",
    );
    expect(bounds.xMin).toBe(0);
    expect(bounds.yMin).toBe(0);
    expect(bounds.xMax).toBeGreaterThan(0.002);
    expect(bounds.yMax).toBe(3.5e8);

    const negative = dataObservedPlotBounds(
      [-0.001, 0, 0.002],
      [-2e8, 0, 3e8],
      "strain.engineering",
      "stress.engineering",
    );
    const generic = paddedPlotBounds([-0.001, 0, 0.002], [-2e8, 0, 3e8]);
    expect(negative).toEqual(generic);
    expect(dataObservedPlotBounds([0, 1], [0, 1], "strain.true_plastic", "stress.engineering")).toEqual(paddedPlotBounds([0, 1], [0, 1]));
    expect(dataObservedPlotBounds([0, 1], [-1, 1], "strain.engineering", "predicted - measured")).toEqual(paddedPlotBounds([0, 1], [-1, 1]));
  });

  it("uses readable review ticks without changing the underlying data bounds", () => {
    expect(readableAxisTicks(0, 0.1537, 5)).toEqual([0, 0.025, 0.05, 0.075, 0.1, 0.125, 0.15]);
    expect(readableAxisTicks(0, 669_000_000, 5)).toEqual([
      0,
      100_000_000,
      200_000_000,
      300_000_000,
      400_000_000,
      500_000_000,
      600_000_000,
    ]);
  });

  it("derives residual and tangent evidence from server-evaluated candidate curves", () => {
    expect(linearInterpolate([0, 1], [10, 20], 0.25)).toBe(12.5);
    expect(linearInterpolate([0, 1], [10, 20], 1.1)).toBeNull();
    expect(residualValues([0, 0.5, 1], [10, 20, 30], [0, 1], [12, 32])).toEqual({
      xValues: [0, 0.5, 1],
      yValues: [2, 2, 2],
    });
    expect(derivativeValues([0, 0.5, 1], [10, 20, 35])).toEqual({
      xValues: [0.25, 0.75],
      yValues: [20, 30],
    });
  });

  it("compares observed hardening, residual, tangent, and explicit extrapolation domain", () => {
    const observed: CommonCurveStage = {
      ordinal: 1,
      method_id: "metal.engineering_to_true_plastic",
      method_version: "1.0.0",
      point_count: 4,
      series: [
        { quantity: "strain.true_plastic", unit: "1", values: [0, 0.04, 0.08, 0.1] },
        { quantity: "stress.true", unit: "Pa", values: [3e8, 4e8, 4.8e8, 5.1e8] },
      ],
      diagnostics: [],
      scalar_results: [],
    };
    const hardening: CommonCurveStage = {
      ordinal: 2,
      method_id: "metal.hardening_fit_extrapolate",
      method_version: "1.0.0",
      point_count: 6,
      series: [
        { quantity: "strain.true_plastic", unit: "1", values: [0, 0.04, 0.08, 0.1, 0.2, 0.3] },
        { quantity: "stress.hardening.voce", unit: "Pa", values: [3e8, 4.05e8, 4.75e8, 5.05e8, 5.8e8, 6.2e8] },
        { quantity: "stress.hardening.swift", unit: "Pa", values: [3.1e8, 3.95e8, 4.85e8, 5.15e8, 6e8, 6.5e8] },
        { quantity: "stress.hardening.selected", unit: "Pa", values: [3.05e8, 4e8, 4.8e8, 5.1e8, 5.9e8, 6.35e8] },
      ],
      diagnostics: ["extrapolated domain (0.1, 0.3] is not observed"],
      scalar_results: [],
    };
    const hardeningPreview = { ...preview, independent_quantity: "strain.true_plastic", stages: [baseStage, observed, hardening] };
    const hardeningStep = {
      method_id: "metal.hardening_fit_extrapolate",
      method_version: "1.0.0",
      options: {
        stress_quantity: "stress.true",
        fit_minimum_strain: 0,
        fit_maximum_strain: 0.1,
        primary_family: "swift",
        secondary_family: "voce",
        primary_weight: 0.6,
      },
    };
    const { container } = render(<EngineeringCurvePlot preview={hardeningPreview} activeStage={hardening} baseStage={baseStage} activeStep={hardeningStep} width={760} height={420} />);

    expect(screen.getByText("Observed plastic workup")).toBeTruthy();
    expect(screen.getByText("Preview Swift/Voce blend")).toBeTruthy();
    expect(screen.getByText("Shaded: extrapolated/unobserved")).toBeTruthy();
    expect(container.querySelector(".extrapolation-region")).toBeTruthy();
    const shade = container.querySelector(".extrapolation-region rect");
    const annotationLayer = container.querySelector(".extrapolation-annotation-layer");
    const annotationLabel = annotationLayer?.querySelector("text.extrapolation-label");
    const hardeningClipGroup = container.querySelector("g.hardening-series-clip");
    const hardeningClipReference = hardeningClipGroup?.getAttribute("clip-path");
    const hardeningClipId = hardeningClipReference?.match(/^url\(#(.+)\)$/)?.[1];
    const hardeningClipPath = Array.from(container.querySelectorAll("clipPath")).find((node) => node.id === hardeningClipId);
    const hardeningClipRect = hardeningClipPath?.querySelector("rect");
    const candidateLines = container.querySelectorAll("polyline.curve-line");
    expect(shade).toBeTruthy();
    expect(annotationLayer).toBeTruthy();
    expect(annotationLabel).toBeTruthy();
    expect(hardeningClipGroup).toBeTruthy();
    expect(hardeningClipReference).toMatch(/^url\(#.+\)$/);
    expect(container.querySelectorAll("clipPath")).toHaveLength(1);
    expect(hardeningClipRect).toBeTruthy();
    expect(Number(hardeningClipRect?.getAttribute("x"))).toBe(80);
    expect(Number(hardeningClipRect?.getAttribute("y"))).toBe(Number(shade?.getAttribute("y")));
    expect(Number(hardeningClipRect?.getAttribute("width"))).toBe(656);
    expect(Number(hardeningClipRect?.getAttribute("height"))).toBe(344);
    expect(Array.from(candidateLines).every((line) => hardeningClipGroup?.contains(line))).toBe(true);
    expect(annotationLayer?.querySelector("rect")).toBeNull();
    expect(container.querySelector(".extrapolation-region text")).toBeNull();
    expect(hardeningClipGroup?.compareDocumentPosition(annotationLayer!)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(Number(annotationLabel?.getAttribute("y"))).toBeLessThan(Number(shade?.getAttribute("y")));
    fireEvent.click(screen.getByRole("tab", { name: "Residual" }));
    expect(screen.getByText("predicted - observed [MPa]")).toBeTruthy();
    expect(container.querySelectorAll("polyline.curve-line")).toHaveLength(3);
    expect(Array.from(container.querySelectorAll("polyline.curve-line")).every((line) => hardeningClipGroup?.contains(line))).toBe(true);
    fireEvent.click(screen.getByRole("tab", { name: "Tangent modulus" }));
    expect(container.querySelectorAll(".chart-axis-label")[1]?.textContent).toMatch(/d\(stress\) \/ d\(plastic strain\) \[(M|G)Pa\]/);
    expect(Array.from(container.querySelectorAll("polyline.curve-line")).every((line) => hardeningClipGroup?.contains(line))).toBe(true);
  });

  it("uses the explicit engineer fit identity instead of labeling the preview blend as selected", () => {
    const observed: CommonCurveStage = {
      ordinal: 1,
      method_id: "metal.engineering_to_true_plastic",
      method_version: "1.0.0",
      point_count: 3,
      series: [
        { quantity: "strain.true_plastic", unit: "1", values: [0, 0.05, 0.1] },
        { quantity: "stress.true", unit: "Pa", values: [3e8, 4e8, 5e8] },
      ],
      diagnostics: [],
      scalar_results: [],
    };
    const hardening: CommonCurveStage = {
      ordinal: 2,
      method_id: "metal.hardening_fit_extrapolate",
      method_version: "1.0.0",
      point_count: 4,
      series: [
        { quantity: "strain.true_plastic", unit: "1", values: [0, 0.05, 0.1, 0.2] },
        { quantity: "stress.hardening.swift", unit: "Pa", values: [3.1e8, 4.1e8, 5.1e8, 6e8] },
        { quantity: "stress.hardening.voce", unit: "Pa", values: [3e8, 4e8, 5e8, 5.7e8] },
        { quantity: "stress.hardening.selected", unit: "Pa", values: [3.06e8, 4.06e8, 5.06e8, 5.88e8] },
      ],
      diagnostics: [],
      scalar_results: [],
    };
    const hardeningPreview = { ...preview, independent_quantity: "strain.true_plastic", stages: [baseStage, observed, hardening] };
    const hardeningStep = {
      method_id: "metal.hardening_fit_extrapolate",
      method_version: "1.0.0",
      options: {
        stress_quantity: "stress.true",
        fit_minimum_strain: 0,
        fit_maximum_strain: 0.1,
        primary_family: "swift",
        secondary_family: "voce",
        primary_weight: 0.6,
      },
    };
    render(<EngineeringCurvePlot
      preview={hardeningPreview}
      activeStage={hardening}
      baseStage={baseStage}
      activeStep={hardeningStep}
      fitSelection={{
        candidateKey: "swift",
        displayLabel: "swift",
        mode: "single",
        primaryLaw: "swift",
        reason: "",
        warningAcknowledged: false,
        fitRange: "0–0.1 measured",
      }}
      width={760}
      height={420}
    />);

    expect(screen.getByText("Selected · swift")).toBeTruthy();
    expect(screen.queryByText(/Selected blend/)).toBeNull();
    expect(screen.queryByText(/explicit engineer selection/)).toBeNull();
  });

  it("trims every Ghosh epsilon_0 response/tangent tail independent of selection", () => {
    const hardeningDefinition = {
      definition_version: "1.0.0" as const,
      channels: [
        {
          key: "strain.true_plastic",
          label: "True plastic strain",
          quantity_semantics: "strain.true_plastic",
          axis_role: "independent" as const,
          unit_contract: "common" as const,
          dimension: "strain",
          original_units: [{ unit: "1", scale_to_normalized: "1", offset_to_normalized: "0" }],
          normalized_unit: "1",
          display_unit: "1",
          display_scale: "1",
          display_offset: "0",
          value_basis: "derived" as const,
        },
        ...["ghosh", "swift", "selected"].map((family) => ({
          key: `stress.hardening.${family}`,
          label: "Hardening stress",
          quantity_semantics: `stress.hardening.${family}`,
          axis_role: "dependent" as const,
          unit_contract: "explicit_legacy" as const,
          dimension: null,
          original_units: [{ unit: "Pa", scale_to_normalized: "1", offset_to_normalized: "0" }],
          normalized_unit: "Pa",
          display_unit: "MPa",
          display_scale: "0.000001",
          display_offset: "0",
          value_basis: "derived" as const,
        })),
      ],
      deviations: [],
    };
    const observed: CommonCurveStage = {
      ordinal: 1,
      method_id: "metal.engineering_to_true_plastic",
      method_version: "1.0.0",
      point_count: 4,
      series: [
        { quantity: "strain.true_plastic", unit: "1", values: [0, 0.05, 0.1, 0.2] },
        { quantity: "stress.true", unit: "Pa", values: [3e8, 4e8, 5e8, 6e8] },
      ],
      diagnostics: [],
      scalar_results: [],
    };
    const ghosh: CommonCurveStage = {
      ordinal: 2,
      method_id: "metal.hardening_fit_extrapolate",
      method_version: "1.0.0",
      point_count: 4,
      series: [
        { quantity: "strain.true_plastic", unit: "1", values: [0, 0.05, 0.1, 0.2] },
        { quantity: "stress.hardening.ghosh", unit: "Pa", values: [3e8, 4e8, 5e8, 1e12] },
        { quantity: "stress.hardening.swift", unit: "Pa", values: [3.1e8, 4.1e8, 5.1e8, 6.2e8] },
        { quantity: "stress.hardening.selected", unit: "Pa", values: [3e8, 4e8, 5e8, 6e8] },
      ],
      diagnostics: [],
      scalar_results: [],
      metadata_state: "declared",
      curve_definition_sha256: "d".repeat(64),
      curve_definition: hardeningDefinition,
      fit_candidates: [{
        family: "ghosh",
        response: [3e8, 4e8, 5e8, 1e12],
        residual: [0, 1, 2, 3],
        tangent: [100, 200, 300, 400],
        parameter_names: ["epsilon_0"],
        parameter_units: ["1"],
        lower: [0],
        initial: [0.1],
        fitted: [0.1],
        upper: [1],
        rmse_pa: 1,
        relative_rmse: 0.1,
        objective: 1,
        scipy_cost: 1,
        convergence: true,
        nfev: 1,
        active_bound: ["epsilon_0"],
        jacobian_rank: 1,
        jacobian_tolerance: 1e-8,
        jacobian_condition: null,
        identifiability: "structural",
        uncertainty: "not_provided",
        objective_history: [1],
      }],
    };
    const selected = {
      candidateKey: "ghosh",
      displayLabel: "Ghosh",
      mode: "single" as const,
      primaryLaw: "ghosh",
      reason: "review",
      warningAcknowledged: true,
      fitRange: "0–0.1 measured",
    };
    const step = {
      method_id: "metal.hardening_fit_extrapolate",
      method_version: "1.0.0",
      options: { fit_minimum_strain: 0, fit_maximum_strain: 0.1 },
    };
    const hardeningPreview = { ...preview, independent_quantity: "strain.true_plastic", stages: [baseStage, observed, ghosh] };
    const { container, rerender } = render(<EngineeringCurvePlot preview={hardeningPreview} activeStage={ghosh} baseStage={observed} activeStep={step} fitSelection={selected} width={760} height={420} />);

    const swiftSelection = {
      ...selected,
      candidateKey: "swift",
      displayLabel: "Swift",
      primaryLaw: "swift",
      warningAcknowledged: false,
    };
    const swiftBlendSelection = {
      ...selected,
      candidateKey: "swift+voce",
      displayLabel: "Swift / Voce blend",
      mode: "blend" as const,
      primaryLaw: "swift",
      secondaryLaw: "voce",
      warningAcknowledged: false,
    };
    const ghoshBlendSelection = {
      ...selected,
      candidateKey: "ghosh+voce",
      displayLabel: "Ghosh / Voce blend",
      mode: "blend" as const,
      secondaryLaw: "voce",
    };
    expect(isGhoshTailDisplayTrim(ghosh, step, null, "response")).toBe(true);
    expect(isGhoshTailDisplayTrim(ghosh, step, swiftSelection, "response")).toBe(true);
    expect(isGhoshTailDisplayTrim(ghosh, step, swiftBlendSelection, "response")).toBe(true);
    expect(isGhoshTailDisplayTrim(ghosh, step, ghoshBlendSelection, "response")).toBe(true);
    expect(isGhoshTailDisplayTrim(ghosh, step, selected, "residual")).toBe(false);
    expect(isGhoshTailDisplayTrim(ghosh, step, selected, "derivative")).toBe(true);
    expect(screen.getByText("Ghosh exceeds chart scale")).toBeTruthy();
    expect(screen.getByText("Hardening stress [MPa]")).toBeTruthy();
    // The exact response array remains fully plotted, including the tail point.
    const ghoshLine = container.querySelector("polyline.hardening-candidate[style*='rgb']")
      ?? container.querySelector("polyline.hardening-candidate");
    expect(ghoshLine?.getAttribute("points")?.split(" ")).toHaveLength(4);
    const hardeningClipGroup = container.querySelector("g.hardening-series-clip");
    const hardeningClipReference = hardeningClipGroup?.getAttribute("clip-path");
    const hardeningClipId = hardeningClipReference?.match(/^url\(#(.+)\)$/)?.[1];
    const hardeningClipPath = Array.from(container.querySelectorAll("clipPath")).find((node) => node.id === hardeningClipId);
    const hardeningClipRect = hardeningClipPath?.querySelector("rect");
    const shade = container.querySelector(".extrapolation-region rect");
    const annotationLayer = container.querySelector(".extrapolation-annotation-layer");
    const annotationLabel = annotationLayer?.querySelector("text.extrapolation-label");
    expect(hardeningClipGroup).toBeTruthy();
    expect(hardeningClipRect).toBeTruthy();
    expect(Number(hardeningClipRect?.getAttribute("y"))).toBe(Number(shade?.getAttribute("y")));
    expect(Number(hardeningClipRect?.getAttribute("width"))).toBe(656);
    expect(Number(hardeningClipRect?.getAttribute("height"))).toBe(344);
    expect(Array.from(container.querySelectorAll("polyline.curve-line")).every((line) => hardeningClipGroup?.contains(line))).toBe(true);
    expect(hardeningClipGroup?.compareDocumentPosition(annotationLayer!)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(Number(annotationLabel?.getAttribute("y"))).toBeLessThanOrEqual(Number(hardeningClipRect?.getAttribute("y")));
    expect(container.querySelectorAll("polyline.curve-line").length).toBeGreaterThanOrEqual(4);
    fireEvent.click(screen.getByRole("tab", { name: "Tangent modulus" }));
    expect(screen.getByText("d(stress) / d(plastic strain) [Pa]")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Response" }));

    // A non-Ghosh explicit choice keeps its own full series while the Ghosh
    // candidate still cannot inflate the shared auto scale.
    rerender(<EngineeringCurvePlot preview={hardeningPreview} activeStage={ghosh} baseStage={observed} activeStep={step} fitSelection={swiftSelection} width={760} height={420} />);
    expect(screen.getByText("Hardening stress [MPa]")).toBeTruthy();
    rerender(<EngineeringCurvePlot preview={hardeningPreview} activeStage={ghosh} baseStage={observed} activeStep={step} fitSelection={ghoshBlendSelection} width={760} height={420} />);
    expect(screen.getByText("Hardening stress [MPa]")).toBeTruthy();
  });

  it("compares measured Prony relaxation and residuals on a logarithmic time axis", () => {
    const observed: CommonCurveStage = {
      ordinal: 1,
      method_id: "polymer.log_time_resample",
      method_version: "1.0.0",
      point_count: 5,
      series: [
        { quantity: "time", unit: "s", values: [0.01, 0.1, 1, 10, 100] },
        { quantity: "modulus.shear.relaxation", unit: "Pa", values: [1.1e9, 1e9, 8.5e8, 6.8e8, 5.5e8] },
      ],
      diagnostics: ["log-time grid; extrapolation rejected"],
      scalar_results: [],
    };
    const prony: CommonCurveStage = {
      ordinal: 2,
      method_id: "polymer.prony_fit_compare",
      method_version: "1.0.0",
      point_count: 5,
      series: [
        observed.series[0],
        observed.series[1],
        { quantity: "modulus.prony.candidate_1_term", unit: "Pa", values: [1.08e9, 1.01e9, 8.7e8, 6.9e8, 5.6e8] },
        { quantity: "modulus.prony.candidate_2_term", unit: "Pa", values: [1.1e9, 0.995e9, 8.52e8, 6.79e8, 5.51e8] },
        { quantity: "modulus.prony.selected", unit: "Pa", values: [1.1e9, 0.995e9, 8.52e8, 6.79e8, 5.51e8] },
      ],
      diagnostics: ["selected 2-term candidate by automatic_bic"],
      scalar_results: [
        { key: "prony_1_bic", quantity_semantics: "statistics.bayesian_information_criterion", value: 12.4, unit: "1" },
        { key: "prony_1_normalized_rmse", quantity_semantics: "statistics.root_mean_square.normalized", value: 0.025, unit: "1" },
        { key: "prony_2_bic", quantity_semantics: "statistics.bayesian_information_criterion", value: 4.2, unit: "1" },
        { key: "prony_2_normalized_rmse", quantity_semantics: "statistics.root_mean_square.normalized", value: 0.004, unit: "1" },
      ],
    };
    const pronyPreview = { ...preview, independent_quantity: "time", stages: [baseStage, observed, prony] };
    const { container } = render(<EngineeringCurvePlot preview={pronyPreview} activeStage={prony} baseStage={observed} activeStep={{ method_id: "polymer.prony_fit_compare", method_version: "1.0.0", options: { modulus_quantity: "modulus.shear.relaxation" } }} width={760} height={420} />);

    expect(screen.getByText("Measured relaxation")).toBeTruthy();
    expect(screen.getByText("Server result preview · Prony candidate")).toBeTruthy();
    expect(screen.queryByText(/Selected ·/)).toBeNull();
    expect(screen.getByText("time [s] · logarithmic")).toBeTruthy();
    expect(screen.getByText("modulus shear relaxation [GPa]")).toBeTruthy();
    expect(container.querySelectorAll("polyline.curve-line")).toHaveLength(4);
    fireEvent.click(screen.getByRole("tab", { name: "Residual" }));
    expect(screen.getByText("predicted - measured [MPa]")).toBeTruthy();
    expect(container.querySelectorAll("polyline.curve-line")).toHaveLength(3);
  });

  it("labels the actual Prony result as selected only after the engineer chooses its row", () => {
    const observed: CommonCurveStage = {
      ordinal: 1,
      method_id: "polymer.log_time_resample",
      method_version: "1.0.0",
      point_count: 3,
      series: [
        { quantity: "time", unit: "s", values: [0.1, 1, 10] },
        { quantity: "modulus.shear.relaxation", unit: "Pa", values: [1e9, 8e8, 6e8] },
      ],
      diagnostics: [],
      scalar_results: [],
    };
    const fitted: CommonCurveStage = {
      ordinal: 2,
      method_id: "polymer.prony_fit_compare",
      method_version: "1.0.0",
      point_count: 3,
      series: [
        { quantity: "time", unit: "s", values: [0.1, 1, 10] },
        { quantity: "modulus.prony.candidate_2_term", unit: "Pa", values: [1e9, 8e8, 6e8] },
        { quantity: "modulus.prony.selected", unit: "Pa", values: [1e9, 8e8, 6e8] },
      ],
      diagnostics: [],
      scalar_results: [],
    };
    render(<EngineeringCurvePlot
      preview={{ ...preview, independent_quantity: "time", stages: [baseStage, observed, fitted] }}
      activeStage={fitted}
      baseStage={observed}
      activeStep={{ method_id: "polymer.prony_fit_compare", method_version: "1.0.0", options: { modulus_quantity: "modulus.shear.relaxation" } }}
      fitSelection={{
        candidateKey: "prony:2",
        displayLabel: "2-term Prony",
        mode: "single",
        primaryLaw: "generalized_maxwell",
        actualTermCount: 2,
        requestedTermPolicy: "automatic_bic",
        reason: "",
        warningAcknowledged: false,
        fitRange: "Measured time grid",
      }}
      width={760}
      height={420}
    />);

    expect(screen.getByText("Selected · 2-term Generalized Maxwell")).toBeTruthy();
    expect(screen.getByText(/explicit engineer selection/)).toBeTruthy();
  });

  it("compares measured and fitted DMA storage/loss responses on log frequency", () => {
    const measured: CommonCurveStage = {
      ordinal: 1,
      method_id: "rows.sort_unique",
      method_version: "1.0.0",
      point_count: 4,
      series: [
        { quantity: "frequency", unit: "Hz", values: [0.01, 0.1, 1, 10] },
        { quantity: "modulus.shear.storage", unit: "Pa", values: [3.1e8, 3.8e8, 6.2e8, 8.9e8] },
        { quantity: "modulus.shear.loss", unit: "Pa", values: [3e7, 8e7, 1.7e8, 1.1e8] },
      ],
      diagnostics: [],
      scalar_results: [],
    };
    const fitted: CommonCurveStage = {
      ordinal: 2,
      method_id: "polymer.dma_prony_fit_compare",
      method_version: "1.0.0",
      point_count: 4,
      series: [
        ...measured.series,
        { quantity: "modulus.storage.prony.candidate_2_term", unit: "Pa", values: [3.1e8, 3.81e8, 6.19e8, 8.91e8] },
        { quantity: "modulus.loss.prony.candidate_2_term", unit: "Pa", values: [3.01e7, 7.99e7, 1.69e8, 1.11e8] },
        { quantity: "modulus.storage.prony.selected", unit: "Pa", values: [3.1e8, 3.81e8, 6.19e8, 8.91e8] },
        { quantity: "modulus.loss.prony.selected", unit: "Pa", values: [3.01e7, 7.99e7, 1.69e8, 1.11e8] },
      ],
      diagnostics: ["selected 2-term candidate by automatic_bic"],
      scalar_results: [
        { key: "prony_2_bic", quantity_semantics: "statistics.bayesian_information_criterion", value: -42, unit: "1" },
        { key: "prony_2_normalized_rmse", quantity_semantics: "statistics.root_mean_square.normalized", value: 0.001, unit: "1" },
      ],
    };
    const dmaPreview = { ...preview, independent_quantity: "frequency", stages: [baseStage, measured, fitted] };
    const { container } = render(
      <EngineeringCurvePlot
        preview={dmaPreview}
        activeStage={fitted}
        baseStage={measured}
        activeStep={{
          method_id: "polymer.dma_prony_fit_compare",
          method_version: "1.0.0",
          options: {
            storage_modulus_quantity: "modulus.shear.storage",
            loss_modulus_quantity: "modulus.shear.loss",
          },
        }}
        width={760}
        height={420}
      />,
    );

    expect(screen.getByText("Measured storage modulus")).toBeTruthy();
    expect(screen.getByText("Measured loss modulus")).toBeTruthy();
    expect(screen.getByText("Server result preview · storage modulus")).toBeTruthy();
    expect(screen.getByText("Server result preview · loss modulus")).toBeTruthy();
    expect(screen.getByText("frequency [Hz] · logarithmic")).toBeTruthy();
    expect(screen.getByLabelText("DMA storage and loss Prony candidate curves")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Residual" }));
    expect(screen.getByText("predicted - measured [MPa]")).toBeTruthy();
    expect(container.querySelectorAll("polyline.curve-line").length).toBeGreaterThanOrEqual(2);
  });
});
