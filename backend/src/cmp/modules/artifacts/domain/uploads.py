"""Framework-free T-09 multipart upload and Raw Asset invariants."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import DataClassification

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ETAG = re.compile(r"^[\x21-\x7e]{1,255}$")
_FAILURE = re.compile(r"^[a-z][a-z0-9_]{0,99}$")


class UploadError(Exception):
    """Base T-09 upload error."""


class InvalidUpload(UploadError, ValueError):
    """Request metadata, part manifest, or completion facts are invalid."""


class UploadConflict(UploadError):
    """Idempotency key, part number, or terminal result conflicts."""


class UploadNotFound(UploadError):
    """Upload or Raw Asset is absent or hidden by tenant policy."""


class UploadAccessDenied(UploadError):
    """Classification or capability scope is not authorized."""


class UploadExpired(UploadError):
    """The short-lived upload capability is no longer valid."""


class UploadStateError(UploadError):
    """The requested operation is not valid in the current upload state."""


class ObjectStoreError(UploadError):
    """The multipart object-store boundary failed closed."""


class DigestMismatch(UploadError):
    """Completed object bytes differ from the immutable upload request."""


class UploadState(StrEnum):
    OPEN = "open"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RawAssetStorageState(StrEnum):
    """T-09 stops before T-10 content-addressed finalization."""

    STAGED_VERIFIED = "staged_verified"


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise ValueError(f"{name} must be non-zero")


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _trimmed(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{name} must be trimmed and contain 1..{maximum} characters")


@dataclass(frozen=True, slots=True)
class StoredPart:
    part_number: int
    size_bytes: int
    sha256: str
    etag: str

    def __post_init__(self) -> None:
        if not 1 <= self.part_number <= 100_000:
            raise ValueError("part_number must be between 1 and 100000")
        if self.size_bytes <= 0:
            raise ValueError("stored upload part must be non-empty")
        if _SHA256.fullmatch(self.sha256) is None or _ETAG.fullmatch(self.etag) is None:
            raise ValueError("stored upload part digest or etag is invalid")


@dataclass(frozen=True, slots=True)
class CompletedObject:
    object_key: str
    size_bytes: int
    sha256: str
    etag: str

    def __post_init__(self) -> None:
        _trimmed("object_key", self.object_key, 1024)
        if self.size_bytes <= 0 or _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("completed object size or digest is invalid")
        if _ETAG.fullmatch(self.etag) is None:
            raise ValueError("completed object etag is invalid")


@dataclass(frozen=True, slots=True)
class UploadPart:
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    upload_session_id: UUID
    part_number: int
    size_bytes: int
    sha256: str
    storage_etag: str
    recorded_at: datetime
    recorded_by: UUID

    def __post_init__(self) -> None:
        for name, value in (
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("upload_session_id", self.upload_session_id),
            ("recorded_by", self.recorded_by),
        ):
            _nonzero(name, value)
        StoredPart(self.part_number, self.size_bytes, self.sha256, self.storage_etag)
        _aware("recorded_at", self.recorded_at)

    def stored(self) -> StoredPart:
        return StoredPart(
            self.part_number,
            self.size_bytes,
            self.sha256,
            self.storage_etag,
        )


@dataclass(frozen=True, slots=True)
class UploadSession:
    id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    state: UploadState
    original_filename: str
    media_type: str
    expected_size_bytes: int
    expected_sha256: str
    part_size_bytes: int
    expected_part_count: int
    test_run_revision_id: UUID | None
    staging_object_key: str
    object_upload_id: str
    idempotency_key: str
    submission_digest: str
    created_at: datetime
    expires_at: datetime
    created_by: UUID
    request_id: UUID
    trace_id: str
    updated_at: datetime
    terminal_at: datetime | None
    raw_asset_id: UUID | None
    failure_code: str | None
    parts: tuple[UploadPart, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("created_by", self.created_by),
            ("request_id", self.request_id),
        ):
            _nonzero(name, value)
        if self.test_run_revision_id is not None:
            _nonzero("test_run_revision_id", self.test_run_revision_id)
        if any(separator in self.original_filename for separator in ("/", "\\")):
            raise ValueError("original_filename must not contain a path")
        _trimmed("original_filename", self.original_filename, 255)
        _trimmed("media_type", self.media_type, 255)
        _trimmed("staging_object_key", self.staging_object_key, 1024)
        _trimmed("object_upload_id", self.object_upload_id, 1024)
        _trimmed("idempotency_key", self.idempotency_key, 255)
        _trimmed("trace_id", self.trace_id, 255)
        if not 1 <= self.expected_size_bytes <= 9_223_372_036_854_775_807:
            raise ValueError("expected_size_bytes must be a positive bigint")
        if _SHA256.fullmatch(self.expected_sha256) is None or _SHA256.fullmatch(
            self.submission_digest
        ) is None:
            raise ValueError("upload digests must be lowercase SHA-256")
        if not 1 <= self.part_size_bytes <= self.expected_size_bytes:
            raise ValueError("part_size_bytes must fit the expected object size")
        calculated = (
            self.expected_size_bytes + self.part_size_bytes - 1
        ) // self.part_size_bytes
        if self.expected_part_count != calculated or not 1 <= calculated <= 100_000:
            raise ValueError("expected_part_count differs from size/part policy")
        _aware("created_at", self.created_at)
        _aware("expires_at", self.expires_at)
        _aware("updated_at", self.updated_at)
        if self.expires_at <= self.created_at or self.updated_at < self.created_at:
            raise ValueError("upload timestamps are inconsistent")
        terminal = self.state in {
            UploadState.COMPLETED,
            UploadState.FAILED,
            UploadState.CANCELLED,
        }
        if terminal != (self.terminal_at is not None):
            raise ValueError("terminal upload state and terminal_at must agree")
        if self.terminal_at is not None:
            _aware("terminal_at", self.terminal_at)
        if self.state is UploadState.COMPLETED:
            if self.raw_asset_id is None or self.failure_code is not None:
                raise ValueError("completed upload requires Raw Asset and no failure")
        elif self.raw_asset_id is not None:
            raise ValueError("only a completed upload may reference a Raw Asset")
        if self.state is UploadState.FAILED:
            if self.failure_code is None or _FAILURE.fullmatch(self.failure_code) is None:
                raise ValueError("failed upload requires a generic failure code")
        elif self.failure_code is not None:
            raise ValueError("only a failed upload may carry a failure code")
        if tuple(sorted(self.parts, key=lambda item: item.part_number)) != self.parts:
            raise ValueError("upload parts must be sorted")
        if len({item.part_number for item in self.parts}) != len(self.parts):
            raise ValueError("upload part numbers must be unique")

    def expected_part_size(self, part_number: int) -> int:
        if not 1 <= part_number <= self.expected_part_count:
            raise InvalidUpload("part_number is outside the immutable upload manifest")
        if part_number < self.expected_part_count:
            return self.part_size_bytes
        return self.expected_size_bytes - self.part_size_bytes * (
            self.expected_part_count - 1
        )

    @property
    def terminal(self) -> bool:
        return self.state in {
            UploadState.COMPLETED,
            UploadState.FAILED,
            UploadState.CANCELLED,
        }


@dataclass(frozen=True, slots=True)
class RawAsset:
    id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    sha256: str
    size_bytes: int
    media_type: str
    original_filename: str
    storage_state: RawAssetStorageState
    staging_object_key: str
    created_at: datetime
    created_by: UUID

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("created_by", self.created_by),
        ):
            _nonzero(name, value)
        if _SHA256.fullmatch(self.sha256) is None or self.size_bytes <= 0:
            raise ValueError("Raw Asset digest or size is invalid")
        if any(separator in self.original_filename for separator in ("/", "\\")):
            raise ValueError("Raw Asset filename must not contain a path")
        _trimmed("original_filename", self.original_filename, 255)
        _trimmed("media_type", self.media_type, 255)
        _trimmed("staging_object_key", self.staging_object_key, 1024)
        _aware("created_at", self.created_at)


@dataclass(frozen=True, slots=True)
class IngestionEvent:
    id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    raw_asset_id: UUID
    upload_session_id: UUID
    test_run_revision_id: UUID | None
    duplicate_content: bool
    occurred_at: datetime
    actor_id: UUID
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("raw_asset_id", self.raw_asset_id),
            ("upload_session_id", self.upload_session_id),
            ("actor_id", self.actor_id),
            ("request_id", self.request_id),
        ):
            _nonzero(name, value)
        if self.test_run_revision_id is not None:
            _nonzero("test_run_revision_id", self.test_run_revision_id)
        _aware("occurred_at", self.occurred_at)
        _trimmed("trace_id", self.trace_id, 255)
