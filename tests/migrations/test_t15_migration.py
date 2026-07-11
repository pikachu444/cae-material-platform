from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t15_migration_renders_explicit_job_attempt_lease_runner_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()

    required = {
        "CREATE SCHEMA jobs",
        "CREATE TABLE jobs.runner",
        "CREATE TABLE jobs.runner_job_type",
        "CREATE TABLE jobs.job",
        "CREATE TABLE jobs.job_attempt",
        "CONSTRAINT fk_job_current_attempt",
        "CONSTRAINT ck_job_attempt_spec_identity",
        "CREATE INDEX ix_job_queue_claim",
        "CREATE INDEX ix_job_attempt_expired_lease",
        "CREATE FUNCTION jobs.guard_job_mutation()",
        "CREATE FUNCTION jobs.guard_job_attempt_mutation()",
        "CREATE TRIGGER job_attempt_mutation_guard",
        "ALTER TABLE jobs.job FORCE ROW LEVEL SECURITY",
        "CREATE POLICY job_authorized_insert",
        "CREATE POLICY job_attempt_authorized_update",
    }
    assert all(fragment in sql for fragment in required)


def test_t15_uses_jsonb_only_for_the_named_versioned_job_spec_contract() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260711_004_T15_job_engine.py"
    ).read_text(encoding="utf-8")

    assert migration.count("postgresql.JSONB") == 1
    assert 'sa.Column("job_spec", postgresql.JSONB' in migration
    assert '"attribute"' not in migration
    assert '"entity_type"' not in migration
    assert '"material"' not in migration
    assert '"test_run"' not in migration
    assert '"solver_card"' not in migration
