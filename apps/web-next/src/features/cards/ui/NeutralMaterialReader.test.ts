import { describe, expect, it } from "vitest";
import { parameterRows } from "./NeutralMaterialReader";

describe("saved model parameter display", () => {
  it("uses GPa and MPa only for declared Pa parameters and preserves saved values", () => {
    const source = { youngs_modulus: { value: 210e9, unit: "Pa" }, initial_yield_stress: { value: 450e6, unit: "Pa" }, poisson_ratio: { value: 0.3, unit: "1" } };
    const original = JSON.stringify(source);
    expect(parameterRows(source).map(row => row.item)).toEqual([{ value: 210, unit: "GPa" }, { value: 0.3, unit: "1" }, { value: 450, unit: "MPa" }]);
    expect(JSON.stringify(source)).toBe(original);
    expect(parameterRows({ youngs_modulus: { value: 210, unit: "GPa" } })[0].item.value).toBe(210);
  });
});
