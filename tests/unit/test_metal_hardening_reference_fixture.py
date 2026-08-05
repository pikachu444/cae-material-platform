from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
import yaml
from numpy.typing import NDArray
from scipy.optimize import least_squares  # type: ignore[import-untyped]

FloatArray = NDArray[np.float64]


def _reference_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[2]
    return (
        root / "fixtures" / "synthetic" / "metal-hardening-reference-v1.json",
        root / "fixtures" / "manifests" / "metal-hardening-reference-v1.yaml",
    )


def _fixture() -> dict[str, Any]:
    fixture_path, _ = _reference_paths()
    return cast(dict[str, Any], json.loads(fixture_path.read_bytes()))


def _public_stress_and_tangent(
    family: str, parameters: dict[str, float], strain: float
) -> tuple[float, float | None]:
    if strain < 0:
        raise ValueError("negative strain")
    if family == "voce":
        exponential = math.exp(-parameters["B"] * strain)
        return (
            parameters["K0"] + parameters["Q"] * (1.0 - exponential),
            parameters["Q"] * parameters["B"] * exponential,
        )
    if family == "swift":
        base = strain + parameters["epsilon_0"]
        return (
            parameters["A"] * base ** parameters["n"],
            parameters["A"] * parameters["n"] * base ** (parameters["n"] - 1.0),
        )
    if family == "hockett_sherby":
        if strain == 0.0:
            return parameters["Q0"], None
        strain_power = strain ** parameters["n"]
        exponential = math.exp(-parameters["m"] * strain_power)
        return (
            parameters["Qs"] - (parameters["Qs"] - parameters["Q0"]) * exponential,
            (parameters["Qs"] - parameters["Q0"])
            * parameters["m"]
            * parameters["n"]
            * strain ** (parameters["n"] - 1.0)
            * exponential,
        )
    if family == "ghosh":
        base = parameters["epsilon_0"] - strain
        if base <= 0:
            raise ValueError("ghosh domain")
        exponent = parameters["n"] - parameters["p"]
        return (
            parameters["K"] * base**exponent,
            parameters["K"] * (parameters["p"] - parameters["n"]) * base ** (exponent - 1.0),
        )
    raise AssertionError(f"unknown reference family {family}")


def _fit_response(family: str, parameters: FloatArray, strain: FloatArray) -> FloatArray:
    if family == "voce":
        sigma_0, q, b = parameters
        return cast(FloatArray, sigma_0 + q * (1.0 - np.exp(-b * strain)))
    if family == "swift":
        k, epsilon_0, n = parameters
        return cast(FloatArray, k * np.power(epsilon_0 + strain, n))
    if family == "hockett_sherby":
        sigma_0, q, b, n = parameters
        return cast(FloatArray, sigma_0 + q * (1.0 - np.exp(-b * np.power(strain, n))))
    if family == "ghosh":
        k, epsilon_0, delta = parameters
        if np.any(strain >= epsilon_0):
            raise ValueError("ghosh domain")
        return cast(FloatArray, k * np.power(epsilon_0 - strain, -delta))
    raise AssertionError(f"unknown fit family {family}")


def _fit_jacobian(family: str, parameters: FloatArray, strain: FloatArray) -> FloatArray:
    if family == "voce":
        _, q, b = parameters
        exponential = np.exp(-b * strain)
        return np.column_stack((np.ones_like(strain), 1.0 - exponential, q * strain * exponential))
    if family == "swift":
        k, epsilon_0, n = parameters
        base = epsilon_0 + strain
        stress = k * np.power(base, n)
        return np.column_stack(
            (np.power(base, n), k * n * np.power(base, n - 1.0), stress * np.log(base))
        )
    if family == "hockett_sherby":
        _, q, b, n = parameters
        strain_power = np.power(strain, n)
        exponential = np.exp(-b * strain_power)
        logarithm = np.zeros_like(strain)
        positive = strain > 0
        logarithm[positive] = np.log(strain[positive])
        return np.column_stack(
            (
                np.ones_like(strain),
                1.0 - exponential,
                q * strain_power * exponential,
                q * b * strain_power * logarithm * exponential,
            )
        )
    if family == "ghosh":
        k, epsilon_0, delta = parameters
        base = epsilon_0 - strain
        stress = k * np.power(base, -delta)
        return np.column_stack(
            (
                np.power(base, -delta),
                -k * delta * np.power(base, -delta - 1.0),
                -stress * np.log(base),
            )
        )
    raise AssertionError(f"unknown fit family {family}")


