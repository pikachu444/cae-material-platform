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
from scipy.optimize import least_squares  # type: ignore[import-untyped]
from scipy.signal import savgol_filter  # type: ignore[import-untyped]

from cmp.modules.datasets.domain.canonical_test_data import CanonicalTestDataDocument
from cmp.modules.processing.domain.metal_hardening import (
    MetalHardeningError,
    fit_hardening_candidates,
)
from cmp.modules.processing.domain.polymer_viscoelastic import (
    PolymerViscoelasticError,
    fit_prony_candidates,
    log_time_resample,
)
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
class ScalarResult:
    key: str
    quantity_semantics: str
    value: float
    unit: str


@dataclass(frozen=True, slots=True)
class CurveStage:
    ordinal: int
    method_id: str
    method_version: str
    point_count: int
    series: tuple[QuantitySeries, ...]
    diagnostics: tuple[str, ...]
    scalar_results: tuple[ScalarResult, ...] = ()


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
                "scalar_results": [
                    {
                        "key": item.key,
                        "quantity_semantics": item.quantity_semantics,
                        "value": item.value,
                        "unit": item.unit,
                    }
                    for item in stage.scalar_results
                ],
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
                "attribute_definition_revision_id": str(item.attribute_definition_revision_id),
                "target_quantity": item.target_quantity,
                "accepted_normalized_units": list(item.accepted_normalized_units),
                "required": item.required,
            }
            for item in value.attribute_bindings
        ],
    }


