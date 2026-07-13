"""Typed reference-pair outlier-review facts without mutating source data.

The first T-21 method works only from the immutable two-sample result emitted by T-20.
It intentionally flags *both* sides of a discrepant pair for human review: two samples are
not sufficient evidence to identify one specimen as an outlier.  An Assessment is a separate,
immutable decision scoped to the exact Statistical Plan revision and never changes a Dataset or
Selection revision.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cmp.modules.statistics.domain.reference_tensile_pair import (
    REFERENCE_TENSILE_PAIR_PLAN_KIND,
    ReferenceTensilePairResultContent,
    StatisticsConflict,
)

REFERENCE_TENSILE_PAIR_OUTLIER_DETECTION_PLAN_KIND = (
    "reference_tensile_pair_peak_difference_review"
)
REFERENCE_TENSILE_PAIR_OUTLIER_DETECTION_PLAN_SCHEMA = (
    "urn:cmp:statistics:reference-tensile-pair-outlier-detection-plan:1.0.0"
)
REFERENCE_TENSILE_PAIR_OUTLIER_ASSESSMENT_SCHEMA = (
    "urn:cmp:statistics:reference-tensile-pair-outlier-assessment:1.0.0"
)
REFERENCE_TENSILE_PAIR_OUTLIER_SCHEMA_VERSION = "1.0.0"
REFERENCE_TENSILE_PAIR_OUTLIER_DETECTOR = "relative_peak_engineering_stress_difference"
REFERENCE_TENSILE_PAIR_OUTLIER_FORMULA_VERSION = "1.0.0"
REFERENCE_TENSILE_PAIR_OUTLIER_FEATURE = "peak_engineering_stress_pa"
REFERENCE_TENSILE_PAIR_OUTLIER_SCOPE_KIND = "reference_pair_analysis"


class OutlierCandidateStatus(StrEnum):
    """A detector signal is never an automatic exclusion decision."""

    REVIEW_REQUIRED = "review_required"


class OutlierDetectionRunStatus(StrEnum):
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class OutlierAssessmentDecision(StrEnum):
    RETAINED = "retained"
    EXCLUDED_FROM_REFERENCE_ANALYSIS = "excluded_from_reference_analysis"


class ReferencePairPosition(StrEnum):
    FIRST = "first"
    SECOND = "second"


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
class ReferenceTensilePairOutlierDetectionPlanContent:
    """Immutable detector configuration pinned to one immutable Statistics Result."""

    plan_label: str
    statistical_result_id: UUID
    statistical_result_revision_id: UUID
    relative_peak_difference_threshold: float

    def __post_init__(self) -> None:
        _text("plan_label", self.plan_label, 160)
        _uuid("statistical_result_id", self.statistical_result_id)
        _uuid("statistical_result_revision_id", self.statistical_result_revision_id)
        if not math.isfinite(self.relative_peak_difference_threshold) or not (
            0.0 < self.relative_peak_difference_threshold <= 1.0
        ):
            raise ValueError(
                "relative_peak_difference_threshold must be finite and in (0, 1]"
            )


@dataclass(frozen=True, slots=True)
class ReferenceTensilePairOutlierCandidate:
    """Immutable review signal for one side of a reference two-sample pair."""

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
    dataset_id: UUID
    dataset_revision_id: UUID
    pair_position: ReferencePairPosition
    peak_engineering_stress_pa: float
    peer_peak_engineering_stress_pa: float
    relative_peak_difference: float
    relative_peak_difference_threshold: float
    status: OutlierCandidateStatus = OutlierCandidateStatus.REVIEW_REQUIRED

    def __post_init__(self) -> None:
        for name, reference in (
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
            ("dataset_id", self.dataset_id),
            ("dataset_revision_id", self.dataset_revision_id),
        ):
            _uuid(name, reference)
        for name, numeric_value in (
            ("peak_engineering_stress_pa", self.peak_engineering_stress_pa),
            ("peer_peak_engineering_stress_pa", self.peer_peak_engineering_stress_pa),
            ("relative_peak_difference", self.relative_peak_difference),
            (
                "relative_peak_difference_threshold",
                self.relative_peak_difference_threshold,
            ),
        ):
            _finite_non_negative(name, numeric_value)
        if self.relative_peak_difference > 1.0:
            raise ValueError("relative_peak_difference must not exceed 1")
        if not 0.0 < self.relative_peak_difference_threshold <= 1.0:
            raise ValueError("relative_peak_difference_threshold must be in (0, 1]")
        if self.relative_peak_difference < self.relative_peak_difference_threshold:
            raise ValueError("candidate must meet its declared threshold")
        if self.status is not OutlierCandidateStatus.REVIEW_REQUIRED:
            raise ValueError("reference detector may create review_required candidates only")


@dataclass(frozen=True, slots=True)
class ReferenceTensilePairOutlierAssessmentContent:
    """A human decision scoped to exactly one immutable reference-pair Plan revision."""

    candidate_id: UUID
    statistical_plan_id: UUID
    statistical_plan_revision_id: UUID
    decision: OutlierAssessmentDecision
    assessment_reason: str

    def __post_init__(self) -> None:
        _uuid("candidate_id", self.candidate_id)
        _uuid("statistical_plan_id", self.statistical_plan_id)
        _uuid("statistical_plan_revision_id", self.statistical_plan_revision_id)
        _text("assessment_reason", self.assessment_reason, 2000)


def reference_tensile_pair_outlier_detection_plan_canonical(
    value: ReferenceTensilePairOutlierDetectionPlanContent,
) -> dict[str, object]:
    return {
        "plan_kind": REFERENCE_TENSILE_PAIR_OUTLIER_DETECTION_PLAN_KIND,
        "detector": REFERENCE_TENSILE_PAIR_OUTLIER_DETECTOR,
        "formula_version": REFERENCE_TENSILE_PAIR_OUTLIER_FORMULA_VERSION,
        "statistical_result_id": str(value.statistical_result_id),
        "statistical_result_revision_id": str(value.statistical_result_revision_id),
        "statistical_result_kind": REFERENCE_TENSILE_PAIR_PLAN_KIND,
        "feature": REFERENCE_TENSILE_PAIR_OUTLIER_FEATURE,
        "relative_peak_difference_threshold": value.relative_peak_difference_threshold,
        "candidate_policy": "flag_both_pair_members_for_human_review",
        "automatic_exclusion": False,
        "scope_kind": REFERENCE_TENSILE_PAIR_OUTLIER_SCOPE_KIND,
    }


def reference_tensile_pair_outlier_assessment_canonical(
    value: ReferenceTensilePairOutlierAssessmentContent,
) -> dict[str, object]:
    return {
        "scope_kind": REFERENCE_TENSILE_PAIR_OUTLIER_SCOPE_KIND,
        "candidate_id": str(value.candidate_id),
        "statistical_plan_id": str(value.statistical_plan_id),
        "statistical_plan_revision_id": str(value.statistical_plan_revision_id),
        "decision": value.decision.value,
        "assessment_reason": value.assessment_reason,
    }


def relative_peak_difference(first: float, second: float) -> float:
    """Return a bounded, explicit pair discrepancy without claiming an outlier identity."""

    _finite_non_negative("first_peak_engineering_stress_pa", first)
    _finite_non_negative("second_peak_engineering_stress_pa", second)
    denominator = max(first, second)
    return 0.0 if denominator == 0.0 else abs(first - second) / denominator


def reference_tensile_pair_review_candidates(
    *,
    candidate_ids: tuple[UUID, UUID],
    detection_run_id: UUID,
    detection_plan_id: UUID,
    detection_plan_revision_id: UUID,
    statistical_result_id: UUID,
    statistical_result_revision_id: UUID,
    result: ReferenceTensilePairResultContent,
    relative_peak_difference_threshold: float,
) -> tuple[ReferenceTensilePairOutlierCandidate, ...]:
    """Create both review candidates only if the pinned pair exceeds its declared threshold."""

    if len(candidate_ids) != 2:
        raise ValueError("reference pair detector requires exactly two candidate IDs")
    if statistical_result_id.int == 0 or statistical_result_revision_id.int == 0:
        raise ValueError("statistical result identity and revision must be non-zero")
    if not 0.0 < relative_peak_difference_threshold <= 1.0:
        raise ValueError("relative_peak_difference_threshold must be in (0, 1]")
    first = result.scalar.first_peak_engineering_stress_pa
    second = result.scalar.second_peak_engineering_stress_pa
    difference = relative_peak_difference(first, second)
    if difference < relative_peak_difference_threshold:
        return ()
    if result.first_selection_revision_id == result.second_selection_revision_id:
        raise StatisticsConflict("outlier detector input must retain distinct Selection revisions")
    return (
        ReferenceTensilePairOutlierCandidate(
            id=candidate_ids[0],
            detection_run_id=detection_run_id,
            detection_plan_id=detection_plan_id,
            detection_plan_revision_id=detection_plan_revision_id,
            statistical_result_id=statistical_result_id,
            statistical_result_revision_id=statistical_result_revision_id,
            statistical_plan_id=result.plan_id,
            statistical_plan_revision_id=result.plan_revision_id,
            selection_id=result.first_selection_id,
            selection_revision_id=result.first_selection_revision_id,
            dataset_id=result.first_dataset_id,
            dataset_revision_id=result.first_dataset_revision_id,
            pair_position=ReferencePairPosition.FIRST,
            peak_engineering_stress_pa=first,
            peer_peak_engineering_stress_pa=second,
            relative_peak_difference=difference,
            relative_peak_difference_threshold=relative_peak_difference_threshold,
        ),
        ReferenceTensilePairOutlierCandidate(
            id=candidate_ids[1],
            detection_run_id=detection_run_id,
            detection_plan_id=detection_plan_id,
            detection_plan_revision_id=detection_plan_revision_id,
            statistical_result_id=statistical_result_id,
            statistical_result_revision_id=statistical_result_revision_id,
            statistical_plan_id=result.plan_id,
            statistical_plan_revision_id=result.plan_revision_id,
            selection_id=result.second_selection_id,
            selection_revision_id=result.second_selection_revision_id,
            dataset_id=result.second_dataset_id,
            dataset_revision_id=result.second_dataset_revision_id,
            pair_position=ReferencePairPosition.SECOND,
            peak_engineering_stress_pa=second,
            peer_peak_engineering_stress_pa=first,
            relative_peak_difference=difference,
            relative_peak_difference_threshold=relative_peak_difference_threshold,
        ),
    )
