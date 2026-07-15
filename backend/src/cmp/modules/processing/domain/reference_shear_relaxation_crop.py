"""Explicit observed-point crop for the reference shear-relaxation vertical."""

from __future__ import annotations

import math
from dataclasses import dataclass

from cmp.modules.datasets.domain.reference_shear_relaxation import ShearRelaxationPoint
from cmp.modules.processing.domain.reference_tensile_crop import InvalidProcessingRequest
from cmp.shared.domain.revisions import content_sha256

REFERENCE_SHEAR_RELAXATION_CROP_RECIPE_KIND = "reference_shear_relaxation_inclusive_time_crop"
REFERENCE_SHEAR_RELAXATION_CROP_SCHEMA_ID = (
    "urn:cmp:processing:reference-shear-relaxation-time-crop-recipe:1.0.0"
)
REFERENCE_SHEAR_RELAXATION_CROP_SCHEMA_VERSION = "1.0.0"
REFERENCE_SHEAR_RELAXATION_CROP_INPUT_SCHEMA = (
    "urn:cmp:datasets:reference-shear-relaxation-normalized-parquet:1.0.0"
)
REFERENCE_SHEAR_RELAXATION_CROP_OUTPUT_SCHEMA = (
    "urn:cmp:datasets:reference-shear-relaxation-processed-parquet:1.0.0"
)


def _label(value: str) -> None:
    if not value or value != value.strip() or len(value) > 160 or "\x00" in value:
        raise InvalidProcessingRequest(
            "recipe_label must be trimmed and contain 1..160 characters"
        )


@dataclass(frozen=True, slots=True)
class ReferenceShearRelaxationCropRecipeContent:
    """Select observed normalized points inclusively without interpolation or smoothing."""

    recipe_label: str
    minimum_time_s: float
    maximum_time_s: float

    def __post_init__(self) -> None:
        _label(self.recipe_label)
        if not math.isfinite(self.minimum_time_s) or self.minimum_time_s < 0.0:
            raise InvalidProcessingRequest("minimum_time_s must be finite and non-negative")
        if (
            not math.isfinite(self.maximum_time_s)
            or self.maximum_time_s <= self.minimum_time_s
        ):
            raise InvalidProcessingRequest(
                "maximum_time_s must be finite and greater than minimum_time_s"
            )

    def canonical(self) -> dict[str, object]:
        return {
            "recipe_kind": REFERENCE_SHEAR_RELAXATION_CROP_RECIPE_KIND,
            "input_schema_ref": REFERENCE_SHEAR_RELAXATION_CROP_INPUT_SCHEMA,
            "output_schema_ref": REFERENCE_SHEAR_RELAXATION_CROP_OUTPUT_SCHEMA,
            "steps": [
                {
                    "ordinal": 0,
                    "step_kind": "inclusive_crop_by_time",
                    "minimum_time_s": self.minimum_time_s,
                    "maximum_time_s": self.maximum_time_s,
                    "boundary_policy": (
                        "select_observed_points_inclusive_no_interpolation"
                    ),
                }
            ],
        }

    @property
    def digest(self) -> str:
        return content_sha256(self.canonical())


@dataclass(frozen=True, slots=True)
class ReferenceShearRelaxationCropOutcome:
    points: tuple[ShearRelaxationPoint, ...]
    input_point_count: int
    removed_point_count: int

    @property
    def output_point_count(self) -> int:
        return len(self.points)


def crop_reference_shear_relaxation_points(
    points: tuple[ShearRelaxationPoint, ...],
    recipe: ReferenceShearRelaxationCropRecipeContent,
) -> ReferenceShearRelaxationCropOutcome:
    if len(points) < 3:
        raise InvalidProcessingRequest(
            "reference shear-relaxation crop requires at least three normalized points"
        )
    selected = tuple(
        point
        for point in points
        if recipe.minimum_time_s <= point.time_s <= recipe.maximum_time_s
    )
    if len(selected) < 3:
        raise InvalidProcessingRequest(
            "time bounds must retain at least three observed normalized points"
        )
    return ReferenceShearRelaxationCropOutcome(
        points=selected,
        input_point_count=len(points),
        removed_point_count=len(points) - len(selected),
    )
