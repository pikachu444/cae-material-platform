from __future__ import annotations

import json
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.review_release.adapters.persistence.lifecycle import (
    SqlInitialLifecycleHook,
)
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
)
from cmp.shared.domain.revisions import RevisionConflict, RevisionRecord, TenantScope
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


@dataclass(frozen=True, slots=True)
class NoteContent:
    title: str
    body: str
    pinned: bool = False


@dataclass(frozen=True, slots=True)
class PostgresHarness:
    engine: Engine
    database_url: URL
    identity_table: sa.Table
    revision_table: sa.Table
    rls_role: str | None


def _psycopg_url(value: str) -> URL:
    url = make_url(value)
    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise ValueError("CMP_TEST_POSTGRES_DSN must use PostgreSQL with psycopg")
    return url


def _alembic_config(database_url: URL) -> Config:
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"))
    rendered = database_url.render_as_string(hide_password=False).replace("%", "%%")
    configuration.set_main_option("sqlalchemy.url", rendered)
    return configuration


def _set_scope(connection: sa.Connection, scope: TenantScope) -> None:
    connection.execute(
        sa.select(
            sa.func.set_config("cmp.organization_id", str(scope.organization_id), True),
            sa.func.set_config("cmp.project_id", str(scope.project_id), True),
            sa.func.set_config(
                "cmp.permissions",
                json.dumps(
                    [
                        "governance.read",
                        "governance.write",
                        "revision.read",
                        "revision.write",
                    ]
                ),
                True,
            ),
            sa.func.set_config("cmp.max_classification_rank", "2", True),
            sa.func.set_config("cmp.allow_export_controlled", "true", True),
        )
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresHarness]:
    assert POSTGRES_DSN is not None
    admin_url = _psycopg_url(POSTGRES_DSN)
    database_name = f"cmp_t06_{uuid4().hex}"
    admin_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')

    database_url = admin_url.set(database=database_name)
    engine = sa.create_engine(database_url, pool_pre_ping=True)
    role_name: str | None = None
    try:
        command.upgrade(_alembic_config(database_url), "head")
        fixture_sql = (
            PROJECT_ROOT / "tests/migrations/fixtures/T06_typed_revision_fixture.sql"
        ).read_text(encoding="utf-8")
        with engine.begin() as connection:
            connection.exec_driver_sql(fixture_sql)
            is_superuser = bool(
                connection.execute(
                    sa.text(
                        "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
                    )
                ).scalar_one()
            )
            if is_superuser:
                role_name = f"cmp_t06_rls_{uuid4().hex}"
                connection.exec_driver_sql(
                    f'CREATE ROLE "{role_name}" NOLOGIN NOSUPERUSER NOBYPASSRLS'
                )
                connection.exec_driver_sql(
                    f'GRANT USAGE ON SCHEMA kernel_fixture, governance, revisioning, '
                    f'access_control '
                    f'TO "{role_name}"'
                )
                connection.exec_driver_sql(
                    f'GRANT SELECT ON ALL TABLES IN SCHEMA kernel_fixture, governance '
                    f'TO "{role_name}"'
                )

        metadata = sa.MetaData()
        metadata.reflect(engine, schema="kernel_fixture")
        yield PostgresHarness(
            engine=engine,
            database_url=database_url,
            identity_table=metadata.tables["kernel_fixture.revisioned_note"],
            revision_table=metadata.tables[
                "kernel_fixture.revisioned_note_revision"
            ],
            rls_role=role_name,
        )
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS kernel_fixture CASCADE")
        command.downgrade(_alembic_config(database_url), "base")
        engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
            if role_name is not None:
                connection.exec_driver_sql(f'DROP ROLE "{role_name}"')
        admin_engine.dispose()


def _service(postgres: PostgresHarness) -> RevisionService[NoteContent]:
    sessions = sessionmaker(postgres.engine, class_=Session, expire_on_commit=False)
    tables: TypedRevisionTables[NoteContent] = TypedRevisionTables(
        aggregate_type="test.note",
        identity_table=postgres.identity_table,
        revision_table=postgres.revision_table,
        canonical_content=lambda content: {
            "title": content.title,
            "body": content.body,
            "pinned": content.pinned,
        },
        content_values=lambda content: {
            "title": content.title,
            "body": content.body,
            "pinned": content.pinned,
        },
    )
    store = SqlAlchemyRevisionStore(
        session_factory=sessions,
        tables=tables,
        hooks=(SqlInitialLifecycleHook(),),
    )
    return RevisionService(
        aggregate_type="test.note",
        store=store,
    )


def _scope(project_id: UUID | None = None) -> TenantScope:
    return TenantScope(
        UUID("10000000-0000-4000-8000-000000000001"),
        project_id or UUID("10000000-0000-4000-8000-000000000002"),
        "internal",
    )


