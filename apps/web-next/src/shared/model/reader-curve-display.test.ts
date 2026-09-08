import { readerCurveDisplay } from "./reader-curve-display";
import { curveChannelPair, curveSegments } from "./curve-contracts";
import { makeSelectedCurve } from "../../features/test-data/model/fixtures";

describe("approved tensile display units", () => {
  it("shows Pa as MPa and dimensionless engineering strain as percent without changing source values or gaps", () => {
    const { definition } = makeSelectedCurve();
    definition.channels[0] = { ...definition.channels[0], quantity_semantics: "mechanics.strain.engineering", unit_contract: "common", display_unit: "1", display_scale: "1", display_offset: "0" };
    definition.channels[1] = { ...definition.channels[1], quantity_semantics: "mechanics.stress.engineering", unit_contract: "common", display_unit: "Pa", display_scale: "1", display_offset: "0" };
    const original = JSON.stringify(definition);
    const values = { point_count: 4, returned_point_count: 4, sampled: false, indices: [0,1,2,3], channels: [{key:definition.channels[0].key, values:[0,.003,null,.15]}, {key:definition.channels[1].key, values:[0,450000000,null,620000000]}], deviations:[], source_counts:[] };
    const display = readerCurveDisplay(definition);
    const pair = curveChannelPair(display, values, definition.channels[1].key)!;
    expect(pair.xValues).toEqual([0,.3,null,15]);
    expect(pair.yValues).toEqual([0,450,null,620]);
    expect(curveSegments(pair.xValues,pair.yValues)).toHaveLength(2);
    expect(pair.independent.display_unit).toBe("%");
    expect(pair.dependent.display_unit).toBe("MPa");
    expect(JSON.stringify(definition)).toBe(original);
  });
  it("retains already declared units, other quantities and explicit legacy contracts", () => {
    const { definition } = makeSelectedCurve();
    const original = JSON.stringify(definition);
    expect(JSON.stringify(readerCurveDisplay(definition))).toBe(original);
    definition.channels[0] = {...definition.channels[0], unit_contract:"explicit_legacy",display_unit:"1"};
    expect(readerCurveDisplay(definition)?.channels[0]).toBe(definition.channels[0]);
  });
});
