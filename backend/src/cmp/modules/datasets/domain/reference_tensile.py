"""Explicit reference tensile CSV mapping and typed Dataset revision values."""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import cast
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.modules.datasets.domain.curve_metadata import (
    CURVE_DEFINITION_PARQUET_KEY,
    CURVE_DEFINITION_SHA256_PARQUET_KEY,
    AxisRole,
    CurveChannel,
    CurveDefinition,
    OriginalUnit,
    UnitContract,
    ValueBasis,
    curve_definition_json_bytes,
)
from cmp.modules.units.domain.system import (
    DimensionId,
    QuantityReference,
    UnitError,
    convert_value,
    unit_definition,
)
from cmp.shared.domain.revisions import content_sha256

REFERENCE_TENSILE_IMPORTER_ID = "urn:cmp:datasets:reference-uniaxial-tensile-csv:1.0.0"
REFERENCE_TENSILE_IMPORTER_VERSION = "1.0.0"
REFERENCE_TENSILE_PARQUET_SCHEMA_V1 = (
    "urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0"
)
REFERENCE_TENSILE_PARQUET_SCHEMA = (
    "urn:cmp:datasets:reference-tensile-normalized-parquet:1.1.0"
)
REFERENCE_TENSILE_PARQUET_SCHEMAS = frozenset(
    {REFERENCE_TENSILE_PARQUET_SCHEMA_V1, REFERENCE_TENSILE_PARQUET_SCHEMA}
)
REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA_V1 = (
    "urn:cmp:datasets:reference-tensile-processed-parquet:1.0.0"
)
REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA = (
    "urn:cmp:datasets:reference-tensile-processed-parquet:1.1.0"
)
REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMAS = frozenset(
    {
        REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA_V1,
        REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA,
    }
)
REFERENCE_TENSILE_SCHEMA_VERSION = "1.0.0"
MAX_REFERENCE_TENSILE_POINTS = 100_000

# PyArrow exposes runtime API signatures for its table types but does not yet
# type its parquet helpers.  Keep the untyped boundary at these two calls rather
# than allowing an untyped result to leak into the Dataset domain.
_write_parquet_table = cast(Callable[..., None], pq.write_table)
_read_parquet_table = cast(Callable[..., pa.Table], pq.read_table)

class DatasetError(Exception):
    """Base error for the typed Dataset slice."""


class InvalidDatasetData(DatasetError, ValueError):
    """A Dataset request, mapping, or reference CSV is invalid."""


class DatasetNotFound(DatasetError):
    """A Dataset is absent or hidden in the tenant scope."""


class DatasetConflict(DatasetError):
    """A Dataset input conflicts with an immutable source or representation."""


class DatasetRepresentation(StrEnum):
    RAW = "raw"
    NORMALIZED = "normalized"
    PROCESSED = "processed"


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidDatasetData(f"{name} must be non-zero")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidDatasetData(f"{name} must be trimmed and contain 1..{maximum} characters")


def _unit_scale(
    unit_id: str, *, dimension: DimensionId, semantics: str, target_unit_id: str
) -> float:
    try:
        unit = unit_definition(unit_id)
        if unit.dimension is not dimension:
            raise UnitError(
                code="CMP-UNIT-0002",
                message="unit does not match the reference tensile quantity dimension",
                location="reference_tensile.mapping",
                source_dimension=unit.dimension,
                target_dimension=dimension,
            )
        return float(
            convert_value(
                "1",
                original_unit_string=unit_id,
                source=QuantityReference(dimension, semantics, unit_id),
                target=QuantityReference(dimension, semantics, target_unit_id),
                location="reference_tensile.mapping",
            ).scale
        )
    except UnitError as error:
        raise InvalidDatasetData(error.message) from error


