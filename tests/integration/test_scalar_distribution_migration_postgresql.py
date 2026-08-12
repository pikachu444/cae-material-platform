from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import DBAPIError

ROOT = Path(__file__).resolve().parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")
PREVIOUS_REVISION = "20260928_097_issue207_bundle"
CURRENT_REVISION = "20260929_098_issue210_dist"
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


def _trigger_function(connection: sa.Connection, trigger_name: str) -> str:
    value = connection.scalar(
        sa.text(
            "SELECT p.proname FROM pg_trigger t "
            "JOIN pg_proc p ON p.oid = t.tgfoid "
            "WHERE t.tgname = :trigger_name AND NOT t.tgisinternal"
        ),
        {"trigger_name": trigger_name},
    )
    assert isinstance(value, str)
    return value


def _prove_result_revision_is_immutable(connection: sa.Connection) -> None:
    result_id = uuid4()
    revision_id = uuid4()
    actor_id = uuid4()
    request_id = uuid4()
    observations = [
        {
            "ordinal": index,
            "dataset_id": str(uuid4()),
            "dataset_revision_id": str(uuid4()),
            "test_run_id": str(uuid4()),
            "test_run_revision_id": str(uuid4()),
            "value_pa": 500_000_000.0 + index,
            "quality": "observed",
            "outlier_assessment": "not_assessed",
        }
        for index in range(8)
    ]
    candidates = [
        {
            "family": family,
            "status": "not_eligible",
            "candidate_sha256": str(index + 1) * 64,
        }
        for index, family in enumerate(("normal", "lognormal", "weibull"))
    ]
    connection.execute(
        sa.text(
            "ALTER TABLE statistics.scalar_distribution_result_revision "
            "DISABLE TRIGGER statistics_scalar_distribution_result_guard"
        )
    )
    connection.execute(
        sa.text(
            "INSERT INTO statistics.scalar_distribution_result ("
            "id, organization_id, project_id, classification, current_revision_id, "
            "created_at, created_by, updated_at, statistical_run_id, result_kind"
            ") VALUES ("
            ":id, :organization_id, :project_id, 'internal', :revision_id, now(), "
            ":actor_id, now(), :run_id, 'scalar_distribution_comparison'"
            ")"
        ),
        {
            "id": result_id,
            "organization_id": uuid4(),
            "project_id": uuid4(),
            "revision_id": revision_id,
            "actor_id": actor_id,
            "run_id": uuid4(),
        },
    )
    identity = (
        connection.execute(
            sa.text(
                "SELECT organization_id, project_id, statistical_run_id "
                "FROM statistics.scalar_distribution_result WHERE id = :id"
            ),
            {"id": result_id},
        )
        .mappings()
        .one()
    )
    values = {
        "id": revision_id,
        "aggregate_id": result_id,
        "organization_id": identity["organization_id"],
        "project_id": identity["project_id"],
        "actor_id": actor_id,
        "request_id": request_id,
        "run_id": identity["statistical_run_id"],
        "statistical_result_id": uuid4(),
        "statistical_result_revision_id": uuid4(),
        "plan_id": uuid4(),
        "plan_revision_id": uuid4(),
        "selection_id": uuid4(),
        "selection_revision_id": uuid4(),
        "observations": json.dumps(observations),
        "candidates": json.dumps(candidates),
        "recommended": json.dumps([]),
        "artifact_id": uuid4(),
    }
    connection.execute(
        sa.text(
            "INSERT INTO statistics.scalar_distribution_result_revision ("
            "id, aggregate_id, organization_id, project_id, classification, revision_no, "
            "based_on_revision_id, schema_id, schema_version, content_hash, created_at, "
            "created_by, change_reason, request_id, trace_id, result_kind, statistical_run_id, "
            "statistical_result_id, statistical_result_revision_id, plan_id, plan_revision_id, "
            "selection_id, selection_revision_id, scalar_feature, sample_count, "
            "minimum_sample_count, small_sample_warning_below, seed, bootstrap_samples, "
            "observations, candidates, recommended_families, recommendation_method, "
            "algorithm_version, python_version, numpy_version, scipy_version, rng, "
            "source_sha256, lock_sha256, environment_sha256, artifact_id, artifact_sha256"
            ") VALUES ("
            ":id, :aggregate_id, :organization_id, :project_id, 'internal', 1, NULL, "
            "'urn:cmp:statistics:scalar-distribution-result:1.0.0', '1.0.0', "
            "repeat('a', 64), now(), :actor_id, 'immutable persistence test', :request_id, "
            "'test-trace', 'scalar_distribution_comparison', :run_id, :statistical_result_id, "
            ":statistical_result_revision_id, :plan_id, :plan_revision_id, :selection_id, "
            ":selection_revision_id, 'peak_engineering_stress_pa', 8, 8, 20, 210, 999, "
            "CAST(:observations AS jsonb), CAST(:candidates AS jsonb), "
            "CAST(:recommended AS jsonb), "
            "'aicc_delta_le_2_at_least_two_successful_candidates_v1', "
            "'scalar_distribution_fitting_v1', '3.13.7', '2.3.4', '1.16.3', "
            "'numpy.random.PCG64', repeat('b', 64), repeat('c', 64), repeat('d', 64), "
            ":artifact_id, repeat('e', 64)"
            ")"
        ),
        values,
    )
    with pytest.raises(DBAPIError, match="immutable"):
        connection.execute(
            sa.text(
                "UPDATE statistics.scalar_distribution_result_revision "
                "SET change_reason = 'mutated' WHERE id = :id"
            ),
            {"id": revision_id},
        )


def test_issue210_upgrade_downgrade_reupgrade_and_immutable_revision() -> None:
    assert POSTGRES_DSN is not None
    cluster_url = _url(POSTGRES_DSN)
    database_name = f"cmp_issue210_migration_{uuid4().hex}"
    cluster = sa.create_engine(cluster_url, isolation_level="AUTOCOMMIT")
    with cluster.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
    database_url = cluster_url.set(database=database_name)
    database = sa.create_engine(database_url, pool_pre_ping=True)
    try:
        command.upgrade(_config(database_url), PREVIOUS_REVISION)
        command.upgrade(_config(database_url), "head")
        with database.connect() as connection:
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == (
                CURRENT_REVISION
            )
            assert (
                _trigger_function(
                    connection,
                    "statistics_scalar_distribution_result_revision_immutable",
                )
                == "reject_immutable_row_mutation"
            )
            default = connection.scalar(
                sa.text(
                    "SELECT column_default FROM information_schema.columns "
                    "WHERE table_schema = 'statistics' "
                    "AND table_name = 'replicate_statistical_plan_revision' "
                    "AND column_name = 'scalar_distribution_enabled'"
                )
            )
            assert default is None
        command.downgrade(_config(database_url), PREVIOUS_REVISION)
        with database.connect() as connection:
            assert (
                connection.scalar(
                    sa.text("SELECT to_regclass('statistics.scalar_distribution_result') IS NULL")
                )
                is True
            )
            definition = connection.scalar(
                sa.text(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conname = 'ck_statistics_replicate_run_terminal'"
                )
            )
            assert isinstance(definition, str)
            assert "scalar_distribution" not in definition
        command.upgrade(_config(database_url), "head")
        with database.connect() as connection:
            transaction = connection.begin()
            try:
                _prove_result_revision_is_immutable(connection)
            finally:
                transaction.rollback()
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
