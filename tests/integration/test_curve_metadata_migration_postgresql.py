from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")
PREVIOUS_REVISION = "20260926_095_issue205_units"
CURRENT_REVISION = "20260927_096_issue206_curve"
pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.container_service,
    pytest.mark.skipif(
        not POSTGRES_DSN,
        reason="set CMP_TEST_POSTGRES_DSN to an isolated PostgreSQL admin URL",
    ),
]


def _url(value: str) -> URL:
    parsed = make_url(value)
    if parsed.drivername in {"postgres", "postgresql"}:
        return parsed.set(drivername="postgresql+psycopg")
    if parsed.drivername != "postgresql+psycopg":
        raise ValueError("CMP_TEST_POSTGRES_DSN must use PostgreSQL with psycopg")
    return parsed


def _config(database_url: URL) -> Config:
    result = Config(str(ROOT / "alembic.ini"))
    result.set_main_option(
        "sqlalchemy.url",
        database_url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    return result


def _constraint(connection: sa.Connection, name: str) -> str:
    value = connection.scalar(
        sa.text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :name"
        ),
        {"name": name},
    )
    assert isinstance(value, str)
    return value


def test_issue206_real_upgrade_downgrade_and_reupgrade() -> None:
    assert POSTGRES_DSN is not None
    cluster_url = _url(POSTGRES_DSN)
    database_name = f"cmp_issue206_migration_{uuid4().hex}"
    cluster = sa.create_engine(cluster_url, isolation_level="AUTOCOMMIT")
    with cluster.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
    database_url = cluster_url.set(database=database_name)
    database = sa.create_engine(database_url, pool_pre_ping=True)
    try:
        command.upgrade(_config(database_url), PREVIOUS_REVISION)
        with database.connect() as connection:
            legacy = _constraint(
                connection, "ck_processing_recipe_revision_input_schema"
            )
            assert "1.0.0" in legacy
            assert "1.1.0" not in legacy

        command.upgrade(_config(database_url), CURRENT_REVISION)
        with database.connect() as connection:
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == (
                CURRENT_REVISION
            )
            current = _constraint(
                connection, "ck_processing_recipe_revision_input_schema"
            )
            pair = _constraint(
                connection, "ck_statistics_statistical_plan_revision_curve_schema"
            )
            replicate = _constraint(
                connection, "ck_statistics_replicate_plan_rev_curve_schema"
            )
            assert "1.0.0" in current and "1.1.0" in current
            assert "1.0.0" in pair and "1.1.0" in pair
            assert "1.0.0" in replicate and "1.1.0" in replicate

        command.downgrade(_config(database_url), PREVIOUS_REVISION)
        with database.connect() as connection:
            restored = _constraint(
                connection, "ck_processing_recipe_revision_input_schema"
            )
            assert "1.0.0" in restored
            assert "1.1.0" not in restored
        command.upgrade(_config(database_url), CURRENT_REVISION)
    finally:
        database.dispose()
        with cluster.connect() as connection:
            connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
        cluster.dispose()