@dataclass(frozen=True, slots=True)
class ReferenceTensileMapping:
    """User-confirmed columns and original units; no implicit detection or unit guessing."""

    strain_column: str
    stress_column: str
    strain_unit: str
    stress_unit: str

    def __post_init__(self) -> None:
        _text("strain_column", self.strain_column, 255)
        _text("stress_column", self.stress_column, 255)
        if self.strain_column == self.stress_column:
            raise InvalidDatasetData("strain and stress columns must be distinct")
        _unit_scale(
            self.strain_unit,
            dimension=DimensionId.STRAIN,
            semantics="mechanics.strain.engineering",
            target_unit_id="1",
        )
        _unit_scale(
            self.stress_unit,
            dimension=DimensionId.FORCE_PER_AREA,
            semantics="mechanics.stress.engineering",
            target_unit_id="Pa",
        )

    @property
    def digest(self) -> str:
        return content_sha256(reference_tensile_mapping_canonical(self))


@dataclass(frozen=True, slots=True)
class DatasetContent:
    """Two explicitly typed channels for one raw or normalized reference tensile revision."""

    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    data_artifact_id: UUID
    data_sha256: str
    representation: DatasetRepresentation
    source_dataset_revision_id: UUID | None
    point_count: int
    mapping: ReferenceTensileMapping
    importer_id: str = REFERENCE_TENSILE_IMPORTER_ID
    importer_version: str = REFERENCE_TENSILE_IMPORTER_VERSION
    # A processed Dataset is a new stable Dataset identity produced by a concrete Processing Run.
    # It deliberately is not an in-place revision of the normalized source Dataset.
    processing_run_id: UUID | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("test_run_id", self.test_run_id),
            ("test_run_revision_id", self.test_run_revision_id),
            ("raw_asset_id", self.raw_asset_id),
            ("raw_artifact_id", self.raw_artifact_id),
            ("data_artifact_id", self.data_artifact_id),
        ):
            _uuid(name, value)
        if self.source_dataset_revision_id is not None:
            _uuid("source_dataset_revision_id", self.source_dataset_revision_id)
        if len(self.data_sha256) != 64 or any(
            value not in "0123456789abcdef" for value in self.data_sha256
        ):
            raise InvalidDatasetData("data_sha256 must be a lowercase SHA-256 digest")
        if not 2 <= self.point_count <= MAX_REFERENCE_TENSILE_POINTS:
            raise InvalidDatasetData("reference tensile Dataset must contain 2..100000 points")
        if self.importer_id != REFERENCE_TENSILE_IMPORTER_ID:
            raise InvalidDatasetData("reference tensile importer identity is fixed")
        if self.importer_version != REFERENCE_TENSILE_IMPORTER_VERSION:
            raise InvalidDatasetData("reference tensile importer version is fixed")
        if self.representation is DatasetRepresentation.RAW:
            if self.source_dataset_revision_id is not None:
                raise InvalidDatasetData(
                    "raw Dataset revision cannot have a source Dataset revision"
                )
            if self.processing_run_id is not None:
                raise InvalidDatasetData("raw Dataset revision cannot reference a Processing Run")
            if self.data_artifact_id != self.raw_artifact_id:
                raise InvalidDatasetData("raw Dataset revision must point at its raw Artifact")
        elif self.representation is DatasetRepresentation.NORMALIZED:
            if self.source_dataset_revision_id is None:
                raise InvalidDatasetData(
                    "normalized Dataset revision requires a concrete raw revision"
                )
            if self.processing_run_id is not None:
                raise InvalidDatasetData(
                    "normalized Dataset revision cannot reference a Processing Run"
                )
            if self.data_artifact_id == self.raw_artifact_id:
                raise InvalidDatasetData(
                    "normalized Dataset requires a distinct derived Artifact"
                )
        else:
            if self.source_dataset_revision_id is None:
                raise InvalidDatasetData(
                    "processed Dataset requires a concrete normalized source revision"
                )
            if self.processing_run_id is None:
                raise InvalidDatasetData("processed Dataset requires a concrete Processing Run")
            _uuid("processing_run_id", self.processing_run_id)
            if self.data_artifact_id == self.raw_artifact_id:
                raise InvalidDatasetData("processed Dataset requires a distinct derived Artifact")

    @property
    def mapping_sha256(self) -> str:
        return self.mapping.digest


