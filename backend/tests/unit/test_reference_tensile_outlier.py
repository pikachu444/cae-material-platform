from __future__ import annotations

from uuid import UUID

import pytest
from cmp.modules.statistics.domain.reference_tensile_outlier import (
    OutlierAssessmentDecision,
    OutlierCandidateStatus,
    ReferencePairPosition,
    ReferenceTensilePairOutlierAssessmentContent,
    ReferenceTensilePairOutlierDetectionPlanContent,
    reference_tensile_pair_review_candidates,
    relative_peak_difference,
)
from cmp.modules.statistics.domain.reference_tensile_pair import (
    ReferenceTensilePairResultContent,
    ReferenceTensilePairScalarStatistics,
)

PLAN = UUID("f9000000-0000-4000-8000-000000000001")
PLAN_REVISION = UUID("f9000000-0000-4000-8000-000000000002")
RESULT = UUID("f9000000-0000-4000-8000-000000000003")
RESULT_REVISION = UUID("f9000000-0000-4000-8000-000000000004")
RUN = UUID("f9000000-0000-4000-8000-000000000005")
FIRST_CANDIDATE = UUID("f9000000-0000-4000-8000-000000000006")
SECOND_CANDIDATE = UUID("f9000000-0000-4000-8000-000000000007")
FIRST_SELECTION = UUID("f9000000-0000-4000-8000-000000000008")
FIRST_SELECTION_REVISION = UUID("f9000000-0000-4000-8000-000000000009")
SECOND_SELECTION = UUID("f9000000-0000-4000-8000-00000000000a")
SECOND_SELECTION_REVISION = UUID("f9000000-0000-4000-8000-00000000000b")
FIRST_DATASET = UUID("f9000000-0000-4000-8000-00000000000c")
FIRST_DATASET_REVISION = UUID("f9000000-0000-4000-8000-00000000000d")
SECOND_DATASET = UUID("f9000000-0000-4000-8000-00000000000e")
SECOND_DATASET_REVISION = UUID("f9000000-0000-4000-8000-00000000000f")


def _result(
    first_peak: float = 120.0,
    second_peak: float = 150.0,
) -> ReferenceTensilePairResultContent:
    return ReferenceTensilePairResultContent(
        statistical_run_id=RUN,
        plan_id=PLAN,
        plan_revision_id=PLAN_REVISION,
        first_selection_id=FIRST_SELECTION,
        first_selection_revision_id=FIRST_SELECTION_REVISION,
        first_dataset_id=FIRST_DATASET,
        first_dataset_revision_id=FIRST_DATASET_REVISION,
        second_selection_id=SECOND_SELECTION,
        second_selection_revision_id=SECOND_SELECTION_REVISION,
        second_dataset_id=SECOND_DATASET,
        second_dataset_revision_id=SECOND_DATASET_REVISION,
        curve_artifact_id=UUID("f9000000-0000-4000-8000-000000000010"),
        curve_sha256="a" * 64,
        curve_point_count=3,
        scalar=ReferenceTensilePairScalarStatistics(
            first_peak_engineering_stress_pa=first_peak,
            second_peak_engineering_stress_pa=second_peak,
            mean_engineering_stress_pa=(first_peak + second_peak) / 2.0,
            sample_standard_deviation_engineering_stress_pa=1.0,
            median_engineering_stress_pa=(first_peak + second_peak) / 2.0,
            median_absolute_deviation_engineering_stress_pa=1.0,
            interquartile_range_engineering_stress_pa=1.0,
            minimum_engineering_stress_pa=min(first_peak, second_peak),
            maximum_engineering_stress_pa=max(first_peak, second_peak),
            coefficient_of_variation=0.01,
        ),
    )


def test_reference_pair_detector_flags_both_members_for_human_review_at_threshold() -> None:
    candidates = reference_tensile_pair_review_candidates(
        candidate_ids=(FIRST_CANDIDATE, SECOND_CANDIDATE),
        detection_run_id=RUN,
        detection_plan_id=UUID("f9000000-0000-4000-8000-000000000011"),
        detection_plan_revision_id=UUID("f9000000-0000-4000-8000-000000000012"),
        statistical_result_id=RESULT,
        statistical_result_revision_id=RESULT_REVISION,
        result=_result(),
        relative_peak_difference_threshold=0.2,
    )

    assert len(candidates) == 2
    assert tuple(candidate.pair_position for candidate in candidates) == (
        ReferencePairPosition.FIRST,
        ReferencePairPosition.SECOND,
    )
    assert all(
        candidate.status is OutlierCandidateStatus.REVIEW_REQUIRED
        for candidate in candidates
    )
    assert all(candidate.relative_peak_difference == pytest.approx(0.2) for candidate in candidates)
    assert candidates[0].selection_revision_id == FIRST_SELECTION_REVISION
    assert candidates[1].dataset_revision_id == SECOND_DATASET_REVISION


def test_reference_pair_detector_does_not_claim_an_outlier_below_threshold() -> None:
    candidates = reference_tensile_pair_review_candidates(
        candidate_ids=(FIRST_CANDIDATE, SECOND_CANDIDATE),
        detection_run_id=RUN,
        detection_plan_id=UUID("f9000000-0000-4000-8000-000000000011"),
        detection_plan_revision_id=UUID("f9000000-0000-4000-8000-000000000012"),
        statistical_result_id=RESULT,
        statistical_result_revision_id=RESULT_REVISION,
        result=_result(),
        relative_peak_difference_threshold=0.200001,
    )

    assert candidates == ()
    assert relative_peak_difference(120.0, 150.0) == pytest.approx(0.2)
    assert relative_peak_difference(0.0, 0.0) == 0.0


def test_typed_plan_and_assessment_reject_unscoped_or_invalid_review_data() -> None:
    with pytest.raises(ValueError, match=r"in \(0, 1\]"):
        ReferenceTensilePairOutlierDetectionPlanContent(
            plan_label="Invalid detector",
            statistical_result_id=RESULT,
            statistical_result_revision_id=RESULT_REVISION,
            relative_peak_difference_threshold=0.0,
        )
    with pytest.raises(ValueError, match="assessment_reason"):
        ReferenceTensilePairOutlierAssessmentContent(
            candidate_id=FIRST_CANDIDATE,
            statistical_plan_id=PLAN,
            statistical_plan_revision_id=PLAN_REVISION,
            decision=OutlierAssessmentDecision.RETAINED,
            assessment_reason=" ",
        )
