from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t09_migration_renders_explicit_upload_raw_event_guards_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()

    required = {
        "CREATE SCHEMA artifact",
        "CREATE TABLE artifact.raw_asset",
        "CREATE TABLE artifact.upload_session",
        "CREATE TABLE artifact.upload_part",
        "CREATE TABLE artifact.ingestion_event",
        "CONSTRAINT uq_artifact_raw_asset_content",
        "CONSTRAINT uq_artifact_upload_session_idempotency",
        "CREATE FUNCTION artifact.guard_upload_part_insert()",
        "CREATE FUNCTION artifact.guard_raw_asset_insert()",
        "CREATE FUNCTION artifact.guard_ingestion_event_insert()",
        "CREATE FUNCTION artifact.guard_upload_session_mutation()",
        "CREATE TRIGGER raw_asset_immutable",
        "ALTER TABLE artifact.raw_asset FORCE ROW LEVEL SECURITY",
        "ALTER TABLE artifact.upload_session FORCE ROW LEVEL SECURITY",
        "CREATE POLICY upload_session_authorized_update",
        "'artifact.read'",
        "'artifact.write'",
    }
    assert all(fragment in sql for fragment in required)


def test_t09_has_no_jsonb_eav_generic_artifact_or_business_tables() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260712_006_T09_streaming_upload.py"
    ).read_text(encoding="utf-8")

    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert 'op.create_table(\n        "artifact"' not in migration
    assert '"material"' not in migration
    assert '"dataset"' not in migration
    assert '"solver_card"' not in migration
