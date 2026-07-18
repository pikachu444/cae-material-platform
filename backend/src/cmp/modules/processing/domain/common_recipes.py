"""Versioned, solver-neutral common Processing Recipes (T-54)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cmp.modules.processing.domain.common_pipeline import (
    MAX_PIPELINE_STEPS,
    CommonPipelineError,
    ProcessingStep,
)
from cmp.shared.domain.revisions import content_sha256


class RecipeLifecycle(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


@dataclass(frozen=True, slots=True)
class CommonProcessingRecipeContent:
    recipe_key: str
    label: str
    description: str | None
    mapping_profile_id: UUID
    mapping_profile_revision_id: UUID
    mapping_profile_sha256: str
    steps: tuple[ProcessingStep, ...]
    lifecycle_state: RecipeLifecycle = RecipeLifecycle.DRAFT

    def __post_init__(self) -> None:
        if not self.recipe_key.strip() or len(self.recipe_key) > 160:
            raise CommonPipelineError("recipe_key must contain 1..160 trimmed characters")
        if not self.label.strip() or len(self.label) > 200:
            raise CommonPipelineError("Recipe label must contain 1..200 trimmed characters")
        if self.description is not None and (
            not self.description.strip() or len(self.description) > 2000
        ):
            raise CommonPipelineError("Recipe description must contain 1..2000 characters")
        if not 1 <= len(self.steps) <= MAX_PIPELINE_STEPS:
            raise CommonPipelineError("a Recipe requires 1..32 ordered steps")
        if len(self.mapping_profile_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.mapping_profile_sha256
        ):
            raise CommonPipelineError("Recipe Mapping Profile SHA-256 is invalid")

    @property
    def digest(self) -> str:
        return content_sha256(common_processing_recipe_canonical(self))


def common_processing_recipe_canonical(
    value: CommonProcessingRecipeContent,
) -> dict[str, object]:
    return {
        "recipe_key": value.recipe_key,
        "label": value.label,
        "description": value.description,
        "mapping_profile": {
            "aggregate_id": str(value.mapping_profile_id),
            "revision_id": str(value.mapping_profile_revision_id),
            "sha256": value.mapping_profile_sha256,
        },
        "steps": [
            {
                "method_id": step.method_id,
                "method_version": step.method_version,
                "options": step.options,
            }
            for step in value.steps
        ],
        "lifecycle_state": value.lifecycle_state.value,
    }
