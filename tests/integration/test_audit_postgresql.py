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
from cmp.modules.audit.adapters.persistence.repository import (
    SqlAlchemyAuditRepository,
    SqlAlchemyRevisionAuditHook,
    event_table,
)
from cmp.modules.audit.application.service import AuditEventQuery, AuditService
from cmp.modules.audit.domain.model import (
    AuditIntegrityIssueCode,
    AuditIntegrityState,
)
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
from cmp.shared.domain.revisions import RevisionCreated, RevisionRecord, TenantScope
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

NOW = datetime(2026, 7, 13, 14, 0, tzinfo=UTC)
ORG = UUID("a8000000-0000-4000-8000-000000000001")
PROJECT_A = UUID("a8000000-0000-4000-8000-000000000002")
PROJECT_B = UUID("a8000000-0000-4000-8000-000000000003")
ACTOR = UUID("a8000000-0000-4000-8000-000000000004")
TRACE = "00-000000000000000000000000000000a8-00000000000000a8-01"


@dataclass(frozen=True, slots=True)
class PostgresHarness:
    database_url: URL
    admin_engine: Engine
    sessions: sessionmaker[Session]
    rls: SqlAlchemyRlsContext
    repository: SqlAlchemyAuditRepository
    service: AuditService


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


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresHarness]:
    assert POSTGRES_DSN is not None
    admin_url = _psycopg_url(POSTGRES_DSN)
    database_name = f"cmp_t05_{uuid4().hex}"
    app_role = f"cmp_t05_app_{uuid4().hex}"
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
            connection.execute(
                sa.text(
                    "INSERT INTO identity.principal "
                    "(id, principal_type, display_name, active, created_at, updated_at) "
                    "VALUES (:id, 'user', 'T05 Auditor', true, :now, :now)"
                ),
                {"id": ACTOR, "now": NOW - timedelta(days=1)},
            )
            connection.exec_driver_sql(
                "GRANT USAGE ON SCHEMA identity, revisioning, access_control, "
                f'audit TO "{app_role}"'
            )
            connection.exec_driver_sql(
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA audit '
                f'TO "{app_role}"'
            )
            connection.exec_driver_sql(
                "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA "
                f'access_control, revisioning, audit TO "{app_role}"'
            )
        app_engine = sa.create_engine(
            database_url.set(username=app_role, password=None), pool_pre_ping=True
        )
        sessions = sessionmaker(app_engine, class_=Session, expire_on_commit=False)
        rls = SqlAlchemyRlsContext()
        with sessions() as session, session.begin():
            rls.assert_application_role(session)
        repository = SqlAlchemyAuditRepository(session_factory=sessions, rls_context=rls)
        yield PostgresHarness(
            database_url=database_url,
            admin_engine=admin_engine,
            sessions=sessions,
            rls=rls,
            repository=repository,
            service=AuditService(repository=repository),
        )
    finally:
        if app_engine is not None:
            app_engine.dispose()
        admin_engine.dispose()
        with cluster_engine.connect() as connection:
            connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity WHERE datname=:name"
                ),
                {"name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
            connection.exec_driver_sql(f'DROP ROLE "{app_role}"')
        cluster_engine.dispose()


def _context(project_id: UUID = PROJECT_A) -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "T05 Auditor", True),
        organization_id=ORG,
        project_id=project_id,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(
    context: SecurityContext,
    permission: Permission,
    *,
    seal: bool = False,
) -> AuthorizationDecision:
    permissions = set(database_permissions_for(permission))
    if seal:
        permissions.add("audit.seal")
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=context.organization_id,
        project_id=context.project_id,
        permission=permission,
        roles=((Role.AUDITOR,) if permission is Permission.AUDIT_READ else (Role.DATA_STEWARD,)),
        database_permissions=tuple(sorted(permissions)),
        max_classification=DataClassification.RESTRICTED,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


def _revision(context: SecurityContext, number: int) -> RevisionCreated:
    revision_id = UUID(f"a9000000-0000-4000-8000-{number:012d}")
    based_on = (
        None
        if number == 1
        else UUID(f"a9000000-0000-4000-8000-{number - 1:012d}")
    )
    return RevisionCreated(
        RevisionRecord(
            revision_id=revision_id,
            aggregate_type="synthetic.fixture",
            aggregate_id=UUID("aa000000-0000-4000-8000-000000000001"),
            scope=TenantScope(ORG, context.project_id, "internal"),
            revision_no=number,
            based_on_revision_id=based_on,
            schema_id="urn:cmp:test:fixture:1",
            schema_version="1.0.0",
            content_hash=f"{number:064x}",
            created_at=NOW + timedelta(seconds=number),
            created_by=ACTOR,
            change_reason=f"append revision {number}",
            request_id=context.request_id,
            trace_id=context.trace_id,
        ),
        "draft",
    )


