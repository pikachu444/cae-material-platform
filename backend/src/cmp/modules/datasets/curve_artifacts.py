"""Public compatibility boundary for immutable curve Artifact bytes.

Declared 1.1+ Parquet carries its canonical curve definition and hash.  Known historical
schemas are admitted only through an explicit adapter; an unknown schema remains readable as
``metadata_state=absent`` but is never assigned guessed channels or deviation evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.modules.datasets.domain.curve_metadata import (
    CURVE_DEFINITION_PARQUET_KEY,
    CURVE_DEFINITION_SHA256_PARQUET_KEY,
    CurveContractError,
    CurveDefinition,
    CurveSeries,
    MetadataState,
    curve_definition_from_mapping,
)

_read_parquet = cast(Callable[..., pa.Table], pq.read_table)


@dataclass(frozen=True, slots=True)
class CurveArtifactResolution:
    state: MetadataState
    series: CurveSeries | None

    def __post_init__(self) -> None:
        if (self.state is MetadataState.ABSENT) != (self.series is None):
            raise ValueError("absent curve metadata must not expose inferred series")


@dataclass(frozen=True, slots=True)
class LegacyParquetAdapter:
    definition: CurveDefinition
    channel_columns: Mapping[str, str]
    deviation_columns: Mapping[str, str]
    source_count_columns: Mapping[str, str]
    expected_columns: tuple[str, ...] | None = None
    validate_table: Callable[[pa.Table], None] | None = None


def _error(code: str, location: str, message: str) -> CurveContractError:
    return CurveContractError(code=code, location=location, message=message)


def _table(value: bytes) -> pa.Table:
    try:
        return _read_parquet(pa.BufferReader(value))
    except Exception as error:
        raise _error(
            "CMP-CURVE-0032", "artifact.bytes", "known curve Artifact is not readable Parquet"
        ) from error


def _float_columns(
    table: pa.Table, columns: Mapping[str, str], location: str
) -> dict[str, tuple[float | None, ...]]:
    result: dict[str, tuple[float | None, ...]] = {}
    for logical_key, physical_key in columns.items():
        if physical_key not in table.column_names:
            raise _error(
                "CMP-CURVE-0033",
                f"{location}.{logical_key}",
                f"declared series column is absent: {physical_key}",
            )
        try:
            values = tuple(
                float(item) if item is not None else None
                for item in table.column(physical_key).to_pylist()
            )
        except (TypeError, ValueError) as error:
            raise _error(
                "CMP-CURVE-0033",
                f"{location}.{logical_key}",
                "declared series column is not numeric",
            ) from error
        result[logical_key] = values
    return result


def _count_columns(table: pa.Table, columns: Mapping[str, str]) -> dict[str, tuple[int, ...]]:
    result: dict[str, tuple[int, ...]] = {}
    for logical_key, physical_key in columns.items():
        if physical_key not in table.column_names:
            raise _error(
                "CMP-CURVE-0033",
                f"series.source_counts.{logical_key}",
                f"declared source-count column is absent: {physical_key}",
            )
        raw = table.column(physical_key).to_pylist()
        if any(not isinstance(item, int) or isinstance(item, bool) for item in raw):
            raise _error(
                "CMP-CURVE-0033",
                f"series.source_counts.{logical_key}",
                "declared source-count column is not integral",
            )
        result[logical_key] = tuple(raw)
    return result


def _declared_resolution(table: pa.Table, *, schema_ref: str | None) -> CurveArtifactResolution:
    metadata = table.schema.metadata or {}
    definition_bytes = metadata.get(CURVE_DEFINITION_PARQUET_KEY)
    definition_sha = metadata.get(CURVE_DEFINITION_SHA256_PARQUET_KEY)
    if definition_bytes is None or definition_sha is None:
        raise _error(
            "CMP-CURVE-0034",
            "artifact.parquet_metadata",
            "declared curve Artifact is missing its definition or definition digest",
        )
    stored_schema = metadata.get(b"cmp.schema")
    if schema_ref is not None and stored_schema != schema_ref.encode("utf-8"):
        raise _error(
            "CMP-CURVE-0035",
            "artifact.schema_ref",
            "Parquet schema reference differs from the immutable Artifact manifest",
        )
    try:
        raw_definition = json.loads(definition_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _error(
            "CMP-CURVE-0034",
            "artifact.parquet_metadata.definition",
            "curve definition metadata is not canonical UTF-8 JSON",
        ) from error
    definition = curve_definition_from_mapping(raw_definition)
    try:
        decoded_sha = definition_sha.decode("ascii")
    except UnicodeDecodeError as error:
        raise _error(
            "CMP-CURVE-0034",
            "artifact.parquet_metadata.definition_sha256",
            "curve definition digest is not ASCII",
        ) from error
    if decoded_sha != definition.sha256:
        raise _error(
            "CMP-CURVE-0036",
            "artifact.parquet_metadata.definition_sha256",
            "curve definition digest does not match its canonical metadata",
        )
    channel_columns = {item.key: item.key for item in definition.channels}
    deviation_columns = {
        item.series_key: item.series_key
        for item in definition.deviations
        if item.series_key is not None
    }
    count_columns = {
        item.source_count_series_key: item.source_count_series_key
        for item in definition.deviations
        if item.source_count_series_key is not None
    }
    return CurveArtifactResolution(
        MetadataState.DECLARED,
        CurveSeries(
            definition=definition,
            channels=_float_columns(table, channel_columns, "series.channels"),
            deviations=_float_columns(table, deviation_columns, "series.deviations"),
            source_counts=_count_columns(table, count_columns),
        ),
    )


def resolve_curve_artifact(
    value: bytes,
    *,
    schema_ref: str | None,
    expected_sha256: str,
    legacy_adapter: LegacyParquetAdapter | None = None,
    declared_required: bool = False,
) -> CurveArtifactResolution:
    """Validate digest and full arrays before returning any sampleable curve values."""

    if hashlib.sha256(value).hexdigest() != expected_sha256:
        raise _error(
            "CMP-CURVE-0037",
            "artifact.sha256",
            "curve Artifact bytes differ from the exact immutable digest",
        )
    if legacy_adapter is None and not declared_required:
        return CurveArtifactResolution(MetadataState.ABSENT, None)
    table = _table(value)
    metadata = table.schema.metadata or {}
    has_definition = CURVE_DEFINITION_PARQUET_KEY in metadata
    has_definition_sha = CURVE_DEFINITION_SHA256_PARQUET_KEY in metadata
    if has_definition or has_definition_sha:
        if not (has_definition and has_definition_sha):
            raise _error(
                "CMP-CURVE-0034",
                "artifact.parquet_metadata",
                "curve definition and digest metadata must be present together",
            )
        return _declared_resolution(table, schema_ref=schema_ref)
    if declared_required:
        raise _error(
            "CMP-CURVE-0034",
            "artifact.parquet_metadata",
            "this curve schema requires declared metadata",
        )
    if legacy_adapter is None:
        return CurveArtifactResolution(MetadataState.ABSENT, None)
    if (
        legacy_adapter.expected_columns is not None
        and tuple(table.column_names) != legacy_adapter.expected_columns
    ):
        raise _error(
            "CMP-CURVE-0033",
            "artifact.parquet_columns",
            "known legacy curve Artifact columns differ from the reviewed schema",
        )
    if legacy_adapter.validate_table is not None:
        legacy_adapter.validate_table(table)
    return CurveArtifactResolution(
        MetadataState.LEGACY_COMPATIBLE,
        CurveSeries(
            definition=legacy_adapter.definition,
            channels=_float_columns(
                table, legacy_adapter.channel_columns, "series.channels"
            ),
            deviations=_float_columns(
                table, legacy_adapter.deviation_columns, "series.deviations"
            ),
            source_counts=_count_columns(table, legacy_adapter.source_count_columns),
        ),
    )


def sample_curve_series(
    series: CurveSeries, maximum_points: int
) -> tuple[
    tuple[int, ...],
    dict[str, tuple[float | None, ...]],
    dict[str, tuple[float | None, ...]],
    dict[str, tuple[int, ...]],
]:
    indices = series.sample_indices(maximum_points)
    return (
        indices,
        {key: tuple(values[index] for index in indices) for key, values in series.channels.items()},
        {
            key: tuple(values[index] for index in indices)
            for key, values in series.deviations.items()
        },
        {
            key: tuple(values[index] for index in indices)
            for key, values in series.source_counts.items()
        },
    )


__all__ = [
    "CurveArtifactResolution",
    "LegacyParquetAdapter",
    "resolve_curve_artifact",
    "sample_curve_series",
]
