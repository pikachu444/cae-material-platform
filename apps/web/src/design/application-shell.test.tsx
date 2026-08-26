import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApplicationShell, publishWorkspaceCommandState, publishWorkspaceStatus } from "./application-shell";

describe("ApplicationShell", () => {
  it("keeps global navigation and status separate while Materials modes stay local to the workspace", () => {
    render(<ApplicationShell path="/materials" navigate={vi.fn()}><input aria-label="Search materials" /></ApplicationShell>);

    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Materials commands" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Compare" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Browse Tree" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Subsets" })).toBeNull();
    expect(screen.queryByRole("button", { name: "New material" })).toBeNull();

    act(() => publishWorkspaceCommandState("materials:browse"));
    expect(screen.queryByRole("button", { name: "Browse Tree" })).toBeNull();

    act(() => publishWorkspaceStatus({ selection: "DP780", revision: "r4 · released", jobs: "1 job running", warnings: "1 warning" }));
    expect(screen.getByRole("status").textContent).toContain("DP780");
    expect(screen.getByRole("status").textContent).toContain("r4 · released");
  });

  it("focuses search with Ctrl+K and cycles shell regions with F6", () => {
    render(<ApplicationShell path="/materials" navigate={vi.fn()}><input aria-label="Search materials" /></ApplicationShell>);

    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(document.activeElement).toBe(screen.getByRole("textbox", { name: "Search materials" }));

    fireEvent.keyDown(window, { key: "F6" });
    expect(document.activeElement).toBe(document.querySelector(".application-status-bar"));
    fireEvent.keyDown(window, { key: "F6" });
    expect(document.activeElement).toBe(document.querySelector(".application-menu-bar"));
  });

  it("reports offline and restored connection state", () => {
    render(<ApplicationShell path="/materials" navigate={vi.fn()}><p>workspace</p></ApplicationShell>);

    act(() => window.dispatchEvent(new Event("offline")));
    expect(screen.getByText("Offline")).toBeTruthy();
    act(() => window.dispatchEvent(new Event("online")));
    expect(screen.getByText("Online")).toBeTruthy();
  });

  it("distinguishes a degraded service from a browser network outage", () => {
    render(<ApplicationShell path="/materials" navigate={vi.fn()}><p>workspace</p></ApplicationShell>);

    act(() => publishWorkspaceStatus({ connection: "degraded" }));
    expect(screen.getByText("Service unavailable")).toBeTruthy();
  });

  it.each(["/catalog/schema", "/catalog/records"])(
    "keeps the global navigation and omits the duplicate command bar for legacy Administration path %s",
    (path) => {
      render(<ApplicationShell path={path} navigate={vi.fn()}><p>administration workspace</p></ApplicationShell>);

      const primary = screen.getByRole("navigation", { name: "Primary navigation" });
      expect(screen.getByRole("button", { name: "Materials" })).toBeTruthy();
      expect(screen.getByRole("button", { name: "Modeling" })).toBeTruthy();
      expect(screen.getByRole("button", { name: "Activity" })).toBeTruthy();
      expect(primary.querySelector('[aria-current="page"]')).toBeNull();
      expect(screen.queryByRole("region", { name: "Materials commands" })).toBeNull();
      expect(document.querySelector(".application-shell")?.classList.contains("workspace-command-bar-omitted")).toBe(true);
    },
  );
});
