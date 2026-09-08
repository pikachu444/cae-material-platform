import { fireEvent, render, screen, within } from "@testing-library/react";
import { vi } from "vitest";
import type { MaterialDetail, MaterialRow } from "../api";
import { MaterialCard } from "./MaterialCard";
import { MaterialProperties } from "./MaterialProperties";

const material: MaterialRow = {
  id: "material", revisionId: "material-r3", name: "DP780", code: "DP780", family: "강재", materialClass: "metal", description: null,
  revision: { id: "material-r3", revision_no: 3, schema_id: "cmp.material", schema_version: "1", content_hash: "hash", created_at: "2026-01-01" },
};
const detail: MaterialDetail = {
  material,
  states: [{ id: "state", materialId: material.id, revisionId: "state-pin", name: "냉간 압연" }],
  propertySets: [{ id: "property", stateId: "state", revisionId: "property-pin", content: {
    density_kg_per_m3: 7800, youngs_modulus_pa: 210000000000, poisson_ratio: 0.3, yield_stress_pa: 450000000,
    applicability: { temperature_min_k: 293.15, temperature_max_k: 293.15, note: "Synthetic reference conditions; not validated for engineering use." },
  } }],
};

describe("material comparison cards", () => {
  it("keeps values, units and temperature; descriptive metadata stays off the comparison card", () => {
    const original = JSON.stringify(detail);
    const { rerender } = render(<MaterialCard material={material} detail={detail} failed={false} selected={false} onSelect={() => {}} />);
    const modulus = screen.getByText("탄성계수").parentElement!;
    expect(within(modulus).getByText("210")).toBeTruthy();
    expect(within(modulus).getByText("GPa")).toBeTruthy();
    expect(screen.getByText("20 °C")).toBeTruthy();
    expect(screen.queryByText(/소재 정보 r3/)).toBeNull();
    expect(screen.queryByText(/공학적 적용은 검증되지/)).toBeNull();
    rerender(<MaterialProperties detail={detail} />);
    expect(screen.getByText(/공학적 적용은 검증되지/)).toBeTruthy();
    expect(JSON.stringify(detail)).toBe(original);
  });

  it("keeps separate values and conditions when a material has multiple property sets", () => {
    const multiple: MaterialDetail = { ...detail, propertySets: [...detail.propertySets, {
      ...detail.propertySets[0], id: "hot-property", content: { youngs_modulus_pa: 190000000000, applicability: { temperature_min_k: 373.15, temperature_max_k: 373.15 } },
    }] };
    render(<MaterialCard material={material} detail={multiple} failed={false} selected={false} onSelect={() => {}} />);
    expect(screen.getAllByText("냉간 압연")).toHaveLength(2);
    expect(screen.getByText("210")).toBeTruthy();
    expect(screen.getByText("190")).toBeTruthy();
    expect(screen.getByText("20 °C")).toBeTruthy();
    expect(screen.getByText("100 °C")).toBeTruthy();
  });

  it("selects from the whole card, expands with Enter or double click, and keeps the preview button independent", () => {
    const onSelect = vi.fn();
    render(<MaterialCard material={material} detail={detail} failed={false} selected={false} onSelect={onSelect} />);
    const card = screen.getByRole("article", { name: "DP780 선택" });
    fireEvent.click(screen.getByText("탄성계수"));
    expect(onSelect).toHaveBeenLastCalledWith();
    fireEvent.keyDown(card, { key: "Enter" });
    expect(onSelect).toHaveBeenLastCalledWith(true);
    fireEvent.keyDown(card, { key: " " });
    expect(onSelect).toHaveBeenLastCalledWith(false);
    fireEvent.doubleClick(screen.getByText("탄성계수"));
    expect(onSelect).toHaveBeenLastCalledWith(true);
    onSelect.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "미리보기 →" }));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith();
  });
});
