"""Versioned curve-channel meaning, deviation evidence, and immutable bindings.

The definition is deliberately independent from the Artifact/revision envelope.  It can be
hashed and embedded in immutable columnar bytes without creating a digest cycle.  Public API
responses bind that definition to the exact owning revision, Artifact, inputs, and calculation
provenance through :class:`CurveMetadata`.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final
from uuid import UUID

from cmp.modules.units.domain.system import (
    DimensionId,
    QuantityReference,
    UnitError,
    convert_value,
    decimal_text,
    dimension_for_quantity_semantics,
    parse_decimal,
    unit_definition,
)
from cmp.shared.domain.revisions import content_sha256

CURVE_METADATA_CONTRACT_VERSION: Final = "1.0.0"
CURVE_DEFINITION_VERSION: Final = "1.0.0"
CURVE_DEFINITION_SCHEMA_REF: Final = "urn:cmp:datasets:curve-channel-metadata:1.0.0"
CURVE_DEFINITION_PARQUET_KEY: Final = b"cmp.curve_definition"
CURVE_DEFINITION_SHA256_PARQUET_KEY: Final = b"cmp.curve_definition_sha256"

_KEY = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_SEMANTICS = re.compile(r"^[a-z][a-z0-9_.-]{0,159}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CurveContractError(ValueError):
    """Stable structured failure for contract, adapter, and API boundaries."""

    def __init__(self, *, code: str, location: str, message: str) -> None:
        self.code = code
        self.location = location
        self.message = message
        super().__init__(message)

    def detail(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "message": self.message}


class MetadataState(StrEnum):
    DECLARED = "declared"
    LEGACY_COMPATIBLE = "legacy_compatible"
    ABSENT = "absent"


class AxisRole(StrEnum):
    INDEPENDENT = "independent"
    DEPENDENT = "dependent"
    AUXILIARY = "auxiliary"


class UnitContract(StrEnum):
    COMMON = "common"
    EXPLICIT_LEGACY = "explicit_legacy"


class ValueBasis(StrEnum):
    ORIGINAL = "original"
    NORMALIZED = "normalized"
    DERIVED = "derived"


class DeviationScope(StrEnum):
    CHANNEL_SCALAR = "channel_scalar"
    POINTWISE = "pointwise"


class DeviationKind(StrEnum):
    STANDARD_DEVIATION = "standard_deviation"
    STANDARD_ERROR = "standard_error"
    CONFIDENCE_BOUND = "confidence_bound"
    PREDICTION_BOUND = "prediction_bound"
    TOLERANCE_BOUND = "tolerance_bound"
    QUANTILE = "quantile"
    MEDIAN_ABSOLUTE_DEVIATION = "median_absolute_deviation"
    INTERQUARTILE_RANGE = "interquartile_range"
    RANGE_BOUND = "range_bound"
    COEFFICIENT_OF_VARIATION = "coefficient_of_variation"


class BoundDirection(StrEnum):
    NONE = "none"
    LOWER = "lower"
    UPPER = "upper"


class Coverage(StrEnum):
    POINTWISE = "pointwise"
    SIMULTANEOUS = "simultaneous"


class ProvenanceKind(StrEnum):
    INPUT_USAGE = "input_usage"
    GENERATION_ACTIVITY = "generation_activity"
    CALCULATION_PLAN = "calculation_plan"
    CALCULATION_RUN = "calculation_run"
    CALCULATION_RESULT = "calculation_result"


def _contract_error(code: str, location: str, message: str) -> CurveContractError:
    return CurveContractError(code=code, location=location, message=message)


def _key(value: str, location: str) -> None:
    if not _KEY.fullmatch(value):
        raise _contract_error(
            "CMP-CURVE-0001", location, "value must be a stable lower-case key"
        )


def _text(value: str, location: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise _contract_error(
            "CMP-CURVE-0002", location, f"value must be trimmed and contain 1..{maximum} characters"
        )


def _decimal(value: str, location: str) -> Decimal:
    try:
        return parse_decimal(value, location=location)
    except UnitError as error:
        raise _contract_error(error.code, error.location, error.message) from error


def _uuid(value: UUID, location: str) -> None:
    if value.int == 0:
        raise _contract_error("CMP-CURVE-0003", location, "UUID must be non-zero")


def _sha256(value: str, location: str) -> None:
    if not _SHA256.fullmatch(value):
        raise _contract_error(
            "CMP-CURVE-0004", location, "value must be a lowercase SHA-256 digest"
        )


@dataclass(frozen=True, slots=True)
class OriginalUnit:
    unit: str
    scale_to_normalized: str
    offset_to_normalized: str = "0"

    def __post_init__(self) -> None:
        _text(self.unit, "original_units[].unit", 80)
        if _decimal(self.scale_to_normalized, "original_units[].scale_to_normalized") == 0:
            raise _contract_error(
                "CMP-CURVE-0007",
                "original_units[].scale_to_normalized",
                "normalization scale must be non-zero",
            )
        _decimal(self.offset_to_normalized, "original_units[].offset_to_normalized")


@dataclass(frozen=True, slots=True)
class CurveChannel:
    key: str
    label: str
    quantity_semantics: str
    axis_role: AxisRole
    unit_contract: UnitContract
    dimension: DimensionId | None
    original_units: tuple[OriginalUnit, ...]
    normalized_unit: str
    display_unit: str
    display_scale: str
    display_offset: str
    value_basis: ValueBasis

    def __post_init__(self) -> None:
        _key(self.key, f"channels.{self.key}.key")
        _text(self.label, f"channels.{self.key}.label", 200)
        if not _SEMANTICS.fullmatch(self.quantity_semantics):
            raise _contract_error(
                "CMP-CURVE-0001",
                f"channels.{self.key}.quantity_semantics",
                "quantity semantics must be a stable lower-case identifier",
            )
        if not 1 <= len(self.original_units) <= 64:
            raise _contract_error(
                "CMP-CURVE-0005",
                f"channels.{self.key}.original_units",
                "one to 64 original units are required",
            )
        original_names = [item.unit for item in self.original_units]
        if len(original_names) != len(set(original_names)):
            raise _contract_error(
                "CMP-CURVE-0006",
                f"channels.{self.key}.original_units",
                "original unit identifiers must be unique",
            )
        _text(self.normalized_unit, f"channels.{self.key}.normalized_unit", 80)
        _text(self.display_unit, f"channels.{self.key}.display_unit", 80)
        display_scale = _decimal(
            self.display_scale, f"channels.{self.key}.display_scale"
        )
        display_offset = _decimal(
            self.display_offset, f"channels.{self.key}.display_offset"
        )
        if display_scale == 0:
            raise _contract_error(
                "CMP-CURVE-0007",
                f"channels.{self.key}.display_scale",
                "display scale must be non-zero",
            )
        if self.unit_contract is UnitContract.EXPLICIT_LEGACY:
            if self.dimension is not None:
                raise _contract_error(
                    "CMP-CURVE-0008",
                    f"channels.{self.key}.dimension",
                    "explicit legacy units must not claim a common registry dimension",
                )
            return
        if self.dimension is None:
            raise _contract_error(
                "CMP-CURVE-0008",
                f"channels.{self.key}.dimension",
                "common unit channels require a dimension",
            )
        try:
            semantic_dimension = dimension_for_quantity_semantics(
                self.quantity_semantics,
                location=f"channels.{self.key}.quantity_semantics",
            )
            if semantic_dimension is not self.dimension:
                raise _contract_error(
                    "CMP-CURVE-0009",
                    f"channels.{self.key}.dimension",
                    "quantity semantics and declared dimension do not match",
                )
            normalized = unit_definition(
                self.normalized_unit, location=f"channels.{self.key}.normalized_unit"
            )
            display = unit_definition(
                self.display_unit, location=f"channels.{self.key}.display_unit"
            )
            if (
                normalized.dimension is not self.dimension
                or display.dimension is not self.dimension
            ):
                raise _contract_error(
                    "CMP-CURVE-0010",
                    f"channels.{self.key}.normalized_unit",
                    "normalized/display units must match the channel dimension",
                )
            for index, original in enumerate(self.original_units):
                result = convert_value(
                    "0",
                    original_unit_string=original.unit,
                    source=QuantityReference(
                        self.dimension, self.quantity_semantics, original.unit
                    ),
                    target=QuantityReference(
                        self.dimension, self.quantity_semantics, self.normalized_unit
                    ),
                    location=f"channels.{self.key}.original_units[{index}]",
                )
                if (
                    _decimal(
                        original.scale_to_normalized,
                        f"channels.{self.key}.original_units[{index}].scale_to_normalized",
                    )
                    != result.scale
                    or _decimal(
                        original.offset_to_normalized,
                        f"channels.{self.key}.original_units[{index}].offset_to_normalized",
                    )
                    != result.offset
                ):
                    raise _contract_error(
                        "CMP-CURVE-0011",
                        f"channels.{self.key}.original_units[{index}]",
                        "stored scale/offset does not match the exact common unit conversion",
                    )
            display_result = convert_value(
                "0",
                original_unit_string=self.normalized_unit,
                source=QuantityReference(
                    self.dimension, self.quantity_semantics, self.normalized_unit
                ),
                target=QuantityReference(
                    self.dimension, self.quantity_semantics, self.display_unit
                ),
                location=f"channels.{self.key}.display",
            )
            if display_scale != display_result.scale or display_offset != display_result.offset:
                raise _contract_error(
                    "CMP-CURVE-0011",
                    f"channels.{self.key}.display",
                    "stored display scale/offset does not match the exact common unit conversion",
                )
        except UnitError as error:
            raise _contract_error(error.code, error.location, error.message) from error


_CONFIDENCE_KINDS: Final = frozenset(
    {
        DeviationKind.CONFIDENCE_BOUND,
        DeviationKind.PREDICTION_BOUND,
        DeviationKind.TOLERANCE_BOUND,
    }
)
_DDOF_KINDS: Final = frozenset(
    {
        DeviationKind.STANDARD_DEVIATION,
        DeviationKind.STANDARD_ERROR,
        DeviationKind.CONFIDENCE_BOUND,
        DeviationKind.COEFFICIENT_OF_VARIATION,
    }
)


@dataclass(frozen=True, slots=True)
class CurveDeviation:
    key: str
    target_channel_key: str
    scope: DeviationScope
    kind: DeviationKind
    method_id: str
    method_version: str
    unit: str
    bound_direction: BoundDirection = BoundDirection.NONE
    band_group: str | None = None
    scalar_value: str | None = None
    series_key: str | None = None
    source_count: int | None = None
    source_count_series_key: str | None = None
    confidence_level: float | None = None
    coverage: Coverage | None = None
    ddof: int | None = None
    quantile_probability: float | None = None
    quantile_method: str | None = None

    def __post_init__(self) -> None:
        _key(self.key, f"deviations.{self.key}.key")
        _key(
            self.target_channel_key,
            f"deviations.{self.key}.target_channel_key",
        )
        _key(self.method_id, f"deviations.{self.key}.method_id")
        _text(self.method_version, f"deviations.{self.key}.method_version", 64)
        _text(self.unit, f"deviations.{self.key}.unit", 80)
        if self.scope is DeviationScope.CHANNEL_SCALAR:
            if self.scalar_value is None or self.series_key is not None:
                raise _contract_error(
                    "CMP-CURVE-0012",
                    f"deviations.{self.key}",
                    "channel_scalar requires scalar_value and forbids series_key",
                )
            _decimal(self.scalar_value, f"deviations.{self.key}.scalar_value")
            if self.source_count_series_key is not None:
                raise _contract_error(
                    "CMP-CURVE-0013",
                    f"deviations.{self.key}.source_count_series_key",
                    "scalar deviation cannot reference pointwise source counts",
                )
        else:
            if self.scalar_value is not None or self.series_key is None:
                raise _contract_error(
                    "CMP-CURVE-0012",
                    f"deviations.{self.key}",
                    "pointwise deviation requires series_key and forbids scalar_value",
                )
            _key(self.series_key, f"deviations.{self.key}.series_key")
        if self.source_count is not None and self.source_count < 1:
            raise _contract_error(
                "CMP-CURVE-0013",
                f"deviations.{self.key}.source_count",
                "source count must be positive",
            )
        if self.source_count_series_key is not None:
            _key(
                self.source_count_series_key,
                f"deviations.{self.key}.source_count_series_key",
            )
        if (self.source_count is None) == (self.source_count_series_key is None):
            raise _contract_error(
                "CMP-CURVE-0013",
                f"deviations.{self.key}",
                "exactly one scalar or pointwise source-count declaration is required",
            )
        if self.kind in _CONFIDENCE_KINDS:
            if (
                self.confidence_level is None
                or not 0 < self.confidence_level < 1
                or self.coverage is None
                or self.bound_direction is BoundDirection.NONE
                or self.band_group is None
            ):
                raise _contract_error(
                    "CMP-CURVE-0014",
                    f"deviations.{self.key}",
                    "confidence/prediction/tolerance bounds require level, coverage, "
                    "direction, and band group",
                )
        elif self.confidence_level is not None or self.coverage is not None:
            raise _contract_error(
                "CMP-CURVE-0014",
                f"deviations.{self.key}",
                "confidence level and coverage are not applicable to this deviation kind",
            )
        if self.kind is DeviationKind.QUANTILE:
            if (
                self.quantile_probability is None
                or not 0 <= self.quantile_probability <= 1
                or self.quantile_method is None
            ):
                raise _contract_error(
                    "CMP-CURVE-0015",
                    f"deviations.{self.key}",
                    "quantile requires probability and method",
                )
            _text(
                self.quantile_method,
                f"deviations.{self.key}.quantile_method",
                100,
            )
        elif self.quantile_probability is not None or self.quantile_method is not None:
            raise _contract_error(
                "CMP-CURVE-0015",
                f"deviations.{self.key}",
                "quantile probability and method are not applicable to this deviation kind",
            )
        if self.ddof is not None and (self.kind not in _DDOF_KINDS or self.ddof < 0):
            raise _contract_error(
                "CMP-CURVE-0016",
                f"deviations.{self.key}.ddof",
                "ddof is invalid or not applicable to this deviation kind",
            )
        if self.bound_direction is BoundDirection.NONE:
            if self.band_group is not None:
                raise _contract_error(
                    "CMP-CURVE-0017",
                    f"deviations.{self.key}.band_group",
                    "a non-bound deviation cannot declare a band group",
                )
        elif self.band_group is None:
            raise _contract_error(
                "CMP-CURVE-0017",
                f"deviations.{self.key}.band_group",
                "a bound direction requires a band group",
            )
        elif self.band_group is not None:
            _key(self.band_group, f"deviations.{self.key}.band_group")


@dataclass(frozen=True, slots=True)
class CurveDefinition:
    channels: tuple[CurveChannel, ...]
    deviations: tuple[CurveDeviation, ...] = ()
    definition_version: str = CURVE_DEFINITION_VERSION

    def __post_init__(self) -> None:
        if self.definition_version != CURVE_DEFINITION_VERSION:
            raise _contract_error(
                "CMP-CURVE-0018",
                "definition_version",
                f"only {CURVE_DEFINITION_VERSION} is supported",
            )
        if not 2 <= len(self.channels) <= 512:
            raise _contract_error(
                "CMP-CURVE-0019", "channels", "two to 512 channels are required"
            )
        channel_by_key = {channel.key: channel for channel in self.channels}
        if len(channel_by_key) != len(self.channels):
            raise _contract_error(
                "CMP-CURVE-0020", "channels", "channel keys must be unique"
            )
        independent = [
            channel for channel in self.channels if channel.axis_role is AxisRole.INDEPENDENT
        ]
        dependent = [
            channel for channel in self.channels if channel.axis_role is AxisRole.DEPENDENT
        ]
        if not independent or not dependent:
            raise _contract_error(
                "CMP-CURVE-0021",
                "channels.axis_role",
                "a curve requires at least one independent and one dependent channel",
            )
        deviation_by_key = {item.key: item for item in self.deviations}
        if len(deviation_by_key) != len(self.deviations):
            raise _contract_error(
                "CMP-CURVE-0020", "deviations", "deviation keys must be unique"
            )
        pointwise_series_keys = [
            item.series_key for item in self.deviations if item.series_key is not None
        ]
        if len(pointwise_series_keys) != len(set(pointwise_series_keys)):
            raise _contract_error(
                "CMP-CURVE-0020",
                "deviations.series_key",
                "pointwise deviation series keys must be unique",
            )
        for deviation in self.deviations:
            target = channel_by_key.get(deviation.target_channel_key)
            if target is None:
                raise _contract_error(
                    "CMP-CURVE-0022",
                    f"deviations.{deviation.key}.target_channel_key",
                    "deviation target does not reference a channel",
                )
            if target.axis_role is AxisRole.INDEPENDENT:
                raise _contract_error(
                    "CMP-CURVE-0022",
                    f"deviations.{deviation.key}.target_channel_key",
                    "deviation target must be dependent or auxiliary",
                )
            if target.unit_contract is UnitContract.COMMON:
                if deviation.kind is DeviationKind.COEFFICIENT_OF_VARIATION:
                    if deviation.unit != "1":
                        raise _contract_error(
                            "CMP-CURVE-0023",
                            f"deviations.{deviation.key}.unit",
                            "coefficient of variation must use the explicit unit 1",
                        )
                    continue
                try:
                    deviation_unit = unit_definition(
                        deviation.unit, location=f"deviations.{deviation.key}.unit"
                    )
                except UnitError as error:
                    raise _contract_error(error.code, error.location, error.message) from error
                if deviation_unit.dimension is not target.dimension:
                    raise _contract_error(
                        "CMP-CURVE-0023",
                        f"deviations.{deviation.key}.unit",
                        "deviation unit dimension differs from its target channel",
                    )
        band_groups: dict[str, list[CurveDeviation]] = {}
        for deviation in self.deviations:
            if deviation.band_group is not None:
                band_groups.setdefault(deviation.band_group, []).append(deviation)
        for group, members in band_groups.items():
            if len(members) != 2 or {item.bound_direction for item in members} != {
                BoundDirection.LOWER,
                BoundDirection.UPPER,
            }:
                raise _contract_error(
                    "CMP-CURVE-0024",
                    f"deviations.band_group.{group}",
                    "a displayable band requires exactly one lower and one upper bound",
                )
            first, second = members
            comparable = (
                "target_channel_key",
                "scope",
                "kind",
                "method_id",
                "method_version",
                "unit",
                "source_count",
                "source_count_series_key",
                "confidence_level",
                "coverage",
                "ddof",
                "quantile_method",
            )
            if any(getattr(first, name) != getattr(second, name) for name in comparable):
                raise _contract_error(
                    "CMP-CURVE-0024",
                    f"deviations.band_group.{group}",
                    "band bounds must share target, scope, method, unit, and sampling evidence",
                )

    @property
    def sha256(self) -> str:
        return content_sha256(curve_definition_canonical(self))


@dataclass(frozen=True, slots=True)
class CurveSeries:
    """Full, same-index curve arrays validated before any bounded preview sampling."""

    definition: CurveDefinition
    channels: dict[str, tuple[float | None, ...]]
    deviations: dict[str, tuple[float | None, ...]]
    source_counts: dict[str, tuple[int, ...]]

    def __post_init__(self) -> None:
        expected_channels = {item.key for item in self.definition.channels}
        if set(self.channels) != expected_channels:
            raise _contract_error(
                "CMP-CURVE-0025",
                "series.channels",
                "channel arrays must exactly match the definition",
            )
        lengths = {len(values) for values in self.channels.values()}
        if len(lengths) != 1 or not lengths or next(iter(lengths)) < 2:
            raise _contract_error(
                "CMP-CURVE-0026",
                "series.channels",
                "all channel arrays must have the same length of at least two",
            )
        point_count = next(iter(lengths))
        for key, values in self.channels.items():
            if any(value is not None and not math.isfinite(value) for value in values):
                raise _contract_error(
                    "CMP-CURVE-0027", f"series.channels.{key}", "values must be finite"
                )
        expected_deviation_series = {
            item.series_key
            for item in self.definition.deviations
            if item.scope is DeviationScope.POINTWISE
        }
        if set(self.deviations) != expected_deviation_series:
            raise _contract_error(
                "CMP-CURVE-0025",
                "series.deviations",
                "deviation arrays must exactly match pointwise series declarations",
            )
        expected_count_series = {
            item.source_count_series_key
            for item in self.definition.deviations
            if item.source_count_series_key is not None
        }
        if set(self.source_counts) != expected_count_series:
            raise _contract_error(
                "CMP-CURVE-0025",
                "series.source_counts",
                "source-count arrays must exactly match pointwise count declarations",
            )
        for key, values in self.deviations.items():
            if len(values) != point_count:
                raise _contract_error(
                    "CMP-CURVE-0026",
                    f"series.deviations.{key}",
                    "pointwise deviation length differs from channel length",
                )
            if any(value is not None and not math.isfinite(value) for value in values):
                raise _contract_error(
                    "CMP-CURVE-0027", f"series.deviations.{key}", "values must be finite"
                )
        for key, values in self.source_counts.items():
            if len(values) != point_count:
                raise _contract_error(
                    "CMP-CURVE-0026",
                    f"series.source_counts.{key}",
                    "pointwise source-count length differs from channel length",
                )
            if any(value < 1 for value in values):
                raise _contract_error(
                    "CMP-CURVE-0013",
                    f"series.source_counts.{key}",
                    "pointwise source counts must be positive",
                )
        deviations_by_key = {item.key: item for item in self.definition.deviations}
        for group in {
            item.band_group
            for item in self.definition.deviations
            if item.band_group is not None
        }:
            members = [
                item
                for item in deviations_by_key.values()
                if item.band_group == group
            ]
            lower = next(
                item for item in members if item.bound_direction is BoundDirection.LOWER
            )
            upper = next(
                item for item in members if item.bound_direction is BoundDirection.UPPER
            )
            if lower.scope is DeviationScope.CHANNEL_SCALAR:
                assert lower.scalar_value is not None and upper.scalar_value is not None
                if _decimal(lower.scalar_value, "band.lower") > _decimal(
                    upper.scalar_value, "band.upper"
                ):
                    raise _contract_error(
                        "CMP-CURVE-0024",
                        f"series.band_group.{group}",
                        "band lower bound exceeds its upper bound",
                    )
                continue
            assert lower.series_key is not None and upper.series_key is not None
            for index, (lower_value, upper_value) in enumerate(
                zip(
                    self.deviations[lower.series_key],
                    self.deviations[upper.series_key],
                    strict=True,
                )
            ):
                if (
                    lower_value is not None
                    and upper_value is not None
                    and lower_value > upper_value
                ):
                    raise _contract_error(
                        "CMP-CURVE-0024",
                        f"series.band_group.{group}[{index}]",
                        "band lower bound exceeds its upper bound",
                    )

    @property
    def point_count(self) -> int:
        return len(next(iter(self.channels.values())))

    def sample_indices(self, maximum_points: int) -> tuple[int, ...]:
        if maximum_points < 2:
            raise _contract_error(
                "CMP-CURVE-0028", "maximum_points", "preview requires at least two points"
            )
        if self.point_count <= maximum_points:
            return tuple(range(self.point_count))
        return tuple(
            round(index * (self.point_count - 1) / (maximum_points - 1))
            for index in range(maximum_points)
        )

    def preview(self, maximum_points: int) -> CurveSeriesPreview:
        indices = self.sample_indices(maximum_points)
        return CurveSeriesPreview(
            point_count=self.point_count,
            indices=indices,
            channels={
                key: tuple(values[index] for index in indices)
                for key, values in self.channels.items()
            },
            deviations={
                key: tuple(values[index] for index in indices)
                for key, values in self.deviations.items()
            },
            source_counts={
                key: tuple(values[index] for index in indices)
                for key, values in self.source_counts.items()
            },
        )


@dataclass(frozen=True, slots=True)
class CurveSeriesPreview:
    point_count: int
    indices: tuple[int, ...]
    channels: dict[str, tuple[float | None, ...]]
    deviations: dict[str, tuple[float | None, ...]]
    source_counts: dict[str, tuple[int, ...]]

    @property
    def returned_point_count(self) -> int:
        return len(self.indices)

    @property
    def sampled(self) -> bool:
        return self.returned_point_count != self.point_count


@dataclass(frozen=True, slots=True)
class RevisionPin:
    entity_type: str
    entity_id: UUID
    revision_id: UUID

    def __post_init__(self) -> None:
        _key(self.entity_type, "owning_revision.entity_type")
        _uuid(self.entity_id, "owning_revision.entity_id")
        _uuid(self.revision_id, "owning_revision.revision_id")


@dataclass(frozen=True, slots=True)
class ArtifactPin:
    artifact_id: UUID
    sha256: str
    schema_ref: str | None
    media_type: str

    def __post_init__(self) -> None:
        _uuid(self.artifact_id, "artifact.artifact_id")
        _sha256(self.sha256, "artifact.sha256")
        if self.schema_ref is not None:
            _text(self.schema_ref, "artifact.schema_ref", 300)
        _text(self.media_type, "artifact.media_type", 200)


@dataclass(frozen=True, slots=True)
class SourcePin:
    entity_type: str
    entity_id: UUID
    revision_id: UUID
    artifact_id: UUID | None = None
    artifact_sha256: str | None = None

    def __post_init__(self) -> None:
        _key(self.entity_type, "sources[].entity_type")
        _uuid(self.entity_id, "sources[].entity_id")
        _uuid(self.revision_id, "sources[].revision_id")
        if (self.artifact_id is None) != (self.artifact_sha256 is None):
            raise _contract_error(
                "CMP-CURVE-0029",
                "sources[]",
                "source Artifact id and digest must be supplied together",
            )
        if self.artifact_id is not None:
            _uuid(self.artifact_id, "sources[].artifact_id")
            assert self.artifact_sha256 is not None
            _sha256(self.artifact_sha256, "sources[].artifact_sha256")


@dataclass(frozen=True, slots=True)
class ProvenancePointer:
    kind: ProvenanceKind
    entity_id: UUID
    revision_id: UUID | None = None

    def __post_init__(self) -> None:
        _uuid(self.entity_id, "provenance[].entity_id")
        if self.revision_id is not None:
            _uuid(self.revision_id, "provenance[].revision_id")


@dataclass(frozen=True, slots=True)
class CurveMetadata:
    state: MetadataState
    owning_revision: RevisionPin
    artifact: ArtifactPin
    definition: CurveDefinition | None
    sources: tuple[SourcePin, ...] = ()
    provenance: tuple[ProvenancePointer, ...] = ()

    def __post_init__(self) -> None:
        if self.state is MetadataState.ABSENT:
            if self.definition is not None:
                raise _contract_error(
                    "CMP-CURVE-0030",
                    "definition",
                    "metadata_state absent requires a null definition",
                )
        elif self.definition is None:
            raise _contract_error(
                "CMP-CURVE-0030",
                "definition",
                "declared and legacy-compatible metadata require a definition",
            )

    @property
    def definition_sha256(self) -> str | None:
        return self.definition.sha256 if self.definition is not None else None


def original_unit_canonical(value: OriginalUnit) -> dict[str, str]:
    return {
        "unit": value.unit,
        "scale_to_normalized": decimal_text(_decimal(value.scale_to_normalized, "scale")),
        "offset_to_normalized": decimal_text(_decimal(value.offset_to_normalized, "offset")),
    }


def channel_canonical(value: CurveChannel) -> dict[str, object]:
    return {
        "key": value.key,
        "label": value.label,
        "quantity_semantics": value.quantity_semantics,
        "axis_role": value.axis_role.value,
        "unit_contract": value.unit_contract.value,
        "dimension": value.dimension.value if value.dimension is not None else None,
        "original_units": [original_unit_canonical(item) for item in value.original_units],
        "normalized_unit": value.normalized_unit,
        "display_unit": value.display_unit,
        "display_scale": decimal_text(_decimal(value.display_scale, "display_scale")),
        "display_offset": decimal_text(_decimal(value.display_offset, "display_offset")),
        "value_basis": value.value_basis.value,
    }


def deviation_canonical(value: CurveDeviation) -> dict[str, object]:
    return {
        "key": value.key,
        "target_channel_key": value.target_channel_key,
        "scope": value.scope.value,
        "kind": value.kind.value,
        "method_id": value.method_id,
        "method_version": value.method_version,
        "unit": value.unit,
        "bound_direction": value.bound_direction.value,
        "band_group": value.band_group,
        "scalar_value": (
            decimal_text(_decimal(value.scalar_value, "scalar_value"))
            if value.scalar_value is not None
            else None
        ),
        "series_key": value.series_key,
        "source_count": value.source_count,
        "source_count_series_key": value.source_count_series_key,
        "confidence_level": value.confidence_level,
        "coverage": value.coverage.value if value.coverage is not None else None,
        "ddof": value.ddof,
        "quantile_probability": value.quantile_probability,
        "quantile_method": value.quantile_method,
    }


def curve_definition_canonical(value: CurveDefinition) -> dict[str, object]:
    return {
        "definition_version": value.definition_version,
        "channels": [channel_canonical(item) for item in value.channels],
        "deviations": [deviation_canonical(item) for item in value.deviations],
    }


def curve_definition_json_bytes(value: CurveDefinition) -> bytes:
    return json.dumps(
        curve_definition_canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def curve_definition_from_mapping(document: object) -> CurveDefinition:
    """Parse the strict canonical representation used in Parquet/Processing metadata."""

    if not isinstance(document, dict) or set(document) != {
        "definition_version",
        "channels",
        "deviations",
    }:
        raise _contract_error(
            "CMP-CURVE-0031", "definition", "curve definition keys do not match version 1.0.0"
        )
    channels_raw = document.get("channels")
    deviations_raw = document.get("deviations")
    if not isinstance(channels_raw, list) or not isinstance(deviations_raw, list):
        raise _contract_error(
            "CMP-CURVE-0031", "definition", "channels and deviations must be arrays"
        )
    try:
        channels = tuple(
            CurveChannel(
                key=str(item["key"]),
                label=str(item["label"]),
                quantity_semantics=str(item["quantity_semantics"]),
                axis_role=AxisRole(item["axis_role"]),
                unit_contract=UnitContract(item["unit_contract"]),
                dimension=(
                    DimensionId(item["dimension"]) if item["dimension"] is not None else None
                ),
                original_units=tuple(
                    OriginalUnit(
                        unit=str(unit["unit"]),
                        scale_to_normalized=str(unit["scale_to_normalized"]),
                        offset_to_normalized=str(unit["offset_to_normalized"]),
                    )
                    for unit in item["original_units"]
                ),
                normalized_unit=str(item["normalized_unit"]),
                display_unit=str(item["display_unit"]),
                display_scale=str(item["display_scale"]),
                display_offset=str(item["display_offset"]),
                value_basis=ValueBasis(item["value_basis"]),
            )
            for item in channels_raw
        )
        deviations = tuple(
            CurveDeviation(
                key=str(item["key"]),
                target_channel_key=str(item["target_channel_key"]),
                scope=DeviationScope(item["scope"]),
                kind=DeviationKind(item["kind"]),
                method_id=str(item["method_id"]),
                method_version=str(item["method_version"]),
                unit=str(item["unit"]),
                bound_direction=BoundDirection(item["bound_direction"]),
                band_group=item["band_group"],
                scalar_value=item["scalar_value"],
                series_key=item["series_key"],
                source_count=item["source_count"],
                source_count_series_key=item["source_count_series_key"],
                confidence_level=item["confidence_level"],
                coverage=(Coverage(item["coverage"]) if item["coverage"] is not None else None),
                ddof=item["ddof"],
                quantile_probability=item["quantile_probability"],
                quantile_method=item["quantile_method"],
            )
            for item in deviations_raw
        )
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, CurveContractError):
            raise
        raise _contract_error(
            "CMP-CURVE-0031", "definition", "curve definition field types are invalid"
        ) from error
    return CurveDefinition(
        definition_version=str(document["definition_version"]),
        channels=channels,
        deviations=deviations,
    )


def curve_metadata_canonical(value: CurveMetadata) -> dict[str, object]:
    return {
        "contract_version": CURVE_METADATA_CONTRACT_VERSION,
        "metadata_state": value.state.value,
        "definition_sha256": value.definition_sha256,
        "definition": (
            curve_definition_canonical(value.definition)
            if value.definition is not None
            else None
        ),
        "owning_revision": {
            "entity_type": value.owning_revision.entity_type,
            "entity_id": str(value.owning_revision.entity_id),
            "revision_id": str(value.owning_revision.revision_id),
        },
        "artifact": {
            "artifact_id": str(value.artifact.artifact_id),
            "sha256": value.artifact.sha256,
            "schema_ref": value.artifact.schema_ref,
            "media_type": value.artifact.media_type,
        },
        "sources": [
            {
                "entity_type": item.entity_type,
                "entity_id": str(item.entity_id),
                "revision_id": str(item.revision_id),
                "artifact_id": str(item.artifact_id) if item.artifact_id is not None else None,
                "artifact_sha256": item.artifact_sha256,
            }
            for item in value.sources
        ],
        "provenance": [
            {
                "kind": item.kind.value,
                "entity_id": str(item.entity_id),
                "revision_id": str(item.revision_id) if item.revision_id is not None else None,
            }
            for item in value.provenance
        ],
    }