def _number_schema(
    *, minimum: float | None = None, maximum: float | None = None
) -> dict[str, object]:
    result: dict[str, object] = {"type": "number"}
    if minimum is not None:
        result["minimum"] = minimum
    if maximum is not None:
        result["maximum"] = maximum
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
    MethodDefinition(
        "metal.elastic_modulus",
        COMMON_METHOD_VERSION,
        "Metal elastic modulus",
        "Calculates modulus by user-range OLS, Huber robust regression, chord, "
        "secant, or manual input.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "strain_quantity": {"type": "string", "minLength": 1},
                "stress_quantity": {"type": "string", "minLength": 1},
                "method": {
                    "enum": [
                        "linear_regression",
                        "robust_huber",
                        "chord",
                        "secant",
                        "manual",
                    ]
                },
                "minimum_strain": _number_schema(),
                "maximum_strain": _number_schema(),
                "manual_modulus_pa": _number_schema(minimum=0),
            },
            "required": [
                "strain_quantity",
                "stress_quantity",
                "method",
                "minimum_strain",
                "maximum_strain",
                "manual_modulus_pa",
            ],
        },
    ),
    MethodDefinition(
        "metal.proof_stress",
        COMMON_METHOD_VERSION,
        "Offset proof stress",
        "Finds the observed-curve intersection with an explicit offset elastic line.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "strain_quantity": {"type": "string", "minLength": 1},
                "stress_quantity": {"type": "string", "minLength": 1},
                "youngs_modulus_pa": _number_schema(minimum=0),
                "offset_strain": _number_schema(minimum=0),
                "search_start": _number_schema(),
                "search_end": _number_schema(),
            },
            "required": [
                "strain_quantity",
                "stress_quantity",
                "youngs_modulus_pa",
                "offset_strain",
                "search_start",
                "search_end",
            ],
        },
    ),
    MethodDefinition(
        "metal.necking_candidate",
        COMMON_METHOD_VERSION,
        "Metal necking candidate",
        "Reports an automatic peak-stress candidate without cropping or confirming the curve.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "strain_quantity": {"type": "string", "minLength": 1},
                "stress_quantity": {"type": "string", "minLength": 1},
                "method": {"const": "peak_engineering_stress"},
            },
            "required": ["strain_quantity", "stress_quantity", "method"],
        },
    ),
    MethodDefinition(
        "metal.engineering_to_true_plastic",
        COMMON_METHOD_VERSION,
        "Engineering to true/plastic",
        "Derives true stress, true total strain, and true plastic strain up to an "
        "explicit necking boundary.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "strain_quantity": {"type": "string", "minLength": 1},
                "stress_quantity": {"type": "string", "minLength": 1},
                "youngs_modulus_pa": _number_schema(minimum=0),
                "necking_policy": {"enum": ["observed_full_domain", "manual_index"]},
                "manual_necking_index": {"type": "integer", "minimum": 0},
                "negative_plastic_policy": {"enum": ["retain", "clip_zero", "drop"]},
            },
            "required": [
                "strain_quantity",
                "stress_quantity",
                "youngs_modulus_pa",
                "necking_policy",
                "manual_necking_index",
                "negative_plastic_policy",
            ],
        },
    ),
    MethodDefinition(
        "metal.hardening_fit_extrapolate",
        COMMON_METHOD_VERSION,
        "Metal hardening candidates",
        "Fits public Voce, Swift, Hockett-Sherby, and Ghosh equations with one objective, "
        "then explicitly combines two candidates on a bounded extrapolation grid.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "plastic_strain_quantity": {"type": "string", "minLength": 1},
                "stress_quantity": {"type": "string", "minLength": 1},
                "families": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 4,
                    "uniqueItems": True,
                    "items": {"enum": ["voce", "swift", "hockett_sherby", "ghosh"]},
                },
                "fit_minimum_strain": _number_schema(minimum=0, maximum=5),
                "fit_maximum_strain": _number_schema(minimum=0, maximum=5),
                "extrapolation_maximum_strain": _number_schema(minimum=0, maximum=5),
                "output_point_count": {"type": "integer", "minimum": 21, "maximum": 501},
                "primary_family": {"enum": ["voce", "swift", "hockett_sherby", "ghosh"]},
                "secondary_family": {"enum": ["voce", "swift", "hockett_sherby", "ghosh"]},
                "primary_weight": _number_schema(minimum=0, maximum=1),
                "normalization_stress_pa": _number_schema(minimum=1),
                "maximum_function_evaluations": {
                    "type": "integer",
                    "minimum": 50,
                    "maximum": 100000,
                },
                "selection_reason": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 500,
                },
            },
            "required": [
                "plastic_strain_quantity",
                "stress_quantity",
                "families",
                "fit_minimum_strain",
                "fit_maximum_strain",
                "extrapolation_maximum_strain",
                "output_point_count",
                "primary_family",
                "secondary_family",
                "primary_weight",
                "normalization_stress_pa",
                "maximum_function_evaluations",
            ],
        },
        allows_extrapolation=True,
    ),
    MethodDefinition(
        "polymer.log_time_resample",
        COMMON_METHOD_VERSION,
        "Polymer log-time resampling",
        "Resamples positive relaxation time on a log10 grid and rejects extrapolation.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "start_time_s": _number_schema(minimum=0),
                "end_time_s": _number_schema(minimum=0),
                "count": {"type": "integer", "minimum": 3, "maximum": MAX_PREVIEW_POINTS},
                "extrapolation": {"const": "reject"},
            },
            "required": ["start_time_s", "end_time_s", "count", "extrapolation"],
        },
    ),
    MethodDefinition(
        "polymer.prony_fit_compare",
        COMMON_METHOD_VERSION,
        "Polymer Prony candidate comparison",
        "Fits one-to-ten-term generalized-Maxwell candidates and selects by BIC or an "
        "explicit user choice.",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "time_quantity": {"type": "string", "minLength": 1},
                "modulus_quantity": {"type": "string", "minLength": 1},
                "candidate_term_counts": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 10,
                    "uniqueItems": True,
                    "items": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "selection_mode": {"enum": ["automatic_bic", "manual"]},
                "selected_term_count": {"type": "integer", "minimum": 1, "maximum": 10},
                "normalization_modulus_pa": _number_schema(minimum=1),
                "minimum_relaxation_time_s": _number_schema(minimum=0),
                "maximum_relaxation_time_s": _number_schema(minimum=0),
                "maximum_function_evaluations": {
                    "type": "integer",
                    "minimum": 50,
                    "maximum": 100000,
                },
            },
            "required": [
                "time_quantity",
                "modulus_quantity",
                "candidate_term_counts",
                "selection_mode",
                "selected_term_count",
                "normalization_modulus_pa",
                "minimum_relaxation_time_s",
                "maximum_relaxation_time_s",
                "maximum_function_evaluations",
            ],
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
    scalar_results: tuple[ScalarResult, ...] = (),
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
        scalar_results=scalar_results,
    )


def _require_quantity(columns: dict[str, np.ndarray], options: dict[str, Any]) -> str:
    quantity = _text_option(options, "quantity")
    if quantity not in columns:
        raise CommonPipelineError(f"quantity {quantity} is not mapped")
    return quantity


def _named_quantity(
    columns: dict[str, np.ndarray], options: dict[str, Any], option_key: str
) -> str:
    quantity = _text_option(options, option_key)
    if quantity not in columns:
        raise CommonPipelineError(f"quantity {quantity} is not mapped")
    return quantity


