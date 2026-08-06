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
HARDENING_EQUATION_CONTRACT = "altair-material-modeler-2025-v1"


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
    # The legacy preview contract only exposed ``columns``.  Fit evidence is kept in
    # typed side-car fields so the response/residual/tangent arrays can retain their
    # native domains (the response grid and the observed fit points respectively).
    candidates: tuple[HardeningCandidateEvidence, ...] = ()
    objective_contract: str = "normalized_predicted_minus_observed_sum_squares_v1"


@dataclass(frozen=True, slots=True)
class HardeningCandidateEvidence:
    """One deterministic bounded fit and its server-produced evidence."""

    family: str
    response: FloatArray
    residual: FloatArray
    tangent: FloatArray
    parameter_names: tuple[str, ...]
    parameter_units: tuple[str, ...]
    lower: FloatArray
    initial: FloatArray
    fitted: FloatArray
    upper: FloatArray
    rmse_pa: float
    relative_rmse: float
    objective: float
    scipy_cost: float
    convergence: bool
    nfev: int
    active_bound: tuple[str, ...]
    jacobian_rank: int
    jacobian_tolerance: float
    jacobian_condition: float | None
    identifiability: str
    uncertainty: str = "not_provided"
    objective_history: tuple[float, ...] = ()
    # Keep SciPy's optimizer status/message alongside the boolean convergence
    # flag.  The status is diagnostic evidence, not a second success policy.
    optimizer_status: int = 0
    optimizer_message: str = ""


@dataclass(frozen=True, slots=True)
class _FamilyDefinition:
    parameter_names: tuple[str, ...]
    parameter_units: tuple[str, ...]
    evaluator: Evaluator
    tangent: Evaluator
    public_parameter_names: tuple[str, ...] | None = None
    public_evaluator: Evaluator | None = None
    public_tangent: Evaluator | None = None


