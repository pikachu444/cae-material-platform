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

export const COLUMN_RESIZE_KEYBOARD_STEP = 8;

export const SCROLL_RAIL_METRICS = {
  thumbMinimum: 36,
  keyboardStep: 36,
} as const;
