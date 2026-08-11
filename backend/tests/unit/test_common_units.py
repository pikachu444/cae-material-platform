from __future__ import annotations

from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import pytest
from cmp.modules.units.domain.profiles import (
    UnitApplicationRole,
    UnitProfileContent,
    UnitProfilePin,
    UnitProfileSelection,
    applications_for_profile,
)
from cmp.modules.units.domain.system import (
    DIMENSIONS,
    DimensionId,
    QuantityReference,
    UnitError,
    canonical_unit_id,
    convert_value,
    unit_system_contract,
)


def _semantics(dimension: DimensionId) -> str:
    return {
        DimensionId.FORCE_PER_AREA: "mechanics.stress.engineering",
        DimensionId.LENGTH: "length",
        DimensionId.TIME: "time.elapsed",
        DimensionId.FORCE: "mechanics.force",
        DimensionId.MASS: "mass",
        DimensionId.MASS_PER_VOLUME: "mass.density",
        DimensionId.TEMPERATURE: "temperature.absolute",
        DimensionId.STRAIN: "mechanics.strain.engineering",
    }[dimension]


@pytest.mark.parametrize(
    ("dimension", "source_unit", "target_unit"),
    [
        (definition.dimension, source.unit_id, target.unit_id)
        for definition in DIMENSIONS
        for source in definition.units
        for target in definition.units
    ],
)
@pytest.mark.parametrize("value", ["-123.456789", "0", "987654.321"])
def test_each_supported_unit_round_trips_within_contract_tolerance(
    dimension: DimensionId,
    source_unit: str,
    target_unit: str,
    value: str,
) -> None:
    semantics = _semantics(dimension)
    source = QuantityReference(dimension, semantics, source_unit)
    target = QuantityReference(dimension, semantics, target_unit)

    converted = convert_value(
        value,
        original_unit_string=source_unit,
        source=source,
        target=target,
        location="test.value",
    )
    round_trip = convert_value(
        converted.converted_value,
        original_unit_string=target_unit,
        source=target,
        target=source,
        location="test.value",
    )

    difference = abs(round_trip.converted_value - Decimal(value))
    allowed = max(
        converted.absolute_tolerance,
        abs(Decimal(value)) * converted.relative_tolerance,
    )
    assert difference <= allowed


def test_absolute_temperature_applies_offset_but_temperature_difference_does_not() -> None:
    absolute = convert_value(
        "25",
        original_unit_string="Cel",
        source=QuantityReference(DimensionId.TEMPERATURE, "temperature.test", "Cel"),
        target=QuantityReference(DimensionId.TEMPERATURE, "temperature.test", "K"),
        location="conditions.temperature",
    )
    difference = convert_value(
        "25",
        original_unit_string="Cel",
        source=QuantityReference(
            DimensionId.TEMPERATURE, "temperature.difference", "Cel"
        ),
        target=QuantityReference(DimensionId.TEMPERATURE, "temperature.difference", "K"),
        location="conditions.temperature_delta",
    )

    assert absolute.converted_value == Decimal("298.15")
    assert absolute.offset == Decimal("273.15")
    assert absolute.conversion_kind.value == "affine_absolute"
    assert difference.converted_value == Decimal("25")
    assert difference.offset == 0
    assert difference.conversion_kind.value == "multiplicative"


def test_density_composite_dimension_and_legacy_alias_are_explicit() -> None:
    converted = convert_value(
        "7.85",
        original_unit_string="g/cm^3",
        source=QuantityReference(DimensionId.MASS_PER_VOLUME, "mass.density", "g/cm3"),
        target=QuantityReference(DimensionId.MASS_PER_VOLUME, "mass.density", "kg/m3"),
        location="material.density",
    )

    assert canonical_unit_id("kg/m^3") == "kg/m3"
    assert canonical_unit_id("g/cm^3") == "g/cm3"
    assert converted.converted_value == Decimal("7850")


def test_cross_dimension_failure_is_structured_and_location_aware() -> None:
    with pytest.raises(UnitError) as caught:
        convert_value(
            "1",
            original_unit_string="Pa",
            source=QuantityReference(
                DimensionId.FORCE_PER_AREA,
                "mechanics.stress.engineering",
                "Pa",
            ),
            target=QuantityReference(
                DimensionId.LENGTH,
                "mechanics.stress.engineering",
                "m",
            ),
            location="records[2].yield_strength",
        )

    assert caught.value.detail() == {
        "code": "CMP-UNIT-0002",
        "message": "cross-dimension conversion is not supported",
        "location": "records[2].yield_strength",
        "source_dimension": "force_per_area",
        "target_dimension": "length",
    }
    assert caught.value.contextual_message() == (
        "cross-dimension conversion is not supported; code=CMP-UNIT-0002; "
        "location=records[2].yield_strength; source_dimension=force_per_area; "
        "target_dimension=length"
    )