def _require_metal_tensile_units(units: dict[str, str], strain_key: str, stress_key: str) -> None:
    if units[strain_key] != "1" or units[stress_key] != "Pa":
        raise CommonPipelineError(
            "metal tensile methods require normalized strain unit 1 and stress unit Pa"
        )


def _elastic_modulus(
    columns: dict[str, np.ndarray], units: dict[str, str], options: dict[str, Any]
) -> tuple[tuple[str, ...], tuple[ScalarResult, ...]]:
    strain_key = _named_quantity(columns, options, "strain_quantity")
    stress_key = _named_quantity(columns, options, "stress_quantity")
    _require_metal_tensile_units(units, strain_key, stress_key)
    method = _text_option(options, "method")
    minimum = _float_option(options, "minimum_strain")
    maximum = _float_option(options, "maximum_strain")
    manual = _float_option(options, "manual_modulus_pa")
    x = columns[strain_key]
    y = columns[stress_key]
    if np.any(np.diff(x) <= 0):
        raise CommonPipelineError("elastic modulus requires sorted unique strain")
    mask = (x >= minimum) & (x <= maximum)
    count = int(np.sum(mask))
    if minimum >= maximum or count < 2:
        raise CommonPipelineError("elastic modulus domain must contain at least two points")
    selected_x = x[mask]
    selected_y = y[mask]
    intercept = 0.0
    if method == "linear_regression":
        modulus, intercept = np.polyfit(selected_x, selected_y, 1)
    elif method == "robust_huber":
        initial = np.polyfit(selected_x, selected_y, 1)
        scale = max(float(np.median(np.abs(selected_y - np.median(selected_y)))), 1.0)
        optimized = least_squares(
            lambda values: (values[0] * selected_x + values[1] - selected_y) / scale,
            initial,
            loss="huber",
            f_scale=1.0,
        )
        modulus, intercept = optimized.x
    elif method == "chord":
        start_stress = float(np.interp(minimum, x, y))
        end_stress = float(np.interp(maximum, x, y))
        modulus = (end_stress - start_stress) / (maximum - minimum)
        intercept = start_stress - modulus * minimum
    elif method == "secant":
        if maximum <= 0:
            raise CommonPipelineError("secant modulus requires positive maximum_strain")
        modulus = float(np.interp(maximum, x, y)) / maximum
    elif method == "manual":
        modulus = manual
    else:
        raise CommonPipelineError("unsupported elastic modulus method")
    modulus = float(modulus)
    intercept = float(intercept)
    if not math.isfinite(modulus) or modulus <= 0:
        raise CommonPipelineError("elastic modulus result must be finite and positive")
    predicted = modulus * selected_x + intercept
    total = float(np.sum((selected_y - np.mean(selected_y)) ** 2))
    residual = float(np.sum((selected_y - predicted) ** 2))
    r_squared = 1.0 if total == 0 and residual == 0 else 1.0 - residual / total if total else 0.0
    return (
        (f"{method} elastic modulus on [{minimum}, {maximum}] using {count} points",),
        (
            ScalarResult("youngs_modulus", "modulus.young", modulus, "Pa"),
            ScalarResult("elastic_intercept", "stress.intercept", intercept, "Pa"),
            ScalarResult("elastic_r_squared", "statistics.r_squared", r_squared, "1"),
        ),
    )


def _proof_stress(
    columns: dict[str, np.ndarray], units: dict[str, str], options: dict[str, Any]
) -> tuple[tuple[str, ...], tuple[ScalarResult, ...]]:
    strain_key = _named_quantity(columns, options, "strain_quantity")
    stress_key = _named_quantity(columns, options, "stress_quantity")
    _require_metal_tensile_units(units, strain_key, stress_key)
    modulus = _float_option(options, "youngs_modulus_pa")
    offset = _float_option(options, "offset_strain")
    start = _float_option(options, "search_start")
    end = _float_option(options, "search_end")
    if modulus <= 0 or offset < 0 or start >= end:
        raise CommonPipelineError("proof stress requires positive modulus and valid offset/domain")
    x = columns[strain_key]
    y = columns[stress_key]
    if np.any(np.diff(x) <= 0):
        raise CommonPipelineError("proof stress requires sorted unique strain")
    mask = (x >= start) & (x <= end)
    domain_x = x[mask]
    domain_y = y[mask]
    if len(domain_x) < 2:
        raise CommonPipelineError("proof stress search domain contains fewer than two points")
    difference = domain_y - modulus * (domain_x - offset)
    crossings = np.where((difference[:-1] >= 0) & (difference[1:] <= 0))[0]
    if not len(crossings):
        raise CommonPipelineError("offset proof line does not intersect the observed search domain")
    index = int(crossings[0])
    denominator = difference[index] - difference[index + 1]
    fraction = 0.0 if denominator == 0 else float(difference[index] / denominator)
    proof_strain = float(domain_x[index] + fraction * (domain_x[index + 1] - domain_x[index]))
    proof_stress = float(domain_y[index] + fraction * (domain_y[index + 1] - domain_y[index]))
    return (
        (f"offset proof intersection at strain={proof_strain} with offset={offset}",),
        (
            ScalarResult("proof_stress", "stress.proof", proof_stress, "Pa"),
            ScalarResult("proof_strain", "strain.proof", proof_strain, "1"),
            ScalarResult("proof_offset", "strain.offset", offset, "1"),
        ),
    )


