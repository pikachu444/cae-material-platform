import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useBrowserNavigation } from "./navigation";

function NavigationHarness() {
  const { location, navigate, replace } = useBrowserNavigation();
  return (
    <div>
      <output aria-label="Current location">{location}</output>
      <button type="button" onClick={() => navigate("/modeling?stage=fit")}>
        Open Fit
      </button>
      <button type="button" onClick={() => replace("/materials")}>
        Replace with Materials
      </button>
    </div>
  );
}

describe("useBrowserNavigation", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/materials?q=DP780");
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("projects push navigation from browser history and skips an identical target", () => {
    const pushState = vi.spyOn(window.history, "pushState");
    render(<NavigationHarness />);

    fireEvent.click(screen.getByRole("button", { name: "Open Fit" }));
    fireEvent.click(screen.getByRole("button", { name: "Open Fit" }));

    expect(pushState).toHaveBeenCalledTimes(1);
    expect(window.location.pathname).toBe("/modeling");
    expect(window.location.search).toBe("?stage=fit");
    expect(screen.getByLabelText("Current location").textContent).toBe(
      "/modeling?stage=fit",
    );
  });

  it("reads popstate from browser history instead of maintaining a second route truth", () => {
    render(<NavigationHarness />);

    act(() => {
      window.history.pushState({}, "", "/activity?view=recent");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });

    expect(screen.getByLabelText("Current location").textContent).toBe(
      "/activity?view=recent",
    );
  });

  it("replaces the current entry while synchronizing the projected location", () => {
    const replaceState = vi.spyOn(window.history, "replaceState");
    render(<NavigationHarness />);

    fireEvent.click(
      screen.getByRole("button", { name: "Replace with Materials" }),
    );

    expect(replaceState).toHaveBeenCalledTimes(1);
    expect(window.location.pathname).toBe("/materials");
    expect(window.location.search).toBe("");
    expect(screen.getByLabelText("Current location").textContent).toBe(
      "/materials",
    );
  });
});
