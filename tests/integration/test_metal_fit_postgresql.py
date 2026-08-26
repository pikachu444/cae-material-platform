from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.identity_access.adapters.persistence.rls import SqlAlchemyRlsContext
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.processing.adapters.persistence.metal_fit_runs import (
    SqlAlchemyMetalFitRunRepository,
)
from cmp.modules.processing.application.common_outputs import ExactRevisionPin
from cmp.modules.processing.application.metal_fit_runs import (
    MetalFitAttempt,
    MetalFitAttemptStatus,
    MetalFitRun,
    MetalFitRunStatus,
    MetalFitTerminalConflict,
)
from cmp.modules.processing.domain.metal_hardening import HARDENING_FAMILIES
from sqlalchemy.engine import URL, Engine, make_url
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

NOW = datetime(2025, 1, 1, 13, 0, tzinfo=UTC)
ORG = UUID("e1580000-0000-4000-8000-000000000001")
PROJECT_A = UUID("e1580000-0000-4000-8000-000000000002")
PROJECT_B = UUID("e1580000-0000-4000-8000-000000000003")
ACTOR = UUID("e1580000-0000-4000-8000-000000000004")
RUN_ID = UUID("e1580000-0000-4000-8000-000000000005")
RUN_REVISION = UUID("e1580000-0000-4000-8000-000000000006")
ATTEMPT_ID = UUID("e1580000-0000-4000-8000-000000000007")
FAILED_ATTEMPT_ID = UUID("e1580000-0000-4000-8000-000000000011")
SOURCE_OUTPUT = UUID("e1580000-0000-4000-8000-000000000008")
SOURCE_OUTPUT_REVISION = UUID("e1580000-0000-4000-8000-000000000009")
SOURCE_DOCUMENT = UUID("e1580000-0000-4000-8000-00000000000a")
SOURCE_DOCUMENT_REVISION = UUID("e1580000-0000-4000-8000-00000000000b")
MAPPING_PROFILE = UUID("e1580000-0000-4000-8000-00000000000c")
MAPPING_PROFILE_REVISION = UUID("e1580000-0000-4000-8000-00000000000d")
OUTPUT_ARTIFACT = UUID("e1580000-0000-4000-8000-00000000000e")
REQUEST_ID = UUID("e1580000-0000-4000-8000-00000000000f")
TRACE_ID = "00-0000000000000000000000000000e158-000000000000e158-01"


@dataclass(frozen=True, slots=True)
class PostgresHarness:
    admin_engine: Engine
    app_engine: Engine
    sessions: sessionmaker[Session]
    rls: SqlAlchemyRlsContext
    repository: SqlAlchemyMetalFitRunRepository
    database_url: URL
    app_role: str


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


