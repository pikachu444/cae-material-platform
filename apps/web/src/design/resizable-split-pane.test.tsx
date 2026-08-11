import { fireEvent, render, screen } from "@testing-library/react";
import { useRef, useState } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  ContextPaneOverlay,
  desktopViewportClass,
  materialsPaneDefaults,
  ResizableSplitPane,
  shouldUseContextOverlay,
} from "./resizable-split-pane";

describe("ResizableSplitPane", () => {
  it("uses the three approved desktop viewport classes", () => {
    expect(desktopViewportClass(1366)).toBe("compact");
    expect(desktopViewportClass(1440)).toBe("standard");
    expect(desktopViewportClass(1920)).toBe("wide");
  });

  it("keeps compact divider controls usable when ResizeObserver is unavailable", () => {
    render(<ResizableSplitPane id="test" navigator={<aside>Navigator content</aside>} main={<main>Main content</main>} context={<aside>Context content</aside>} navigatorLabel="filters" contextLabel="details" />);

    expect(screen.getByText("Navigator content")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Collapse filters pane" }));
    expect(screen.queryByText("Navigator content")).toBe(null);
    fireEvent.click(screen.getByRole("button", { name: "Expand details pane" }));
    expect(screen.getByText("Context content")).toBeTruthy();
  });

  it("starts each viewport at the approved Materials pane topology", () => {
    expect(materialsPaneDefaults.compact).toEqual({ navigator: 244, main: 1102, context: 0 });
    expect(materialsPaneDefaults.standard).toEqual({ navigator: 264, main: 856, context: 280 });
    expect(materialsPaneDefaults.wide).toEqual({ navigator: 280, main: 1292, context: 300 });
  });

  it("exposes divider reset affordances alongside collapse controls", () => {
    render(<ResizableSplitPane id="reset" navigator={<aside>Navigator content</aside>} main={<main>Main content</main>} context={<aside>Context content</aside>} navigatorLabel="filters" contextLabel="details" />);

    expect(screen.getByRole("separator", { name: "Resize filters" }).getAttribute("title")).toContain("reset filters width");
    expect(screen.getByRole("separator", { name: "Resize details" }).getAttribute("title")).toContain("reset details width");
  });

  it("uses an overlay only after explicit expansion receives less than one pixel", () => {
    expect(shouldUseContextOverlay(false, 0)).toBe(false);
    expect(shouldUseContextOverlay(true, 0.99)).toBe(true);
    expect(shouldUseContextOverlay(true, 1)).toBe(false);
  });

  it("closes the allocation-driven context overlay, returns focus, and preserves its direct action", () => {
    const openDatasheet = vi.fn();
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
      callback(0);
      return 1;
    });

    function Harness() {
      const [open, setOpen] = useState(false);
      const triggerRef = useRef<HTMLButtonElement>(null);
      return (
        <>
          <button ref={triggerRef} type="button" onClick={() => setOpen(true)}>Show details</button>
          <ContextPaneOverlay
            open={open}
            label="details"
            triggerRef={triggerRef}
            onClose={() => setOpen(false)}
          >
            <button type="button" onClick={openDatasheet}>Open datasheet</button>
          </ContextPaneOverlay>
        </>
      );
    }

    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "Show details" });
    fireEvent.click(trigger);
    expect(screen.getByRole("dialog", { name: "details pane" })).toBeTruthy();
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Close details pane" }),
    );

    const directAction = screen.getByRole("button", { name: "Open datasheet" });
    fireEvent.keyDown(document.activeElement!, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(directAction);
    fireEvent.keyDown(directAction, { key: "Tab" });
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Close details pane" }),
    );
    fireEvent.click(directAction);
    expect(openDatasheet).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(directAction, { key: "Escape" });

    expect(screen.queryByRole("dialog", { name: "details pane" })).toBeNull();
    expect(document.activeElement).toBe(trigger);
    vi.restoreAllMocks();
  });
});
