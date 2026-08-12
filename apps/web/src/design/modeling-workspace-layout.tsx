import { type ReactNode, useEffect, useRef, useState } from "react";
import { Group, Panel, Separator, useDefaultLayout, usePanelCallbackRef, usePanelRef, type LayoutChangedMeta } from "react-resizable-panels";

import { useDisplayDensity } from "./display-density";
import {
  desktopViewportClass,
  DISPLAY_DENSITY_CONTROL_METRICS,
  MODELING_PANE_METRICS,
  modelingPaneMetricsForDensity,
  type DesktopViewportClass,
} from "./metrics";

interface ModelingWorkspaceLayoutProps {
  navigator?: ReactNode;
  ribbon: ReactNode;
  plot: ReactNode;
  dock?: ReactNode;
  dockLabel?: string;
  dataLayoutMode?: "compact" | "content-fit";
  ribbonOpen: boolean;
  onRibbonOpenChange: (open: boolean) => void;
}

export const MODELING_DATA_DEFAULT_PLOT_SIZE = MODELING_PANE_METRICS.dataPlot.preferred;
export const MODELING_DATA_PLOT_MIN_SIZE = MODELING_PANE_METRICS.dataPlot.min;
export const MODELING_DATA_SPLIT_SEPARATOR_SIZE = MODELING_PANE_METRICS.dataPlot.separator;

export function modelingDataRibbonPreferredSize(
  dataLayoutMode: "compact" | "content-fit" | undefined,
  density: "compact" | "standard" | "large" = "standard",
): number {
  const metrics = DISPLAY_DENSITY_CONTROL_METRICS[density];
  return dataLayoutMode === "content-fit"
    ? MODELING_PANE_METRICS.dataRibbon.contentFit
    : metrics.navigatorRow * 3 + metrics.interactive * 2 + metrics.pane + metrics.splitter;
}

