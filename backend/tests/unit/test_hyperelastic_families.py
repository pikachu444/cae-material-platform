from __future__ import annotations

from uuid import UUID

import numpy as np
import pytest
from cmp.modules.modeling.domain.hyperelastic_families import (
    HyperelasticFamily,
    fit_hyperelastic_families,
    hyperelastic_diagnostics_from_parquet,
    hyperelastic_diagnostics_parquet_bytes,
    nominal_stress_pa,
)
from cmp.modules.modeling.domain.reference_ogden_calibration import (
    OgdenCalibrationCurve,
    OgdenCalibrationMember,
    OgdenCalibrationRole,
    OgdenTestMode,
)


def _curve(
    ordinal: int,
    mode: OgdenTestMode,
    family: HyperelasticFamily,
    parameters: tuple[float, ...],
    role: OgdenCalibrationRole = OgdenCalibrationRole.CALIBRATION,
) -> OgdenCalibrationCurve:
    strain = np.linspace(0.0, 0.9, 31)
    stress = nominal_stress_pa(family, mode, strain, np.asarray(parameters))
    return OgdenCalibrationCurve(
        OgdenCalibrationMember(
            ordinal,
            role,
            mode,
            UUID(int=100 + ordinal),
            UUID(int=200 + ordinal),
        ),
        tuple(float(item) for item in strain),
        tuple(float(item) for item in stress),
    )


@pytest.mark.parametrize(
    ("family", "parameters"),
    [
        (HyperelasticFamily.NEO_HOOKEAN, (1.2e6,)),
        (HyperelasticFamily.MOONEY_RIVLIN, (0.8e6, 0.35e6)),
        (HyperelasticFamily.YEOH, (0.6e6, 0.08e6, 0.015e6)),
        (HyperelasticFamily.OGDEN_1, (1.4e6, 3.1)),
    ],
)
def test_family_fit_recovers_synthetic_multimode_response(
    family: HyperelasticFamily, parameters: tuple[float, ...]
) -> None:
    curves = (
        _curve(0, OgdenTestMode.UNIAXIAL_TENSION, family, parameters),
        _curve(1, OgdenTestMode.PLANAR_TENSION, family, parameters),
        _curve(
            2,
            OgdenTestMode.BIAXIAL_TENSION,
            family,
            parameters,
            OgdenCalibrationRole.HOLDOUT,
        ),
    )
    candidate = fit_hyperelastic_families(
        curves,
        (family,),
        multistart_count=4,
        random_seed=55,
    )[0]
    assert candidate.calibration_normalized_rmse < 1e-6
    assert candidate.holdout_normalized_rmse is not None
    assert candidate.holdout_normalized_rmse < 1e-5
    assert candidate.stability_status == "monotonic_on_fitted_domain"


def test_family_comparison_ranks_generating_family_and_is_deterministic() -> None:
    generating = HyperelasticFamily.YEOH
    parameters = (0.55e6, 0.11e6, 0.025e6)
    curves = (
        _curve(0, OgdenTestMode.UNIAXIAL_TENSION, generating, parameters),
        _curve(1, OgdenTestMode.PLANAR_TENSION, generating, parameters),
        _curve(2, OgdenTestMode.BIAXIAL_TENSION, generating, parameters),
    )
    families = tuple(HyperelasticFamily)
    first = fit_hyperelastic_families(curves, families, multistart_count=3, random_seed=8)
    second = fit_hyperelastic_families(curves, families, multistart_count=3, random_seed=8)
    assert min(first, key=lambda item: item.objective_total).family is generating
    assert [item.candidate_sha256 for item in first] == [item.candidate_sha256 for item in second]


def test_neo_hookean_is_the_alpha_two_ogden_limit() -> None:
    strain = np.linspace(0.0, 1.0, 21)
    mu = 1.3e6
    for mode in OgdenTestMode:
        neo = nominal_stress_pa(
            HyperelasticFamily.NEO_HOOKEAN, mode, strain, np.asarray([mu / 2.0])
        )
        ogden = nominal_stress_pa(HyperelasticFamily.OGDEN_1, mode, strain, np.asarray([mu, 2.0]))
        assert np.allclose(neo, ogden)


def test_family_candidate_diagnostics_round_trip_without_curve_loss() -> None:
    candidate = fit_hyperelastic_families(
        (
            _curve(
                0,
                OgdenTestMode.UNIAXIAL_TENSION,
                HyperelasticFamily.MOONEY_RIVLIN,
                (0.8e6, 0.3e6),
            ),
        ),
        (HyperelasticFamily.MOONEY_RIVLIN,),
        multistart_count=2,
        random_seed=3,
    )[0]
    restored = hyperelastic_diagnostics_from_parquet(
        hyperelastic_diagnostics_parquet_bytes(candidate)
    )
    assert restored == candidate.diagnostics
    assert restored[-1].predicted_nominal_stress_pa == pytest.approx(
        restored[-1].observed_nominal_stress_pa, rel=1e-6
    )