def _seed(connection: sa.Connection, app_role: str) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO identity.principal "
            "(id, principal_type, display_name, active, created_at, updated_at) "
            "VALUES (:id, 'user', 'Metal Fit User', true, :now, :now)"
        ),
        {"id": ACTOR, "now": NOW - timedelta(days=1)},
    )
    connection.execute(
        sa.text(
            "INSERT INTO identity.role_binding "
            "(id, organization_id, project_id, classification, subject_type, principal_id, "
            "role, max_classification, allow_export_controlled, valid_from, created_at, "
            "created_by, grant_reason) "
            "VALUES (:id, :organization_id, :project_id, 'restricted', 'principal', :principal_id, "
            "'material_modeler', 'internal', false, :valid_from, :created_at, :created_by, :reason)"
        ),
        {
            "id": UUID("e1580000-0000-4000-8000-000000000010"),
            "organization_id": ORG,
            "project_id": PROJECT_A,
            "principal_id": ACTOR,
            "valid_from": NOW - timedelta(hours=1),
            "created_at": NOW - timedelta(hours=2),
            "created_by": ACTOR,
            "reason": "metal Fit PostgreSQL integration fixture",
        },
    )
    # The source Processing Output is only a FK anchor for this repository
    # test.  Its domain foreign keys point to fixture IDs that are not needed
    # by the run repository, so seed it in the isolated database with the
    # admin role while replication triggers are disabled.
    connection.exec_driver_sql("SET session_replication_role = 'replica'")
    connection.execute(
        sa.text(
            "INSERT INTO processing.common_processing_output "
            "(id, organization_id, project_id, classification, label, current_revision_id, "
            "created_at, created_by, updated_at) "
            "VALUES (:id, :organization_id, :project_id, 'internal', 'Fit source', :revision, "
            ":now, :created_by, :now)"
        ),
        {
            "id": SOURCE_OUTPUT,
            "organization_id": ORG,
            "project_id": PROJECT_A,
            "revision": SOURCE_OUTPUT_REVISION,
            "now": NOW,
            "created_by": ACTOR,
        },
    )
    connection.execute(
        sa.text(
            "INSERT INTO processing.common_processing_output_revision "
            "(id, aggregate_id, organization_id, project_id, classification, revision_no, "
            "schema_id, schema_version, content_hash, created_at, created_by, change_reason, "
            "request_id, trace_id, label, source_document_id, source_document_revision_id, "
            "source_document_sha256, source_canonical_artifact_sha256, mapping_profile_id, "
            "mapping_profile_revision_id, mapping_profile_sha256, independent_quantity, "
            "step_count, stage_count, final_point_count, output_artifact_id, output_sha256) "
            "VALUES (:id, :aggregate_id, :organization_id, :project_id, 'internal', 1, "
            ":schema_id, '1.3.0', :content_hash, :now, :created_by, :reason, :request_id, "
            ":trace_id, 'Fit source', :source_document_id, :source_document_revision_id, "
            ":source_document_sha256, :source_artifact_sha256, :mapping_profile_id, "
            ":mapping_profile_revision_id, :mapping_profile_sha256, 'strain.plastic', 1, 2, 2, "
            ":artifact_id, :output_sha256)"
        ),
        {
            "id": SOURCE_OUTPUT_REVISION,
            "aggregate_id": SOURCE_OUTPUT,
            "organization_id": ORG,
            "project_id": PROJECT_A,
            "schema_id": "urn:cmp:processing:common-output:1.3.0",
            "content_hash": "1" * 64,
            "now": NOW,
            "created_by": ACTOR,
            "reason": "metal Fit PostgreSQL integration fixture",
            "request_id": REQUEST_ID,
            "trace_id": TRACE_ID,
            "source_document_id": SOURCE_DOCUMENT,
            "source_document_revision_id": SOURCE_DOCUMENT_REVISION,
            "source_document_sha256": "2" * 64,
            "source_artifact_sha256": "3" * 64,
            "mapping_profile_id": MAPPING_PROFILE,
            "mapping_profile_revision_id": MAPPING_PROFILE_REVISION,
            "mapping_profile_sha256": "4" * 64,
            "artifact_id": OUTPUT_ARTIFACT,
            "output_sha256": "5" * 64,
        },
    )
    connection.exec_driver_sql("SET session_replication_role = 'origin'")
    connection.exec_driver_sql(
        "GRANT USAGE ON SCHEMA identity, revisioning, access_control, processing "
        f'TO "{app_role}"'
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresHarness]:
    assert POSTGRES_DSN is not None
    admin_url = _psycopg_url(POSTGRES_DSN)
    database_name = f"cmp_t3b_{uuid4().hex}"
    app_role = f"cmp_t3b_app_{uuid4().hex}"
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
            _seed(connection, app_role)
            connection.exec_driver_sql(
                f"GRANT SELECT, INSERT, UPDATE ON processing.metal_fit_run, "
                f"processing.metal_fit_attempt, processing.common_processing_output_revision, "
                f"processing.metal_fit_run_unit_application "
                f'TO "{app_role}"'
            )
            connection.exec_driver_sql(
                f'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA access_control TO "{app_role}"'
            )
        app_engine = sa.create_engine(
            database_url.set(username=app_role, password=None), pool_pre_ping=True
        )
        sessions = sessionmaker(app_engine, class_=Session, expire_on_commit=False)
        rls = SqlAlchemyRlsContext()
        with sessions() as session, session.begin():
            rls.assert_application_role(session)
        yield PostgresHarness(
            admin_engine=admin_engine,
            app_engine=app_engine,
            sessions=sessions,
            rls=rls,
            repository=SqlAlchemyMetalFitRunRepository(
                session_factory=sessions,
                rls_context=rls,
            ),
            database_url=database_url,
            app_role=app_role,
        )
    finally:
        if app_engine is not None:
            app_engine.dispose()
        try:
            command.downgrade(_alembic_config(database_url), "base")
        finally:
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


def _context(*, project_id: UUID = PROJECT_A) -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Metal Fit User", True),
        organization_id=ORG,
        project_id=project_id,
        issuer="urn:cmp:metal-fit-postgresql",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=REQUEST_ID,
        trace_id=TRACE_ID,
        authenticated_at=NOW,
    )


