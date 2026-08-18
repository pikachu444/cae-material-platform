import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";
import type { PanelImperativeHandle } from "react-resizable-panels";

type PanelHandleEntry = {
  kind: "ref" | "callback";
  active: PanelImperativeHandle | null;
  pending: PanelImperativeHandle | null | undefined;
  commit?: (next: PanelImperativeHandle | null) => void;
};

type GroupLayoutEntry = {
  id: string | number | undefined;
  callback: ((layout: Record<string, number>, meta: { isUserInteraction: boolean }) => void) | undefined;
};

const panelHandleState = vi.hoisted(() => ({ entries: [] as PanelHandleEntry[] }));
const groupLayoutState = vi.hoisted(() => ({ entries: [] as GroupLayoutEntry[] }));

vi.mock("react-resizable-panels", async () => {
  const actual = await vi.importActual<typeof import("react-resizable-panels")>("react-resizable-panels");
  const react = await vi.importActual<typeof import("react")>("react");

  function TrackingGroup(props: any) {
    const entryRef = react.useRef<GroupLayoutEntry | null>(null);
    if (entryRef.current === null) {
      entryRef.current = { id: props.id, callback: props.onLayoutChanged };
      groupLayoutState.entries.push(entryRef.current);
    } else {
      entryRef.current.id = props.id;
      entryRef.current.callback = props.onLayoutChanged;
    }
    return react.createElement(actual.Group, props);
  }

  function useDeferredPanelRef() {
    const entryRef = react.useRef<PanelHandleEntry | null>(null);
    const holderRef = react.useRef<{ current: PanelImperativeHandle | null } | null>(null);
    if (entryRef.current === null) {
      entryRef.current = { kind: "ref", active: null, pending: undefined };
      panelHandleState.entries.push(entryRef.current);
    }
    const entry = entryRef.current;
    if (holderRef.current === null) {
      const holder = {} as { current: PanelImperativeHandle | null };
      Object.defineProperty(holder, "current", {
        configurable: true,
        enumerable: true,
        get: () => entry.active,
        set: (next: PanelImperativeHandle | null) => {
          entry.pending = next;
        },
      });
      holderRef.current = holder;
    }
    return holderRef.current;
  }

  function useDeferredPanelCallbackRef() {
    const [active, setActive] = useState<PanelImperativeHandle | null>(null);
    const entryRef = react.useRef<PanelHandleEntry | null>(null);
    if (entryRef.current === null) {
      entryRef.current = { kind: "callback", active: null, pending: undefined, commit: setActive };
      panelHandleState.entries.push(entryRef.current);
    } else {
      entryRef.current.commit = setActive;
    }
    const entry = entryRef.current;
    const callback = react.useCallback((next: PanelImperativeHandle | null) => {
      entry.pending = next;
    }, [entry]);
    return [active, callback] as const;
  }

  return {
    ...actual,
    Group: TrackingGroup,
    usePanelRef: useDeferredPanelRef,
    usePanelCallbackRef: useDeferredPanelCallbackRef,
  };
});

function flushLatePanelHandles(): void {
  for (const entry of panelHandleState.entries) {
    if (entry.pending === undefined) continue;
    entry.active = entry.pending;
    entry.commit?.(entry.pending);
    entry.pending = undefined;
  }
}

function latestPendingPanelHandle(): PanelImperativeHandle | null {
  return [...panelHandleState.entries].reverse().find((entry) => entry.pending !== undefined && entry.pending !== null)?.pending ?? null;
}

function latestDataLayoutCallback(): NonNullable<GroupLayoutEntry["callback"]> {
  const entry = [...groupLayoutState.entries].reverse().find((candidate) => String(candidate.id).includes("modeling-data-split"));
  if (!entry?.callback) throw new Error("Data Group layout callback did not arrive");
  return entry.callback;
}

function activeNavigatorHandle(): PanelImperativeHandle | null {
  return panelHandleState.entries.find((entry) => entry.kind === "ref")?.active ?? null;
}

import {
  MODELING_DATA_DEFAULT_PLOT_SIZE,
  MODELING_DATA_PLOT_MIN_SIZE,
  MODELING_DATA_SPLIT_SEPARATOR_SIZE,
  ModelingWorkspaceLayout,
  modelingDataRibbonPreferredSize,
} from "./modeling-workspace-layout";

afterEach(() => {
  cleanup();
  panelHandleState.entries.length = 0;
  groupLayoutState.entries.length = 0;
  vi.unstubAllGlobals();
});

