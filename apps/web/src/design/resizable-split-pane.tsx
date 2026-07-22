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
  compact: { navigator: 244, main: 1122, context: 0 },
  standard: { navigator: 248, main: 912, context: 280 },
  wide: { navigator: 280, main: 1340, context: 300 },
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
    id: `${id}-v3-${viewport}`,
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
        <div className="materials-pane-toggles" aria-label="Workspace panes">
          <button className="ux-button tertiary" type="button" aria-expanded={navigatorOpen} onClick={() => setNavigatorOpen((current) => !current)}>{navigatorOpen ? `Hide ${navigatorLabel}` : `Show ${navigatorLabel}`}</button>
          <button className="ux-button tertiary" type="button" aria-expanded={contextOpen} onClick={() => setContextOpen((current) => !current)}>{contextOpen ? `Hide ${contextLabel}` : `Show ${contextLabel}`}</button>
        </div>
        <div className="materials-workspace resizable-workspace-fallback">
          {navigatorOpen ? <div className="materials-workspace-panel navigator-panel">{navigator}</div> : null}
          {navigatorOpen ? <div className="materials-resize-handle" role="separator" aria-label={`Resize ${navigatorLabel}`} /> : null}
          <div className="materials-workspace-panel main-panel">{main}</div>
          {contextOpen ? <div className="materials-resize-handle" role="separator" aria-label={`Resize ${contextLabel}`} /> : null}
          {contextOpen ? <div className="materials-workspace-panel context-panel">{context}</div> : null}
        </div>
      </div>
    );
  }

  return (
    <div className={`resizable-workspace viewport-${viewport}`} data-viewport-class={viewport}>
      <div className="materials-pane-toggles" aria-label="Workspace panes">
        <button className="ux-button tertiary" type="button" aria-expanded={navigatorOpen} onClick={toggleNavigator}>
          {navigatorOpen ? `Hide ${navigatorLabel}` : `Show ${navigatorLabel}`}
        </button>
        <button className="ux-button tertiary" type="button" aria-expanded={contextOpen} onClick={toggleContext}>
          {contextOpen ? `Hide ${contextLabel}` : `Show ${contextLabel}`}
        </button>
      </div>
      <Group
        key={`${id}-v3-${viewport}`}
        id={`${id}-v3-${viewport}`}
        className="materials-workspace"
        style={{ width: "calc(100% - 16px)", height: "calc(100% - 30px)" }}
        orientation="horizontal"
        defaultLayout={initialLayout}
        onLayoutChanged={persistence.onLayoutChanged}
      >
        <Panel
          id="navigator"
          panelRef={navigatorRef}
          className="materials-workspace-panel navigator-panel"
          defaultSize={defaults[viewport].navigator}
          minSize={240}
          maxSize={320}
          collapsedSize={0}
          collapsible
          groupResizeBehavior="preserve-pixel-size"
          onResize={({ inPixels }) => setNavigatorOpen(inPixels > 1)}
        >
          {navigator}
        </Panel>
        <Separator className="materials-resize-handle" aria-label={`Resize ${navigatorLabel}`} />
        <Panel id="main" className="materials-workspace-panel main-panel" minSize={720}>
          {main}
        </Panel>
        <Separator className="materials-resize-handle" aria-label={`Resize ${contextLabel}`} />
        <Panel
          id="context"
          panelRef={contextRef}
          className="materials-workspace-panel context-panel"
          defaultSize={defaults[viewport].context}
          minSize={280}
          maxSize={420}
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
