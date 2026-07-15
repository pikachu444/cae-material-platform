from __future__ import annotations

import math
from uuid import UUID

import pytest
from cmp.modules.datasets.domain.reference_tensile import CurvePoint
from cmp.modules.modeling.domain.reference_voce_calibration import VoceEngineeringCurveInput
from cmp.modules.validation.domain.reference_voce_holdout import (
    VoceHoldoutVerdict,
    evaluate_reference_voce_holdout,
    reference_voce_holdout_comparison_bytes,
)


def _curve(*, offset_pa: float = 0.0) -> VoceEngineeringCurveInput:
    youngs = 210e9
    sigma_0 = 300e6
    q = 160e6
    b = 12.0
    points: list[CurvePoint] = []
    for plastic_strain in (0.0, 0.01, 0.02, 0.03, 0.04):
        true_stress = sigma_0 + q * (1.0 - math.exp(-b * plastic_strain)) + offset_pa
        engineering_strain = math.exp(plastic_strain + true_stress / youngs) - 1.0
        engineering_stress = true_stress / (1.0 + engineering_strain)
        points.append(CurvePoint(engineering_strain, engineering_stress))
    return VoceEngineeringCurveInput(
        member_ordinal=0,
        dataset_id=UUID(int=1),
        dataset_revision_id=UUID(int=2),
        test_run_id=UUID(int=3),
        test_run_revision_id=UUID(int=4),
        points=tuple(points),
    )


def test_exact_public_voce_response_passes_independent_holdout() -> None:
    result = evaluate_reference_voce_holdout(
        _curve(),
        youngs_modulus_pa=210e9,
        sigma_0_pa=300e6,
        q_pa=160e6,
        b=12.0,
    )

    assert result.verdict is VoceHoldoutVerdict.PASSED
    assert result.root_mean_squared_error_pa == pytest.approx(0.0, abs=1e-6)
    assert result.relative_root_mean_squared_error == pytest.approx(0.0, abs=1e-14)
    assert len(result.points) == 4
    assert b'"solver"' not in reference_voce_holdout_comparison_bytes(result)


def test_reference_threshold_reports_failed_without_refitting() -> None:
    result = evaluate_reference_voce_holdout(
        _curve(offset_pa=50e6),
        youngs_modulus_pa=210e9,
        sigma_0_pa=300e6,
        q_pa=160e6,
        b=12.0,
    )

    assert result.verdict is VoceHoldoutVerdict.FAILED
    assert result.relative_root_mean_squared_error > 0.05
    assert all(point.residual_true_yield_stress_pa < 0 for point in result.points)
