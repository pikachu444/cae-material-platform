from __future__ import annotations

import math
from uuid import UUID

import pytest
from cmp.modules.datasets.domain.reference_tensile import CurvePoint
from cmp.modules.statistics.domain.reference_tensile_pair import QcOutcome
from cmp.modules.statistics.domain.reference_tensile_replicates import (
    ReferenceTensileReplicatePlanContent,
    ReferenceTensileReplicateResultContent,
    calculate_reference_tensile_replicate_statistics,
    calculate_scalar_statistics,
    exact_replicate_grid_qc,
    reference_tensile_replicate_curve_from_parquet,
    reference_tensile_replicate_curve_parquet_bytes,
    reference_tensile_replicate_plan_canonical,
    reference_tensile_replicate_result_canonical,
)


def test_replicate_plan_pins_one_concrete_multi_member_selection_revision() -> None:
    plan = ReferenceTensileReplicatePlanContent(
        plan_label="DP780 aligned replicate statistics",
        selection_id=UUID("10000000-0000-4000-8000-000000000001"),
        selection_revision_id=UUID("10000000-0000-4000-8000-000000000002"),
    )

    canonical = reference_tensile_replicate_plan_canonical(plan)

    assert canonical["required_input_representation"] == "processed"
    assert canonical["curve_grid_policy"] == "exact_processed_grid_match_no_alignment"
    assert canonical["confidence_interval_method"] == "student_t_95_two_sided"


def test_replicate_scalar_statistics_use_specimens_not_curve_points() -> None:
    result = calculate_scalar_statistics((10.0, 20.0, 30.0))

    assert result.sample_count == 3
    assert result.mean == 20.0
    assert result.sample_standard_deviation == 10.0
    assert result.median == 20.0
    assert result.median_absolute_deviation == 10.0
    assert result.interquartile_range == 10.0
    assert result.coefficient_of_variation == 0.5
    half_width = 4.3027 * 10.0 / math.sqrt(3)
    assert result.mean_confidence_interval_lower_95 == pytest.approx(max(0.0, 20 - half_width))
    assert result.mean_confidence_interval_upper_95 == pytest.approx(20 + half_width)


def test_replicate_curve_statistics_preserve_exact_grid_and_pointwise_band() -> None:
    curves = tuple(
        (
            CurvePoint(0.0, 0.0),
            CurvePoint(0.01, peak - 10.0),
            CurvePoint(0.02, peak),
        )
        for peak in (100.0, 110.0, 120.0)
    )

    result = calculate_reference_tensile_replicate_statistics(curves)

    assert result.peak_engineering_stress_pa.sample_count == 3
    assert result.peak_engineering_stress_pa.mean == 110.0
    assert [point.engineering_strain for point in result.curve] == [0.0, 0.01, 0.02]
    assert result.curve[-1].stress.minimum == 100.0
    assert result.curve[-1].stress.maximum == 120.0


def test_replicate_statistics_reject_grid_difference_without_alignment() -> None:
    curves = (
        (CurvePoint(0.0, 0.0), CurvePoint(0.01, 100.0)),
        (CurvePoint(0.0, 0.0), CurvePoint(0.011, 110.0)),
    )

    qc = exact_replicate_grid_qc(curves)
    assert qc.outcome is QcOutcome.FAILED
    assert qc.mismatch_index == 1
    with pytest.raises(Exception, match="performed no alignment"):
        calculate_reference_tensile_replicate_statistics(curves)


def test_replicate_curve_artifact_round_trip_preserves_declared_statistics() -> None:
    curves = tuple(
        (
            CurvePoint(0.0, 0.0),
            CurvePoint(0.01, peak - 10.0),
            CurvePoint(0.02, peak),
        )
        for peak in (100.0, 110.0, 120.0)
    )
    calculated = calculate_reference_tensile_replicate_statistics(curves)

    encoded = reference_tensile_replicate_curve_parquet_bytes(calculated.curve)
    decoded = reference_tensile_replicate_curve_from_parquet(encoded)

    assert decoded == calculated.curve


def test_replicate_result_canonical_retains_scalar_uncertainty_and_input_revision() -> None:
    peak = calculate_scalar_statistics((100.0, 110.0, 120.0))
    result = ReferenceTensileReplicateResultContent(
        statistical_run_id=UUID("20000000-0000-4000-8000-000000000001"),
        plan_id=UUID("20000000-0000-4000-8000-000000000002"),
        plan_revision_id=UUID("20000000-0000-4000-8000-000000000003"),
        selection_id=UUID("20000000-0000-4000-8000-000000000004"),
        selection_revision_id=UUID("20000000-0000-4000-8000-000000000005"),
        curve_artifact_id=UUID("20000000-0000-4000-8000-000000000006"),
        curve_sha256="a" * 64,
        curve_point_count=31,
        peak_engineering_stress_pa=peak,
    )

    canonical = reference_tensile_replicate_result_canonical(result)

    assert canonical["selection_revision_id"] == str(result.selection_revision_id)
    assert canonical["sample_count"] == 3
    assert canonical["mean_engineering_stress_pa"] == 110.0
    assert canonical["confidence_interval_method"] == "student_t_95_two_sided"