@dataclass(frozen=True, slots=True)
class CurvePoint:
    engineering_strain: float
    engineering_stress: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.engineering_strain) or not math.isfinite(
            self.engineering_stress
        ):
            raise InvalidDatasetData("curve point values must be finite")


@dataclass(frozen=True, slots=True)
class ParsedReferenceTensile:
    raw_points: tuple[CurvePoint, ...]
    normalized_points: tuple[CurvePoint, ...]

    def __post_init__(self) -> None:
        if len(self.raw_points) != len(self.normalized_points) or len(self.raw_points) < 2:
            raise InvalidDatasetData(
                "reference tensile parse must preserve at least two paired rows"
            )


def reference_tensile_mapping_canonical(value: ReferenceTensileMapping) -> dict[str, str]:
    return {
        "strain_column": value.strain_column,
        "stress_column": value.stress_column,
        "strain_unit": value.strain_unit,
        "stress_unit": value.stress_unit,
    }


def dataset_canonical(value: DatasetContent) -> dict[str, object]:
    return {
        "test_run_id": str(value.test_run_id),
        "test_run_revision_id": str(value.test_run_revision_id),
        "raw_asset_id": str(value.raw_asset_id),
        "raw_artifact_id": str(value.raw_artifact_id),
        "data_artifact_id": str(value.data_artifact_id),
        "data_sha256": value.data_sha256,
        "representation": value.representation.value,
        "source_dataset_revision_id": (
            str(value.source_dataset_revision_id)
            if value.source_dataset_revision_id is not None
            else None
        ),
        "processing_run_id": (
            str(value.processing_run_id) if value.processing_run_id is not None else None
        ),
        "point_count": value.point_count,
        "mapping": reference_tensile_mapping_canonical(value.mapping),
        "importer_id": value.importer_id,
        "importer_version": value.importer_version,
        "channels": [
            {
                "name": "engineering_strain",
                "quantity_kind": "engineering_strain",
                "original_column": value.mapping.strain_column,
                "original_unit": value.mapping.strain_unit,
                "normalized_unit": "1",
                "axis_role": "independent",
            },
            {
                "name": "engineering_stress",
                "quantity_kind": "engineering_stress",
                "original_column": value.mapping.stress_column,
                "original_unit": value.mapping.stress_unit,
                "normalized_unit": "Pa",
                "axis_role": "dependent",
            },
        ],
    }


def _numeric(row: int, name: str, value: str | None) -> float:
    if value is None or not value.strip():
        raise InvalidDatasetData(f"row {row}: {name} is missing")
    try:
        parsed = float(value.strip())
    except ValueError as error:
        raise InvalidDatasetData(f"row {row}: {name} is not a decimal number") from error
    if not math.isfinite(parsed):
        raise InvalidDatasetData(f"row {row}: {name} must be finite")
    return parsed


