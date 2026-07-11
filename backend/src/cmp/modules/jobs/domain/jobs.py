"""Framework-free T-15 Job/Attempt/Lease invariants.

The stable ``Job`` identity is a mutable operational projection. Every execution is a
separate ``Attempt`` with its own immutable, canonical Job Spec. Retrying never resumes or
rewrites a previous attempt.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256

_JOB_TYPE = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_FAILURE_CODE = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class JobError(Exception):
    """Base error for durable job commands."""


class InvalidJobSpec(JobError, ValueError):
    """The immutable Job Spec violates the versioned contract or core invariants."""


class InvalidJobTransition(JobError):
    """A command attempted an unsupported state transition."""


class JobNotFound(JobError):
    """No visible job matched the tenant-scoped opaque identifier."""


class JobConflict(JobError):
    """An idempotency key or stable identity conflicts with different input."""


class RetryNotAllowed(JobError):
    """The immutable input or resource policy does not permit another attempt."""


class LeaseLost(JobError):
    """The attempt lease expired or its fencing token no longer owns the job."""


class FinalizeConflict(JobError):
    """A terminal attempt was already finalized with a different outcome or digest."""


class JobState(StrEnum):
    PLANNED = "planned"
    NEEDS_INPUT = "needs_input"
    QUEUED = "queued"
    CLAIMED = "claimed"
    RUNNING = "running"
    WAITING_EXTERNAL = "waiting_external"
    CANCEL_REQUESTED = "cancel_requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class AttemptState(StrEnum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    RUNNING = "running"
    WAITING_EXTERNAL = "waiting_external"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class FailureCategory(StrEnum):
    """Generic execution taxonomy; no test, model, plugin, or solver semantics."""

    TRANSIENT_INFRASTRUCTURE = "transient_infrastructure"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    EXTERNAL_UNAVAILABLE = "external_unavailable"
    DOMAIN_INVALID = "domain_invalid"
    POLICY_DENIED = "policy_denied"
    OUTPUT_INVALID = "output_invalid"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    INTERNAL_ERROR = "internal_error"


class RetryDisposition(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL_ONLY = "manual_only"
    NEVER = "never"


class RetryKind(StrEnum):
    INITIAL = "initial"
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    LEASE_RECOVERY = "lease_recovery"


TERMINAL_JOB_STATES = frozenset(
    {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED, JobState.TIMED_OUT}
)
TERMINAL_ATTEMPT_STATES = frozenset(
    {
        AttemptState.SUCCEEDED,
        AttemptState.FAILED,
        AttemptState.CANCELLED,
        AttemptState.TIMED_OUT,
    }
)
ACTIVE_ATTEMPT_STATES = frozenset(
    {AttemptState.CLAIMED, AttemptState.RUNNING, AttemptState.WAITING_EXTERNAL}
)

_JOB_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.PLANNED: frozenset(
        {
            JobState.NEEDS_INPUT,
            JobState.QUEUED,
            JobState.FAILED,
            JobState.CANCEL_REQUESTED,
            JobState.CANCELLED,
        }
    ),
    JobState.NEEDS_INPUT: frozenset(
        {
            JobState.QUEUED,
            JobState.FAILED,
            JobState.CANCEL_REQUESTED,
            JobState.CANCELLED,
        }
    ),
    JobState.QUEUED: frozenset(
        {JobState.CLAIMED, JobState.CANCELLED, JobState.TIMED_OUT}
    ),
    JobState.CLAIMED: frozenset(
        {
            JobState.RUNNING,
            JobState.CANCEL_REQUESTED,
            JobState.FAILED,
            JobState.TIMED_OUT,
        }
    ),
    JobState.RUNNING: frozenset(
        {
            JobState.WAITING_EXTERNAL,
            JobState.CANCEL_REQUESTED,
            JobState.SUCCEEDED,
            JobState.FAILED,
            JobState.CANCELLED,
            JobState.TIMED_OUT,
        }
    ),
    JobState.WAITING_EXTERNAL: frozenset(
        {
            JobState.RUNNING,
            JobState.CANCEL_REQUESTED,
            JobState.SUCCEEDED,
            JobState.FAILED,
            JobState.CANCELLED,
            JobState.TIMED_OUT,
        }
    ),
    JobState.CANCEL_REQUESTED: frozenset(
        {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED, JobState.TIMED_OUT}
    ),
    # Only an explicit retry command may use these two projection transitions.
    JobState.FAILED: frozenset({JobState.QUEUED}),
    JobState.TIMED_OUT: frozenset({JobState.QUEUED}),
    JobState.SUCCEEDED: frozenset(),
    JobState.CANCELLED: frozenset(),
}


def assert_job_transition(current: JobState, target: JobState) -> None:
    if target not in _JOB_TRANSITIONS[current]:
        raise InvalidJobTransition(f"job cannot transition from {current} to {target}")


def retry_disposition(category: FailureCategory) -> RetryDisposition:
    """Return the conservative policy pending Domain approval of the final taxonomy."""

    if category in {
        FailureCategory.TRANSIENT_INFRASTRUCTURE,
        FailureCategory.RESOURCE_EXHAUSTED,
        FailureCategory.EXTERNAL_UNAVAILABLE,
        FailureCategory.INTERNAL_ERROR,
    }:
        return RetryDisposition.AUTOMATIC
    if category in {
        FailureCategory.POLICY_DENIED,
        FailureCategory.OUTPUT_INVALID,
        FailureCategory.DEADLINE_EXCEEDED,
    }:
        return RetryDisposition.MANUAL_ONLY
    return RetryDisposition.NEVER


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise ValueError(f"{name} must be non-zero")


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _trimmed(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{name} must be trimmed and contain 1..{maximum} characters")


def _document_uuid(document: dict[str, Any], name: str) -> UUID:
    value = document.get(name)
    if not isinstance(value, str):
        raise InvalidJobSpec(f"{name} must be a UUID string")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise InvalidJobSpec(f"{name} must be a concrete UUID") from error
    if parsed.int == 0:
        raise InvalidJobSpec(f"{name} must be non-zero")
    return parsed


def _deadline(document: dict[str, Any]) -> datetime:
    execution = document.get("execution")
    if not isinstance(execution, dict):
        raise InvalidJobSpec("execution must be an object")
    value = execution.get("deadline")
    if not isinstance(value, str):
        raise InvalidJobSpec("execution.deadline must be an RFC3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidJobSpec("execution.deadline must be an RFC3339 timestamp") from error
    try:
        _aware("execution.deadline", parsed)
    except ValueError as error:
        raise InvalidJobSpec(str(error)) from error
    return parsed


@dataclass(frozen=True, slots=True)
class ImmutableJobSpec:
    """Canonical bytes keep a validated attempt spec immutable in application memory."""

    job_id: UUID
    attempt_id: UUID
    deadline: datetime
    canonical_document: bytes
    digest: str

    def __post_init__(self) -> None:
        _nonzero("job_id", self.job_id)
        _nonzero("attempt_id", self.attempt_id)
        _aware("deadline", self.deadline)
        if not self.canonical_document or not _SHA256.fullmatch(self.digest):
            raise ValueError("canonical Job Spec and lowercase SHA-256 digest are required")
        if content_sha256(self.document()) != self.digest:
            raise ValueError("Job Spec digest does not match canonical content")

    @classmethod
    def from_validated_document(cls, document: object) -> ImmutableJobSpec:
        if not isinstance(document, dict):
            raise InvalidJobSpec("Job Spec must be an object")
        if document.get("job_spec_version") != "1.0":
            raise InvalidJobSpec("job_spec_version must be exactly 1.0")
        job_id = _document_uuid(document, "job_id")
        attempt_id = _document_uuid(document, "attempt_id")
        try:
            canonical = canonical_json_bytes(document)
        except ValueError as error:
            raise InvalidJobSpec("Job Spec must contain canonical JSON values") from error
        canonical_value = json.loads(canonical)
        return cls(
            job_id=job_id,
            attempt_id=attempt_id,
            deadline=_deadline(canonical_value),
            canonical_document=canonical,
            digest=content_sha256(canonical_value),
        )

    def document(self) -> dict[str, Any]:
        value = json.loads(self.canonical_document)
        if not isinstance(value, dict):
            raise RuntimeError("canonical Job Spec ceased to be an object")
        return value

    def for_attempt(self, attempt_id: UUID) -> ImmutableJobSpec:
        _nonzero("attempt_id", attempt_id)
        document = self.document()
        document["attempt_id"] = str(attempt_id)
        return ImmutableJobSpec.from_validated_document(document)


@dataclass(frozen=True, slots=True)
class ResourcePolicy:
    cpu_millis: int
    memory_mb: int
    gpu_count: int
    max_attempts: int

    def __post_init__(self) -> None:
        if not 1 <= self.cpu_millis <= 10_000_000:
            raise ValueError("cpu_millis must be between 1 and 10000000")
        if not 1 <= self.memory_mb <= 100_000_000:
            raise ValueError("memory_mb must be between 1 and 100000000")
        if not 0 <= self.gpu_count <= 1024:
            raise ValueError("gpu_count must be between 0 and 1024")
        if not 1 <= self.max_attempts <= 100:
            raise ValueError("max_attempts must be between 1 and 100")


@dataclass(frozen=True, slots=True)
class Failure:
    category: FailureCategory
    code: str
    detail: str

    def __post_init__(self) -> None:
        if _FAILURE_CODE.fullmatch(self.code) is None:
            raise ValueError("failure code must be a generic lowercase code")
        _trimmed("failure detail", self.detail, 4000)


@dataclass(frozen=True, slots=True)
class RunnerRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    name: str
    max_concurrency: int
    cpu_capacity_millis: int
    memory_capacity_mb: int
    gpu_capacity: int


@dataclass(frozen=True, slots=True)
class JobRecord:
    id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    job_type: str
    state: JobState
    priority: int
    submitted_at: datetime
    submitted_by: UUID
    deadline: datetime
    resource_policy: ResourcePolicy
    attempt_count: int
    current_attempt_id: UUID
    result_manifest_id: UUID | None
    result_manifest_digest: str | None
    failure: Failure | None
    cancel_requested_at: datetime | None
    updated_at: datetime

    def __post_init__(self) -> None:
        if _JOB_TYPE.fullmatch(self.job_type) is None:
            raise ValueError("job_type must be a stable generic identifier")
        if self.attempt_count < 1:
            raise ValueError("attempt_count must be positive")


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    id: UUID
    job_id: UUID
    attempt_no: int
    state: AttemptState
    retry_kind: RetryKind
    retry_reason: str
    spec: ImmutableJobSpec
    runner_id: UUID | None
    lease_token: UUID | None
    lease_expires_at: datetime | None
    heartbeat_at: datetime | None
    claimed_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    progress_fraction: float | None
    progress_phase: str | None
    progress_updated_at: datetime | None
    result_manifest_id: UUID | None
    result_manifest_digest: str | None
    failure: Failure | None

    def __post_init__(self) -> None:
        if self.attempt_no < 1:
            raise ValueError("attempt_no must be positive")
        if self.spec.job_id != self.job_id or self.spec.attempt_id != self.id:
            raise ValueError("Job Spec IDs must match the owning job and attempt")


@dataclass(frozen=True, slots=True)
class JobDetails:
    job: JobRecord
    attempts: tuple[AttemptRecord, ...]

    def __post_init__(self) -> None:
        if not self.attempts:
            raise ValueError("job details require at least one attempt")
        if self.attempts[-1].id != self.job.current_attempt_id:
            raise ValueError("last attempt must be the current attempt")
