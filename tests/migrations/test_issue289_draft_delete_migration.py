from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).parents[2]
MIGRATION = ROOT / "backend/migrations/versions/20261002_101_issue289_draft_delete.py"


def test_issue289_migration_adds_only_capability_guarded_draft_delete() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20261002_101_issue289_delete"' in source
    assert 'down_revision: str | None = "20261001_100_issue246_source_v2"' in source
    assert "delete_unpublished_r1_draft" in source
    assert "draft_delete_authorization" in source
    assert 'on_delete="NO ACTION"' in source
    assert "row_revision_no <> 1" in source
    assert "catalog.publication_marker" in source
    assert "EXCEPTION WHEN foreign_key_violation" in source
    assert "session_replication_role" not in source
    assert "DISABLE TRIGGER" not in source


def test_issue289_draft_delete_is_present_in_head_sql() -> None:
    output = StringIO()
    configuration = Config(str(ROOT / "alembic.ini"), output_buffer=output)

    command.upgrade(configuration, "head", sql=True)

    sql = output.getvalue()
    assert "CREATE FUNCTION catalog.delete_unpublished_r1_draft" in sql
    assert "CREATE POLICY catalog_schema_table_draft_delete" in sql
    assert "catalog_publication_marker_draft_delete_guard" in sql
