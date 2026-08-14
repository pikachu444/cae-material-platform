import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  EngineeringPane,
  EngineeringPlotRegion,
  EngineeringSection,
  SemanticStatus,
  SemanticText,
  WorkbenchMessage,
} from "./semantic-ui";

describe("semantic UI primitives", () => {
  it("keeps neutral metadata separate from actual status", () => {
    render(
      <>
        <SemanticText semanticRole="metadata">Revision r4</SemanticText>
        <SemanticStatus status="success" label="Saved model ready" detail="Revision r4" />
      </>,
    );

    const metadata = screen.getByText("Revision r4", { selector: "[data-semantic-text]" });
    expect(metadata.getAttribute("data-semantic-text")).toBe("metadata");
    expect(metadata.getAttribute("data-status")).toBeNull();
    expect(metadata.getAttribute("role")).toBeNull();

    const status = screen.getByRole("status", { name: "" });
    expect(status.getAttribute("data-status")).toBe("success");
    expect(status.textContent).toContain("Saved model ready");
    expect(status.textContent).toContain("Revision r4");
  });

  it("fixes message semantics for every supported kind", () => {
    render(
      <>
        <WorkbenchMessage kind="loading" title="Loading test data">Preserving the selected revision.</WorkbenchMessage>
        <WorkbenchMessage kind="empty" title="No candidates">Adjust the current filter.</WorkbenchMessage>
        <WorkbenchMessage kind="blocked" title="Export blocked">Save an explicit model first.</WorkbenchMessage>
        <WorkbenchMessage kind="error" title="Preview failed">The last valid preview remains available.</WorkbenchMessage>
        <WorkbenchMessage kind="recovery" title="Connection restored" action={{ label: "Retry preview", onClick: vi.fn() }}>Retry with the preserved inputs.</WorkbenchMessage>
        <WorkbenchMessage kind="engineeringCondition" title="Engineering condition">Values use the displayed coordinate system.</WorkbenchMessage>
      </>,
    );

    const expectations = [
      ["loading", "status", "polite"],
      ["empty", "status", "polite"],
      ["blocked", "alert", "assertive"],
      ["error", "alert", "assertive"],
      ["recovery", "status", "polite"],
      ["engineeringCondition", "note", "off"],
    ] as const;

    for (const [kind, role, live] of expectations) {
      const message = document.querySelector<HTMLElement>(`[data-message-kind="${kind}"]`);
      expect(message).not.toBeNull();
      expect(message?.getAttribute("role")).toBe(role);
      expect(message?.getAttribute("aria-live")).toBe(live);
    }

    const recovery = document.querySelector<HTMLElement>('[data-message-kind="recovery"]');
    expect(recovery).not.toBeNull();
    expect(within(recovery!).getByRole("button", { name: "Retry preview" })).toBeTruthy();
  });

  it("keeps a recovery action keyboard reachable", async () => {
    const user = userEvent.setup();
    const retry = vi.fn();
    render(
      <WorkbenchMessage
        kind="recovery"
        title="Preview can be retried"
        action={{ label: "Retry preview", onClick: retry }}
      >
        The exact revision and inputs are preserved.
      </WorkbenchMessage>,
    );

    await user.tab();
    const action = screen.getByRole("button", { name: "Retry preview" });
    expect(document.activeElement).toBe(action);
    await user.keyboard("{Enter}");
    expect(retry).toHaveBeenCalledOnce();
  });

  it("creates labeled flat regions without nested card grammar", () => {
    const { container } = render(
      <EngineeringPane label="Fit workspace">
        <EngineeringSection label="Candidate results">
          <SemanticText semanticRole="importantResult">Candidate B</SemanticText>
        </EngineeringSection>
      </EngineeringPane>,
    );

    expect(screen.getByRole("region", { name: "Fit workspace" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Candidate results" })).toBeTruthy();
    expect(container.querySelector(".workbench-card")).toBeNull();
    expect(container.querySelectorAll(".ux-engineering-section")).toHaveLength(1);
  });

  it("renders a companion only when labeled content is provided", () => {
    const { rerender } = render(
      <EngineeringPlotRegion label="Processed response" plot={<div>Curve plot</div>} />,
    );

    expect(screen.getByRole("group", { name: "Processed response plot" })).toBeTruthy();
    expect(document.querySelector("[data-plot-companion]")).toBeNull();

    rerender(
      <EngineeringPlotRegion
        label="Processed response"
        plot={<div>Curve plot</div>}
        companion={<div>Residual summary</div>}
        companionLabel="Residual evidence"
      />,
    );

    const companion = screen.getByRole("complementary", { name: "Residual evidence" });
    expect(companion.textContent).toContain("Residual summary");
    expect(document.querySelector('[data-has-companion="true"]')).not.toBeNull();
  });

  it("rejects empty visible labels and filler companion content", () => {
    expect(() => render(<SemanticStatus status="success" label=" " />)).toThrow(/visible label/);
    expect(() => render(
      <EngineeringPlotRegion
        label="Curve comparison"
        plot={<div>Curve plot</div>}
        companion=""
        companionLabel="Unused"
      />,
    )).not.toThrow();
    expect(document.querySelector("[data-plot-companion]")).toBeNull();
  });

  it("rejects runtime status values outside the semantic contract", () => {
    expect(() => render(
      <SemanticStatus
        status={"neutral" as "success"}
        label="Revision r4"
      />,
    )).toThrow(/does not support status/);
  });

  it.each([
    ["true", true],
    ["empty array", []],
    ["empty fragment", <></>],
    ["whitespace", "   "],
  ])("rejects a non-rendering %s plot", (_name, plot) => {
    expect(() => render(
      <EngineeringPlotRegion label="Curve comparison" plot={plot} />,
    )).toThrow(/requires plot content/);
  });

  it.each([
    ["true", true],
    ["empty array", []],
    ["empty fragment", <></>],
    ["whitespace", "   "],
  ])("does not create a companion for non-rendering %s content", (_name, companion) => {
    expect(() => render(
      <EngineeringPlotRegion
        label="Curve comparison"
        plot={<div>Curve plot</div>}
        companion={companion}
        companionLabel="Residual evidence"
      />,
    )).not.toThrow();
    expect(document.querySelector("[data-plot-companion]")).toBeNull();
  });
});

function compileTimeContracts(): void {
  if (false) {
    // @ts-expect-error neutral metadata is not an actual status
    <SemanticStatus status="neutral" label="Revision r4" />;
    // @ts-expect-error actual status always has a visible label prop
    <SemanticStatus status="success" />;
    // @ts-expect-error recovery always provides a keyboard-reachable action
    <WorkbenchMessage kind="recovery" title="Retry required">Preserved input</WorkbenchMessage>;
    // @ts-expect-error companion content and its accessible label are inseparable
    <EngineeringPlotRegion label="Curve" plot={<div>Plot</div>} companion={<div>Evidence</div>} />;
  }
}

void compileTimeContracts;
