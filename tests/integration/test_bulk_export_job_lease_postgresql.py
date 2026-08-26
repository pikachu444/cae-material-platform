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
from cmp.modules.exporting.adapters.persistence.bulk_export_repository import (
    SqlAlchemyBulkExportRepository,
)
from cmp.modules.exporting.domain.bulk_bundle import BulkExportConflict, BulkExportJobState
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
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.container_service,
    pytest.mark.skipif(
        POSTGRES_DSN is None,
        reason="CMP_TEST_POSTGRES_DSN is required for PostgreSQL integration",
    ),
]

NOW = datetime(2026, 8, 24, 9, 0, tzinfo=UTC)
ORG = UUID("98000000-0000-4000-8000-000000000001")
PROJECT = UUID("98000000-0000-4000-8000-000000000002")
ACTOR = UUID("98000000-0000-4000-8000-000000000003")
SELECTION = UUID("98000000-0000-4000-8000-000000000004")
SELECTION_REVISION = UUID("98000000-0000-4000-8000-000000000005")
JOB = UUID("98000000-0000-4000-8000-000000000006")
FIRST_TOKEN = UUID("98000000-0000-4000-8000-000000000007")
SECOND_TOKEN = UUID("98000000-0000-4000-8000-000000000008")
TRACE = "00-98000000000000000000000000000000-9800000000000000-01"


@dataclass(frozen=True, slots=True)
class PostgresHarness:
    admin_engine: Engine
    app_engine: Engine
    repository: SqlAlchemyBulkExportRepository


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