def test_revision_hook_chain_seal_query_export_rls_and_atomic_rollback(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    write = _decision(context, Permission.DATASET_WRITE)
    hook = SqlAlchemyRevisionAuditHook()
    for number in range(1, 4):
        with postgres.sessions() as session, session.begin():
            postgres.rls.bind_authorization(session, context, write)
            hook(session, _revision(context, number))

    with pytest.raises(RuntimeError, match="rollback"):
        with postgres.sessions() as session, session.begin():
            postgres.rls.bind_authorization(session, context, write)
            hook(session, _revision(context, 4))
            raise RuntimeError("synthetic command rollback")

    read = _decision(context, Permission.AUDIT_READ)
    page = postgres.service.query_events(context, read, AuditEventQuery(limit=2))
    assert [event.sequence_no for event in page.events] == [1, 2]
    assert page.next_after_sequence == 2
    assert all(event.ip_or_client == "policy-redacted" for event in page.events)
    assert postgres.service.integrity(context, read).unsealed_event_count == 3

    root = postgres.service.seal_next(
        context,
        _decision(context, Permission.AUDIT_READ, seal=True),
        maximum_events=100,
    )
    assert root is not None and (root.first_sequence_no, root.last_sequence_no) == (1, 3)
    report = postgres.service.integrity(context, read)
    assert report.state is AuditIntegrityState.VALID
    assert report.sealed_through_sequence_no == 3

    exported = postgres.service.export(context, read, from_sequence=2, to_sequence=3)
    assert exported.anchor_previous_hash == page.events[0].event_hash
    assert [event.sequence_no for event in exported.events] == [2, 3]
    assert exported.segment_roots == (root,)

    other_context = _context(PROJECT_B)
    hidden = postgres.service.query_events(
        other_context,
        _decision(other_context, Permission.AUDIT_READ),
        AuditEventQuery(),
    )
    assert hidden.events == ()


def test_database_blocks_mutation_and_integrity_detects_admin_tampering(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    read = _decision(context, Permission.AUDIT_READ)
    event_id = postgres.service.query_events(
        context, read, AuditEventQuery(limit=1)
    ).events[0].id

    with pytest.raises(DBAPIError):
        with postgres.sessions() as session, session.begin():
            postgres.rls.bind_authorization(session, context, read)
            session.execute(
                sa.update(event_table).where(event_table.c.id == event_id).values(reason="mutate")
            )
    with pytest.raises(DBAPIError):
        with postgres.sessions() as session, session.begin():
            postgres.rls.bind_authorization(session, context, read)
            session.execute(sa.delete(event_table).where(event_table.c.id == event_id))

    with postgres.admin_engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE audit.event DISABLE TRIGGER audit_event_immutable")
        connection.execute(
            sa.text("UPDATE audit.event SET reason='admin mutation' WHERE sequence_no=2")
        )
        connection.exec_driver_sql("ALTER TABLE audit.event ENABLE TRIGGER audit_event_immutable")
    mutation = postgres.service.integrity(context, read)
    assert AuditIntegrityIssueCode.EVENT_HASH_MISMATCH in {
        issue.code for issue in mutation.issues
    }

    with postgres.admin_engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE audit.event DISABLE TRIGGER audit_event_immutable")
        connection.execute(
            sa.text(
                "UPDATE audit.event SET sequence_no=sequence_no+1000 "
                "WHERE sequence_no IN (1,2)"
            )
        )
        connection.execute(sa.text("UPDATE audit.event SET sequence_no=2 WHERE sequence_no=1001"))
        connection.execute(sa.text("UPDATE audit.event SET sequence_no=1 WHERE sequence_no=1002"))
        connection.exec_driver_sql("ALTER TABLE audit.event ENABLE TRIGGER audit_event_immutable")
    reordered = postgres.service.integrity(context, read)
    assert {
        AuditIntegrityIssueCode.EVENT_HASH_MISMATCH,
        AuditIntegrityIssueCode.EVENT_PREVIOUS_HASH_MISMATCH,
    }.intersection(issue.code for issue in reordered.issues)

    with postgres.admin_engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE audit.event DISABLE TRIGGER audit_event_immutable")
        connection.execute(sa.text("DELETE FROM audit.event WHERE sequence_no=2"))
        connection.exec_driver_sql("ALTER TABLE audit.event ENABLE TRIGGER audit_event_immutable")
    deleted = postgres.service.integrity(context, read)
    assert AuditIntegrityIssueCode.SEGMENT_EVENT_MISSING in {
        issue.code for issue in deleted.issues
    }


def test_t05_real_upgrade_downgrade_and_reupgrade(postgres: PostgresHarness) -> None:
    configuration = _alembic_config(postgres.database_url)

    command.downgrade(configuration, "20260713_011_t16")
    with postgres.admin_engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT to_regclass('audit.event')")) is None
    command.upgrade(configuration, "head")
    with postgres.admin_engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT to_regclass('audit.event')")) == "audit.event"
