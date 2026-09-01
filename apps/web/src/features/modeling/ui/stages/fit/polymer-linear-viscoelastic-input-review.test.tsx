import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PolymerLinearViscoelasticInputReview } from "./polymer-linear-viscoelastic-input-review";

afterEach(cleanup);

describe("Polymer input review", () => {
  it("keeps the normal calculation surface to one action and collapsed input details", () => {
    const calculate = vi.fn();
    const { container } = render(
      <PolymerLinearViscoelasticInputReview
        items={[{ label: "Input", value: "Relaxation response" }]}
        setupStatus="approved"
        busy={false}
        onCalculate={calculate}
      />,
    );

    const details = container.querySelector("details") as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(screen.queryByText(/approved|ready|revision|digest/i)).toBeNull();
    expect(screen.queryByRole("button", { name: "Calculation settings" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Calculate Prony models" }));
    expect(calculate).toHaveBeenCalledOnce();
  });

  it("explains the next user action without exposing approval terminology", () => {
    const reviewSettings = vi.fn();
    render(
      <PolymerLinearViscoelasticInputReview
        items={[]}
        setupStatus="missing"
        busy={false}
        onReviewSetup={reviewSettings}
        onCalculate={() => undefined}
      />,
    );

    expect(screen.getByText("Calculation settings need review")).toBeTruthy();
    expect(screen.queryByText(/approval|approved/i)).toBeNull();
    expect(screen.queryByRole("button", { name: "Calculate Prony models" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Review calculation settings" }));
    expect(reviewSettings).toHaveBeenCalledOnce();
  });

  it("offers one status check while calculation review is pending", () => {
    const checkStatus = vi.fn();
    render(
      <PolymerLinearViscoelasticInputReview
        items={[]}
        setupStatus="review"
        busy={false}
        onRetrySetup={checkStatus}
        onCalculate={() => undefined}
      />,
    );

    expect(screen.getByText("Calculation review is pending")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Check review status" }));
    expect(checkStatus).toHaveBeenCalledOnce();
  });
});
