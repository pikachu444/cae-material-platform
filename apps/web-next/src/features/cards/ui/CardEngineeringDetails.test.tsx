import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { CardEngineeringDetails } from "./CardEngineeringDetails";
import type { SolverCardDetail } from "../api";

describe("stored solver-card engineering details", () => {
  it("exposes approximate and unsupported output semantics without exposing storage identifiers", () => {
    const content = { density_kg_per_m3: 7800, youngs_modulus_pa: 210e9, poisson_ratio: 0.3,
      solver_material_id: 9001, mapping_statuses: { post_necking_extension: "approximated", temperature_dependence: "unsupported" },
      applicability: { temperature_min_k: 293.15, temperature_max_k: 293.15 }, content_hash: "storage-only-hash" };
    const detail = { payload: { current_revision: { id: "storage-only-id", content } } } as unknown as SolverCardDetail;
    render(<CardEngineeringDetails detail={detail} />);
    expect(screen.getByText("근사 적용")).not.toBeNull();
    expect(screen.getByText("미지원")).not.toBeNull();
    expect(screen.getByText("210")).not.toBeNull();
    expect(screen.getByText("GPa")).not.toBeNull();
    expect(screen.getByText("9001")).not.toBeNull();
    expect(screen.queryByText("storage-only-hash")).toBeNull();
    expect(screen.queryByText("storage-only-id")).toBeNull();
    expect(content.youngs_modulus_pa).toBe(210e9);
  });
});


it.each(["terms", "prony_terms", "nested"])("shows stored Prony values from %s without inventing bulk relaxation", (source) => {
  const terms = [{ g_ratio: 0.1234, relaxation_time_s: 2.5 }];
  const content = source === "nested" ? { constitutive_model: { prony_terms: [{ g_ratio: 0.1234, relaxation_time: { value: 2.5, unit: "s" } }] } } : { [source]: terms };
  render(<CardEngineeringDetails detail={{ payload: { current_revision: { content } } } as unknown as SolverCardDetail} />);
  expect(screen.getByText("전단 비율 g")).not.toBeNull();
  expect(screen.getByText("0.1234")).not.toBeNull();
  expect(screen.getByText("2.5")).not.toBeNull();
  expect(screen.getByText("미등록")).not.toBeNull();
  expect(terms[0]).not.toHaveProperty("k_ratio");
});
