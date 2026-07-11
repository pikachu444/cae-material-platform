"""T-15 durable job use cases and persistence ports."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.jobs.domain.jobs import (
    AttemptRecord,
    AttemptState,
    Failure,
    ImmutableJobSpec,
    InvalidJobSpec,
    JobDetails,
    JobRecord,
    ResourcePolicy,
)
from cmp.shared.domain.revisions import content_sha256

_JOB_TYPE = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_IDEMPOTENCY_KEY = re.compile(r"^[\x21-\x7e]{1,255}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class JobContractValidator(Protocol):
    def validate_job_spec(self, document: object) -> None:
        """Raise InvalidJobSpec unless the document satisfies Job Spec 1.0."""


@dataclass(frozen=True, slots=True)
class SubmitJob:
    job_type: str
    classification: DataClassification
    job_spec: object
    resource_policy: ResourcePolicy
    priority: int
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class SubmitResult:
    details: JobDetails
    replayed: bool


@dataclass(frozen=True, slots=True)
class CancelJob:
    job_id: UUID
    reason: str


@dataclass(frozen=True, slots=True)
class RetryJob:
    job_id: UUID
    reason: str


@dataclass(frozen=True, slots=True)
class ClaimJob:
    runner_id: UUID
    accepted_job_types: tuple[str, ...]
    lease_duration: timedelta


@dataclass(frozen=True, slots=True)
class ClaimedAttempt:
    job: JobRecord
    attempt: AttemptRecord


@dataclass(frozen=True, slots=True)
class StartAttempt:
    attempt_id: UUID
    lease_token: UUID


@dataclass(frozen=True, slots=True)
class HeartbeatAttempt:
    attempt_id: UUID
    lease_token: UUID
    lease_duration: timedelta
    progress_fraction: float | None = None
    progress_phase: str | None = None
    waiting_external: bool = False


@dataclass(frozen=True, slots=True)
class HeartbeatResult:
    job: JobRecord
    attempt: AttemptRecord
    cancellation_requested: bool


@dataclass(frozen=True, slots=True)
class FinalizeAttempt:
    attempt_id: UUID
    lease_token: UUID
    outcome: AttemptState
    result_manifest_id: UUID | None = None
    result_manifest_digest: str | None = None
    failure: Failure | None = None


@dataclass(frozen=True, slots=True)
class FinalizeResult:
    job: JobRecord
    attempt: AttemptRecord
    idempotent: bool
    retry_scheduled: bool


@dataclass(frozen=True, slots=True)
class RecoverExpired:
    limit: int = 100


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    attempts_timed_out: int
    retries_scheduled: int
    jobs_timed_out: int


class JobRepository(Protocol):
    def submit(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: SubmitJob,
        spec: ImmutableJobSpec,
        submission_digest: str,
        now: datetime,
    ) -> SubmitResult: ...

    def get(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
    ) -> JobDetails: ...

    def cancel(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CancelJob,
        now: datetime,
    ) -> JobDetails: ...

    def retry(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RetryJob,
        attempt_id: UUID,
        now: datetime,
    ) -> JobDetails: ...

    def claim(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ClaimJob,
        lease_token: UUID,
        now: datetime,
    ) -> ClaimedAttempt | None: ...

    def start(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: StartAttempt,
        now: datetime,
    ) -> ClaimedAttempt: ...

    def heartbeat(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: HeartbeatAttempt,
        now: datetime,
    ) -> HeartbeatResult: ...

    def finalize(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: FinalizeAttempt,
        retry_attempt_id: UUID,
        now: datetime,
    ) -> FinalizeResult: ...

    def recover_expired(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RecoverExpired,
        attempt_ids: Sequence[UUID],
        now: datetime,
    ) -> RecoveryResult: ...


def _reason(name: str, value: str) -> None:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError(f"{name} must be trimmed and contain 1..2000 characters")


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise ValueError(f"{name} must be non-zero")


def _duration(value: timedelta) -> None:
    if not timedelta(seconds=5) <= value <= timedelta(hours=24):
        raise ValueError("lease_duration must be between 5 seconds and 24 hours")


def _require_decision(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or decision.permission is not permission
    ):
        raise ValueError("authorization decision does not match command context")


class JobService:
    """Validate generic contracts, then coordinate one transaction per job command."""

    def __init__(
        self,
        *,
        repository: JobRepository,
        validator: JobContractValidator,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._validator = validator
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def submit(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: SubmitJob,
    ) -> SubmitResult:
        _require_decision(context, decision, Permission.JOB_SUBMIT)
        if _JOB_TYPE.fullmatch(command.job_type) is None:
            raise ValueError("job_type must match the generic job identifier contract")
        if not -32768 <= command.priority <= 32767:
            raise ValueError("priority must fit a signed small integer")
        if _IDEMPOTENCY_KEY.fullmatch(command.idempotency_key) is None:
            raise ValueError("idempotency_key must contain 1..255 visible ASCII characters")
        self._validator.validate_job_spec(command.job_spec)
        spec = ImmutableJobSpec.from_validated_document(command.job_spec)
        now = self._clock()
        if spec.deadline <= now:
            raise InvalidJobSpec("execution.deadline must be in the future at submission")
        submission_digest = content_sha256(
            {
                "job_type": command.job_type,
                "classification": command.classification.value,
                "job_spec_digest": spec.digest,
                "resource_policy": {
                    "cpu_millis": command.resource_policy.cpu_millis,
                    "memory_mb": command.resource_policy.memory_mb,
                    "gpu_count": command.resource_policy.gpu_count,
                    "max_attempts": command.resource_policy.max_attempts,
                },
                "priority": command.priority,
            }
        )
        return self._repository.submit(
            context=context,
            decision=decision,
            command=command,
            spec=spec,
            submission_digest=submission_digest,
            now=now,
        )

    def get(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
    ) -> JobDetails:
        _require_decision(context, decision, Permission.JOB_READ)
        _nonzero("job_id", job_id)
        return self._repository.get(
            context=context, decision=decision, job_id=job_id
        )

    def cancel(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CancelJob,
    ) -> JobDetails:
        _require_decision(context, decision, Permission.JOB_CONTROL)
        _nonzero("job_id", command.job_id)
        _reason("cancel reason", command.reason)
        return self._repository.cancel(
            context=context,
            decision=decision,
            command=command,
            now=self._clock(),
        )

    def retry(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RetryJob,
    ) -> JobDetails:
        _require_decision(context, decision, Permission.JOB_CONTROL)
        _nonzero("job_id", command.job_id)
        _reason("retry reason", command.reason)
        return self._repository.retry(
            context=context,
            decision=decision,
            command=command,
            attempt_id=self._id_factory(),
            now=self._clock(),
        )

    def claim(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ClaimJob,
    ) -> ClaimedAttempt | None:
        _require_decision(context, decision, Permission.JOB_EXECUTE)
        _nonzero("runner_id", command.runner_id)
        _duration(command.lease_duration)
        if (
            not command.accepted_job_types
            or tuple(sorted(set(command.accepted_job_types)))
            != command.accepted_job_types
            or any(_JOB_TYPE.fullmatch(value) is None for value in command.accepted_job_types)
        ):
            raise ValueError("accepted_job_types must be non-empty, sorted, and unique")
        return self._repository.claim(
            context=context,
            decision=decision,
            command=command,
            lease_token=self._id_factory(),
            now=self._clock(),
        )

    def start(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: StartAttempt,
    ) -> ClaimedAttempt:
        _require_decision(context, decision, Permission.JOB_EXECUTE)
        _nonzero("attempt_id", command.attempt_id)
        _nonzero("lease_token", command.lease_token)
        return self._repository.start(
            context=context,
            decision=decision,
            command=command,
            now=self._clock(),
        )

    def heartbeat(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: HeartbeatAttempt,
    ) -> HeartbeatResult:
        _require_decision(context, decision, Permission.JOB_EXECUTE)
        _nonzero("attempt_id", command.attempt_id)
        _nonzero("lease_token", command.lease_token)
        _duration(command.lease_duration)
        if command.progress_fraction is not None and not 0 <= command.progress_fraction <= 1:
            raise ValueError("progress_fraction must be between 0 and 1")
        if command.progress_phase is not None:
            if (
                not command.progress_phase
                or command.progress_phase != command.progress_phase.strip()
                or len(command.progress_phase) > 255
                or "\x00" in command.progress_phase
            ):
                raise ValueError("progress_phase must be trimmed and contain 1..255 characters")
        return self._repository.heartbeat(
            context=context,
            decision=decision,
            command=command,
            now=self._clock(),
        )

    def finalize(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: FinalizeAttempt,
    ) -> FinalizeResult:
        _require_decision(context, decision, Permission.JOB_EXECUTE)
        _nonzero("attempt_id", command.attempt_id)
        _nonzero("lease_token", command.lease_token)
        if command.outcome not in {
            AttemptState.SUCCEEDED,
            AttemptState.FAILED,
            AttemptState.CANCELLED,
            AttemptState.TIMED_OUT,
        }:
            raise ValueError("finalize outcome must be terminal")
        manifest_pair = (
            command.result_manifest_id is not None,
            command.result_manifest_digest is not None,
        )
        if manifest_pair[0] != manifest_pair[1]:
            raise ValueError("result manifest ID and digest must be supplied together")
        if command.result_manifest_id is not None:
            _nonzero("result_manifest_id", command.result_manifest_id)
        if (
            command.result_manifest_digest is not None
            and _SHA256.fullmatch(command.result_manifest_digest) is None
        ):
            raise ValueError("result_manifest_digest must be lowercase SHA-256 hex")
        if command.outcome is AttemptState.SUCCEEDED:
            if not all(manifest_pair) or command.failure is not None:
                raise ValueError("succeeded outcome requires a manifest and no failure")
        elif command.outcome in {AttemptState.FAILED, AttemptState.TIMED_OUT}:
            if command.failure is None:
                raise ValueError("failed and timed_out outcomes require a failure")
        elif command.failure is not None:
            raise ValueError("cancelled outcome cannot include a failure")
        return self._repository.finalize(
            context=context,
            decision=decision,
            command=command,
            retry_attempt_id=self._id_factory(),
            now=self._clock(),
        )

    def recover_expired(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RecoverExpired | None = None,
    ) -> RecoveryResult:
        resolved = command or RecoverExpired()
        _require_decision(context, decision, Permission.JOB_EXECUTE)
        if not 1 <= resolved.limit <= 1000:
            raise ValueError("recovery limit must be between 1 and 1000")
        return self._repository.recover_expired(
            context=context,
            decision=decision,
            command=resolved,
            attempt_ids=tuple(self._id_factory() for _ in range(resolved.limit)),
            now=self._clock(),
        )
