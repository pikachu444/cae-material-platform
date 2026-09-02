import { describe, expect, it } from "vitest";

import {
  formatPolymerAxisTick,
  formatPolymerDeviation,
  formatPolymerFitNumber,
  formatPolymerInputNumber,
  formatPolymerRangeCoordinate,
} from "./polymer-linear-viscoelastic-format";

describe("Polymer Fit number presentation", () => {
  it("keeps ordinary engineering coordinates readable without trailing precision noise", () => {
    expect(formatPolymerFitNumber(0.01)).toBe("0.01");
    expect(formatPolymerFitNumber(0.1)).toBe("0.1");
    expect(formatPolymerFitNumber(1)).toBe("1");
    expect(formatPolymerFitNumber(296.15)).toBe("296.15");
  });

  it("uses compact scientific notation only for very large or very small exact values", () => {
    expect(formatPolymerFitNumber(1_089_000_000)).toBe("1.089e+9");
    expect(formatPolymerFitNumber(0.000_125)).toBe("1.250e-4");
    expect(formatPolymerFitNumber(null)).toBe("—");
  });

  it("keeps editable engineering ranges concise without changing their numeric meaning", () => {
    expect(formatPolymerInputNumber(4_000_000)).toBe("4e6");
    expect(formatPolymerInputNumber(0.000_003_333_333_333)).toBe("3.333e-6");
    expect(formatPolymerInputNumber(3333.333_333_333)).toBe("3333.33");
    expect(Number(formatPolymerInputNumber(0.000_03))).toBe(0.000_03);
  });

  it("shows error as a readable percentage without false zero precision", () => {
    expect(formatPolymerDeviation(0)).toBe("0%");
    expect(formatPolymerDeviation(0.000_001)).toBe("<0.01%");
    expect(formatPolymerDeviation(0.012_345)).toBe("1.23%");
  });

  it("shows wide engineering ranges with readable powers of ten", () => {
    expect(formatPolymerRangeCoordinate(0.001)).toBe("10⁻³");
    expect(formatPolymerRangeCoordinate(1_000)).toBe("1000");
    expect(formatPolymerRangeCoordinate(10_000)).toBe("10⁴");
    expect(formatPolymerRangeCoordinate(0.000_125)).toBe("1.25 × 10⁻⁴");
  });

  it("keeps graph ticks short enough to scan", () => {
    expect(formatPolymerAxisTick(12.0708)).toBe("12.1");
    expect(formatPolymerAxisTick(7.73648)).toBe("7.74");
    expect(formatPolymerAxisTick(0.000_001)).toBe("10⁻⁶");
  });
});
