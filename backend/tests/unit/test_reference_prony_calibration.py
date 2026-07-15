from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import numpy as np
import pytest
from cmp.modules.datasets.domain.reference_shear_relaxation import ShearRelaxationPoint
from cmp.modules.modeling.domain.reference_prony_calibration import (
    InvalidPronyCalibration,
    PronyParameterPlan,
    ReferencePronyCalibrationPlanContent,
    calibrate_reference_prony,
    evaluate_two_term_prony,
    prony_diagnostics_from_parquet,
    prony_diagnostics_parquet_bytes,
)


def _plan(multistart_count: int = 4) -> ReferencePronyCalibrationPlanContent:
    return ReferencePronyCalibrationPlanContent(
        plan_label="Synthetic two-term reference",
        input_dataset_id=uuid4(),
        input_dataset_revision_id=uuid4(),
        baseline_model_id=uuid4(),
        baseline_model_revision_id=uuid4(),
        total_g_ratio=PronyParameterPlan("total_g_ratio", "1", 0.1, 0.5, 0.9, "none"),
        fast_term_fraction=PronyParameterPlan(
            "fast_term_fraction", "1", 0.05, 0.5, 0.95, "none"
        ),
        fast_relaxation_time_s=PronyParameterPlan(
            "fast_relaxation_time_s", "s", 0.01, 0.5, 5.0, "log"
        ),
        slow_relaxation_time_s=PronyParameterPlan(
            "slow_relaxation_time_s", "s", 6.0, 40.0, 200.0, "log"
        ),
        normalization_modulus_pa=1_000_000_000.0,
        multistart_count=multistart_count,
        random_seed=20260716,
    )


def _points() -> tuple[ShearRelaxationPoint, ...]:
    times = np.asarray([0.0, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0])
    values = evaluate_two_term_prony(
        instantaneous_shear_modulus_pa=1_000_000_000.0,
        times_s=times,
        total_g_ratio=0.6,
        fast_term_fraction=0.4,
        fast_relaxation_time_s=0.5,
        slow_relaxation_time_s=40.0,
    )
    return tuple(
        ShearRelaxationPoint(float(time), float(value))
        for time, value in zip(times, values, strict=True)
    )


def test_deterministic_multistart_recovers_reference_terms_and_diagnostics() -> None:
    first = calibrate_reference_prony(
        plan=_plan(), points=_points(), instantaneous_shear_modulus_pa=1_000_000_000.0
    )
    second = calibrate_reference_prony(
        plan=_plan(), points=_points(), instantaneous_shear_modulus_pa=1_000_000_000.0
    )
    assert len(first) == 4
    assert [item.candidate_sha256 for item in first] == [
        item.candidate_sha256 for item in second
    ]
    best = min(first, key=lambda item: item.objective_total)
    assert best.status == "converged"
    assert best.total_g_ratio == pytest.approx(0.6, rel=1e-5)
    assert best.fast_g_ratio == pytest.approx(0.24, rel=1e-5)
    assert best.slow_g_ratio == pytest.approx(0.36, rel=1e-5)
    assert best.fast_relaxation_time_s == pytest.approx(0.5, rel=1e-5)
    assert best.slow_relaxation_time_s == pytest.approx(40.0, rel=1e-5)
    encoded = prony_diagnostics_parquet_bytes(points=_points(), candidate=best)
    rows = prony_diagnostics_from_parquet(encoded)
    assert len(rows) == 8
    assert rows[0]["time_s"] == 0.0
    assert abs(float(rows[-1]["residual_pa"])) < 1.0


def test_plan_separates_fast_and_slow_time_bounds_and_requires_enough_points() -> None:
    with pytest.raises(InvalidPronyCalibration, match="below slow"):
        replace(
            _plan(),
            fast_relaxation_time_s=PronyParameterPlan(
                "fast_relaxation_time_s", "s", 0.01, 5.0, 10.0, "log"
            ),
            slow_relaxation_time_s=PronyParameterPlan(
                "slow_relaxation_time_s", "s", 9.0, 40.0, 200.0, "log"
            ),
        )
    with pytest.raises(InvalidPronyCalibration, match="at least five"):
        calibrate_reference_prony(
            plan=_plan(1),
            points=_points()[:4],
            instantaneous_shear_modulus_pa=1_000_000_000.0,
        )
