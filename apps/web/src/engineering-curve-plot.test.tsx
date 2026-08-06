import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { dataObservedPlotBounds, derivativeValues, EngineeringCurvePlot, EngineeringCurvePlotEmpty, isGhoshTailDisplayTrim, linearInterpolate, paddedPlotBounds, plotPoints, residualValues } from "./engineering-curve-plot";
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
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("keeps an actionable engineering SVG frame for an empty Data session", () => {
    const onChooseLocal = vi.fn();
    const { container } = render(<EngineeringCurvePlotEmpty width={760} height={420} onChooseLocal={onChooseLocal} />);

    const plot = screen.getByRole("img", { name: "Empty engineering curve plot" });
    expect(plot.getAttribute("viewBox")).toBe("0 0 760 420");
    expect(container.querySelectorAll(".chart-grid")).toHaveLength(11);
    expect(container.querySelectorAll(".chart-axis")).toHaveLength(2);
    expect(container.querySelectorAll(".curve-line, polyline, path")).toHaveLength(0);
    expect(screen.getByText("Engineering strain [1]")).toBeTruthy();
    expect(screen.getByText("Engineering stress [MPa]")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Local file" }));
    expect(onChooseLocal).toHaveBeenCalledTimes(1);
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

    fireEvent.click(screen.getByRole("button", { name: "Mapped input" }));
    expect(screen.getByRole("button", { name: "Mapped input" }).getAttribute("aria-pressed")).toBe("false");
    expect(container.querySelectorAll("polyline.curve-line")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    fireEvent.click(screen.getByRole("button", { name: "Reset view" }));
    expect(screen.getByText("Wheel to zoom · drag to pan")).toBeTruthy();
  });

  it("updates the SVG coordinate system when its rendered container is resized", () => {
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
    expect(plot?.getAttribute("viewBox")).toBe("0 0 760 420");
    act(() => {
      callback?.([{ contentRect: { width: 920, height: 310 } } as ResizeObserverEntry], {} as ResizeObserver);
    });
    expect(plot?.getAttribute("viewBox")).toBe("0 0 920 310");
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
    expect(bounds.yMax).toBeGreaterThan(3e8);

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
    fireEvent.click(screen.getByRole("tab", { name: "Residual" }));
    expect(screen.getByText("predicted - observed [MPa]")).toBeTruthy();
    expect(container.querySelectorAll("polyline.curve-line")).toHaveLength(3);
    fireEvent.click(screen.getByRole("tab", { name: "Tangent modulus" }));
    expect(container.querySelectorAll(".chart-axis-label")[1]?.textContent).toMatch(/d\(stress\) \/ d\(plastic strain\) \[(M|G)Pa\]/);
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
    expect(screen.getByText("Ghosh tail near ε0 exceeds the display scale; exact values remain in Candidate parameters.")).toBeTruthy();
    expect(screen.getByText("Hardening stress [MPa]")).toBeTruthy();
    // The exact response array remains fully plotted, including the tail point.
    const ghoshLine = container.querySelector("polyline.hardening-candidate[style*='rgb']")
      ?? container.querySelector("polyline.hardening-candidate");
    expect(ghoshLine?.getAttribute("points")?.split(" ")).toHaveLength(4);
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
    expect(screen.getByText("Shear relaxation modulus [GPa]")).toBeTruthy();
    expect(container.querySelectorAll("polyline.curve-line")).toHaveLength(4);
    fireEvent.click(screen.getByRole("tab", { name: "Residual" }));
    expect(screen.getByText("Predicted minus measured [MPa]")).toBeTruthy();
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
    expect(screen.getByText("Predicted minus measured [MPa]")).toBeTruthy();
    expect(container.querySelectorAll("polyline.curve-line").length).toBeGreaterThanOrEqual(2);
  });
});
