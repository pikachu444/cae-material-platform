from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
MIGRATION = (
    PROJECT_ROOT / "backend/migrations/versions/20260826_060_T50_catalog_records.py"
)


def test_t50_adds_revision_pinned_folders_and_indexed_typed_record_search() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260826_060_t50"' in source
    assert 'down_revision: str | None = "20260825_059_t49"' in source
    assert '"folder_revision"' in source
    assert '"parent_folder_revision_id"' in source
    assert '"folder_revision_id"' in source
    assert "guard_folder_revision" in source
    assert "guard_record_folder_table" in source
    assert "ix_catalog_record_revision_name_search" in source
    assert "ix_catalog_record_discrete_search" in source
    assert "ix_catalog_record_text_value_search_value" in source
    assert "postgresql.JSONB" not in source
    assert "sa.JSON" not in source
