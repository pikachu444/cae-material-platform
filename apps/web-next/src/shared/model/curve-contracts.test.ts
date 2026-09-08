import { channelAxisLabel, curveChannelPair, curveDisplayModel, curveSegments, deviationMeaning, deviationSourceCount, displayCurveMagnitude, displayCurveValue, originalUnitSummary } from "./curve-contracts";
import { makeSelectedCurve } from "../../features/test-data/model/fixtures";

describe("reader curve contract", () => {
  it("preserves scale plus offset for values and scale only for magnitudes", () => {
    const { definition, preview } = makeSelectedCurve();
    const strain = definition.channels[0];
    const stress = definition.channels[1];
    expect(displayCurveValue(strain, 0.1)).toBe(10);
    expect(displayCurveValue(stress, 210_000_000_000)).toBe(210_000);
    expect(displayCurveMagnitude(stress, 2_000_000)).toBe(2);
    expect(channelAxisLabel(stress)).toBe("공학 응력 [MPa]");
    expect(originalUnitSummary(strain)).toBe("%");
    const model = curveDisplayModel(definition, preview);
    expect(model?.xValues[421]).toBeNull();
  });

  it("does not connect null gaps and retains deviation semantics", () => {
    const { definition, preview } = makeSelectedCurve();
    const model = curveDisplayModel(definition, preview);
    expect(model).not.toBeNull();
    expect(curveSegments(model!.xValues, model!.yValues)).toHaveLength(2);
    const deviation = definition.deviations[0];
    expect(deviationMeaning(deviation)).toContain("standard deviation");
    expect(deviationMeaning(deviation)).toContain("ddof 1");
    expect(deviationSourceCount(deviation, preview, 4)).toBe(18);
  });

  it("returns an unavailable display model for incomplete curve metadata", () => {
    expect(curveDisplayModel({} as never, {} as never)).toBeNull();
  });

  it("pairs declared nonuniform x values with the selected dependent and keeps null gaps", () => {
    const { definition, preview } = makeSelectedCurve();
    const pair = curveChannelPair(definition, preview, "engineering_stress");
    expect(pair?.xValues.slice(0, 4)).toEqual([0, 0.00010010010010010009, 0.00020020020020020018, 0.0003003003003003003]);
    expect(pair?.xValues[421]).toBeNull();
    expect(pair?.yValues[421]).toBeNull();
    expect(curveSegments(pair!.xValues, pair!.yValues)).toHaveLength(2);
  });

  it("requires an explicit dependent when a declared curve has several dependents", () => {
    const { definition, preview } = makeSelectedCurve();
    const second = { ...definition.channels[1], key: "engineering_stress_fit", label: "Fitted stress" };
    const multi = { ...definition, channels: [...definition.channels, second] };
    const multiPreview = { ...preview, channels: [...preview.channels, { key: second.key, values: preview.channels[1].values }] };
    expect(curveChannelPair(multi, multiPreview)).toBeNull();
    expect(curveChannelPair(multi, multiPreview, second.key)?.dependent.key).toBe(second.key);
  });
});