def _ghosh_public_jacobian(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    k, epsilon_0, n, p = parameters
    base = epsilon_0 - strain
    exponent = n - p
    stress = k * np.power(base, exponent)
    return np.column_stack(
        (
            np.power(base, exponent),
            k * exponent * np.power(base, exponent - 1.0),
            stress * np.log(base),
            -stress * np.log(base),
        )
    )


def _scaled_rank(jacobian: FloatArray, parameters: FloatArray, units: list[str]) -> int:
    floors = np.array([1.0 if unit == "Pa" else 1e-12 for unit in units])
    scales = np.maximum(np.abs(parameters), floors)
    scaled = jacobian / 100e6 * scales
    singular_values = np.linalg.svd(scaled, compute_uv=False)
    tolerance = max(scaled.shape) * np.finfo(np.float64).eps * singular_values[0]
    return int(np.sum(singular_values > tolerance))


def _assert_tolerance(
    actual: float, expected: float, tolerance: dict[str, Any], absolute_key: str
) -> None:
    absolute = float(tolerance[absolute_key])
    relative = float(tolerance["relative"])
    assert abs(actual - expected) <= max(absolute, relative * abs(expected))


def _independent_option_error(options: dict[str, Any]) -> str | None:
    if options.get("equation_contract") != "altair-material-modeler-2025-v1":
        return "equation_contract"
    for key in ("plastic_strain_quantity", "stress_quantity"):
        if not isinstance(options.get(key), str) or not options[key]:
            return key
    families = options.get("families")
    if (
        not isinstance(families, list)
        or not 2 <= len(families) <= 4
        or len(set(families)) != len(families)
        or any(item not in {"voce", "swift", "hockett_sherby", "ghosh"} for item in families)
    ):
        return "families"
    if (
        options.get("primary_family") not in families
        or options.get("secondary_family") not in families
    ):
        return "selected candidates"
    numeric = (
        "fit_minimum_strain",
        "fit_maximum_strain",
        "extrapolation_maximum_strain",
        "primary_weight",
        "normalization_stress_pa",
    )
    if any(
        isinstance(options.get(key), bool)
        or not isinstance(options.get(key), int | float)
        or not math.isfinite(float(options[key]))
        for key in numeric
    ):
        return "numeric options"
    minimum = float(options["fit_minimum_strain"])
    maximum = float(options["fit_maximum_strain"])
    extrapolation = float(options["extrapolation_maximum_strain"])
    if not 0 <= minimum < maximum < extrapolation <= 5:
        return "strain domains"
    if not 0 <= float(options["primary_weight"]) <= 1:
        return "weight"
    if float(options["normalization_stress_pa"]) <= 0:
        return "normalization"
    output_points = options.get("output_point_count")
    if isinstance(output_points, bool) or not isinstance(output_points, int):
        return "output_point_count"
    if not 21 <= output_points <= 501:
        return "output_point_count"
    evaluations = options.get("maximum_function_evaluations")
    if isinstance(evaluations, bool) or not isinstance(evaluations, int):
        return "maximum_function_evaluations"
    if not 50 <= evaluations <= 100000:
        return "maximum_function_evaluations"
    selection_reason = options.get("selection_reason")
    if selection_reason is not None and (
        not isinstance(selection_reason, str)
        or not selection_reason.strip()
        or len(selection_reason) > 500
    ):
        return "selection_reason"
    return None


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def _tamper(value: dict[str, Any], path: str) -> None:
    parts = path.split(".")
    current: dict[str, Any] = value
    for part in parts[:-1]:
        current = cast(dict[str, Any], current[part])
    key = parts[-1]
    old = current[key]
    if isinstance(old, bool):
        current[key] = not old
    elif isinstance(old, str):
        current[key] = f"{old}-tampered"
    elif isinstance(old, int | float):
        current[key] = old + 0.125
    elif isinstance(old, list):
        current[key] = [*old, "tampered"]
    else:
        raise AssertionError(f"unsupported tamper target {path}")


def test_manifest_digest_provenance_and_reference_values_are_independent() -> None:
    fixture_path, manifest_path = _reference_paths()
    test_source = Path(__file__).read_text(encoding="utf-8")
    production_module = ".".join(
        ("cmp", "modules", "processing", "domain", "metal_hardening")
    )
    assert production_module not in test_source
    fixture_bytes = fixture_path.read_bytes()
    fixture = cast(dict[str, Any], json.loads(fixture_bytes))
    manifest = cast(dict[str, Any], yaml.safe_load(manifest_path.read_text(encoding="utf-8")))

    assert hashlib.sha256(fixture_bytes).hexdigest() == manifest["fixture"]["digest"]["value"]
    assert manifest["fixture"]["id"] == fixture["fixture_id"]
    assert manifest["fixture"]["classification"] == fixture["classification"]
    assert fixture["generation"]["production_functions_called"] == []
    assert fixture["reference_case_count"] == 4
    assert fixture["curve_point_row_count"] == 24
    assert [item["id"] for item in manifest["sources"]] == [
        item["id"] for item in fixture["source_catalog"]
    ]

    tolerances = cast(dict[str, dict[str, Any]], fixture["tolerances"])
    rows = 0
    for family_case in cast(list[dict[str, Any]], fixture["families"]):
        family = cast(str, family_case["id"])
        parameters = {
            cast(str, item["symbol"]): float(item["value"])
            for item in cast(list[dict[str, Any]], family_case["public_parameters"])
        }
        expected_curve = cast(list[dict[str, Any]], family_case["expected_curve"])
        rows += len(expected_curve)
        for point in expected_curve:
            strain = float(point["plastic_strain"])
            stress, tangent = _public_stress_and_tangent(family, parameters, strain)
            _assert_tolerance(
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
                _assert_tolerance(
                    tangent,
                    float(point["tangent_pa"]),
                    tolerances[cast(str, point["tangent_tolerance_id"])],
                    "absolute_pa",
                )
                if strain > 0:
                    step = min(1e-6, strain / 4)
                    plus = _public_stress_and_tangent(family, parameters, strain + step)[0]
                    minus = _public_stress_and_tangent(family, parameters, strain - step)[0]
                    finite_difference = (plus - minus) / (2 * step)
                    assert finite_difference == pytest.approx(tangent, rel=2e-6)

    assert rows == fixture["curve_point_row_count"]


def test_objective_sign_aggregation_and_noiseless_case() -> None:
    fixture = _fixture()
    objective = cast(dict[str, Any], fixture["objective_contract"])
    tolerances = cast(dict[str, dict[str, Any]], fixture["tolerances"])
    perfect = cast(dict[str, Any], objective["perfect_noiseless_case"])
    assert perfect["expected_residual_pa"] == [0, 0, 0, 0, 0, 0]
    assert perfect["expected_sum_squared_normalized_residuals"] == 0

    perturbation = cast(dict[str, Any], objective["deterministic_perturbation_case"])
    residual = np.asarray(perturbation["expected_residual_pa"], dtype=np.float64)
    observed_offset = np.asarray(perturbation["observed_offset_pa"], dtype=np.float64)
    assert residual == pytest.approx(-observed_offset)
    normalization = float(objective["normalization_stress_pa"])
    sum_squared = float(np.sum(np.square(residual / normalization)))
    rmse = float(np.sqrt(np.mean(np.square(residual))))
    tolerance = tolerances["objective_f64"]
    _assert_tolerance(
        sum_squared,
        float(perturbation["expected_sum_squared_normalized_residuals"]),
        tolerance,
        "absolute",
    )
    _assert_tolerance(
        0.5 * sum_squared,
        float(perturbation["expected_scipy_cost_equivalent"]),
        tolerance,
        "absolute",
    )
    assert rmse == pytest.approx(float(perturbation["expected_rmse_pa"]), rel=5e-13)


def test_scaled_jacobian_rank_and_fixture_only_parameter_recovery() -> None:
    fixture = _fixture()
    family_cases = {item["id"]: item for item in cast(list[dict[str, Any]], fixture["families"])}
    recovery = cast(
        dict[str, dict[str, Any]], fixture["fixture_only_recovery_contract"]["families"]
    )
    criteria = fixture["tolerances"]["identifiable_parameter_recovery_fixture_only"]

    for family, contract in recovery.items():
        expected = np.asarray(contract["expected"], dtype=np.float64)
        initial = np.asarray(contract["initial"], dtype=np.float64)
        lower = np.asarray(contract["lower"], dtype=np.float64)
        upper = np.asarray(contract["upper"], dtype=np.float64)
        units = cast(list[str], contract["parameter_units"])
        curve = cast(list[dict[str, Any]], family_cases[family]["expected_curve"])
        strain = np.asarray([item["plastic_strain"] for item in curve], dtype=np.float64)
        stress = np.asarray([item["stress_pa"] for item in curve], dtype=np.float64)
        jacobian = _fit_jacobian(family, expected, strain)
        assert _scaled_rank(jacobian, expected, units) == contract["expected_scaled_jacobian_rank"]

        result = least_squares(
            lambda parameters, family=family, strain=strain, stress=stress: (
                _fit_response(family, parameters, strain) - stress
            )
            / 100e6,
            initial,
            bounds=(lower, upper),
            method="trf",
            x_scale="jac",
            ftol=1e-13,
            xtol=1e-13,
            gtol=1e-13,
            max_nfev=10000,
        )
        assert result.success
        for actual, reference, unit in zip(result.x, expected, units, strict=True):
            absolute = (
                criteria["stress_parameter_absolute_pa"]
                if unit == "Pa"
                else criteria["dimensionless_parameter_absolute"]
            )
            assert abs(actual - reference) <= max(
                float(absolute), float(criteria["relative"]) * abs(reference)
            )

    ghosh_case = family_cases["ghosh"]
    public = np.asarray(
        [item["value"] for item in ghosh_case["public_parameters"]], dtype=np.float64
    )
    strain = np.asarray(
        [item["plastic_strain"] for item in ghosh_case["expected_curve"]], dtype=np.float64
    )
    assert (
        _scaled_rank(_ghosh_public_jacobian(public, strain), public, ["Pa", "1", "1", "1"])
        == ghosh_case["identifiability"]["expected_public_rank"]
    )


def test_boundary_rank_and_formula_limits() -> None:
    strain = np.asarray([0, 0.01, 0.05, 0.1, 0.2, 0.4], dtype=np.float64)
    boundary = [
        ("voce", np.asarray([300e6, 0, 11.0]), ["Pa", "Pa", "1"], 2),
        ("swift", np.asarray([650e6, 0.015, 0.0]), ["Pa", "1", "1"], 2),
        ("hockett_sherby", np.asarray([310e6, 0, 8.5, 0.72]), ["Pa", "Pa", "1", "1"], 2),
        ("ghosh", np.asarray([420e6, 0.8, 0.0]), ["Pa", "1", "1"], 2),
    ]
    for family, parameters, units, rank in boundary:
        assert _scaled_rank(_fit_jacobian(family, parameters, strain), parameters, units) == rank

    assert _fit_response("voce", np.asarray([300e6, 220e6, 11.0]), np.asarray([100.0]))[
        0
    ] == pytest.approx(520e6)
    assert _fit_response(
        "hockett_sherby", np.asarray([310e6, 260e6, 8.5, 0.72]), np.asarray([100.0])
    )[0] == pytest.approx(570e6)
    assert _fit_response("ghosh", np.asarray([420e6, 0.8, 0.0]), strain) == pytest.approx(
        np.full(6, 420e6)
    )
    with pytest.raises(ValueError, match="ghosh domain"):
        _fit_response("ghosh", np.asarray([420e6, 0.8, 0.24]), np.asarray([0.8]))


def test_option_normal_boundary_and_error_cases() -> None:
    contract = cast(dict[str, Any], _fixture()["option_validation_contract"])
    base = cast(dict[str, Any], contract["base_options"])
    assert _independent_option_error(base) is None
    for case in cast(list[dict[str, Any]], contract["boundary_cases"]):
        options = {**base, **cast(dict[str, Any], case["patch"])}
        assert _independent_option_error(options) is None, case["id"]
    for case in cast(list[dict[str, Any]], contract["error_cases"]):
        options = {**base, **cast(dict[str, Any], case.get("patch", {}))}
        for key in cast(list[str], case.get("remove", [])):
            options.pop(key, None)
        assert _independent_option_error(options) == case["expected_error"], case["id"]


def test_declared_metamorphic_relations() -> None:
    fixture = _fixture()
    assert [item["id"] for item in fixture["metamorphic_contract"]] == [
        "stress_and_normalization_scale",
        "ghosh_common_exponent_shift",
        "blend_commutativity",
        "candidate_order_invariance",
        "fit_subset_invariance",
        "nested_grid_common_coordinates",
    ]

    residual = np.asarray([-1000, 2000, -3000, 4000, -5000, 6000], dtype=np.float64)
    assert np.sum(np.square(residual / 100e6)) == pytest.approx(
        np.sum(np.square((17 * residual) / (17 * 100e6)))
    )
    parameters = {"K": 420e6, "epsilon_0": 0.8, "n": 0.18, "p": 0.42}
    shifted = {**parameters, "n": 0.31, "p": 0.55}
    for strain in (0.0, 0.1, 0.4):
        assert _public_stress_and_tangent("ghosh", parameters, strain) == pytest.approx(
            _public_stress_and_tangent("ghosh", shifted, strain)
        )

    grid = np.linspace(0, 0.4, 5)
    voce = _fit_response("voce", np.asarray([300e6, 220e6, 11.0]), grid)
    swift = _fit_response("swift", np.asarray([650e6, 0.015, 0.24]), grid)
    assert 0.3 * voce + 0.7 * swift == pytest.approx(0.7 * swift + 0.3 * voce)
    ordered = {
        family: _fit_response(family, np.asarray(contract["expected"]), grid)
        for family, contract in fixture["fixture_only_recovery_contract"]["families"].items()
    }
    reversed_order = {
        family: _fit_response(family, np.asarray(contract["expected"]), grid)
        for family, contract in reversed(
            list(fixture["fixture_only_recovery_contract"]["families"].items())
        )
    }
    for family in ordered:
        assert ordered[family] == pytest.approx(reversed_order[family])

    observations = np.asarray([1, 2, 3, 4, 5], dtype=np.float64)
    predictions = np.asarray([1.1, 1.9, 3.2, 100, -100], dtype=np.float64)
    fit_mask = np.asarray([True, True, True, False, False])
    objective = float(np.sum(np.square(predictions[fit_mask] - observations[fit_mask])))
    assert objective == pytest.approx(float(np.sum(np.square(predictions[:3] - observations[:3]))))
    coarse = np.linspace(0, 0.4, 5)
    fine = np.linspace(0, 0.4, 9)
    assert _fit_response("voce", np.asarray([300e6, 220e6, 11.0]), coarse) == pytest.approx(
        _fit_response("voce", np.asarray([300e6, 220e6, 11.0]), fine)[::2]
    )


def test_canonical_snapshot_reload_and_tamper_rejection() -> None:
    contract = cast(dict[str, Any], _fixture()["persistence_contract"])
    snapshot = cast(dict[str, Any], contract["snapshot"])
    canonical = _canonical_bytes(snapshot)
    digest = hashlib.sha256(canonical).hexdigest()
    assert digest == contract["canonical_snapshot_sha256"]
    assert json.loads(canonical) == snapshot
    assert snapshot["ghosh_fit_evidence"]["parameter_names"] == [
        "k_pa",
        "epsilon_0",
        "delta_p_minus_n",
    ]
    assert not {"n", "p", "d_pa"}.intersection(snapshot["ghosh_fit_evidence"]["parameter_names"])

    for path in cast(list[str], contract["tamper_paths"]):
        tampered = copy.deepcopy(snapshot)
        _tamper(tampered, path)
        assert hashlib.sha256(_canonical_bytes(tampered)).hexdigest() != digest, path
