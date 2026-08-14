import { type ReactNode, type RefObject, useEffect, useMemo, useRef, useState } from "react";
import { Group, Panel, Separator, useDefaultLayout, usePanelRef } from "react-resizable-panels";
import { EngineeringIcon } from "./icon";
import { useDisplayDensity } from "./display-density";
import {
  DISPLAY_DENSITY_PANE_METRICS,
  desktopViewportClass,
  MATERIALS_PANE_METRICS,
  materialsPaneDefaults,
  materialsPaneDefaultsForDensity,
  type DesktopViewportClass,
} from "./metrics";

export { desktopViewportClass, materialsPaneDefaults } from "./metrics";
export type { DesktopViewportClass } from "./metrics";

interface ResizableSplitPaneProps {
  id: string;
  navigator: ReactNode;
  main: ReactNode;
  context?: ReactNode;
  navigatorLabel?: string;
  contextLabel?: string;
}

interface ContextPaneOverlayProps {
  open: boolean;
  label: string;
  triggerRef: RefObject<HTMLButtonElement | null>;
  onClose: () => void;
  children: ReactNode;
}

export function shouldUseContextOverlay(
  explicitlyExpanded: boolean,
  allocationInPixels: number,
): boolean {
  return explicitlyExpanded && allocationInPixels < 1;
}

export function ContextPaneOverlay({
  open,
  label,
  triggerRef,
  onClose,
  children,
}: ContextPaneOverlayProps) {
  const overlayRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) closeRef.current?.focus();
  }, [open]);

  if (!open) return null;

  function close(): void {
    onClose();
    window.requestAnimationFrame(() => triggerRef.current?.focus());
  }

  function keepFocusInside(event: React.KeyboardEvent<HTMLElement>): void {
    if (event.key !== "Tab") return;
    const focusable = [
      ...(overlayRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ) ?? []),
    ];
    if (!focusable.length) return;
    const activeIndex = focusable.indexOf(document.activeElement as HTMLElement);
    const targetIndex = event.shiftKey
      ? activeIndex <= 0 ? focusable.length - 1 : activeIndex - 1
      : activeIndex < 0 || activeIndex === focusable.length - 1 ? 0 : activeIndex + 1;
    event.preventDefault();
    focusable[targetIndex]?.focus();
  }

  return (
    <section
      ref={overlayRef}
      className="materials-context-overlay context-panel"
      role="dialog"
      aria-modal="true"
      aria-label={`${label} pane`}
      data-context-pane-mode="overlay"
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          close();
          return;
        }
        keepFocusInside(event);
      }}
    >
      <header>
        <h2>{label}</h2>
        <button
          ref={closeRef}
          className="ux-button tertiary"
          type="button"
          aria-label={`Close ${label} pane`}
          onClick={close}
        >
          Close
        </button>
      </header>
      <div className="materials-context-overlay-content">{children}</div>
    </section>
  );
}

