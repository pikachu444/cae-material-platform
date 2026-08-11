from __future__ import annotations

from dataclasses import replace

import pytest
from cmp.modules.datasets.domain.curve_metadata import (
    AxisRole,
    BoundDirection,
    Coverage,
    CurveChannel,
    CurveContractError,
    CurveDefinition,
    CurveDeviation,
    CurveSeries,
    DeviationKind,
    DeviationScope,
    OriginalUnit,
    UnitContract,
    ValueBasis,
    curve_definition_canonical,
    curve_definition_from_mapping,
)
from cmp.modules.units.domain.system import DimensionId


def _strain(*, originals: tuple[OriginalUnit, ...] | None = None) -> CurveChannel:
    return CurveChannel(
        key="engineering_strain",
        label="Engineering strain",
        quantity_semantics="mechanics.strain.engineering",
        axis_role=AxisRole.INDEPENDENT,
        unit_contract=UnitContract.COMMON,
        dimension=DimensionId.STRAIN,
        original_units=originals or (OriginalUnit("1", "1"),),
        normalized_unit="1",
        display_unit="%",
        display_scale="100",
        display_offset="0",
        value_basis=ValueBasis.NORMALIZED,
    )


def _stress() -> CurveChannel:
    return CurveChannel(
        key="mean_stress",
        label="Mean engineering stress",
        quantity_semantics="mechanics.stress.engineering",
        axis_role=AxisRole.DEPENDENT,
        unit_contract=UnitContract.COMMON,
        dimension=DimensionId.FORCE_PER_AREA,
        original_units=(OriginalUnit("MPa", "1000000"),),
        normalized_unit="Pa",
        display_unit="MPa",
        display_scale="0.000001",
        display_offset="0",
        value_basis=ValueBasis.DERIVED,
    )


def _sd() -> CurveDeviation:
    return CurveDeviation(
        key="stress_sd",
        target_channel_key="mean_stress",
        scope=DeviationScope.POINTWISE,
        kind=DeviationKind.STANDARD_DEVIATION,
        method_id="sample.standard_deviation",
        method_version="1.0.0",
        unit="Pa",
        series_key="stress_sd_values",
        source_count=3,
        ddof=1,
    )


def _ci(direction: BoundDirection) -> CurveDeviation:
    suffix = direction.value
    return CurveDeviation(
        key=f"mean_ci_{suffix}",
        target_channel_key="mean_stress",
        scope=DeviationScope.POINTWISE,
        kind=DeviationKind.CONFIDENCE_BOUND,
        method_id="student_t.two_sided",
        method_version="1.0.0",
        unit="Pa",
        bound_direction=direction,
        band_group="mean_ci_95",
        series_key=f"mean_ci_{suffix}_values",
        source_count_series_key="pointwise_source_count",
        confidence_level=0.95,
        coverage=Coverage.POINTWISE,
        ddof=1,
    )


def test_definition_supports_mixed_original_units_auxiliary_and_exact_unit_profile() -> None:
    temperature = CurveChannel(
        key="temperature",
        label="Test temperature",
        quantity_semantics="temperature.test",
        axis_role=AxisRole.AUXILIARY,
        unit_contract=UnitContract.COMMON,
        dimension=DimensionId.TEMPERATURE,
        original_units=(OriginalUnit("Cel", "1", "273.15"),),
        normalized_unit="K",
        display_unit="Cel",
        display_scale="1",
        display_offset="-273.15",
        value_basis=ValueBasis.NORMALIZED,
    )
    definition = CurveDefinition(
        channels=(
            _strain(
                originals=(OriginalUnit("%", "0.01"), OriginalUnit("1", "1"))
            ),
            _stress(),
            temperature,
        ),
        deviations=(_sd(), _ci(BoundDirection.LOWER), _ci(BoundDirection.UPPER)),
    )

    assert len(definition.sha256) == 64
    assert curve_definition_from_mapping(curve_definition_canonical(definition)) == definition


