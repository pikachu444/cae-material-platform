from __future__ import annotations

from uuid import UUID

import pytest
from cmp.modules.modeling.domain.reference_linear_elastic_calibration import (
    InvalidCalibrationPlan,
    ReferenceLinearElasticCalibrationPlanContent,
    calibrate_reference_linear_elastic_curve,
    reference_calibration_diagnostics_from_parquet,
    reference_calibration_diagnostics_parquet_bytes,
)

SELECTION = UUID("f9000000-0000-4000-8000-000000000001")
SELECTION_REVISION = UUID("f9000000-0000-4000-8000-000000000002")
MODEL = UUID("f9000000-0000-4000-8000-000000000003")
MODEL_REVISION = UUID("f9000000-0000-4000-8000-000000000004")


def _plan(**overrides: object) -> ReferenceLinearElasticCalibrationPlanContent:
    values: dict[str, object] = {
        "plan_label": "Reference elastic fit",
        "selection_id": SELECTION,
        "selection_revision_id": SELECTION_REVISION,
        "material_model_id": MODEL,
        "material_model_revision_id": MODEL_REVISION,
        "youngs_modulus_lower_bound_pa": 100_000_000_000.0,
        "youngs_modulus_initial_value_pa": 190_000_000_000.0,
        "youngs_modulus_upper_bound_pa": 300_000_000_000.0,
        "normalization_stress_scale_pa": 1_000_000.0,
        "multistart_count": 3,
        "random_seed": 42,
    }
    values.update(overrides)
    return ReferenceLinearElasticCalibrationPlanContent(**values)  # type: ignore[arg-type]


def test_reference_calibration_has_explicit_normalized_objective_and_round_trip() -> None:
    outcome = calibrate_reference_linear_elastic_curve(
        _plan(),
        ((0.0, 0.0), (0.01, 2_000_000_000.0), (0.02, 4_000_000_000.0)),
        attempt_ordinal=2,
    )

    assert outcome.initial_youngs_modulus_pa != 190_000_000_000.0
    assert outcome.calibrated_youngs_modulus_pa == pytest.approx(200_000_000_000.0)
    assert outcome.objective_total == pytest.approx(0.0)
    assert outcome.residual_root_mean_square_pa == pytest.approx(0.0)
    assert outcome.convergence_reason == "analytic_bounded_weighted_least_squares"
    assert outcome.identifiability_status == "not_assessed_reference_one_parameter"
    assert outcome.uncertainty_status == "not_estimated_reference"

    restored = reference_calibration_diagnostics_from_parquet(
        reference_calibration_diagnostics_parquet_bytes(outcome.curve)
    )
    assert restored == outcome.curve


def test_reference_calibration_records_bound_sticking_without_silent_extrapolation() -> None:
    outcome = calibrate_reference_linear_elastic_curve(
        _plan(
            youngs_modulus_initial_value_pa=140_000_000_000.0,
            youngs_modulus_upper_bound_pa=150_000_000_000.0,
        ),
        ((0.0, 0.0), (0.01, 2_000_000_000.0), (0.02, 4_000_000_000.0)),
        attempt_ordinal=1,
    )

    assert outcome.calibrated_youngs_modulus_pa == 150_000_000_000.0
    assert outcome.bound_sticking is True
    assert outcome.objective_total > 0.0


def test_reference_closed_form_calibration_rejects_no_positive_strain_and_bad_bounds() -> None:
    with pytest.raises(InvalidCalibrationPlan, match="positive engineering strain"):
        calibrate_reference_linear_elastic_curve(
            _plan(), ((0.0, 0.0), (0.0, 1_000_000.0)), attempt_ordinal=1
        )

    with pytest.raises(InvalidCalibrationPlan, match="strictly ordered"):
        _plan(
            youngs_modulus_lower_bound_pa=200_000_000_000.0,
            youngs_modulus_upper_bound_pa=200_000_000_000.0,
        )
