from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.identity_access.adapters.persistence.principals import (
    SqlAlchemyPrincipalRepository,
)
from cmp.modules.identity_access.domain.security import (
    AccessDenied,
    AuthenticationFailed,
    Principal,
    PrincipalType,
    VerifiedAccessToken,
)
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.skipif(
        not POSTGRES_DSN,
        reason="set CMP_TEST_POSTGRES_DSN to an isolated PostgreSQL admin URL",
    ),
]


@dataclass(frozen=True, slots=True)
class PostgresHarness:
    engine: Engine
    principal_table: sa.Table
    external_identity_table: sa.Table


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
    database_name = f"cmp_t03_{uuid4().hex}"
    admin_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
    database_url = admin_url.set(database=database_name)
    engine = sa.create_engine(database_url, pool_pre_ping=True)
    try:
        command.upgrade(_alembic_config(database_url), "head")
        metadata = sa.MetaData()
        metadata.reflect(engine, schema="identity")
        yield PostgresHarness(
            engine=engine,
            principal_table=metadata.tables["identity.principal"],
            external_identity_table=metadata.tables["identity.external_identity"],
        )
    finally:
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
        admin_engine.dispose()


def _repository(
    postgres: PostgresHarness, *, auto_provision: bool
) -> SqlAlchemyPrincipalRepository:
    sessions = sessionmaker(postgres.engine, class_=Session, expire_on_commit=False)
    return SqlAlchemyPrincipalRepository(
        session_factory=sessions,
        auto_provision=auto_provision,
    )


def _token(subject: str = "postgres-user") -> VerifiedAccessToken:
    issued_at = datetime.now(UTC)
    return VerifiedAccessToken(
        issuer="https://test-idp.invalid",
        subject=subject,
        audiences=("urn:cmp:test-api",),
        expires_at=issued_at + timedelta(minutes=5),
        issued_at=issued_at,
        token_id=str(uuid4()),
        client_id="cmp-test-web",
        principal_type=PrincipalType.USER,
        display_name="PostgreSQL User",
        organization_id=UUID("50000000-0000-4000-8000-000000000001"),
        project_id=UUID("50000000-0000-4000-8000-000000000002"),
        groups=("test-engineers",),
        scopes=("openid",),
    )


def test_auto_provision_is_idempotent_and_updates_only_projection_fields(
    postgres: PostgresHarness,
) -> None:
    repository = _repository(postgres, auto_provision=True)
    token = _token()
    first_seen = datetime.now(UTC)
    first = repository.resolve_or_provision(token, first_seen)
    renamed = replace(token, display_name="Renamed User")
    second_seen = first_seen + timedelta(seconds=1)
    second = repository.resolve_or_provision(renamed, second_seen)

    with postgres.engine.connect() as connection:
        principal_rows = connection.execute(
            sa.select(postgres.principal_table)
        ).mappings().all()
        external_rows = connection.execute(
            sa.select(postgres.external_identity_table)
        ).mappings().all()

    assert first.id == second.id
    assert first.id.version == 4
    assert second.display_name == "Renamed User"
    assert len(principal_rows) == len(external_rows) == 1
    assert principal_rows[0]["principal_type"] == "user"
    assert external_rows[0]["issuer"] == token.issuer
    assert external_rows[0]["subject"] == token.subject
    assert external_rows[0]["last_seen_at"] == second_seen


def test_unknown_principal_is_denied_when_jit_provisioning_is_disabled(
    postgres: PostgresHarness,
) -> None:
    with pytest.raises(AccessDenied, match="principal_not_provisioned"):
        _repository(postgres, auto_provision=False).resolve_or_provision(
            _token("not-provisioned"), datetime.now(UTC)
        )


def test_same_issuer_subject_cannot_switch_between_user_and_service(
    postgres: PostgresHarness,
) -> None:
    repository = _repository(postgres, auto_provision=True)
    user = _token("fixed-subject")
    repository.resolve_or_provision(user, datetime.now(UTC))
    confused = replace(user, principal_type=PrincipalType.SERVICE)

    with pytest.raises(AuthenticationFailed, match="principal_type_mismatch"):
        repository.resolve_or_provision(confused, datetime.now(UTC))


def test_concurrent_first_login_creates_one_principal_and_external_identity(
    postgres: PostgresHarness,
) -> None:
    repository = _repository(postgres, auto_provision=True)
    token = _token("concurrent-subject")
    barrier = Barrier(2)

    def resolve(_: int) -> Principal:
        barrier.wait(timeout=10)
        return repository.resolve_or_provision(token, datetime.now(UTC))

    with ThreadPoolExecutor(max_workers=2) as executor:
        principals = list(executor.map(resolve, (1, 2)))

    assert principals[0].id == principals[1].id
    with postgres.engine.connect() as connection:
        principal_count = connection.execute(
            sa.select(sa.func.count())
            .select_from(postgres.principal_table)
            .where(postgres.principal_table.c.id == principals[0].id)
        ).scalar_one()
        external_count = connection.execute(
            sa.select(sa.func.count())
            .select_from(postgres.external_identity_table)
            .where(postgres.external_identity_table.c.principal_id == principals[0].id)
        ).scalar_one()
    assert principal_count == external_count == 1


def test_database_guards_external_identity_and_principal_keys(
    postgres: PostgresHarness,
) -> None:
    principal = _repository(postgres, auto_provision=True).resolve_or_provision(
        _token("guarded-subject"), datetime.now(UTC)
    )

    with pytest.raises(DBAPIError) as external_error, postgres.engine.begin() as connection:
        connection.execute(
            sa.update(postgres.external_identity_table)
            .where(postgres.external_identity_table.c.principal_id == principal.id)
            .values(subject="overwritten-subject")
        )
    assert getattr(external_error.value.orig, "sqlstate", None) == "55000"

    with pytest.raises(DBAPIError) as principal_error, postgres.engine.begin() as connection:
        connection.execute(
            sa.update(postgres.principal_table)
            .where(postgres.principal_table.c.id == principal.id)
            .values(principal_type="service")
        )
    assert getattr(principal_error.value.orig, "sqlstate", None) == "55000"

    with postgres.engine.connect() as connection:
        last_seen_at = connection.execute(
            sa.select(postgres.external_identity_table.c.last_seen_at).where(
                postgres.external_identity_table.c.principal_id == principal.id
            )
        ).scalar_one()
    with pytest.raises(DBAPIError) as last_seen_error, postgres.engine.begin() as connection:
        connection.execute(
            sa.update(postgres.external_identity_table)
            .where(postgres.external_identity_table.c.principal_id == principal.id)
            .values(last_seen_at=last_seen_at - timedelta(seconds=1))
        )
    assert getattr(last_seen_error.value.orig, "sqlstate", None) == "55000"