export function ResizableSplitPane({
  id,
  navigator,
  main,
  context,
  navigatorLabel = "navigator",
  contextLabel = "details",
}: ResizableSplitPaneProps) {
  const { density } = useDisplayDensity();
  const [viewport, setViewport] = useState<DesktopViewportClass>(() =>
    desktopViewportClass(typeof window === "undefined" ? 1440 : window.innerWidth),
  );
  const navigatorRef = usePanelRef();
  const contextRef = usePanelRef();
  const previousNavigatorDefaultRef = useRef<number | null>(null);
  const previousContextDefaultRef = useRef<number | null>(null);
  const contextToggleRef = useRef<HTMLButtonElement>(null);
  const explicitlyExpandedContextRef = useRef(false);
  const [navigatorOpen, setNavigatorOpen] = useState(true);
  const [contextOpen, setContextOpen] = useState(viewport !== "compact");
  const [contextOverlayOpen, setContextOverlayOpen] = useState(false);
  const persistence = useDefaultLayout({
    id: `${id}-v5-${viewport}`,
    panelIds: ["navigator", "main", "context"],
    storage: typeof window === "undefined" ? undefined : window.localStorage,
  });
  const paneMetrics = DISPLAY_DENSITY_PANE_METRICS[density];
  const paneDefaults = materialsPaneDefaultsForDensity(viewport, density);
  const initialLayout = useMemo(() => persistence.defaultLayout, [persistence.defaultLayout]);

  useEffect(() => {
    const update = () => setViewport(desktopViewportClass(window.innerWidth));
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  useEffect(() => {
    const previous = previousNavigatorDefaultRef.current;
    previousNavigatorDefaultRef.current = paneDefaults.navigator;
    const panel = navigatorRef.current;
    if (previous === null || !panel || panel.isCollapsed()) return;
    if (Math.abs(panel.getSize().inPixels - previous) <= 1) {
      panel.resize(paneDefaults.navigator);
    }
  }, [navigatorRef, paneDefaults.navigator]);

  useEffect(() => {
    const previous = previousContextDefaultRef.current;
    previousContextDefaultRef.current = paneDefaults.context;
    const panel = contextRef.current;
    if (previous === null || !panel || panel.isCollapsed() || previous === 0) return;
    if (Math.abs(panel.getSize().inPixels - previous) <= 1) {
      panel.resize(paneDefaults.context);
    }
  }, [contextRef, paneDefaults.context]);

  useEffect(() => {
    if (typeof ResizeObserver === "undefined") return;
    if (viewport === "compact" && contextRef.current && !contextRef.current.isCollapsed()) {
      explicitlyExpandedContextRef.current = false;
      contextRef.current.collapse();
      setContextOpen(false);
      setContextOverlayOpen(false);
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
    if (contextOverlayOpen) {
      closeContextOverlay();
      return;
    }
    if (panel.isCollapsed()) {
      explicitlyExpandedContextRef.current = true;
      panel.expand();
      window.requestAnimationFrame(() => {
        const allocation = contextRef.current?.getSize().inPixels ?? 0;
        const useOverlay = shouldUseContextOverlay(true, allocation);
        setContextOverlayOpen(useOverlay);
        setContextOpen(!useOverlay && allocation >= 1);
      });
    } else {
      explicitlyExpandedContextRef.current = false;
      panel.collapse();
      setContextOpen(false);
      setContextOverlayOpen(false);
    }
  }

  function closeContextOverlay(): void {
    explicitlyExpandedContextRef.current = false;
    setContextOverlayOpen(false);
    setContextOpen(false);
    contextRef.current?.collapse();
  }

  function resetNavigator(): void {
    navigatorRef.current?.resize(paneDefaults.navigator);
    setNavigatorOpen(true);
  }

  function resetContext(): void {
    const panel = contextRef.current;
    if (!panel) return;
    if (paneDefaults.context === 0) {
      explicitlyExpandedContextRef.current = false;
      panel.collapse();
      setContextOpen(false);
      setContextOverlayOpen(false);
      return;
    }
    explicitlyExpandedContextRef.current = true;
    panel.resize(paneDefaults.context);
    setContextOpen(true);
    setContextOverlayOpen(false);
  }

  if (context === undefined) {
    if (typeof ResizeObserver === "undefined") {
      return (
        <div className={`resizable-workspace viewport-${viewport}`} data-viewport-class={viewport}>
          <div className="materials-workspace materials-workspace-two-pane resizable-workspace-fallback">
            {navigatorOpen ? <div className="materials-workspace-panel navigator-panel">{navigator}</div> : null}
            <div className="materials-resize-handle" role="separator" aria-label={`Resize ${navigatorLabel}`} onDoubleClick={resetNavigator} title={`Double-click to reset ${navigatorLabel} width`}>
              <button className="pane-divider-control" type="button" aria-label={`${navigatorOpen ? "Collapse" : "Expand"} ${navigatorLabel} pane`} aria-expanded={navigatorOpen} onClick={() => setNavigatorOpen((current) => !current)}><EngineeringIcon name={navigatorOpen ? "chevron-left" : "chevron-right"}/></button>
            </div>
            <div className="materials-workspace-panel main-panel">{main}</div>
          </div>
        </div>
      );
    }
    return (
      <div className={`resizable-workspace viewport-${viewport}`} data-viewport-class={viewport}>
        <Group
          key={`${id}-v1-${viewport}`}
          id={`${id}-v1-${viewport}`}
          className="materials-workspace materials-workspace-two-pane"
          style={{ height: "100%" }}
          orientation="horizontal"
        >
          <Panel
            id="navigator"
            panelRef={navigatorRef}
            className="materials-workspace-panel navigator-panel"
            defaultSize={paneDefaults.navigator}
            minSize={paneMetrics.navigator.min}
            maxSize={paneMetrics.navigator.max}
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
        </Group>
      </div>
    );
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
            <button ref={contextToggleRef} className="pane-divider-control" type="button" aria-label={`${contextOpen ? "Collapse" : "Expand"} ${contextLabel} pane`} aria-expanded={contextOpen} onClick={() => setContextOpen((current) => !current)}><EngineeringIcon name={contextOpen ? "chevron-right" : "chevron-left"}/></button>
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
          defaultSize={paneDefaults.navigator}
          minSize={paneMetrics.navigator.min}
          maxSize={paneMetrics.navigator.max}
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
          <button ref={contextToggleRef} className="pane-divider-control" type="button" aria-label={`${contextOpen || contextOverlayOpen ? "Collapse" : "Expand"} ${contextLabel} pane`} aria-expanded={contextOpen || contextOverlayOpen} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); toggleContext(); }}><EngineeringIcon name={contextOpen || contextOverlayOpen ? "chevron-right" : "chevron-left"}/></button>
        </Separator>
        <Panel
          id="context"
          panelRef={contextRef}
          className="materials-workspace-panel context-panel"
          defaultSize={paneDefaults.context}
          minSize={paneMetrics.context.min}
          maxSize={paneMetrics.context.max}
          collapsedSize={0}
          collapsible
          groupResizeBehavior="preserve-pixel-size"
          onResize={({ inPixels }) => {
            const allocated = inPixels >= 1;
            setContextOpen(allocated);
            if (allocated) setContextOverlayOpen(false);
            else if (shouldUseContextOverlay(explicitlyExpandedContextRef.current, inPixels)) setContextOverlayOpen(true);
          }}
        >
          {contextOverlayOpen ? null : context}
        </Panel>
      </Group>
      <ContextPaneOverlay
        open={contextOverlayOpen}
        label={contextLabel}
        triggerRef={contextToggleRef}
        onClose={closeContextOverlay}
      >
        {context}
      </ContextPaneOverlay>
    </div>
  );
}
