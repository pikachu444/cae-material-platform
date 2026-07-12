"""T-05 append-only audit values, canonical hashes, and integrity verification."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[a-z][a-z0-9_.-]{0,149}$")
_ACTION = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z0-9_-]+)+$")
GENESIS_HASH = "0" * 64


class AuditError(Exception):
    """Base error for audit operations."""


class InvalidAuditEvent(AuditError, ValueError):
    """An audit value violates the public and persistence contract."""


class AuditConflict(AuditError):
    """The requested audit operation conflicts with immutable chain state."""


class AuditActorType(StrEnum):
    USER = "user"
    SERVICE = "service"


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


class AuditIntegrityState(StrEnum):
    VALID = "valid"
    INVALID = "invalid"


class AuditIntegrityIssueCode(StrEnum):
    EVENT_SEQUENCE_GAP = "event_sequence_gap"
    EVENT_PREVIOUS_HASH_MISMATCH = "event_previous_hash_mismatch"
    EVENT_HASH_MISMATCH = "event_hash_mismatch"
    SEGMENT_SEQUENCE_GAP = "segment_sequence_gap"
    SEGMENT_RANGE_GAP = "segment_range_gap"
    SEGMENT_EVENT_MISSING = "segment_event_missing"
    SEGMENT_EVENT_HASH_MISMATCH = "segment_event_hash_mismatch"
    SEGMENT_PREVIOUS_ROOT_MISMATCH = "segment_previous_root_mismatch"
    SEGMENT_ROOT_HASH_MISMATCH = "segment_root_hash_mismatch"


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidAuditEvent(f"{name} must be non-zero")


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidAuditEvent(f"{name} must be timezone-aware")


def _token(name: str, value: str) -> None:
    if _TOKEN.fullmatch(value) is None:
        raise InvalidAuditEvent(f"{name} must be a stable token")


def _action(value: str) -> None:
    if len(value) > 150 or _ACTION.fullmatch(value) is None:
        raise InvalidAuditEvent("action must be a namespaced stable token")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidAuditEvent(
            f"{name} must be trimmed and contain 1..{maximum} characters"
        )


def _digest(name: str, value: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise InvalidAuditEvent(f"{name} must be a lowercase SHA-256 digest")


def redact_ip_or_client(value: str | None) -> str:
    """Never persist a raw network address or caller-controlled client identifier."""

    del value
    return "policy-redacted"


@dataclass(frozen=True, slots=True)
class AuditScope:
    organization_id: UUID
    project_id: UUID

    def __post_init__(self) -> None:
        _nonzero("organization_id", self.organization_id)
        _nonzero("project_id", self.project_id)


@dataclass(frozen=True, slots=True)
class AuditEventDraft:
    id: UUID
    scope: AuditScope
    occurred_at: datetime
    actor_type: AuditActorType
    actor_id: UUID
    action: str
    target_type: str
    target_id: UUID | None
    outcome: AuditOutcome
    request_id: UUID
    trace_id: str
    ip_or_client: str
    reason: str

    def __post_init__(self) -> None:
        _nonzero("event id", self.id)
        _aware("occurred_at", self.occurred_at)
        _nonzero("actor_id", self.actor_id)
        _action(self.action)
        _token("target_type", self.target_type)
        if self.target_id is not None:
            _nonzero("target_id", self.target_id)
        _nonzero("request_id", self.request_id)
        _text("trace_id", self.trace_id, 255)
        if self.ip_or_client != "policy-redacted":
            raise InvalidAuditEvent("ip_or_client must be policy-redacted before persistence")
        _text("reason", self.reason, 2000)


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: UUID
    scope: AuditScope
    sequence_no: int
    occurred_at: datetime
    recorded_at: datetime
    actor_type: AuditActorType
    actor_id: UUID
    action: str
    target_type: str
    target_id: UUID | None
    outcome: AuditOutcome
    request_id: UUID
    trace_id: str
    ip_or_client: str
    reason: str
    previous_hash: str
    event_hash: str

    def __post_init__(self) -> None:
        AuditEventDraft(
            id=self.id,
            scope=self.scope,
            occurred_at=self.occurred_at,
            actor_type=self.actor_type,
            actor_id=self.actor_id,
            action=self.action,
            target_type=self.target_type,
            target_id=self.target_id,
            outcome=self.outcome,
            request_id=self.request_id,
            trace_id=self.trace_id,
            ip_or_client=self.ip_or_client,
            reason=self.reason,
        )
        if self.sequence_no <= 0:
            raise InvalidAuditEvent("sequence_no must be positive")
        _aware("recorded_at", self.recorded_at)
        _digest("previous_hash", self.previous_hash)
        _digest("event_hash", self.event_hash)


@dataclass(frozen=True, slots=True)
class AuditSegmentRoot:
    id: UUID
    scope: AuditScope
    segment_no: int
    first_sequence_no: int
    last_sequence_no: int
    event_count: int
    first_event_hash: str
    last_event_hash: str
    previous_root_hash: str
    root_hash: str
    created_at: datetime
    created_by: UUID
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        _nonzero("segment root id", self.id)
        if self.segment_no <= 0:
            raise InvalidAuditEvent("segment_no must be positive")
        if self.first_sequence_no <= 0 or self.last_sequence_no < self.first_sequence_no:
            raise InvalidAuditEvent("segment sequence range is invalid")
        if self.event_count != self.last_sequence_no - self.first_sequence_no + 1:
            raise InvalidAuditEvent("segment event_count must equal its contiguous range")
        for name, value in (
            ("first_event_hash", self.first_event_hash),
            ("last_event_hash", self.last_event_hash),
            ("previous_root_hash", self.previous_root_hash),
            ("root_hash", self.root_hash),
        ):
            _digest(name, value)
        _aware("created_at", self.created_at)
        _nonzero("created_by", self.created_by)
        _nonzero("request_id", self.request_id)
        _text("trace_id", self.trace_id, 255)


def _timestamp(value: datetime) -> str:
    _aware("hash timestamp", value)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _frame(value: object | None) -> bytes:
    if value is None:
        return b"-1:"
    rendered = str(value).encode("utf-8")
    return str(len(rendered)).encode("ascii") + b":" + rendered


def canonical_event_bytes(value: AuditEvent) -> bytes:
    """Return the versioned, length-framed bytes mirrored by PostgreSQL."""

    fields: tuple[object | None, ...] = (
        "cmp-audit-event-v1",
        value.scope.organization_id,
        value.scope.project_id,
        value.sequence_no,
        value.id,
        _timestamp(value.occurred_at),
        _timestamp(value.recorded_at),
        value.actor_type.value,
        value.actor_id,
        value.action,
        value.target_type,
        value.target_id,
        value.outcome.value,
        value.request_id,
        value.trace_id,
        value.ip_or_client,
        value.reason,
        value.previous_hash,
    )
    return b"".join(_frame(field) for field in fields)


def canonical_segment_root_bytes(value: AuditSegmentRoot) -> bytes:
    fields: tuple[object | None, ...] = (
        "cmp-audit-segment-v1",
        value.scope.organization_id,
        value.scope.project_id,
        value.segment_no,
        value.first_sequence_no,
        value.last_sequence_no,
        value.event_count,
        value.first_event_hash,
        value.last_event_hash,
        value.previous_root_hash,
        _timestamp(value.created_at),
        value.created_by,
        value.request_id,
        value.trace_id,
    )
    return b"".join(_frame(field) for field in fields)


def event_sha256(value: AuditEvent) -> str:
    return hashlib.sha256(canonical_event_bytes(value)).hexdigest()


def segment_root_sha256(value: AuditSegmentRoot) -> str:
    return hashlib.sha256(canonical_segment_root_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class AuditIntegrityIssue:
    code: AuditIntegrityIssueCode
    event_sequence_no: int | None = None
    segment_no: int | None = None


@dataclass(frozen=True, slots=True)
class AuditIntegrityReport:
    state: AuditIntegrityState
    event_count: int
    last_sequence_no: int
    segment_count: int
    sealed_through_sequence_no: int
    unsealed_event_count: int
    issues: tuple[AuditIntegrityIssue, ...]


def verify_audit_integrity(
    events: tuple[AuditEvent, ...],
    segment_roots: tuple[AuditSegmentRoot, ...] = (),
) -> AuditIntegrityReport:
    """Detect event mutation/reorder/delete and invalid or disconnected segment roots."""

    issues: list[AuditIntegrityIssue] = []
    expected_previous = GENESIS_HASH
    events_by_sequence: dict[int, AuditEvent] = {}
    for expected_sequence, event in enumerate(events, start=1):
        events_by_sequence[event.sequence_no] = event
        if event.sequence_no != expected_sequence:
            issues.append(
                AuditIntegrityIssue(
                    AuditIntegrityIssueCode.EVENT_SEQUENCE_GAP,
                    event_sequence_no=event.sequence_no,
                )
            )
        if event.previous_hash != expected_previous:
            issues.append(
                AuditIntegrityIssue(
                    AuditIntegrityIssueCode.EVENT_PREVIOUS_HASH_MISMATCH,
                    event_sequence_no=event.sequence_no,
                )
            )
        if event.event_hash != event_sha256(event):
            issues.append(
                AuditIntegrityIssue(
                    AuditIntegrityIssueCode.EVENT_HASH_MISMATCH,
                    event_sequence_no=event.sequence_no,
                )
            )
        expected_previous = event.event_hash

    expected_segment = 1
    expected_first = 1
    expected_root = GENESIS_HASH
    sealed_through = 0
    for root in segment_roots:
        if root.segment_no != expected_segment:
            issues.append(
                AuditIntegrityIssue(
                    AuditIntegrityIssueCode.SEGMENT_SEQUENCE_GAP,
                    segment_no=root.segment_no,
                )
            )
        if root.first_sequence_no != expected_first:
            issues.append(
                AuditIntegrityIssue(
                    AuditIntegrityIssueCode.SEGMENT_RANGE_GAP,
                    segment_no=root.segment_no,
                )
            )
        first = events_by_sequence.get(root.first_sequence_no)
        last = events_by_sequence.get(root.last_sequence_no)
        observed_segment_count = sum(
            root.first_sequence_no <= sequence <= root.last_sequence_no
            for sequence in events_by_sequence
        )
        if first is None or last is None or observed_segment_count != root.event_count:
            issues.append(
                AuditIntegrityIssue(
                    AuditIntegrityIssueCode.SEGMENT_EVENT_MISSING,
                    segment_no=root.segment_no,
                )
            )
        elif (
            root.first_event_hash != first.event_hash
            or root.last_event_hash != last.event_hash
        ):
            issues.append(
                AuditIntegrityIssue(
                    AuditIntegrityIssueCode.SEGMENT_EVENT_HASH_MISMATCH,
                    segment_no=root.segment_no,
                )
            )
        if root.previous_root_hash != expected_root:
            issues.append(
                AuditIntegrityIssue(
                    AuditIntegrityIssueCode.SEGMENT_PREVIOUS_ROOT_MISMATCH,
                    segment_no=root.segment_no,
                )
            )
        if root.root_hash != segment_root_sha256(root):
            issues.append(
                AuditIntegrityIssue(
                    AuditIntegrityIssueCode.SEGMENT_ROOT_HASH_MISMATCH,
                    segment_no=root.segment_no,
                )
            )
        expected_segment = root.segment_no + 1
        expected_first = root.last_sequence_no + 1
        expected_root = root.root_hash
        sealed_through = max(sealed_through, root.last_sequence_no)

    last_sequence = max(events_by_sequence, default=0)
    return AuditIntegrityReport(
        state=(AuditIntegrityState.INVALID if issues else AuditIntegrityState.VALID),
        event_count=len(events),
        last_sequence_no=last_sequence,
        segment_count=len(segment_roots),
        sealed_through_sequence_no=sealed_through,
        unsealed_event_count=max(0, last_sequence - sealed_through),
        issues=tuple(issues),
    )
