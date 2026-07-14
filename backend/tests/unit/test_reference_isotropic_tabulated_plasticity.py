from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
from cmp.modules.datasets.domain.reference_tensile import CurvePoint
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    REFERENCE_HARDENING_CURVE_SCHEMA,
    HardeningPointOrigin,
    InvalidTabulatedPlasticity,
    ReferenceIsotropicTabulatedPlasticityContent,
    derive_reference_isotropic_hardening_curve,
    hardening_curve_from_parquet,
    hardening_curve_parquet_bytes,
    reference_isotropic_tabulated_plasticity_canonical,
)


def _id(value: int) -> UUID:
    return UUID(int=value)


def _curve() -> tuple[CurvePoint, ...]:
    return (
        CurvePoint(0.0, 0.0),
        CurvePoint(0.001, 200_000_000.0),
        CurvePoint(0.002, 300_000_000.0),
        CurvePoint(0.01, 400_000_000.0),
        CurvePoint(0.05, 500_000_000.0),
        CurvePoint(0.10, 480_000_000.0),
    )


def test_reduction_converts_only_pre_necking_and_retains_approved_extension() -> None:
    outcome = derive_reference_isotropic_hardening_curve(
        _curve(),
        youngs_modulus_pa=200_000_000_000.0,
        initial_yield_stress_pa=250_000_000.0,
        extension_max_true_plastic_strain=0.5,
        acknowledge_post_necking_approximation=True,
    )

    assert outcome.necking_source_index == 4
    assert outcome.necking_engineering_strain == 0.05
    assert outcome.post_necking_excluded_count == 1
    assert outcome.pre_yield_excluded_count == 2
    assert outcome.points[0].true_plastic_strain == 0.0
    assert outcome.points[0].true_yield_stress_pa == 250_000_000.0
    assert outcome.points[0].origin is HardeningPointOrigin.CATALOG_YIELD_ANCHOR
    assert outcome.points[-1].true_plastic_strain == 0.5
    assert outcome.points[-1].true_yield_stress_pa == outcome.points[-2].true_yield_stress_pa
    assert outcome.points[-1].origin is HardeningPointOrigin.APPROVED_CONSTANT_EXTENSION


def test_reduction_requires_explicit_post_necking_acknowledgement() -> None:
    with pytest.raises(
        InvalidTabulatedPlasticity,
        match="post-necking constant extension must be explicitly acknowledged",
    ):
        derive_reference_isotropic_hardening_curve(
            _curve(),
            youngs_modulus_pa=200_000_000_000.0,
            initial_yield_stress_pa=250_000_000.0,
            extension_max_true_plastic_strain=0.5,
            acknowledge_post_necking_approximation=False,
        )


def test_reduction_rejects_non_monotone_source_without_hidden_resampling() -> None:
    points = list(_curve())
    points[3] = CurvePoint(0.0015, 400_000_000.0)

    with pytest.raises(InvalidTabulatedPlasticity, match="strictly increasing"):
        derive_reference_isotropic_hardening_curve(
            tuple(points),
            youngs_modulus_pa=200_000_000_000.0,
            initial_yield_stress_pa=250_000_000.0,
            extension_max_true_plastic_strain=0.5,
            acknowledge_post_necking_approximation=True,
        )


def test_hardening_parquet_round_trip_preserves_origin_and_values() -> None:
    outcome = derive_reference_isotropic_hardening_curve(
        _curve(),
        youngs_modulus_pa=200_000_000_000.0,
        initial_yield_stress_pa=250_000_000.0,
        extension_max_true_plastic_strain=0.5,
        acknowledge_post_necking_approximation=True,
    )

    encoded = hardening_curve_parquet_bytes(outcome.points)

    assert hardening_curve_from_parquet(encoded) == outcome.points


def test_ir_canonical_pins_dataset_artifact_and_transformation_evidence() -> None:
    outcome = derive_reference_isotropic_hardening_curve(
        _curve(),
        youngs_modulus_pa=200_000_000_000.0,
        initial_yield_stress_pa=250_000_000.0,
        extension_max_true_plastic_strain=0.5,
        acknowledge_post_necking_approximation=True,
    )
    content = ReferenceIsotropicTabulatedPlasticityContent(
        material_id=_id(1),
        material_revision_id=_id(2),
        material_state_id=_id(3),
        material_state_revision_id=_id(4),
        property_set_id=_id(5),
        property_set_revision_id=_id(6),
        source_dataset_id=_id(7),
        source_dataset_revision_id=_id(8),
        hardening_curve_artifact_id=_id(9),
        hardening_curve_sha256="a" * 64,
        hardening_curve_point_count=len(outcome.points),
        source_point_count=outcome.input_point_count,
        pre_yield_excluded_point_count=outcome.pre_yield_excluded_count,
        post_necking_excluded_point_count=outcome.post_necking_excluded_count,
        necking_source_point_index=outcome.necking_source_index,
        density_kg_per_m3=7_850.0,
        youngs_modulus_pa=200_000_000_000.0,
        poisson_ratio=0.3,
        initial_yield_stress_pa=250_000_000.0,
        necking_engineering_strain=outcome.necking_engineering_strain,
        characterized_max_true_plastic_strain=(
            outcome.characterized_max_true_plastic_strain
        ),
        extension_max_true_plastic_strain=outcome.extension_max_true_plastic_strain,
        post_necking_approximation_acknowledged=True,
    )

    canonical = reference_isotropic_tabulated_plasticity_canonical(content)
    hardening_curve = cast(dict[str, object], canonical["hardening_curve"])
    transformation = cast(dict[str, object], canonical["transformation"])

    assert canonical["source_dataset_revision_id"] == str(_id(8))
    assert hardening_curve["schema_ref"] == REFERENCE_HARDENING_CURVE_SCHEMA
    assert transformation["approximation_acknowledged"] is True
    assert transformation["source_point_count"] == len(_curve())
    assert transformation["post_necking_excluded_point_count"] == 1
