from __future__ import annotations

import hashlib
from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from cmp.curve_artifact_registry import known_legacy_parquet_adapter
from cmp.modules.datasets.application.canonical_test_data import NORMALIZED_PARQUET_SCHEMA_V1
from cmp.modules.datasets.curve_artifacts import CurveArtifactResolution, resolve_curve_artifact
from cmp.modules.datasets.domain.curve_metadata import (
    AxisRole,
    CurveContractError,
    MetadataState,
    UnitContract,
)
from cmp.modules.datasets.domain.reference_shear_relaxation import (
    REFERENCE_SHEAR_RELAXATION_PARQUET_SCHEMA,
    ShearRelaxationPoint,
    shear_relaxation_parquet_bytes,
)
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    REFERENCE_HARDENING_CURVE_SCHEMA,
    HardeningCurvePoint,
    HardeningPointOrigin,
    hardening_curve_parquet_bytes,
)
from cmp.modules.processing.domain.viscoelastic_master_curve import (
    VISCOELASTIC_MASTER_PARQUET_SCHEMA,
)


def _resolve(value: bytes, schema_ref: str) -> CurveArtifactResolution:
    return resolve_curve_artifact(
        value,
        schema_ref=schema_ref,
        expected_sha256=hashlib.sha256(value).hexdigest(),
        legacy_adapter=known_legacy_parquet_adapter(schema_ref, value),
    )


def _parquet(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    pq.write_table(  # type: ignore[no-untyped-call]
        table, sink, compression="zstd", use_dictionary=False
    )
    return cast(bytes, sink.getvalue().to_pybytes())


def test_reviewed_shear_relaxation_adapter_preserves_stored_channels() -> None:
    value = shear_relaxation_parquet_bytes(
        (
            ShearRelaxationPoint(0.0, 3_000_000.0),
            ShearRelaxationPoint(1.0, 2_000_000.0),
            ShearRelaxationPoint(2.0, 1_000_000.0),
        )
    )

    resolution = _resolve(value, REFERENCE_SHEAR_RELAXATION_PARQUET_SCHEMA)

    assert resolution.state is MetadataState.LEGACY_COMPATIBLE
    assert resolution.series is not None
    assert resolution.series.channels["time_s"] == (0.0, 1.0, 2.0)
    assert resolution.series.definition.deviations == ()


def test_reviewed_canonical_test_data_adapter_uses_stored_semantics_and_units() -> None:
    value = _parquet(
        pa.table(
            {
                "frequency": [1.0, 10.0],
                "storage": [3_000_000.0, 2_500_000.0],
                "loss": [300_000.0, 350_000.0],
            }
        ).replace_schema_metadata(
            {
                b"cmp.schema": NORMALIZED_PARQUET_SCHEMA_V1.encode("ascii"),
                b"cmp.channel.frequency.quantity_semantics": b"frequency.cyclic",
                b"cmp.channel.frequency.normalized_unit": b"Hz",
                b"cmp.channel.storage.quantity_semantics": b"modulus.shear.storage",
                b"cmp.channel.storage.normalized_unit": b"Pa",
                b"cmp.channel.loss.quantity_semantics": b"modulus.shear.loss",
                b"cmp.channel.loss.normalized_unit": b"Pa",
            }
        )
    )

    resolution = _resolve(value, NORMALIZED_PARQUET_SCHEMA_V1)

    assert resolution.state is MetadataState.LEGACY_COMPATIBLE
    assert resolution.series is not None
    channels = {item.key: item for item in resolution.series.definition.channels}
    assert channels["frequency"].axis_role is AxisRole.INDEPENDENT
    assert channels["frequency"].unit_contract is UnitContract.EXPLICIT_LEGACY
    assert channels["frequency"].normalized_unit == "Hz"
    assert channels["storage"].axis_role is AxisRole.DEPENDENT
    assert resolution.series.channels["loss"] == (300_000.0, 350_000.0)


def test_unreviewed_canonical_channel_remains_absent_for_catalog_use() -> None:
    value = _parquet(
        pa.table({"x": [1.0, 2.0], "y": [3.0, 4.0]}).replace_schema_metadata(
            {
                b"cmp.schema": NORMALIZED_PARQUET_SCHEMA_V1.encode("ascii"),
                b"cmp.channel.x.quantity_semantics": b"custom.unreviewed.x",
                b"cmp.channel.x.normalized_unit": b"1",
                b"cmp.channel.y.quantity_semantics": b"custom.unreviewed.y",
                b"cmp.channel.y.normalized_unit": b"1",
            }
        )
    )

    resolution = _resolve(value, NORMALIZED_PARQUET_SCHEMA_V1)

    assert resolution.state is MetadataState.ABSENT
    assert resolution.series is None


def test_reviewed_master_curve_adapter_preserves_sd_range_and_counts() -> None:
    value = _parquet(
        pa.table(
            {
                "reduced_time_s": pa.array([0.1, 1.0], type=pa.float64()),
                "contributing_curve_count": pa.array([3, 3], type=pa.int32()),
                "mean_shear_modulus_pa": pa.array([3_000_000.0, 2_000_000.0]),
                "sample_standard_deviation_pa": pa.array([100_000.0, 80_000.0]),
                "minimum_shear_modulus_pa": pa.array([2_800_000.0, 1_850_000.0]),
                "maximum_shear_modulus_pa": pa.array([3_200_000.0, 2_150_000.0]),
            }
        )
    )

    resolution = _resolve(value, VISCOELASTIC_MASTER_PARQUET_SCHEMA)

    assert resolution.series is not None
    assert resolution.series.source_counts["contributing_curve_count"] == (3, 3)
    assert resolution.series.deviations["sample_standard_deviation_pa"] == (
        100_000.0,
        80_000.0,
    )


def test_reviewed_hardening_adapter_checks_non_numeric_origin_evidence() -> None:
    value = hardening_curve_parquet_bytes(
        (
            HardeningCurvePoint(
                0.0,
                400_000_000.0,
                HardeningPointOrigin.CATALOG_YIELD_ANCHOR,
            ),
            HardeningCurvePoint(
                0.1,
                500_000_000.0,
                HardeningPointOrigin.PRE_NECKING_OBSERVATION,
            ),
            HardeningCurvePoint(
                0.2,
                500_000_000.0,
                HardeningPointOrigin.APPROVED_CONSTANT_EXTENSION,
            ),
        )
    )

    resolution = _resolve(value, REFERENCE_HARDENING_CURVE_SCHEMA)

    assert resolution.series is not None
    assert resolution.series.channels["true_plastic_strain"] == (0.0, 0.1, 0.2)


def test_known_schema_rejects_structural_corruption_instead_of_hiding_it() -> None:
    value = _parquet(
        pa.table(
            {
                "reduced_time_s": [0.1, 1.0],
                "mean_shear_modulus_pa": [3_000_000.0, 2_000_000.0],
            }
        )
    )

    with pytest.raises(CurveContractError, match="columns differ") as captured:
        _resolve(value, VISCOELASTIC_MASTER_PARQUET_SCHEMA)
    assert captured.value.code == "CMP-CURVE-0033"


def test_unknown_historical_schema_remains_honestly_absent_without_parsing() -> None:
    value = b"historical opaque bytes"
    resolution = resolve_curve_artifact(
        value,
        schema_ref="urn:cmp:datasets:unreviewed-curve:1.0.0",
        expected_sha256=hashlib.sha256(value).hexdigest(),
    )

    assert resolution.state is MetadataState.ABSENT
    assert resolution.series is None
