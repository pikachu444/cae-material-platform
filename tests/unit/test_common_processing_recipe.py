from uuid import UUID

import pytest
from cmp.modules.processing.domain.common_pipeline import CommonPipelineError, ProcessingStep
from cmp.modules.processing.domain.common_recipes import (
    CommonProcessingRecipeContent,
    RecipeLifecycle,
    common_processing_recipe_canonical,
)


def _recipe(*, lifecycle: RecipeLifecycle = RecipeLifecycle.DRAFT) -> CommonProcessingRecipeContent:
    return CommonProcessingRecipeContent(
        recipe_key="normalized-tensile-cleanup",
        label="Normalized tensile cleanup",
        description="Explicit sort and duplicate rejection",
        mapping_profile_id=UUID("d5410000-0000-4000-8000-000000000001"),
        mapping_profile_revision_id=UUID("d5410000-0000-4000-8000-000000000002"),
        mapping_profile_sha256="a" * 64,
        steps=(
            ProcessingStep(
                "rows.sort_unique", "1.0.0", {"duplicate_policy": "reject"}
            ),
        ),
        lifecycle_state=lifecycle,
    )


def test_recipe_canonical_pins_profile_step_version_and_lifecycle() -> None:
    value = _recipe(lifecycle=RecipeLifecycle.PUBLISHED)
    canonical = common_processing_recipe_canonical(value)

    assert canonical["mapping_profile"] == {
        "aggregate_id": "d5410000-0000-4000-8000-000000000001",
        "revision_id": "d5410000-0000-4000-8000-000000000002",
        "sha256": "a" * 64,
    }
    assert canonical["steps"] == [
        {
            "method_id": "rows.sort_unique",
            "method_version": "1.0.0",
            "options": {"duplicate_policy": "reject"},
        }
    ]
    assert canonical["lifecycle_state"] == "published"
    assert len(value.digest) == 64


def test_recipe_rejects_empty_steps_and_invalid_profile_digest() -> None:
    base = _recipe()
    with pytest.raises(CommonPipelineError, match=r"1\.\.32"):
        CommonProcessingRecipeContent(
            base.recipe_key,
            base.label,
            base.description,
            base.mapping_profile_id,
            base.mapping_profile_revision_id,
            base.mapping_profile_sha256,
            (),
        )
    with pytest.raises(CommonPipelineError, match="SHA-256"):
        CommonProcessingRecipeContent(
            base.recipe_key,
            base.label,
            base.description,
            base.mapping_profile_id,
            base.mapping_profile_revision_id,
            "not-a-digest",
            base.steps,
        )
