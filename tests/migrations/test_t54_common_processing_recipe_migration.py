from pathlib import Path


def test_t54_recipe_migration_has_exact_profile_pin_and_typed_steps() -> None:
    source = Path(
        "backend/migrations/versions/20260831_065_T54_common_processing_recipes.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260831_065_t54_recipe"' in source
    assert 'down_revision: str | None = "20260830_064_t53_output"' in source
    assert "common_processing_recipe_revision" in source
    assert "common_processing_recipe_step" in source
    assert "fk_processing_common_recipe_profile_exact" in source
    assert "mapping_profile_revision_id" in source
    assert "options_sha256" in source
    assert "lifecycle_state IN ('draft','published')" in source
    assert "jsonb_typeof(options)='object'" in source
