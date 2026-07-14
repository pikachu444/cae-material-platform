from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t31_migration_renders_append_only_lifecycle_usage_and_rls() -> None:
    output = StringIO()
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(configuration, "head", sql=True)
    sql = output.getvalue()
    required = {
        "CREATE TABLE governance.release_lifecycle_projection",
        "CREATE TABLE governance.release_lifecycle_event",
        "CREATE TABLE governance.release_usage",
        "CREATE INDEX ix_release_lifecycle_projection_state",
        "CREATE INDEX ix_release_lifecycle_event_release_history",
        "CREATE INDEX ix_release_lifecycle_event_successor_lookup",
        "CREATE INDEX ix_release_usage_release_history",
        "release_lifecycle_event_immutable",
        "release_usage_immutable",
        "release_lifecycle_projection_transition_guard",
        "fk_release_lifecycle_projection_event",
        "ALTER TABLE governance.release_usage FORCE ROW LEVEL SECURITY",
        "CREATE POLICY release_lifecycle_projection_authorized_update",
        "kind = 'supersede'",
        "to_state = 'withdrawn'",
        "lifecycle_state = 'released'",
    }
    assert all(fragment in sql for fragment in required)


def test_t31_migration_uses_typed_relations_without_generic_eav_payloads() -> None:
    migration = (
        PROJECT_ROOT / "backend/migrations/versions/20260725_027_T31_release_lifecycle.py"
    ).read_text(encoding="utf-8")
    assert "postgresql.JSONB" not in migration
    assert 'sa.Column("key"' not in migration
    assert 'sa.Column("value"' not in migration
    assert 'sa.Column("content"' not in migration
    assert "reject_immutable_row_mutation" in migration
    assert "organization_id" in migration and "project_id" in migration
