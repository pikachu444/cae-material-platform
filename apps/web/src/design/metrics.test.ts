import { describe, expect, it } from "vitest";

import {
  COLUMN_RESIZE_KEYBOARD_STEP,
  desktopViewportClass,
  DISPLAY_DENSITY_PANE_METRICS,
  ENGINEERING_PLOT_MARGIN,
  engineeringPlotMarginsForDensity,
  MATERIALS_PANE_METRICS,
  MATERIALS_TREE_METRICS,
  materialsPaneDefaults,
  materialsPaneDefaultsForDensity,
  MODELING_PANE_METRICS,
  modelingPaneMetricsForDensity,
  SCROLL_RAIL_METRICS,
} from "./metrics";

describe("shared desktop metrics", () => {
  it("maps every acceptance viewport to one shared desktop class", () => {
    expect([
      desktopViewportClass(1366),
      desktopViewportClass(1440),
      desktopViewportClass(1920),
      desktopViewportClass(2560),
      desktopViewportClass(3840),
    ]).toEqual(["compact", "standard", "wide", "wide", "wide"]);
  });

  it("keeps pane defaults within their semantic bounds", () => {
    for (const layout of Object.values(materialsPaneDefaults)) {
      expect(layout.navigator).toBeGreaterThanOrEqual(MATERIALS_PANE_METRICS.navigator.min);
      expect(layout.navigator).toBeLessThanOrEqual(MATERIALS_PANE_METRICS.navigator.max);
      expect(layout.main).toBeGreaterThanOrEqual(MATERIALS_PANE_METRICS.main.min);
      if (layout.context > 0) {
        expect(layout.context).toBeGreaterThanOrEqual(MATERIALS_PANE_METRICS.context.min);
        expect(layout.context).toBeLessThanOrEqual(MATERIALS_PANE_METRICS.context.max);
      }
    }
  });

  it("publishes the approved P2 pane contract for every user density", () => {
    expect(DISPLAY_DENSITY_PANE_METRICS).toEqual({
      compact: {
        navigator: { min: 200, default: 264, max: 360 },
        context: { min: 260, default: 280, max: 480 },
      },
      standard: {
        navigator: { min: 216, default: 288, max: 384 },
        context: { min: 280, default: 304, max: 512 },
      },
      large: {
        navigator: { min: 232, default: 312, max: 416 },
        context: { min: 300, default: 328, max: 544 },
      },
    });
    expect(materialsPaneDefaultsForDensity("compact", "large")).toEqual({
      navigator: 312,
      main: 1102,
      context: 0,
    });
    expect(modelingPaneMetricsForDensity("compact")).toEqual({
      min: 200,
      default: 264,
      max: 360,
    });
  });

  it("publishes interaction, tree, ribbon, and graph geometry from one module", () => {
    expect(COLUMN_RESIZE_KEYBOARD_STEP).toBe(8);
    expect(SCROLL_RAIL_METRICS).toEqual({ thumbMinimum: 36, keyboardStep: 36 });
    expect(MATERIALS_TREE_METRICS).toEqual({
      rowHeight: 26,
      overscanRows: 8,
      baseIndent: 8,
      levelIndent: 12,
    });
    expect(MODELING_PANE_METRICS.dataRibbon).toEqual({ compact: 178, contentFit: 384 });
    expect(ENGINEERING_PLOT_MARGIN).toEqual({ left: 80, right: 24, top: 24, bottom: 52 });
    expect(engineeringPlotMarginsForDensity("compact")).toEqual({ left: 80, right: 212, top: 24, bottom: 52 });
    expect(engineeringPlotMarginsForDensity("standard")).toEqual({ left: 80, right: 230, top: 24, bottom: 52 });
    expect(engineeringPlotMarginsForDensity("large")).toEqual({ left: 80, right: 248, top: 24, bottom: 52 });
  });
});
