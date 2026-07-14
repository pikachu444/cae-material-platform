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
    decision: ReviewDecisionRecord | None = None

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
        _non_blank("reason", self.reason, 2000)
        _aware("requested_at", self.requested_at)


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
    classification: DataClassification
    aggregate_type: str
    aggregate_id: UUID
    revision_id: UUID
    manifest_sha256: str
    reason: str

    def __post_init__(self) -> None:
        validate_aggregate_type(self.aggregate_type)
        validate_manifest_sha256(self.manifest_sha256)
        _uuid("aggregate_id", self.aggregate_id)
        _uuid("revision_id", self.revision_id)
        _non_blank("reason", self.reason, 2000)


@dataclass(frozen=True, slots=True)
class DecideReviewRequest:
    expected_manifest_sha256: str
    decision: ReviewDecisionKind
    reason: str

    def __post_init__(self) -> None:
        validate_manifest_sha256(self.expected_manifest_sha256)
        _non_blank("reason", self.reason, 2000)