def _seed_legacy_active_job(connection: sa.Connection) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO identity.principal "
            "(id, principal_type, display_name, active, created_at, updated_at) "
            "VALUES (:actor, 'service', 'Bulk Export lease worker', true, :now, :now)"
        ),
        {"actor": ACTOR, "now": NOW - timedelta(days=1)},
    )
    # This fixture is intentionally not an Export Selection test. The deferred snapshot
    # validator is disabled only while creating the minimum immutable FK parent records.
    connection.exec_driver_sql(
        "ALTER TABLE exporting.export_selection_revision "
        "DISABLE TRIGGER export_selection_revision_snapshot_guard"
    )
    connection.execute(
        sa.text(
            "INSERT INTO exporting.export_selection "
            "(id, organization_id, project_id, classification, current_revision_id, "
            "selection_label, created_at, created_by, updated_at) VALUES "
            "(:selection, :organization, :project, 'internal', :revision, "
            "'Lease recovery fixture', :now, :actor, :now)"
        ),
        {
            "selection": SELECTION,
            "revision": SELECTION_REVISION,
            "organization": ORG,
            "project": PROJECT,
            "actor": ACTOR,
            "now": NOW,
        },
    )
    connection.execute(
        sa.text(
            "INSERT INTO exporting.export_selection_revision "
            "(id, aggregate_id, organization_id, project_id, classification, revision_no, "
            "based_on_revision_id, schema_id, schema_version, content_hash, created_at, "
            "created_by, change_reason, request_id, trace_id, selection_label, member_count, "
            "omission_count, expected_size_bytes) VALUES "
            "(:revision, :selection, :organization, :project, 'internal', 1, NULL, "
            "'urn:cmp:test:lease-selection', '1.0.0', :content_hash, :now, :actor, "
            "'PostgreSQL lease integration fixture', :request_id, :trace_id, "
            "'Lease recovery fixture', 1, 0, 1)"
        ),
        {
            "revision": SELECTION_REVISION,
            "selection": SELECTION,
            "organization": ORG,
            "project": PROJECT,
            "content_hash": "a" * 64,
            "now": NOW,
            "actor": ACTOR,
            "request_id": uuid4(),
            "trace_id": TRACE,
        },
    )
    connection.exec_driver_sql(
        "ALTER TABLE exporting.export_selection_revision "
        "ENABLE TRIGGER export_selection_revision_snapshot_guard"
    )
    connection.execute(
        sa.text(
            "INSERT INTO exporting.bulk_export_job "
            "(id, organization_id, project_id, classification, selection_id, "
            "selection_revision_id, state, attempt_count, bundle_id, failure_code, "
            "failure_detail, submitted_at, submitted_by, started_at, completed_at) VALUES "
            "(:job, :organization, :project, 'internal', :selection, :revision, "
            "'running', 1, NULL, NULL, NULL, :now, :actor, :started_at, NULL)"
        ),
        {
            "job": JOB,
            "organization": ORG,
            "project": PROJECT,
            "selection": SELECTION,
            "revision": SELECTION_REVISION,
            "now": NOW,
            "started_at": NOW - timedelta(minutes=1),
            "actor": ACTOR,
        },
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresHarness]:
    assert POSTGRES_DSN is not None
    admin_url = _psycopg_url(POSTGRES_DSN)
    database_name = f"cmp_t47_lease_{uuid4().hex}"
    app_role = f"cmp_t47_lease_app_{uuid4().hex}"
    cluster = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with cluster.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        connection.exec_driver_sql(
            f'CREATE ROLE "{app_role}" LOGIN NOSUPERUSER NOCREATEDB '
            "NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )

    database_url = admin_url.set(database=database_name)
    admin_engine = sa.create_engine(database_url, pool_pre_ping=True)
    app_engine: Engine | None = None
    try:
        command.upgrade(_alembic_config(database_url), "20260823_057_t47_bundle")
        with admin_engine.begin() as connection:
            _seed_legacy_active_job(connection)
        command.upgrade(_alembic_config(database_url), "head")
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(
                f'GRANT USAGE ON SCHEMA access_control, revisioning, exporting TO "{app_role}"'
            )
            connection.exec_driver_sql(
                "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA exporting "
                f'TO "{app_role}"'
            )
            connection.exec_driver_sql(
                "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA access_control, revisioning "
                f'TO "{app_role}"'
            )
        app_engine = sa.create_engine(
            database_url.set(username=app_role, password=None), pool_pre_ping=True
        )
        sessions = sessionmaker(app_engine, class_=Session, expire_on_commit=False)
        rls = SqlAlchemyRlsContext()
        with sessions() as session, session.begin():
            rls.assert_application_role(session)
        yield PostgresHarness(
            admin_engine,
            app_engine,
            SqlAlchemyBulkExportRepository(session_factory=sessions, rls_context=rls),
        )
    finally:
        if app_engine is not None:
            app_engine.dispose()
        admin_engine.dispose()
        with cluster.connect() as connection:
            connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=:database_name AND pid<>pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
            connection.exec_driver_sql(f'DROP ROLE "{app_role}"')
        cluster.dispose()


def _context() -> SecurityContext:
    return SecurityContext(
        Principal(ACTOR, PrincipalType.SERVICE, "Bulk Export lease worker", True),
        ORG,
        PROJECT,
        "https://test.invalid",
        str(ACTOR),
        "t47-lease-token",
        (),
        (),
        uuid4(),
        TRACE,
        NOW,
    )


def _decision(context: SecurityContext) -> AuthorizationDecision:
    return AuthorizationDecision(
        ACTOR,
        ORG,
        PROJECT,
        Permission.EXPORT_EXECUTE,
        (Role.MATERIAL_MODELER,),
        database_permissions_for(Permission.EXPORT_EXECUTE),
        DataClassification.INTERNAL,
        False,
        context.request_id,
        TRACE,
        NOW,
    )


def test_expired_lease_is_reclaimed_and_stale_worker_is_fenced(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    decision = _decision(context)
    repository = postgres.repository

    with postgres.admin_engine.connect() as connection:
        migrated = connection.execute(
            sa.text(
                "SELECT state, attempt_count, lease_token, heartbeat_at, lease_expires_at "
                "FROM exporting.bulk_export_job WHERE id=:job"
            ),
            {"job": JOB},
        ).mappings().one()
    assert migrated["state"] == "running"
    assert migrated["attempt_count"] == 1
    assert migrated["lease_token"] is not None
    assert migrated["heartbeat_at"] == NOW - timedelta(minutes=1)
    reclaim_at = migrated["lease_expires_at"]
    assert isinstance(reclaim_at, datetime)
    assert reclaim_at > migrated["heartbeat_at"]

    first = repository.claim_next_job(
        context=context,
        decision=decision,
        lease_token=FIRST_TOKEN,
        lease_duration=timedelta(seconds=10),
        now=reclaim_at,
    )
    assert first is not None
    assert first.state is BulkExportJobState.RUNNING
    assert first.lease_token == FIRST_TOKEN
    assert first.attempt_count == 2

    renewed = repository.renew_job_lease(
        context=context,
        decision=decision,
        job_id=JOB,
        lease_token=FIRST_TOKEN,
        lease_duration=timedelta(seconds=10),
        now=reclaim_at + timedelta(seconds=4),
    )
    assert renewed.heartbeat_at == reclaim_at + timedelta(seconds=4)
    assert renewed.lease_expires_at == reclaim_at + timedelta(seconds=14)
    assert (
        repository.claim_next_job(
            context=context,
            decision=decision,
            lease_token=SECOND_TOKEN,
            lease_duration=timedelta(seconds=10),
            now=reclaim_at + timedelta(seconds=11),
        )
        is None
    )

    with pytest.raises(DBAPIError, match="invalid Bulk Export Job state or lease transition"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE exporting.bulk_export_job SET heartbeat_at=:heartbeat, "
                    "lease_expires_at=:expiry WHERE id=:job"
                ),
                {
                    "heartbeat": reclaim_at + timedelta(seconds=15),
                    "expiry": reclaim_at + timedelta(seconds=25),
                    "job": JOB,
                },
            )

    reclaimed = repository.claim_next_job(
        context=context,
        decision=decision,
        lease_token=SECOND_TOKEN,
        lease_duration=timedelta(seconds=10),
        now=reclaim_at + timedelta(seconds=15),
    )
    assert reclaimed is not None
    assert reclaimed.lease_token == SECOND_TOKEN
    assert reclaimed.attempt_count == 3

    with pytest.raises(BulkExportConflict, match="lost or expired"):
        repository.fail_job(
            context=context,
            decision=decision,
            job_id=JOB,
            failure_code="stale_worker",
            failure_detail="an expired worker must not finalize the reclaimed job",
            lease_token=FIRST_TOKEN,
            now=reclaim_at + timedelta(seconds=16),
        )

    failed = repository.fail_job(
        context=context,
        decision=decision,
        job_id=JOB,
        failure_code="fixture_complete",
        failure_detail="the current fencing token owns this terminal transition",
        lease_token=SECOND_TOKEN,
        now=reclaim_at + timedelta(seconds=16),
    )
    assert failed.state is BulkExportJobState.FAILED
    assert failed.lease_token is None
    assert failed.lease_expires_at is None
    assert failed.heartbeat_at is None

    with postgres.admin_engine.connect() as connection:
        row = connection.execute(
            sa.text(
                "SELECT state, attempt_count, lease_token FROM exporting.bulk_export_job "
                "WHERE id=:job"
            ),
            {"job": JOB},
        ).mappings().one()
    assert row == {"state": "failed", "attempt_count": 3, "lease_token": None}
