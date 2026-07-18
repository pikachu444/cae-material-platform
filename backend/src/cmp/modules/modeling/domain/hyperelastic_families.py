"""Public incompressible hyperelastic family comparison for T-55E.

The equations use nominal stress and stretch for uniaxial, planar, and equibiaxial tension.
This module is solver neutral; solver mappings are declared separately and never inferred here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares  # type: ignore[import-untyped]

from cmp.modules.modeling.domain.reference_ogden_calibration import (
    OgdenCalibrationCurve,
    OgdenCalibrationRole,
    OgdenTestMode,
)
from cmp.shared.domain.revisions import content_sha256


class HyperelasticFamily(StrEnum):
    NEO_HOOKEAN = "neo_hookean"
    MOONEY_RIVLIN = "mooney_rivlin"
    YEOH = "yeoh"
    OGDEN_1 = "ogden_1"


class HyperelasticFamilyError(ValueError):
    """Candidate configuration or numerical response violates the reference contract."""


@dataclass(frozen=True, slots=True)
class HyperelasticParameter:
    name: str
    value: float
    unit: str


@dataclass(frozen=True, slots=True)
class HyperelasticFamilyCandidate:
    family: HyperelasticFamily
    parameters: tuple[HyperelasticParameter, ...]
    objective_total: float
    calibration_normalized_rmse: float
    holdout_normalized_rmse: float | None
    objective_by_mode: tuple[tuple[OgdenTestMode, float], ...]
    function_evaluations: int
    convergence_reason: str
    stability_status: str
    warnings: tuple[str, ...]
    candidate_sha256: str


def _invariants(
    mode: OgdenTestMode, stretch: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    if mode is OgdenTestMode.UNIAXIAL_TENSION:
        i1 = stretch**2 + 2.0 / stretch
        i2 = 2.0 * stretch + stretch**-2
    elif mode is OgdenTestMode.PLANAR_TENSION:
        i1 = stretch**2 + 1.0 + stretch**-2
        i2 = i1
    else:
        i1 = 2.0 * stretch**2 + stretch**-4
        i2 = stretch**4 + 2.0 * stretch**-2
    return np.asarray(i1, dtype=np.float64), np.asarray(i2, dtype=np.float64)


def nominal_stress_pa(
    family: HyperelasticFamily,
    mode: OgdenTestMode,
    engineering_strain: NDArray[np.float64],
    parameters: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Evaluate an incompressible family using first Piola (nominal) stress."""

    stretch = 1.0 + engineering_strain
    if np.any(stretch <= 0):
        raise HyperelasticFamilyError("stretch must remain positive")
    if family is HyperelasticFamily.OGDEN_1:
        mu_pa, alpha = float(parameters[0]), float(parameters[1])
        if alpha <= 0:
            raise HyperelasticFamilyError("Ogden alpha must be positive")
        if mode is OgdenTestMode.UNIAXIAL_TENSION:
            factor = stretch ** (alpha - 1.0) - stretch ** (-alpha / 2.0 - 1.0)
        elif mode is OgdenTestMode.PLANAR_TENSION:
            factor = stretch ** (alpha - 1.0) - stretch ** (-alpha - 1.0)
        else:
            factor = stretch ** (alpha - 1.0) - stretch ** (-2.0 * alpha - 1.0)
        return np.asarray((2.0 * mu_pa / alpha) * factor, dtype=np.float64)

    c10 = float(parameters[0])
    c01 = float(parameters[1]) if family is HyperelasticFamily.MOONEY_RIVLIN else 0.0
    if family is HyperelasticFamily.YEOH:
        i1, _i2 = _invariants(mode, stretch)
        shifted = i1 - 3.0
        derivative_i1 = (
            c10 + 2.0 * float(parameters[1]) * shifted + 3.0 * float(parameters[2]) * shifted**2
        )
        if mode is OgdenTestMode.UNIAXIAL_TENSION:
            factor = stretch - stretch**-2
        elif mode is OgdenTestMode.PLANAR_TENSION:
            factor = stretch - stretch**-3
        else:
            factor = stretch - stretch**-5
        return np.asarray(2.0 * derivative_i1 * factor, dtype=np.float64)
    if mode is OgdenTestMode.UNIAXIAL_TENSION:
        response = 2.0 * (c10 + c01 / stretch) * (stretch - stretch**-2)
    elif mode is OgdenTestMode.PLANAR_TENSION:
        response = 2.0 * (c10 + c01) * (stretch - stretch**-3)
    else:
        response = 2.0 * (c10 + c01 * stretch**2) * (stretch - stretch**-5)
    return np.asarray(response, dtype=np.float64)


