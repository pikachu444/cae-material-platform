from __future__ import annotations

import numpy as np
import pytest
from cmp.modules.processing.domain.metal_hardening import (
    HARDENING_EQUATION_CONTRACT,
    MetalHardeningError,
    evaluate_hardening_family,
    fit_hardening_candidates,
)


@pytest.mark.parametrize(
    ("family", "parameters", "expected"),
    [
        ("voce", (300.0, 200.0, 10.0), 300.0 + 200.0 * (1.0 - np.exp(-1.0))),
        ("swift", (500.0, 0.01, 0.2), 500.0 * 0.11**0.2),
        (
            "hockett_sherby",
            (300.0, 200.0, 10.0, 0.8),
            300.0 + 200.0 * (1.0 - np.exp(-10.0 * 0.1**0.8)),
        ),
        ("ghosh", (500.0, 0.8, 0.18, 0.42), 500.0 * 0.7 ** (0.18 - 0.42)),
    ],
)
def test_public_hardening_equations_match_analytical_values(
    family: str, parameters: tuple[float, ...], expected: float
) -> None:
    response = evaluate_hardening_family(family, parameters, np.array([0.1]))
    assert response[0] == pytest.approx(expected)


def _options() -> dict[str, object]:
    return {
        "equation_contract": HARDENING_EQUATION_CONTRACT,
        "plastic_strain_quantity": "strain.true_plastic",
        "stress_quantity": "stress.true",
        "families": ["voce", "swift", "hockett_sherby", "ghosh"],
        "fit_minimum_strain": 0.001,
        "fit_maximum_strain": 0.15,
        "extrapolation_maximum_strain": 0.5,
        "output_point_count": 101,
        "primary_family": "swift",
        "secondary_family": "voce",
        "primary_weight": 0.25,
        "normalization_stress_pa": 100e6,
        "maximum_function_evaluations": 10_000,
        "selection_reason": "Best residual shape without late-strain softening.",
    }


def test_candidates_share_objective_and_combination_is_explicit_and_bounded() -> None:
    strain = np.linspace(0.001, 0.15, 31)
    stress = evaluate_hardening_family("voce", (350e6, 250e6, 15.0), strain)
    result = fit_hardening_candidates(
        {"strain.true_plastic": strain, "stress.true": stress},
        {"strain.true_plastic": "1", "stress.true": "Pa"},
        _options(),
    )

    grid = result.columns["strain.true_plastic"]
    assert len(grid) == 101
    assert grid[0] == 0.0
    assert grid[-1] == 0.5
    assert set(result.columns) == {
        "strain.true_plastic",
        "stress.hardening.voce",
        "stress.hardening.swift",
        "stress.hardening.hockett_sherby",
        "stress.hardening.ghosh",
        "stress.hardening.selected",
    }
    combined = (
        0.25 * result.columns["stress.hardening.swift"]
        + 0.75 * result.columns["stress.hardening.voce"]
    )
    assert result.columns["stress.hardening.selected"] == pytest.approx(combined)
    scalar = {item.key: item.value for item in result.scalars}
    assert scalar["voce.relative_rmse"] < 1e-8
    lower = scalar["voce.parameter.sigma_0_pa.lower"]
    upper = scalar["voce.parameter.sigma_0_pa.upper"]
    assert lower <= scalar["voce.parameter.sigma_0_pa.initial"] <= upper
    assert lower <= scalar["voce.parameter.sigma_0_pa"] <= upper
    assert scalar["selection.primary_weight"] == 0.25
    assert scalar["fit.observed_maximum_strain"] == 0.15
    assert scalar["fit.extrapolation_maximum_strain"] == 0.5
    assert "ghosh.parameter.delta_p_minus_n" in scalar
    assert "ghosh.parameter.n" not in scalar
    assert "ghosh.parameter.p" not in scalar
    assert "ghosh.parameter.d_pa" not in scalar
    assert f"equation_contract={HARDENING_EQUATION_CONTRACT}" in result.diagnostics
    assert "extrapolated domain (0.15, 0.5] is not observed" in result.diagnostics
    assert any(
        "public n and p are structurally non-identifiable" in item for item in result.diagnostics
    )
    assert (
        "selection reason: Best residual shape without late-strain softening." in result.diagnostics
    )

    repeated = fit_hardening_candidates(
        {"strain.true_plastic": strain, "stress.true": stress},
        {"strain.true_plastic": "1", "stress.true": "Pa"},
        _options(),
    )
    assert repeated.columns["stress.hardening.selected"] == pytest.approx(
        result.columns["stress.hardening.selected"]
    )
    assert repeated.scalars == result.scalars


def test_fit_rejects_hidden_or_unbounded_extrapolation() -> None:
    strain = np.linspace(0.001, 0.15, 31)
    stress = evaluate_hardening_family("voce", (350e6, 250e6, 15.0), strain)
    options = _options()
    options["extrapolation_maximum_strain"] = 5.1

    with pytest.raises(MetalHardeningError, match="extrapolation maximum <= 5"):
        fit_hardening_candidates(
            {"strain.true_plastic": strain, "stress.true": stress},
            {"strain.true_plastic": "1", "stress.true": "Pa"},
            options,
        )


def test_fit_rejects_legacy_recipe_without_explicit_equation_contract() -> None:
    strain = np.linspace(0.001, 0.15, 31)
    stress = evaluate_hardening_family("voce", (350e6, 250e6, 15.0), strain)
    options = _options()
    del options["equation_contract"]

    with pytest.raises(MetalHardeningError, match="legacy hardening recipes"):
        fit_hardening_candidates(
            {"strain.true_plastic": strain, "stress.true": stress},
            {"strain.true_plastic": "1", "stress.true": "Pa"},
            options,
        )


def test_ghosh_public_variant_domain_and_structural_invariance() -> None:
    strain = np.array([0.0, 0.1, 0.4])
    reference = evaluate_hardening_family("ghosh", (420e6, 0.8, 0.18, 0.42), strain)
    shifted = evaluate_hardening_family("ghosh", (420e6, 0.8, 0.28, 0.52), strain)

    assert shifted == pytest.approx(reference)
    with pytest.raises(MetalHardeningError, match="plastic strain < epsilon_0"):
        evaluate_hardening_family("ghosh", (420e6, 0.8, 0.18, 0.42), np.array([0.8]))
