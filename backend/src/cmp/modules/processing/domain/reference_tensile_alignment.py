"""Explicit common-grid alignment for immutable reference tensile replicates."""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise

from cmp.modules.datasets.domain.reference_tensile import CurvePoint
from cmp.modules.processing.domain.reference_tensile_crop import (
    REFERENCE_TENSILE_CROP_INPUT_SCHEMA,
    REFERENCE_TENSILE_CROP_OUTPUT_SCHEMA,
    REFERENCE_TENSILE_CROP_SCHEMA_PAIRS,
    InvalidProcessingRequest,
)

REFERENCE_TENSILE_ALIGNMENT_RECIPE_KIND = "reference_tensile_common_grid_linear"
REFERENCE_TENSILE_ALIGNMENT_SCHEMA_VERSION = "1.0.0"
REFERENCE_TENSILE_ALIGNMENT_SCHEMA_ID = (
    "urn:cmp:processing:reference-tensile-common-grid-recipe:1.0.0"
)
REFERENCE_TENSILE_ALIGNMENT_DIAGNOSTICS_SCHEMA = (
    "urn:cmp:processing:reference-tensile-common-grid-diagnostics:1.0.0"
)


class AlignmentDomainPolicy(StrEnum):
    INTERSECTION = "intersection"


class AlignmentInterpolationPolicy(StrEnum):
    PIECEWISE_LINEAR = "piecewise_linear"


