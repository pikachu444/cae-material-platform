"""Typed reference shear-relaxation CSV mapping and normalized curve payload."""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.shared.domain.revisions import content_sha256

REFERENCE_SHEAR_RELAXATION_IMPORTER_ID = "urn:cmp:datasets:reference-shear-relaxation-csv:1.0.0"
REFERENCE_SHEAR_RELAXATION_SCHEMA_VERSION = "1.0.0"
REFERENCE_SHEAR_RELAXATION_PARQUET_SCHEMA = (
    "urn:cmp:datasets:reference-shear-relaxation-normalized-parquet:1.0.0"
)
MAX_SHEAR_RELAXATION_POINTS = 100_000

_TIME_FACTORS = {"s": 1.0, "ms": 0.001, "min": 60.0, "h": 3600.0}
_MODULUS_FACTORS = {"Pa": 1.0, "kPa": 1_000.0, "MPa": 1_000_000.0, "GPa": 1_000_000_000.0}
_write_parquet = cast(Callable[..., None], pq.write_table)
_read_parquet = cast(Callable[..., pa.Table], pq.read_table)


class ShearRelaxationError(Exception):
    """Base error for the bounded reference shear-relaxation Dataset."""


class InvalidShearRelaxationData(ShearRelaxationError, ValueError):
    """CSV mapping or curve evidence violates the declared contract."""


class ShearRelaxationNotFound(ShearRelaxationError):
    """Dataset identity or revision is not visible."""


class ShearRelaxationConflict(ShearRelaxationError):
    """Immutable source evidence conflicts with an existing identity."""


def _text(name: str, value: str, maximum: int = 255) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidShearRelaxationData(f"{name} must contain 1..{maximum} trimmed characters")


@dataclass(frozen=True, slots=True)
class ShearRelaxationMapping:
    time_column: str
    shear_modulus_column: str
    time_unit: str
    shear_modulus_unit: str

    def __post_init__(self) -> None:
        _text("time_column", self.time_column)
        _text("shear_modulus_column", self.shear_modulus_column)
        if self.time_column == self.shear_modulus_column:
            raise InvalidShearRelaxationData("time and shear-modulus columns must be distinct")
        if self.time_unit not in _TIME_FACTORS:
            raise InvalidShearRelaxationData("time unit must be s, ms, min, or h")
        if self.shear_modulus_unit not in _MODULUS_FACTORS:
            raise InvalidShearRelaxationData("modulus unit must be Pa, kPa, MPa, or GPa")

    @property
    def digest(self) -> str:
        return content_sha256(self.canonical())

    def canonical(self) -> dict[str, str]:
        return {
            "time_column": self.time_column,
            "shear_modulus_column": self.shear_modulus_column,
            "time_unit": self.time_unit,
            "shear_modulus_unit": self.shear_modulus_unit,
        }


@dataclass(frozen=True, slots=True)
class ShearRelaxationPoint:
    time_s: float
    shear_modulus_pa: float

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.time_s)
            or self.time_s < 0
            or not math.isfinite(self.shear_modulus_pa)
            or self.shear_modulus_pa <= 0
        ):
            raise InvalidShearRelaxationData(
                "time must be finite/non-negative and shear modulus finite/positive"
            )


@dataclass(frozen=True, slots=True)
class ParsedShearRelaxation:
    raw_points: tuple[ShearRelaxationPoint, ...]
    normalized_points: tuple[ShearRelaxationPoint, ...]

    def __post_init__(self) -> None:
        if len(self.raw_points) != len(self.normalized_points) or len(self.raw_points) < 3:
            raise InvalidShearRelaxationData("shear-relaxation CSV requires at least three rows")


def _number(row: int, column: str, value: str | None) -> float:
    if value is None or not value.strip():
        raise InvalidShearRelaxationData(f"row {row}: {column} is missing")
    try:
        result = float(value.strip())
    except ValueError as error:
        raise InvalidShearRelaxationData(f"row {row}: {column} is not numeric") from error
    if not math.isfinite(result):
        raise InvalidShearRelaxationData(f"row {row}: {column} must be finite")
    return result


