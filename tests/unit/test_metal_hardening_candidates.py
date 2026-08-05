from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
import yaml
from cmp.modules.processing.domain.metal_hardening import (
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


def test_ghosh_public_variant_domain_and_structural_invariance() -> None:
    strain = np.array([0.0, 0.1, 0.4])
    reference = evaluate_hardening_family("ghosh", (420e6, 0.8, 0.18, 0.42), strain)
    shifted = evaluate_hardening_family("ghosh", (420e6, 0.8, 0.28, 0.52), strain)

    assert shifted == pytest.approx(reference)
    with pytest.raises(MetalHardeningError, match="plastic strain < epsilon_0"):
        evaluate_hardening_family("ghosh", (420e6, 0.8, 0.18, 0.42), np.array([0.8]))


def _reference_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[2]
    return (
        root / "fixtures" / "synthetic" / "metal-hardening-reference-v1.json",
        root / "fixtures" / "manifests" / "metal-hardening-reference-v1.yaml",
    )


def _independent_stress_and_tangent(
    family: str, parameters: dict[str, float], strain: float
) -> tuple[float, float | None]:
    if family == "voce":
        k_0 = parameters["K0"]
        q = parameters["Q"]
        b = parameters["B"]
        exponential = math.exp(-b * strain)
        return k_0 + q * (1.0 - exponential), q * b * exponential
    if family == "swift":
        a = parameters["A"]
        epsilon_0 = parameters["epsilon_0"]
        n = parameters["n"]
        base = strain + epsilon_0
        return a * base**n, a * n * base ** (n - 1.0)
    if family == "hockett_sherby":
        q_s = parameters["Qs"]
        q_0 = parameters["Q0"]
        m = parameters["m"]
        n = parameters["n"]
        if strain == 0.0:
            return q_0, None
        strain_power = strain**n
        exponential = math.exp(-m * strain_power)
        stress = q_s - (q_s - q_0) * exponential
        tangent = (q_s - q_0) * m * n * strain ** (n - 1.0) * exponential
        return stress, tangent
    if family == "ghosh":
        k = parameters["K"]
        epsilon_0 = parameters["epsilon_0"]
        n = parameters["n"]
        p = parameters["p"]
        base = epsilon_0 - strain
        return k * base ** (n - p), k * (p - n) * base ** (n - p - 1.0)
    raise AssertionError(f"unknown reference family {family}")


def _assert_fixture_tolerance(
    actual: float, expected: float, tolerance: dict[str, Any], absolute_key: str
) -> None:
    absolute = float(tolerance[absolute_key])
    relative = float(tolerance["relative"])
    assert abs(actual - expected) <= max(absolute, relative * abs(expected))


def test_reference_fixture_digest_values_and_objective_are_independent() -> None:
    fixture_path, manifest_path = _reference_paths()
    fixture_bytes = fixture_path.read_bytes()
    fixture = cast(dict[str, Any], json.loads(fixture_bytes))
    manifest = cast(dict[str, Any], yaml.safe_load(manifest_path.read_text(encoding="utf-8")))

    digest = hashlib.sha256(fixture_bytes).hexdigest()
    assert manifest["fixture"]["digest"]["algorithm"] == "sha256"
    assert digest == manifest["fixture"]["digest"]["value"]
    assert manifest["fixture"]["id"] == fixture["fixture_id"]
    assert manifest["fixture"]["classification"] == fixture["classification"]
    assert fixture["generation"]["production_functions_called"] == []
    assert fixture["reference_case_count"] == 4
    assert fixture["curve_point_row_count"] == 24
    manifest_source_ids = [item["id"] for item in manifest["sources"]]
    fixture_source_ids = [item["id"] for item in fixture["source_catalog"]]
    assert manifest_source_ids == fixture_source_ids

    tolerances = cast(dict[str, dict[str, Any]], fixture["tolerances"])
    family_ids: list[str] = []
    point_rows = 0
    for family_case_any in fixture["families"]:
        family_case = cast(dict[str, Any], family_case_any)
        family = cast(str, family_case["id"])
        family_ids.append(family)
        parameters = {
            cast(str, item["symbol"]): float(item["value"])
            for item in cast(list[dict[str, Any]], family_case["public_parameters"])
        }
        expected_curve = cast(list[dict[str, Any]], family_case["expected_curve"])
        point_rows += len(expected_curve)
        for point in expected_curve:
            strain = float(point["plastic_strain"])
            stress, tangent = _independent_stress_and_tangent(family, parameters, strain)
            _assert_fixture_tolerance(
                stress,
                float(point["stress_pa"]),
                tolerances[cast(str, point["stress_tolerance_id"])],
                "absolute_pa",
            )
            if point["tangent_pa"] is None:
                assert tangent is None
                assert point["tangent_limit"] == "positive_infinity"
            else:
                assert tangent is not None
                _assert_fixture_tolerance(
                    tangent,
                    float(point["tangent_pa"]),
                    tolerances[cast(str, point["tangent_tolerance_id"])],
                    "absolute_pa",
                )

    assert family_ids == ["voce", "swift", "hockett_sherby", "ghosh"]
    assert point_rows == fixture["curve_point_row_count"]

    objective = cast(dict[str, Any], fixture["objective_contract"])
    perturbation = cast(dict[str, Any], objective["deterministic_perturbation_case"])
    residual = [float(item) for item in perturbation["expected_residual_pa"]]
    observed_offset = [float(item) for item in perturbation["observed_offset_pa"]]
    assert residual == [-item for item in observed_offset]
    normalization = float(objective["normalization_stress_pa"])
    normalized = [item / normalization for item in residual]
    sum_squared = sum(item * item for item in normalized)
    rmse = math.sqrt(sum(item * item for item in residual) / len(residual))
    objective_tolerance = tolerances["objective_f64"]
    _assert_fixture_tolerance(
        sum_squared,
        float(perturbation["expected_sum_squared_normalized_residuals"]),
        objective_tolerance,
        "absolute",
    )
    _assert_fixture_tolerance(
        0.5 * sum_squared,
        float(perturbation["expected_scipy_cost_equivalent"]),
        objective_tolerance,
        "absolute",
    )
    assert rmse == pytest.approx(float(perturbation["expected_rmse_pa"]), rel=5e-13)
