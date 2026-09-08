import { render, screen } from "@testing-library/react";
import { PropertySetValues } from "./MaterialProperties";
import { materialPropertyRows } from "./material-property-display";

describe("material property display", () => {
  it("keeps small magnitudes and exact values when comparison numbers are shortened", () => {
    const propertySet = { id: "property", stateId: "state", revisionId: "pin", content: { youngs_modulus_pa: 3322222222, poisson_ratio: 0.00000031 } };
    const original = JSON.stringify(propertySet);
    const compact = materialPropertyRows(propertySet, true);
    expect(compact.find(row => row.key === "youngs_modulus_pa")?.value).toBe("3.322");
    expect(compact.find(row => row.key === "youngs_modulus_pa")?.exactValue).toBe("3.322222222");
    expect(compact.find(row => row.key === "poisson_ratio")?.value).not.toBe("0");
    expect(JSON.stringify(propertySet)).toBe(original);
  });
  it("distinguishes applicability from test temperature and converts display units without mutating the stored property", () => {
    const propertySet = {id:"property",stateId:"state",revisionId:"pin",content:{youngs_modulus_pa:210000000000,yield_stress_pa:450000000,applicability:{temperature_min_k:293.15,temperature_max_k:293.15,strain_rate_min_per_s:null,strain_rate_max_per_s:null}}};
    const original = JSON.stringify(propertySet);
    render(<PropertySetValues propertySet={propertySet} stateName="저장된 소재 상태" />);
    expect(screen.getByText("물성 적용 온도")).toBeTruthy();
    expect(screen.queryByText("시험 온도")).toBeNull();
    expect(screen.getByText("20 °C")).toBeTruthy();
    expect(screen.getByText("210")).toBeTruthy();
    expect(screen.getByText("GPa")).toBeTruthy();
    expect(screen.getByText("450")).toBeTruthy();
    expect(screen.getByText("MPa")).toBeTruthy();
    expect(screen.getAllByText("미등록").length).toBeGreaterThan(0);
    expect(JSON.stringify(propertySet)).toBe(original);
  });
});
