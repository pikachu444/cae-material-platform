"""Reference multi-replicate outlier evidence and calibration-scoped decisions.

This bounded P0-2 method is synthetic and non-production.  Detector evidence never removes a
Dataset or Selection member.  A human Assessment is separate, and a calibration input Scope is a
new immutable projection pinned to exact assessment revisions.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cmp.modules.statistics.domain.reference_tensile_pair import StatisticsConflict

REFERENCE_REPLICATE_OUTLIER_PLAN_KIND = "reference_tensile_replicate_modified_z_review"
REFERENCE_REPLICATE_OUTLIER_PLAN_SCHEMA = (
    "urn:cmp:statistics:reference-tensile-replicate-outlier-plan:1.0.0"
)
REFERENCE_REPLICATE_OUTLIER_ASSESSMENT_SCHEMA = (
    "urn:cmp:statistics:reference-tensile-replicate-outlier-assessment:1.0.0"
)
REFERENCE_CALIBRATION_INPUT_SCOPE_SCHEMA = (
    "urn:cmp:statistics:reference-calibration-input-scope:1.0.0"
)
REFERENCE_REPLICATE_OUTLIER_SCHEMA_VERSION = "1.0.0"
REFERENCE_REPLICATE_OUTLIER_DETECTOR = "absolute_modified_z_score_peak_stress"
REFERENCE_REPLICATE_OUTLIER_FORMULA_VERSION = "1.0.0"
REFERENCE_REPLICATE_OUTLIER_FEATURE = "peak_engineering_stress_pa"
REFERENCE_CALIBRATION_SCOPE_KIND = "reference_voce_calibration_input"
MODIFIED_Z_SCALE = 0.6744897501960817


class ReplicateOutlierEvidenceCode(StrEnum):
    MODIFIED_Z_THRESHOLD_EXCEEDED = "modified_z_threshold_exceeded"
    MAD_ZERO_NONMEDIAN_REVIEW = "mad_zero_nonmedian_review"


class ReplicateOutlierAssessmentDecision(StrEnum):
    RETAINED = "retained"
    EXCLUDED_FROM_CALIBRATION = "excluded_from_calibration"


class CalibrationScopeDisposition(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise ValueError(f"{name} must be non-zero")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{name} must be trimmed and contain 1..{maximum} characters")


def _finite_non_negative(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ReferenceReplicateOutlierPlanContent:
    plan_label: str
    statistical_result_id: UUID
    statistical_result_revision_id: UUID
    absolute_modified_z_threshold: float

    def __post_init__(self) -> None:
        _text("plan_label", self.plan_label, 160)
        _uuid("statistical_result_id", self.statistical_result_id)
        _uuid("statistical_result_revision_id", self.statistical_result_revision_id)
        if not math.isfinite(self.absolute_modified_z_threshold) or not (
            0.0 < self.absolute_modified_z_threshold <= 20.0
        ):
            raise ValueError("absolute_modified_z_threshold must be finite and in (0, 20]")


@dataclass(frozen=True, slots=True)
class ReplicateOutlierMemberEvidence:
    ordinal: int
    dataset_id: UUID
    dataset_revision_id: UUID
    test_run_id: UUID
    test_run_revision_id: UUID
    peak_engineering_stress_pa: float

    def __post_init__(self) -> None:
        if not 1 <= self.ordinal <= 50:
            raise ValueError("ordinal must be between 1 and 50")
        for reference_name, reference_value in (
            ("dataset_id", self.dataset_id),
            ("dataset_revision_id", self.dataset_revision_id),
            ("test_run_id", self.test_run_id),
            ("test_run_revision_id", self.test_run_revision_id),
        ):
            _uuid(reference_name, reference_value)
        _finite_non_negative(
            "peak_engineering_stress_pa", self.peak_engineering_stress_pa
        )


@dataclass(frozen=True, slots=True)
class ReferenceReplicateOutlierCandidate:
    id: UUID
    detection_run_id: UUID
    detection_plan_id: UUID
    detection_plan_revision_id: UUID
    statistical_result_id: UUID
    statistical_result_revision_id: UUID
    statistical_plan_id: UUID
    statistical_plan_revision_id: UUID
    selection_id: UUID
    selection_revision_id: UUID
    member: ReplicateOutlierMemberEvidence
    sample_count: int
    sample_median_peak_stress_pa: float
    sample_mad_peak_stress_pa: float
    absolute_modified_z_score: float | None
    threshold: float
    evidence_code: ReplicateOutlierEvidenceCode

    def __post_init__(self) -> None:
        for reference_name, reference_value in (
            ("id", self.id),
            ("detection_run_id", self.detection_run_id),
            ("detection_plan_id", self.detection_plan_id),
            ("detection_plan_revision_id", self.detection_plan_revision_id),
            ("statistical_result_id", self.statistical_result_id),
            ("statistical_result_revision_id", self.statistical_result_revision_id),
            ("statistical_plan_id", self.statistical_plan_id),
            ("statistical_plan_revision_id", self.statistical_plan_revision_id),
            ("selection_id", self.selection_id),
            ("selection_revision_id", self.selection_revision_id),
        ):
            _uuid(reference_name, reference_value)
        if not 3 <= self.sample_count <= 50:
            raise ValueError("sample_count must be between 3 and 50")
        for numeric_name, numeric_value in (
            ("sample_median_peak_stress_pa", self.sample_median_peak_stress_pa),
            ("sample_mad_peak_stress_pa", self.sample_mad_peak_stress_pa),
            ("threshold", self.threshold),
        ):
            _finite_non_negative(numeric_name, numeric_value)
        if not 0.0 < self.threshold <= 20.0:
            raise ValueError("threshold must be in (0, 20]")
        if self.evidence_code is ReplicateOutlierEvidenceCode.MODIFIED_Z_THRESHOLD_EXCEEDED:
            if self.absolute_modified_z_score is None:
                raise ValueError("modified-z evidence requires a finite score")
            _finite_non_negative(
                "absolute_modified_z_score", self.absolute_modified_z_score
            )
            if self.absolute_modified_z_score < self.threshold:
                raise ValueError("modified-z candidate must meet its threshold")
            if self.sample_mad_peak_stress_pa == 0.0:
                raise ValueError("modified-z evidence requires non-zero MAD")
        elif (
            self.absolute_modified_z_score is not None
            or self.sample_mad_peak_stress_pa != 0.0
            or self.member.peak_engineering_stress_pa
            == self.sample_median_peak_stress_pa
        ):
            raise ValueError("MAD-zero review evidence is internally inconsistent")


@dataclass(frozen=True, slots=True)
class ReferenceReplicateOutlierAssessmentContent:
    candidate_id: UUID
    detection_plan_id: UUID
    detection_plan_revision_id: UUID
    decision: ReplicateOutlierAssessmentDecision
    assessment_reason: str

    def __post_init__(self) -> None:
        _uuid("candidate_id", self.candidate_id)
        _uuid("detection_plan_id", self.detection_plan_id)
        _uuid("detection_plan_revision_id", self.detection_plan_revision_id)
        _text("assessment_reason", self.assessment_reason, 2000)


@dataclass(frozen=True, slots=True)
class CalibrationInputScopeMember:
    ordinal: int
    dataset_id: UUID
    dataset_revision_id: UUID
    test_run_id: UUID
    test_run_revision_id: UUID
    disposition: CalibrationScopeDisposition
    candidate_id: UUID | None
    assessment_id: UUID | None
    assessment_revision_id: UUID | None

    def __post_init__(self) -> None:
        if not 1 <= self.ordinal <= 50:
            raise ValueError("ordinal must be between 1 and 50")
        for reference_name, reference_value in (
            ("dataset_id", self.dataset_id),
            ("dataset_revision_id", self.dataset_revision_id),
            ("test_run_id", self.test_run_id),
            ("test_run_revision_id", self.test_run_revision_id),
        ):
            _uuid(reference_name, reference_value)
        optional = (self.candidate_id, self.assessment_id, self.assessment_revision_id)
        if any(value is None for value in optional) and any(
            value is not None for value in optional
        ):
            raise ValueError("candidate and assessment references must be all null or all set")
        for optional_name, optional_value in (
            ("candidate_id", self.candidate_id),
            ("assessment_id", self.assessment_id),
            ("assessment_revision_id", self.assessment_revision_id),
        ):
            if optional_value is not None:
                _uuid(optional_name, optional_value)
        if self.disposition is CalibrationScopeDisposition.EXCLUDED and self.candidate_id is None:
            raise ValueError("excluded member requires an explicit assessed candidate")


@dataclass(frozen=True, slots=True)
class ReferenceCalibrationInputScopeContent:
    scope_label: str
    source_selection_id: UUID
    source_selection_revision_id: UUID
    statistical_result_id: UUID
    statistical_result_revision_id: UUID
    detection_plan_id: UUID
    detection_plan_revision_id: UUID
    members: tuple[CalibrationInputScopeMember, ...]

    def __post_init__(self) -> None:
        _text("scope_label", self.scope_label, 160)
        for name, value in (
            ("source_selection_id", self.source_selection_id),
            ("source_selection_revision_id", self.source_selection_revision_id),
            ("statistical_result_id", self.statistical_result_id),
            ("statistical_result_revision_id", self.statistical_result_revision_id),
            ("detection_plan_id", self.detection_plan_id),
            ("detection_plan_revision_id", self.detection_plan_revision_id),
        ):
            _uuid(name, value)
        if not 3 <= len(self.members) <= 50:
            raise ValueError("calibration input scope requires 3..50 source members")
        if tuple(item.ordinal for item in self.members) != tuple(
            range(1, len(self.members) + 1)
        ):
            raise ValueError("calibration input scope member ordinals must be contiguous")
        if len({item.dataset_revision_id for item in self.members}) != len(self.members):
            raise ValueError("calibration input scope Dataset revisions must be unique")
        if len({item.test_run_revision_id for item in self.members}) != len(self.members):
            raise ValueError("calibration input scope Test Run revisions must be unique")
        if sum(
            item.disposition is CalibrationScopeDisposition.INCLUDED for item in self.members
        ) < 2:
            raise ValueError("calibration input scope must retain at least two members")


def reference_replicate_outlier_plan_canonical(
    value: ReferenceReplicateOutlierPlanContent,
) -> dict[str, object]:
    return {
        "plan_kind": REFERENCE_REPLICATE_OUTLIER_PLAN_KIND,
        "detector": REFERENCE_REPLICATE_OUTLIER_DETECTOR,
        "formula_version": REFERENCE_REPLICATE_OUTLIER_FORMULA_VERSION,
        "statistical_result_id": str(value.statistical_result_id),
        "statistical_result_revision_id": str(value.statistical_result_revision_id),
        "feature": REFERENCE_REPLICATE_OUTLIER_FEATURE,
        "absolute_modified_z_threshold": value.absolute_modified_z_threshold,
        "mad_zero_policy": "flag_nonmedian_members_for_human_review",
        "automatic_exclusion": False,
        "minimum_sample_count": 3,
    }


def reference_replicate_outlier_assessment_canonical(
    value: ReferenceReplicateOutlierAssessmentContent,
) -> dict[str, object]:
    return {
        "candidate_id": str(value.candidate_id),
        "detection_plan_id": str(value.detection_plan_id),
        "detection_plan_revision_id": str(value.detection_plan_revision_id),
        "decision": value.decision.value,
        "assessment_reason": value.assessment_reason,
        "automatic_exclusion": False,
    }


def reference_calibration_input_scope_canonical(
    value: ReferenceCalibrationInputScopeContent,
) -> dict[str, object]:
    return {
        "scope_kind": REFERENCE_CALIBRATION_SCOPE_KIND,
        "source_selection_id": str(value.source_selection_id),
        "source_selection_revision_id": str(value.source_selection_revision_id),
        "statistical_result_id": str(value.statistical_result_id),
        "statistical_result_revision_id": str(value.statistical_result_revision_id),
        "detection_plan_id": str(value.detection_plan_id),
        "detection_plan_revision_id": str(value.detection_plan_revision_id),
        "source_member_count": len(value.members),
        "included_member_count": sum(
            item.disposition is CalibrationScopeDisposition.INCLUDED for item in value.members
        ),
        "excluded_member_count": sum(
            item.disposition is CalibrationScopeDisposition.EXCLUDED for item in value.members
        ),
        "members": [
            {
                "ordinal": item.ordinal,
                "dataset_id": str(item.dataset_id),
                "dataset_revision_id": str(item.dataset_revision_id),
                "test_run_id": str(item.test_run_id),
                "test_run_revision_id": str(item.test_run_revision_id),
                "disposition": item.disposition.value,
                "candidate_id": str(item.candidate_id) if item.candidate_id else None,
                "assessment_id": str(item.assessment_id) if item.assessment_id else None,
                "assessment_revision_id": (
                    str(item.assessment_revision_id) if item.assessment_revision_id else None
                ),
            }
            for item in value.members
        ],
    }


def reference_replicate_review_candidates(
    *,
    candidate_ids: tuple[UUID, ...],
    detection_run_id: UUID,
    detection_plan_id: UUID,
    detection_plan_revision_id: UUID,
    statistical_result_id: UUID,
    statistical_result_revision_id: UUID,
    statistical_plan_id: UUID,
    statistical_plan_revision_id: UUID,
    selection_id: UUID,
    selection_revision_id: UUID,
    members: tuple[ReplicateOutlierMemberEvidence, ...],
    absolute_modified_z_threshold: float,
) -> tuple[ReferenceReplicateOutlierCandidate, ...]:
    """Return review evidence only; never decide exclusion or mutate the input set."""

    if not 3 <= len(members) <= 50:
        raise ValueError("reference replicate detector requires 3..50 members")
    if len(candidate_ids) != len(members):
        raise ValueError("one deterministic candidate ID is required per source member")
    if tuple(item.ordinal for item in members) != tuple(range(1, len(members) + 1)):
        raise ValueError("member ordinals must be contiguous")
    if len({item.dataset_revision_id for item in members}) != len(members):
        raise StatisticsConflict("detector input Dataset revisions must be distinct")
    if len({item.test_run_revision_id for item in members}) != len(members):
        raise StatisticsConflict("detector input Test Run revisions must be distinct")
    if not math.isfinite(absolute_modified_z_threshold) or not (
        0.0 < absolute_modified_z_threshold <= 20.0
    ):
        raise ValueError("absolute_modified_z_threshold must be finite and in (0, 20]")
    peaks = tuple(item.peak_engineering_stress_pa for item in members)
    median = statistics.median(peaks)
    mad = statistics.median(tuple(abs(value - median) for value in peaks))
    candidates: list[ReferenceReplicateOutlierCandidate] = []
    for candidate_id, member in zip(candidate_ids, members, strict=True):
        if mad == 0.0:
            if member.peak_engineering_stress_pa == median:
                continue
            score = None
            evidence_code = ReplicateOutlierEvidenceCode.MAD_ZERO_NONMEDIAN_REVIEW
        else:
            score = abs(
                MODIFIED_Z_SCALE * (member.peak_engineering_stress_pa - median) / mad
            )
            if score < absolute_modified_z_threshold:
                continue
            evidence_code = ReplicateOutlierEvidenceCode.MODIFIED_Z_THRESHOLD_EXCEEDED
        candidates.append(
            ReferenceReplicateOutlierCandidate(
                id=candidate_id,
                detection_run_id=detection_run_id,
                detection_plan_id=detection_plan_id,
                detection_plan_revision_id=detection_plan_revision_id,
                statistical_result_id=statistical_result_id,
                statistical_result_revision_id=statistical_result_revision_id,
                statistical_plan_id=statistical_plan_id,
                statistical_plan_revision_id=statistical_plan_revision_id,
                selection_id=selection_id,
                selection_revision_id=selection_revision_id,
                member=member,
                sample_count=len(members),
                sample_median_peak_stress_pa=median,
                sample_mad_peak_stress_pa=mad,
                absolute_modified_z_score=score,
                threshold=absolute_modified_z_threshold,
                evidence_code=evidence_code,
            )
        )
    return tuple(candidates)
