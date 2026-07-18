from pathlib import Path


def test_t54_batch_migration_pins_inputs_and_preserves_append_only_attempts() -> None:
    source = Path(
        "backend/migrations/versions/20260901_066_T54_common_processing_batches.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260901_066_t54_batch"' in source
    assert 'down_revision: str | None = "20260831_065_t54_recipe"' in source
    assert "fk_processing_common_batch_recipe_exact" in source
    assert "fk_processing_common_batch_member_source_exact" in source
    assert "fk_processing_common_batch_attempt_output_exact" in source
    assert "uq_processing_common_batch_attempt_no" in source
    assert "status IN ('succeeded','failed')" in source
    assert "reject_immutable_row_mutation" in source
