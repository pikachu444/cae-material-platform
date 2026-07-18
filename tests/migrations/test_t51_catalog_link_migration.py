from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
MIGRATION = PROJECT_ROOT / "backend/migrations/versions/20260827_061_T51_catalog_links.py"


def test_t51_adds_typed_exact_revision_links_cardinality_and_rls() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260827_061_t51"' in source
    assert 'down_revision: str | None = "20260826_060_t50"' in source
    assert '"link_type_revision"' in source
    assert '"record_link_revision"' in source
    assert '"source_record_revision_id"' in source
    assert '"target_record_revision_id"' in source
    assert "guard_record_link_revision" in source
    assert "source cardinality one exceeded" in source
    assert "target cardinality one exceeded" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "reject_immutable_row_mutation" in source
    assert "postgresql.JSONB" not in source
    assert "sa.JSON" not in source
