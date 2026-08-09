"""Typed review/lifecycle policy for immutable candidate revisions.

T-29 deliberately keeps governance facts separate from the candidate domain.  A review request
pins one immutable aggregate revision and one manifest digest; decisions append an immutable fact
and advance the shared lifecycle projection.  No candidate content is updated by this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.review_release.domain.evidence import ReviewSubjectEvidence

REGISTERED_REVIEW_TYPES = frozenset(
    {
        "catalog.material",
        "catalog.configurable_record",
        "datasets.test_data_document",
        "modeling.material_model",
        "exporting.solver_card",
        "exporting.neutral_solver_card",
        # Legacy T-29 consumers still submit validation results with an explicit
        # digest.  New Issue #160 subjects use the closed evidence registry.
        "validation.result",
    }
)

_AGGREGATE_TYPE = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

REVIEW_REQUEST_SCHEMA_ID = "urn:cmp:governance:review-request:1.0.0"
REVIEW_REQUEST_SCHEMA_VERSION = "1.0.0"
REVIEW_DECISION_SCHEMA_ID = "urn:cmp:governance:review-decision:1.0.0"
REVIEW_DECISION_SCHEMA_VERSION = "1.0.0"
REQUIRED_REVIEW_ROLE = "domain_reviewer"


class LifecycleState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"


class ReviewDecisionKind(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"


class ReviewError(Exception):
    """Base error for review/lifecycle operations."""


class ReviewNotFound(ReviewError):
    """The requested review or immutable lifecycle target is not visible."""


class ReviewConflict(ReviewError):
    """The review command conflicts with immutable evidence or lifecycle state."""


class InvalidReview(ReviewError):
    """A review command violates the typed governance policy."""


def _non_blank(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidReview(f"{name} must be trimmed and contain 1..{maximum} characters")


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidReview(f"{name} must be a non-zero UUID")


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidReview(f"{name} must be timezone-aware")


def validate_manifest_sha256(value: str) -> str:
    if _SHA256.fullmatch(value) is None:
        raise InvalidReview("manifest_sha256 must be a lowercase SHA-256 hex digest")
    return value


def validate_aggregate_type(value: str) -> str:
    if _AGGREGATE_TYPE.fullmatch(value) is None:
        raise InvalidReview("aggregate_type must be a stable namespaced token")
    if value not in REGISTERED_REVIEW_TYPES:
        raise InvalidReview("aggregate_type is not registered for review")
    return value


@dataclass(frozen=True, slots=True)
class ReviewRequestRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    aggregate_type: str
    aggregate_id: UUID
    revision_id: UUID
    manifest_sha256: str
    required_role: str
    requested_by: UUID
    requested_at: datetime
    reason: str
    lifecycle_state: LifecycleState
    requested_by_display_name: str | None = None
    decision: ReviewDecisionRecord | None = None
    evidence: ReviewSubjectEvidence | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("aggregate_id", self.aggregate_id),
            ("revision_id", self.revision_id),
            ("requested_by", self.requested_by),
        ):
            _uuid(name, value)
        validate_aggregate_type(self.aggregate_type)
        validate_manifest_sha256(self.manifest_sha256)
        _non_blank("required_role", self.required_role, 100)
        if self.requested_by_display_name is not None:
            _non_blank("requested_by_display_name", self.requested_by_display_name, 255)
        _non_blank("reason", self.reason, 2000)
        _aware("requested_at", self.requested_at)
        if self.evidence is not None:
            if (
                self.evidence.subject_type != self.aggregate_type
                or self.evidence.subject_id != self.aggregate_id
                or self.evidence.subject_revision_id != self.revision_id
                or self.evidence.classification is not self.classification
                or self.evidence.server_manifest_sha256 != self.manifest_sha256
            ):
                raise InvalidReview("subject evidence does not match the immutable review target")


@dataclass(frozen=True, slots=True)
class ReviewDecisionRecord:
    id: UUID
    review_request_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    aggregate_type: str
    aggregate_id: UUID
    revision_id: UUID
    manifest_sha256: str
    decision: ReviewDecisionKind
    decided_by: UUID
    decided_at: datetime
    reason: str

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("review_request_id", self.review_request_id),
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("aggregate_id", self.aggregate_id),
            ("revision_id", self.revision_id),
            ("decided_by", self.decided_by),
        ):
            _uuid(name, value)
        validate_aggregate_type(self.aggregate_type)
        validate_manifest_sha256(self.manifest_sha256)
        _non_blank("reason", self.reason, 2000)
        _aware("decided_at", self.decided_at)


@dataclass(frozen=True, slots=True)
class SubmitReviewRequest:
    classification: DataClassification | None
    aggregate_type: str
    aggregate_id: UUID
    revision_id: UUID
    manifest_sha256: str | None
    reason: str
    evidence: ReviewSubjectEvidence | None = None

    def __post_init__(self) -> None:
        validate_aggregate_type(self.aggregate_type)
        if self.classification is not None and self.manifest_sha256 is not None:
            validate_manifest_sha256(self.manifest_sha256)
        elif self.classification is not None or self.manifest_sha256 is not None:
            raise InvalidReview("classification and manifest_sha256 must be provided together")
        _uuid("aggregate_id", self.aggregate_id)
        _uuid("revision_id", self.revision_id)
        _non_blank("reason", self.reason, 2000)
        if self.evidence is not None:
            if self.classification is None or self.manifest_sha256 is None:
                raise InvalidReview(
                    "subject evidence requires resolved classification and manifest"
                )
            if (
                self.evidence.subject_type != self.aggregate_type
                or self.evidence.subject_id != self.aggregate_id
                or self.evidence.subject_revision_id != self.revision_id
                or self.evidence.classification is not self.classification
                or self.evidence.server_manifest_sha256 != self.manifest_sha256
            ):
                raise InvalidReview("subject evidence does not match the immutable review target")


@dataclass(frozen=True, slots=True)
class DecideReviewRequest:
    expected_manifest_sha256: str
    decision: ReviewDecisionKind
    reason: str

    def __post_init__(self) -> None:
        validate_manifest_sha256(self.expected_manifest_sha256)
        _non_blank("reason", self.reason, 2000)