def _voce(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    sigma_0, q, b = parameters
    return cast(FloatArray, sigma_0 + q * (1.0 - np.exp(-b * strain)))


def _swift(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    k, epsilon_0, n = parameters
    return cast(FloatArray, k * np.power(epsilon_0 + strain, n))


def _hockett_sherby(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    sigma_0, q, b, n = parameters
    return cast(FloatArray, sigma_0 + q * (1.0 - np.exp(-b * np.power(strain, n))))


def _ghosh_public(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    k, epsilon_0, n, p = parameters
    return cast(FloatArray, k * np.power(epsilon_0 - strain, n - p))


def _ghosh_fit(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    k, epsilon_0, delta_p_minus_n = parameters
    return cast(FloatArray, k * np.power(epsilon_0 - strain, -delta_p_minus_n))


def _tangent_voce(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    _sigma_0, q, b = parameters
    return cast(FloatArray, q * b * np.exp(-b * strain))


def _tangent_swift(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    k, epsilon_0, n = parameters
    base = epsilon_0 + strain
    return cast(FloatArray, k * n * np.power(base, n - 1.0))


def _tangent_hockett_sherby(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    _sigma_0, q, b, n = parameters
    result = np.empty_like(strain, dtype=np.float64)
    zero = strain == 0.0
    result[zero] = np.inf if q > 0.0 and b > 0.0 and n < 1.0 else 0.0
    positive = ~zero
    if np.any(positive):
        x = strain[positive]
        x_power = np.power(x, n)
        result[positive] = q * b * n * np.power(x, n - 1.0) * np.exp(-b * x_power)
    return result


def _tangent_ghosh_public(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    k, epsilon_0, n, p = parameters
    base = epsilon_0 - strain
    return cast(FloatArray, k * (p - n) * np.power(base, n - p - 1.0))


def _tangent_ghosh_fit(parameters: FloatArray, strain: FloatArray) -> FloatArray:
    k, epsilon_0, delta_p_minus_n = parameters
    base = epsilon_0 - strain
    return cast(FloatArray, k * delta_p_minus_n * np.power(base, -delta_p_minus_n - 1.0))


_FAMILIES = {
    "voce": _FamilyDefinition(
        ("sigma_0_pa", "q_pa", "b"), ("Pa", "Pa", "1"), _voce, _tangent_voce
    ),
    "swift": _FamilyDefinition(
        ("k_pa", "epsilon_0", "n"), ("Pa", "1", "1"), _swift, _tangent_swift
    ),
    "hockett_sherby": _FamilyDefinition(
        ("sigma_0_pa", "q_pa", "b", "n"),
        ("Pa", "Pa", "1", "1"),
        _hockett_sherby,
        _tangent_hockett_sherby,
    ),
    "ghosh": _FamilyDefinition(
        ("k_pa", "epsilon_0", "delta_p_minus_n"),
        ("Pa", "1", "1"),
        _ghosh_fit,
        _tangent_ghosh_fit,
        ("k_pa", "epsilon_0", "n", "p"),
        _ghosh_public,
        _tangent_ghosh_public,
    ),
}


def evaluate_hardening_family(
    family: str, parameters: tuple[float, ...], plastic_strain: FloatArray
) -> FloatArray:
    """Evaluate one declared public hardening equation for fixtures and downstream reuse."""

    definition = _FAMILIES.get(family)
    if definition is None:
        raise MetalHardeningError(f"unsupported hardening family {family}")
    parameter_names = definition.public_parameter_names or definition.parameter_names
    evaluator = definition.public_evaluator or definition.evaluator
    values = np.asarray(parameters, dtype=np.float64)
    if len(values) != len(parameter_names):
        raise MetalHardeningError(f"{family} requires {len(parameter_names)} parameters")
    if np.any(~np.isfinite(values)) or np.any(values < 0.0):
        raise MetalHardeningError("hardening parameters must be finite and non-negative")
    strain = np.asarray(plastic_strain, dtype=np.float64)
    if np.any(~np.isfinite(strain)) or np.any(strain < 0.0):
        raise MetalHardeningError("plastic strain must be finite and non-negative")
    if family == "ghosh" and np.any(strain >= float(values[1])):
        raise MetalHardeningError("ghosh requires plastic strain < epsilon_0")
    response = evaluator(values, strain)
    if np.any(~np.isfinite(response)):
        raise MetalHardeningError(f"{family} produced a non-finite response")
    return response


def evaluate_hardening_tangent(
    family: str, parameters: tuple[float, ...], plastic_strain: FloatArray
) -> FloatArray:
    """Evaluate the analytical tangent for one public hardening equation.

    A Hockett--Sherby tangent at zero strain is a genuine positive-infinity limit for
    ``0 < n < 1``.  It is intentionally returned as ``inf`` instead of being silently
    replaced by an arbitrary finite value; fit persistence records that limit in its
    diagnostic metadata rather than serializing a non-finite JSON number.
    """

    definition = _FAMILIES.get(family)
    if definition is None:
        raise MetalHardeningError(f"unsupported hardening family {family}")
    parameter_names = definition.public_parameter_names or definition.parameter_names
    evaluator = definition.public_tangent or definition.tangent
    values = np.asarray(parameters, dtype=np.float64)
    if len(values) != len(parameter_names):
        raise MetalHardeningError(f"{family} requires {len(parameter_names)} parameters")
    if np.any(~np.isfinite(values)) or np.any(values < 0.0):
        raise MetalHardeningError("hardening parameters must be finite and non-negative")
    strain = np.asarray(plastic_strain, dtype=np.float64)
    if np.any(~np.isfinite(strain)) or np.any(strain < 0.0):
        raise MetalHardeningError("plastic strain must be finite and non-negative")
    if family == "ghosh" and np.any(strain >= float(values[1])):
        raise MetalHardeningError("ghosh requires plastic strain < epsilon_0")
    tangent = evaluator(values, strain)
    # Infinite is accepted only for the documented Hockett--Sherby limit.
    if np.any(np.isnan(tangent)) or np.any(np.isneginf(tangent)) or np.any(
        np.isfinite(tangent) & (tangent < 0.0)
    ):
        raise MetalHardeningError(f"{family} produced an invalid analytical tangent")
    return tangent


def hardening_family_jacobian(
    family: str, parameters: FloatArray, plastic_strain: FloatArray
) -> FloatArray:
    """Return the closed-form stress Jacobian in the stored fit parameterization."""

    definition = _FAMILIES.get(family)
    if definition is None:
        raise MetalHardeningError(f"unsupported hardening family {family}")
    values = np.asarray(parameters, dtype=np.float64)
    strain = np.asarray(plastic_strain, dtype=np.float64)
    if len(values) != len(definition.parameter_names):
        raise MetalHardeningError(f"{family} requires {len(definition.parameter_names)} parameters")
    if np.any(~np.isfinite(values)) or np.any(values < 0.0):
        raise MetalHardeningError("hardening parameters must be finite and non-negative")
    if np.any(~np.isfinite(strain)) or np.any(strain < 0.0):
        raise MetalHardeningError("plastic strain must be finite and non-negative")
    if family == "voce":
        _sigma_0, q, b = values
        e = np.exp(-b * strain)
        return np.column_stack((np.ones_like(strain), 1.0 - e, q * strain * e))
    if family == "swift":
        k, epsilon_0, n = values
        base = epsilon_0 + strain
        if np.any(base <= 0.0):
            raise MetalHardeningError("swift requires epsilon_0 + plastic strain > 0")
        stress = k * np.power(base, n)
        return np.column_stack(
            (np.power(base, n), k * n * np.power(base, n - 1.0), stress * np.log(base))
        )
    if family == "hockett_sherby":
        _sigma_0, q, b, n = values
        if np.any((strain == 0.0) & (n < 1.0)):
            # The stress Jacobian remains finite at zero; the tangent singularity does
            # not imply a singular parameter derivative for this evaluator.
            pass
        x_power = np.power(strain, n)
        e = np.exp(-b * x_power)
        logarithm = np.zeros_like(strain)
        positive = strain > 0.0
        logarithm[positive] = np.log(strain[positive])
        return np.column_stack(
            (np.ones_like(strain), 1.0 - e, q * x_power * e, q * b * x_power * logarithm * e)
        )
    if family == "ghosh":
        k, epsilon_0, delta = values
        base = epsilon_0 - strain
        if np.any(base <= 0.0):
            raise MetalHardeningError("ghosh requires plastic strain < epsilon_0")
        stress = k * np.power(base, -delta)
        return np.column_stack(
            (
                np.power(base, -delta),
                -k * delta * np.power(base, -delta - 1.0),
                -stress * np.log(base),
            )
        )
    raise MetalHardeningError(f"unsupported hardening family {family}")


def _fit_bounds(
    family: str,
    strain: FloatArray,
    stress: FloatArray,
    evaluation_maximum_strain: float,
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
        delta_p_minus_n = 0.2
        domain_margin = max(1e-8, 1e-6 * max(1.0, evaluation_maximum_strain))
        epsilon_0_lower = evaluation_maximum_strain + domain_margin
        epsilon_0 = max(
            1.5 * epsilon_0_lower,
            evaluation_maximum_strain + max(x_max, 0.1),
        )
        epsilon_0_upper = max(epsilon_0_lower + 10.0, 10.0 * epsilon_0)
        k = maximum * ((epsilon_0 - x_max) ** delta_p_minus_n)
        return (
            np.array([0.01 * first, epsilon_0_lower, 1e-6]),
            np.array([k, epsilon_0, delta_p_minus_n]),
            np.array([100.0 * maximum, epsilon_0_upper, 2.0]),
        )
    raise MetalHardeningError(f"unsupported hardening family {family}")


@dataclass(frozen=True, slots=True)
class _FittedFamily:
    lower: FloatArray
    initial: FloatArray
    fitted: FloatArray
    upper: FloatArray
    rmse_pa: float
    relative_rmse: float
    nfev: int
    message: str
    objective: float
    objective_history: tuple[float, ...]
    jacobian_rank: int
    jacobian_tolerance: float
    jacobian_condition: float | None
    active_bound: tuple[str, ...]
    convergence: bool
    optimizer_status: int
    optimizer_message: str


def _fit_family(
    family: str,
    strain: FloatArray,
    stress: FloatArray,
    normalization_stress_pa: float,
    maximum_function_evaluations: int,
    evaluation_maximum_strain: float,
) -> _FittedFamily:
    definition = _FAMILIES[family]
    lower, initial, upper = _fit_bounds(family, strain, stress, evaluation_maximum_strain)
    objective_history: list[float] = []

    def residual(parameters: FloatArray) -> FloatArray:
        values = (definition.evaluator(parameters, strain) - stress) / normalization_stress_pa
        objective_history.append(float(np.sum(np.square(values))))
        return values

    optimized = least_squares(
        residual,
        initial,
        bounds=(lower, upper),
        method="trf",
        x_scale="jac",
        max_nfev=maximum_function_evaluations,
        ftol=1e-10,
        xtol=1e-10,
        gtol=1e-10,
    )
    if np.any(~np.isfinite(optimized.x)):
        raise MetalHardeningError(f"{family} fitting failed: {optimized.message}")
    predicted = definition.evaluator(optimized.x, strain)
    residual_values = predicted - stress
    rmse = float(np.sqrt(np.mean(np.square(residual_values))))
    relative_rmse = rmse / max(float(np.mean(stress)), 1.0)
    jacobian = hardening_family_jacobian(family, optimized.x, strain)
    units = _FAMILIES[family].parameter_units
    floors = np.asarray([1.0 if unit == "Pa" else 1e-12 for unit in units], dtype=np.float64)
    scales = np.maximum(np.abs(optimized.x), floors)
    scaled = jacobian / normalization_stress_pa * scales
    singular_values = np.linalg.svd(scaled, compute_uv=False)
    leading = float(singular_values[0]) if singular_values.size else 0.0
    tolerance = max(scaled.shape) * np.finfo(np.float64).eps * leading
    rank = int(np.sum(singular_values > tolerance)) if leading else 0
    condition = None
    if singular_values.size and singular_values[-1] > 0.0:
        condition = float(singular_values[0] / singular_values[-1])
    # ``active_mask`` is SciPy's authoritative bound evidence.  Do not infer
    # active bounds from rounded parameter values; that can mark an interior
    # value as active and loses the exact lower/upper transition semantics.
    active = tuple(
        name
        for name, mask in zip(definition.parameter_names, optimized.active_mask, strict=True)
        if int(mask) != 0
    )
    return _FittedFamily(
        lower,
        initial,
        optimized.x,
        upper,
        rmse,
        relative_rmse,
        int(optimized.nfev),
        str(optimized.message),
        float(np.sum(np.square((predicted - stress) / normalization_stress_pa))),
        tuple(objective_history),
        rank,
        tolerance,
        condition,
        active,
        bool(optimized.success),
        int(getattr(optimized, "status", 0)),
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
    if options.get("equation_contract") != HARDENING_EQUATION_CONTRACT:
        raise MetalHardeningError(
            "equation_contract must be altair-material-modeler-2025-v1; "
            "legacy hardening recipes require an explicit revision before re-execution"
        )
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
    if primary == secondary:
        raise MetalHardeningError("primary and secondary families must be distinct for a blend")
    minimum = _number(options, "fit_minimum_strain")
    maximum = _number(options, "fit_maximum_strain")
    extrapolation_maximum = _number(options, "extrapolation_maximum_strain")
    primary_weight = _number(options, "primary_weight")
    normalization = _number(options, "normalization_stress_pa")
    selection_reason = options.get("selection_reason")
    if selection_reason is not None and (
        not isinstance(selection_reason, str)
        or not selection_reason.strip()
        or len(selection_reason) > 500
    ):
        raise MetalHardeningError("selection_reason must be 1..500 non-whitespace characters")
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
    if not 0.0 < primary_weight < 1.0 or normalization <= 0.0:
        raise MetalHardeningError(
            "blend weight must be strictly between 0 and 1 and normalization stress positive"
        )
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
        f"equation_contract={HARDENING_EQUATION_CONTRACT}",
        f"fit observed domain [{minimum}, {maximum}] with {len(fit_strain)} points",
        f"extrapolated domain ({maximum}, {extrapolation_maximum}] is not observed",
        "objective=uniform normalized predicted-minus-observed least squares",
    ]
    scalars: list[HardeningScalar] = []
    responses: dict[str, FloatArray] = {}
    candidate_evidence: list[HardeningCandidateEvidence] = []
    for family in families:
        fitted = _fit_family(
            family,
            fit_strain,
            fit_stress,
            normalization,
            maximum_evaluations_value,
            extrapolation_maximum,
        )
        response = _FAMILIES[family].evaluator(fitted.fitted, grid)
        if np.any(~np.isfinite(response)) or np.any(response <= 0.0):
            raise MetalHardeningError(f"{family} extrapolation produced a non-positive response")
        if np.min(np.diff(response)) < -max(float(np.max(response)) * 1e-10, 1e-3):
            raise MetalHardeningError(f"{family} extrapolation is not monotonic non-decreasing")
        quantity = f"stress.hardening.{family}"
        responses[family] = response
        result_columns[quantity] = response
        result_units[quantity] = "Pa"
        tangent = _FAMILIES[family].tangent(fitted.fitted, grid)
        # Residuals intentionally retain the observed fit-point domain.  They are not
        # interpolated onto the extrapolation grid, which keeps their sign and exact
        # objective input unambiguous for API consumers.
        fit_response = _FAMILIES[family].evaluator(fitted.fitted, fit_strain)
        candidate_evidence.append(
            HardeningCandidateEvidence(
                family=family,
                response=response,
                residual=fit_response - fit_stress,
                tangent=tangent,
                parameter_names=_FAMILIES[family].parameter_names,
                parameter_units=_FAMILIES[family].parameter_units,
                lower=fitted.lower,
                initial=fitted.initial,
                fitted=fitted.fitted,
                upper=fitted.upper,
                rmse_pa=fitted.rmse_pa,
                relative_rmse=fitted.relative_rmse,
                objective=fitted.objective,
                scipy_cost=0.5 * fitted.objective,
                nfev=fitted.nfev,
                active_bound=fitted.active_bound,
                jacobian_rank=fitted.jacobian_rank,
                jacobian_tolerance=fitted.jacobian_tolerance,
                jacobian_condition=fitted.jacobian_condition,
                identifiability=(
                    "not_applicable_structural_non_identifiability"
                    if family == "ghosh"
                    else (
                        "identifiable"
                        if fitted.jacobian_rank == len(fitted.fitted)
                        else "rank_deficient"
                    )
                ),
                convergence=fitted.convergence,
                optimizer_status=fitted.optimizer_status,
                optimizer_message=fitted.optimizer_message,
                objective_history=fitted.objective_history,
            )
        )
        diagnostics.append(
            f"{family}: rmse={fitted.rmse_pa} Pa, relative_rmse={fitted.relative_rmse}, "
            f"nfev={fitted.nfev}, rank={fitted.jacobian_rank}, "
            f"condition={fitted.jacobian_condition}, status={fitted.optimizer_status}, "
            f"converged={fitted.convergence}, {fitted.message}"
        )
        if family == "ghosh":
            diagnostics.append(
                "ghosh: fitted delta_p_minus_n=p-n; public n and p are "
                "structurally non-identifiable"
            )
        scalars.extend(
            (
                HardeningScalar(f"{family}.rmse_pa", "statistics.rmse", fitted.rmse_pa, "Pa"),
                HardeningScalar(
                    f"{family}.relative_rmse", "statistics.relative_rmse", fitted.relative_rmse, "1"
                ),
                HardeningScalar(
                    f"{family}.objective",
                    "objective.sum_squared_normalized_residuals",
                    fitted.objective,
                    "1",
                ),
                HardeningScalar(
                    f"{family}.scipy_cost",
                    "objective.scipy_half_sum_squared_normalized_residuals",
                    0.5 * fitted.objective,
                    "1",
                ),
                HardeningScalar(
                    f"{family}.nfev", "diagnostic.function_evaluations", float(fitted.nfev), "1"
                ),
                HardeningScalar(
                    f"{family}.jacobian_rank",
                    "diagnostic.jacobian.rank",
                    float(fitted.jacobian_rank),
                    "1",
                ),
                HardeningScalar(
                    f"{family}.jacobian_tolerance",
                    "diagnostic.jacobian.rank_tolerance",
                    fitted.jacobian_tolerance,
                    "1",
                ),
            )
        )
        if fitted.jacobian_condition is not None:
            scalars.append(
                HardeningScalar(
                    f"{family}.jacobian_condition",
                    "diagnostic.jacobian.condition",
                    fitted.jacobian_condition,
                    "1",
                )
            )
        definition = _FAMILIES[family]
        for name, unit, lower_value, initial_value, value, upper_value in zip(
            definition.parameter_names,
            definition.parameter_units,
            fitted.lower,
            fitted.initial,
            fitted.fitted,
            fitted.upper,
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

    selected = (
        primary_weight * responses[str(primary)]
        + (1.0 - primary_weight) * responses[str(secondary)]
    )
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
    diagnostics.append(f"selected={primary_weight}*{primary}+{1.0 - primary_weight}*{secondary}")
    if isinstance(selection_reason, str):
        diagnostics.append(f"selection reason: {selection_reason.strip()}")
    # The configured blend is a server result too.  Keep it as a fifth evidence
    # row (distinct from the four family attempts) so residual/tangent views can
    # consume authoritative arrays without reconstructing a blend in the UI.
    by_family = {item.family: item for item in candidate_evidence}
    primary_evidence = by_family[str(primary)]
    secondary_evidence = by_family[str(secondary)]
    blend_residual = (
        primary_weight * primary_evidence.residual
        + (1.0 - primary_weight) * secondary_evidence.residual
    )
    blend_tangent = (
        primary_weight * primary_evidence.tangent
        + (1.0 - primary_weight) * secondary_evidence.tangent
    )
    blend_rmse = float(np.sqrt(np.mean(np.square(blend_residual))))
    blend_relative_rmse = blend_rmse / max(float(np.mean(fit_stress)), 1.0)
    candidate_evidence.append(
        HardeningCandidateEvidence(
            family=f"{primary}+{secondary}",
            response=selected,
            residual=blend_residual,
            tangent=blend_tangent,
            parameter_names=(),
            parameter_units=(),
            lower=np.asarray((), dtype=np.float64),
            initial=np.asarray((), dtype=np.float64),
            fitted=np.asarray((), dtype=np.float64),
            upper=np.asarray((), dtype=np.float64),
            rmse_pa=blend_rmse,
            relative_rmse=blend_relative_rmse,
            objective=float(np.sum(np.square(blend_residual / normalization))),
            scipy_cost=float(0.5 * np.sum(np.square(blend_residual / normalization))),
            convergence=bool(primary_evidence.convergence and secondary_evidence.convergence),
            nfev=max(primary_evidence.nfev, secondary_evidence.nfev),
            active_bound=tuple(
                sorted(set(primary_evidence.active_bound + secondary_evidence.active_bound))
            ),
            jacobian_rank=min(primary_evidence.jacobian_rank, secondary_evidence.jacobian_rank),
            jacobian_tolerance=max(
                primary_evidence.jacobian_tolerance,
                secondary_evidence.jacobian_tolerance,
            ),
            jacobian_condition=(
                None
                if primary_evidence.jacobian_condition is None
                or secondary_evidence.jacobian_condition is None
                else max(primary_evidence.jacobian_condition, secondary_evidence.jacobian_condition)
            ),
            identifiability="blend_of_supported_laws",
            uncertainty="not_provided",
            optimizer_status=(
                primary_evidence.optimizer_status
                if primary_evidence.optimizer_status == secondary_evidence.optimizer_status
                else 0
            ),
            optimizer_message="configured server blend",
            objective_history=(),
        )
    )
    return HardeningFitResult(
        result_columns,
        result_units,
        tuple(diagnostics),
        tuple(scalars),
        tuple(candidate_evidence),
    )
