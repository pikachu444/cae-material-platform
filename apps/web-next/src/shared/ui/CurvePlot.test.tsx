import { plotScale } from "./CurvePlot";

describe("engineering plot scale", () => {
  it.each([[0, 620], [-13, -2], [-0.0013, 0.0004], [210, 210], [0, 0]])(
    "keeps the entire sample range visible for %s to %s",
    (min, max) => {
      const scale = plotScale(min, max);
      expect(scale.min).toBeLessThanOrEqual(min);
      expect(scale.max).toBeGreaterThanOrEqual(max);
      expect(scale.max).toBeGreaterThan(scale.min);
      expect(scale.ticks.length).toBeGreaterThan(1);
      expect(scale.ticks.every(Number.isFinite)).toBe(true);
      expect(scale.ticks.every((tick, i) => i === 0 || tick > scale.ticks[i - 1])).toBe(true);
    },
  );
});