def _engineering_to_true_plastic(
    columns: dict[str, np.ndarray],
    units: dict[str, str],
    options: dict[str, Any],
) -> tuple[dict[str, np.ndarray], tuple[str, ...], tuple[ScalarResult, ...]]:
    strain_key = _named_quantity(columns, options, "strain_quantity")
    stress_key = _named_quantity(columns, options, "stress_quantity")
    _require_metal_tensile_units(units, strain_key, stress_key)
    modulus = _float_option(options, "youngs_modulus_pa")
    necking_policy = _text_option(options, "necking_policy")
    manual_index = _int_option(options, "manual_necking_index")
    negative_policy = _text_option(options, "negative_plastic_policy")
    if modulus <= 0:
        raise CommonPipelineError("true/plastic conversion requires positive Young's modulus")
    strain = columns[strain_key]
    stress = columns[stress_key]
    if np.any(strain <= -1) or np.any(stress < 0) or np.any(np.diff(strain) <= 0):
        raise CommonPipelineError("engineering strain/stress must be ordered and physically valid")
    if necking_policy == "observed_full_domain":
        necking_index = len(strain) - 1
    elif necking_policy == "manual_index":
        necking_index = manual_index
    else:
        raise CommonPipelineError("unsupported necking policy")
    if not 1 <= necking_index < len(strain):
        raise CommonPipelineError("necking index must retain at least two observed points")
    result = {key: value[: necking_index + 1] for key, value in columns.items()}
    engineering_strain = result[strain_key]
    engineering_stress = result[stress_key]
    true_strain = np.log1p(engineering_strain)
    true_stress = engineering_stress * (1.0 + engineering_strain)
    true_plastic = true_strain - true_stress / modulus
    if negative_policy == "clip_zero":
        true_plastic = np.maximum(true_plastic, 0.0)
    elif negative_policy == "drop":
        keep = true_plastic > 0.0
        if int(np.sum(keep)) < 2:
            raise CommonPipelineError(
                "dropping non-positive plastic strain leaves fewer than two points"
            )
        result = {key: value[keep] for key, value in result.items()}
        true_strain = true_strain[keep]
        true_stress = true_stress[keep]
        true_plastic = true_plastic[keep]
    elif negative_policy != "retain":
        raise CommonPipelineError("unsupported negative plastic strain policy")
    result["strain.true"] = true_strain
    result["stress.true"] = true_stress
    result["strain.true_plastic"] = true_plastic
    units["strain.true"] = "1"
    units["stress.true"] = units[stress_key]
    units["strain.true_plastic"] = "1"
    return (
        result,
        (
            f"{necking_policy} necking boundary at source index {necking_index}",
            f"negative true plastic strain policy={negative_policy}",
            *(
                (
                    "observed_full_domain may include post-necking data; confirm a manual "
                    "candidate before constitutive identification",
                )
                if necking_policy == "observed_full_domain"
                else ()
            ),
        ),
        (
            ScalarResult("necking_index", "index.necking", float(necking_index), "1"),
            ScalarResult(
                "necking_engineering_strain",
                "strain.engineering.necking",
                float(strain[necking_index]),
                "1",
            ),
            ScalarResult(
                "necking_engineering_stress",
                "stress.engineering.necking",
                float(stress[necking_index]),
                units[stress_key],
            ),
        ),
    )