def test_same_dimension_cannot_silently_change_quantity_semantics() -> None:
    with pytest.raises(UnitError, match="cannot change quantity semantics"):
        convert_value(
            "1",
            original_unit_string="1",
            source=QuantityReference(
                DimensionId.STRAIN, "mechanics.strain.engineering", "1"
            ),
            target=QuantityReference(DimensionId.STRAIN, "generic.dimensionless", "%"),
            location="test_data.channels.strain",
        )


@pytest.mark.parametrize("value", ["1e309", "1e-309", "12345678901234567890123456789012345"])
def test_numeric_range_and_precision_boundaries_fail_closed(value: str) -> None:
    with pytest.raises(UnitError) as caught:
        convert_value(
            value,
            original_unit_string="Pa",
            source=QuantityReference(
                DimensionId.FORCE_PER_AREA,
                "mechanics.stress.engineering",
                "Pa",
            ),
            target=QuantityReference(
                DimensionId.FORCE_PER_AREA,
                "mechanics.stress.engineering",
                "GPa",
            ),
            location="value",
        )
    assert caught.value.code == "CMP-UNIT-0004"


def test_conversion_overflow_after_scaling_fails_closed() -> None:
    with pytest.raises(UnitError) as caught:
        convert_value(
            "9e307",
            original_unit_string="GPa",
            source=QuantityReference(
                DimensionId.FORCE_PER_AREA,
                "mechanics.stress.engineering",
                "GPa",
            ),
            target=QuantityReference(
                DimensionId.FORCE_PER_AREA,
                "mechanics.stress.engineering",
                "Pa",
            ),
            location="value",
        )
    assert caught.value.code == "CMP-UNIT-0004"


def _profile() -> UnitProfileContent:
    return UnitProfileContent(
        profile_key="synthetic_si_display_mpa",
        label="Synthetic SI with MPa display",
        description="Non-production verification profile.",
        non_production=True,
        selections=(
            UnitProfileSelection(
                quantity_semantics="mechanics.stress.engineering",
                dimension=DimensionId.FORCE_PER_AREA,
                input_unit_id="MPa",
                display_unit_id="MPa",
                solver_export_unit_id="Pa",
            ),
            UnitProfileSelection(
                quantity_semantics="mechanics.strain.engineering",
                dimension=DimensionId.STRAIN,
                input_unit_id="%",
                display_unit_id="%",
                solver_export_unit_id="1",
            ),
        ),
    )


def test_unit_profile_is_typed_and_resolves_exact_application_locations() -> None:
    profile = _profile()
    applications = applications_for_profile(
        profile,
        uses=(
            (
                "processing.input.engineering_stress",
                UnitApplicationRole.INPUT,
                "mechanics.stress.engineering",
                DimensionId.FORCE_PER_AREA,
            ),
            (
                "solver_card.engineering_stress",
                UnitApplicationRole.SOLVER_EXPORT,
                "mechanics.stress.engineering",
                DimensionId.FORCE_PER_AREA,
            ),
        ),
    )

    assert profile.non_production is True
    assert applications[0].unit_id == "MPa"
    assert applications[1].unit_id == "Pa"


def test_profile_rejects_aliases_wrong_dimensions_and_missing_solver_choice() -> None:
    with pytest.raises(UnitError, match="stable canonical"):
        UnitProfileSelection(
            "mass.density",
            DimensionId.MASS_PER_VOLUME,
            "kg/m^3",
            "kg/m3",
        )
    with pytest.raises(UnitError, match="declared dimension"):
        UnitProfileSelection("mass", DimensionId.MASS, "kg", "MPa")
    with pytest.raises(UnitError, match="no solver export unit"):
        UnitProfileSelection("mass", DimensionId.MASS, "kg", "g").unit_for(
            UnitApplicationRole.SOLVER_EXPORT
        )


def test_exact_pin_rejects_moving_names_and_invalid_hashes() -> None:
    with pytest.raises((ValueError, TypeError)):
        UnitProfilePin(
            UUID("10000000-0000-4000-8000-000000000001"),
            cast(Any, "latest"),
            "a" * 64,
        )
    with pytest.raises(UnitError, match="SHA-256"):
        UnitProfilePin(
            UUID("10000000-0000-4000-8000-000000000001"),
            UUID("10000000-0000-4000-8000-000000000002"),
            "not-a-hash",
        )


def test_unit_system_contract_has_no_production_default() -> None:
    contract = unit_system_contract()
    compatibility = contract["compatibility_unit_systems"]
    assert isinstance(compatibility, list)
    assert compatibility == [
        {
            "unit_system_id": "kg_m_s",
            "production_default": False,
            "units": {
                "force_per_area": "Pa",
                "length": "m",
                "time": "s",
                "force": "N",
                "mass": "kg",
                "mass_per_volume": "kg/m3",
                "temperature": "K",
                "strain": "1",
            },
        }
    ]
