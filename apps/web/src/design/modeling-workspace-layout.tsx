import { type ReactNode, useEffect, useState } from "react";
import { Group, Panel, Separator, useDefaultLayout, usePanelRef } from "react-resizable-panels";

import { desktopViewportClass, type DesktopViewportClass } from "./resizable-split-pane";

interface ModelingWorkspaceLayoutProps {
  navigator: ReactNode;
  ribbon: ReactNode;
  plot: ReactNode;
  dock?: ReactNode;
  ribbonOpen: boolean;
  onRibbonOpenChange: (open: boolean) => void;
}

const navigatorDefaults: Record<DesktopViewportClass, number> = {
  compact: 184,
  standard: 192,
  wide: 208,
};

export function ModelingWorkspaceLayout({
  navigator,
  ribbon,
  plot,
  dock,
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

  useEffect(() => {
    const update = () => setViewport(desktopViewportClass(window.innerWidth));
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  function toggleNavigator(): void {
    const panel = navigatorRef.current;
    if (!panel) return;
    if (panel.isCollapsed()) panel.expand();
    else panel.collapse();
  }

  const main = (
    <section className={`modeling-main-surface${dock ? " has-dock" : ""}`} aria-label="Persistent Modeling graph and task controls">
      <section className="modeling-task-ribbon" hidden={!ribbonOpen} aria-label="Current-stage settings">
        {ribbon}
      </section>
      {plot}
      {dock ? <section className="modeling-workspace-dock" aria-label="Delivery">{dock}</section> : null}
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
        minSize={180}
        maxSize={240}
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
      <Panel id="modeling-main" minSize={720} className="modeling-main-panel">
        {main}
      </Panel>
    </Group>
  );
}
