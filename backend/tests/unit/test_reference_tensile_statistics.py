from __future__ import annotations

import math
from uuid import UUID

import pytest
from cmp.modules.datasets.domain.reference_tensile import CurvePoint
from cmp.modules.statistics.domain.reference_tensile_pair import (
    InvalidStatisticsRequest,
    QcOutcome,
    ReferenceTensilePairPlanContent,
    StatisticsConflict,
    calculate_reference_tensile_pair_statistics,
    observed_grid_qc,
    reference_tensile_pair_curve_from_parquet,
    reference_tensile_pair_curve_parquet_bytes,
)

FIRST_SELECTION = UUID("f6000000-0000-4000-8000-000000000001")
FIRST_SELECTION_REVISION = UUID("f6000000-0000-4000-8000-000000000002")
SECOND_SELECTION = UUID("f6000000-0000-4000-8000-000000000003")
SECOND_SELECTION_REVISION = UUID("f6000000-0000-4000-8000-000000000004")


def _curve(*stresses: float) -> tuple[CurvePoint, ...]:
    return tuple(
        CurvePoint(engineering_strain=index * 0.01, engineering_stress=stress)
        for index, stress in enumerate(stresses)
    )


def test_reference_pair_statistics_uses_one_peak_per_test_run_and_typed_curve_band() -> None:
    result = calculate_reference_tensile_pair_statistics(
        _curve(0.0, 100.0, 120.0),
        _curve(0.0, 110.0, 140.0),
    )

    assert result.scalar.first_peak_engineering_stress_pa == 120.0
    assert result.scalar.second_peak_engineering_stress_pa == 140.0
    assert result.scalar.mean_engineering_stress_pa == 130.0
    assert result.scalar.median_engineering_stress_pa == 130.0
    assert result.scalar.median_absolute_deviation_engineering_stress_pa == 10.0
    assert result.scalar.interquartile_range_engineering_stress_pa == 10.0
    assert result.scalar.minimum_engineering_stress_pa == 120.0
    assert result.scalar.maximum_engineering_stress_pa == 140.0
    assert result.scalar.sample_standard_deviation_engineering_stress_pa == pytest.approx(
        math.sqrt(200.0)
    )
    assert result.scalar.coefficient_of_variation == pytest.approx(math.sqrt(200.0) / 130.0)
    assert result.curve[1].mean_engineering_stress_pa == 105.0
    assert result.curve[1].sample_standard_deviation_engineering_stress_pa == pytest.approx(
        math.sqrt(50.0)
    )
    assert result.curve[2].minimum_engineering_stress_pa == 120.0
    assert result.curve[2].maximum_engineering_stress_pa == 140.0

    round_trip = reference_tensile_pair_curve_from_parquet(
        reference_tensile_pair_curve_parquet_bytes(result.curve)
    )
    assert round_trip == result.curve


def test_reference_pair_refuses_even_one_observed_grid_difference_without_alignment() -> None:
    first = _curve(0.0, 100.0, 120.0)
    second = (
        CurvePoint(0.0, 0.0),
        CurvePoint(0.0100000001, 110.0),
        CurvePoint(0.02, 140.0),
    )

    qc = observed_grid_qc(first, second)

    assert qc.outcome is QcOutcome.FAILED
    assert qc.mismatch_index == 1
    assert "no implicit alignment or resampling" in qc.detail
    with pytest.raises(StatisticsConflict, match="no implicit alignment"):
        calculate_reference_tensile_pair_statistics(first, second)


def test_reference_pair_plan_pins_two_distinct_immutable_selection_revisions() -> None:
    plan = ReferenceTensilePairPlanContent(
        plan_label="Reference pair",
        first_selection_id=FIRST_SELECTION,
        first_selection_revision_id=FIRST_SELECTION_REVISION,
        second_selection_id=SECOND_SELECTION,
        second_selection_revision_id=SECOND_SELECTION_REVISION,
    )

    assert plan.first_selection_id == FIRST_SELECTION
    assert plan.second_selection_revision_id == SECOND_SELECTION_REVISION
    with pytest.raises(InvalidStatisticsRequest, match="must be distinct"):
        ReferenceTensilePairPlanContent(
            plan_label="Invalid reference pair",
            first_selection_id=FIRST_SELECTION,
            first_selection_revision_id=FIRST_SELECTION_REVISION,
            second_selection_id=SECOND_SELECTION,
            second_selection_revision_id=FIRST_SELECTION_REVISION,
        )
