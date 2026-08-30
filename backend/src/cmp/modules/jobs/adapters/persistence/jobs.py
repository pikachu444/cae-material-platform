"""SQLAlchemy/PostgreSQL implementation of atomic T-15 job commands."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.jobs.application.jobs import (
    CancelJob,
    ClaimedAttempt,
    ClaimJob,
    FinalizeAttempt,
    FinalizeResult,
    HeartbeatAttempt,
    HeartbeatResult,
    RecoverExpired,
    RecoveryResult,
    RetryJob,
    StartAttempt,
    SubmitJob,
    SubmitResult,
)
from cmp.modules.jobs.domain.jobs import (
    ACTIVE_ATTEMPT_STATES,
    TERMINAL_ATTEMPT_STATES,
    AttemptRecord,
    AttemptState,
    Failure,
    FailureCategory,
    FinalizeConflict,
    ImmutableJobSpec,
    InvalidJobTransition,
    JobConflict,
    JobDetails,
    JobNotFound,
    JobRecord,
    JobState,
    LeaseLost,
    ResourcePolicy,
    RetryDisposition,
    RetryKind,
    RetryNotAllowed,
    assert_job_transition,
    retry_disposition,
)

metadata = sa.MetaData()
uuid_type = postgresql.UUID(as_uuid=True)

runner_table = sa.Table(
    "runner",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    sa.Column("max_concurrency", sa.Integer(), nullable=False),
    sa.Column("cpu_capacity_millis", sa.Integer(), nullable=False),
    sa.Column("memory_capacity_mb", sa.Integer(), nullable=False),
    sa.Column("gpu_capacity", sa.Integer(), nullable=False),
    sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", uuid_type, nullable=False),
    sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    schema="jobs",
)

runner_job_type_table = sa.Table(
    "runner_job_type",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("runner_id", uuid_type, nullable=False),
    sa.Column("job_type", sa.String(100), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", uuid_type, nullable=False),
    schema="jobs",
)

job_table = sa.Table(
    "job",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("job_type", sa.String(100), nullable=False),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("priority", sa.SmallInteger(), nullable=False),
    sa.Column("idempotency_key", sa.String(255), nullable=False),
    sa.Column("submission_digest", sa.CHAR(64), nullable=False),
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("submitted_by", uuid_type, nullable=False),
    sa.Column("request_id", uuid_type, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("requested_cpu_millis", sa.Integer(), nullable=False),
    sa.Column("requested_memory_mb", sa.Integer(), nullable=False),
    sa.Column("requested_gpu_count", sa.Integer(), nullable=False),
    sa.Column("max_attempts", sa.SmallInteger(), nullable=False),
    sa.Column("attempt_count", sa.SmallInteger(), nullable=False),
    sa.Column("current_attempt_id", uuid_type, nullable=False),
    sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cancel_requested_by", uuid_type, nullable=True),
    sa.Column("cancel_reason", sa.Text(), nullable=True),
    sa.Column("result_manifest_id", uuid_type, nullable=True),
    sa.Column("result_manifest_digest", sa.CHAR(64), nullable=True),
    sa.Column("failure_category", sa.String(64), nullable=True),
    sa.Column("failure_code", sa.String(100), nullable=True),
    sa.Column("failure_detail", sa.Text(), nullable=True),
    sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("row_version", sa.BigInteger(), nullable=False),
    schema="jobs",
)

job_attempt_table = sa.Table(
    "job_attempt",
    metadata,
    sa.Column("organization_id", uuid_type, nullable=False),
    sa.Column("project_id", uuid_type, nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("job_id", uuid_type, nullable=False),
    sa.Column("attempt_no", sa.SmallInteger(), nullable=False),
    sa.Column("state", sa.String(32), nullable=False),
    sa.Column("retry_kind", sa.String(32), nullable=False),
    sa.Column("retry_reason", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", uuid_type, nullable=False),
    sa.Column("job_spec", postgresql.JSONB(), nullable=False),
    sa.Column("job_spec_digest", sa.CHAR(64), nullable=False),
    sa.Column("runner_id", uuid_type, nullable=True),
    sa.Column("lease_token", uuid_type, nullable=True),
    sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("progress_fraction", sa.Numeric(7, 6), nullable=True),
    sa.Column("progress_phase", sa.String(255), nullable=True),
    sa.Column("progress_updated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("result_manifest_id", uuid_type, nullable=True),
    sa.Column("result_manifest_digest", sa.CHAR(64), nullable=True),
    sa.Column("failure_category", sa.String(64), nullable=True),
    sa.Column("failure_code", sa.String(100), nullable=True),
    sa.Column("failure_detail", sa.Text(), nullable=True),
    schema="jobs",
)


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


def _failure(row: RowMapping) -> Failure | None:
    category = row["failure_category"]
    if category is None:
        return None
    return Failure(
        FailureCategory(str(category)),
        str(row["failure_code"]),
        str(row["failure_detail"]),
    )


def _job_record(row: RowMapping) -> JobRecord:
    return JobRecord(
        id=cast(UUID, row["id"]),
        organization_id=cast(UUID, row["organization_id"]),
        project_id=cast(UUID, row["project_id"]),
        classification=DataClassification(str(row["classification"])),
        job_type=str(row["job_type"]),
        state=JobState(str(row["state"])),
        priority=int(row["priority"]),
        submitted_at=cast(datetime, row["submitted_at"]),
        submitted_by=cast(UUID, row["submitted_by"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
        deadline=cast(datetime, row["deadline_at"]),
        resource_policy=ResourcePolicy(
            cpu_millis=int(row["requested_cpu_millis"]),
            memory_mb=int(row["requested_memory_mb"]),
            gpu_count=int(row["requested_gpu_count"]),
            max_attempts=int(row["max_attempts"]),
        ),
        attempt_count=int(row["attempt_count"]),
        current_attempt_id=cast(UUID, row["current_attempt_id"]),
        result_manifest_id=cast(UUID | None, row["result_manifest_id"]),
        result_manifest_digest=cast(str | None, row["result_manifest_digest"]),
        failure=_failure(row),
        cancel_requested_at=cast(datetime | None, row["cancel_requested_at"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


def _attempt_record(row: RowMapping) -> AttemptRecord:
    spec = ImmutableJobSpec.from_validated_document(row["job_spec"])
    if spec.digest != row["job_spec_digest"]:
        raise RuntimeError("persisted Job Spec digest mismatch")
    progress = row["progress_fraction"]
    return AttemptRecord(
        id=cast(UUID, row["id"]),
        job_id=cast(UUID, row["job_id"]),
        attempt_no=int(row["attempt_no"]),
        state=AttemptState(str(row["state"])),
        retry_kind=RetryKind(str(row["retry_kind"])),
        retry_reason=str(row["retry_reason"]),
        spec=spec,
        runner_id=cast(UUID | None, row["runner_id"]),
        lease_token=cast(UUID | None, row["lease_token"]),
        lease_expires_at=cast(datetime | None, row["lease_expires_at"]),
        heartbeat_at=cast(datetime | None, row["heartbeat_at"]),
        claimed_at=cast(datetime | None, row["claimed_at"]),
        started_at=cast(datetime | None, row["started_at"]),
        ended_at=cast(datetime | None, row["ended_at"]),
        progress_fraction=float(cast(Decimal, progress)) if progress is not None else None,
        progress_phase=cast(str | None, row["progress_phase"]),
        progress_updated_at=cast(datetime | None, row["progress_updated_at"]),
        result_manifest_id=cast(UUID | None, row["result_manifest_id"]),
        result_manifest_digest=cast(str | None, row["result_manifest_digest"]),
        failure=_failure(row),
    )


def _failure_values(failure: Failure | None) -> dict[str, object | None]:
    return {
        "failure_category": failure.category.value if failure else None,
        "failure_code": failure.code if failure else None,
        "failure_detail": failure.detail if failure else None,
    }


class SqlAlchemyJobRepository:
    """All claims and state changes are serialized in PostgreSQL transactions."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context

    def _bind(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    @staticmethod
    def _job_row(
        session: Session,
        job_id: UUID,
        *,
        lock: bool = False,
        skip_locked: bool = False,
    ) -> RowMapping:
        statement = sa.select(job_table).where(job_table.c.id == job_id)
        if lock:
            statement = statement.with_for_update(
                of=job_table, skip_locked=skip_locked
            )
        row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise JobNotFound(str(job_id))
        return row

    @staticmethod
    def _attempt_rows(session: Session, job_id: UUID) -> tuple[RowMapping, ...]:
        return tuple(
            session.execute(
                sa.select(job_attempt_table)
                .where(job_attempt_table.c.job_id == job_id)
                .order_by(job_attempt_table.c.attempt_no)
            ).mappings()
        )

    @classmethod
    def _details_from_row(cls, session: Session, row: RowMapping) -> JobDetails:
        job = _job_record(row)
        attempts = tuple(
            _attempt_record(item) for item in cls._attempt_rows(session, job.id)
        )
        return JobDetails(job, attempts)

    @staticmethod
    def _attempt_row(
        session: Session, attempt_id: UUID, *, lock: bool = False
    ) -> RowMapping:
        statement = sa.select(job_attempt_table).where(
            job_attempt_table.c.id == attempt_id
        )
        if lock:
            statement = statement.with_for_update(of=job_attempt_table)
        row = session.execute(statement).mappings().one_or_none()
        if row is None:
            raise JobNotFound(str(attempt_id))
        return row

    @staticmethod
    def _insert_attempt(
        session: Session,
        *,
        job: RowMapping,
        spec: ImmutableJobSpec,
        attempt_no: int,
        retry_kind: RetryKind,
        retry_reason: str,
        actor_id: UUID,
        now: datetime,
    ) -> None:
        session.execute(
            sa.insert(job_attempt_table).values(
                organization_id=job["organization_id"],
                project_id=job["project_id"],
                classification=job["classification"],
                id=spec.attempt_id,
                job_id=job["id"],
                attempt_no=attempt_no,
                state=AttemptState.QUEUED.value,
                retry_kind=retry_kind.value,
                retry_reason=retry_reason,
                created_at=now,
                created_by=actor_id,
                job_spec=spec.document(),
                job_spec_digest=spec.digest,
            )
        )

    @staticmethod
    def _transition_job(
        session: Session,
        row: RowMapping,
        target: JobState,
        now: datetime,
        **values: object,
    ) -> None:
        current = JobState(str(row["state"]))
        assert_job_transition(current, target)
        result = session.execute(
            sa.update(job_table)
            .where(
                job_table.c.organization_id == row["organization_id"],
                job_table.c.project_id == row["project_id"],
                job_table.c.id == row["id"],
                job_table.c.row_version == row["row_version"],
            )
            .values(
                state=target.value,
                updated_at=now,
                row_version=int(row["row_version"]) + 1,
                **values,
            )
        )
        if getattr(result, "rowcount", None) != 1:
            raise JobConflict("job projection changed concurrently")

    def submit(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: SubmitJob,
        spec: ImmutableJobSpec,
        submission_digest: str,
        now: datetime,
    ) -> SubmitResult:
        values = {
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "id": spec.job_id,
            "classification": command.classification.value,
            "job_type": command.job_type,
            "state": JobState.QUEUED.value,
            "priority": command.priority,
            "idempotency_key": command.idempotency_key,
            "submission_digest": submission_digest,
            "submitted_at": now,
            "submitted_by": context.principal.id,
            "request_id": context.request_id,
            "trace_id": context.trace_id,
            "deadline_at": spec.deadline,
            "requested_cpu_millis": command.resource_policy.cpu_millis,
            "requested_memory_mb": command.resource_policy.memory_mb,
            "requested_gpu_count": command.resource_policy.gpu_count,
            "max_attempts": command.resource_policy.max_attempts,
            "attempt_count": 1,
            "current_attempt_id": spec.attempt_id,
            "updated_at": now,
            "row_version": 1,
        }
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            inserted = session.execute(
                postgresql.insert(job_table)
                .values(values)
                .on_conflict_do_nothing()
                .returning(job_table.c.id)
            ).scalar_one_or_none()
            if inserted is None:
                existing = session.execute(
                    sa.select(job_table).where(
                        job_table.c.idempotency_key == command.idempotency_key
                    )
                ).mappings().one_or_none()
                if existing is None or existing["submission_digest"] != submission_digest:
                    raise JobConflict("idempotency key or job ID is already in use")
                return SubmitResult(self._details_from_row(session, existing), True)
            self._insert_attempt(
                session,
                job=cast(RowMapping, values),
                spec=spec,
                attempt_no=1,
                retry_kind=RetryKind.INITIAL,
                retry_reason="initial submission",
                actor_id=context.principal.id,
                now=now,
            )
            row = self._job_row(session, spec.job_id)
            return SubmitResult(self._details_from_row(session, row), False)

    def get(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
    ) -> JobDetails:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            return self._details_from_row(session, self._job_row(session, job_id))

    def cancel(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CancelJob,
        now: datetime,
    ) -> JobDetails:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            job = self._job_row(session, command.job_id, lock=True)
            state = JobState(str(job["state"]))
            if state is JobState.CANCELLED or state is JobState.CANCEL_REQUESTED:
                return self._details_from_row(session, job)
            if state in {
                JobState.SUCCEEDED,
                JobState.FAILED,
                JobState.TIMED_OUT,
            }:
                raise InvalidJobTransition(f"cannot cancel terminal job in {state}")
            cancel_values = {
                "cancel_requested_at": now,
                "cancel_requested_by": context.principal.id,
                "cancel_reason": command.reason,
            }
            if state in {JobState.PLANNED, JobState.NEEDS_INPUT, JobState.QUEUED}:
                session.execute(
                    sa.update(job_attempt_table)
                    .where(job_attempt_table.c.id == job["current_attempt_id"])
                    .values(state=AttemptState.CANCELLED.value, ended_at=now)
                )
                self._transition_job(
                    session,
                    job,
                    JobState.CANCELLED,
                    now,
                    terminal_at=now,
                    **cancel_values,
                )
            else:
                self._transition_job(
                    session,
                    job,
                    JobState.CANCEL_REQUESTED,
                    now,
                    **cancel_values,
                )
            return self._details_from_row(
                session, self._job_row(session, command.job_id)
            )

    def _schedule_retry(
        self,
        session: Session,
        *,
        job: RowMapping,
        previous: RowMapping,
        attempt_id: UUID,
        kind: RetryKind,
        reason: str,
        actor_id: UUID,
        now: datetime,
    ) -> None:
        spec = _attempt_record(previous).spec.for_attempt(attempt_id)
        self._insert_attempt(
            session,
            job=job,
            spec=spec,
            attempt_no=int(job["attempt_count"]) + 1,
            retry_kind=kind,
            retry_reason=reason,
            actor_id=actor_id,
            now=now,
        )
        self._transition_job(
            session,
            job,
            JobState.QUEUED,
            now,
            attempt_count=int(job["attempt_count"]) + 1,
            current_attempt_id=attempt_id,
            result_manifest_id=None,
            result_manifest_digest=None,
            failure_category=None,
            failure_code=None,
            failure_detail=None,
            terminal_at=None,
        )

    def retry(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RetryJob,
        attempt_id: UUID,
        now: datetime,
    ) -> JobDetails:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            job = self._job_row(session, command.job_id, lock=True)
            state = JobState(str(job["state"]))
            if state not in {JobState.FAILED, JobState.TIMED_OUT}:
                raise RetryNotAllowed(f"job in {state} cannot be retried")
            # A calibration Run owns the immutable result lifecycle.  Once its generic
            # plugin Job is terminal, a manual retry would create a second execution under
            # the same Run and break selection/result identity.  The check runs after the
            # row lock, so concurrent retry requests cannot bypass it; all unrelated generic
            # Job types retain the normal T-15 retry policy below.
            if str(job["job_type"]) == "plugin.run":
                current_attempt = self._attempt_row(
                    session, cast(UUID, job["current_attempt_id"]), lock=True
                )
                specification = current_attempt["job_spec"]
                if isinstance(specification, dict):
                    extension = specification.get("extension")
                    if (
                        specification.get("operation") == "execute_plan"
                        and isinstance(extension, dict)
                        and extension.get("plugin_id")
                        == "cmp.linear_viscoelastic.calibrator"
                    ):
                        raise RetryNotAllowed("terminal_calibration_requires_new_run")
            if job["cancel_requested_at"] is not None:
                raise RetryNotAllowed("cancelled execution cannot be retried")
            failure = _failure(job)
            if failure is None or retry_disposition(failure.category) is RetryDisposition.NEVER:
                raise RetryNotAllowed("immutable invalid input cannot be retried")
            if int(job["attempt_count"]) >= int(job["max_attempts"]):
                raise RetryNotAllowed("maximum attempt count reached")
            if cast(datetime, job["deadline_at"]) <= now:
                raise RetryNotAllowed("job deadline has passed")
            previous = self._attempt_row(
                session, cast(UUID, job["current_attempt_id"]), lock=True
            )
            self._schedule_retry(
                session,
                job=job,
                previous=previous,
                attempt_id=attempt_id,
                kind=RetryKind.MANUAL,
                reason=command.reason,
                actor_id=context.principal.id,
                now=now,
            )
            return self._details_from_row(
                session, self._job_row(session, command.job_id)
            )

    def claim(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ClaimJob,
        lease_token: UUID,
        now: datetime,
    ) -> ClaimedAttempt | None:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            runner = session.execute(
                sa.select(runner_table)
                .where(
                    runner_table.c.id == command.runner_id,
                    runner_table.c.status == "active",
                )
                .with_for_update(of=runner_table)
            ).mappings().one_or_none()
            if runner is None:
                raise JobNotFound(str(command.runner_id))
            capabilities = tuple(
                session.execute(
                    sa.select(runner_job_type_table.c.job_type).where(
                        runner_job_type_table.c.runner_id == command.runner_id,
                        runner_job_type_table.c.job_type.in_(
                            command.accepted_job_types
                        ),
                    )
                ).scalars()
            )
            if not capabilities:
                return None
            active_count = session.execute(
                sa.select(sa.func.count())
                .select_from(job_attempt_table)
                .where(
                    job_attempt_table.c.runner_id == command.runner_id,
                    job_attempt_table.c.state.in_(
                        tuple(state.value for state in ACTIVE_ATTEMPT_STATES)
                    ),
                    job_attempt_table.c.lease_expires_at > now,
                )
            ).scalar_one()
            if int(active_count) >= int(runner["max_concurrency"]):
                return None
            current = job_table.join(
                job_attempt_table,
                sa.and_(
                    job_attempt_table.c.organization_id
                    == job_table.c.organization_id,
                    job_attempt_table.c.project_id == job_table.c.project_id,
                    job_attempt_table.c.job_id == job_table.c.id,
                    job_attempt_table.c.id == job_table.c.current_attempt_id,
                ),
            )
            job = session.execute(
                sa.select(job_table)
                .select_from(current)
                .where(
                    job_table.c.state == JobState.QUEUED.value,
                    job_attempt_table.c.state == AttemptState.QUEUED.value,
                    job_table.c.job_type.in_(capabilities),
                    job_table.c.deadline_at > now,
                    job_table.c.requested_cpu_millis
                    <= runner["cpu_capacity_millis"],
                    job_table.c.requested_memory_mb
                    <= runner["memory_capacity_mb"],
                    job_table.c.requested_gpu_count <= runner["gpu_capacity"],
                )
                .order_by(
                    job_table.c.priority.desc(),
                    job_table.c.submitted_at,
                    job_table.c.id,
                )
                .limit(1)
                .with_for_update(of=job_table, skip_locked=True)
            ).mappings().one_or_none()
            if job is None:
                return None
            lease_expires = now + command.lease_duration
            session.execute(
                sa.update(job_attempt_table)
                .where(job_attempt_table.c.id == job["current_attempt_id"])
                .values(
                    state=AttemptState.CLAIMED.value,
                    runner_id=command.runner_id,
                    lease_token=lease_token,
                    lease_expires_at=lease_expires,
                    heartbeat_at=now,
                    claimed_at=now,
                )
            )
            self._transition_job(session, job, JobState.CLAIMED, now)
            session.execute(
                sa.update(runner_table)
                .where(runner_table.c.id == command.runner_id)
                .values(last_heartbeat_at=now)
            )
            refreshed = self._job_row(session, cast(UUID, job["id"]))
            details = self._details_from_row(session, refreshed)
            return ClaimedAttempt(details.job, details.attempts[-1])

    def _leased_rows(
        self,
        session: Session,
        attempt_id: UUID,
        lease_token: UUID,
        now: datetime,
    ) -> tuple[RowMapping, RowMapping]:
        attempt = self._attempt_row(session, attempt_id, lock=True)
        job = self._job_row(session, cast(UUID, attempt["job_id"]), lock=True)
        if (
            attempt["lease_token"] != lease_token
            or job["current_attempt_id"] != attempt_id
            or attempt["lease_expires_at"] is None
            or cast(datetime, attempt["lease_expires_at"]) <= now
        ):
            raise LeaseLost("attempt lease fencing token is stale or expired")
        return job, attempt

    def start(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: StartAttempt,
        now: datetime,
    ) -> ClaimedAttempt:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            job, attempt = self._leased_rows(
                session, command.attempt_id, command.lease_token, now
            )
            attempt_state = AttemptState(str(attempt["state"]))
            if attempt_state is AttemptState.RUNNING:
                return ClaimedAttempt(_job_record(job), _attempt_record(attempt))
            if JobState(str(job["state"])) is JobState.CANCEL_REQUESTED:
                return ClaimedAttempt(_job_record(job), _attempt_record(attempt))
            if attempt_state is not AttemptState.CLAIMED:
                raise InvalidJobTransition(f"cannot start attempt in {attempt_state}")
            session.execute(
                sa.update(job_attempt_table)
                .where(job_attempt_table.c.id == command.attempt_id)
                .values(state=AttemptState.RUNNING.value, started_at=now)
            )
            self._transition_job(session, job, JobState.RUNNING, now)
            refreshed = self._job_row(session, cast(UUID, job["id"]))
            details = self._details_from_row(session, refreshed)
            return ClaimedAttempt(details.job, details.attempts[-1])

    def heartbeat(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: HeartbeatAttempt,
        now: datetime,
    ) -> HeartbeatResult:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            job, attempt = self._leased_rows(
                session, command.attempt_id, command.lease_token, now
            )
            state = AttemptState(str(attempt["state"]))
            if state not in ACTIVE_ATTEMPT_STATES:
                raise LeaseLost("attempt is no longer active")
            target = state
            if command.waiting_external and state is AttemptState.RUNNING:
                target = AttemptState.WAITING_EXTERNAL
            elif not command.waiting_external and state is AttemptState.WAITING_EXTERNAL:
                target = AttemptState.RUNNING
            values: dict[str, object] = {
                "lease_expires_at": now + command.lease_duration,
                "heartbeat_at": now,
            }
            if command.progress_fraction is not None:
                values["progress_fraction"] = command.progress_fraction
            if command.progress_phase is not None:
                values["progress_phase"] = command.progress_phase
            if command.progress_fraction is not None or command.progress_phase is not None:
                values["progress_updated_at"] = now
            if target is not state:
                values["state"] = target.value
            session.execute(
                sa.update(job_attempt_table)
                .where(job_attempt_table.c.id == command.attempt_id)
                .values(**values)
            )
            job_state = JobState(str(job["state"]))
            if target is not state and job_state is not JobState.CANCEL_REQUESTED:
                target_job = (
                    JobState.WAITING_EXTERNAL
                    if target is AttemptState.WAITING_EXTERNAL
                    else JobState.RUNNING
                )
                self._transition_job(session, job, target_job, now)
            refreshed = self._job_row(session, cast(UUID, job["id"]))
            details = self._details_from_row(session, refreshed)
            return HeartbeatResult(
                details.job,
                details.attempts[-1],
                details.job.state is JobState.CANCEL_REQUESTED,
            )

    @staticmethod
    def _same_finalize(attempt: RowMapping, command: FinalizeAttempt) -> bool:
        failure = _failure(attempt)
        return (
            attempt["state"] == command.outcome.value
            and attempt["result_manifest_id"] == command.result_manifest_id
            and attempt["result_manifest_digest"] == command.result_manifest_digest
            and failure == command.failure
        )

    def finalize(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: FinalizeAttempt,
        retry_attempt_id: UUID,
        now: datetime,
    ) -> FinalizeResult:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            requested = self._attempt_row(session, command.attempt_id, lock=True)
            job = self._job_row(session, cast(UUID, requested["job_id"]), lock=True)
            if requested["lease_token"] != command.lease_token:
                raise LeaseLost("attempt lease fencing token does not match")
            if AttemptState(str(requested["state"])) in TERMINAL_ATTEMPT_STATES:
                if self._same_finalize(requested, command):
                    return FinalizeResult(
                        _job_record(job), _attempt_record(requested), True, False
                    )
                if (
                    job["state"] == JobState.SUCCEEDED.value
                    and command.outcome is AttemptState.SUCCEEDED
                    and job["result_manifest_digest"] == command.result_manifest_digest
                ):
                    current = self._attempt_row(
                        session, cast(UUID, job["current_attempt_id"])
                    )
                    return FinalizeResult(
                        _job_record(job), _attempt_record(current), True, False
                    )
                raise FinalizeConflict("attempt already has a different terminal result")
            if (
                job["current_attempt_id"] != command.attempt_id
                or requested["lease_expires_at"] is None
                or cast(datetime, requested["lease_expires_at"]) <= now
            ):
                raise LeaseLost("attempt is no longer the leased current attempt")
            attempt_values: dict[str, object | None] = {
                "state": command.outcome.value,
                "ended_at": now,
                "result_manifest_id": command.result_manifest_id,
                "result_manifest_digest": command.result_manifest_digest,
                **_failure_values(command.failure),
            }
            session.execute(
                sa.update(job_attempt_table)
                .where(job_attempt_table.c.id == command.attempt_id)
                .values(**attempt_values)
            )
            target_job = JobState(command.outcome.value)
            job_values: dict[str, object | None] = {
                "terminal_at": now,
                "result_manifest_id": command.result_manifest_id,
                "result_manifest_digest": command.result_manifest_digest,
                **_failure_values(command.failure),
            }
            self._transition_job(session, job, target_job, now, **job_values)
            retry_scheduled = False
            terminal_job = self._job_row(session, cast(UUID, job["id"]), lock=True)
            if (
                command.outcome is AttemptState.FAILED
                and command.failure is not None
                and JobState(str(job["state"])) is not JobState.CANCEL_REQUESTED
                and retry_disposition(command.failure.category)
                is RetryDisposition.AUTOMATIC
                and int(terminal_job["attempt_count"]) < int(terminal_job["max_attempts"])
                and cast(datetime, terminal_job["deadline_at"]) > now
            ):
                finalized = self._attempt_row(session, command.attempt_id)
                self._schedule_retry(
                    session,
                    job=terminal_job,
                    previous=finalized,
                    attempt_id=retry_attempt_id,
                    kind=RetryKind.AUTOMATIC,
                    reason=f"automatic retry after {command.failure.category.value}",
                    actor_id=context.principal.id,
                    now=now,
                )
                retry_scheduled = True
            final_job = self._job_row(session, cast(UUID, job["id"]))
            finalized = self._attempt_row(session, command.attempt_id)
            return FinalizeResult(
                _job_record(final_job),
                _attempt_record(finalized),
                False,
                retry_scheduled,
            )

    def recover_expired(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RecoverExpired,
        attempt_ids: Sequence[UUID],
        now: datetime,
    ) -> RecoveryResult:
        timed_out = 0
        retries = 0
        jobs_timed_out = 0
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            current = job_table.join(
                job_attempt_table,
                sa.and_(
                    job_attempt_table.c.organization_id
                    == job_table.c.organization_id,
                    job_attempt_table.c.project_id == job_table.c.project_id,
                    job_attempt_table.c.job_id == job_table.c.id,
                    job_attempt_table.c.id == job_table.c.current_attempt_id,
                ),
            )
            expired = tuple(
                session.execute(
                    sa.select(job_attempt_table.c.id, job_table.c.id.label("stable_job_id"))
                    .select_from(current)
                    .where(
                        job_attempt_table.c.state.in_(
                            tuple(state.value for state in ACTIVE_ATTEMPT_STATES)
                        ),
                        job_attempt_table.c.lease_expires_at <= now,
                    )
                    .order_by(job_attempt_table.c.lease_expires_at)
                    .limit(command.limit)
                    .with_for_update(of=job_table, skip_locked=True)
                ).mappings()
            )
            for index, expired_ref in enumerate(expired):
                job = self._job_row(
                    session, cast(UUID, expired_ref["stable_job_id"]), lock=True
                )
                attempt = self._attempt_row(
                    session, cast(UUID, expired_ref["id"]), lock=True
                )
                failure = Failure(
                    FailureCategory.TRANSIENT_INFRASTRUCTURE,
                    "lease_expired",
                    "Worker heartbeat lease expired before terminal finalization.",
                )
                session.execute(
                    sa.update(job_attempt_table)
                    .where(job_attempt_table.c.id == attempt["id"])
                    .values(
                        state=AttemptState.TIMED_OUT.value,
                        ended_at=now,
                        **_failure_values(failure),
                    )
                )
                self._transition_job(
                    session,
                    job,
                    JobState.TIMED_OUT,
                    now,
                    terminal_at=now,
                    **_failure_values(failure),
                )
                timed_out += 1
                terminal_job = self._job_row(
                    session, cast(UUID, job["id"]), lock=True
                )
                may_retry = (
                    JobState(str(job["state"])) is not JobState.CANCEL_REQUESTED
                    and int(terminal_job["attempt_count"])
                    < int(terminal_job["max_attempts"])
                    and cast(datetime, terminal_job["deadline_at"]) > now
                )
                if may_retry:
                    self._schedule_retry(
                        session,
                        job=terminal_job,
                        previous=self._attempt_row(session, cast(UUID, attempt["id"])),
                        attempt_id=attempt_ids[index],
                        kind=RetryKind.LEASE_RECOVERY,
                        reason="new attempt after expired worker lease",
                        actor_id=context.principal.id,
                        now=now,
                    )
                    retries += 1
                else:
                    jobs_timed_out += 1

            remaining = command.limit - len(expired)
            if remaining > 0:
                overdue = tuple(
                    session.execute(
                        sa.select(job_table.c.id, job_table.c.current_attempt_id)
                        .where(
                            job_table.c.state == JobState.QUEUED.value,
                            job_table.c.deadline_at <= now,
                        )
                        .order_by(job_table.c.deadline_at)
                        .limit(remaining)
                        .with_for_update(of=job_table, skip_locked=True)
                    ).mappings()
                )
                for overdue_ref in overdue:
                    job = self._job_row(
                        session, cast(UUID, overdue_ref["id"]), lock=True
                    )
                    failure = Failure(
                        FailureCategory.DEADLINE_EXCEEDED,
                        "deadline_exceeded",
                        "Job deadline elapsed before an attempt could finish.",
                    )
                    session.execute(
                        sa.update(job_attempt_table)
                        .where(
                            job_attempt_table.c.id
                            == overdue_ref["current_attempt_id"]
                        )
                        .values(
                            state=AttemptState.TIMED_OUT.value,
                            ended_at=now,
                            **_failure_values(failure),
                        )
                    )
                    self._transition_job(
                        session,
                        job,
                        JobState.TIMED_OUT,
                        now,
                        terminal_at=now,
                        **_failure_values(failure),
                    )
                    timed_out += 1
                    jobs_timed_out += 1
        return RecoveryResult(timed_out, retries, jobs_timed_out)
