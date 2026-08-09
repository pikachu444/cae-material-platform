import { type ReactNode, useEffect, useRef, useState } from "react";
import { Group, Panel, Separator, useDefaultLayout, usePanelCallbackRef, usePanelRef, type LayoutChangedMeta } from "react-resizable-panels";

import {
  desktopViewportClass,
  MODELING_PANE_METRICS,
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

const navigatorDefaults: Record<DesktopViewportClass, number> = {
  compact: MODELING_PANE_METRICS.navigator.defaults.compact,
  standard: MODELING_PANE_METRICS.navigator.defaults.standard,
  wide: MODELING_PANE_METRICS.navigator.defaults.wide,
};

export const MODELING_DATA_DEFAULT_PLOT_SIZE = MODELING_PANE_METRICS.dataPlot.preferred;
export const MODELING_DATA_PLOT_MIN_SIZE = MODELING_PANE_METRICS.dataPlot.min;
export const MODELING_DATA_SPLIT_SEPARATOR_SIZE = MODELING_PANE_METRICS.dataPlot.separator;

export function modelingDataRibbonPreferredSize(dataLayoutMode?: "compact" | "content-fit"): number {
  return dataLayoutMode === "content-fit"
    ? MODELING_PANE_METRICS.dataRibbon.contentFit
    : MODELING_PANE_METRICS.dataRibbon.compact;
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
  const [viewport, setViewport] = useState<DesktopViewportClass>(() =>
    desktopViewportClass(typeof window === "undefined" ? 1440 : window.innerWidth),
  );
  const navigatorRef = usePanelRef();
  const [navigatorOpen, setNavigatorOpen] = useState(true);
  const persistence = useDefaultLayout({
    id: `modeling-workspace-v1-${viewport}`,
    panelIds: ["modeling-navigator", "modeling-main"],
    storage: typeof window === "undefined" ? undefined : window.localStorage,
  });
  const [dataRibbonPanel, setDataRibbonPanel] = usePanelCallbackRef();
  const dataRibbonDesiredSizeRef = useRef(modelingDataRibbonPreferredSize(dataLayoutMode));
  const dataRibbonModeRef = useRef(dataLayoutMode);
  const dataRibbonRestoreAttemptRef = useRef<{ desired: number; current: number } | null>(null);

  useEffect(() => {
    const update = () => setViewport(desktopViewportClass(window.innerWidth));
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  const dataRibbonPreferredSize = modelingDataRibbonPreferredSize(dataLayoutMode);

  useEffect(() => {
    const modeChanged = dataRibbonModeRef.current !== dataLayoutMode;
    if (modeChanged) {
      dataRibbonModeRef.current = dataLayoutMode;
      dataRibbonDesiredSizeRef.current = dataRibbonPreferredSize;
      dataRibbonRestoreAttemptRef.current = null;
    }
    if (!dataLayoutMode || !dataRibbonPanel) return;
    dataRibbonPanel.resize(dataRibbonDesiredSizeRef.current);
  }, [dataLayoutMode, dataRibbonPanel, dataRibbonPreferredSize]);

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
        <section className="modeling-task-ribbon" hidden={!ribbonOpen} aria-label="Current-stage settings">
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
    <section className={`modeling-main-surface${dock ? " has-dock" : ""}${dockLabel === "Candidate parameters" ? " has-fit-evidence-dock" : ""}${dataLayoutMode ? " has-data-split" : ""}`} aria-label="Persistent Modeling graph and task controls">
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
        <div className="modeling-pane-divider" role="separator" aria-label="Resize curve and process navigator">
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
        defaultSize={navigatorDefaults[viewport]}
        minSize={MODELING_PANE_METRICS.navigator.min}
        maxSize={MODELING_PANE_METRICS.navigator.max}
        collapsedSize={0}
        collapsible
        groupResizeBehavior="preserve-pixel-size"
        onResize={({ inPixels }) => setNavigatorOpen(inPixels > 1)}
      >
        {navigator}
      </Panel>
      <Separator className="modeling-pane-divider" aria-label="Resize curve and process navigator">
        <button type="button" aria-label={`${navigatorOpen ? "Collapse" : "Expand"} curve and process navigator`} aria-expanded={navigatorOpen} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); toggleNavigator(); }}><span aria-hidden="true">{navigatorOpen ? "‹" : "›"}</span></button>
      </Separator>
      <Panel id="modeling-main" minSize={MODELING_PANE_METRICS.main.min} className="modeling-main-panel">
        {main}
      </Panel>
    </Group>
  );
}
