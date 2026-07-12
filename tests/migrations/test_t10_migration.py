from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t10_migration_renders_content_key_manifest_integrity_guards_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()

    required = {
        "CREATE FUNCTION artifact.content_object_key(",
        "CREATE TABLE artifact.artifact_pending",
        "CREATE TABLE artifact.artifact",
        "CREATE TABLE artifact.integrity_observation",
        "CREATE TABLE artifact.integrity_projection",
        "CREATE TABLE artifact.reconciliation_issue",
        "CONSTRAINT uq_artifact_pending_idempotency",
        "CONSTRAINT ck_artifact_manifest_content_key",
        "CREATE FUNCTION artifact.guard_pending_mutation()",
        "CREATE FUNCTION artifact.guard_artifact_insert()",
        "CREATE FUNCTION artifact.guard_integrity_observation_insert()",
        "CREATE FUNCTION artifact.guard_integrity_projection_mutation()",
        "CREATE TRIGGER artifact_manifest_immutable",
        "ALTER TABLE artifact.artifact FORCE ROW LEVEL SECURITY",
        "ALTER TABLE artifact.integrity_observation FORCE ROW LEVEL SECURITY",
        "CREATE POLICY artifact_pending_authorized_update",
        "'artifact.read'",
        "'artifact.write'",
    }
    assert all(fragment in sql for fragment in required)


def test_t10_has_no_jsonb_eav_or_business_schema() -> None:
    migration = (
        PROJECT_ROOT
        / "backend/migrations/versions/20260712_007_T10_content_artifacts.py"
    ).read_text(encoding="utf-8")

    assert "postgresql.JSONB" not in migration
    assert "sa.JSON" not in migration
    assert '"key"' not in migration
    assert '"value"' not in migration
    assert '"material"' not in migration
    assert '"test_run"' not in migration
    assert '"dataset"' not in migration
    assert '"solver_card"' not in migration