def _decision(context: SecurityContext, permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=context.project_id,
        permission=permission,
        roles=(Role.MATERIAL_MODELER,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=REQUEST_ID,
        trace_id=TRACE_ID,
        decided_at=NOW,
    )


def _run() -> MetalFitRun:
    return MetalFitRun(
        id=RUN_ID,
        classification=DataClassification.INTERNAL,
        source_processing_output=ExactRevisionPin(SOURCE_OUTPUT, SOURCE_OUTPUT_REVISION),
        source_processing_output_sha256="5" * 64,
        source_document=ExactRevisionPin(SOURCE_DOCUMENT, SOURCE_DOCUMENT_REVISION),
        mapping_profile=ExactRevisionPin(MAPPING_PROFILE, MAPPING_PROFILE_REVISION),
        options={"families": list(HARDENING_FAMILIES)},
        reproducibility_evidence={"execution": "pending", "runtime": {"source_commit": "fixture"}},
        status=MetalFitRunStatus.EXECUTING,
        failure_code=None,
        failure_reason=None,
        started_at=NOW,
        ended_at=None,
        created_at=NOW,
        created_by=ACTOR,
        request_id=REQUEST_ID,
        trace_id=TRACE_ID,
    )


def test_repository_round_trip_terminal_once_and_rls_scope(postgres: PostgresHarness) -> None:
    context = _context()
    execute = _decision(context, Permission.PROCESSING_EXECUTE)
    read = _decision(context, Permission.PROCESSING_READ)
    repository = postgres.repository
    run = repository.create_run(context=context, decision=execute, run=_run())
    attempt = repository.create_attempt(
        context=context,
        decision=execute,
        attempt=MetalFitAttempt(
            id=ATTEMPT_ID,
            run_id=run.id,
            ordinal=0,
            family="voce",
            status=MetalFitAttemptStatus.EXECUTING,
            result=None,
            objective_history=(),
            failure_code=None,
            failure_reason=None,
            started_at=NOW,
            ended_at=None,
        ),
    )
    with postgres.admin_engine.connect() as connection:
        assert connection.execute(
            sa.text("SELECT result IS NULL FROM processing.metal_fit_attempt WHERE id = :id"),
            {"id": ATTEMPT_ID},
        ).scalar_one()
    assert repository.get_run(context=context, decision=read, run_id=run.id).id == run.id
    repository.succeed_attempt(
        context=context,
        decision=execute,
        attempt_id=attempt.id,
        result={"family": "voce"},
        objective_history=(1.0, 0.1),
    )
    failed_attempt = repository.create_attempt(
        context=context,
        decision=execute,
        attempt=MetalFitAttempt(
            id=FAILED_ATTEMPT_ID,
            run_id=run.id,
            ordinal=1,
            family="swift",
            status=MetalFitAttemptStatus.EXECUTING,
            result=None,
            objective_history=(),
            failure_code=None,
            failure_reason=None,
            started_at=NOW,
            ended_at=None,
        ),
    )
    repository.fail_attempt(
        context=context,
        decision=execute,
        attempt_id=failed_attempt.id,
        failure_code="optimizer_not_converged",
        failure_reason="fixture failure",
    )
    with postgres.admin_engine.connect() as connection:
        assert connection.execute(
            sa.text("SELECT result IS NULL FROM processing.metal_fit_attempt WHERE id = :id"),
            {"id": FAILED_ATTEMPT_ID},
        ).scalar_one()
    repository.succeed_run(
        context=context,
        decision=execute,
        run_id=run.id,
        reproducibility_evidence={"execution": "completed", "exact_source_digest": "5" * 64},
    )
    terminal = repository.get_run(context=context, decision=read, run_id=run.id)
    assert terminal.status is MetalFitRunStatus.SUCCEEDED
    assert (
        repository.list_attempts(context=context, decision=read, run_id=run.id)[0].status
        is MetalFitAttemptStatus.SUCCEEDED
    )
    with pytest.raises(MetalFitTerminalConflict):
        repository.fail_run(
            context=context,
            decision=execute,
            run_id=run.id,
            failure_code="late_failure",
            failure_reason="terminal transition must be rejected",
        )
    with pytest.raises(MetalFitTerminalConflict):
        repository.fail_attempt(
            context=context,
            decision=execute,
            attempt_id=attempt.id,
            failure_code="late_failure",
            failure_reason="terminal transition must be rejected",
        )
    other_context = _context(project_id=PROJECT_B)
    assert (
        repository.list_runs(
            context=other_context,
            decision=_decision(other_context, Permission.PROCESSING_READ),
        )
        == ()
    )
