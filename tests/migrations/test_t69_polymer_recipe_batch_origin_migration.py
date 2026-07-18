from pathlib import Path

MIGRATION = Path("backend/migrations/versions/20260915_080_T69_polymer_recipe_batch_origin.py")


def test_t69_migration_pins_exact_recipe_batch_and_attempt() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260915_080_t69_origin"' in text
    assert 'down_revision: str | None = "20260914_079_t67_polymer"' in text
    assert "processing_recipe_revision_id" in text
    assert "processing_batch_attempt_id" in text
    assert "fk_modeling_linear_prony_recipe_exact" in text
    assert "fk_modeling_linear_prony_batch_attempt_exact" in text
    assert "validate_linear_prony_recipe_batch_origin" in text
    assert "status IS DISTINCT FROM 'succeeded'" in text
    assert "output_revision_id IS DISTINCT FROM NEW.processing_output_revision_id" in text
    assert "reject_immutable_row_mutation" not in text  # parent evidence table already owns it


def test_t69_migration_rejects_partial_origin_and_protects_downgrade() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert "ck_modeling_linear_prony_recipe_batch_all_or_none" in text
    assert "processing_recipe_sha256 ~ '^[0-9a-f]{64}$'" in text
    assert "cannot downgrade while immutable Recipe/Batch evidence exists" in text