def parse_reference_tensile_csv(
    value: bytes, mapping: ReferenceTensileMapping
) -> ParsedReferenceTensile:
    """Parse the narrowly documented CSV shape after the user has confirmed its mapping."""

    try:
        text = value.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise InvalidDatasetData("reference tensile CSV must be UTF-8 encoded") from error
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise InvalidDatasetData("reference tensile CSV requires a header row")
    headers = tuple(item.strip() for item in reader.fieldnames)
    if mapping.strain_column not in headers or mapping.stress_column not in headers:
        raise InvalidDatasetData("approved mapping columns are absent from the CSV header")
    strain_scale = _unit_scale(
        mapping.strain_unit,
        dimension=DimensionId.STRAIN,
        semantics="mechanics.strain.engineering",
        target_unit_id="1",
    )
    stress_scale = _unit_scale(
        mapping.stress_unit,
        dimension=DimensionId.FORCE_PER_AREA,
        semantics="mechanics.stress.engineering",
        target_unit_id="Pa",
    )
    raw: list[CurvePoint] = []
    normalized: list[CurvePoint] = []
    for row_number, row in enumerate(reader, start=2):
        if all(value is None or not value.strip() for value in row.values()):
            continue
        strain = _numeric(row_number, mapping.strain_column, row.get(mapping.strain_column))
        stress = _numeric(row_number, mapping.stress_column, row.get(mapping.stress_column))
        if strain < 0.0 or stress < 0.0:
            raise InvalidDatasetData("reference tensile strain and stress must be non-negative")
        if raw and strain <= raw[-1].engineering_strain:
            raise InvalidDatasetData("reference tensile strain values must be strictly increasing")
        raw.append(CurvePoint(strain, stress))
        normalized.append(
            CurvePoint(
                strain * strain_scale,
                stress * stress_scale,
            )
        )
        if len(raw) > MAX_REFERENCE_TENSILE_POINTS:
            raise InvalidDatasetData("reference tensile CSV exceeds the 100000-point MVP limit")
    return ParsedReferenceTensile(tuple(raw), tuple(normalized))


def reference_tensile_curve_definition(
    mapping: ReferenceTensileMapping | None = None,
    *,
    value_basis: ValueBasis = ValueBasis.NORMALIZED,
) -> CurveDefinition:
    """Return the single channel authority used by Dataset, charts, and Fit previews."""

    resolved = mapping or ReferenceTensileMapping(
        strain_column="engineering_strain",
        stress_column="engineering_stress",
        strain_unit="1",
        stress_unit="Pa",
    )
    strain_scale = _unit_scale(
        resolved.strain_unit,
        dimension=DimensionId.STRAIN,
        semantics="mechanics.strain.engineering",
        target_unit_id="1",
    )
    stress_scale = _unit_scale(
        resolved.stress_unit,
        dimension=DimensionId.FORCE_PER_AREA,
        semantics="mechanics.stress.engineering",
        target_unit_id="Pa",
    )
    return CurveDefinition(
        channels=(
            CurveChannel(
                key="engineering_strain",
                label="Engineering strain",
                quantity_semantics="mechanics.strain.engineering",
                axis_role=AxisRole.INDEPENDENT,
                unit_contract=UnitContract.COMMON,
                dimension=DimensionId.STRAIN,
                original_units=(
                    OriginalUnit(resolved.strain_unit, str(strain_scale), "0"),
                ),
                normalized_unit="1",
                display_unit="1",
                display_scale="1",
                display_offset="0",
                value_basis=value_basis,
            ),
            CurveChannel(
                key="engineering_stress",
                label="Engineering stress",
                quantity_semantics="mechanics.stress.engineering",
                axis_role=AxisRole.DEPENDENT,
                unit_contract=UnitContract.COMMON,
                dimension=DimensionId.FORCE_PER_AREA,
                original_units=(
                    OriginalUnit(resolved.stress_unit, str(stress_scale), "0"),
                ),
                normalized_unit="Pa",
                display_unit="MPa",
                display_scale="0.000001",
                display_offset="0",
                value_basis=value_basis,
            ),
        )
    )


