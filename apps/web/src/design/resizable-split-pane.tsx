import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Group, Panel, Separator, useDefaultLayout, usePanelRef } from "react-resizable-panels";
import { EngineeringIcon } from "./icon";
import {
  desktopViewportClass,
  MATERIALS_PANE_METRICS,
  materialsPaneDefaults,
  type DesktopViewportClass,
} from "./metrics";

export { desktopViewportClass, materialsPaneDefaults } from "./metrics";
export type { DesktopViewportClass } from "./metrics";

interface ResizableSplitPaneProps {
  id: string;
  navigator: ReactNode;
  main: ReactNode;
  context: ReactNode;
  navigatorLabel?: string;
  contextLabel?: string;
}

export function ResizableSplitPane({
  id,
  navigator,
  main,
  context,
  navigatorLabel = "navigator",
  contextLabel = "details",
}: ResizableSplitPaneProps) {
  const [viewport, setViewport] = useState<DesktopViewportClass>(() =>
    desktopViewportClass(typeof window === "undefined" ? 1440 : window.innerWidth),
  );
  const navigatorRef = usePanelRef();
  const contextRef = usePanelRef();
  const [navigatorOpen, setNavigatorOpen] = useState(true);
  const [contextOpen, setContextOpen] = useState(viewport !== "compact");
  const persistence = useDefaultLayout({
    id: `${id}-v5-${viewport}`,
    panelIds: ["navigator", "main", "context"],
    storage: typeof window === "undefined" ? undefined : window.localStorage,
  });
  const initialLayout = useMemo(() => persistence.defaultLayout, [persistence.defaultLayout]);

  useEffect(() => {
    const update = () => setViewport(desktopViewportClass(window.innerWidth));
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  useEffect(() => {
    if (typeof ResizeObserver === "undefined") return;
    if (viewport === "compact" && contextRef.current && !contextRef.current.isCollapsed()) {
      contextRef.current.collapse();
      setContextOpen(false);
    }
  }, [contextRef, viewport]);

  function toggleNavigator(): void {
    const panel = navigatorRef.current;
    if (!panel) return;
    if (panel.isCollapsed()) {
      panel.expand();
      setNavigatorOpen(true);
    } else {
      panel.collapse();
      setNavigatorOpen(false);
    }
  }

  function toggleContext(): void {
    const panel = contextRef.current;
    if (!panel) return;
    if (panel.isCollapsed()) {
      panel.expand();
      setContextOpen(true);
    } else {
      panel.collapse();
      setContextOpen(false);
    }
  }

  function resetNavigator(): void {
    navigatorRef.current?.resize(materialsPaneDefaults[viewport].navigator);
    setNavigatorOpen(true);
  }

  function resetContext(): void {
    const panel = contextRef.current;
    if (!panel) return;
    if (materialsPaneDefaults[viewport].context === 0) {
      panel.collapse();
      setContextOpen(false);
      return;
    }
    panel.resize(materialsPaneDefaults[viewport].context);
    setContextOpen(true);
  }

  if (typeof ResizeObserver === "undefined") {
    return (
      <div className={`resizable-workspace viewport-${viewport}`} data-viewport-class={viewport}>
        <div className="materials-workspace resizable-workspace-fallback">
          {navigatorOpen ? <div className="materials-workspace-panel navigator-panel">{navigator}</div> : null}
          <div className="materials-resize-handle" role="separator" aria-label={`Resize ${navigatorLabel}`} onDoubleClick={resetNavigator} title={`Double-click to reset ${navigatorLabel} width`}>
            <button className="pane-divider-control" type="button" aria-label={`${navigatorOpen ? "Collapse" : "Expand"} ${navigatorLabel} pane`} aria-expanded={navigatorOpen} onClick={() => setNavigatorOpen((current) => !current)}><EngineeringIcon name={navigatorOpen ? "chevron-left" : "chevron-right"}/></button>
          </div>
          <div className="materials-workspace-panel main-panel">{main}</div>
          <div className="materials-resize-handle" role="separator" aria-label={`Resize ${contextLabel}`} onDoubleClick={resetContext} title={`Double-click to reset ${contextLabel} width`}>
            <button className="pane-divider-control" type="button" aria-label={`${contextOpen ? "Collapse" : "Expand"} ${contextLabel} pane`} aria-expanded={contextOpen} onClick={() => setContextOpen((current) => !current)}><EngineeringIcon name={contextOpen ? "chevron-right" : "chevron-left"}/></button>
          </div>
          {contextOpen ? <div className="materials-workspace-panel context-panel">{context}</div> : null}
        </div>
      </div>
    );
  }

  return (
    <div className={`resizable-workspace viewport-${viewport}`} data-viewport-class={viewport}>
      <Group
        key={`${id}-v5-${viewport}`}
        id={`${id}-v5-${viewport}`}
        className="materials-workspace"
        style={{ height: "100%" }}
        orientation="horizontal"
        defaultLayout={initialLayout}
        onLayoutChanged={persistence.onLayoutChanged}
      >
        <Panel
          id="navigator"
          panelRef={navigatorRef}
          className="materials-workspace-panel navigator-panel"
          defaultSize={materialsPaneDefaults[viewport].navigator}
          minSize={MATERIALS_PANE_METRICS.navigator.min}
          maxSize={MATERIALS_PANE_METRICS.navigator.max}
          collapsedSize={0}
          collapsible
          groupResizeBehavior="preserve-pixel-size"
          onResize={({ inPixels }) => setNavigatorOpen(inPixels > 1)}
        >
          {navigator}
        </Panel>
        <Separator className="materials-resize-handle" aria-label={`Resize ${navigatorLabel}`} onDoubleClick={resetNavigator} title={`Double-click to reset ${navigatorLabel} width`}>
          <button className="pane-divider-control" type="button" aria-label={`${navigatorOpen ? "Collapse" : "Expand"} ${navigatorLabel} pane`} aria-expanded={navigatorOpen} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); toggleNavigator(); }}><EngineeringIcon name={navigatorOpen ? "chevron-left" : "chevron-right"}/></button>
        </Separator>
        <Panel id="main" className="materials-workspace-panel main-panel" minSize={MATERIALS_PANE_METRICS.main.min}>
          {main}
        </Panel>
        <Separator className="materials-resize-handle" aria-label={`Resize ${contextLabel}`} onDoubleClick={resetContext} title={`Double-click to reset ${contextLabel} width`}>
          <button className="pane-divider-control" type="button" aria-label={`${contextOpen ? "Collapse" : "Expand"} ${contextLabel} pane`} aria-expanded={contextOpen} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); toggleContext(); }}><EngineeringIcon name={contextOpen ? "chevron-right" : "chevron-left"}/></button>
        </Separator>
        <Panel
          id="context"
          panelRef={contextRef}
          className="materials-workspace-panel context-panel"
          defaultSize={materialsPaneDefaults[viewport].context}
          minSize={MATERIALS_PANE_METRICS.context.min}
          maxSize={MATERIALS_PANE_METRICS.context.max}
          collapsedSize={0}
          collapsible
          groupResizeBehavior="preserve-pixel-size"
          onResize={({ inPixels }) => setContextOpen(inPixels > 1)}
        >
          {context}
        </Panel>
      </Group>
    </div>
  );
}
