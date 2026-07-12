from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t16_migration_renders_explicit_outbox_delivery_and_inbox() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()

    required = {
        "CREATE TABLE events.outbox_event",
        "CREATE TABLE events.outbox_delivery",
        "CREATE TABLE events.consumer_inbox",
        "uq_events_outbox_aggregate_sequence",
        "uq_events_outbox_deduplication",
        "ix_events_outbox_delivery_claim",
        "ENABLE ROW LEVEL SECURITY",
        "FORCE ROW LEVEL SECURITY",
        "'events.publish'",
        "'events.dispatch'",
        "'events.consume'",
    }
    assert all(fragment in sql for fragment in required)


def test_t16_jsonb_is_limited_to_schema_identified_cloudevent_data() -> None:
    migration = (
        PROJECT_ROOT / "backend/migrations/versions/20260713_010_T16_transactional_outbox.py"
    ).read_text(encoding="utf-8")

    assert migration.count("postgresql.JSONB") == 1
    assert 'sa.Column("data", postgresql.JSONB' in migration
    assert 'sa.Column("data_schema"' in migration
    assert 'sa.Column("data_sha256"' in migration
    assert '"attribute"' not in migration
    assert '"value"' not in migration


def test_t16_phase2_renders_durable_schedule_run_and_staging_only_cleanup() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()

    assert "CREATE TABLE artifact.reconciliation_schedule" in sql
    assert "CREATE TABLE artifact.reconciliation_run" in sql
    assert "CREATE TABLE artifact.staging_cleanup" in sql
    assert "ix_reconciliation_schedule_due" in sql
    assert "artifact_reconciliation_run_guard" in sql
    migration = (
        PROJECT_ROOT / "backend/migrations/versions/20260713_011_T16_reconciliation_schedule.py"
    ).read_text(encoding="utf-8")
    assert "storage_key" not in migration
    assert "DELETE FROM" not in migration
    assert "postgresql.JSONB" not in migration
