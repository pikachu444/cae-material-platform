from __future__ import annotations

from uuid import UUID

import pytest
from cmp.modules.catalog.domain.model import (
    Applicability,
    InvalidCatalogCommand,
    MaterialClass,
    MaterialContent,
    PropertySetContent,
    PropertySource,
    PropertySourceKind,
    material_canonical,
    property_set_canonical,
)

STATE = UUID("c7000000-0000-4000-8000-000000000001")
STATE_REVISION = UUID("c7000000-0000-4000-8000-000000000002")


def _source() -> PropertySource:
    return PropertySource(PropertySourceKind.MANUAL)


def test_material_class_is_explicit_canonical_routing_metadata() -> None:
    legacy = MaterialContent("Legacy material")
    steel = MaterialContent(
        "Reference steel",
        material_code="REF-STEEL",
        material_family="steel",
        material_class=MaterialClass.METAL,
    )

    assert material_canonical(legacy)["material_class"] == "unclassified"
    assert material_canonical(steel)["material_class"] == "metal"


def test_initial_property_set_is_typed_si_content_not_a_generic_attribute_map() -> None:
    content = PropertySetContent(
        material_state_id=STATE,
        material_state_revision_id=STATE_REVISION,
        density_kg_per_m3=7850.0,
        density_source=_source(),
        youngs_modulus_pa=210_000_000_000.0,
        youngs_modulus_source=_source(),
        poisson_ratio=0.3,
        poisson_ratio_source=_source(),
        yield_stress_pa=355_000_000.0,
        yield_stress_source=PropertySource(
            PropertySourceKind.SUPPLIER_DATASHEET, "datasheet:acme-s355:2026-01"
        ),
        applicability=Applicability(
            temperature_min_k=273.15,
            temperature_max_k=373.15,
            strain_rate_min_per_s=0.0,
            strain_rate_max_per_s=1.0,
        ),
    )

    document = property_set_canonical(content)

    assert set(document) == {
        "material_state_id",
        "material_state_revision_id",
        "density_kg_per_m3",
        "density_source",
        "youngs_modulus_pa",
        "youngs_modulus_source",
        "poisson_ratio",
        "poisson_ratio_source",
        "yield_stress_pa",
        "yield_stress_source",
        "applicability",
    }
    assert "key" not in document
    assert "value" not in document
    assert document["density_kg_per_m3"] == 7850.0
    assert document["youngs_modulus_pa"] == 210_000_000_000.0


def test_typed_property_invariants_reject_unstable_elasticity_and_unattributed_source() -> None:
    with pytest.raises(InvalidCatalogCommand, match="stable isotropic interval"):
        PropertySetContent(
            material_state_id=STATE,
            material_state_revision_id=STATE_REVISION,
            density_kg_per_m3=7850.0,
            density_source=_source(),
            youngs_modulus_pa=210_000_000_000.0,
            youngs_modulus_source=_source(),
            poisson_ratio=0.5,
            poisson_ratio_source=_source(),
        )

    with pytest.raises(InvalidCatalogCommand, match="requires a stable source reference"):
        PropertySource(PropertySourceKind.TEST_DERIVED)


def test_property_set_keeps_yield_value_and_source_as_an_atomic_typed_pair() -> None:
    with pytest.raises(InvalidCatalogCommand, match="supplied together"):
        PropertySetContent(
            material_state_id=STATE,
            material_state_revision_id=STATE_REVISION,
            density_kg_per_m3=7850.0,
            density_source=_source(),
            youngs_modulus_pa=210_000_000_000.0,
            youngs_modulus_source=_source(),
            poisson_ratio=0.3,
            poisson_ratio_source=_source(),
            yield_stress_pa=355_000_000.0,
        )