def _parquet_bytes(
    points: tuple[CurvePoint, ...],
    *,
    schema_ref: str,
    definition: CurveDefinition | None,
) -> bytes:
    """Encode normalized reference channels as a typed external Parquet Artifact."""

    if len(points) < 2:
        raise InvalidDatasetData("normalized reference Dataset requires at least two points")
    stress_column = (
        "engineering_stress"
        if schema_ref
        in {REFERENCE_TENSILE_PARQUET_SCHEMA, REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA}
        else "engineering_stress_pa"
    )
    table = pa.table(
        {
            "engineering_strain": pa.array(
                [point.engineering_strain for point in points], type=pa.float64()
            ),
            stress_column: pa.array(
                [point.engineering_stress for point in points], type=pa.float64()
            ),
        }
    )
    metadata: dict[bytes, bytes] = {b"cmp.schema": schema_ref.encode("ascii")}
    if definition is not None:
        metadata[CURVE_DEFINITION_PARQUET_KEY] = curve_definition_json_bytes(definition)
        metadata[CURVE_DEFINITION_SHA256_PARQUET_KEY] = definition.sha256.encode("ascii")
    table = table.replace_schema_metadata(metadata)
    sink = pa.BufferOutputStream()
    _write_parquet_table(
        table,
        sink,
        compression="zstd",
        version="2.6",
        data_page_version="2.0",
        use_dictionary=False,
        write_statistics=True,
    )
    return cast(bytes, sink.getvalue().to_pybytes())


def normalized_parquet_bytes(
    points: tuple[CurvePoint, ...],
    mapping: ReferenceTensileMapping | None = None,
) -> bytes:
    return _parquet_bytes(
        points,
        schema_ref=REFERENCE_TENSILE_PARQUET_SCHEMA,
        definition=reference_tensile_curve_definition(mapping),
    )


def processed_parquet_bytes(
    points: tuple[CurvePoint, ...],
    mapping: ReferenceTensileMapping | None = None,
    *,
    schema_ref: str = REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA,
) -> bytes:
    """Encode a processed reference curve without changing its typed channel semantics.

    The Artifact schema reference, Processing Recipe revision, and Processing Run carry the
    transformation meaning.  The Parquet columns intentionally remain the same two normalized
    engineering channels so a downstream reader cannot silently mistake the output for raw data.
    """

    return _parquet_bytes(
        points,
        schema_ref=schema_ref,
        definition=(
            reference_tensile_curve_definition(mapping, value_basis=ValueBasis.DERIVED)
            if schema_ref == REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA
            else None
        ),
    )


def normalized_points_from_parquet(value: bytes) -> tuple[CurvePoint, ...]:
    """Read only the two declared channels and reject a malformed derived Artifact."""

    try:
        table = _read_parquet_table(pa.BufferReader(value))
    except Exception as error:
        raise InvalidDatasetData(
            "normalized Dataset Artifact is not the reference Parquet schema"
        ) from error
    column_names = tuple(table.column_names)
    if column_names not in {
        ("engineering_strain", "engineering_stress_pa"),
        ("engineering_strain", "engineering_stress"),
    }:
        raise InvalidDatasetData("normalized Dataset Artifact channel names are invalid")
    strain = table.column("engineering_strain").to_pylist()
    stress = table.column(column_names[1]).to_pylist()
    if len(strain) != len(stress) or len(strain) < 2:
        raise InvalidDatasetData("normalized Dataset Artifact point count is invalid")
    points = tuple(CurvePoint(float(x), float(y)) for x, y in zip(strain, stress, strict=True))
    if any(
        point.engineering_strain < 0.0 or point.engineering_stress < 0.0
        for point in points
    ):
        raise InvalidDatasetData(
            "normalized Dataset Artifact contains negative reference tensile data"
        )
    if any(
        points[index].engineering_strain <= points[index - 1].engineering_strain
        for index in range(1, len(points))
    ):
        raise InvalidDatasetData(
            "normalized Dataset Artifact strain values are not strictly increasing"
        )
    return points


def preview_points(points: tuple[CurvePoint, ...], maximum_points: int) -> tuple[CurvePoint, ...]:
    """Return a deterministic evenly spaced preview without mutating source data."""

    if not 2 <= maximum_points <= 10_000:
        raise InvalidDatasetData("preview point limit must be between 2 and 10000")
    if len(points) <= maximum_points:
        return points
    last = len(points) - 1
    indexes = tuple(round(index * last / (maximum_points - 1)) for index in range(maximum_points))
    return tuple(points[index] for index in indexes)
