import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { desktopViewportClass, ResizableSplitPane } from "./resizable-split-pane";

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
});