describe("ModelingWorkspaceLayout", () => {
  it("derives the adjustable Data ribbon preferred and reset sizes from shared density tokens", () => {
    expect(modelingDataRibbonPreferredSize("content-fit", "compact")).toBe(384);
    expect(modelingDataRibbonPreferredSize("compact", "compact")).toBe(199);
    expect(modelingDataRibbonPreferredSize("content-fit", "standard")).toBe(384);
    expect(modelingDataRibbonPreferredSize("compact", "standard")).toBe(230);
    expect(modelingDataRibbonPreferredSize(undefined, "standard")).toBe(230);
    expect(modelingDataRibbonPreferredSize("content-fit", "large")).toBe(384);
    expect(modelingDataRibbonPreferredSize("compact", "large")).toBe(261);
    expect(MODELING_DATA_DEFAULT_PLOT_SIZE).toBeGreaterThanOrEqual(296);
    expect(MODELING_DATA_PLOT_MIN_SIZE).toBe(240);
    expect(MODELING_DATA_SPLIT_SEPARATOR_SIZE).toBe(8);
  });

  it("keeps compact navigator and ribbon controls keyboard accessible", () => {
    const onRibbonOpenChange = vi.fn();
    render(
      <ModelingWorkspaceLayout
        navigator={<span>Curve navigator</span>}
        ribbon={<span>Fit settings</span>}
        plot={<span>Persistent plot</span>}
        dock={<span>Export delivery</span>}
        ribbonOpen
        onRibbonOpenChange={onRibbonOpenChange}
      />,
    );

    act(() => flushLatePanelHandles());

    fireEvent.click(screen.getByRole("button", { name: "Collapse curve and process navigator" }));
    expect(screen.queryByText("Curve navigator")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Hide current-stage settings" }));
    expect(onRibbonOpenChange).toHaveBeenCalledWith(false);
    expect(screen.getByText("Persistent plot")).toBeTruthy();
    expect(screen.getByText("Export delivery")).toBeTruthy();
  });

  it("resets the Modeling navigator independently from display density and ribbon state", () => {
    class ResizeObserverMock {
      observe(): void {}
      disconnect(): void {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
    render(
      <ModelingWorkspaceLayout
        navigator={<span>Curve navigator</span>}
        ribbon={<span>Fit settings</span>}
        plot={<span>Persistent plot</span>}
        ribbonOpen
        onRibbonOpenChange={vi.fn()}
      />,
    );
    act(() => flushLatePanelHandles());
    const navigator = activeNavigatorHandle();
    expect(navigator).not.toBeNull();
    if (!navigator) throw new Error("Navigator panel handle did not arrive");
    const resize = vi.fn();
    Object.defineProperty(navigator, "resize", {
      configurable: true,
      value: resize,
    });

    const divider = screen.getByRole("separator", {
      name: "Resize curve and process navigator",
    });
    expect(divider.getAttribute("title")).toContain("reset curve and process navigator width");
    fireEvent.doubleClick(divider);

    expect(resize).toHaveBeenCalledWith(288);
    expect(screen.getByText("Fit settings")).toBeTruthy();
  });

  it("reclaims the navigator region when a task does not supply one", () => {
    const { container } = render(
      <ModelingWorkspaceLayout
        ribbon={<span>Export evidence</span>}
        plot={<span>Persistent export plot</span>}
        ribbonOpen={false}
        onRibbonOpenChange={vi.fn()}
      />,
    );

    expect(screen.getByText("Persistent export plot")).toBeTruthy();
    expect(screen.queryByLabelText("Resize curve and process navigator")).toBeNull();
    expect(document.querySelector(".modeling-workspace-rail")).toBeNull();
    expect(container.querySelector(".modeling-split-workspace-no-navigator .modeling-main-surface")).toBeTruthy();
  });

  it("uses a bounded dock overlay only after the actual Candidate parameters plot frame collapses", () => {
    class ResizeObserverMock {
      observe(): void {}
      disconnect(): void {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
    const props = {
      navigator: <span>Curve navigator</span>,
      ribbon: <span>Fit settings</span>,
      plot: <div className="engineering-plot-frame">Persistent plot</div>,
      ribbonOpen: true,
      onRibbonOpenChange: vi.fn(),
    };
    const { container, rerender } = render(
      <ModelingWorkspaceLayout
        {...props}
        dock={<span>Candidate evidence</span>}
        dockLabel="Candidate parameters"
      />,
    );
    const surface = container.querySelector(".modeling-main-surface");

    expect(surface?.getAttribute("data-dock-presentation")).toBe("overlay");
    expect(surface?.classList.contains("has-dock-overlay")).toBe(true);

    rerender(<ModelingWorkspaceLayout {...props} />);
    expect(surface?.getAttribute("data-dock-presentation")).toBe("allocated");
    expect(surface?.classList.contains("has-dock-overlay")).toBe(false);
  });

  it("keeps Candidate parameters allocated when the actual graph frame has space", () => {
    class ResizeObserverMock {
      observe(): void {}
      disconnect(): void {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
    const original = HTMLElement.prototype.getBoundingClientRect;
    HTMLElement.prototype.getBoundingClientRect = function getBoundingClientRect() {
      if (this.classList.contains("engineering-plot-frame")) {
        return { x: 0, y: 0, top: 0, right: 700, bottom: 120, left: 0, width: 700, height: 120, toJSON: () => ({}) };
      }
      return original.call(this);
    };
    try {
      const { container } = render(
        <ModelingWorkspaceLayout
          navigator={<span>Curve navigator</span>}
          ribbon={<span>Fit settings</span>}
          plot={<div className="engineering-plot-frame">Persistent plot</div>}
          dock={<span>Candidate evidence</span>}
          dockLabel="Candidate parameters"
          ribbonOpen
          onRibbonOpenChange={vi.fn()}
        />,
      );
      expect(container.querySelector(".modeling-main-surface")?.getAttribute("data-dock-presentation")).toBe("allocated");
    } finally {
      HTMLElement.prototype.getBoundingClientRect = original;
    }
  });

  it("exposes an accessible vertical Data ribbon/plot divider in content-fit mode", () => {
    class ResizeObserverMock {
      observe(): void {}
      disconnect(): void {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);

    render(
      <ModelingWorkspaceLayout
        navigator={<span>Curve navigator</span>}
        ribbon={<span>Mapping decision</span>}
        plot={<span>Persistent plot</span>}
        dataLayoutMode="content-fit"
        ribbonOpen
        onRibbonOpenChange={vi.fn()}
      />,
    );

    const divider = screen.getByRole("separator", { name: "Resize Test Data controls and curve plot" });
    expect(divider.getAttribute("aria-orientation")).toBe("horizontal");
    expect(divider.getAttribute("tabindex")).toBe("0");
    const ribbon = screen.getByRole("region", { name: "Current-stage settings" });
    expect(ribbon.getAttribute("tabindex")).toBe("0");
    expect(ribbon.classList.contains("modeling-task-ribbon-scrollable")).toBe(true);
    expect(screen.getByText("Mapping decision")).toBeTruthy();
    expect(screen.getByText("Persistent plot")).toBeTruthy();
  });

  it("preserves stateful Data ribbon content when the layout mode changes", () => {
    class ResizeObserverMock {
      observe(): void {}
      disconnect(): void {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);

    function StatefulRibbon() {
      const [value, setValue] = useState("");
      return <label>Mapping decision<input aria-label="Mapping decision" value={value} onChange={(event) => setValue(event.target.value)} /></label>;
    }

    const props = {
      navigator: <span>Curve navigator</span>,
      ribbon: <StatefulRibbon />,
      plot: <span>Persistent plot</span>,
      ribbonOpen: true,
      onRibbonOpenChange: vi.fn(),
    };
    const { rerender } = render(<ModelingWorkspaceLayout {...props} dataLayoutMode="compact" />);
    fireEvent.change(screen.getByRole("textbox", { name: "Mapping decision" }), { target: { value: "Keep exact source units" } });

    rerender(<ModelingWorkspaceLayout {...props} dataLayoutMode="content-fit" />);

    expect((screen.getByRole("textbox", { name: "Mapping decision" }) as HTMLInputElement).value).toBe("Keep exact source units");
    expect(screen.getByRole("separator", { name: "Resize Test Data controls and curve plot" })).toBeTruthy();
  });

  it("waits for a late Data panel handle before applying mode sizes and preserves user resizing", () => {
    class ResizeObserverMock {
      observe(): void {}
      disconnect(): void {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);

    const renderLayout = (dataLayoutMode: "compact" | "content-fit", ribbonOpen = true) => (
      <ModelingWorkspaceLayout
        navigator={<span>Curve navigator</span>}
        ribbon={<span>Mapping decision</span>}
        plot={<span>Persistent plot</span>}
        dataLayoutMode={dataLayoutMode}
        ribbonOpen={ribbonOpen}
        onRibbonOpenChange={vi.fn()}
      />
    );

    const { rerender } = render(renderLayout("compact"));
    const dataRibbonPanel = latestPendingPanelHandle();
    expect(dataRibbonPanel).not.toBeNull();
    if (!dataRibbonPanel) throw new Error("Data panel handle did not arrive");

    act(() => flushLatePanelHandles());
    expect(panelHandleState.entries.some((entry) => entry.kind === "callback" && entry.active === dataRibbonPanel)).toBe(true);

    const resize = vi.fn();
    Object.defineProperty(dataRibbonPanel, "resize", {
      configurable: true,
      get: () => resize,
      set: () => {},
    });

    dataRibbonPanel.resize(260);
    rerender(renderLayout("compact", false));
    expect(resize).toHaveBeenCalledTimes(1);

    rerender(renderLayout("content-fit"));
    expect(resize).toHaveBeenNthCalledWith(2, 384);

    rerender(renderLayout("compact"));
    expect(resize).toHaveBeenNthCalledWith(3, 230);
  });

  it("restores the desired ribbon size after a non-user constraint clamp", () => {
    class ResizeObserverMock {
      observe(): void {}
      disconnect(): void {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);

    render(
      <ModelingWorkspaceLayout
        navigator={<span>Curve navigator</span>}
        ribbon={<span>Mapping decision</span>}
        plot={<span>Persistent plot</span>}
        dataLayoutMode="compact"
        ribbonOpen
        onRibbonOpenChange={vi.fn()}
      />,
    );

    const dataRibbonPanel = latestPendingPanelHandle();
    expect(dataRibbonPanel).not.toBeNull();
    if (!dataRibbonPanel) throw new Error("Data panel handle did not arrive");
    act(() => flushLatePanelHandles());

    let panelPixels = 120;
    const resize = vi.fn();
    Object.defineProperty(dataRibbonPanel, "getSize", {
      configurable: true,
      value: () => ({ asPercentage: 0, inPixels: panelPixels }),
    });
    Object.defineProperty(dataRibbonPanel, "resize", {
      configurable: true,
      value: resize,
    });

    act(() => latestDataLayoutCallback()({}, { isUserInteraction: false }));
    expect(resize).toHaveBeenCalledTimes(1);
    expect(resize).toHaveBeenCalledWith(230);

    panelPixels = 230;
    act(() => latestDataLayoutCallback()({}, { isUserInteraction: false }));
    expect(resize).toHaveBeenCalledTimes(1);
  });

  it("remembers a user splitter size for later non-user restoration", () => {
    class ResizeObserverMock {
      observe(): void {}
      disconnect(): void {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);

    render(
      <ModelingWorkspaceLayout
        navigator={<span>Curve navigator</span>}
        ribbon={<span>Mapping decision</span>}
        plot={<span>Persistent plot</span>}
        dataLayoutMode="compact"
        ribbonOpen
        onRibbonOpenChange={vi.fn()}
      />,
    );

    const dataRibbonPanel = latestPendingPanelHandle();
    expect(dataRibbonPanel).not.toBeNull();
    if (!dataRibbonPanel) throw new Error("Data panel handle did not arrive");
    act(() => flushLatePanelHandles());

    let panelPixels = 260;
    const resize = vi.fn();
    Object.defineProperty(dataRibbonPanel, "getSize", {
      configurable: true,
      value: () => ({ asPercentage: 0, inPixels: panelPixels }),
    });
    Object.defineProperty(dataRibbonPanel, "resize", {
      configurable: true,
      value: resize,
    });

    act(() => latestDataLayoutCallback()({}, { isUserInteraction: true }));
    expect(resize).not.toHaveBeenCalled();

    panelPixels = 120;
    act(() => latestDataLayoutCallback()({}, { isUserInteraction: false }));
    expect(resize).toHaveBeenCalledTimes(1);
    expect(resize).toHaveBeenCalledWith(260);
  });

  it("uses the current mode preferred size for reset and mode changes", () => {
    class ResizeObserverMock {
      observe(): void {}
      disconnect(): void {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);

    const props = {
      navigator: <span>Curve navigator</span>,
      ribbon: <span>Mapping decision</span>,
      plot: <span>Persistent plot</span>,
      ribbonOpen: true,
      onRibbonOpenChange: vi.fn(),
    };
    render(<ModelingWorkspaceLayout {...props} dataLayoutMode="compact" />);
    const dataRibbonPanel = latestPendingPanelHandle();
    expect(dataRibbonPanel).not.toBeNull();
    if (!dataRibbonPanel) throw new Error("Data panel handle did not arrive");
    act(() => flushLatePanelHandles());

    const resize = vi.fn();
    Object.defineProperty(dataRibbonPanel, "resize", {
      configurable: true,
      value: resize,
    });
    fireEvent.doubleClick(screen.getByRole("separator", { name: "Resize Test Data controls and curve plot" }));
    expect(resize).toHaveBeenNthCalledWith(1, 230);
  });
});
