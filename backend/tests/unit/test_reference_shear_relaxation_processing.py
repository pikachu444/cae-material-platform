from __future__ import annotations

from typing import cast

import pytest
from cmp.modules.datasets.domain.reference_shear_relaxation import ShearRelaxationPoint
from cmp.modules.processing.domain.reference_shear_relaxation_crop import (
    REFERENCE_SHEAR_RELAXATION_CROP_INPUT_SCHEMA,
    REFERENCE_SHEAR_RELAXATION_CROP_OUTPUT_SCHEMA,
    ReferenceShearRelaxationCropRecipeContent,
    crop_reference_shear_relaxation_points,
)
from cmp.modules.processing.domain.reference_tensile_crop import InvalidProcessingRequest

POINTS = (
    ShearRelaxationPoint(0.0, 925_000_000.0),
    ShearRelaxationPoint(1.0, 760_000_000.0),
    ShearRelaxationPoint(10.0, 560_000_000.0),
    ShearRelaxationPoint(50.0, 440_000_000.0),
    ShearRelaxationPoint(100.0, 390_000_000.0),
)


def test_time_crop_selects_only_observed_points_and_declares_schema_transition() -> None:
    recipe = ReferenceShearRelaxationCropRecipeContent("Calibration window", 1.0, 50.0)
    outcome = crop_reference_shear_relaxation_points(POINTS, recipe)
    assert outcome.points == POINTS[1:4]
    assert outcome.input_point_count == 5
    assert outcome.output_point_count == 3
    assert outcome.removed_point_count == 2
    manifest = recipe.canonical()
    assert manifest["input_schema_ref"] == REFERENCE_SHEAR_RELAXATION_CROP_INPUT_SCHEMA
    assert manifest["output_schema_ref"] == REFERENCE_SHEAR_RELAXATION_CROP_OUTPUT_SCHEMA
    steps = cast(list[dict[str, object]], manifest["steps"])
    assert str(steps[0]["boundary_policy"]).endswith("no_interpolation")


def test_time_crop_rejects_invalid_bounds_or_fewer_than_three_retained_points() -> None:
    with pytest.raises(InvalidProcessingRequest, match="greater"):
        ReferenceShearRelaxationCropRecipeContent("Bad", 10.0, 10.0)
    with pytest.raises(InvalidProcessingRequest, match="at least three"):
        crop_reference_shear_relaxation_points(
            POINTS,
            ReferenceShearRelaxationCropRecipeContent("Too narrow", 50.0, 100.0),
        )
