import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ModelingFitCandidateComparison } from "./modeling-fit-candidate-comparison";

afterEach(cleanup);

describe("ModelingFitCandidateComparison", () => {
  it("keeps a long candidate set in one keyboard-reachable comparison table", () => {
    const onSelect = vi.fn();
    render(
      <ModelingFitCandidateComparison
        rows={Array.from({ length: 12 }, (_, index) => ({
          id: `candidate-${index + 1}`,
          label: `${index + 1}-term Prony`,
          selected: index === 4,
          recommended: index === 4,
          primaryValue: `${(index + 1) / 10}%`,
          secondaryValue: `${(index + 2) / 10}%`,
          status: "Calculated",
        }))}
        primaryColumnLabel="Fit difference"
        secondaryColumnLabel="Check difference"
        onSelect={onSelect}
        decision={<p>Selection editor</p>}
      />,
    );

    const table = screen.getByRole("table", { name: "Calculated model comparison" });
    expect(table.querySelectorAll("tbody tr")).toHaveLength(12);
    expect(table.parentElement?.tabIndex).toBe(0);
    expect(screen.getAllByText("Recommended")).toHaveLength(1);
    expect(screen.queryByRole("columnheader", { name: "Recommendation" })).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "Warning" })).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "Select 10-term Prony" }));
    expect(onSelect).toHaveBeenCalledWith("candidate-10");
  });
});
