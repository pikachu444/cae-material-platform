import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ModelingTrackMenu } from "./modeling-track-menu";

afterEach(cleanup);

describe("ModelingTrackMenu", () => {
  it("exposes model families as one compact keyboard-operable menu", () => {
    const change = vi.fn();
    const { container } = render(<ModelingTrackMenu value="metal" onChange={change} onOpenValidation={vi.fn()} />);
    const details = container.querySelector("details") as HTMLDetailsElement;
    fireEvent.click(screen.getByText("Change model family"));
    const metal = screen.getByRole("menuitemradio", { name: "Metal · elastoplastic" });
    const polymer = screen.getByRole("menuitemradio", { name: "Polymer · viscoelastic" });
    metal.focus();
    fireEvent.keyDown(metal, { key: "ArrowDown" });
    expect(document.activeElement).toBe(polymer);
    fireEvent.click(polymer);
    expect(change).toHaveBeenCalledWith("polymer");
    expect(details.open).toBe(false);
    expect(document.activeElement).toBe(screen.getByText("Change model family"));
  });
});
