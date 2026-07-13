"""Explicit reference tensile CSV mapping, normalization, and Dataset revision values."""

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

from cmp.shared.domain.revisions import content_sha256

REFERENCE_TENSILE_IMPORTER_ID = "urn:cmp:datasets:reference-uniaxial-tensile-csv:1.0.0"
REFERENCE_TENSILE_IMPORTER_VERSION = "1.0.0"
REFERENCE_TENSILE_PARQUET_SCHEMA = "urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0"
REFERENCE_TENSILE_SCHEMA_VERSION = "1.0.0"
MAX_REFERENCE_TENSILE_POINTS = 100_000

# PyArrow exposes runtime API signatures for its table types but does not yet
# type its parquet helpers.  Keep the untyped boundary at these two calls rather
# than allowing an untyped result to leak into the Dataset domain.
_write_parquet_table = cast(Callable[..., None], pq.write_table)
_read_parquet_table = cast(Callable[..., pa.Table], pq.read_table)

_STRAIN_FACTORS = {"1": 1.0, "%": 0.01}
_STRESS_FACTORS = {"Pa": 1.0, "kPa": 1_000.0, "MPa": 1_000_000.0, "GPa": 1_000_000_000.0}


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


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidDatasetData(f"{name} must be non-zero")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidDatasetData(f"{name} must be trimmed and contain 1..{maximum} characters")


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
        if self.strain_unit not in _STRAIN_FACTORS:
            raise InvalidDatasetData("strain unit must be one of 1 or %")
        if self.stress_unit not in _STRESS_FACTORS:
            raise InvalidDatasetData("stress unit must be Pa, kPa, MPa, or GPa")

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
            if self.data_artifact_id != self.raw_artifact_id:
                raise InvalidDatasetData("raw Dataset revision must point at its raw Artifact")
        elif self.source_dataset_revision_id is None:
            raise InvalidDatasetData("normalized Dataset revision requires a concrete raw revision")
        elif self.data_artifact_id == self.raw_artifact_id:
            raise InvalidDatasetData("normalized Dataset requires a distinct derived Artifact")

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
                strain * _STRAIN_FACTORS[mapping.strain_unit],
                stress * _STRESS_FACTORS[mapping.stress_unit],
            )
        )
        if len(raw) > MAX_REFERENCE_TENSILE_POINTS:
            raise InvalidDatasetData("reference tensile CSV exceeds the 100000-point MVP limit")
    return ParsedReferenceTensile(tuple(raw), tuple(normalized))


def normalized_parquet_bytes(points: tuple[CurvePoint, ...]) -> bytes:
    """Encode normalized reference channels as a typed external Parquet Artifact."""

    if len(points) < 2:
        raise InvalidDatasetData("normalized reference Dataset requires at least two points")
    table = pa.table(
        {
            "engineering_strain": pa.array(
                [point.engineering_strain for point in points], type=pa.float64()
            ),
            "engineering_stress_pa": pa.array(
                [point.engineering_stress for point in points], type=pa.float64()
            ),
        }
    )
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


def normalized_points_from_parquet(value: bytes) -> tuple[CurvePoint, ...]:
    """Read only the two declared channels and reject a malformed derived Artifact."""

    try:
        table = _read_parquet_table(
            pa.BufferReader(value), columns=["engineering_strain", "engineering_stress_pa"]
        )
    except Exception as error:
        raise InvalidDatasetData(
            "normalized Dataset Artifact is not the reference Parquet schema"
        ) from error
    if tuple(table.column_names) != ("engineering_strain", "engineering_stress_pa"):
        raise InvalidDatasetData("normalized Dataset Artifact channel names are invalid")
    strain = table.column("engineering_strain").to_pylist()
    stress = table.column("engineering_stress_pa").to_pylist()
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