export function ModelingWorkspaceLayout({
  navigator,
  ribbon,
  plot,
  dock,
  dockLabel = "Delivery",
  dataLayoutMode,
  ribbonOpen,
  onRibbonOpenChange,
}: ModelingWorkspaceLayoutProps) {
  const { density } = useDisplayDensity();
  const navigatorMetrics = modelingPaneMetricsForDensity(density);
  const [viewport, setViewport] = useState<DesktopViewportClass>(() =>
    desktopViewportClass(typeof window === "undefined" ? 1440 : window.innerWidth),
  );
  const navigatorRef = usePanelRef();
  const previousNavigatorDefaultRef = useRef(navigatorMetrics.default);
  const [navigatorOpen, setNavigatorOpen] = useState(true);
  const persistence = useDefaultLayout({
    id: `modeling-workspace-v1-${viewport}`,
    panelIds: ["modeling-navigator", "modeling-main"],
    storage: typeof window === "undefined" ? undefined : window.localStorage,
  });
  const [dataRibbonPanel, setDataRibbonPanel] = usePanelCallbackRef();
  const dataRibbonDesiredSizeRef = useRef(modelingDataRibbonPreferredSize(dataLayoutMode, density));
  const dataRibbonModeRef = useRef(dataLayoutMode);
  const dataRibbonDensityRef = useRef(density);
  const dataRibbonRestoreAttemptRef = useRef<{ desired: number; current: number } | null>(null);
  const mainSurfaceRef = useRef<HTMLElement>(null);
  const dockOverlayLatchedRef = useRef(false);
  const [dockOverlay, setDockOverlay] = useState(false);
  const dockPresent = Boolean(dock);
  const evidenceDock = dockLabel === "Candidate parameters" || dockLabel === "Distribution candidates";

  useEffect(() => {
    const update = () => setViewport(desktopViewportClass(window.innerWidth));
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  useEffect(() => {
    const previous = previousNavigatorDefaultRef.current;
    previousNavigatorDefaultRef.current = navigatorMetrics.default;
    const panel = navigatorRef.current;
    if (!panel || panel.isCollapsed()) return;
    const current = panel.getSize().inPixels;
    if (Math.abs(current - previous) <= 1) panel.resize(navigatorMetrics.default);
  }, [navigatorMetrics.default, navigatorRef]);

  const dataRibbonPreferredSize = modelingDataRibbonPreferredSize(dataLayoutMode, density);

  useEffect(() => {
    const modeChanged = dataRibbonModeRef.current !== dataLayoutMode;
    const densityChanged = dataRibbonDensityRef.current !== density;
    if (modeChanged || densityChanged) {
      dataRibbonModeRef.current = dataLayoutMode;
      dataRibbonDensityRef.current = density;
      dataRibbonDesiredSizeRef.current = dataRibbonPreferredSize;
      dataRibbonRestoreAttemptRef.current = null;
    }
    if (!dataLayoutMode || !dataRibbonPanel) return;
    dataRibbonPanel.resize(dataRibbonDesiredSizeRef.current);
  }, [dataLayoutMode, dataRibbonPanel, dataRibbonPreferredSize, density]);

  useEffect(() => {
    if (!dockPresent || !evidenceDock) {
      dockOverlayLatchedRef.current = false;
      setDockOverlay(false);
      return undefined;
    }
    const surface = mainSurfaceRef.current;
    if (!surface || typeof ResizeObserver === "undefined") return undefined;
    const update = () => {
      if (dockOverlayLatchedRef.current) return;
      const frame = surface.querySelector<HTMLElement>(".engineering-plot-frame");
      if (!frame || frame.getBoundingClientRect().height >= 1) return;
      dockOverlayLatchedRef.current = true;
      setDockOverlay(true);
    };
    const observer = new ResizeObserver(update);
    observer.observe(surface);
    const frame = surface.querySelector<HTMLElement>(".engineering-plot-frame");
    if (frame) observer.observe(frame);
    update();
    return () => observer.disconnect();
  }, [dockPresent, evidenceDock]);

  function resetDataRibbon(): void {
    dataRibbonDesiredSizeRef.current = dataRibbonPreferredSize;
    dataRibbonRestoreAttemptRef.current = null;
    dataRibbonPanel?.resize(dataRibbonPreferredSize);
  }

  function onDataLayoutChanged(_layout: Record<string, number>, meta: LayoutChangedMeta): void {
    const panel = dataRibbonPanel;
    if (!panel) return;

    const current = panel.getSize().inPixels;
    if (meta.isUserInteraction) {
      dataRibbonDesiredSizeRef.current = current;
      dataRibbonRestoreAttemptRef.current = null;
      return;
    }

    const desired = dataRibbonDesiredSizeRef.current;
    if (Math.abs(current - desired) <= 1) {
      dataRibbonRestoreAttemptRef.current = null;
      return;
    }

    const previousAttempt = dataRibbonRestoreAttemptRef.current;
    if (previousAttempt && previousAttempt.desired === desired && Math.abs(previousAttempt.current - current) <= 1) return;

    const attempt = { desired, current };
    dataRibbonRestoreAttemptRef.current = attempt;
    panel.resize(desired);
    queueMicrotask(() => {
      if (dataRibbonRestoreAttemptRef.current === attempt) dataRibbonRestoreAttemptRef.current = null;
    });
  }

  function toggleNavigator(): void {
    const panel = navigatorRef.current;
    if (!panel) return;
    if (panel.isCollapsed()) panel.expand();
    else panel.collapse();
  }

  function resetNavigator(): void {
    const panel = navigatorRef.current;
    if (!panel) return;
    panel.resize(navigatorMetrics.default);
    setNavigatorOpen(true);
  }

  const dataSplit = dataLayoutMode && typeof ResizeObserver !== "undefined" ? (
    <Group
      key={`modeling-data-split-v2-${viewport}`}
      id={`modeling-data-split-v2-${viewport}`}
      className="modeling-data-split"
      orientation="vertical"
      onLayoutChanged={onDataLayoutChanged}
    >
      <Panel
        id="modeling-data-ribbon"
        panelRef={setDataRibbonPanel}
        className="modeling-data-ribbon-panel"
        defaultSize={dataRibbonPreferredSize}
        minSize={120}
        groupResizeBehavior="preserve-pixel-size"
      >
        <section
          className={`modeling-task-ribbon${dataLayoutMode === "content-fit" ? " modeling-task-ribbon-scrollable" : ""}`}
          hidden={!ribbonOpen}
          aria-label="Current-stage settings"
          tabIndex={dataLayoutMode === "content-fit" ? 0 : undefined}
        >
          {ribbon}
        </section>
      </Panel>
      <Separator
        id="modeling-data-ribbon-plot-divider"
        className="modeling-data-divider"
        aria-label="Resize Test Data controls and curve plot"
        aria-orientation="horizontal"
        disableDoubleClick
        onDoubleClick={resetDataRibbon}
      />
      <Panel
        id="modeling-data-plot"
        className="modeling-data-plot-panel"
        minSize={MODELING_DATA_PLOT_MIN_SIZE}
      >
        {plot}
      </Panel>
    </Group>
  ) : (
    <>
      <section className="modeling-task-ribbon" hidden={!ribbonOpen} aria-label="Current-stage settings">
        {ribbon}
      </section>
      {plot}
    </>
  );

  const main = (
    <section
      ref={mainSurfaceRef}
      className={`modeling-main-surface${dock ? " has-dock" : ""}${dockLabel === "Candidate parameters" ? " has-fit-evidence-dock" : ""}${dockLabel === "Distribution candidates" ? " has-distribution-dock" : ""}${dockOverlay ? " has-dock-overlay" : ""}${dataLayoutMode ? " has-data-split" : ""}`}
      data-dock-presentation={dockOverlay ? "overlay" : "allocated"}
      aria-label="Persistent Modeling graph and task controls"
    >
      {dataSplit}
      {dock ? <section className="modeling-workspace-dock" aria-label={dockLabel}>{dock}</section> : null}
      <button
        className="modeling-ribbon-control"
        type="button"
        aria-expanded={ribbonOpen}
        aria-label={`${ribbonOpen ? "Hide" : "Show"} current-stage settings`}
        onClick={() => onRibbonOpenChange(!ribbonOpen)}
      >
        <span aria-hidden="true">{ribbonOpen ? "⌃" : "⌄"}</span>
      </button>
    </section>
  );

  // Export is an evidence/preflight task, not a curve-selection task.  Omitting
  // the navigator must reclaim its width instead of leaving an empty resizable
  // panel and divider behind.
  if (!navigator) {
    return (
      <div className={`modeling-split-workspace modeling-split-workspace-no-navigator viewport-${viewport}`} data-viewport-class={viewport}>
        {main}
      </div>
    );
  }

  if (typeof ResizeObserver === "undefined") {
    return (
      <div className={`modeling-split-workspace viewport-${viewport}`} data-viewport-class={viewport}>
        {navigatorOpen ? <aside className="modeling-workspace-rail">{navigator}</aside> : null}
        <div className="modeling-pane-divider" role="separator" aria-label="Resize curve and process navigator" onDoubleClick={resetNavigator} title="Double-click to reset curve and process navigator width">
          <button type="button" aria-label={`${navigatorOpen ? "Collapse" : "Expand"} curve and process navigator`} aria-expanded={navigatorOpen} onClick={() => setNavigatorOpen((current) => !current)}><span aria-hidden="true">{navigatorOpen ? "‹" : "›"}</span></button>
        </div>
        {main}
      </div>
    );
  }

  return (
    <Group
      id={`modeling-workspace-v1-${viewport}`}
      className={`modeling-split-workspace viewport-${viewport}`}
      data-viewport-class={viewport}
      orientation="horizontal"
      defaultLayout={persistence.defaultLayout}
      onLayoutChanged={persistence.onLayoutChanged}
    >
      <Panel
        id="modeling-navigator"
        panelRef={navigatorRef}
        className="modeling-workspace-rail"
        defaultSize={navigatorMetrics.default}
        minSize={navigatorMetrics.min}
        maxSize={navigatorMetrics.max}
        collapsedSize={0}
        collapsible
        groupResizeBehavior="preserve-pixel-size"
        onResize={({ inPixels }) => setNavigatorOpen(inPixels > 1)}
      >
        {navigator}
      </Panel>
      <Separator className="modeling-pane-divider" aria-label="Resize curve and process navigator" onDoubleClick={resetNavigator} title="Double-click to reset curve and process navigator width">
        <button type="button" aria-label={`${navigatorOpen ? "Collapse" : "Expand"} curve and process navigator`} aria-expanded={navigatorOpen} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); toggleNavigator(); }}><span aria-hidden="true">{navigatorOpen ? "‹" : "›"}</span></button>
      </Separator>
      <Panel id="modeling-main" minSize={MODELING_PANE_METRICS.main.min} className="modeling-main-panel">
        {main}
      </Panel>
    </Group>
  );
}
