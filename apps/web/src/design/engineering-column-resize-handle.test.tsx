import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EngineeringColumnResizeHandle } from "./engineering-column-resize-handle";

describe("EngineeringColumnResizeHandle", () => {
  it("resizes a column from the keyboard within its limits", () => {
    const onChange = vi.fn();
    render(<EngineeringColumnResizeHandle label="Material" width={220} min={160} max={360} onChange={onChange} />);
    const handle = screen.getByRole("separator", { name: "Resize Material column" });
    fireEvent.keyDown(handle, { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith(228);
  });
});
