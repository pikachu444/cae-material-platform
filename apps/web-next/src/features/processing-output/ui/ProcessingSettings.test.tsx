import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ProcessingSettings } from "./ProcessingSettings";

describe("saved processing settings", () => {
  it("preserves a consequential exclusion choice and stored modulus without inventing defaults", () => {
    render(<ProcessingSettings steps={[{ method_id: "metal.engineering_to_true_plastic", method_version: "1.0.0",
      options: { negative_plastic_policy: "drop", youngs_modulus_pa: 210e9, manual_necking_index: 0 } }]} />);
    expect(screen.getByText("음의 소성 변형률")).not.toBeNull();
    expect(screen.getByText("제외")).not.toBeNull();
    expect(screen.getByText("210")).not.toBeNull();
    expect(screen.getByText("0")).not.toBeNull();
    expect(screen.queryByText("주 모델 가중치")).toBeNull();
  });
});
