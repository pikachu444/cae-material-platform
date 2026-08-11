"""Reviewed cross-module legacy curve adapters exposed to the Catalog boundary."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.modules.datasets.application.canonical_test_data import (
    NORMALIZED_PARQUET_SCHEMA,
    NORMALIZED_PARQUET_SCHEMA_V1,
)
from cmp.modules.datasets.curve_artifacts import LegacyParquetAdapter
from cmp.modules.datasets.domain.curve_metadata import (
    AxisRole,
    BoundDirection,
    CurveChannel,
    CurveContractError,
    CurveDefinition,
    CurveDeviation,
    DeviationKind,
    DeviationScope,
    OriginalUnit,
    UnitContract,
    ValueBasis,
)
from cmp.modules.datasets.domain.reference_shear_relaxation import (
    REFERENCE_SHEAR_RELAXATION_PARQUET_SCHEMA,
)
from cmp.modules.datasets.domain.reference_tensile import (
    REFERENCE_TENSILE_PARQUET_SCHEMA,
    REFERENCE_TENSILE_PARQUET_SCHEMA_V1,
    REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA,
    REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA_V1,
    reference_tensile_curve_definition,
)
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    REFERENCE_HARDENING_CURVE_SCHEMA,
    HardeningPointOrigin,
)
from cmp.modules.processing.domain.reference_shear_relaxation_crop import (
    REFERENCE_SHEAR_RELAXATION_CROP_OUTPUT_SCHEMA,
)
from cmp.modules.processing.domain.viscoelastic_master_curve import (
    VISCOELASTIC_ALIGNED_PARQUET_SCHEMA,
    VISCOELASTIC_MASTER_PARQUET_SCHEMA,
    VISCOELASTIC_STATISTICS_PARQUET_SCHEMA,
)
from cmp.modules.statistics.domain.reference_tensile_pair import (
    REFERENCE_TENSILE_PAIR_CURVE_SCHEMA,
    REFERENCE_TENSILE_PAIR_CURVE_SCHEMA_V1,
    reference_tensile_pair_curve_definition,
)
from cmp.modules.statistics.domain.reference_tensile_replicates import (
    REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA,
    REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA_V1,
    reference_tensile_replicate_curve_definition,
)
from cmp.modules.units.domain.system import (
    DimensionId,
    UnitError,
    dimension_for_quantity_semantics,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_read_parquet = cast(Callable[..., pa.Table], pq.read_table)

_CANONICAL_TEST_DATA_CHANNELS: dict[str, tuple[str, AxisRole]] = {
    "mechanics.strain.engineering": ("Engineering strain", AxisRole.INDEPENDENT),
    "mechanics.stress.engineering": ("Engineering stress", AxisRole.DEPENDENT),
    "temperature.test": ("Test temperature", AxisRole.AUXILIARY),
    "time.elapsed": ("Elapsed time", AxisRole.INDEPENDENT),
    "modulus.shear.relaxation": ("Shear relaxation modulus", AxisRole.DEPENDENT),
    "frequency.cyclic": ("Cyclic frequency", AxisRole.INDEPENDENT),
    "modulus.shear.storage": ("Storage modulus", AxisRole.DEPENDENT),
    "modulus.shear.loss": ("Loss modulus", AxisRole.DEPENDENT),
}


def _common_channel(
    key: str,
    label: str,
    semantics: str,
    role: AxisRole,
    dimension: DimensionId,
    unit: str,
    *,
    display_unit: str | None = None,
    display_scale: str = "1",
    value_basis: ValueBasis = ValueBasis.DERIVED,
) -> CurveChannel:
    return CurveChannel(
        key=key,
        label=label,
        quantity_semantics=semantics,
        axis_role=role,
        unit_contract=UnitContract.COMMON,
        dimension=dimension,
        original_units=(OriginalUnit(unit, "1"),),
        normalized_unit=unit,
        display_unit=display_unit or unit,
        display_scale=display_scale,
        display_offset="0",
        value_basis=value_basis,
    )


def _legacy_count_channel(key: str, label: str) -> CurveChannel:
    return CurveChannel(
        key=key,
        label=label,
        quantity_semantics=key,
        axis_role=AxisRole.AUXILIARY,
        unit_contract=UnitContract.EXPLICIT_LEGACY,
        dimension=None,
        original_units=(OriginalUnit("1", "1"),),
        normalized_unit="1",
        display_unit="1",
        display_scale="1",
        display_offset="0",
        value_basis=ValueBasis.DERIVED,
    )


def _shear_definition(value_basis: ValueBasis) -> CurveDefinition:
    return CurveDefinition(
        channels=(
            _common_channel(
                "time_s",
                "Elapsed time",
                "time.elapsed",
                AxisRole.INDEPENDENT,
                DimensionId.TIME,
                "s",
                value_basis=value_basis,
            ),
            _common_channel(
                "shear_modulus_pa",
                "Shear relaxation modulus",
                "mechanics.modulus.shear.relaxation",
                AxisRole.DEPENDENT,
                DimensionId.FORCE_PER_AREA,
                "Pa",
                value_basis=value_basis,
            ),
        )
    )


def _modulus_statistics_definition(*, master: bool) -> CurveDefinition:
    independent_key = "reduced_time_s" if master else "time_s"
    independent_label = "Reduced time" if master else "Elapsed time"
    channels: list[CurveChannel] = [
        _common_channel(
            independent_key,
            independent_label,
            "time.relaxation" if master else "time.elapsed",
            AxisRole.INDEPENDENT,
            DimensionId.TIME,
            "s",
        ),
        _common_channel(
            "mean_shear_modulus_pa",
            "Mean shear relaxation modulus",
            "mechanics.modulus.shear.relaxation",
            AxisRole.DEPENDENT,
            DimensionId.FORCE_PER_AREA,
            "Pa",
        ),
    ]
    count_key = "contributing_curve_count" if master else "replicate_count"
    if not master:
        channels.extend(
            (
                _common_channel(
                    "temperature_k",
                    "Test temperature",
                    "temperature.test",
                    AxisRole.AUXILIARY,
                    DimensionId.TEMPERATURE,
                    "K",
                ),
                _common_channel(
                    "median_shear_modulus_pa",
                    "Median shear relaxation modulus",
                    "mechanics.modulus.shear.relaxation",
                    AxisRole.AUXILIARY,
                    DimensionId.FORCE_PER_AREA,
                    "Pa",
                ),
            )
        )

    def deviation(
        key: str,
        kind: DeviationKind,
        method: str,
        *,
        direction: BoundDirection = BoundDirection.NONE,
        group: str | None = None,
        ddof: int | None = None,
    ) -> CurveDeviation:
        return CurveDeviation(
            key=key,
            target_channel_key="mean_shear_modulus_pa",
            scope=DeviationScope.POINTWISE,
            kind=kind,
            method_id=method,
            method_version="1.0.0",
            unit="Pa",
            bound_direction=direction,
            band_group=group,
            series_key=key,
            source_count_series_key=count_key,
            ddof=ddof,
        )

    return CurveDefinition(
        channels=tuple(channels),
        deviations=(
            deviation(
                "sample_standard_deviation_pa",
                DeviationKind.STANDARD_DEVIATION,
                "sample.standard_deviation",
                ddof=1,
            ),
            deviation(
                "minimum_shear_modulus_pa",
                DeviationKind.RANGE_BOUND,
                "observed.minimum_maximum",
                direction=BoundDirection.LOWER,
                group="observed_shear_modulus_range",
            ),
            deviation(
                "maximum_shear_modulus_pa",
                DeviationKind.RANGE_BOUND,
                "observed.minimum_maximum",
                direction=BoundDirection.UPPER,
                group="observed_shear_modulus_range",
            ),
        ),
    )


def _hardening_definition() -> CurveDefinition:
    return CurveDefinition(
        channels=(
            _common_channel(
                "true_plastic_strain",
                "True plastic strain",
                "strain.true_plastic",
                AxisRole.INDEPENDENT,
                DimensionId.STRAIN,
                "1",
            ),
            _common_channel(
                "true_yield_stress_pa",
                "True yield stress",
                "stress.true",
                AxisRole.DEPENDENT,
                DimensionId.FORCE_PER_AREA,
                "Pa",
            ),
        )
    )


def _validate_hardening_table(table: pa.Table) -> None:
    metadata = table.schema.metadata or {}
    if metadata.get(b"cmp_schema_ref") != REFERENCE_HARDENING_CURVE_SCHEMA.encode("ascii"):
        raise CurveContractError(
            code="CMP-CURVE-0035",
            location="artifact.schema_ref",
            message="hardening Parquet schema reference is invalid",
        )
    profile = metadata.get(b"cmp_transformation_profile")
    digest = metadata.get(b"cmp_transformation_digest")
    try:
        profile_text = profile.decode("utf-8") if profile is not None else ""
        digest_text = digest.decode("ascii") if digest is not None else ""
    except UnicodeDecodeError as error:
        raise CurveContractError(
            code="CMP-CURVE-0035",
            location="artifact.parquet_metadata",
            message="hardening transformation evidence is not encoded correctly",
        ) from error
    if not profile_text or not _SHA256.fullmatch(digest_text):
        raise CurveContractError(
            code="CMP-CURVE-0035",
            location="artifact.parquet_metadata",
            message="hardening transformation profile and digest are required",
        )
    try:
        tuple(
            HardeningPointOrigin(str(value))
            for value in table.column("point_origin").to_pylist()
        )
    except (KeyError, ValueError) as error:
        raise CurveContractError(
            code="CMP-CURVE-0033",
            location="series.channels.point_origin",
            message="hardening point-origin evidence is invalid",
        ) from error


def _canonical_test_data_v1_adapter(value: bytes) -> LegacyParquetAdapter | None:
    """Read only the semantics the historical canonical format actually stored."""

    try:
        table = _read_parquet(pa.BufferReader(value))
    except Exception as error:
        raise CurveContractError(
            code="CMP-CURVE-0032",
            location="artifact.bytes",
            message="known canonical Test Data Artifact is not readable Parquet",
        ) from error
    metadata = table.schema.metadata or {}
    if metadata.get(b"cmp.schema") != NORMALIZED_PARQUET_SCHEMA_V1.encode("ascii"):
        raise CurveContractError(
            code="CMP-CURVE-0035",
            location="artifact.schema_ref",
            message="canonical Test Data Parquet schema reference drifted",
        )
    channels: list[CurveChannel] = []
    for key in table.column_names:
        semantics_raw = metadata.get(
            f"cmp.channel.{key}.quantity_semantics".encode()
        )
        unit_raw = metadata.get(f"cmp.channel.{key}.normalized_unit".encode())
        if semantics_raw is None or unit_raw is None:
            raise CurveContractError(
                code="CMP-CURVE-0034",
                location=f"artifact.parquet_metadata.{key}",
                message="historical canonical channel semantics and unit are required",
            )
        try:
            semantics = semantics_raw.decode("utf-8")
            unit = unit_raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CurveContractError(
                code="CMP-CURVE-0034",
                location=f"artifact.parquet_metadata.{key}",
                message="historical canonical channel metadata is not UTF-8",
            ) from error
        reviewed = _CANONICAL_TEST_DATA_CHANNELS.get(semantics)
        if reviewed is None:
            return None
        label, role = reviewed
        try:
            dimension = dimension_for_quantity_semantics(
                semantics, location=f"artifact.parquet_metadata.{key}.quantity_semantics"
            )
        except UnitError:
            if semantics != "frequency.cyclic" or unit != "Hz":
                return None
            channels.append(
                CurveChannel(
                    key=key,
                    label=label,
                    quantity_semantics=semantics,
                    axis_role=role,
                    unit_contract=UnitContract.EXPLICIT_LEGACY,
                    dimension=None,
                    original_units=(OriginalUnit(unit, "1"),),
                    normalized_unit=unit,
                    display_unit=unit,
                    display_scale="1",
                    display_offset="0",
                    value_basis=ValueBasis.NORMALIZED,
                )
            )
        else:
            channels.append(
                _common_channel(
                    key,
                    label,
                    semantics,
                    role,
                    dimension,
                    unit,
                    value_basis=ValueBasis.NORMALIZED,
                )
            )
    definition = CurveDefinition(channels=tuple(channels))
    return LegacyParquetAdapter(
        definition=definition,
        channel_columns={channel.key: channel.key for channel in channels},
        deviation_columns={},
        source_count_columns={},
        expected_columns=tuple(table.column_names),
    )


DECLARED_CURVE_SCHEMA_REFS = frozenset(
    {
        REFERENCE_TENSILE_PARQUET_SCHEMA,
        REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA,
        REFERENCE_TENSILE_PAIR_CURVE_SCHEMA,
        REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA,
        NORMALIZED_PARQUET_SCHEMA,
    }
)


def known_legacy_parquet_adapter(
    schema_ref: str | None, value: bytes | None = None
) -> LegacyParquetAdapter | None:
    """Return only reviewed historical formats; never infer from arbitrary columns."""

    if schema_ref == NORMALIZED_PARQUET_SCHEMA_V1:
        return _canonical_test_data_v1_adapter(value) if value is not None else None

    if schema_ref == REFERENCE_TENSILE_PARQUET_SCHEMA_V1:
        return LegacyParquetAdapter(
            definition=reference_tensile_curve_definition(),
            channel_columns={
                "engineering_strain": "engineering_strain",
                "engineering_stress": "engineering_stress_pa",
            },
            deviation_columns={},
            source_count_columns={},
            expected_columns=("engineering_strain", "engineering_stress_pa"),
        )
    if schema_ref == REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA_V1:
        return LegacyParquetAdapter(
            definition=reference_tensile_curve_definition(value_basis=ValueBasis.DERIVED),
            channel_columns={
                "engineering_strain": "engineering_strain",
                "engineering_stress": "engineering_stress_pa",
            },
            deviation_columns={},
            source_count_columns={},
            expected_columns=("engineering_strain", "engineering_stress_pa"),
        )
    if schema_ref == REFERENCE_TENSILE_PAIR_CURVE_SCHEMA_V1:
        return LegacyParquetAdapter(
            definition=reference_tensile_pair_curve_definition(),
            channel_columns={
                "engineering_strain": "engineering_strain",
                "mean_engineering_stress_pa": "mean_engineering_stress_pa",
                "median_engineering_stress_pa": "median_engineering_stress_pa",
            },
            deviation_columns={
                "sample_standard_deviation_engineering_stress_pa": (
                    "sample_standard_deviation_engineering_stress_pa"
                ),
                "minimum_engineering_stress_pa": "minimum_engineering_stress_pa",
                "maximum_engineering_stress_pa": "maximum_engineering_stress_pa",
            },
            source_count_columns={},
            expected_columns=(
                "engineering_strain",
                "mean_engineering_stress_pa",
                "sample_standard_deviation_engineering_stress_pa",
                "median_engineering_stress_pa",
                "minimum_engineering_stress_pa",
                "maximum_engineering_stress_pa",
            ),
        )
    if schema_ref == REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA_V1:
        return LegacyParquetAdapter(
            definition=reference_tensile_replicate_curve_definition(),
            channel_columns={
                "engineering_strain": "engineering_strain",
                "mean_engineering_stress_pa": "mean_engineering_stress_pa",
                "median_engineering_stress_pa": "median_engineering_stress_pa",
            },
            deviation_columns={
                "sample_standard_deviation_engineering_stress_pa": (
                    "sample_standard_deviation_engineering_stress_pa"
                ),
                "median_absolute_deviation_engineering_stress_pa": (
                    "median_absolute_deviation_engineering_stress_pa"
                ),
                "interquartile_range_engineering_stress_pa": (
                    "interquartile_range_engineering_stress_pa"
                ),
                "coefficient_of_variation": "coefficient_of_variation",
                "minimum_engineering_stress_pa": "minimum_engineering_stress_pa",
                "maximum_engineering_stress_pa": "maximum_engineering_stress_pa",
                "mean_confidence_interval_lower_95_pa": ("mean_confidence_interval_lower_95_pa"),
                "mean_confidence_interval_upper_95_pa": ("mean_confidence_interval_upper_95_pa"),
            },
            source_count_columns={"sample_count": "sample_count"},
            expected_columns=(
                "engineering_strain",
                "sample_count",
                "mean_engineering_stress_pa",
                "sample_standard_deviation_engineering_stress_pa",
                "median_engineering_stress_pa",
                "median_absolute_deviation_engineering_stress_pa",
                "interquartile_range_engineering_stress_pa",
                "minimum_engineering_stress_pa",
                "maximum_engineering_stress_pa",
                "coefficient_of_variation",
                "mean_confidence_interval_lower_95_pa",
                "mean_confidence_interval_upper_95_pa",
            ),
        )
    if schema_ref in {
        REFERENCE_SHEAR_RELAXATION_PARQUET_SCHEMA,
        REFERENCE_SHEAR_RELAXATION_CROP_OUTPUT_SCHEMA,
    }:
        return LegacyParquetAdapter(
            definition=_shear_definition(
                ValueBasis.NORMALIZED
                if schema_ref == REFERENCE_SHEAR_RELAXATION_PARQUET_SCHEMA
                else ValueBasis.DERIVED
            ),
            channel_columns={"time_s": "time_s", "shear_modulus_pa": "shear_modulus_pa"},
            deviation_columns={},
            source_count_columns={},
            expected_columns=("time_s", "shear_modulus_pa"),
        )
    if schema_ref == VISCOELASTIC_ALIGNED_PARQUET_SCHEMA:
        definition = CurveDefinition(
            channels=(
                _common_channel(
                    "time_s",
                    "Elapsed time",
                    "time.elapsed",
                    AxisRole.INDEPENDENT,
                    DimensionId.TIME,
                    "s",
                ),
                _common_channel(
                    "shear_modulus_pa",
                    "Shear relaxation modulus",
                    "mechanics.modulus.shear.relaxation",
                    AxisRole.DEPENDENT,
                    DimensionId.FORCE_PER_AREA,
                    "Pa",
                ),
                _common_channel(
                    "temperature_k",
                    "Test temperature",
                    "temperature.test",
                    AxisRole.AUXILIARY,
                    DimensionId.TEMPERATURE,
                    "K",
                ),
                _legacy_count_channel("member_ordinal", "Selection member ordinal"),
            )
        )
        return LegacyParquetAdapter(
            definition=definition,
            channel_columns={item.key: item.key for item in definition.channels},
            deviation_columns={},
            source_count_columns={},
            expected_columns=(
                "temperature_k",
                "member_ordinal",
                "time_s",
                "shear_modulus_pa",
            ),
        )
    if schema_ref == VISCOELASTIC_STATISTICS_PARQUET_SCHEMA:
        definition = _modulus_statistics_definition(master=False)
        return LegacyParquetAdapter(
            definition=definition,
            channel_columns={item.key: item.key for item in definition.channels},
            deviation_columns={
                item.series_key: item.series_key
                for item in definition.deviations
                if item.series_key is not None
            },
            source_count_columns={"replicate_count": "replicate_count"},
            expected_columns=(
                "temperature_k",
                "time_s",
                "replicate_count",
                "mean_shear_modulus_pa",
                "sample_standard_deviation_pa",
                "median_shear_modulus_pa",
                "minimum_shear_modulus_pa",
                "maximum_shear_modulus_pa",
            ),
        )
    if schema_ref == VISCOELASTIC_MASTER_PARQUET_SCHEMA:
        definition = _modulus_statistics_definition(master=True)
        return LegacyParquetAdapter(
            definition=definition,
            channel_columns={item.key: item.key for item in definition.channels},
            deviation_columns={
                item.series_key: item.series_key
                for item in definition.deviations
                if item.series_key is not None
            },
            source_count_columns={"contributing_curve_count": "contributing_curve_count"},
            expected_columns=(
                "reduced_time_s",
                "contributing_curve_count",
                "mean_shear_modulus_pa",
                "sample_standard_deviation_pa",
                "minimum_shear_modulus_pa",
                "maximum_shear_modulus_pa",
            ),
        )
    if schema_ref == REFERENCE_HARDENING_CURVE_SCHEMA:
        return LegacyParquetAdapter(
            definition=_hardening_definition(),
            channel_columns={
                "true_plastic_strain": "true_plastic_strain",
                "true_yield_stress_pa": "true_yield_stress_pa",
            },
            deviation_columns={},
            source_count_columns={},
            expected_columns=(
                "true_plastic_strain",
                "true_yield_stress_pa",
                "point_origin",
            ),
            validate_table=_validate_hardening_table,
        )
    return None


__all__ = ["DECLARED_CURVE_SCHEMA_REFS", "known_legacy_parquet_adapter"]