def _contract(
    family: HyperelasticFamily, stress_scale_pa: float
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], tuple[str, ...]]:
    if family is HyperelasticFamily.NEO_HOOKEAN:
        return (
            np.asarray([stress_scale_pa / 6.0]),
            np.asarray([stress_scale_pa * 1e-8]),
            np.asarray([stress_scale_pa * 10.0]),
            ("c10_pa",),
        )
    if family is HyperelasticFamily.MOONEY_RIVLIN:
        return (
            np.asarray([stress_scale_pa / 12.0, stress_scale_pa / 12.0]),
            np.asarray([stress_scale_pa * 1e-8, 0.0]),
            np.asarray([stress_scale_pa * 10.0, stress_scale_pa * 10.0]),
            ("c10_pa", "c01_pa"),
        )
    if family is HyperelasticFamily.YEOH:
        return (
            np.asarray([stress_scale_pa / 6.0, 0.0, 0.0]),
            np.asarray([stress_scale_pa * 1e-8, -stress_scale_pa * 10.0, -stress_scale_pa * 10.0]),
            np.asarray([stress_scale_pa * 10.0, stress_scale_pa * 10.0, stress_scale_pa * 10.0]),
            ("c10_pa", "c20_pa", "c30_pa"),
        )
    return (
        np.asarray([stress_scale_pa / 3.0, 2.0]),
        np.asarray([stress_scale_pa * 1e-8, 0.25]),
        np.asarray([stress_scale_pa * 10.0, 12.0]),
        ("mu_pa", "alpha"),
    )


def _mode_weights(curves: tuple[OgdenCalibrationCurve, ...]) -> dict[int, float]:
    counts = {
        mode: sum(curve.member.test_mode is mode for curve in curves) for mode in OgdenTestMode
    }
    return {
        curve.member.ordinal: curve.member.weight
        / max(counts[curve.member.test_mode], 1)
        / len(curve.engineering_strain)
        for curve in curves
    }