def test_closed_unit_registry_does_not_reject_explicit_legacy_frequency() -> None:
    frequency = CurveChannel(
        key="frequency",
        label="Cyclic frequency",
        quantity_semantics="frequency.cyclic",
        axis_role=AxisRole.INDEPENDENT,
        unit_contract=UnitContract.EXPLICIT_LEGACY,
        dimension=None,
        original_units=(OriginalUnit("Hz", "1"),),
        normalized_unit="Hz",
        display_unit="Hz",
        display_scale="1",
        display_offset="0",
        value_basis=ValueBasis.ORIGINAL,
    )
    storage = replace(
        _stress(),
        key="storage_modulus",
        label="Storage modulus",
        quantity_semantics="modulus.shear.storage",
    )

    assert CurveDefinition(channels=(frequency, storage)).channels[0] == frequency


def test_pointwise_arrays_are_fully_validated_before_sampling() -> None:
    definition = CurveDefinition(channels=(_strain(), _stress()), deviations=(_sd(),))
    series = CurveSeries(
        definition=definition,
        channels={
            "engineering_strain": (0.0, 0.01, 0.02, 0.03),
            "mean_stress": (100.0, 110.0, 120.0, 130.0),
        },
        deviations={"stress_sd_values": (1.0, 1.1, 1.2, 1.3)},
        source_counts={},
    )

    assert series.sample_indices(3) == (0, 2, 3)

    with pytest.raises(CurveContractError, match="length differs") as captured:
        CurveSeries(
            definition=definition,
            channels=series.channels,
            deviations={"stress_sd_values": (1.0, 1.1)},
            source_counts={},
        )
    assert captured.value.code == "CMP-CURVE-0026"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda: replace(_stress(), dimension=DimensionId.STRAIN),
        lambda: replace(_stress(), display_scale="1"),
        lambda: replace(_stress(), axis_role=AxisRole.AUXILIARY),
    ],
)
def test_dimension_scale_and_role_mismatches_are_rejected(mutation: object) -> None:
    with pytest.raises(CurveContractError):
        CurveDefinition(channels=(_strain(), mutation()))  # type: ignore[operator]


def test_band_is_not_displayable_without_exact_lower_upper_pair() -> None:
    with pytest.raises(CurveContractError, match="exactly one lower and one upper") as captured:
        CurveDefinition(
            channels=(_strain(), _stress()), deviations=(_ci(BoundDirection.LOWER),)
        )

    assert captured.value.code == "CMP-CURVE-0024"


def test_deviation_fields_are_not_inferred_for_unrelated_kinds() -> None:
    with pytest.raises(CurveContractError, match="not applicable"):
        replace(_sd(), confidence_level=0.95, coverage=Coverage.POINTWISE)


def test_pointwise_source_count_length_and_values_are_exact() -> None:
    definition = CurveDefinition(
        channels=(_strain(), _stress()),
        deviations=(_ci(BoundDirection.LOWER), _ci(BoundDirection.UPPER)),
    )
    with pytest.raises(CurveContractError, match="source-count length differs"):
        CurveSeries(
            definition=definition,
            channels={
                "engineering_strain": (0.0, 0.1, 0.2),
                "mean_stress": (100.0, 200.0, 300.0),
            },
            deviations={
                "mean_ci_lower_values": (90.0, 190.0, 290.0),
                "mean_ci_upper_values": (110.0, 210.0, 310.0),
            },
            source_counts={"pointwise_source_count": (3, 3)},
        )


def test_zero_original_scale_is_rejected() -> None:
    with pytest.raises(CurveContractError, match="normalization scale must be non-zero"):
        OriginalUnit("MPa", "0")


def test_band_values_must_preserve_lower_upper_direction() -> None:
    definition = CurveDefinition(
        channels=(_strain(), _stress()),
        deviations=(_ci(BoundDirection.LOWER), _ci(BoundDirection.UPPER)),
    )
    with pytest.raises(CurveContractError, match="lower bound exceeds") as captured:
        CurveSeries(
            definition=definition,
            channels={
                "engineering_strain": (0.0, 0.1),
                "mean_stress": (100.0, 200.0),
            },
            deviations={
                "mean_ci_lower_values": (90.0, 210.0),
                "mean_ci_upper_values": (110.0, 190.0),
            },
            source_counts={"pointwise_source_count": (3, 3)},
        )
    assert captured.value.code == "CMP-CURVE-0024"


def test_pointwise_deviations_cannot_alias_one_physical_series() -> None:
    with pytest.raises(CurveContractError, match="series keys must be unique"):
        CurveDefinition(
            channels=(_strain(), _stress()),
            deviations=(_sd(), replace(_sd(), key="stress_se")),
        )
