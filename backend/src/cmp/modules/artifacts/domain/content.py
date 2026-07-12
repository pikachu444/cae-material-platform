"""Framework-free T-10 immutable Artifact and integrity invariants."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import DataClassification

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ROLE = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_CODE = re.compile(r"^[a-z][a-z0-9_]{0,99}$")
_ETAG = re.compile(r"^[\x21-\x7e]{1,255}$")


class ArtifactError(Exception):
    """Base T-10 artifact error."""


class InvalidArtifact(ArtifactError, ValueError):
    """An Artifact manifest, content key, or transfer request is invalid."""


class ArtifactConflict(ArtifactError):
    """An idempotency key or immutable Artifact identity conflicts."""


class ArtifactNotFound(ArtifactError):
    """An Artifact is absent or hidden by tenant policy."""


class ArtifactAccessDenied(ArtifactError):
    """An Artifact capability or classification is not authorized."""


class ArtifactTransferExpired(ArtifactError):
    """A short-lived Artifact transfer capability expired."""


class ArtifactStateError(ArtifactError):
    """A finalization command is invalid for the pending state."""


class ArtifactIntegrityError(ArtifactError):
    """Stored bytes do not match the immutable Artifact manifest."""


class ArtifactKind(StrEnum):
    RAW = "raw"
    DERIVED = "derived"
    RELEASE = "release"


class PendingArtifactState(StrEnum):
    PENDING = "pending"
    PROMOTING = "promoting"
    AVAILABLE = "available"
    RETRYABLE = "retryable"
    REJECTED = "rejected"


class IntegrityStatus(StrEnum):
    VERIFIED = "verified"
    MISSING = "missing"
    CORRUPT = "corrupt"


class IntegrityCheckKind(StrEnum):
    FINALIZATION = "finalization"
    RECONCILIATION = "reconciliation"
    DOWNLOAD = "download"


class ReconciliationIssueType(StrEnum):
    ORPHAN_OBJECT = "orphan_object"
    PENDING_MISSING_STAGING = "pending_missing_staging"
    PENDING_STAGING_CORRUPT = "pending_staging_corrupt"
    PENDING_FINAL_CORRUPT = "pending_final_corrupt"


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise ValueError(f"{name} must be non-zero")


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _trimmed(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{name} must be trimmed and contain 1..{maximum} characters")


def _digest(name: str, value: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256")


def content_object_key(
    organization_id: UUID,
    project_id: UUID,
    classification: DataClassification,
    sha256: str,
) -> str:
    """Return the deterministic tenant/classification-scoped content key."""

    _nonzero("organization_id", organization_id)
    _nonzero("project_id", project_id)
    _digest("sha256", sha256)
    return (
        f"final/{organization_id}/{project_id}/{classification.value}/sha256/"
        f"{sha256[:2]}/{sha256[2:4]}/{sha256}"
    )


def parse_content_object_key(
    value: str,
) -> tuple[UUID, UUID, DataClassification, str]:
    """Parse only the exact canonical key form produced by ``content_object_key``."""

    parts = value.split("/")
    if len(parts) != 8 or parts[0] != "final" or parts[4] != "sha256":
        raise InvalidArtifact("object key is not a canonical content key")
    try:
        organization_id = UUID(parts[1])
        project_id = UUID(parts[2])
        classification = DataClassification(parts[3])
    except ValueError as error:
        raise InvalidArtifact("object key tenant scope is invalid") from error
    sha256 = parts[7]
    expected = content_object_key(
        organization_id, project_id, classification, sha256
    )
    if value != expected or parts[5] != sha256[:2] or parts[6] != sha256[2:4]:
        raise InvalidArtifact("object key is not canonical for its digest")
    return organization_id, project_id, classification, sha256


@dataclass(frozen=True, slots=True)
class StoredObject:
    object_key: str
    size_bytes: int
    sha256: str
    etag: str
    version_id: str

    def __post_init__(self) -> None:
        _trimmed("object_key", self.object_key, 1024)
        if self.size_bytes < 0:
            raise ValueError("stored object size must be non-negative")
        _digest("stored object sha256", self.sha256)
        if _ETAG.fullmatch(self.etag) is None:
            raise ValueError("stored object etag is invalid")
        _trimmed("version_id", self.version_id, 1024)


@dataclass(frozen=True, slots=True)
class PendingArtifact:
    id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    state: PendingArtifactState
    artifact_kind: ArtifactKind
    artifact_role: str
    schema_ref: str | None
    media_type: str
    expected_size_bytes: int
    expected_sha256: str
    staging_object_key: str
    final_object_key: str
    encryption_profile: str
    source_raw_asset_id: UUID | None
    idempotency_key: str
    submission_digest: str
    reserved_artifact_id: UUID
    available_artifact_id: UUID | None
    attempt_count: int
    failure_code: str | None
    created_at: datetime
    created_by: UUID
    request_id: UUID
    trace_id: str
    updated_at: datetime
    terminal_at: datetime | None

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("reserved_artifact_id", self.reserved_artifact_id),
            ("created_by", self.created_by),
            ("request_id", self.request_id),
        ):
            _nonzero(name, value)
        if self.source_raw_asset_id is not None:
            _nonzero("source_raw_asset_id", self.source_raw_asset_id)
        if self.artifact_kind is ArtifactKind.RAW:
            if self.source_raw_asset_id is None or self.schema_ref is not None:
                raise ValueError("raw Artifact requires a Raw Asset and no schema_ref")
        elif self.source_raw_asset_id is not None or self.schema_ref is None:
            raise ValueError("non-raw Artifact requires schema_ref and no Raw Asset source")
        if _ROLE.fullmatch(self.artifact_role) is None:
            raise ValueError("artifact_role is invalid")
        if self.schema_ref is not None:
            _trimmed("schema_ref", self.schema_ref, 500)
        _trimmed("media_type", self.media_type, 255)
        if not 0 <= self.expected_size_bytes <= 9_223_372_036_854_775_807:
            raise ValueError("expected_size_bytes must fit a non-negative bigint")
        _digest("expected_sha256", self.expected_sha256)
        _trimmed("staging_object_key", self.staging_object_key, 1024)
        _trimmed("final_object_key", self.final_object_key, 1024)
        if self.final_object_key != content_object_key(
            self.organization_id,
            self.project_id,
            self.classification,
            self.expected_sha256,
        ):
            raise ValueError("final_object_key differs from the content manifest")
        _trimmed("encryption_profile", self.encryption_profile, 255)
        _trimmed("idempotency_key", self.idempotency_key, 255)
        _digest("submission_digest", self.submission_digest)
        if self.available_artifact_id is not None:
            _nonzero("available_artifact_id", self.available_artifact_id)
        if not 0 <= self.attempt_count <= 2_147_483_647:
            raise ValueError("attempt_count is invalid")
        _aware("created_at", self.created_at)
        _aware("updated_at", self.updated_at)
        if self.updated_at < self.created_at:
            raise ValueError("pending Artifact time moved backwards")
        _trimmed("trace_id", self.trace_id, 255)
        if self.terminal_at is not None:
            _aware("terminal_at", self.terminal_at)
        terminal = self.state in {
            PendingArtifactState.AVAILABLE,
            PendingArtifactState.REJECTED,
        }
        if terminal != (self.terminal_at is not None):
            raise ValueError("pending Artifact terminal state and time differ")
        if self.state is PendingArtifactState.AVAILABLE:
            if (
                self.available_artifact_id != self.reserved_artifact_id
                or self.failure_code is not None
                or self.attempt_count < 1
            ):
                raise ValueError("available pending Artifact facts are inconsistent")
        elif self.available_artifact_id is not None:
            raise ValueError("only available pending Artifact may reference an Artifact")
        if self.state in {
            PendingArtifactState.RETRYABLE,
            PendingArtifactState.REJECTED,
        }:
            if self.failure_code is None or _CODE.fullmatch(self.failure_code) is None:
                raise ValueError("failed pending Artifact requires a bounded failure code")
        elif self.failure_code is not None:
            raise ValueError("active/available pending Artifact cannot carry failure")
        if self.state is PendingArtifactState.PENDING and self.attempt_count != 0:
            raise ValueError("new pending Artifact cannot have promotion attempts")
        if self.state is not PendingArtifactState.PENDING and self.attempt_count < 1:
            raise ValueError("started pending Artifact requires a promotion attempt")


@dataclass(frozen=True, slots=True)
class Artifact:
    id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    artifact_kind: ArtifactKind
    artifact_role: str
    schema_ref: str | None
    media_type: str
    size_bytes: int
    sha256: str
    storage_key: str
    encryption_profile: str
    source_raw_asset_id: UUID | None
    source_pending_id: UUID
    created_at: datetime
    created_by: UUID

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("source_pending_id", self.source_pending_id),
            ("created_by", self.created_by),
        ):
            _nonzero(name, value)
        if self.source_raw_asset_id is not None:
            _nonzero("source_raw_asset_id", self.source_raw_asset_id)
        if self.artifact_kind is ArtifactKind.RAW:
            if self.source_raw_asset_id is None or self.schema_ref is not None:
                raise ValueError("raw Artifact source/schema facts are invalid")
        elif self.source_raw_asset_id is not None or self.schema_ref is None:
            raise ValueError("non-raw Artifact source/schema facts are invalid")
        if _ROLE.fullmatch(self.artifact_role) is None:
            raise ValueError("artifact_role is invalid")
        if self.schema_ref is not None:
            _trimmed("schema_ref", self.schema_ref, 500)
        _trimmed("media_type", self.media_type, 255)
        if not 0 <= self.size_bytes <= 9_223_372_036_854_775_807:
            raise ValueError("Artifact size must fit a non-negative bigint")
        _digest("Artifact sha256", self.sha256)
        if self.storage_key != content_object_key(
            self.organization_id,
            self.project_id,
            self.classification,
            self.sha256,
        ):
            raise ValueError("Artifact storage key differs from its content identity")
        _trimmed("encryption_profile", self.encryption_profile, 255)
        _aware("created_at", self.created_at)


@dataclass(frozen=True, slots=True)
class IntegrityObservation:
    id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    artifact_id: UUID
    check_kind: IntegrityCheckKind
    status: IntegrityStatus
    expected_sha256: str
    expected_size_bytes: int
    observed_sha256: str | None
    observed_size_bytes: int | None
    object_version_id: str | None
    checked_at: datetime
    checked_by: UUID
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("artifact_id", self.artifact_id),
            ("checked_by", self.checked_by),
            ("request_id", self.request_id),
        ):
            _nonzero(name, value)
        _digest("expected_sha256", self.expected_sha256)
        if self.expected_size_bytes < 0:
            raise ValueError("expected_size_bytes must be non-negative")
        if self.observed_sha256 is not None:
            _digest("observed_sha256", self.observed_sha256)
        if self.observed_size_bytes is not None and self.observed_size_bytes < 0:
            raise ValueError("observed_size_bytes must be non-negative")
        if self.object_version_id is not None:
            _trimmed("object_version_id", self.object_version_id, 1024)
        observed = (self.observed_sha256, self.observed_size_bytes)
        if self.status is IntegrityStatus.VERIFIED:
            if observed != (self.expected_sha256, self.expected_size_bytes):
                raise ValueError("verified observation must match the Artifact")
        elif self.status is IntegrityStatus.MISSING:
            if observed != (None, None) or self.object_version_id is not None:
                raise ValueError("missing observation cannot claim stored bytes")
        elif (
            self.observed_sha256 is None
            or self.observed_size_bytes is None
            or observed == (self.expected_sha256, self.expected_size_bytes)
        ):
            raise ValueError("corrupt observation must identify a mismatch")
        _aware("checked_at", self.checked_at)
        _trimmed("trace_id", self.trace_id, 255)


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact: Artifact
    integrity_status: IntegrityStatus
    last_checked_at: datetime
    last_observation_id: UUID

    def __post_init__(self) -> None:
        _aware("last_checked_at", self.last_checked_at)
        _nonzero("last_observation_id", self.last_observation_id)


@dataclass(frozen=True, slots=True)
class ReconciliationIssue:
    id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    issue_type: ReconciliationIssueType
    artifact_id: UUID | None
    pending_artifact_id: UUID | None
    object_key: str
    expected_sha256: str | None
    expected_size_bytes: int | None
    observed_sha256: str | None
    observed_size_bytes: int | None
    detected_at: datetime
    detected_by: UUID
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("detected_by", self.detected_by),
            ("request_id", self.request_id),
        ):
            _nonzero(name, value)
        if self.artifact_id is not None:
            _nonzero("artifact_id", self.artifact_id)
        if self.pending_artifact_id is not None:
            _nonzero("pending_artifact_id", self.pending_artifact_id)
        if self.issue_type is ReconciliationIssueType.ORPHAN_OBJECT:
            if self.artifact_id is not None or self.pending_artifact_id is not None:
                raise ValueError("orphan issue cannot reference DB resources")
        elif self.pending_artifact_id is None:
            raise ValueError("pending reconciliation issue requires a pending Artifact")
        _trimmed("object_key", self.object_key, 1024)
        for name, digest_value in (
            ("expected_sha256", self.expected_sha256),
            ("observed_sha256", self.observed_sha256),
        ):
            if digest_value is not None:
                _digest(name, digest_value)
        for name, size_value in (
            ("expected_size_bytes", self.expected_size_bytes),
            ("observed_size_bytes", self.observed_size_bytes),
        ):
            if size_value is not None and size_value < 0:
                raise ValueError(f"{name} must be non-negative")
        _aware("detected_at", self.detected_at)
        _trimmed("trace_id", self.trace_id, 255)
