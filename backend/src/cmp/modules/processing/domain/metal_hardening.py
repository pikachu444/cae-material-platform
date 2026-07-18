"""Public-equation metal hardening fit, comparison, and bounded extrapolation.

The formulas are independent reference implementations.  They do not reproduce a proprietary
optimizer, parameter database, or solver mapping.  Every fit shares one normalized least-squares
objective and every extrapolated point is bounded by an explicit user option.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares  # type: ignore[import-untyped]

FloatArray = NDArray[np.float64]
Evaluator = Callable[[FloatArray, FloatArray], FloatArray]

HARDENING_FAMILIES = ("voce", "swift", "hockett_sherby", "ghosh")


class MetalHardeningError(ValueError):
    """A hardening fit or extrapolation request violates the explicit reference contract."""


@dataclass(frozen=True, slots=True)
class HardeningScalar:
    key: str
    quantity_semantics: str
    value: float
    unit: str


@dataclass(frozen=True, slots=True)
class HardeningFitResult:
    columns: dict[str, FloatArray]
    units: dict[str, str]
    diagnostics: tuple[str, ...]
    scalars: tuple[HardeningScalar, ...]


@dataclass(frozen=True, slots=True)
class _FamilyDefinition:
    parameter_names: tuple[str, ...]
    parameter_units: tuple[str, ...]
    evaluator: Evaluator


def _voce(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    sigma_0, q, b = parameters
    return cast(FloatArray, sigma_0 + q * (1.0 - np.exp(-b * strain)))


def _swift(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    k, epsilon_0, n = parameters
    return cast(FloatArray, k * np.power(epsilon_0 + strain, n))


def _hockett_sherby(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    sigma_0, q, b, n = parameters
    return cast(FloatArray, sigma_0 + q * (1.0 - np.exp(-b * np.power(strain, n))))


def _ghosh(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    k, epsilon_0, n, d = parameters
    return cast(FloatArray, k * np.power(epsilon_0 + strain, n) - d)


_FAMILIES = {
    "voce": _FamilyDefinition(
        ("sigma_0_pa", "q_pa", "b"), ("Pa", "Pa", "1"), _voce
    ),
    "swift": _FamilyDefinition(("k_pa", "epsilon_0", "n"), ("Pa", "1", "1"), _swift),
    "hockett_sherby": _FamilyDefinition(
        ("sigma_0_pa", "q_pa", "b", "n"), ("Pa", "Pa", "1", "1"), _hockett_sherby
    ),
    "ghosh": _FamilyDefinition(
        ("k_pa", "epsilon_0", "n", "d_pa"), ("Pa", "1", "1", "Pa"), _ghosh
    ),
}


def evaluate_hardening_family(
    family: str, parameters: tuple[float, ...], plastic_strain: FloatArray
) -> FloatArray:
    """Evaluate one declared public hardening equation for fixtures and downstream reuse."""

    definition = _FAMILIES.get(family)
    if definition is None:
        raise MetalHardeningError(f"unsupported hardening family {family}")
    values = np.asarray(parameters, dtype=np.float64)
    if len(values) != len(definition.parameter_names):
        raise MetalHardeningError(f"{family} requires {len(definition.parameter_names)} parameters")
    if np.any(~np.isfinite(values)) or np.any(values < 0.0):
        raise MetalHardeningError("hardening parameters must be finite and non-negative")
    strain = np.asarray(plastic_strain, dtype=np.float64)
    if np.any(~np.isfinite(strain)) or np.any(strain < 0.0):
        raise MetalHardeningError("plastic strain must be finite and non-negative")
    response = definition.evaluator(values, strain)
    if np.any(~np.isfinite(response)):
        raise MetalHardeningError(f"{family} produced a non-finite response")
    return response


def _fit_bounds(
    family: str, strain: FloatArray, stress: FloatArray
) -> tuple[FloatArray, FloatArray, FloatArray]:
    first = max(float(stress[0]), 1.0)
    maximum = max(float(np.max(stress)), first)
    span = max(maximum - first, 0.05 * maximum, 1.0)
    x_max = max(float(strain[-1]), 1e-6)
    if family == "voce":
        return (
            np.array([0.1 * first, 0.0, 1e-6]),
            np.array([first, span, min(10.0 / x_max, 100.0)]),
            np.array([2.0 * maximum, 10.0 * maximum, 1_000.0]),
        )
    if family == "swift":
        n = 0.2
        epsilon_0 = min(max(0.1 * x_max, 1e-5), 0.1)
        k = maximum / ((epsilon_0 + x_max) ** n)
        return (
            np.array([0.01 * first, 1e-8, 0.01]),
            np.array([k, epsilon_0, n]),
            np.array([100.0 * maximum, 1.0, 2.0]),
        )
    if family == "hockett_sherby":
        return (
            np.array([0.1 * first, 0.0, 1e-6, 0.05]),
            np.array([first, span, min(10.0 / x_max, 100.0), 0.8]),
            np.array([2.0 * maximum, 20.0 * maximum, 1_000.0, 2.0]),
        )
    if family == "ghosh":
        n = 0.2
        epsilon_0 = min(max(0.1 * x_max, 1e-5), 0.1)
        k = maximum / ((epsilon_0 + x_max) ** n)
        return (
            np.array([0.01 * first, 1e-8, 0.01, 0.0]),
            np.array([k, epsilon_0, n, 0.05 * first]),
            np.array([100.0 * maximum, 1.0, 2.0, 2.0 * maximum]),
        )
    raise MetalHardeningError(f"unsupported hardening family {family}")


def _fit_family(
    family: str,
    strain: FloatArray,
    stress: FloatArray,
    normalization_stress_pa: float,
    maximum_function_evaluations: int,
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray, float, float, int, str]:
    definition = _FAMILIES[family]
    lower, initial, upper = _fit_bounds(family, strain, stress)
    optimized = least_squares(
        lambda parameters: (
            definition.evaluator(parameters, strain) - stress
        )
        / normalization_stress_pa,
        initial,
        bounds=(lower, upper),
        method="trf",
        x_scale="jac",
        max_nfev=maximum_function_evaluations,
        ftol=1e-10,
        xtol=1e-10,
        gtol=1e-10,
    )
    if not optimized.success or np.any(~np.isfinite(optimized.x)):
        raise MetalHardeningError(f"{family} fitting failed: {optimized.message}")
    predicted = definition.evaluator(optimized.x, strain)
    residual = predicted - stress
    rmse = float(np.sqrt(np.mean(np.square(residual))))
    relative_rmse = rmse / max(float(np.mean(stress)), 1.0)
    return (
        lower,
        initial,
        optimized.x,
        upper,
        rmse,
        relative_rmse,
        int(optimized.nfev),
        str(optimized.message),
    )


def _number(options: dict[str, Any], key: str) -> float:
    value = options.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise MetalHardeningError(f"option {key} must be a finite number")
    return float(value)


def fit_hardening_candidates(
    columns: dict[str, FloatArray], units: dict[str, str], options: dict[str, Any]
) -> HardeningFitResult:
    strain_key = options.get("plastic_strain_quantity")
    stress_key = options.get("stress_quantity")
    if not isinstance(strain_key, str) or strain_key not in columns:
        raise MetalHardeningError("plastic_strain_quantity is not mapped")
    if not isinstance(stress_key, str) or stress_key not in columns:
        raise MetalHardeningError("stress_quantity is not mapped")
    if units[strain_key] != "1" or units[stress_key] != "Pa":
        raise MetalHardeningError(
            "metal hardening requires normalized plastic strain unit 1 and stress unit Pa"
        )
    requested = options.get("families")
    if (
        not isinstance(requested, list)
        or not 2 <= len(requested) <= len(HARDENING_FAMILIES)
        or any(item not in HARDENING_FAMILIES for item in requested)
        or len(set(requested)) != len(requested)
    ):
        raise MetalHardeningError("families must contain 2..4 unique supported family IDs")
    families = tuple(str(item) for item in requested)
    primary = options.get("primary_family")
    secondary = options.get("secondary_family")
    if primary not in families or secondary not in families:
        raise MetalHardeningError("primary and secondary families must be selected candidates")
    minimum = _number(options, "fit_minimum_strain")
    maximum = _number(options, "fit_maximum_strain")
    extrapolation_maximum = _number(options, "extrapolation_maximum_strain")
    primary_weight = _number(options, "primary_weight")
    normalization = _number(options, "normalization_stress_pa")
    point_count_value = options.get("output_point_count")
    maximum_evaluations_value = options.get("maximum_function_evaluations")
    if isinstance(point_count_value, bool) or not isinstance(point_count_value, int):
        raise MetalHardeningError("output_point_count must be an integer")
    if isinstance(maximum_evaluations_value, bool) or not isinstance(
        maximum_evaluations_value, int
    ):
        raise MetalHardeningError("maximum_function_evaluations must be an integer")
    if not 0.0 <= minimum < maximum < extrapolation_maximum <= 5.0:
        raise MetalHardeningError(
            "strain domains must satisfy 0 <= fit minimum < fit maximum < "
            "extrapolation maximum <= 5"
        )
    if not 0.0 <= primary_weight <= 1.0 or normalization <= 0.0:
        raise MetalHardeningError("weight must be in [0,1] and normalization stress positive")
    if not 21 <= point_count_value <= 501 or not 50 <= maximum_evaluations_value <= 100_000:
        raise MetalHardeningError("output points or maximum evaluations are outside bounded limits")

    plastic_strain = columns[strain_key]
    stress = columns[stress_key]
    if (
        np.any(~np.isfinite(plastic_strain))
        or np.any(~np.isfinite(stress))
        or np.any(np.diff(plastic_strain) <= 0.0)
        or np.any(plastic_strain < 0.0)
        or np.any(stress <= 0.0)
    ):
        raise MetalHardeningError(
            "hardening observations must be finite, positive-stress and strictly ordered"
        )
    mask = (plastic_strain >= minimum) & (plastic_strain <= maximum)
    fit_strain = plastic_strain[mask]
    fit_stress = stress[mask]
    if len(fit_strain) < 5:
        raise MetalHardeningError("hardening fit domain requires at least five observed points")

    grid = np.linspace(0.0, extrapolation_maximum, point_count_value)
    result_columns: dict[str, FloatArray] = {strain_key: grid}
    result_units = {strain_key: "1"}
    diagnostics: list[str] = [
        f"fit observed domain [{minimum}, {maximum}] with {len(fit_strain)} points",
        f"extrapolated domain ({maximum}, {extrapolation_maximum}] is not observed",
        "objective=uniform normalized predicted-minus-observed least squares",
    ]
    scalars: list[HardeningScalar] = []
    responses: dict[str, FloatArray] = {}
    for family in families:
        lower, initial, parameters, upper, rmse, relative_rmse, nfev, message = _fit_family(
            family,
            fit_strain,
            fit_stress,
            normalization,
            maximum_evaluations_value,
        )
        response = _FAMILIES[family].evaluator(parameters, grid)
        if np.any(~np.isfinite(response)) or np.any(response <= 0.0):
            raise MetalHardeningError(f"{family} extrapolation produced a non-positive response")
        if np.min(np.diff(response)) < -max(float(np.max(response)) * 1e-10, 1e-3):
            raise MetalHardeningError(f"{family} extrapolation is not monotonic non-decreasing")
        quantity = f"stress.hardening.{family}"
        responses[family] = response
        result_columns[quantity] = response
        result_units[quantity] = "Pa"
        diagnostics.append(
            f"{family}: rmse={rmse} Pa, relative_rmse={relative_rmse}, nfev={nfev}, {message}"
        )
        scalars.extend(
            (
                HardeningScalar(
                    f"{family}.rmse_pa", "statistics.rmse", rmse, "Pa"
                ),
                HardeningScalar(
                    f"{family}.relative_rmse", "statistics.relative_rmse", relative_rmse, "1"
                ),
            )
        )
        definition = _FAMILIES[family]
        for name, unit, lower_value, initial_value, value, upper_value in zip(
            definition.parameter_names,
            definition.parameter_units,
            lower,
            initial,
            parameters,
            upper,
            strict=True,
        ):
            scalars.extend(
                (
                    HardeningScalar(
                        f"{family}.parameter.{name}.lower",
                        f"model.parameter.bound.lower.{name}",
                        float(lower_value),
                        unit,
                    ),
                    HardeningScalar(
                        f"{family}.parameter.{name}.initial",
                        f"model.parameter.initial.{name}",
                        float(initial_value),
                        unit,
                    ),
                    HardeningScalar(
                        f"{family}.parameter.{name}",
                        f"model.parameter.{name}",
                        float(value),
                        unit,
                    ),
                    HardeningScalar(
                        f"{family}.parameter.{name}.upper",
                        f"model.parameter.bound.upper.{name}",
                        float(upper_value),
                        unit,
                    ),
                )
            )

    selected = primary_weight * responses[str(primary)] + (1.0 - primary_weight) * responses[
        str(secondary)
    ]
    result_columns["stress.hardening.selected"] = selected
    result_units["stress.hardening.selected"] = "Pa"
    scalars.extend(
        (
            HardeningScalar(
                "selection.primary_weight", "selection.weight.primary", primary_weight, "1"
            ),
            HardeningScalar(
                "fit.observed_maximum_strain", "strain.domain.observed.maximum", maximum, "1"
            ),
            HardeningScalar(
                "fit.extrapolation_maximum_strain",
                "strain.domain.extrapolated.maximum",
                extrapolation_maximum,
                "1",
            ),
        )
    )
    diagnostics.append(
        f"selected={primary_weight}*{primary}+{1.0 - primary_weight}*{secondary}"
    )
    return HardeningFitResult(
        result_columns,
        result_units,
        tuple(diagnostics),
        tuple(scalars),
    )
