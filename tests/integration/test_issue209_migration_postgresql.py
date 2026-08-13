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
PREVIOUS_REVISION = "20260929_098_issue210_dist"
CURRENT_REVISION = "20260930_099_issue209_dma_fld"

pytestmark = [
    pytest.mark.postgresql,
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
        sa.text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :name"),
        {"name": name},
    )
    assert isinstance(value, str)
    return value


def _column_nullable(
    connection: sa.Connection,
    schema: str,
    table: str,
    column: str,
) -> str | None:
    return connection.scalar(
        sa.text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_schema=:schema AND table_name=:table AND column_name=:column"
        ),
        {"schema": schema, "table": table, "column": column},
    )


def test_issue209_upgrade_downgrade_reupgrade_and_direct_review_guard() -> None:
    assert POSTGRES_DSN is not None
    cluster_url = _url(POSTGRES_DSN)
    database_name = f"cmp_issue209_migration_{uuid4().hex}"
    cluster = sa.create_engine(cluster_url, isolation_level="AUTOCOMMIT")
    with cluster.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
    database_url = cluster_url.set(database=database_name)
    database = sa.create_engine(database_url, pool_pre_ping=True)
    try:
        command.upgrade(_config(database_url), PREVIOUS_REVISION)
        with database.connect() as connection:
            legacy = _constraint(connection, "import_profile_revision_data_schema_check")
            assert "dma_frequency_temperature_sweep" not in legacy
            assert "forming_limit_diagram" not in legacy
            assert (
                _column_nullable(
                    connection,
                    "governance",
                    "review_publication_projection",
                    "record_id",
                )
                == "NO"
            )

        command.upgrade(_config(database_url), "head")
        with database.connect() as connection:
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == (
                CURRENT_REVISION
            )
            schemas = _constraint(connection, "import_profile_revision_data_schema_check")
            quantities = _constraint(connection, "import_profile_channel_source_quantity_check")
            assert "dma_frequency_temperature_sweep" in schemas
            assert "forming_limit_diagram" in schemas
            assert "storage_modulus" in quantities
            assert "minor_strain" in quantities
            assert (
                _column_nullable(connection, "datasets", "tabular_import_run", "idempotency_key")
                == "NO"
            )
            assert (
                _column_nullable(
                    connection,
                    "governance",
                    "review_publication_projection",
                    "record_id",
                )
                == "YES"
            )
            assert (
                _column_nullable(
                    connection,
                    "governance",
                    "review_publication_projection",
                    "material_id",
                )
                == "YES"
            )

        command.downgrade(_config(database_url), PREVIOUS_REVISION)
        with database.connect() as connection:
            restored = _constraint(connection, "import_profile_revision_data_schema_check")
            assert "dma_frequency_temperature_sweep" not in restored
            assert "forming_limit_diagram" not in restored
            assert (
                _column_nullable(connection, "datasets", "tabular_import_run", "idempotency_key")
                is None
            )
            assert (
                _column_nullable(
                    connection,
                    "governance",
                    "review_publication_projection",
                    "material_id",
                )
                is None
            )
            assert (
                _column_nullable(
                    connection,
                    "governance",
                    "review_publication_projection",
                    "record_id",
                )
                == "NO"
            )

        command.upgrade(_config(database_url), "head")
        with database.begin() as connection:
            connection.execute(
                sa.text(
                    "ALTER TABLE governance.review_publication_projection "
                    "NO FORCE ROW LEVEL SECURITY"
                )
            )
            connection.execute(
                sa.text(
                    "ALTER TABLE governance.review_publication_projection "
                    "DISABLE ROW LEVEL SECURITY"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO governance.review_publication_projection ("
                    "organization_id, project_id, classification, review_request_id, "
                    "subject_type, subject_id, subject_revision_id, material_id, "
                    "material_revision_id, published_at, published_by) VALUES ("
                    ":organization_id, :project_id, 'internal', :request_id, "
                    "'datasets.test_data_document', :subject_id, :subject_revision_id, "
                    ":material_id, :material_revision_id, now(), :published_by)"
                ),
                {
                    "organization_id": uuid4(),
                    "project_id": uuid4(),
                    "request_id": uuid4(),
                    "subject_id": uuid4(),
                    "subject_revision_id": uuid4(),
                    "material_id": uuid4(),
                    "material_revision_id": uuid4(),
                    "published_by": uuid4(),
                },
            )
            connection.execute(
                sa.text(
                    "ALTER TABLE governance.review_publication_projection ENABLE ROW LEVEL SECURITY"
                )
            )
            connection.execute(
                sa.text(
                    "ALTER TABLE governance.review_publication_projection FORCE ROW LEVEL SECURITY"
                )
            )

        with pytest.raises(
            sa.exc.DBAPIError,
            match="direct governed Material review projections exist",
        ):
            command.downgrade(_config(database_url), PREVIOUS_REVISION)
        with database.connect() as connection:
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == (
                CURRENT_REVISION
            )
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
