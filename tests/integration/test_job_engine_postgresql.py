from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Lock
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.apps.worker import DurableJobWorker, HandlerResult, WorkerExecution
from cmp.modules.identity_access.adapters.persistence.rls import SqlAlchemyRlsContext
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.modules.jobs.adapters.contracts.jsonschema import (
    JsonSchemaJobContractValidator,
)
from cmp.modules.jobs.adapters.persistence.jobs import SqlAlchemyJobRepository
from cmp.modules.jobs.adapters.worker.queue import AuthorizedJobWorkerQueue
from cmp.modules.jobs.application.jobs import (
    CancelJob,
    ClaimedAttempt,
    ClaimJob,
    FinalizeAttempt,
    HeartbeatAttempt,
    JobService,
    RecoverExpired,
    RetryJob,
    StartAttempt,
    SubmitJob,
)
from cmp.modules.jobs.domain.jobs import (
    AttemptState,
    Failure,
    FailureCategory,
    FinalizeConflict,
    JobNotFound,
    JobState,
    LeaseLost,
    ResourcePolicy,
    RetryKind,
    RetryNotAllowed,
)
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.container_service,
    pytest.mark.skipif(
        not POSTGRES_DSN,
        reason="set CMP_TEST_POSTGRES_DSN to an isolated PostgreSQL admin URL",
    ),
]

NOW = datetime(2026, 7, 11, 8, 0, tzinfo=UTC)
ORG = UUID("83000000-0000-4000-8000-000000000001")
PROJECT_A = UUID("83000000-0000-4000-8000-000000000002")
PROJECT_B = UUID("83000000-0000-4000-8000-000000000003")
USER_A = UUID("83000000-0000-4000-8000-000000000004")
USER_B = UUID("83000000-0000-4000-8000-000000000005")
SERVICE = UUID("83000000-0000-4000-8000-000000000006")
RUNNER = UUID("83000000-0000-4000-8000-000000000007")
TRACE = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
MANIFEST_DIGEST = "a" * 64
JOB_TYPES = (
    "test.cancel",
    "test.concurrent",
    "test.crash",
    "test.finalize",
    "test.invalid",
    "test.isolation",
    "test.transient",
    "test.worker",
)


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self._value = value
        self._lock = Lock()

    def __call__(self) -> datetime:
        with self._lock:
            return self._value

    def advance(self, delta: timedelta) -> None:
        with self._lock:
            self._value += delta


@dataclass(frozen=True, slots=True)
class PostgresHarness:
    admin_engine: Engine
    app_engine: Engine
    database_url: URL
    app_role: str
    clock: MutableClock
    service: JobService


def _psycopg_url(value: str) -> URL:
    url = make_url(value)
    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise ValueError("CMP_TEST_POSTGRES_DSN must use PostgreSQL with psycopg")
    return url


