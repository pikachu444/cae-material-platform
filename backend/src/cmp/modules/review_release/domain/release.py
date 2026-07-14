"""Typed T-30 release manifest and completeness-gate policy."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.shared.domain.revisions import content_sha256

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CODE = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")

RELEASE_SCHEMA_ID = "urn:cmp:governance:release:1.0.0"
RELEASE_SCHEMA_VERSION = "1.0.0"
RELEASE_CHANNEL = "reference"
RELEASE_STATE = "released"
RELEASE_PACKAGE_MEDIA_TYPE = "application/vnd.cmp.release-manifest+json"


class ReleaseError(Exception):
    """Base T-30 release error."""


class ReleaseNotFound(ReleaseError):
    """A release or one of its immutable inputs is not visible."""


class ReleaseConflict(ReleaseError):
    """The release completeness gate or immutable identity conflicts."""


class InvalidRelease(ReleaseError, ValueError):
    """A typed release command is invalid."""


class ReleaseState(StrEnum):
    RELEASED = "released"


class ReleaseLifecycleState(StrEnum):
    RELEASED = "released"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class ReleaseTransitionKind(StrEnum):
    SUPERSEDE = "supersede"
    WITHDRAW = "withdraw"


class ReleaseUsageKind(StrEnum):
    DOWNLOAD = "download"
    CONSUME = "consume"


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidRelease(f"{name} must be a non-zero UUID")


def _digest(name: str, value: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise InvalidRelease(f"{name} must be a lowercase SHA-256 hex digest")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidRelease(f"{name} must be trimmed and contain 1..{maximum} characters")


@dataclass(frozen=True, slots=True)
class CreateRelease:
    classification: DataClassification
    release_code: str
    title: str
    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    material_model_content_sha256: str
    solver_card_id: UUID
    solver_card_revision_id: UUID
    solver_card_content_sha256: str
    mapping_report_sha256: str
    card_sha256: str
    validation_result_id: UUID
    validation_result_sha256: str
    review_request_id: UUID
    review_manifest_sha256: str
    provenance_snapshot_sha256: str
    reason: str

    def __post_init__(self) -> None:
        _text("release_code", self.release_code, 100)
        if _CODE.fullmatch(self.release_code) is None:
            raise InvalidRelease("release_code must be a lowercase stable token")
        _text("title", self.title, 255)
        _text("reason", self.reason, 2000)
        for uuid_name, uuid_value in (
            ("material_id", self.material_id),
            ("material_revision_id", self.material_revision_id),
            ("material_state_id", self.material_state_id),
            ("material_state_revision_id", self.material_state_revision_id),
            ("property_set_id", self.property_set_id),
            ("property_set_revision_id", self.property_set_revision_id),
            ("material_model_id", self.material_model_id),
            ("material_model_revision_id", self.material_model_revision_id),
            ("solver_card_id", self.solver_card_id),
            ("solver_card_revision_id", self.solver_card_revision_id),
            ("validation_result_id", self.validation_result_id),
            ("review_request_id", self.review_request_id),
        ):
            _uuid(uuid_name, uuid_value)
        for digest_name, digest_value in (
            ("material_model_content_sha256", self.material_model_content_sha256),
            ("solver_card_content_sha256", self.solver_card_content_sha256),
            ("mapping_report_sha256", self.mapping_report_sha256),
            ("card_sha256", self.card_sha256),
            ("validation_result_sha256", self.validation_result_sha256),
            ("review_manifest_sha256", self.review_manifest_sha256),
            ("provenance_snapshot_sha256", self.provenance_snapshot_sha256),
        ):
            _digest(digest_name, digest_value)


def candidate_manifest_document(command: CreateRelease) -> dict[str, Any]:
    """Return the explicit reviewed candidate manifest, without release metadata."""

    return {
        "material": {
            "id": str(command.material_id),
            "revision_id": str(command.material_revision_id),
            "state_id": str(command.material_state_id),
            "state_revision_id": str(command.material_state_revision_id),
            "property_set_id": str(command.property_set_id),
            "property_set_revision_id": str(command.property_set_revision_id),
        },
        "material_model": {
            "id": str(command.material_model_id),
            "revision_id": str(command.material_model_revision_id),
            "content_sha256": command.material_model_content_sha256,
        },
        "solver_card": {
            "id": str(command.solver_card_id),
            "revision_id": str(command.solver_card_revision_id),
            "content_sha256": command.solver_card_content_sha256,
            "mapping_report_sha256": command.mapping_report_sha256,
            "card_sha256": command.card_sha256,
        },
        "validation_result": {
            "id": str(command.validation_result_id),
            "result_sha256": command.validation_result_sha256,
        },
        "provenance_snapshot_sha256": command.provenance_snapshot_sha256,
    }


def candidate_manifest_sha256(command: CreateRelease) -> str:
    return content_sha256(candidate_manifest_document(command))


@dataclass(frozen=True, slots=True)
class ReleaseManifestRecord:
    id: UUID
    release_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    manifest_sha256: str
    package_sha256: str
    package_size_bytes: int
    package_media_type: str
    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    material_model_content_sha256: str
    solver_card_id: UUID
    solver_card_revision_id: UUID
    solver_card_content_sha256: str
    mapping_report_sha256: str
    card_sha256: str
    validation_result_id: UUID
    validation_result_sha256: str
    review_request_id: UUID
    review_manifest_sha256: str
    provenance_snapshot_sha256: str
    created_at: datetime
    created_by: UUID
    reason: str
    state: ReleaseState = ReleaseState.RELEASED

    def __post_init__(self) -> None:
        for uuid_name, uuid_value in (
            ("id", self.id),
            ("release_id", self.release_id),
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("material_id", self.material_id),
            ("material_revision_id", self.material_revision_id),
            ("material_state_id", self.material_state_id),
            ("material_state_revision_id", self.material_state_revision_id),
            ("property_set_id", self.property_set_id),
            ("property_set_revision_id", self.property_set_revision_id),
            ("material_model_id", self.material_model_id),
            ("material_model_revision_id", self.material_model_revision_id),
            ("solver_card_id", self.solver_card_id),
            ("solver_card_revision_id", self.solver_card_revision_id),
            ("validation_result_id", self.validation_result_id),
            ("review_request_id", self.review_request_id),
            ("created_by", self.created_by),
        ):
            _uuid(uuid_name, uuid_value)
        for digest_name, digest_value in (
            ("manifest_sha256", self.manifest_sha256),
            ("package_sha256", self.package_sha256),
            ("material_model_content_sha256", self.material_model_content_sha256),
            ("solver_card_content_sha256", self.solver_card_content_sha256),
            ("mapping_report_sha256", self.mapping_report_sha256),
            ("card_sha256", self.card_sha256),
            ("validation_result_sha256", self.validation_result_sha256),
            ("review_manifest_sha256", self.review_manifest_sha256),
            ("provenance_snapshot_sha256", self.provenance_snapshot_sha256),
        ):
            _digest(digest_name, digest_value)
        if self.package_size_bytes <= 0:
            raise InvalidRelease("package_size_bytes must be positive")
        if self.state is not ReleaseState.RELEASED:
            raise InvalidRelease("release manifest must be released")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise InvalidRelease("created_at must be timezone-aware")
        _text("reason", self.reason, 2000)


@dataclass(frozen=True, slots=True)
class ReleaseRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    release_code: str
    title: str
    channel: str
    created_at: datetime
    created_by: UUID
    manifest: ReleaseManifestRecord
    package_text: str
    lifecycle_state: ReleaseLifecycleState = ReleaseLifecycleState.RELEASED

    def __post_init__(self) -> None:
        _uuid("id", self.id)
        _uuid("organization_id", self.organization_id)
        _uuid("project_id", self.project_id)
        _uuid("created_by", self.created_by)
        _text("release_code", self.release_code, 100)
        _text("title", self.title, 255)
        _text("channel", self.channel, 32)
        _text("package_text", self.package_text, 2_000_000)
        package_bytes = self.package_text.encode("utf-8")
        if len(package_bytes) != self.manifest.package_size_bytes:
            raise ReleaseConflict("release package size does not match its immutable manifest")
        if hashlib.sha256(package_bytes).hexdigest() != self.manifest.package_sha256:
            raise ReleaseConflict("release package digest does not match its immutable manifest")


@dataclass(frozen=True, slots=True)
class SupersedeRelease:
    successor_release_id: UUID
    reason: str

    def __post_init__(self) -> None:
        _uuid("successor_release_id", self.successor_release_id)
        _text("reason", self.reason, 2000)


@dataclass(frozen=True, slots=True)
class WithdrawRelease:
    reason: str

    def __post_init__(self) -> None:
        _text("reason", self.reason, 2000)


@dataclass(frozen=True, slots=True)
class RecordReleaseUsage:
    usage_kind: ReleaseUsageKind
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.usage_kind, ReleaseUsageKind):
            raise InvalidRelease("usage_kind must be a supported ReleaseUsageKind")
        _text("reason", self.reason, 2000)


@dataclass(frozen=True, slots=True)
class ReleaseTransitionRecord:
    id: UUID
    release_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    kind: ReleaseTransitionKind
    from_state: ReleaseLifecycleState
    to_state: ReleaseLifecycleState
    successor_release_id: UUID | None
    reason: str
    occurred_at: datetime
    occurred_by: UUID

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("release_id", self.release_id),
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("occurred_by", self.occurred_by),
        ):
            _uuid(name, value)
        if not isinstance(self.kind, ReleaseTransitionKind):
            raise InvalidRelease("kind must be a supported ReleaseTransitionKind")
        if not isinstance(self.from_state, ReleaseLifecycleState) or not isinstance(
            self.to_state, ReleaseLifecycleState
        ):
            raise InvalidRelease("transition states must be supported ReleaseLifecycleState values")
        if self.successor_release_id is not None:
            _uuid("successor_release_id", self.successor_release_id)
        if self.from_state is not ReleaseLifecycleState.RELEASED:
            raise InvalidRelease("release transitions must start from released")
        if self.kind is ReleaseTransitionKind.SUPERSEDE:
            if self.to_state is not ReleaseLifecycleState.SUPERSEDED:
                raise InvalidRelease("supersede transition must end in superseded")
            if self.successor_release_id is None:
                raise InvalidRelease("supersede transition requires a successor Release")
        elif self.kind is ReleaseTransitionKind.WITHDRAW:
            if self.to_state is not ReleaseLifecycleState.WITHDRAWN:
                raise InvalidRelease("withdraw transition must end in withdrawn")
            if self.successor_release_id is not None:
                raise InvalidRelease("withdraw transition cannot have a successor Release")
        _text("reason", self.reason, 2000)
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise InvalidRelease("occurred_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ReleaseUsageRecord:
    id: UUID
    release_id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    usage_kind: ReleaseUsageKind
    used_by: UUID
    used_at: datetime
    reason: str

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("release_id", self.release_id),
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("used_by", self.used_by),
        ):
            _uuid(name, value)
        if not isinstance(self.usage_kind, ReleaseUsageKind):
            raise InvalidRelease("usage_kind must be a supported ReleaseUsageKind")
        _text("reason", self.reason, 2000)
        if self.used_at.tzinfo is None or self.used_at.utcoffset() is None:
            raise InvalidRelease("used_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ReleaseImpactRecord:
    release: ReleaseRecord
    predecessor_release_id: UUID | None
    successor_release_id: UUID | None
    usages: tuple[ReleaseUsageRecord, ...]
    transitions: tuple[ReleaseTransitionRecord, ...] = ()
    warning: str | None = None


def release_manifest_document(command: CreateRelease, manifest_sha256: str) -> dict[str, Any]:
    return {
        "schema_id": RELEASE_SCHEMA_ID,
        "schema_version": RELEASE_SCHEMA_VERSION,
        "release_code": command.release_code,
        "title": command.title,
        "channel": RELEASE_CHANNEL,
        "state": RELEASE_STATE,
        "manifest_sha256": manifest_sha256,
        "candidate_manifest_sha256": candidate_manifest_sha256(command),
        "components": candidate_manifest_document(command),
        "review": {
            "review_request_id": str(command.review_request_id),
            "manifest_sha256": command.review_manifest_sha256,
        },
    }
