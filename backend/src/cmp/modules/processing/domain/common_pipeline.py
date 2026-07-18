"""Quantity-driven common curve processing methods for the configurable Workbench (T-53).

The pipeline is deliberately independent of a test method, material family, constitutive model,
and solver.  A Mapping Profile binds canonical Test Data channels to calculation quantities before
an ordered list of versioned methods is evaluated.  Every numerical policy is explicit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

import numpy as np
from scipy.interpolate import UnivariateSpline  # type: ignore[import-untyped]
from scipy.signal import savgol_filter  # type: ignore[import-untyped]

from cmp.modules.datasets.domain.canonical_test_data import CanonicalTestDataDocument
from cmp.shared.domain.revisions import content_sha256

COMMON_METHOD_VERSION = "1.0.0"
MAX_PREVIEW_POINTS = 100_000
MAX_PIPELINE_STEPS = 32


class CommonPipelineError(ValueError):
    """A Mapping Profile or processing pipeline is invalid or incompatible."""


class MissingDataPolicy(StrEnum):
    REJECT = "reject"
    DROP_ANY = "drop_any"


@dataclass(frozen=True, slots=True)
class ChannelBinding:
    channel_key: str
    target_quantity: str
    accepted_normalized_units: tuple[str, ...]
    required: bool = True
    scale: float = 1.0
    offset: float = 0.0

    def __post_init__(self) -> None:
        if not self.channel_key or not self.target_quantity:
            raise CommonPipelineError("mapping channel_key and target_quantity are required")
        if not self.accepted_normalized_units:
            raise CommonPipelineError("mapping requires at least one accepted normalized unit")
        if not math.isfinite(self.scale) or self.scale == 0 or not math.isfinite(self.offset):
            raise CommonPipelineError("mapping scale must be finite/non-zero and offset finite")


@dataclass(frozen=True, slots=True)
class AttributeBinding:
    attribute_definition_id: UUID
    attribute_definition_revision_id: UUID
    target_quantity: str
    accepted_normalized_units: tuple[str, ...]
    required: bool = True

    def __post_init__(self) -> None:
        if not self.target_quantity or not self.accepted_normalized_units:
            raise CommonPipelineError(
                "attribute mapping requires target_quantity and accepted normalized units"
            )


@dataclass(frozen=True, slots=True)
class MappingProfileContent:
    profile_key: str
    label: str
    independent_quantity: str
    missing_data_policy: MissingDataPolicy
    bindings: tuple[ChannelBinding, ...]
    attribute_bindings: tuple[AttributeBinding, ...] = ()

    def __post_init__(self) -> None:
        if not self.profile_key.strip() or len(self.profile_key) > 160:
            raise CommonPipelineError("profile_key must contain 1..160 trimmed characters")
        if not self.label.strip() or len(self.label) > 200:
            raise CommonPipelineError("mapping label must contain 1..200 trimmed characters")
        if not 2 <= len(self.bindings) <= 128:
            raise CommonPipelineError("a Mapping Profile requires 2..128 bindings")
        sources = [item.channel_key for item in self.bindings]
        targets = [item.target_quantity for item in self.bindings]
        if len(set(sources)) != len(sources) or len(set(targets)) != len(targets):
            raise CommonPipelineError(
                "mapping source channels and target quantities must be unique"
            )
        if self.independent_quantity not in targets:
            raise CommonPipelineError("independent_quantity must be a mapped target quantity")
        attribute_targets = [item.target_quantity for item in self.attribute_bindings]
        if len(set(attribute_targets)) != len(attribute_targets):
            raise CommonPipelineError("attribute mapping target quantities must be unique")
        if set(attribute_targets) & set(targets):
            raise CommonPipelineError("channel and attribute mapping targets must be unique")

    @property
    def digest(self) -> str:
        return content_sha256(mapping_profile_canonical(self))


@dataclass(frozen=True, slots=True)
class ProcessingStep:
    method_id: str
    method_version: str
    options: dict[str, Any]

    def __post_init__(self) -> None:
        if self.method_version != COMMON_METHOD_VERSION:
            raise CommonPipelineError(
                "unsupported method version "
                f"{self.method_version}; expected {COMMON_METHOD_VERSION}"
            )


@dataclass(frozen=True, slots=True)
class QuantitySeries:
    quantity: str
    unit: str
    values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class CurveStage:
    ordinal: int
    method_id: str
    method_version: str
    point_count: int
    series: tuple[QuantitySeries, ...]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProcessingPreview:
    source_document_sha256: str
    mapping_profile_sha256: str
    independent_quantity: str
    stages: tuple[CurveStage, ...]


def processing_preview_canonical(value: ProcessingPreview) -> dict[str, object]:
    """Return the stable numeric representation used by committed processing evidence."""

    return {
        "source_document_sha256": value.source_document_sha256,
        "mapping_profile_sha256": value.mapping_profile_sha256,
        "independent_quantity": value.independent_quantity,
        "stages": [
            {
                "ordinal": stage.ordinal,
                "method_id": stage.method_id,
                "method_version": stage.method_version,
                "point_count": stage.point_count,
                "series": [
                    {
                        "quantity": series.quantity,
                        "unit": series.unit,
                        "values": list(series.values),
                    }
                    for series in stage.series
                ],
                "diagnostics": list(stage.diagnostics),
            }
            for stage in value.stages
        ],
    }


@dataclass(frozen=True, slots=True)
class MethodDefinition:
    method_id: str
    version: str
    label: str
    description: str
    option_schema: dict[str, Any]
    deterministic: bool = True
    allows_extrapolation: bool = False


def mapping_profile_canonical(value: MappingProfileContent) -> dict[str, object]:
    return {
        "profile_key": value.profile_key,
        "label": value.label,
        "independent_quantity": value.independent_quantity,
        "missing_data_policy": value.missing_data_policy.value,
        "bindings": [
            {
                "channel_key": item.channel_key,
                "target_quantity": item.target_quantity,
                "accepted_normalized_units": list(item.accepted_normalized_units),
                "required": item.required,
                "scale": item.scale,
                "offset": item.offset,
            }
            for item in value.bindings
        ],
        "attribute_bindings": [
            {
                "attribute_definition_id": str(item.attribute_definition_id),
                "attribute_definition_revision_id": str(
                    item.attribute_definition_revision_id
                ),
                "target_quantity": item.target_quantity,
                "accepted_normalized_units": list(item.accepted_normalized_units),
                "required": item.required,
            }
            for item in value.attribute_bindings
        ],
    }


def _number_schema(*, minimum: float | None = None) -> dict[str, object]:
    result: dict[str, object] = {"type": "number"}
    if minimum is not None:
        result["minimum"] = minimum
    return result


METHOD_REGISTRY: tuple[MethodDefinition, ...] = (
    MethodDefinition(
        "rows.sort_unique",
        COMMON_METHOD_VERSION,
        "Sort and resolve duplicate x values",
        "Sorts by the independent quantity and applies an explicit duplicate policy.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"duplicate_policy": {"enum": ["reject", "first", "mean"]}},
            "required": ["duplicate_policy"],
        },
    ),
    MethodDefinition(
        "curve.crop",
        COMMON_METHOD_VERSION,
        "Crop domain",
        "Keeps observed points inside an inclusive x range without interpolation.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"minimum": _number_schema(), "maximum": _number_schema()},
            "required": ["minimum", "maximum"],
        },
    ),
    MethodDefinition(
        "curve.scale_shift",
        COMMON_METHOD_VERSION,
        "Scale and shift quantity",
        "Applies y = scale*y + offset to one declared quantity.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "quantity": {"type": "string", "minLength": 1},
                "scale": _number_schema(),
                "offset": _number_schema(),
            },
            "required": ["quantity", "scale", "offset"],
        },
    ),
    MethodDefinition(
        "curve.resample_linear",
        COMMON_METHOD_VERSION,
        "Linear resampling",
        "Resamples on an explicit uniform grid and rejects extrapolation.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "start": _number_schema(),
                "end": _number_schema(),
                "count": {"type": "integer", "minimum": 2, "maximum": MAX_PREVIEW_POINTS},
                "extrapolation": {"const": "reject"},
            },
            "required": ["start", "end", "count", "extrapolation"],
        },
    ),
    MethodDefinition(
        "curve.moving_average",
        COMMON_METHOD_VERSION,
        "Centered moving average",
        "Smooths one dependent quantity with an odd reflected-edge window.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "quantity": {"type": "string", "minLength": 1},
                "window": {"type": "integer", "minimum": 3},
            },
            "required": ["quantity", "window"],
        },
    ),
    MethodDefinition(
        "curve.savitzky_golay",
        COMMON_METHOD_VERSION,
        "Savitzky-Golay smoothing",
        "Smooths one quantity with an explicit odd window and polynomial order.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "quantity": {"type": "string", "minLength": 1},
                "window": {"type": "integer", "minimum": 3},
                "polynomial_order": {"type": "integer", "minimum": 1},
            },
            "required": ["quantity", "window", "polynomial_order"],
        },
    ),
    MethodDefinition(
        "curve.smoothing_spline",
        COMMON_METHOD_VERSION,
        "Smoothing spline",
        "Fits a cubic smoothing spline to one quantity on a strictly increasing domain.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "quantity": {"type": "string", "minLength": 1},
                "smoothing_factor": _number_schema(minimum=0),
            },
            "required": ["quantity", "smoothing_factor"],
        },
    ),
)

_METHODS = {item.method_id: item for item in METHOD_REGISTRY}


def _float_option(options: dict[str, Any], key: str) -> float:
    value = options.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise CommonPipelineError(f"option {key} must be a finite number")
    return float(value)


def _int_option(options: dict[str, Any], key: str) -> int:
    value = options.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise CommonPipelineError(f"option {key} must be an integer")
    return value


def _text_option(options: dict[str, Any], key: str) -> str:
    value = options.get(key)
    if not isinstance(value, str) or not value:
        raise CommonPipelineError(f"option {key} must be a non-empty string")
    return value


def _validate_options(step: ProcessingStep, definition: MethodDefinition) -> None:
    schema = definition.option_schema
    allowed = set(schema["properties"])
    required = set(schema["required"])
    if set(step.options) - allowed:
        raise CommonPipelineError(f"{step.method_id} contains unknown options")
    if required - set(step.options):
        raise CommonPipelineError(f"{step.method_id} is missing required options")


def _mapped_series(
    document: CanonicalTestDataDocument, profile: MappingProfileContent
) -> tuple[list[str], dict[str, np.ndarray]]:
    channels = {item.key: item for item in document.channels}
    units: list[str] = []
    columns: dict[str, list[float | None]] = {}
    for binding in profile.bindings:
        channel = channels.get(binding.channel_key)
        if channel is None:
            if binding.required:
                raise CommonPipelineError(f"required channel {binding.channel_key} is missing")
            continue
        if channel.normalized_unit not in binding.accepted_normalized_units:
            raise CommonPipelineError(
                f"channel {binding.channel_key} unit {channel.normalized_unit} is not accepted"
            )
        columns[binding.target_quantity] = [
            None if value is None else float(value) * binding.scale + binding.offset
            for value in channel.normalized_values
        ]
        units.append(channel.normalized_unit)
    if profile.independent_quantity not in columns:
        raise CommonPipelineError("mapped independent quantity is unavailable")
    missing_rows = {
        ordinal
        for values in columns.values()
        for ordinal, value in enumerate(values)
        if value is None
    }
    if missing_rows and profile.missing_data_policy is MissingDataPolicy.REJECT:
        raise CommonPipelineError(
            f"mapping encountered {len(missing_rows)} rows with missing values; policy is reject"
        )
    keep = [index for index in range(document.point_count) if index not in missing_rows]
    if len(keep) < 2:
        raise CommonPipelineError("mapping leaves fewer than two complete rows")
    result = {
        quantity: np.asarray([values[index] for index in keep], dtype=np.float64)
        for quantity, values in columns.items()
    }
    return units, result


def _stage(
    ordinal: int,
    method_id: str,
    columns: dict[str, np.ndarray],
    units: dict[str, str],
    diagnostics: tuple[str, ...],
) -> CurveStage:
    return CurveStage(
        ordinal=ordinal,
        method_id=method_id,
        method_version=COMMON_METHOD_VERSION,
        point_count=len(next(iter(columns.values()))),
        series=tuple(
            QuantitySeries(quantity, units[quantity], tuple(float(item) for item in values))
            for quantity, values in columns.items()
        ),
        diagnostics=diagnostics,
    )


def _require_quantity(columns: dict[str, np.ndarray], options: dict[str, Any]) -> str:
    quantity = _text_option(options, "quantity")
    if quantity not in columns:
        raise CommonPipelineError(f"quantity {quantity} is not mapped")
    return quantity


def _sort_unique(
    columns: dict[str, np.ndarray], x_key: str, options: dict[str, Any]
) -> tuple[dict[str, np.ndarray], tuple[str, ...]]:
    policy = _text_option(options, "duplicate_policy")
    if policy not in {"reject", "first", "mean"}:
        raise CommonPipelineError("duplicate_policy must be reject, first, or mean")
    order = np.argsort(columns[x_key], kind="stable")
    sorted_columns = {key: value[order] for key, value in columns.items()}
    x = sorted_columns[x_key]
    unique, starts, counts = np.unique(x, return_index=True, return_counts=True)
    duplicate_count = int(np.sum(counts - 1))
    if duplicate_count and policy == "reject":
        raise CommonPipelineError(f"independent quantity contains {duplicate_count} duplicates")
    if not duplicate_count:
        return sorted_columns, ("input rows sorted by independent quantity",)
    if policy == "first":
        return (
            {key: value[starts] for key, value in sorted_columns.items()},
            (f"resolved {duplicate_count} duplicate rows with first",),
        )
    averaged = {
        key: np.asarray(
            [
                float(np.mean(value[start : start + count]))
                for start, count in zip(starts, counts, strict=True)
            ],
            dtype=np.float64,
        )
        for key, value in sorted_columns.items()
    }
    averaged[x_key] = unique
    return averaged, (f"resolved {duplicate_count} duplicate rows with mean",)


def _apply_step(
    columns: dict[str, np.ndarray], x_key: str, step: ProcessingStep
) -> tuple[dict[str, np.ndarray], tuple[str, ...]]:
    definition = _METHODS.get(step.method_id)
    if definition is None:
        raise CommonPipelineError(f"unknown processing method {step.method_id}")
    _validate_options(step, definition)
    options = step.options
    if step.method_id == "rows.sort_unique":
        return _sort_unique(columns, x_key, options)
    if step.method_id == "curve.crop":
        minimum = _float_option(options, "minimum")
        maximum = _float_option(options, "maximum")
        if minimum >= maximum:
            raise CommonPipelineError("crop minimum must be less than maximum")
        mask = (columns[x_key] >= minimum) & (columns[x_key] <= maximum)
        if int(np.sum(mask)) < 2:
            raise CommonPipelineError("crop leaves fewer than two observed points")
        return (
            {key: value[mask] for key, value in columns.items()},
            (f"kept {int(np.sum(mask))} observed points in inclusive domain",),
        )
    if step.method_id == "curve.scale_shift":
        quantity = _require_quantity(columns, options)
        scale = _float_option(options, "scale")
        offset = _float_option(options, "offset")
        if scale == 0:
            raise CommonPipelineError("scale cannot be zero")
        result = dict(columns)
        result[quantity] = columns[quantity] * scale + offset
        return result, (f"applied y={scale}*y+{offset} to {quantity}",)
    if step.method_id == "curve.resample_linear":
        start = _float_option(options, "start")
        end = _float_option(options, "end")
        count = _int_option(options, "count")
        if options.get("extrapolation") != "reject":
            raise CommonPipelineError("the common linear resampler only supports reject")
        x = columns[x_key]
        if np.any(np.diff(x) <= 0):
            raise CommonPipelineError("resampling requires sorted unique independent values")
        if start < x[0] or end > x[-1]:
            raise CommonPipelineError("resampling would extrapolate beyond the observed domain")
        if start >= end or not 2 <= count <= MAX_PREVIEW_POINTS:
            raise CommonPipelineError("resampling requires start < end and count 2..100000")
        grid = np.linspace(start, end, count)
        result = {key: np.interp(grid, x, value) for key, value in columns.items()}
        result[x_key] = grid
        return result, ("piecewise-linear interpolation; extrapolation rejected",)
    if step.method_id == "curve.moving_average":
        quantity = _require_quantity(columns, options)
        window = _int_option(options, "window")
        if window < 3 or window % 2 == 0 or window > len(columns[quantity]):
            raise CommonPipelineError("moving-average window must be odd, >=3, and <= point count")
        kernel = np.ones(window, dtype=np.float64) / window
        pad = window // 2
        result = dict(columns)
        result[quantity] = np.convolve(
            np.pad(columns[quantity], pad, mode="reflect"), kernel, "valid"
        )
        return result, (f"centered reflected-edge moving average window={window}",)
    if step.method_id == "curve.savitzky_golay":
        quantity = _require_quantity(columns, options)
        window = _int_option(options, "window")
        order = _int_option(options, "polynomial_order")
        if window < 3 or window % 2 == 0 or window > len(columns[quantity]) or order >= window:
            raise CommonPipelineError(
                "Savitzky-Golay requires odd window <= points and order < window"
            )
        result = dict(columns)
        result[quantity] = savgol_filter(columns[quantity], window, order, mode="interp")
        return result, (f"Savitzky-Golay window={window}, polynomial_order={order}",)
    if step.method_id == "curve.smoothing_spline":
        quantity = _require_quantity(columns, options)
        smoothing = _float_option(options, "smoothing_factor")
        x = columns[x_key]
        if smoothing < 0 or np.any(np.diff(x) <= 0):
            raise CommonPipelineError("spline requires nonnegative smoothing and sorted unique x")
        if len(x) < 4:
            raise CommonPipelineError("cubic smoothing spline requires at least four points")
        result = dict(columns)
        result[quantity] = UnivariateSpline(x, columns[quantity], s=smoothing, k=3)(x)
        return result, (f"cubic smoothing spline factor={smoothing}",)
    raise CommonPipelineError(f"method {step.method_id} is not executable")


def preview_pipeline(
    document: CanonicalTestDataDocument,
    profile: MappingProfileContent,
    steps: tuple[ProcessingStep, ...],
) -> ProcessingPreview:
    """Map canonical channels and evaluate immutable in-memory stage snapshots."""

    if document.point_count > MAX_PREVIEW_POINTS:
        raise CommonPipelineError("interactive preview supports at most 100000 points")
    if len(steps) > MAX_PIPELINE_STEPS:
        raise CommonPipelineError("a preview supports at most 32 ordered steps")
    _unused_units, columns = _mapped_series(document, profile)
    channel_by_key = {item.key: item for item in document.channels}
    units = {
        binding.target_quantity: channel_by_key[binding.channel_key].normalized_unit
        for binding in profile.bindings
        if binding.channel_key in channel_by_key
    }
    stages = [_stage(0, "mapping", columns, units, ("canonical normalized values mapped",))]
    current = columns
    for ordinal, step in enumerate(steps, start=1):
        current, diagnostics = _apply_step(current, profile.independent_quantity, step)
        if any(not np.all(np.isfinite(values)) for values in current.values()):
            raise CommonPipelineError(f"method {step.method_id} produced non-finite output")
        stages.append(_stage(ordinal, step.method_id, current, units, diagnostics))
    return ProcessingPreview(
        source_document_sha256=document.digest,
        mapping_profile_sha256=profile.digest,
        independent_quantity=profile.independent_quantity,
        stages=tuple(stages),
    )