def fit_hyperelastic_families(
    curves: tuple[OgdenCalibrationCurve, ...],
    families: tuple[HyperelasticFamily, ...],
    *,
    multistart_count: int,
    random_seed: int,
    maximum_function_evaluations: int = 5000,
) -> tuple[HyperelasticFamilyCandidate, ...]:
    """Fit one best candidate per requested public family with shared weighting semantics."""

    if not curves or not families or len(set(families)) != len(families):
        raise HyperelasticFamilyError("curves and unique candidate families are required")
    calibration = tuple(
        curve for curve in curves if curve.member.role is OgdenCalibrationRole.CALIBRATION
    )
    holdout = tuple(curve for curve in curves if curve.member.role is OgdenCalibrationRole.HOLDOUT)
    if not calibration or not 1 <= multistart_count <= 32:
        raise HyperelasticFamilyError("calibration curves and multistart_count 1..32 are required")
    scale = max(max(curve.nominal_stress_pa) for curve in calibration)
    weights = _mode_weights(calibration)
    rng = np.random.Generator(np.random.PCG64(random_seed))
    candidates: list[HyperelasticFamilyCandidate] = []
    for family in families:
        initial, lower, upper, names = _contract(family, scale)

        def residual(
            parameters: NDArray[np.float64],
            selected_family: HyperelasticFamily = family,
        ) -> NDArray[np.float64]:
            values = []
            for curve in calibration:
                strain = np.asarray(curve.engineering_strain, dtype=np.float64)
                observed = np.asarray(curve.nominal_stress_pa, dtype=np.float64)
                values.append(
                    (
                        nominal_stress_pa(
                            selected_family, curve.member.test_mode, strain, parameters
                        )
                        - observed
                    )
                    / curve.normalization_stress_pa
                    * math.sqrt(weights[curve.member.ordinal])
                )
            return np.concatenate(values)

        starts = [initial]
        starts.extend(rng.uniform(lower, upper) for _ in range(multistart_count - 1))
        outcomes = [
            least_squares(
                residual,
                start,
                bounds=(lower, upper),
                method="trf",
                max_nfev=maximum_function_evaluations,
                ftol=1e-10,
                xtol=1e-10,
                gtol=1e-10,
            )
            for start in starts
        ]
        outcome = min(outcomes, key=lambda value: float(np.sum(value.fun**2)))
        parameters = np.asarray(outcome.x, dtype=np.float64)
        by_mode: list[tuple[OgdenTestMode, float]] = []
        normalized_calibration: list[float] = []
        for mode in OgdenTestMode:
            total = 0.0
            for curve in calibration:
                if curve.member.test_mode is not mode:
                    continue
                predicted = nominal_stress_pa(
                    family,
                    mode,
                    np.asarray(curve.engineering_strain, dtype=np.float64),
                    parameters,
                )
                normalized = (
                    predicted - np.asarray(curve.nominal_stress_pa, dtype=np.float64)
                ) / curve.normalization_stress_pa
                normalized_calibration.extend(float(item) for item in normalized)
                total += float(np.sum(normalized**2) * weights[curve.member.ordinal])
            by_mode.append((mode, total))
        normalized_holdout = [
            float(item)
            for curve in holdout
            for item in (
                (
                    nominal_stress_pa(
                        family,
                        curve.member.test_mode,
                        np.asarray(curve.engineering_strain, dtype=np.float64),
                        parameters,
                    )
                    - np.asarray(curve.nominal_stress_pa, dtype=np.float64)
                )
                / curve.normalization_stress_pa
            )
        ]
        stability_grid = np.linspace(
            0.0, max(max(curve.engineering_strain) for curve in curves), 201
        )
        stable = all(
            np.all(np.diff(nominal_stress_pa(family, mode, stability_grid, parameters)) >= -1e-8)
            for mode in {curve.member.test_mode for curve in curves}
        )
        warnings = tuple(
            item
            for item, present in (
                ("optimizer_nonconverged", not outcome.success),
                ("nonmonotonic_reference_response", not stable),
                ("no_holdout_data", not holdout),
                ("single_test_mode", len({curve.member.test_mode for curve in calibration}) < 2),
            )
            if present
        )
        parameter_values = tuple(
            HyperelasticParameter(name, float(value), "1" if name == "alpha" else "Pa")
            for name, value in zip(names, parameters, strict=True)
        )
        canonical = {
            "family": family.value,
            "parameters": [(item.name, item.value, item.unit) for item in parameter_values],
            "objective_by_mode": [(mode.value, value) for mode, value in by_mode],
            "warnings": warnings,
        }
        candidates.append(
            HyperelasticFamilyCandidate(
                family=family,
                parameters=parameter_values,
                objective_total=sum(value for _mode, value in by_mode),
                calibration_normalized_rmse=float(
                    np.sqrt(np.mean(np.square(normalized_calibration)))
                ),
                holdout_normalized_rmse=(
                    float(np.sqrt(np.mean(np.square(normalized_holdout))))
                    if normalized_holdout
                    else None
                ),
                objective_by_mode=tuple(by_mode),
                function_evaluations=int(outcome.nfev),
                convergence_reason=str(outcome.message)[:255],
                stability_status="monotonic_on_fitted_domain" if stable else "nonmonotonic",
                warnings=warnings,
                candidate_sha256=content_sha256(canonical),
            )
        )
    return tuple(candidates)