def _create_command(
    aggregate_id: UUID, scope: TenantScope, title: str = "initial"
) -> CreateRevisionedAggregate[NoteContent]:
    return CreateRevisionedAggregate(
        aggregate_id=aggregate_id,
        scope=scope,
        schema_id="urn:cmp:test:typed-note:v1",
        schema_version="1.0.0",
        content=NoteContent(title, "immutable original"),
        created_by=UUID("10000000-0000-4000-8000-000000000003"),
        change_reason="create typed test revision",
        request_id=uuid4(),
        trace_id="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    )


def _revise_command(
    aggregate_id: UUID,
    scope: TenantScope,
    expected: UUID,
    title: str,
) -> ReviseAggregate[NoteContent]:
    return ReviseAggregate(
        aggregate_id=aggregate_id,
        scope=scope,
        expected_current_revision_id=expected,
        based_on_revision_id=expected,
        schema_id="urn:cmp:test:typed-note:v1",
        schema_version="1.0.0",
        content=NoteContent(title, f"body for {title}", True),
        created_by=UUID("10000000-0000-4000-8000-000000000003"),
        change_reason="append typed test revision",
        request_id=uuid4(),
        trace_id="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    )


def test_migration_installs_constraints_indexes_triggers_and_rls(
    postgres: PostgresHarness,
) -> None:
    with postgres.engine.connect() as connection:
        constraints = set(
            connection.execute(
                sa.text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE connamespace = 'governance'::regnamespace"
                )
            ).scalars()
        )
        policies = set(
            connection.execute(
                sa.text(
                    "SELECT policyname FROM pg_policies "
                    "WHERE schemaname IN ('governance', 'kernel_fixture')"
                )
            ).scalars()
        )
        triggers = set(
            connection.execute(
                sa.text(
                    "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal "
                    "AND tgrelid IN ("
                    "'governance.lifecycle_event'::regclass, "
                    "'kernel_fixture.revisioned_note'::regclass, "
                    "'kernel_fixture.revisioned_note_revision'::regclass)"
                )
            ).scalars()
        )

    assert "fk_lifecycle_projection_last_event" in constraints
    assert "lifecycle_event_authorized_select" in policies
    assert "revisioned_note_revision_authorized_select" in policies
    assert "lifecycle_event_immutable" in triggers
    assert "revisioned_note_head_only" in triggers
    assert "revisioned_note_revision_immutable" in triggers


def test_create_and_revise_commit_typed_rows_and_lifecycle_atomically(
    postgres: PostgresHarness,
) -> None:
    aggregate_id = uuid4()
    scope = _scope()
    service = _service(postgres)

    first = service.create(_create_command(aggregate_id, scope))
    second = service.revise(
        _revise_command(aggregate_id, scope, first.revision_id, "second")
    )

    with postgres.engine.begin() as connection:
        _set_scope(connection, scope)
        rows = connection.execute(
            sa.select(
                postgres.revision_table.c.id,
                postgres.revision_table.c.revision_no,
                postgres.revision_table.c.title,
            )
            .where(postgres.revision_table.c.aggregate_id == aggregate_id)
            .order_by(postgres.revision_table.c.revision_no)
        ).all()
        lifecycle_count = connection.execute(
            sa.text(
                "SELECT count(*) FROM governance.lifecycle_event "
                "WHERE aggregate_id = :aggregate_id"
            ),
            {"aggregate_id": aggregate_id},
        ).scalar_one()

    row_values = [(row.id, row.revision_no, row.title) for row in rows]
    assert row_values == [
        (first.revision_id, 1, "initial"),
        (second.revision_id, 2, "second"),
    ]
    assert lifecycle_count == 2


def test_concurrent_compare_and_swap_allows_exactly_one_new_head(
    postgres: PostgresHarness,
) -> None:
    aggregate_id = uuid4()
    scope = _scope()
    service = _service(postgres)
    first = service.create(_create_command(aggregate_id, scope))
    barrier = Barrier(2)

    def attempt(title: str) -> RevisionRecord | Exception:
        barrier.wait(timeout=10)
        try:
            return service.revise(
                _revise_command(aggregate_id, scope, first.revision_id, title)
            )
        except Exception as error:  # returned for exact result classification below
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ("concurrent-a", "concurrent-b")))

    successes = [result for result in results if isinstance(result, RevisionRecord)]
    conflicts = [result for result in results if isinstance(result, RevisionConflict)]
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert successes[0].revision_no == 2
    assert conflicts[0].current == successes[0].ref


