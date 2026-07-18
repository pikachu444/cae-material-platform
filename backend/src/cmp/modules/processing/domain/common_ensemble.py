"""Solver-neutral replicate alignment and pointwise curve statistics for T-53."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cmp.modules.datasets.domain.canonical_test_data import CanonicalTestDataDocument
from cmp.modules.processing.domain.common_pipeline import (
    COMMON_METHOD_VERSION,
    MAX_PREVIEW_POINTS,
    CommonPipelineError,
    CurveStage,
    MappingProfileContent,
    MethodDefinition,
    ProcessingStep,
    QuantitySeries,
    preview_pipeline,
)

ALIGNMENT_METHOD_ID = "curves.align_linear_intersection"
STATISTICS_METHOD_ID = "curves.pointwise_statistics"

ENSEMBLE_METHOD_REGISTRY: tuple[MethodDefinition, ...] = (
    MethodDefinition(
        method_id=ALIGNMENT_METHOD_ID,
        version=COMMON_METHOD_VERSION,
        label="Align replicate curves on observed intersection",
        description=(
            "Uses a shared linear grid inside every member domain and rejects extrapolation."
        ),
        option_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["point_count", "domain_policy", "extrapolation"],
            "properties": {
                "point_count": {"type": "integer", "minimum": 2, "maximum": 100000},
                "domain_policy": {"const": "intersection"},
                "extrapolation": {"const": "reject"},
            },
        },
    ),
    MethodDefinition(
        method_id=STATISTICS_METHOD_ID,
        version=COMMON_METHOD_VERSION,
        label="Pointwise replicate statistics",
        description=(
            "Retains members and computes mean, median, sample SD, MAD, IQR and 95% mean CI."
        ),
        option_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "standard_deviation_ddof": {"const": 1},
                "confidence_level": {"const": 0.95},
                "confidence_method": {"const": "normal_approximation"},
                "mad_scale": {"const": "unscaled"},
            },
        },
    ),
)


@dataclass(frozen=True, slots=True)
class EnsembleAlignmentOptions:
    point_count: int
    domain_policy: str = "intersection"
    extrapolation: str = "reject"

    def __post_init__(self) -> None:
        if not 2 <= self.point_count <= MAX_PREVIEW_POINTS:
            raise CommonPipelineError("ensemble point_count must be 2..100000")
        if self.domain_policy != "intersection" or self.extrapolation != "reject":
            raise CommonPipelineError(
                "common ensemble alignment only supports intersection with extrapolation reject"
            )


@dataclass(frozen=True, slots=True)
class EnsembleMember:
    ordinal: int
    source_document_sha256: str
    stage: CurveStage


@dataclass(frozen=True, slots=True)
class PointwiseStatistics:
    quantity: str
    unit: str
    mean: tuple[float, ...]
    median: tuple[float, ...]
    standard_deviation: tuple[float, ...]
    mad: tuple[float, ...]
    q1: tuple[float, ...]
    q3: tuple[float, ...]
    confidence_95_lower: tuple[float, ...]
    confidence_95_upper: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class EnsemblePreview:
    mapping_profile_sha256: str
    independent_quantity: str
    grid_unit: str
    grid: tuple[float, ...]
    members: tuple[EnsembleMember, ...]
    statistics: tuple[PointwiseStatistics, ...]
    diagnostics: tuple[str, ...]


def _series(stage: CurveStage) -> dict[str, QuantitySeries]:
    return {item.quantity: item for item in stage.series}


def preview_ensemble(
    documents: tuple[CanonicalTestDataDocument, ...],
    profile: MappingProfileContent,
    preprocessing_steps: tuple[ProcessingStep, ...],
    alignment: EnsembleAlignmentOptions,
) -> EnsemblePreview:
    """Preprocess each replicate, align on the observed intersection, and retain all curves."""

    if not 2 <= len(documents) <= 100:
        raise CommonPipelineError("ensemble preview requires 2..100 Test Data documents")
    previews = tuple(
        preview_pipeline(document, profile, preprocessing_steps) for document in documents
    )
    finals = tuple(value.stages[-1] for value in previews)
    mapped = tuple(_series(stage) for stage in finals)
    quantity_order = tuple(item.quantity for item in finals[0].series)
    if any(tuple(item.quantity for item in stage.series) != quantity_order for stage in finals):
        raise CommonPipelineError("ensemble members must expose the same ordered quantities")
    units = {item.quantity: item.unit for item in finals[0].series}
    if any(
        any(item.unit != units[item.quantity] for item in stage.series)
        for stage in finals[1:]
    ):
        raise CommonPipelineError("ensemble quantity units must match after Mapping Profile")
    x_values = tuple(
        np.asarray(member[profile.independent_quantity].values, dtype=np.float64)
        for member in mapped
    )
    if any(np.any(np.diff(values) <= 0) for values in x_values):
        raise CommonPipelineError(
            "ensemble alignment requires sorted unique independent values; add rows.sort_unique"
        )
    start = max(float(values[0]) for values in x_values)
    end = min(float(values[-1]) for values in x_values)
    if not start < end:
        raise CommonPipelineError("ensemble observed domains do not overlap")
    grid = np.linspace(start, end, alignment.point_count)
    members: list[EnsembleMember] = []
    aligned_by_quantity: dict[str, list[np.ndarray]] = {
        quantity: [] for quantity in quantity_order if quantity != profile.independent_quantity
    }
    for ordinal, (preview, member, x) in enumerate(zip(previews, mapped, x_values, strict=True)):
        aligned: list[QuantitySeries] = [
            QuantitySeries(
                profile.independent_quantity,
                units[profile.independent_quantity],
                tuple(float(value) for value in grid),
            )
        ]
        for quantity in quantity_order:
            if quantity == profile.independent_quantity:
                continue
            values = np.interp(grid, x, np.asarray(member[quantity].values, dtype=np.float64))
            aligned_by_quantity[quantity].append(values)
            aligned.append(
                QuantitySeries(quantity, units[quantity], tuple(float(value) for value in values))
            )
        members.append(
            EnsembleMember(
                ordinal=ordinal,
                source_document_sha256=preview.source_document_sha256,
                stage=CurveStage(
                    ordinal=0,
                    method_id=ALIGNMENT_METHOD_ID,
                    method_version=COMMON_METHOD_VERSION,
                    point_count=alignment.point_count,
                    series=tuple(aligned),
                    diagnostics=(
                        f"linear interpolation on observed intersection [{start}, {end}]",
                        "extrapolation rejected",
                    ),
                ),
            )
        )
    statistics: list[PointwiseStatistics] = []
    for quantity, curves in aligned_by_quantity.items():
        matrix = np.vstack(curves)
        mean = np.mean(matrix, axis=0)
        median = np.median(matrix, axis=0)
        standard_deviation = np.std(matrix, axis=0, ddof=1)
        mad = np.median(np.abs(matrix - median), axis=0)
        q1, q3 = np.quantile(matrix, [0.25, 0.75], axis=0, method="linear")
        margin = 1.96 * standard_deviation / np.sqrt(len(documents))
        statistics.append(
            PointwiseStatistics(
                quantity=quantity,
                unit=units[quantity],
                mean=tuple(float(value) for value in mean),
                median=tuple(float(value) for value in median),
                standard_deviation=tuple(float(value) for value in standard_deviation),
                mad=tuple(float(value) for value in mad),
                q1=tuple(float(value) for value in q1),
                q3=tuple(float(value) for value in q3),
                confidence_95_lower=tuple(float(value) for value in mean - margin),
                confidence_95_upper=tuple(float(value) for value in mean + margin),
            )
        )
    return EnsemblePreview(
        mapping_profile_sha256=profile.digest,
        independent_quantity=profile.independent_quantity,
        grid_unit=units[profile.independent_quantity],
        grid=tuple(float(value) for value in grid),
        members=tuple(members),
        statistics=tuple(statistics),
        diagnostics=(
            f"{len(documents)} immutable member curves retained",
            "pointwise sample standard deviation uses ddof=1",
            "MAD is unscaled median absolute deviation",
            "IQR uses linear q1/q3 quantiles",
            "95% mean confidence interval uses normal approximation",
        ),
    )
