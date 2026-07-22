import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Group, Panel, Separator, useDefaultLayout, usePanelRef } from "react-resizable-panels";

export type DesktopViewportClass = "compact" | "standard" | "wide";

interface ResizableSplitPaneProps {
  id: string;
  navigator: ReactNode;
  main: ReactNode;
  context: ReactNode;
  navigatorLabel?: string;
  contextLabel?: string;
}

export function desktopViewportClass(width: number): DesktopViewportClass {
  if (width <= 1390) return "compact";
  if (width >= 1600) return "wide";
  return "standard";
}

const defaults: Record<DesktopViewportClass, { navigator: number; main: number; context: number }> = {
  compact: { navigator: 232, main: 1118, context: 0 },
  standard: { navigator: 240, main: 920, context: 264 },
  wide: { navigator: 272, main: 1344, context: 288 },
};

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
    id: `${id}-v4-${viewport}`,
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

  if (typeof ResizeObserver === "undefined") {
    return (
      <div className={`resizable-workspace viewport-${viewport}`} data-viewport-class={viewport}>
        <div className="materials-workspace resizable-workspace-fallback">
          {navigatorOpen ? <div className="materials-workspace-panel navigator-panel">{navigator}</div> : null}
          <div className="materials-resize-handle" role="separator" aria-label={`Resize ${navigatorLabel}`}>
            <button className="pane-divider-control" type="button" aria-label={`${navigatorOpen ? "Collapse" : "Expand"} ${navigatorLabel} pane`} aria-expanded={navigatorOpen} onClick={() => setNavigatorOpen((current) => !current)}><span aria-hidden="true">{navigatorOpen ? "‹" : "›"}</span></button>
          </div>
          <div className="materials-workspace-panel main-panel">{main}</div>
          <div className="materials-resize-handle" role="separator" aria-label={`Resize ${contextLabel}`}>
            <button className="pane-divider-control" type="button" aria-label={`${contextOpen ? "Collapse" : "Expand"} ${contextLabel} pane`} aria-expanded={contextOpen} onClick={() => setContextOpen((current) => !current)}><span aria-hidden="true">{contextOpen ? "›" : "‹"}</span></button>
          </div>
          {contextOpen ? <div className="materials-workspace-panel context-panel">{context}</div> : null}
        </div>
      </div>
    );
  }

  return (
    <div className={`resizable-workspace viewport-${viewport}`} data-viewport-class={viewport}>
      <Group
        key={`${id}-v4-${viewport}`}
        id={`${id}-v4-${viewport}`}
        className="materials-workspace"
        style={{ width: "calc(100% - 16px)", height: "100%" }}
        orientation="horizontal"
        defaultLayout={initialLayout}
        onLayoutChanged={persistence.onLayoutChanged}
      >
        <Panel
          id="navigator"
          panelRef={navigatorRef}
          className="materials-workspace-panel navigator-panel"
          defaultSize={defaults[viewport].navigator}
          minSize={220}
          maxSize={320}
          collapsedSize={0}
          collapsible
          groupResizeBehavior="preserve-pixel-size"
          onResize={({ inPixels }) => setNavigatorOpen(inPixels > 1)}
        >
          {navigator}
        </Panel>
        <Separator className="materials-resize-handle" aria-label={`Resize ${navigatorLabel}`}>
          <button className="pane-divider-control" type="button" aria-label={`${navigatorOpen ? "Collapse" : "Expand"} ${navigatorLabel} pane`} aria-expanded={navigatorOpen} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); toggleNavigator(); }}><span aria-hidden="true">{navigatorOpen ? "‹" : "›"}</span></button>
        </Separator>
        <Panel id="main" className="materials-workspace-panel main-panel" minSize={720}>
          {main}
        </Panel>
        <Separator className="materials-resize-handle" aria-label={`Resize ${contextLabel}`}>
          <button className="pane-divider-control" type="button" aria-label={`${contextOpen ? "Collapse" : "Expand"} ${contextLabel} pane`} aria-expanded={contextOpen} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); toggleContext(); }}><span aria-hidden="true">{contextOpen ? "›" : "‹"}</span></button>
        </Separator>
        <Panel
          id="context"
          panelRef={contextRef}
          className="materials-workspace-panel context-panel"
          defaultSize={defaults[viewport].context}
          minSize={260}
          maxSize={400}
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