def _necking_candidate(
    columns: dict[str, np.ndarray], units: dict[str, str], options: dict[str, Any]
) -> tuple[tuple[str, ...], tuple[ScalarResult, ...]]:
    strain_key = _named_quantity(columns, options, "strain_quantity")
    stress_key = _named_quantity(columns, options, "stress_quantity")
    _require_metal_tensile_units(units, strain_key, stress_key)
    if options.get("method") != "peak_engineering_stress":
        raise CommonPipelineError("the reference necking candidate uses peak engineering stress")
    strain = columns[strain_key]
    stress = columns[stress_key]
    index = int(np.argmax(stress))
    if not 1 <= index < len(stress):
        raise CommonPipelineError("peak-stress necking candidate is outside a usable domain")
    return (
        ("automatic candidate only; no point was cropped or confirmed",),
        (
            ScalarResult("necking_candidate_index", "index.necking.candidate", float(index), "1"),
            ScalarResult(
                "necking_candidate_engineering_strain",
                "strain.engineering.necking.candidate",
                float(strain[index]),
                units[strain_key],
            ),
            ScalarResult(
                "necking_candidate_engineering_stress",
                "stress.engineering.necking.candidate",
                float(stress[index]),
                units[stress_key],
            ),
        ),
    )


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
    columns: dict[str, np.ndarray],
    units: dict[str, str],
    x_key: str,
    step: ProcessingStep,
) -> tuple[dict[str, np.ndarray], tuple[str, ...], tuple[ScalarResult, ...]]:
    definition = _METHODS.get(step.method_id)
    if definition is None:
        raise CommonPipelineError(f"unknown processing method {step.method_id}")
    _validate_options(step, definition)
    options = step.options
    if step.method_id == "rows.sort_unique":
        result, diagnostics = _sort_unique(columns, x_key, options)
        return result, diagnostics, ()
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
            (),
        )
    if step.method_id == "curve.scale_shift":
        quantity = _require_quantity(columns, options)
        scale = _float_option(options, "scale")
        offset = _float_option(options, "offset")
        if scale == 0:
            raise CommonPipelineError("scale cannot be zero")
        result = dict(columns)
        result[quantity] = columns[quantity] * scale + offset
        return result, (f"applied y={scale}*y+{offset} to {quantity}",), ()
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
        return result, ("piecewise-linear interpolation; extrapolation rejected",), ()
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
        return result, (f"centered reflected-edge moving average window={window}",), ()
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
        return result, (f"Savitzky-Golay window={window}, polynomial_order={order}",), ()
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
        return result, (f"cubic smoothing spline factor={smoothing}",), ()
    if step.method_id == "metal.elastic_modulus":
        diagnostics, scalars = _elastic_modulus(columns, units, options)
        return dict(columns), diagnostics, scalars
    if step.method_id == "metal.proof_stress":
        diagnostics, scalars = _proof_stress(columns, units, options)
        return dict(columns), diagnostics, scalars
    if step.method_id == "metal.necking_candidate":
        diagnostics, scalars = _necking_candidate(columns, units, options)
        return dict(columns), diagnostics, scalars
    if step.method_id == "metal.engineering_to_true_plastic":
        return _engineering_to_true_plastic(columns, units, options)
    if step.method_id == "metal.hardening_fit_extrapolate":
        try:
            fitted = fit_hardening_candidates(columns, units, options)
        except MetalHardeningError as error:
            raise CommonPipelineError(str(error)) from error
        units.update(fitted.units)
        return (
            fitted.columns,
            fitted.diagnostics,
            tuple(
                ScalarResult(item.key, item.quantity_semantics, item.value, item.unit)
                for item in fitted.scalars
            ),
        )
    if step.method_id == "polymer.log_time_resample":
        try:
            resampled = log_time_resample(columns, units, x_key, options)
        except PolymerViscoelasticError as error:
            raise CommonPipelineError(str(error)) from error
        units.update(resampled.units)
        return resampled.columns, resampled.diagnostics, ()
    if step.method_id == "polymer.prony_fit_compare":
        try:
            fitted_prony = fit_prony_candidates(columns, units, options)
        except PolymerViscoelasticError as error:
            raise CommonPipelineError(str(error)) from error
        units.update(fitted_prony.units)
        return (
            fitted_prony.columns,
            fitted_prony.diagnostics,
            tuple(
                ScalarResult(item.key, item.quantity_semantics, item.value, item.unit)
                for item in fitted_prony.scalars
            ),
        )
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
        current, diagnostics, scalar_results = _apply_step(
            current, units, profile.independent_quantity, step
        )
        if any(not np.all(np.isfinite(values)) for values in current.values()):
            raise CommonPipelineError(f"method {step.method_id} produced non-finite output")
        stages.append(
            _stage(
                ordinal,
                step.method_id,
                current,
                units,
                diagnostics,
                scalar_results,
            )
        )
    return ProcessingPreview(
        source_document_sha256=document.digest,
        mapping_profile_sha256=profile.digest,
        independent_quantity=profile.independent_quantity,
        stages=tuple(stages),
    )
