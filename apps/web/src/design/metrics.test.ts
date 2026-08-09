import { describe, expect, it } from "vitest";

import {
  COLUMN_RESIZE_KEYBOARD_STEP,
  desktopViewportClass,
  ENGINEERING_PLOT_MARGIN,
  MATERIALS_PANE_METRICS,
  MATERIALS_TREE_METRICS,
  materialsPaneDefaults,
  MODELING_PANE_METRICS,
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
  });
});
