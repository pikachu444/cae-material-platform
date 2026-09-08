import { describe, expect, it } from "vitest";
import { exactModelState, modelParameterSummary } from "./ModelsReader";
import type { MaterialModelRow } from "../api";
import type { MaterialDetail } from "../../materials/api";
const row: MaterialModelRow = { id: "model", revisionId: "model-pin", family: "elastic", schemaId: "elastic", resourcePath: "material-models", stateId: "state", stateRevisionId: "saved", content: { youngs_modulus_pa: 210e9, yield_stress_pa: 450e6, reference_temperature_k: 293.15 }, ir: {} };
describe("model normal-surface exact context", () => {
  it("uses a state name only for the exact stored revision", () => {
    const materials = [{ material: { name: "강재" }, states: [{ id: "state", revisionId: "saved", name: "열처리" }] }] as MaterialDetail[];
    expect(exactModelState(row, materials)).toEqual({ materialName: "강재", stateName: "열처리" });
    expect(exactModelState({ ...row, stateRevisionId: "older" }, materials)).toBeNull();
    expect(exactModelState({ ...row, stateRevisionId: null }, materials)).toBeNull();
  });
  it("converts declared display units while preserving original parameters", () => {
    const original = JSON.stringify(row);
    expect(modelParameterSummary(row).map(({ value, unit }) => [value, unit])).toEqual([["210", "GPa"], ["450", "MPa"], ["20", "°C"]]);
    expect(JSON.stringify(row)).toBe(original);
    expect(modelParameterSummary({ ...row, content: { youngs_modulus_pa: { value: 210, unit: "GPa" } } })[0].value).toBe("210");
  });
});
