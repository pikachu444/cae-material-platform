"""Transport-neutral CloudEvent and at-least-once delivery invariants for T-16."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256

_TOKEN = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_-]*)+$")
_EVENT_TYPE = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z0-9_-]+)+\.v[1-9][0-9]*$")
_CONSUMER = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z0-9_-]+)+$")
_FAILURE = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")


class EventError(Exception):
    """Base error for event persistence and delivery."""


class InvalidCloudEvent(EventError, ValueError):
    """A CloudEvent draft or received envelope violates the stable contract."""


class EventConflict(EventError):
    """A deduplication key or delivery result conflicts with immutable history."""


class EventNotFound(EventError):
    """No tenant-visible event matched the opaque identifier."""


class EventLeaseLost(EventError):
    """A publisher attempted to use an expired or replaced fencing token."""


class DeliveryState(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    PUBLISHED = "published"
    POISON = "poison"


class InboxOutcome(StrEnum):
    COMPLETED = "completed"
    IGNORED = "ignored"


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidCloudEvent(f"{name} must be non-zero")


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidCloudEvent(f"{name} must be timezone-aware")


def _trimmed(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidCloudEvent(f"{name} must be trimmed and contain 1..{maximum} characters")


def _absolute_uri(name: str, value: str, maximum: int) -> None:
    _trimmed(name, value, maximum)
    parsed = urlsplit(value)
    if not parsed.scheme or parsed.username is not None or parsed.password is not None:
        raise InvalidCloudEvent(f"{name} must be an absolute URI without credentials")


@dataclass(frozen=True, slots=True)
class CloudEventDraft:
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    source: str
    subject: str
    data_schema: str
    data: object
    occurred_at: datetime
    recorded_by: UUID
    request_id: UUID
    trace_id: str
    deduplication_key: str

    def __post_init__(self) -> None:
        for name, value in (
            ("organization_id", self.organization_id),
            ("project_id", self.project_id),
            ("aggregate_id", self.aggregate_id),
            ("recorded_by", self.recorded_by),
            ("request_id", self.request_id),
        ):
            _nonzero(name, value)
        if _TOKEN.fullmatch(self.aggregate_type) is None:
            raise InvalidCloudEvent("aggregate_type must be a namespaced stable token")
        if _EVENT_TYPE.fullmatch(self.event_type) is None:
            raise InvalidCloudEvent("event_type must be a versioned namespaced token")
        _absolute_uri("source", self.source, 500)
        _trimmed("subject", self.subject, 500)
        _absolute_uri("data_schema", self.data_schema, 500)
        _aware("occurred_at", self.occurred_at)
        _trimmed("trace_id", self.trace_id, 255)
        _trimmed("deduplication_key", self.deduplication_key, 255)
        if not isinstance(self.data, dict):
            raise InvalidCloudEvent("CloudEvent data must be a schema-validated object")
        try:
            canonical_json_bytes(self.data)
        except (TypeError, ValueError) as error:
            raise InvalidCloudEvent("CloudEvent data must contain canonical JSON values") from error

    @property
    def data_sha256(self) -> str:
        return content_sha256(self.data)


@dataclass(frozen=True, slots=True)
class CloudEventRecord:
    id: UUID
    sequence_no: int
    draft: CloudEventDraft
    recorded_at: datetime

    def __post_init__(self) -> None:
        _nonzero("event_id", self.id)
        if self.sequence_no < 1:
            raise InvalidCloudEvent("sequence_no must be positive")
        _aware("recorded_at", self.recorded_at)
        if self.recorded_at < self.draft.occurred_at:
            raise InvalidCloudEvent("recorded_at cannot precede occurred_at")

    def envelope(self) -> dict[str, Any]:
        draft = self.draft
        return {
            "specversion": "1.0",
            "id": str(self.id),
            "source": draft.source,
            "type": draft.event_type,
            "subject": draft.subject,
            "time": draft.occurred_at.isoformat().replace("+00:00", "Z"),
            "datacontenttype": "application/json",
            "dataschema": draft.data_schema,
            "cmpsequence": self.sequence_no,
            "cmporganizationid": str(draft.organization_id),
            "cmpprojectid": str(draft.project_id),
            "cmpclassification": draft.classification.value,
            "data": json.loads(canonical_json_bytes(draft.data)),
        }


@dataclass(frozen=True, slots=True)
class ClaimedCloudEvent:
    event: CloudEventRecord
    lease_token: UUID
    lease_expires_at: datetime
    attempt_count: int

    def __post_init__(self) -> None:
        _nonzero("lease_token", self.lease_token)
        _aware("lease_expires_at", self.lease_expires_at)
        if self.lease_expires_at <= self.event.recorded_at:
            raise InvalidCloudEvent("delivery lease must expire after event recording")
        if self.attempt_count < 1:
            raise InvalidCloudEvent("claimed delivery attempt_count must be positive")


@dataclass(frozen=True, slots=True)
class InboxReceipt:
    consumer_name: str
    event_id: UUID
    event_type: str
    data_sha256: str
    outcome: InboxOutcome
    side_effect_key: str | None
    received_at: datetime
    processed_at: datetime

    def __post_init__(self) -> None:
        if _CONSUMER.fullmatch(self.consumer_name) is None:
            raise InvalidCloudEvent("consumer_name must be a namespaced stable token")
        _nonzero("event_id", self.event_id)
        if _EVENT_TYPE.fullmatch(self.event_type) is None:
            raise InvalidCloudEvent("inbox event_type is invalid")
        if re.fullmatch(r"[0-9a-f]{64}", self.data_sha256) is None:
            raise InvalidCloudEvent("inbox data_sha256 must be lowercase SHA-256")
        if self.side_effect_key is not None:
            _trimmed("side_effect_key", self.side_effect_key, 255)
        _aware("received_at", self.received_at)
        _aware("processed_at", self.processed_at)
        if self.processed_at < self.received_at:
            raise InvalidCloudEvent("processed_at cannot precede received_at")


def validate_failure_code(value: str) -> None:
    if _FAILURE.fullmatch(value) is None:
        raise ValueError("failure_code must be a stable token")
