"""Solver- and test-method-neutral canonical Test Data JSON contract (T-52).

JSON is the user exchange format.  This module validates semantic invariants before a document is
stored as immutable evidence or converted to an internal columnar representation.  It deliberately
does not infer units, quantities, missing values, or normalization transforms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from cmp.shared.domain.revisions import content_sha256

TEST_DATA_DOCUMENT_TYPE = "cmp.test-data"
TEST_DATA_SCHEMA_VERSION = "1.0.0"
TEST_DATA_SCHEMA_ID = "urn:cmp:test-data:1.0.0"
MAX_CANONICAL_JSON_BYTES = 25 * 1024 * 1024
MAX_CHANNELS = 512
MAX_POINTS = 1_000_000

_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_SEMANTICS = re.compile(r"^[a-z][a-z0-9_.-]{0,159}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CanonicalTestDataError(ValueError):
    """The canonical Test Data document is syntactically or semantically invalid."""


class ChannelAxisRole(StrEnum):
    INDEPENDENT = "independent"
    DEPENDENT = "dependent"
    AUXILIARY = "auxiliary"


def _text(name: str, value: str, maximum: int, *, optional: bool = False) -> None:
    if optional and value == "":
        return
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise CanonicalTestDataError(
            f"{name} must be trimmed and contain {1 if not optional else 0}..{maximum} characters"
        )


def _finite_decimal(name: str, value: Decimal) -> None:
    if not value.is_finite():
        raise CanonicalTestDataError(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class TestMaterialMetadata:
    maker: str
    grade: str
    lot_batch: str | None = None

    def __post_init__(self) -> None:
        _text("material.maker", self.maker, 200)
        _text("material.grade", self.grade, 200)
        if self.lot_batch is not None:
            _text("material.lot_batch", self.lot_batch, 200)


@dataclass(frozen=True, slots=True)
class TestExecutionMetadata:
    test_date: date
    operator: str
    laboratory: str
    method: str
    equipment_maker: str | None = None
    equipment_model: str | None = None

    def __post_init__(self) -> None:
        _text("test.operator", self.operator, 200)
        _text("test.laboratory", self.laboratory, 200)
        _text("test.method", self.method, 300)
        if self.equipment_maker is not None:
            _text("test.equipment_maker", self.equipment_maker, 200)
        if self.equipment_model is not None:
            _text("test.equipment_model", self.equipment_model, 200)


@dataclass(frozen=True, slots=True)
class TestSpecimenMetadata:
    specimen_id: str
    description: str | None = None

    def __post_init__(self) -> None:
        _text("specimen.specimen_id", self.specimen_id, 200)
        if self.description is not None:
            _text("specimen.description", self.description, 1000)


@dataclass(frozen=True, slots=True)
class TestCondition:
    key: str
    quantity_semantics: str
    original_value: Decimal
    original_unit_string: str
    normalized_value: Decimal
    normalized_unit: str

    def __post_init__(self) -> None:
        if _KEY.fullmatch(self.key) is None:
            raise CanonicalTestDataError("condition key is invalid")
        if _SEMANTICS.fullmatch(self.quantity_semantics) is None:
            raise CanonicalTestDataError("condition quantity_semantics is invalid")
        _text("condition.original_unit_string", self.original_unit_string, 64)
        _text("condition.normalized_unit", self.normalized_unit, 64)
        _finite_decimal("condition.original_value", self.original_value)
        _finite_decimal("condition.normalized_value", self.normalized_value)


@dataclass(frozen=True, slots=True)
class TestDataSource:
    file_name: str
    media_type: str
    sha256: str

    def __post_init__(self) -> None:
        _text("source.file_name", self.file_name, 255)
        _text("source.media_type", self.media_type, 255)
        if _SHA256.fullmatch(self.sha256) is None:
            raise CanonicalTestDataError("source.sha256 must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class TestDataChannel:
    key: str
    name: str
    quantity_semantics: str
    axis_role: ChannelAxisRole
    original_unit_string: str
    normalized_unit: str
    normalization_scale: Decimal
    normalization_offset: Decimal
    original_values: tuple[Decimal | None, ...]
    normalized_values: tuple[Decimal | None, ...]
    missing_reasons: tuple[str | None, ...]

    def __post_init__(self) -> None:
        if _KEY.fullmatch(self.key) is None:
            raise CanonicalTestDataError("channel key is invalid")
        _text("channel.name", self.name, 200)
        if _SEMANTICS.fullmatch(self.quantity_semantics) is None:
            raise CanonicalTestDataError("channel quantity_semantics is invalid")
        _text("channel.original_unit_string", self.original_unit_string, 64)
        _text("channel.normalized_unit", self.normalized_unit, 64)
        _finite_decimal("channel.normalization_scale", self.normalization_scale)
        _finite_decimal("channel.normalization_offset", self.normalization_offset)
        if self.normalization_scale == 0:
            raise CanonicalTestDataError("channel normalization scale cannot be zero")
        count = len(self.original_values)
        if not 2 <= count <= MAX_POINTS:
            raise CanonicalTestDataError("channel requires 2..1000000 points")
        if len(self.normalized_values) != count or len(self.missing_reasons) != count:
            raise CanonicalTestDataError("channel value and missing-reason arrays must align")
        for ordinal, (original, normalized, reason) in enumerate(
            zip(
                self.original_values,
                self.normalized_values,
                self.missing_reasons,
                strict=True,
            )
        ):
            if (original is None) != (normalized is None):
                raise CanonicalTestDataError(
                    f"channel {self.key} point {ordinal} must preserve missingness in both arrays"
                )
            if original is None:
                if reason is None:
                    raise CanonicalTestDataError(
                        f"channel {self.key} point {ordinal} requires a missing reason"
                    )
                _text("channel missing reason", reason, 200)
                continue
            if reason is not None:
                raise CanonicalTestDataError(
                    f"channel {self.key} point {ordinal} cannot explain a present value as missing"
                )
            _finite_decimal(f"channel {self.key} original point {ordinal}", original)
            assert normalized is not None
            _finite_decimal(f"channel {self.key} normalized point {ordinal}", normalized)
            expected = original * self.normalization_scale + self.normalization_offset
            tolerance = max(Decimal("1e-12"), abs(expected) * Decimal("1e-12"))
            if abs(normalized - expected) > tolerance:
                raise CanonicalTestDataError(
                    f"channel {self.key} point {ordinal} does not match the explicit normalization"
                )


@dataclass(frozen=True, slots=True)
class CanonicalTestDataDocument:
    document_id: str
    material: TestMaterialMetadata
    test: TestExecutionMetadata
    specimen: TestSpecimenMetadata
    conditions: tuple[TestCondition, ...]
    channels: tuple[TestDataChannel, ...]
    source: TestDataSource
    document_type: str = TEST_DATA_DOCUMENT_TYPE
    schema_version: str = TEST_DATA_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.document_type != TEST_DATA_DOCUMENT_TYPE:
            raise CanonicalTestDataError("document_type must be cmp.test-data")
        if self.schema_version != TEST_DATA_SCHEMA_VERSION:
            raise CanonicalTestDataError("unsupported cmp.test-data schema_version")
        _text("document_id", self.document_id, 200)
        if len(self.conditions) > 128:
            raise CanonicalTestDataError("a Test Data document supports at most 128 conditions")
        if len({item.key for item in self.conditions}) != len(self.conditions):
            raise CanonicalTestDataError("condition keys must be unique")
        if not 2 <= len(self.channels) <= MAX_CHANNELS:
            raise CanonicalTestDataError("a Test Data document requires 2..512 channels")
        if len({item.key for item in self.channels}) != len(self.channels):
            raise CanonicalTestDataError("channel keys must be unique")
        point_counts = {len(item.original_values) for item in self.channels}
        if len(point_counts) != 1:
            raise CanonicalTestDataError("all channel arrays must have the same point count")
        if not any(item.axis_role is ChannelAxisRole.INDEPENDENT for item in self.channels):
            raise CanonicalTestDataError("at least one independent channel is required")
        if not any(item.axis_role is ChannelAxisRole.DEPENDENT for item in self.channels):
            raise CanonicalTestDataError("at least one dependent channel is required")

    @property
    def point_count(self) -> int:
        return len(self.channels[0].original_values)

    @property
    def digest(self) -> str:
        return content_sha256(canonical_test_data(self))


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def canonical_test_data(value: CanonicalTestDataDocument) -> dict[str, Any]:
    """Return the deterministic JSON-compatible representation used for hashing/export."""

    return {
        "document_type": value.document_type,
        "schema_version": value.schema_version,
        "document_id": value.document_id,
        "material": {
            "maker": value.material.maker,
            "grade": value.material.grade,
            "lot_batch": value.material.lot_batch,
        },
        "test": {
            "date": value.test.test_date.isoformat(),
            "operator": value.test.operator,
            "laboratory": value.test.laboratory,
            "method": value.test.method,
            "equipment_maker": value.test.equipment_maker,
            "equipment_model": value.test.equipment_model,
        },
        "specimen": {
            "specimen_id": value.specimen.specimen_id,
            "description": value.specimen.description,
        },
        "conditions": [
            {
                "key": item.key,
                "quantity_semantics": item.quantity_semantics,
                "original_value": _decimal_text(item.original_value),
                "original_unit_string": item.original_unit_string,
                "normalized_value": _decimal_text(item.normalized_value),
                "normalized_unit": item.normalized_unit,
            }
            for item in value.conditions
        ],
        "channels": [
            {
                "key": item.key,
                "name": item.name,
                "quantity_semantics": item.quantity_semantics,
                "axis_role": item.axis_role.value,
                "original_unit_string": item.original_unit_string,
                "normalized_unit": item.normalized_unit,
                "normalization": {
                    "scale": _decimal_text(item.normalization_scale),
                    "offset": _decimal_text(item.normalization_offset),
                },
                "original_values": [
                    _decimal_text(point) if point is not None else None
                    for point in item.original_values
                ],
                "normalized_values": [
                    _decimal_text(point) if point is not None else None
                    for point in item.normalized_values
                ],
                "missing_reasons": list(item.missing_reasons),
            }
            for item in value.channels
        ],
        "source": {
            "file_name": value.source.file_name,
            "media_type": value.source.media_type,
            "sha256": value.source.sha256,
        },
    }
