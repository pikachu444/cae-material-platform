import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { desktopViewportClass, materialsPaneDefaults, ResizableSplitPane } from "./resizable-split-pane";

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
});