def parse_shear_relaxation_csv(
    value: bytes, mapping: ShearRelaxationMapping
) -> ParsedShearRelaxation:
    try:
        text = value.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise InvalidShearRelaxationData("shear-relaxation CSV must be UTF-8") from error
    reader = csv.DictReader(io.StringIO(text))
    headers = tuple(name.strip() for name in (reader.fieldnames or ()))
    if mapping.time_column not in headers or mapping.shear_modulus_column not in headers:
        raise InvalidShearRelaxationData("approved mapping columns are absent from the header")
    raw: list[ShearRelaxationPoint] = []
    normalized: list[ShearRelaxationPoint] = []
    for row_number, row in enumerate(reader, 2):
        if all(item is None or not item.strip() for item in row.values()):
            continue
        time = _number(row_number, mapping.time_column, row.get(mapping.time_column))
        modulus = _number(
            row_number, mapping.shear_modulus_column, row.get(mapping.shear_modulus_column)
        )
        raw_point = ShearRelaxationPoint(time, modulus)
        point = ShearRelaxationPoint(
            time * _TIME_FACTORS[mapping.time_unit],
            modulus * _MODULUS_FACTORS[mapping.shear_modulus_unit],
        )
        if normalized and point.time_s <= normalized[-1].time_s:
            raise InvalidShearRelaxationData("normalized time values must be strictly increasing")
        if normalized and point.shear_modulus_pa > normalized[-1].shear_modulus_pa:
            raise InvalidShearRelaxationData(
                "reference shear-relaxation modulus must be non-increasing"
            )
        raw.append(raw_point)
        normalized.append(point)
        if len(raw) > MAX_SHEAR_RELAXATION_POINTS:
            raise InvalidShearRelaxationData("CSV exceeds the 100000-point reference limit")
    return ParsedShearRelaxation(tuple(raw), tuple(normalized))


def shear_relaxation_parquet_bytes(points: tuple[ShearRelaxationPoint, ...]) -> bytes:
    if len(points) < 3:
        raise InvalidShearRelaxationData("normalized curve requires at least three points")
    table = pa.table(
        {
            "time_s": pa.array([point.time_s for point in points], type=pa.float64()),
            "shear_modulus_pa": pa.array(
                [point.shear_modulus_pa for point in points], type=pa.float64()
            ),
        }
    )
    sink = pa.BufferOutputStream()
    _write_parquet(
        table,
        sink,
        compression="zstd",
        version="2.6",
        data_page_version="2.0",
        use_dictionary=False,
        write_statistics=True,
    )
    return cast(bytes, sink.getvalue().to_pybytes())


def shear_relaxation_points_from_parquet(value: bytes) -> tuple[ShearRelaxationPoint, ...]:
    try:
        table = _read_parquet(pa.BufferReader(value), columns=["time_s", "shear_modulus_pa"])
    except Exception as error:
        raise InvalidShearRelaxationData("Artifact is not the declared Parquet schema") from error
    if tuple(table.column_names) != ("time_s", "shear_modulus_pa"):
        raise InvalidShearRelaxationData("normalized Artifact channels are invalid")
    points = tuple(
        ShearRelaxationPoint(float(time), float(modulus))
        for time, modulus in zip(
            table.column("time_s").to_pylist(),
            table.column("shear_modulus_pa").to_pylist(),
            strict=True,
        )
    )
    if len(points) < 3 or any(
        points[index].time_s <= points[index - 1].time_s
        or points[index].shear_modulus_pa > points[index - 1].shear_modulus_pa
        for index in range(1, len(points))
    ):
        raise InvalidShearRelaxationData("normalized Artifact curve invariants are invalid")
    return points


def preview_shear_relaxation_points(
    points: tuple[ShearRelaxationPoint, ...], maximum_points: int
) -> tuple[ShearRelaxationPoint, ...]:
    if not 3 <= maximum_points <= 10_000:
        raise InvalidShearRelaxationData("preview point limit must be within 3..10000")
    if len(points) <= maximum_points:
        return points
    last = len(points) - 1
    indexes = tuple(round(index * last / (maximum_points - 1)) for index in range(maximum_points))
    return tuple(points[index] for index in indexes)
