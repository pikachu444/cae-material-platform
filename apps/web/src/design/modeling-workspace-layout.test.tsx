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
        ribbonOpen
        onRibbonOpenChange={onRibbonOpenChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Collapse curve and process navigator" }));
    expect(screen.queryByText("Curve navigator")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Hide current-stage settings" }));
    expect(onRibbonOpenChange).toHaveBeenCalledWith(false);
    expect(screen.getByText("Persistent plot")).toBeTruthy();
  });
});
