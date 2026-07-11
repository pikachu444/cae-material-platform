"""Framework-free primitives for T-06 immutable aggregate revisions.

The kernel deliberately models revision metadata only.  Typed bounded modules own their
content columns and validation; this module never persists arbitrary key/value content.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

type CanonicalJson = (
    None
    | bool
    | int
    | float
    | str
    | list["CanonicalJson"]
    | dict[str, "CanonicalJson"]
)

_AGGREGATE_TYPE = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_CLASSIFICATION = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class RevisionKernelError(Exception):
    """Base error for revision-kernel commands."""


class CanonicalizationError(RevisionKernelError, ValueError):
    """Raised when content is not in the supported JSON value domain."""


class InvalidRevisionReference(RevisionKernelError, ValueError):
    """Raised when a caller supplies a moving alias instead of a UUID revision."""


class InvalidRevisionCommand(RevisionKernelError, ValueError):
    """Raised before persistence when a revision command violates an invariant."""


class AggregateAlreadyExists(RevisionKernelError):
    """Raised when create targets an existing stable aggregate identity."""


class AggregateNotFound(RevisionKernelError):
    """Raised without revealing whether an aggregate exists in another tenant."""


@dataclass(frozen=True, slots=True)
class RevisionRef:
    """A concrete immutable revision reference suitable for downstream inputs."""

    revision_id: UUID
    revision_no: int
    content_hash: str

    def __post_init__(self) -> None:
        if self.revision_no < 1:
            raise ValueError("revision_no must be positive")
        if not _SHA256.fullmatch(self.content_hash):
            raise ValueError("content_hash must be a lowercase SHA-256 hex digest")


class RevisionConflict(RevisionKernelError):
    """Raised when optimistic concurrency observes a different aggregate head."""

    def __init__(self, expected_revision_id: UUID, current: RevisionRef) -> None:
        self.expected_revision_id = expected_revision_id
        self.current = current
        super().__init__(
            "stale aggregate head: "
            f"expected {expected_revision_id}, current is {current.revision_id}"
        )


class TenantScopeMismatch(RevisionKernelError):
    """Raised if one database transaction attempts to mix tenant contexts."""


def _non_blank(name: str, value: str, *, maximum: int | None = None) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-blank and trimmed")
    if maximum is not None and len(value) > maximum:
        raise ValueError(f"{name} must contain at most {maximum} characters")


def _normalize_json(value: object, path: str = "$") -> CanonicalJson:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalizationError(f"{path}: NaN and Infinity are not valid JSON")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, CanonicalJson] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError(f"{path}: object keys must be strings")
            normalized[key] = _normalize_json(item, f"{path}/{key}")
        return normalized
    if isinstance(value, (list, tuple)):
        return [_normalize_json(item, f"{path}/{index}") for index, item in enumerate(value)]
    raise CanonicalizationError(
        f"{path}: {type(value).__name__} requires an explicit typed-to-JSON mapping"
    )


def canonical_json_bytes(value: object) -> bytes:
    """Serialize CMP canonical JSON v1 for deterministic content hashing.

    V1 accepts only JSON primitives, string-keyed mappings, lists, and tuples.  Keys are
    ordered, insignificant whitespace is removed, UTF-8 is preserved, and non-finite numbers
    are rejected.  Domain codecs must explicitly map UUID, datetime, Decimal, and custom types.
    """

    normalized = _normalize_json(value)
    return json.dumps(
        normalized,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def content_sha256(value: object) -> str:
    """Return the SHA-256 digest of CMP canonical JSON v1."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def concrete_revision_id(value: UUID | str) -> UUID:
    """Accept only a concrete UUID and reject moving aliases such as ``latest``."""

    if isinstance(value, UUID):
        return value
    try:
        return UUID(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise InvalidRevisionReference("revision input must be a concrete UUID") from error


@dataclass(frozen=True, slots=True)
class TenantScope:
    """Organization/project ownership propagated to every revision write."""

    organization_id: UUID
    project_id: UUID
    classification: str

    def __post_init__(self) -> None:
        if not _CLASSIFICATION.fullmatch(self.classification):
            raise ValueError("classification must be a stable, namespaced token")


@dataclass(frozen=True, slots=True)
class RevisionDraft[ContentT]:
    """Persistence-ready revision data before its monotonic number is assigned."""

    revision_id: UUID
    aggregate_type: str
    aggregate_id: UUID
    scope: TenantScope
    schema_id: str
    schema_version: str
    content: ContentT
    content_hash: str
    created_at: datetime
    created_by: UUID
    change_reason: str
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        if not _AGGREGATE_TYPE.fullmatch(self.aggregate_type):
            raise ValueError("aggregate_type must be a stable, namespaced token")
        _non_blank("schema_id", self.schema_id, maximum=255)
        _non_blank("schema_version", self.schema_version, maximum=64)
        _non_blank("change_reason", self.change_reason, maximum=2000)
        _non_blank("trace_id", self.trace_id, maximum=255)
        if not _SHA256.fullmatch(self.content_hash):
            raise ValueError("content_hash must be a lowercase SHA-256 hex digest")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class RevisionRecord:
    """Metadata for one immutable row in a bounded module's typed revision table."""

    revision_id: UUID
    aggregate_type: str
    aggregate_id: UUID
    scope: TenantScope
    revision_no: int
    based_on_revision_id: UUID | None
    schema_id: str
    schema_version: str
    content_hash: str
    created_at: datetime
    created_by: UUID
    change_reason: str
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        if self.revision_no < 1:
            raise ValueError("revision_no must be positive")
        if (self.revision_no == 1) != (self.based_on_revision_id is None):
            raise ValueError("only revision 1 may omit based_on_revision_id")
        if not _AGGREGATE_TYPE.fullmatch(self.aggregate_type):
            raise ValueError("aggregate_type must be a stable, namespaced token")
        _non_blank("schema_id", self.schema_id, maximum=255)
        _non_blank("schema_version", self.schema_version, maximum=64)
        _non_blank("change_reason", self.change_reason, maximum=2000)
        _non_blank("trace_id", self.trace_id, maximum=255)
        if not _SHA256.fullmatch(self.content_hash):
            raise ValueError("content_hash must be a lowercase SHA-256 hex digest")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")

    @property
    def ref(self) -> RevisionRef:
        return RevisionRef(self.revision_id, self.revision_no, self.content_hash)


@dataclass(frozen=True, slots=True)
class RevisionCreated:
    """Transaction-local hook payload for provenance, audit, lifecycle, and outbox adapters."""

    revision: RevisionRecord
    lifecycle_state: str

    def __post_init__(self) -> None:
        _non_blank("lifecycle_state", self.lifecycle_state, maximum=64)