class AlignmentExtrapolationPolicy(StrEnum):
    REJECT = "reject"


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise InvalidProcessingRequest(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class ReferenceTensileAlignmentRecipeContent:
    """A fully declared common engineering-strain grid with no hidden policy defaults."""

    recipe_label: str
    grid_start_engineering_strain: float
    grid_end_engineering_strain: float
    grid_point_count: int
    domain_policy: AlignmentDomainPolicy
    interpolation_policy: AlignmentInterpolationPolicy
    extrapolation_policy: AlignmentExtrapolationPolicy
    input_schema_ref: str = REFERENCE_TENSILE_CROP_INPUT_SCHEMA
    output_schema_ref: str = REFERENCE_TENSILE_CROP_OUTPUT_SCHEMA

    def __post_init__(self) -> None:
        if (
            not self.recipe_label
            or self.recipe_label != self.recipe_label.strip()
            or len(self.recipe_label) > 160
            or "\x00" in self.recipe_label
        ):
            raise InvalidProcessingRequest(
                "recipe_label must be trimmed and contain 1..160 characters"
            )
        _finite("grid_start_engineering_strain", self.grid_start_engineering_strain)
        _finite("grid_end_engineering_strain", self.grid_end_engineering_strain)
        if self.grid_start_engineering_strain < 0.0:
            raise InvalidProcessingRequest(
                "grid_start_engineering_strain must be non-negative"
            )
        if self.grid_end_engineering_strain <= self.grid_start_engineering_strain:
            raise InvalidProcessingRequest(
                "grid_end_engineering_strain must be greater than grid_start_engineering_strain"
            )
        if not 2 <= self.grid_point_count <= 100_000:
            raise InvalidProcessingRequest("grid_point_count must be between 2 and 100000")
        if self.domain_policy is not AlignmentDomainPolicy.INTERSECTION:
            raise InvalidProcessingRequest("only the explicit intersection domain is supported")
        if self.interpolation_policy is not AlignmentInterpolationPolicy.PIECEWISE_LINEAR:
            raise InvalidProcessingRequest(
                "only explicit piecewise-linear interpolation is supported"
            )
        if self.extrapolation_policy is not AlignmentExtrapolationPolicy.REJECT:
            raise InvalidProcessingRequest("extrapolation must be explicitly rejected")
        if (self.input_schema_ref, self.output_schema_ref) not in (
            REFERENCE_TENSILE_CROP_SCHEMA_PAIRS
        ):
            raise InvalidProcessingRequest(
                "reference tensile Recipe input/output schema versions must form a reviewed pair"
            )


@dataclass(frozen=True, slots=True)
class ReferenceTensileAlignmentOutcome:
    points: tuple[CurvePoint, ...]
    input_point_count: int
    common_domain_start: float
    common_domain_end: float

    @property
    def output_point_count(self) -> int:
        return len(self.points)


def reference_tensile_alignment_canonical(
    value: ReferenceTensileAlignmentRecipeContent,
) -> dict[str, object]:
    return {
        "recipe_kind": REFERENCE_TENSILE_ALIGNMENT_RECIPE_KIND,
        "input_schema_ref": value.input_schema_ref,
        "output_schema_ref": value.output_schema_ref,
        "steps": [
            {
                "ordinal": 0,
                "step_kind": "align_engineering_stress_to_common_engineering_strain_grid",
                "grid_start_engineering_strain": value.grid_start_engineering_strain,
                "grid_end_engineering_strain": value.grid_end_engineering_strain,
                "grid_point_count": value.grid_point_count,
                "domain_policy": value.domain_policy.value,
                "interpolation_policy": value.interpolation_policy.value,
                "extrapolation_policy": value.extrapolation_policy.value,
                "diagnostics_schema_ref": REFERENCE_TENSILE_ALIGNMENT_DIAGNOSTICS_SCHEMA,
            }
        ],
    }


def common_intersection_domain(
    curves: tuple[tuple[CurvePoint, ...], ...],
) -> tuple[float, float]:
    if len(curves) < 2:
        raise InvalidProcessingRequest("replicate alignment requires at least two curves")
    starts: list[float] = []
    ends: list[float] = []
    for points in curves:
        _validate_curve(points)
        starts.append(points[0].engineering_strain)
        ends.append(points[-1].engineering_strain)
    start = max(starts)
    end = min(ends)
    if end <= start:
        raise InvalidProcessingRequest("replicate curves have no common strain interval")
    return start, end


def _validate_curve(points: tuple[CurvePoint, ...]) -> None:
    if len(points) < 2:
        raise InvalidProcessingRequest("alignment input requires at least two points")
    strains = tuple(point.engineering_strain for point in points)
    if any(right <= left for left, right in pairwise(strains)):
        raise InvalidProcessingRequest(
            "alignment input engineering strain must be strictly increasing"
        )


def _linear_stress(
    points: tuple[CurvePoint, ...], strains: tuple[float, ...], strain: float
) -> float:
    right = bisect.bisect_left(strains, strain)
    if right < len(points) and strains[right] == strain:
        return points[right].engineering_stress
    if right == 0 or right == len(points):
        raise InvalidProcessingRequest("alignment would require forbidden extrapolation")
    left_point = points[right - 1]
    right_point = points[right]
    fraction = (strain - left_point.engineering_strain) / (
        right_point.engineering_strain - left_point.engineering_strain
    )
    return left_point.engineering_stress + fraction * (
        right_point.engineering_stress - left_point.engineering_stress
    )


def align_reference_tensile_curve(
    points: tuple[CurvePoint, ...],
    recipe: ReferenceTensileAlignmentRecipeContent,
    *,
    common_domain: tuple[float, float],
) -> ReferenceTensileAlignmentOutcome:
    """Return a new curve on the declared grid; the input tuple is never changed."""

    _validate_curve(points)
    domain_start, domain_end = common_domain
    _finite("common_domain_start", domain_start)
    _finite("common_domain_end", domain_end)
    if domain_end <= domain_start:
        raise InvalidProcessingRequest("common alignment domain is empty")
    tolerance = 1e-12 * max(1.0, abs(domain_start), abs(domain_end))
    if (
        recipe.grid_start_engineering_strain < domain_start - tolerance
        or recipe.grid_end_engineering_strain > domain_end + tolerance
    ):
        raise InvalidProcessingRequest(
            "declared alignment grid must remain inside every replicate curve domain"
        )
    step = (
        recipe.grid_end_engineering_strain - recipe.grid_start_engineering_strain
    ) / (recipe.grid_point_count - 1)
    grid = tuple(
        recipe.grid_end_engineering_strain
        if index == recipe.grid_point_count - 1
        else recipe.grid_start_engineering_strain + index * step
        for index in range(recipe.grid_point_count)
    )
    source_strains = tuple(point.engineering_strain for point in points)
    aligned = tuple(
        CurvePoint(strain, _linear_stress(points, source_strains, strain))
        for strain in grid
    )
    return ReferenceTensileAlignmentOutcome(
        points=aligned,
        input_point_count=len(points),
        common_domain_start=domain_start,
        common_domain_end=domain_end,
    )
