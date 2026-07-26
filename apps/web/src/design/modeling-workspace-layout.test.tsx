import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ModelingWorkspaceLayout } from "./modeling-workspace-layout";

describe("ModelingWorkspaceLayout", () => {
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

    fireEvent.click(screen.getByRole("button", { name: "Collapse curve and process navigator" }));
    expect(screen.queryByText("Curve navigator")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Hide current-stage settings" }));
    expect(onRibbonOpenChange).toHaveBeenCalledWith(false);
    expect(screen.getByText("Persistent plot")).toBeTruthy();
    expect(screen.getByText("Export delivery")).toBeTruthy();
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
});