def test_database_rejects_original_and_released_revision_mutation(
    postgres: PostgresHarness,
) -> None:
    aggregate_id = uuid4()
    scope = _scope()
    service = _service(postgres)
    first = service.create(_create_command(aggregate_id, scope))
    released = service.revise(
        _revise_command(aggregate_id, scope, first.revision_id, "released")
    )
    release_event_id = uuid4()
    with postgres.engine.begin() as connection:
        _set_scope(connection, scope)
        connection.execute(
            sa.text(
                "INSERT INTO governance.lifecycle_event ("
                "id, organization_id, project_id, classification, aggregate_type, "
                "aggregate_id, revision_id, sequence_no, from_state, to_state, "
                "occurred_at, actor_id, reason, request_id, trace_id"
                ") VALUES ("
                ":id, :organization_id, :project_id, :classification, 'test.note', "
                ":aggregate_id, :revision_id, 2, 'draft', 'released', :occurred_at, "
                ":actor_id, 'synthetic release fixture', :request_id, 'test-trace'"
                ")"
            ),
            {
                "id": release_event_id,
                "organization_id": scope.organization_id,
                "project_id": scope.project_id,
                "classification": scope.classification,
                "aggregate_id": aggregate_id,
                "revision_id": released.revision_id,
                "occurred_at": datetime.now(UTC),
                "actor_id": uuid4(),
                "request_id": uuid4(),
            },
        )
        connection.execute(
            sa.text(
                "UPDATE governance.lifecycle_projection "
                "SET lifecycle_state = 'released', sequence_no = 2, "
                "last_event_id = :event_id, updated_at = :updated_at "
                "WHERE aggregate_id = :aggregate_id AND revision_id = :revision_id"
            ),
            {
                "event_id": release_event_id,
                "updated_at": datetime.now(UTC),
                "aggregate_id": aggregate_id,
                "revision_id": released.revision_id,
            },
        )

    with pytest.raises(DBAPIError) as update_error, postgres.engine.begin() as connection:
        _set_scope(connection, scope)
        connection.execute(
            sa.update(postgres.revision_table)
            .where(postgres.revision_table.c.id == first.revision_id)
            .values(title="mutated")
        )
    assert getattr(update_error.value.orig, "sqlstate", None) == "55000"

    with pytest.raises(DBAPIError) as released_error, postgres.engine.begin() as connection:
        _set_scope(connection, scope)
        connection.execute(
            sa.update(postgres.revision_table)
            .where(postgres.revision_table.c.id == released.revision_id)
            .values(title="overwritten-release")
        )
    assert getattr(released_error.value.orig, "sqlstate", None) == "55000"

    with pytest.raises(DBAPIError) as delete_error, postgres.engine.begin() as connection:
        _set_scope(connection, scope)
        connection.execute(
            sa.delete(postgres.revision_table).where(
                postgres.revision_table.c.id == first.revision_id
            )
        )
    assert getattr(delete_error.value.orig, "sqlstate", None) == "55000"

    with pytest.raises(DBAPIError) as event_error, postgres.engine.begin() as connection:
        _set_scope(connection, scope)
        connection.execute(
            sa.text(
                "UPDATE governance.lifecycle_event SET reason = 'overwritten' "
                "WHERE id = :event_id"
            ),
            {"event_id": release_event_id},
        )
    assert getattr(event_error.value.orig, "sqlstate", None) == "55000"


def test_rls_hides_rows_and_lifecycle_counts_from_other_projects(
    postgres: PostgresHarness,
) -> None:
    project_a = _scope(UUID("20000000-0000-4000-8000-000000000001"))
    project_b = _scope(UUID("20000000-0000-4000-8000-000000000002"))
    aggregate_a = uuid4()
    # The same opaque UUID in another project must not collide or disclose existence.
    aggregate_b = aggregate_a
    service = _service(postgres)
    service.create(_create_command(aggregate_a, project_a, "project-a"))
    service.create(_create_command(aggregate_b, project_b, "project-b"))

    with postgres.engine.begin() as connection:
        if postgres.rls_role is not None:
            connection.exec_driver_sql(f'SET LOCAL ROLE "{postgres.rls_role}"')
        _set_scope(connection, project_a)
        identity_count = connection.execute(
            sa.text(
                "SELECT count(*) FROM kernel_fixture.revisioned_note "
                "WHERE id IN (:aggregate_a, :aggregate_b)"
            ),
            {"aggregate_a": aggregate_a, "aggregate_b": aggregate_b},
        ).scalar_one()
        lifecycle_count = connection.execute(
            sa.text(
                "SELECT count(*) FROM governance.lifecycle_event "
                "WHERE aggregate_id IN (:aggregate_a, :aggregate_b)"
            ),
            {"aggregate_a": aggregate_a, "aggregate_b": aggregate_b},
        ).scalar_one()

    assert identity_count == 1
    assert lifecycle_count == 1
