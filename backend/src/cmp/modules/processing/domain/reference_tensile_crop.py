"""Typed reference crop step for the first committed Processing vertical slice."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from cmp.modules.datasets.domain.reference_tensile import CurvePoint, InvalidDatasetData

REFERENCE_TENSILE_CROP_RECIPE_KIND = "reference_tensile_inclusive_crop"
REFERENCE_TENSILE_CROP_INPUT_SCHEMA = (
    "urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0"
)
REFERENCE_TENSILE_CROP_OUTPUT_SCHEMA = (
    "urn:cmp:datasets:reference-tensile-processed-parquet:1.0.0"
)
REFERENCE_TENSILE_CROP_DIAGNOSTICS_SCHEMA = (
    "urn:cmp:processing:reference-tensile-crop-diagnostics:1.0.0"
)
REFERENCE_TENSILE_CROP_SCHEMA_VERSION = "1.0.0"


class ProcessingError(Exception):
    """Base error for typed Processing commands."""


class InvalidProcessingRequest(ProcessingError, ValueError):
    """The recipe or run request violates declared reference-step semantics."""


class ProcessingConflict(ProcessingError):
    """An immutable recipe, selection, or output state conflicts with the command."""


class ProcessingNotFound(ProcessingError):
    """A Processing resource is absent or not visible in the tenant scope."""


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise InvalidProcessingRequest(f"{name} must be finite")


def _label(value: str) -> None:
    if not value or value != value.strip() or len(value) > 160 or "\x00" in value:
        raise InvalidProcessingRequest("recipe_label must be trimmed and contain 1..160 characters")


@dataclass(frozen=True, slots=True)
class ReferenceTensileCropRecipeContent:
    """A one-step inclusive crop over normalized engineering strain.

    Boundaries select already-observed points only.  The step never interpolates a boundary,
    extrapolates, smooths, resamples, or changes stress/strain semantics.
    """

    recipe_label: str
    minimum_engineering_strain: float
    maximum_engineering_strain: float

    def __post_init__(self) -> None:
        _label(self.recipe_label)
        _finite("minimum_engineering_strain", self.minimum_engineering_strain)
        _finite("maximum_engineering_strain", self.maximum_engineering_strain)
        if self.minimum_engineering_strain < 0.0:
            raise InvalidProcessingRequest("minimum_engineering_strain must be non-negative")
        if self.maximum_engineering_strain <= self.minimum_engineering_strain:
            raise InvalidProcessingRequest(
                "maximum_engineering_strain must be greater than minimum_engineering_strain"
            )


@dataclass(frozen=True, slots=True)
class ReferenceTensileCropOutcome:
    points: tuple[CurvePoint, ...]
    input_point_count: int
    removed_point_count: int

    @property
    def output_point_count(self) -> int:
        return len(self.points)


class ProcessingRunStatus(StrEnum):
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def reference_tensile_crop_canonical(
    value: ReferenceTensileCropRecipeContent,
) -> dict[str, object]:
    """Return an explicit one-step manifest, not a generic parameter payload."""

    return {
        "recipe_kind": REFERENCE_TENSILE_CROP_RECIPE_KIND,
        "input_schema_ref": REFERENCE_TENSILE_CROP_INPUT_SCHEMA,
        "output_schema_ref": REFERENCE_TENSILE_CROP_OUTPUT_SCHEMA,
        "steps": [
            {
                "ordinal": 0,
                "step_kind": "inclusive_crop_by_engineering_strain",
                "minimum_engineering_strain": value.minimum_engineering_strain,
                "maximum_engineering_strain": value.maximum_engineering_strain,
                "boundary_policy": "select_observed_points_inclusive_no_interpolation",
                "diagnostics_schema_ref": REFERENCE_TENSILE_CROP_DIAGNOSTICS_SCHEMA,
            }
        ],
    }


def crop_reference_tensile_points(
    points: tuple[CurvePoint, ...],
    recipe: ReferenceTensileCropRecipeContent,
) -> ReferenceTensileCropOutcome:
    """Select observed normalized points inclusively; never mutate or interpolate source data."""

    if len(points) < 2:
        raise InvalidProcessingRequest("reference crop requires at least two normalized points")
    try:
        selected = tuple(
            point
            for point in points
            if recipe.minimum_engineering_strain
            <= point.engineering_strain
            <= recipe.maximum_engineering_strain
        )
    except InvalidDatasetData as error:
        raise InvalidProcessingRequest(
            "reference crop input contains invalid curve data"
        ) from error
    if len(selected) < 2:
        raise InvalidProcessingRequest(
            "crop bounds must retain at least two observed normalized curve points"
        )
    return ReferenceTensileCropOutcome(
        points=selected,
        input_point_count=len(points),
        removed_point_count=len(points) - len(selected),
    )
