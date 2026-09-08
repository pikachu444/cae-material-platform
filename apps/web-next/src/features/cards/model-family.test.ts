import { describe, expect, it } from "vitest";
import { cardModelFamily } from "./model-family";

describe("card model grouping", () => {
  it("groups the same model content together across API compatibility families", () => {
    expect(cardModelFamily({ family: "neutral_solver", neutralFamily: "isotropic_tabulated_plasticity" }))
      .toBe(cardModelFamily({ family: "tabulated_plasticity", neutralFamily: null }));
    expect(cardModelFamily({ family: "neutral_hyperelastic", neutralFamily: "ogden_prony" }))
      .toBe(cardModelFamily({ family: "ogden_prony", neutralFamily: null }));
  });
  it("does not invent a constitutive model when the exchange document family is absent", () => {
    expect(cardModelFamily({ family: "neutral_solver", neutralFamily: null })).toBe("소재 모델");
    expect(cardModelFamily({ family: "unsupported", neutralFamily: null })).toBe("미지원");
  });
});