def _alembic_config(database_url: URL) -> Config:
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"))
    configuration.set_main_option(
        "sqlalchemy.url",
        database_url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    return configuration


def _principal_values(
    principal_id: UUID, principal_type: str, display_name: str
) -> dict[str, object]:
    return {
        "id": principal_id,
        "principal_type": principal_type,
        "display_name": display_name,
        "active": True,
        "created_at": NOW - timedelta(days=1),
        "updated_at": NOW - timedelta(days=1),
    }


def _seed(connection: sa.Connection) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO identity.principal "
            "(id, principal_type, display_name, active, created_at, updated_at) "
            "VALUES (:id, :principal_type, :display_name, :active, :created_at, :updated_at)"
        ),
        [
            _principal_values(USER_A, "user", "Job User A"),
            _principal_values(USER_B, "user", "Job User B"),
            _principal_values(SERVICE, "service", "Job Runner Service"),
        ],
    )
    connection.execute(
        sa.text(
            "INSERT INTO jobs.runner ("
            "organization_id, project_id, id, classification, name, status, "
            "max_concurrency, cpu_capacity_millis, memory_capacity_mb, gpu_capacity, "
            "registered_at, created_by"
            ") VALUES ("
            ":organization_id, :project_id, :id, 'restricted', 'synthetic-runner', "
            "'active', 1, 8000, 32768, 2, :registered_at, :created_by"
            ")"
        ),
        {
            "organization_id": ORG,
            "project_id": PROJECT_A,
            "id": RUNNER,
            "registered_at": NOW - timedelta(hours=1),
            "created_by": SERVICE,
        },
    )
    connection.execute(
        sa.text(
            "INSERT INTO jobs.runner_job_type ("
            "organization_id, project_id, classification, runner_id, job_type, "
            "created_at, created_by"
            ") VALUES ("
            ":organization_id, :project_id, 'restricted', :runner_id, :job_type, "
            ":created_at, :created_by"
            ")"
        ),
        [
            {
                "organization_id": ORG,
                "project_id": PROJECT_A,
                "runner_id": RUNNER,
                "job_type": job_type,
                "created_at": NOW - timedelta(hours=1),
                "created_by": SERVICE,
            }
            for job_type in JOB_TYPES
        ],
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresHarness]:
    assert POSTGRES_DSN is not None
    admin_url = _psycopg_url(POSTGRES_DSN)
    database_name = f"cmp_t15_{uuid4().hex}"
    app_role = f"cmp_t15_app_{uuid4().hex}"
    cluster_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with cluster_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        connection.exec_driver_sql(
            f'CREATE ROLE "{app_role}" LOGIN NOSUPERUSER NOCREATEDB '
            "NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    database_url = admin_url.set(database=database_name)
    admin_engine = sa.create_engine(database_url, pool_pre_ping=True)
    app_engine: Engine | None = None
    try:
        command.upgrade(_alembic_config(database_url), "head")
        with admin_engine.begin() as connection:
            _seed(connection)
            connection.exec_driver_sql(
                f'GRANT USAGE ON SCHEMA identity, revisioning, access_control, jobs '
                f'TO "{app_role}"'
            )
            connection.exec_driver_sql(
                f'GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA jobs '
                f'TO "{app_role}"'
            )
            connection.exec_driver_sql(
                f'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA access_control, revisioning '
                f'TO "{app_role}"'
            )
        app_engine = sa.create_engine(
            database_url.set(username=app_role, password=None), pool_pre_ping=True
        )
        sessions = sessionmaker(app_engine, class_=Session, expire_on_commit=False)
        rls = SqlAlchemyRlsContext()
        with sessions() as session, session.begin():
            rls.assert_application_role(session)
        clock = MutableClock(NOW)
        repository = SqlAlchemyJobRepository(
            session_factory=sessions,
            rls_context=rls,
        )
        yield PostgresHarness(
            admin_engine,
            app_engine,
            database_url,
            app_role,
            clock,
            JobService(
                repository=repository,
                validator=JsonSchemaJobContractValidator(),
                clock=clock,
            ),
        )
    finally:
        if app_engine is not None:
            app_engine.dispose()
        command.downgrade(_alembic_config(database_url), "base")
        admin_engine.dispose()
        with cluster_engine.connect() as connection:
            connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
            connection.exec_driver_sql(f'DROP ROLE "{app_role}"')
        cluster_engine.dispose()


def _context(
    *,
    principal_id: UUID = USER_A,
    principal_type: PrincipalType = PrincipalType.USER,
    project_id: UUID = PROJECT_A,
) -> SecurityContext:
    return SecurityContext(
        principal=Principal(principal_id, principal_type, "Synthetic Job Actor", True),
        organization_id=ORG,
        project_id=project_id,
        issuer="https://test-idp.invalid",
        subject=str(principal_id),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(
    context: SecurityContext, permission: Permission
) -> AuthorizationDecision:
    role = Role.JOB_RUNNER if permission is Permission.JOB_EXECUTE else Role.TEST_ENGINEER
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=context.organization_id,
        project_id=context.project_id,
        permission=permission,
        roles=(role,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.RESTRICTED,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


def _job_spec(job_id: UUID, attempt_id: UUID, deadline: datetime) -> dict[str, Any]:
    document = cast(
        dict[str, Any],
        json.loads(
            (PROJECT_ROOT / "contracts/examples/positive/job-spec.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    document["job_id"] = str(job_id)
    document["attempt_id"] = str(attempt_id)
    document["execution"]["deadline"] = deadline.isoformat().replace("+00:00", "Z")
    return document


def _submit(
    postgres: PostgresHarness,
    job_type: str,
    *,
    maximum_attempts: int = 3,
    context: SecurityContext | None = None,
) -> tuple[SecurityContext, UUID]:
    actor = context or _context()
    job_id = uuid4()
    result = postgres.service.submit(
        actor,
        _decision(actor, Permission.JOB_SUBMIT),
        SubmitJob(
            job_type,
            DataClassification.INTERNAL,
            _job_spec(
                job_id,
                uuid4(),
                postgres.clock() + timedelta(hours=1),
            ),
            ResourcePolicy(1000, 1024, 0, maximum_attempts),
            0,
            str(uuid4()),
        ),
    )
    assert result.details.job.state is JobState.QUEUED
    return actor, job_id


def _runner_scope() -> tuple[SecurityContext, AuthorizationDecision]:
    context = _context(principal_id=SERVICE, principal_type=PrincipalType.SERVICE)
    return context, _decision(context, Permission.JOB_EXECUTE)


def _claim_and_start(
    postgres: PostgresHarness, job_type: str
) -> tuple[SecurityContext, AuthorizationDecision, ClaimedAttempt]:
    context, decision = _runner_scope()
    claimed = postgres.service.claim(
        context,
        decision,
        ClaimJob(RUNNER, (job_type,), timedelta(seconds=30)),
    )
    assert claimed is not None
    assert claimed.attempt.lease_token is not None
    started = postgres.service.start(
        context,
        decision,
        StartAttempt(claimed.attempt.id, claimed.attempt.lease_token),
    )
    return context, decision, started


def _succeed(
    postgres: PostgresHarness,
    context: SecurityContext,
    decision: AuthorizationDecision,
    claimed: ClaimedAttempt,
    *,
    digest: str = MANIFEST_DIGEST,
) -> None:
    assert claimed.attempt.lease_token is not None
    result = postgres.service.finalize(
        context,
        decision,
        FinalizeAttempt(
            claimed.attempt.id,
            claimed.attempt.lease_token,
            AttemptState.SUCCEEDED,
            uuid4(),
            digest,
        ),
    )
    assert result.job.state is JobState.SUCCEEDED


def test_concurrent_atomic_claim_returns_one_owner(
    postgres: PostgresHarness,
) -> None:
    _submit(postgres, "test.concurrent")
    _submit(postgres, "test.concurrent")
    context, decision = _runner_scope()
    barrier = Barrier(2)

    def claim(_: int) -> ClaimedAttempt | None:
        barrier.wait(timeout=10)
        return postgres.service.claim(
            context,
            decision,
            ClaimJob(RUNNER, ("test.concurrent",), timedelta(seconds=30)),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(claim, (1, 2)))
    winners = [item for item in results if item is not None]
    assert len(winners) == 1
    winner = winners[0]
    assert winner.attempt.lease_token is not None
    started = postgres.service.start(
        context,
        decision,
        StartAttempt(winner.attempt.id, winner.attempt.lease_token),
    )
    _succeed(postgres, context, decision, started)
    remaining = postgres.service.claim(
        context,
        decision,
        ClaimJob(RUNNER, ("test.concurrent",), timedelta(seconds=30)),
    )
    assert remaining is not None
    assert remaining.attempt.lease_token is not None
    remaining = postgres.service.start(
        context,
        decision,
        StartAttempt(remaining.attempt.id, remaining.attempt.lease_token),
    )
    _succeed(postgres, context, decision, remaining)


def test_expired_crash_lease_appends_new_attempt_and_fences_stale_worker(
    postgres: PostgresHarness,
) -> None:
    _, job_id = _submit(postgres, "test.crash")
    context, decision, first = _claim_and_start(postgres, "test.crash")
    assert first.job.id == job_id
    assert first.attempt.lease_token is not None
    postgres.clock.advance(timedelta(seconds=31))

    recovered = postgres.service.recover_expired(
        context, decision, RecoverExpired(limit=10)
    )
    read_context = _context()
    details = postgres.service.get(
        read_context, _decision(read_context, Permission.JOB_READ), job_id
    )

    assert recovered.attempts_timed_out == 1
    assert recovered.retries_scheduled == 1
    assert details.job.state is JobState.QUEUED
    assert len(details.attempts) == 2
    assert details.attempts[0].state is AttemptState.TIMED_OUT
    assert details.attempts[1].retry_kind is RetryKind.LEASE_RECOVERY
    assert (
        details.attempts[0].spec.canonical_document
        != details.attempts[1].spec.canonical_document
    )

    with pytest.raises(LeaseLost):
        postgres.service.heartbeat(
            context,
            decision,
            HeartbeatAttempt(
                first.attempt.id,
                first.attempt.lease_token,
                timedelta(seconds=30),
            ),
        )
    runner_context, runner_decision, second = _claim_and_start(
        postgres, "test.crash"
    )
    _succeed(postgres, runner_context, runner_decision, second)


def test_running_cancel_is_cooperative_and_preserves_attempt(
    postgres: PostgresHarness,
) -> None:
    actor, job_id = _submit(postgres, "test.cancel")
    runner_context, runner_decision, claimed = _claim_and_start(
        postgres, "test.cancel"
    )
    cancelled = postgres.service.cancel(
        actor,
        _decision(actor, Permission.JOB_CONTROL),
        CancelJob(job_id, "operator requested cancellation"),
    )
    assert cancelled.job.state is JobState.CANCEL_REQUESTED
    assert claimed.attempt.lease_token is not None

    heartbeat = postgres.service.heartbeat(
        runner_context,
        runner_decision,
        HeartbeatAttempt(
            claimed.attempt.id,
            claimed.attempt.lease_token,
            timedelta(seconds=30),
        ),
    )
    assert heartbeat.cancellation_requested
    finalized = postgres.service.finalize(
        runner_context,
        runner_decision,
        FinalizeAttempt(
            claimed.attempt.id,
            claimed.attempt.lease_token,
            AttemptState.CANCELLED,
        ),
    )
    assert finalized.job.state is JobState.CANCELLED
    assert finalized.attempt.state is AttemptState.CANCELLED

    actor, failed_job_id = _submit(postgres, "test.cancel")
    runner_context, runner_decision, claimed = _claim_and_start(
        postgres, "test.cancel"
    )
    postgres.service.cancel(
        actor,
        _decision(actor, Permission.JOB_CONTROL),
        CancelJob(failed_job_id, "cancel before a transient worker failure"),
    )
    assert claimed.attempt.lease_token is not None
    failed = postgres.service.finalize(
        runner_context,
        runner_decision,
        FinalizeAttempt(
            claimed.attempt.id,
            claimed.attempt.lease_token,
            AttemptState.FAILED,
            failure=Failure(
                FailureCategory.TRANSIENT_INFRASTRUCTURE,
                "cancel_race_failure",
                "Synthetic failure after cancellation was requested.",
            ),
        ),
    )
    assert failed.job.state is JobState.FAILED
    assert not failed.retry_scheduled
    with pytest.raises(RetryNotAllowed, match="cancelled execution"):
        postgres.service.retry(
            actor,
            _decision(actor, Permission.JOB_CONTROL),
            RetryJob(failed_job_id, "cancelled executions stay terminal"),
        )


def test_duplicate_finalize_is_idempotent_but_different_digest_conflicts(
    postgres: PostgresHarness,
) -> None:
    _submit(postgres, "test.finalize")
    context, decision, claimed = _claim_and_start(postgres, "test.finalize")
    assert claimed.attempt.lease_token is not None
    manifest_id = uuid4()
    command_value = FinalizeAttempt(
        claimed.attempt.id,
        claimed.attempt.lease_token,
        AttemptState.SUCCEEDED,
        manifest_id,
        MANIFEST_DIGEST,
    )

    first = postgres.service.finalize(context, decision, command_value)
    replay = postgres.service.finalize(context, decision, command_value)

    assert not first.idempotent
    assert replay.idempotent
    with pytest.raises(FinalizeConflict):
        postgres.service.finalize(
            context,
            decision,
            FinalizeAttempt(
                claimed.attempt.id,
                claimed.attempt.lease_token,
                AttemptState.SUCCEEDED,
                manifest_id,
                "b" * 64,
            ),
        )


def test_domain_invalid_input_is_terminal_and_cannot_be_retried(
    postgres: PostgresHarness,
) -> None:
    actor, job_id = _submit(postgres, "test.invalid")
    context, decision, claimed = _claim_and_start(postgres, "test.invalid")
    assert claimed.attempt.lease_token is not None
    result = postgres.service.finalize(
        context,
        decision,
        FinalizeAttempt(
            claimed.attempt.id,
            claimed.attempt.lease_token,
            AttemptState.FAILED,
            failure=Failure(
                FailureCategory.DOMAIN_INVALID,
                "invalid_input",
                "Immutable input failed the generic domain validation boundary.",
            ),
        ),
    )
    assert result.job.state is JobState.FAILED
    assert not result.retry_scheduled

    with pytest.raises(RetryNotAllowed, match="immutable invalid input"):
        postgres.service.retry(
            actor,
            _decision(actor, Permission.JOB_CONTROL),
            RetryJob(job_id, "try the same invalid input again"),
        )


def test_transient_failure_schedules_distinct_attempt_then_succeeds(
    postgres: PostgresHarness,
) -> None:
    _, job_id = _submit(postgres, "test.transient")
    context, decision, claimed = _claim_and_start(postgres, "test.transient")
    assert claimed.attempt.lease_token is not None
    result = postgres.service.finalize(
        context,
        decision,
        FinalizeAttempt(
            claimed.attempt.id,
            claimed.attempt.lease_token,
            AttemptState.FAILED,
            failure=Failure(
                FailureCategory.TRANSIENT_INFRASTRUCTURE,
                "connection_lost",
                "Synthetic transient infrastructure failure.",
            ),
        ),
    )
    assert result.retry_scheduled
    assert result.job.state is JobState.QUEUED
    read_context = _context()
    details = postgres.service.get(
        read_context, _decision(read_context, Permission.JOB_READ), job_id
    )
    assert [item.state for item in details.attempts] == [
        AttemptState.FAILED,
        AttemptState.QUEUED,
    ]
    assert details.attempts[0].spec.digest != details.attempts[1].spec.digest

    context, decision, claimed = _claim_and_start(postgres, "test.transient")
    _succeed(postgres, context, decision, claimed)


def test_rls_hides_job_from_other_project_and_queued_cancel_is_atomic(
    postgres: PostgresHarness,
) -> None:
    actor, job_id = _submit(postgres, "test.isolation")
    other = _context(principal_id=USER_B, project_id=PROJECT_B)
    with pytest.raises(JobNotFound):
        postgres.service.get(other, _decision(other, Permission.JOB_READ), job_id)

    cancelled = postgres.service.cancel(
        actor,
        _decision(actor, Permission.JOB_CONTROL),
        CancelJob(job_id, "cancel before claim"),
    )
    assert cancelled.job.state is JobState.CANCELLED
    assert cancelled.attempts[0].state is AttemptState.CANCELLED


def test_terminal_attempt_and_job_spec_cannot_be_overwritten(
    postgres: PostgresHarness,
) -> None:
    with postgres.admin_engine.connect() as connection:
        terminal = connection.execute(
            sa.text(
                "SELECT id, job_id FROM jobs.job_attempt WHERE state = 'succeeded' "
                "ORDER BY ended_at LIMIT 1"
            )
        ).one()
    with pytest.raises(DBAPIError) as error, postgres.admin_engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE jobs.job_attempt "
                "SET job_spec = jsonb_set(job_spec, '{operation}', '" + '"mutated"' + "') "
                "WHERE id = :attempt_id"
            ),
            {"attempt_id": terminal.id},
        )
    assert getattr(error.value.orig, "sqlstate", None) == "55000"

    with pytest.raises(DBAPIError) as job_error, postgres.admin_engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE jobs.job SET result_manifest_digest = :digest, "
                "row_version = row_version + 1, "
                "updated_at = updated_at + interval '1 second' "
                "WHERE id = :job_id"
            ),
            {"digest": "c" * 64, "job_id": terminal.job_id},
        )
    assert getattr(job_error.value.orig, "sqlstate", None) == "55000"


def test_authorized_queue_runs_worker_to_terminal_manifest(
    postgres: PostgresHarness,
) -> None:
    _, job_id = _submit(postgres, "test.worker")
    context, decision = _runner_scope()
    queue = AuthorizedJobWorkerQueue(
        service=postgres.service,
        context=context,
        decision=decision,
        runner_id=RUNNER,
        lease_duration=timedelta(seconds=30),
    )

    async def handler(execution: WorkerExecution) -> HandlerResult:
        assert execution.claimed.job.id == job_id
        return HandlerResult(AttemptState.SUCCEEDED, uuid4(), "d" * 64)

    result = asyncio.run(
        DurableJobWorker(
            queue=queue,
            handlers={"test.worker": handler},
            heartbeat_interval_seconds=5,
            lease_duration=timedelta(seconds=30),
        ).run_once()
    )
    read_context = _context()
    details = postgres.service.get(
        read_context, _decision(read_context, Permission.JOB_READ), job_id
    )

    assert result.status == "succeeded"
    assert details.job.state is JobState.SUCCEEDED
    assert details.job.result_manifest_digest == "d" * 64
