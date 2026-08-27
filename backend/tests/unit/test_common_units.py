from __future__ import annotations

from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import pytest
from cmp.modules.units.adapters.api.units import install_units_api
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
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _semantics(dimension: DimensionId) -> str:
    return {
        DimensionId.FORCE_PER_AREA: "mechanics.stress.engineering",
        DimensionId.LENGTH: "length",
        DimensionId.SPEED: "kinematics.speed",
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

    source_density = convert_value(
        "7.85e-9",
        original_unit_string="tonne/mm3",
        source=QuantityReference(
            DimensionId.MASS_PER_VOLUME, "mass.density", "tonne/mm3"
        ),
        target=QuantityReference(
            DimensionId.MASS_PER_VOLUME, "mass.density", "kg/m3"
        ),
        location="source_v2.technical_data.density",
    )
    display_density = convert_value(
        source_density.converted_value,
        original_unit_string="kg/m3",
        source=source_density.target,
        target=QuantityReference(
            DimensionId.MASS_PER_VOLUME, "mass.density", "g/cm3"
        ),
        location="source_v2.technical_data.density",
    )
    assert source_density.converted_value == Decimal("7850")
    assert display_density.converted_value == Decimal("7.85")


def test_speed_mm_per_minute_chain_round_trips_within_declared_tolerance() -> None:
    mm_per_minute = QuantityReference(
        DimensionId.SPEED, "kinematics.speed", "mm/min"
    )
    mm_per_second = QuantityReference(
        DimensionId.SPEED, "kinematics.speed", "mm/s"
    )
    metres_per_second = QuantityReference(
        DimensionId.SPEED, "kinematics.speed", "m/s"
    )

    as_mm_per_second = convert_value(
        "60",
        original_unit_string="mm/min",
        source=mm_per_minute,
        target=mm_per_second,
        location="test_condition.tensile_speed",
    )
    as_metres_per_second = convert_value(
        as_mm_per_second.converted_value,
        original_unit_string="mm/s",
        source=mm_per_second,
        target=metres_per_second,
        location="test_condition.tensile_speed",
    )
    round_trip = convert_value(
        as_metres_per_second.converted_value,
        original_unit_string="m/s",
        source=metres_per_second,
        target=mm_per_minute,
        location="test_condition.tensile_speed",
    )

    assert abs(as_mm_per_second.converted_value - Decimal("1")) <= Decimal("1e-12")
    assert abs(as_metres_per_second.converted_value - Decimal("0.001")) <= Decimal(
        "1e-12"
    )
    assert abs(round_trip.converted_value - Decimal("60")) <= max(
        round_trip.absolute_tolerance,
        Decimal("60") * round_trip.relative_tolerance,
    )


def test_original_unit_alias_is_validated_and_preserved_verbatim() -> None:
    converted = convert_value(
        "12",
        original_unit_string="µm",
        source=QuantityReference(DimensionId.LENGTH, "length", "um"),
        target=QuantityReference(DimensionId.LENGTH, "length", "m"),
        location="geometry.gauge_length",
    )

    assert converted.original_unit_string == "µm"
    assert converted.source.unit_id == "um"
    assert converted.converted_value == Decimal("0.000012")


def test_original_unit_must_be_bounded_and_identify_declared_source() -> None:
    source = QuantityReference(DimensionId.LENGTH, "length", "m")
    target = QuantityReference(DimensionId.LENGTH, "length", "cm")

    with pytest.raises(UnitError) as unsupported:
        convert_value(
            "1",
            original_unit_string="inch",
            source=source,
            target=target,
            location="geometry.gauge_length",
        )
    assert unsupported.value.detail() == {
        "code": "CMP-UNIT-0001",
        "message": "unsupported unit identifier: inch",
        "location": "geometry.gauge_length.original_unit_string",
        "source_dimension": None,
        "target_dimension": None,
    }

    with pytest.raises(UnitError) as mismatched:
        convert_value(
            "1",
            original_unit_string="mm",
            source=source,
            target=target,
            location="geometry.gauge_length",
        )
    assert mismatched.value.detail() == {
        "code": "CMP-UNIT-0005",
        "message": "original_unit_string does not identify the declared source unit",
        "location": "geometry.gauge_length.original_unit_string",
        "source_dimension": "length",
        "target_dimension": "length",
    }


def test_conversion_api_rejects_unbounded_and_source_mismatched_original_unit() -> None:
    test_app = FastAPI()
    install_units_api(
        test_app,
        service=None,
        security_dependency=lambda: None,
        read_dependency=lambda: None,
        write_dependency=lambda: None,
    )
    payload: dict[str, Any] = {
        "location": "geometry.gauge_length",
        "value": "1",
        "original_unit_string": "inch",
        "source": {
            "dimension": "length",
            "quantity_semantics": "length",
            "unit_id": "m",
        },
        "target": {
            "dimension": "length",
            "quantity_semantics": "length",
            "unit_id": "cm",
        },
    }

    with TestClient(test_app) as client:
        unsupported = client.post("/api/v1/unit-conversions", json=payload)
        assert unsupported.status_code == 422
        assert unsupported.json() == {
            "detail": {
                "code": "CMP-UNIT-0001",
                "message": "unsupported unit identifier: inch",
                "location": "geometry.gauge_length.original_unit_string",
                "source_dimension": None,
                "target_dimension": None,
            }
        }

        payload["original_unit_string"] = "mm"
        mismatched = client.post("/api/v1/unit-conversions", json=payload)
        assert mismatched.status_code == 422
        assert mismatched.json() == {
            "detail": {
                "code": "CMP-UNIT-0005",
                "message": (
                    "original_unit_string does not identify the declared source unit"
                ),
                "location": "geometry.gauge_length.original_unit_string",
                "source_dimension": "length",
                "target_dimension": "length",
            }
        }

        payload["original_unit_string"] = "μm"
        payload["source"]["unit_id"] = "um"
        payload["target"]["unit_id"] = "m"
        valid_alias = client.post("/api/v1/unit-conversions", json=payload)
        assert valid_alias.status_code == 200
        assert valid_alias.json()["original_unit_string"] == "μm"


def test_task2_unit_api_exposes_1_1_registry_and_converts_speed() -> None:
    test_app = FastAPI()
    install_units_api(
        test_app,
        service=None,
        security_dependency=lambda: None,
        read_dependency=lambda: None,
        write_dependency=lambda: None,
    )

    with TestClient(test_app) as client:
        registry = client.get("/api/v1/unit-system")
        assert registry.status_code == 200
        body = registry.json()
        assert body["contract_version"] == "1.1.0"
        speed = next(item for item in body["dimensions"] if item["dimension"] == "speed")
        assert speed["canonical_unit_id"] == "m/s"
        assert [item["unit_id"] for item in speed["units"]] == [
            "m/s",
            "mm/s",
            "mm/min",
        ]

        converted = client.post(
            "/api/v1/unit-conversions",
            json={
                "location": "test_data.conditions.tensile_speed",
                "value": "60",
                "original_unit_string": "mm/min",
                "source": {
                    "dimension": "speed",
                    "quantity_semantics": "kinematics.speed",
                    "unit_id": "mm/min",
                },
                "target": {
                    "dimension": "speed",
                    "quantity_semantics": "kinematics.speed",
                    "unit_id": "m/s",
                },
            },
        )
        assert converted.status_code == 200
        assert abs(Decimal(converted.json()["converted_value"]) - Decimal("0.001")) <= (
            Decimal("1e-12")
        )


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


def test_task2_units_fail_closed_for_cross_dimension_wrong_source_and_spelling() -> None:
    source = QuantityReference(DimensionId.SPEED, "kinematics.speed", "mm/min")

    with pytest.raises(UnitError) as cross_dimension:
        convert_value(
            "1",
            original_unit_string="mm/min",
            source=source,
            target=QuantityReference(
                DimensionId.MASS_PER_VOLUME, "kinematics.speed", "kg/m3"
            ),
            location="source_v2.test_condition.speed",
        )
    assert cross_dimension.value.detail() == {
        "code": "CMP-UNIT-0002",
        "message": "cross-dimension conversion is not supported",
        "location": "source_v2.test_condition.speed",
        "source_dimension": "speed",
        "target_dimension": "mass_per_volume",
    }

    with pytest.raises(UnitError) as wrong_source:
        convert_value(
            "1",
            original_unit_string="mm/s",
            source=source,
            target=QuantityReference(DimensionId.SPEED, "kinematics.speed", "m/s"),
            location="source_v2.test_condition.speed",
        )
    assert wrong_source.value.detail()["location"] == (
        "source_v2.test_condition.speed.original_unit_string"
    )
    assert wrong_source.value.detail()["source_dimension"] == "speed"
    assert wrong_source.value.detail()["target_dimension"] == "speed"

    with pytest.raises(UnitError) as unsupported:
        convert_value(
            "1",
            original_unit_string="mm/sec",
            source=source,
            target=QuantityReference(DimensionId.SPEED, "kinematics.speed", "m/s"),
            location="source_v2.test_condition.speed",
        )
    assert unsupported.value.detail() == {
        "code": "CMP-UNIT-0001",
        "message": "unsupported unit identifier: mm/sec",
        "location": "source_v2.test_condition.speed.original_unit_string",
        "source_dimension": None,
        "target_dimension": None,
    }

    with pytest.raises(UnitError) as semantics:
        convert_value(
            "1",
            original_unit_string="mm/min",
            source=source,
            target=QuantityReference(
                DimensionId.SPEED,
                "process.crosshead_speed",
                "m/s",
            ),
            location="source_v2.test_condition.speed",
        )
    assert semantics.value.detail() == {
        "code": "CMP-UNIT-0003",
        "message": "conversion cannot change quantity semantics",
        "location": "source_v2.test_condition.speed",
        "source_dimension": "speed",
        "target_dimension": "speed",
    }


@pytest.mark.parametrize(
    "value",
    [
        "NaN",
        "Infinity",
        "-Infinity",
        "1e309",
        "1e-309",
        "12345678901234567890123456789012345",
    ],
)
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
    assert caught.value.detail()["code"] == "CMP-UNIT-0004"
    assert caught.value.detail()["location"] == "value.value"
    assert caught.value.detail()["source_dimension"] == "force_per_area"
    assert caught.value.detail()["target_dimension"] == "force_per_area"


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
            UnitProfileSelection(
                quantity_semantics="kinematics.speed",
                dimension=DimensionId.SPEED,
                input_unit_id="mm/min",
                display_unit_id="mm/s",
                solver_export_unit_id="m/s",
            ),
            UnitProfileSelection(
                quantity_semantics="mass.density",
                dimension=DimensionId.MASS_PER_VOLUME,
                input_unit_id="tonne/mm3",
                display_unit_id="g/cm3",
                solver_export_unit_id="kg/m3",
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
            (
                "source_v2.test_condition.speed",
                UnitApplicationRole.INPUT,
                "kinematics.speed",
                DimensionId.SPEED,
            ),
            (
                "source_v2.technical_data.density",
                UnitApplicationRole.SOLVER_EXPORT,
                "mass.density",
                DimensionId.MASS_PER_VOLUME,
            ),
        ),
    )

    assert profile.non_production is True
    assert applications[0].unit_id == "MPa"
    assert applications[1].unit_id == "Pa"
    assert applications[2].location == "source_v2.test_condition.speed"
    assert applications[2].unit_id == "mm/min"
    assert applications[3].location == "source_v2.technical_data.density"
    assert applications[3].unit_id == "kg/m3"


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
    assert contract["contract_version"] == "1.1.0"
    dimensions = contract["dimensions"]
    assert isinstance(dimensions, list)
    assert {item["dimension"] for item in dimensions} == {
        "force_per_area",
        "length",
        "speed",
        "time",
        "force",
        "mass",
        "mass_per_volume",
        "temperature",
        "strain",
    }
    assert "Hz" not in {
        unit["unit_id"] for item in dimensions for unit in item["units"]
    }
    compatibility = contract["compatibility_unit_systems"]
    assert isinstance(compatibility, list)
    assert compatibility == [
        {
            "unit_system_id": "kg_m_s",
            "production_default": False,
            "units": {
                "force_per_area": "Pa",
                "length": "m",
                "speed": "m/s",
                "time": "s",
                "force": "N",
                "mass": "kg",
                "mass_per_volume": "kg/m3",
                "temperature": "K",
                "strain": "1",
            },
        }
    ]
