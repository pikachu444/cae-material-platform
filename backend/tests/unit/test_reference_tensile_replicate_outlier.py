from __future__ import annotations

from uuid import UUID

import pytest
from cmp.modules.statistics.domain.reference_tensile_pair import StatisticsConflict
from cmp.modules.statistics.domain.reference_tensile_replicate_outlier import (
    CalibrationInputScopeMember,
    CalibrationScopeDisposition,
    ReferenceCalibrationInputScopeContent,
    ReferenceReplicateOutlierCandidate,
    ReplicateOutlierEvidenceCode,
    ReplicateOutlierMemberEvidence,
    reference_calibration_input_scope_canonical,
    reference_replicate_review_candidates,
)


def uid(value: int) -> UUID:
    return UUID(int=value)


def member(ordinal: int, peak: float) -> ReplicateOutlierMemberEvidence:
    base = ordinal * 10
    return ReplicateOutlierMemberEvidence(
        ordinal=ordinal,
        dataset_id=uid(base + 1),
        dataset_revision_id=uid(base + 2),
        test_run_id=uid(base + 3),
        test_run_revision_id=uid(base + 4),
        peak_engineering_stress_pa=peak,
    )


def candidates(
    members: tuple[ReplicateOutlierMemberEvidence, ...], threshold: float
) -> tuple[ReferenceReplicateOutlierCandidate, ...]:
    return reference_replicate_review_candidates(
        candidate_ids=tuple(uid(100 + index) for index in range(len(members))),
        detection_run_id=uid(200),
        detection_plan_id=uid(201),
        detection_plan_revision_id=uid(202),
        statistical_result_id=uid(203),
        statistical_result_revision_id=uid(204),
        statistical_plan_id=uid(205),
        statistical_plan_revision_id=uid(206),
        selection_id=uid(207),
        selection_revision_id=uid(208),
        members=members,
        absolute_modified_z_threshold=threshold,
    )


def test_modified_z_detector_flags_only_threshold_evidence() -> None:
    result = candidates(
        (member(0, 600_000_000.0), member(1, 610_000_000.0), member(2, 900_000_000.0)),
        3.5,
    )

    assert len(result) == 1
    assert result[0].member.ordinal == 2
    assert result[0].absolute_modified_z_score == pytest.approx(19.56020275568637)
    assert result[0].evidence_code is ReplicateOutlierEvidenceCode.MODIFIED_Z_THRESHOLD_EXCEEDED


def test_zero_mad_nonmedian_member_requires_review_without_infinite_score() -> None:
    result = candidates(
        (member(0, 600.0), member(1, 600.0), member(2, 600.0), member(3, 900.0)),
        3.5,
    )

    assert len(result) == 1
    assert result[0].member.ordinal == 3
    assert result[0].absolute_modified_z_score is None
    assert result[0].sample_mad_peak_stress_pa == 0.0
    assert result[0].evidence_code is ReplicateOutlierEvidenceCode.MAD_ZERO_NONMEDIAN_REVIEW


def test_detector_rejects_point_pseudoreplication_and_duplicate_test_runs() -> None:
    with pytest.raises(ValueError, match=r"3\.\.50"):
        candidates((member(0, 600.0), member(1, 900.0)), 3.5)

    duplicated = member(1, 700.0)
    object.__setattr__(duplicated, "test_run_revision_id", uid(4))
    with pytest.raises(StatisticsConflict, match="Test Run"):
        candidates((member(0, 600.0), duplicated, member(2, 900.0)), 3.5)


def test_calibration_scope_is_separate_and_requires_explicit_exclusion_evidence() -> None:
    included = CalibrationInputScopeMember(
        ordinal=0,
        dataset_id=uid(11),
        dataset_revision_id=uid(12),
        test_run_id=uid(13),
        test_run_revision_id=uid(14),
        disposition=CalibrationScopeDisposition.INCLUDED,
        candidate_id=None,
        assessment_id=None,
        assessment_revision_id=None,
    )
    retained = CalibrationInputScopeMember(
        ordinal=1,
        dataset_id=uid(21),
        dataset_revision_id=uid(22),
        test_run_id=uid(23),
        test_run_revision_id=uid(24),
        disposition=CalibrationScopeDisposition.INCLUDED,
        candidate_id=uid(25),
        assessment_id=uid(26),
        assessment_revision_id=uid(27),
    )
    excluded = CalibrationInputScopeMember(
        ordinal=2,
        dataset_id=uid(31),
        dataset_revision_id=uid(32),
        test_run_id=uid(33),
        test_run_revision_id=uid(34),
        disposition=CalibrationScopeDisposition.EXCLUDED,
        candidate_id=uid(35),
        assessment_id=uid(36),
        assessment_revision_id=uid(37),
    )
    scope = ReferenceCalibrationInputScopeContent(
        scope_label="Reference Voce calibration scope",
        source_selection_id=uid(40),
        source_selection_revision_id=uid(41),
        statistical_result_id=uid(42),
        statistical_result_revision_id=uid(43),
        detection_plan_id=uid(44),
        detection_plan_revision_id=uid(45),
        members=(included, retained, excluded),
    )

    canonical = reference_calibration_input_scope_canonical(scope)
    assert canonical["source_member_count"] == 3
    assert canonical["included_member_count"] == 2
    assert canonical["excluded_member_count"] == 1
    assert canonical["scope_kind"] == "reference_voce_calibration_input"

    with pytest.raises(ValueError, match="explicit assessed candidate"):
        CalibrationInputScopeMember(
            ordinal=2,
            dataset_id=uid(31),
            dataset_revision_id=uid(32),
            test_run_id=uid(33),
            test_run_revision_id=uid(34),
            disposition=CalibrationScopeDisposition.EXCLUDED,
            candidate_id=None,
            assessment_id=None,
            assessment_revision_id=None,
        )


def test_calibration_scope_rejects_excluding_until_fewer_than_two_members_remain() -> None:
    members = tuple(
        CalibrationInputScopeMember(
            ordinal=index,
            dataset_id=uid(index * 10 + 1),
            dataset_revision_id=uid(index * 10 + 2),
            test_run_id=uid(index * 10 + 3),
            test_run_revision_id=uid(index * 10 + 4),
            disposition=(
                CalibrationScopeDisposition.INCLUDED
                if index == 0
                else CalibrationScopeDisposition.EXCLUDED
            ),
            candidate_id=None if index == 0 else uid(index * 10 + 5),
            assessment_id=None if index == 0 else uid(index * 10 + 6),
            assessment_revision_id=None if index == 0 else uid(index * 10 + 7),
        )
        for index in range(3)
    )
    with pytest.raises(ValueError, match="retain at least two"):
        ReferenceCalibrationInputScopeContent(
            scope_label="Invalid scope",
            source_selection_id=uid(40),
            source_selection_revision_id=uid(41),
            statistical_result_id=uid(42),
            statistical_result_revision_id=uid(43),
            detection_plan_id=uid(44),
            detection_plan_revision_id=uid(45),
            members=members,
        )
