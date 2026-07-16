from __future__ import annotations

from uuid import UUID

import numpy as np
import pytest
from cmp.modules.modeling.domain.reference_ogden_calibration import (
    OgdenCalibrationCurve,
    OgdenCalibrationMember,
    OgdenCalibrationRole,
    OgdenTestMode,
    calibrate_reference_ogden,
    ogden_diagnostics_from_parquet,
    ogden_diagnostics_parquet_bytes,
    ogden_nominal_stress_pa,
)
from cmp.modules.modeling.domain.scientific_profile import OgdenScientificParameters


def _id(value: int) -> UUID:
    return UUID(int=value)


def _parameters(
    *, uniaxial_weight: float = 1, planar_weight: float = 1
) -> OgdenScientificParameters:
    return OgdenScientificParameters(
        mu_initial_pa=1_200_000,
        mu_lower_pa=100_000,
        mu_upper_pa=10_000_000,
        mu_scale_pa=1_000_000,
        alpha_initial=2.2,
        alpha_lower=0.5,
        alpha_upper=8,
        alpha_scale=2,
        uniaxial_weight=uniaxial_weight,
        planar_weight=planar_weight,
        biaxial_weight=1,
    )


def _curve(
    ordinal: int,
    mode: OgdenTestMode,
    role: OgdenCalibrationRole,
    *,
    mu_pa: float = 2_000_000,
    alpha: float = 3,
    count: int = 21,
    maximum_strain: float = 0.8,
) -> OgdenCalibrationCurve:
    strain = np.linspace(0, maximum_strain, count, dtype=np.float64)
    stress = ogden_nominal_stress_pa(mode, strain, mu_pa, alpha)
    return OgdenCalibrationCurve(
        OgdenCalibrationMember(ordinal, role, mode, _id(100 + ordinal), _id(200 + ordinal)),
        tuple(float(value) for value in strain),
        tuple(float(value) for value in stress),
    )


def test_ogden_analytic_alpha_two_limits_match_neo_hookean_nominal_forms() -> None:
    strain = np.array([0.1, 0.5, 1.0])
    stretch = 1 + strain
    mu = 1_500_000.0
    assert np.allclose(
        ogden_nominal_stress_pa(OgdenTestMode.UNIAXIAL_TENSION, strain, mu, 2),
        mu * (stretch - stretch**-2),
    )
    assert np.allclose(
        ogden_nominal_stress_pa(OgdenTestMode.PLANAR_TENSION, strain, mu, 2),
        mu * (stretch - stretch**-3),
    )
    assert np.allclose(
        ogden_nominal_stress_pa(OgdenTestMode.BIAXIAL_TENSION, strain, mu, 2),
        mu * (stretch - stretch**-5),
    )


def test_multitest_fit_recovers_parameters_holdout_and_covariance_deterministically() -> None:
    curves = (
        _curve(0, OgdenTestMode.UNIAXIAL_TENSION, OgdenCalibrationRole.CALIBRATION),
        _curve(1, OgdenTestMode.PLANAR_TENSION, OgdenCalibrationRole.CALIBRATION),
        _curve(2, OgdenTestMode.BIAXIAL_TENSION, OgdenCalibrationRole.HOLDOUT),
    )
    first = calibrate_reference_ogden(
        parameters=_parameters(),
        multistart_count=3,
        seed=43,
        maximum_function_evaluations=5000,
        curves=curves,
    )
    second = calibrate_reference_ogden(
        parameters=_parameters(),
        multistart_count=3,
        seed=43,
        maximum_function_evaluations=5000,
        curves=curves,
    )
    best = min(first, key=lambda value: value.objective_total)
    assert best.mu_pa == pytest.approx(2_000_000, rel=1e-7)
    assert best.alpha == pytest.approx(3, rel=1e-7)
    assert best.holdout_normalized_rmse == pytest.approx(0, abs=1e-7)
    assert best.jacobian_rank == 2
    assert best.identifiability_status == "full_rank"
    assert best.uncertainty_status == "estimated_jacobian_covariance"
    assert "insufficient_test_modes" not in best.warnings
    assert [item.candidate_sha256 for item in first] == [
        item.candidate_sha256 for item in second
    ]
    diagnostics = ogden_diagnostics_from_parquet(ogden_diagnostics_parquet_bytes(best))
    assert diagnostics == best.diagnostics


def test_mode_weight_changes_the_compromise_between_inconsistent_curves() -> None:
    curves = (
        _curve(
            0,
            OgdenTestMode.UNIAXIAL_TENSION,
            OgdenCalibrationRole.CALIBRATION,
            mu_pa=1_000_000,
        ),
        _curve(
            1,
            OgdenTestMode.PLANAR_TENSION,
            OgdenCalibrationRole.CALIBRATION,
            mu_pa=3_000_000,
        ),
    )
    favor_uniaxial = min(
        calibrate_reference_ogden(
            parameters=_parameters(uniaxial_weight=10, planar_weight=1),
            multistart_count=1,
            seed=1,
            maximum_function_evaluations=5000,
            curves=curves,
        ),
        key=lambda value: value.objective_total,
    )
    favor_planar = min(
        calibrate_reference_ogden(
            parameters=_parameters(uniaxial_weight=1, planar_weight=10),
            multistart_count=1,
            seed=1,
            maximum_function_evaluations=5000,
            curves=curves,
        ),
        key=lambda value: value.objective_total,
    )
    assert favor_uniaxial.mu_pa < favor_planar.mu_pa


def test_single_mode_fit_is_explicitly_warned_even_when_optimizer_converges() -> None:
    candidate = calibrate_reference_ogden(
        parameters=_parameters(),
        multistart_count=1,
        seed=1,
        maximum_function_evaluations=5000,
        curves=(
            _curve(0, OgdenTestMode.UNIAXIAL_TENSION, OgdenCalibrationRole.CALIBRATION),
        ),
    )[0]
    assert candidate.status == "converged"
    assert "insufficient_test_modes" in candidate.warnings
    assert "no_holdout_data" in candidate.warnings
