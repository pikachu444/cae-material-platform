import type { DisplayDensity } from "./display-density";

export type DesktopViewportClass = "compact" | "standard" | "wide";

export const DESKTOP_VIEWPORT_BREAKPOINTS = {
  compactMaximum: 1390,
  wideMinimum: 1600,
} as const;

export function desktopViewportClass(width: number): DesktopViewportClass {
  if (width <= DESKTOP_VIEWPORT_BREAKPOINTS.compactMaximum) return "compact";
  if (width >= DESKTOP_VIEWPORT_BREAKPOINTS.wideMinimum) return "wide";
  return "standard";
}

export const MATERIALS_PANE_METRICS = {
  navigator: {
    min: 200,
    max: 360,
    defaults: { compact: 244, standard: 264, wide: 280 },
  },
  main: {
    min: 720,
    defaults: { compact: 1102, standard: 856, wide: 1292 },
  },
  context: {
    min: 260,
    max: 480,
    defaults: { compact: 0, standard: 280, wide: 300 },
  },
} as const;

export const DISPLAY_DENSITY_PANE_METRICS: Record<DisplayDensity, {
  navigator: { min: number; default: number; max: number };
  context: { min: number; default: number; max: number };
}> = {
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
};

export const DISPLAY_DENSITY_CONTROL_METRICS: Record<DisplayDensity, {
  control: number;
  interactive: number;
  input: number;
  navigatorRow: number;
  pane: number;
  splitter: number;
}> = {
  compact: { control: 36, interactive: 32, input: 38, navigatorRow: 26, pane: 12, splitter: 5 },
  standard: { control: 38, interactive: 34, input: 40, navigatorRow: 30, pane: 14, splitter: 6 },
  large: { control: 40, interactive: 38, input: 44, navigatorRow: 34, pane: 16, splitter: 7 },
};

export function materialsPaneDefaultsForDensity(
  viewport: DesktopViewportClass,
  density: DisplayDensity,
): { navigator: number; main: number; context: number } {
  const panes = DISPLAY_DENSITY_PANE_METRICS[density];
  return {
    navigator: panes.navigator.default,
    main: MATERIALS_PANE_METRICS.main.defaults[viewport],
    context: viewport === "compact" ? 0 : panes.context.default,
  };
}

export function modelingPaneMetricsForDensity(density: DisplayDensity): {
  min: number;
  default: number;
  max: number;
} {
  return DISPLAY_DENSITY_PANE_METRICS[density].navigator;
}

export const materialsPaneDefaults: Record<
  DesktopViewportClass,
  { navigator: number; main: number; context: number }
> = {
  compact: {
    navigator: MATERIALS_PANE_METRICS.navigator.defaults.compact,
    main: MATERIALS_PANE_METRICS.main.defaults.compact,
    context: MATERIALS_PANE_METRICS.context.defaults.compact,
  },
  standard: {
    navigator: MATERIALS_PANE_METRICS.navigator.defaults.standard,
    main: MATERIALS_PANE_METRICS.main.defaults.standard,
    context: MATERIALS_PANE_METRICS.context.defaults.standard,
  },
  wide: {
    navigator: MATERIALS_PANE_METRICS.navigator.defaults.wide,
    main: MATERIALS_PANE_METRICS.main.defaults.wide,
    context: MATERIALS_PANE_METRICS.context.defaults.wide,
  },
};

export const MODELING_PANE_METRICS = {
  navigator: {
    min: 180,
    max: 240,
    defaults: { compact: 184, standard: 192, wide: 208 },
  },
  main: { min: 720 },
  dataRibbon: { compact: 178, contentFit: 384 },
  dataPlot: { preferred: 304, min: 240, separator: 8 },
} as const;

export const MATERIALS_TREE_METRICS = {
  rowHeight: 26,
  overscanRows: 8,
  baseIndent: 8,
  levelIndent: 12,
} as const;

export const ENGINEERING_PLOT_MARGIN = {
  left: 80,
  right: 24,
  top: 24,
  bottom: 52,
} as const;

export function engineeringPlotMarginsForDensity(density: DisplayDensity): {
  left: number;
  right: number;
  top: number;
  bottom: number;
} {
  void density;
  return {
    ...ENGINEERING_PLOT_MARGIN,
  };
}

export const COLUMN_RESIZE_KEYBOARD_STEP = 8;

export const SCROLL_RAIL_METRICS = {
  thumbMinimum: 36,
  keyboardStep: 36,
} as const;
