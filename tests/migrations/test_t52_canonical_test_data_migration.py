from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = PROJECT_ROOT / "backend/migrations/versions/20260828_062_T52_canonical_test_data.py"


def test_t52_migration_uses_explicit_revision_channel_and_condition_tables() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260828_062_test_json"' in source
    assert 'down_revision: str | None = "20260827_061_t51"' in source
    for table in (
        "test_data_document",
        "test_data_document_revision",
        "test_data_condition",
        "test_data_channel",
    ):
        assert f"datasets.{table}" in source
    assert "canonical_artifact_id" in source
    assert "normalized_artifact_id" in source
    assert "original_unit_string" in source
    assert "quantity_semantics" in source
    assert "postgresql.JSONB" not in source
    assert "reject_immutable_row_mutation" in source
    assert "FORCE ROW LEVEL SECURITY" in source
