from pathlib import Path

MIGRATION = Path("backend/migrations/versions/20260916_081_T70_metal_recipe_batch_origin.py")


def test_t70_migration_pins_exact_metal_recipe_batch_origin() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260916_081_t70_metal_origin"' in sql
    assert 'down_revision: str | None = "20260915_080_t69_origin"' in sql
    assert "processing_recipe_revision_id" in sql
    assert "processing_batch_attempt_id" in sql
    assert "fk_modeling_metal_recipe_exact" in sql
    assert "fk_modeling_metal_batch_attempt_exact" in sql
    assert "validate_metal_recipe_batch_origin" in sql
    assert "origin.status IS DISTINCT FROM 'succeeded'" in sql
    assert "origin.output_revision_id IS DISTINCT FROM NEW.processing_output_revision_id" in sql


def test_t70_downgrade_refuses_to_erase_immutable_origin() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "cannot downgrade while immutable metal Recipe/Batch evidence exists" in sql
