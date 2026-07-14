from __future__ import annotations

import pytest
from cmp.modules.datasets.domain.reference_tensile import CurvePoint
from cmp.modules.processing.domain.reference_tensile_alignment import (
    AlignmentDomainPolicy,
    AlignmentExtrapolationPolicy,
    AlignmentInterpolationPolicy,
    ReferenceTensileAlignmentRecipeContent,
    align_reference_tensile_curve,
    common_intersection_domain,
)


def _recipe(
    start: float = 0.01, end: float = 0.03, count: int = 3
) -> ReferenceTensileAlignmentRecipeContent:
    return ReferenceTensileAlignmentRecipeContent(
        recipe_label="Common grid",
        grid_start_engineering_strain=start,
        grid_end_engineering_strain=end,
        grid_point_count=count,
        domain_policy=AlignmentDomainPolicy.INTERSECTION,
        interpolation_policy=AlignmentInterpolationPolicy.PIECEWISE_LINEAR,
        extrapolation_policy=AlignmentExtrapolationPolicy.REJECT,
    )


def test_alignment_uses_declared_grid_and_piecewise_linear_stress() -> None:
    first = (
        CurvePoint(0.0, 0.0),
        CurvePoint(0.02, 200.0),
        CurvePoint(0.04, 300.0),
    )
    second = (
        CurvePoint(0.01, 80.0),
        CurvePoint(0.03, 240.0),
        CurvePoint(0.05, 320.0),
    )

    common = common_intersection_domain((first, second))
    outcome = align_reference_tensile_curve(first, _recipe(), common_domain=common)

    assert common == (0.01, 0.04)
    assert [point.engineering_strain for point in outcome.points] == pytest.approx(
        [0.01, 0.02, 0.03]
    )
    assert [point.engineering_stress for point in outcome.points] == pytest.approx(
        [100.0, 200.0, 250.0]
    )
    assert first[1] == CurvePoint(0.02, 200.0)


def test_alignment_rejects_extrapolation_and_non_monotonic_input() -> None:
    first = (CurvePoint(0.01, 100.0), CurvePoint(0.03, 200.0))
    second = (CurvePoint(0.0, 0.0), CurvePoint(0.02, 180.0))
    common = common_intersection_domain((first, second))

    with pytest.raises(ValueError, match="inside every replicate"):
        align_reference_tensile_curve(first, _recipe(0.0, 0.02), common_domain=common)
    with pytest.raises(ValueError, match="strictly increasing"):
        common_intersection_domain(
            (
                first,
                (CurvePoint(0.02, 150.0), CurvePoint(0.02, 160.0)),
            )
        )


def test_alignment_recipe_requires_all_supported_policy_values() -> None:
    with pytest.raises(ValueError, match="grid_point_count"):
        _recipe(count=1)
