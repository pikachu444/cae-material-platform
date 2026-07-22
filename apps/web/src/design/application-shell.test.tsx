import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApplicationShell, publishWorkspaceStatus } from "./application-shell";

describe("ApplicationShell", () => {
  it("keeps global navigation, workspace commands, and current status in separate compact regions", () => {
    render(<ApplicationShell path="/materials" navigate={vi.fn()}><input aria-label="Search materials" /></ApplicationShell>);

    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Materials commands" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Compare" }).getAttribute("title")).toMatch(/two material rows/i);
    expect(screen.getByRole("button", { name: "Compare" }).hasAttribute("disabled")).toBe(true);

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
    expect(screen.getByText("Connected")).toBeTruthy();
  });
});
