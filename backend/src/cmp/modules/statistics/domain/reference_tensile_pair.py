"""Reference Statistics/QC calculation over two pinned tensile curve selections.

This deliberately small T-20 slice never aligns, resamples, extrapolates, smooths, or
otherwise changes a source curve.  A Plan names exactly two immutable, one-member Dataset
Selection revisions.  They are independent samples only when they identify distinct Test
Runs, and pointwise curve statistics are allowed only when the observed normalized strain
grids are exactly equal.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import cast
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.modules.datasets.domain.reference_tensile import CurvePoint

REFERENCE_TENSILE_PAIR_PLAN_KIND = "reference_tensile_pair_scalar_and_curve"
REFERENCE_TENSILE_PAIR_PLAN_SCHEMA = "urn:cmp:statistics:reference-tensile-pair-plan:1.0.0"
REFERENCE_TENSILE_PAIR_RESULT_SCHEMA = "urn:cmp:statistics:reference-tensile-pair-result:1.0.0"
REFERENCE_TENSILE_PAIR_CURVE_SCHEMA = (
    "urn:cmp:statistics:reference-tensile-pair-curve-parquet:1.0.0"
)
REFERENCE_TENSILE_PAIR_SCHEMA_VERSION = "1.0.0"
REFERENCE_TENSILE_PAIR_ASSUMPTION_PROFILE = "identical_observed_engineering_strain_grid"
REFERENCE_TENSILE_PAIR_GRID_POLICY = "exact_observed_grid_match_no_alignment"
REFERENCE_TENSILE_PAIR_SCALAR_FEATURE = "peak_engineering_stress_pa"
REFERENCE_TENSILE_PAIR_QUANTILE_METHOD = "linear_inclusive"
REFERENCE_TENSILE_PAIR_CI_STATUS = "not_provided_reference_pair"
MAX_REFERENCE_TENSILE_STATISTICS_POINTS = 100_000


class StatisticsError(Exception):
    """Base error for the typed Statistics/QC slice."""


class InvalidStatisticsRequest(StatisticsError, ValueError):
    """A plan or result violates the declared reference method."""


class StatisticsConflict(StatisticsError):
    """Pinned inputs, scopes, or immutable output state conflict."""


class StatisticsNotFound(StatisticsError):
    """A Statistics resource is absent or hidden in the tenant scope."""


class StatisticalRunStatus(StrEnum):
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class QcOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidStatisticsRequest(f"{name} must be non-zero")


def _label(value: str) -> None:
    if not value or value != value.strip() or len(value) > 160 or "\x00" in value:
        raise InvalidStatisticsRequest("plan_label must be trimmed and contain 1..160 characters")


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise InvalidStatisticsRequest(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class ReferenceTensilePairPlanContent:
    """An immutable reference plan that pins exactly two Selection revisions.

    Selection remains a deliberately one-member Dataset construct from T-19.  Keeping this
    pair at the Plan boundary avoids silently broadening that Selection contract while making
    the two sample inputs auditable and immutable.
    """

    plan_label: str
    first_selection_id: UUID
    first_selection_revision_id: UUID
    second_selection_id: UUID
    second_selection_revision_id: UUID

    def __post_init__(self) -> None:
        _label(self.plan_label)
        for name, value in (
            ("first_selection_id", self.first_selection_id),
            ("first_selection_revision_id", self.first_selection_revision_id),
            ("second_selection_id", self.second_selection_id),
            ("second_selection_revision_id", self.second_selection_revision_id),
        ):
            _uuid(name, value)
        if self.first_selection_revision_id == self.second_selection_revision_id:
            raise InvalidStatisticsRequest("the two Selection revisions must be distinct")


@dataclass(frozen=True, slots=True)
class ReferenceTensilePairScalarStatistics:
    """Explicit scalar statistics over one peak-stress value per specimen/Test Run."""

    first_peak_engineering_stress_pa: float
    second_peak_engineering_stress_pa: float
    mean_engineering_stress_pa: float
    sample_standard_deviation_engineering_stress_pa: float
    median_engineering_stress_pa: float
    median_absolute_deviation_engineering_stress_pa: float
    interquartile_range_engineering_stress_pa: float
    minimum_engineering_stress_pa: float
    maximum_engineering_stress_pa: float
    coefficient_of_variation: float | None

    def __post_init__(self) -> None:
        for name, value in (
            ("first_peak_engineering_stress_pa", self.first_peak_engineering_stress_pa),
            ("second_peak_engineering_stress_pa", self.second_peak_engineering_stress_pa),
            ("mean_engineering_stress_pa", self.mean_engineering_stress_pa),
            (
                "sample_standard_deviation_engineering_stress_pa",
                self.sample_standard_deviation_engineering_stress_pa,
            ),
            ("median_engineering_stress_pa", self.median_engineering_stress_pa),
            (
                "median_absolute_deviation_engineering_stress_pa",
                self.median_absolute_deviation_engineering_stress_pa,
            ),
            (
                "interquartile_range_engineering_stress_pa",
                self.interquartile_range_engineering_stress_pa,
            ),
            ("minimum_engineering_stress_pa", self.minimum_engineering_stress_pa),
            ("maximum_engineering_stress_pa", self.maximum_engineering_stress_pa),
        ):
            _finite(name, value)
            if value < 0.0:
                raise InvalidStatisticsRequest(f"{name} must be non-negative")
        if self.coefficient_of_variation is not None:
            _finite("coefficient_of_variation", self.coefficient_of_variation)
            if self.coefficient_of_variation < 0.0:
                raise InvalidStatisticsRequest("coefficient_of_variation must be non-negative")


@dataclass(frozen=True, slots=True)
class ReferenceTensilePairCurvePoint:
    """One typed pointwise result; its index comes only from an observed common grid."""

    engineering_strain: float
    mean_engineering_stress_pa: float
    sample_standard_deviation_engineering_stress_pa: float
    median_engineering_stress_pa: float
    minimum_engineering_stress_pa: float
    maximum_engineering_stress_pa: float

    def __post_init__(self) -> None:
        for name, value in (
            ("engineering_strain", self.engineering_strain),
            ("mean_engineering_stress_pa", self.mean_engineering_stress_pa),
            (
                "sample_standard_deviation_engineering_stress_pa",
                self.sample_standard_deviation_engineering_stress_pa,
            ),
            ("median_engineering_stress_pa", self.median_engineering_stress_pa),
            ("minimum_engineering_stress_pa", self.minimum_engineering_stress_pa),
            ("maximum_engineering_stress_pa", self.maximum_engineering_stress_pa),
        ):
            _finite(name, value)
            if value < 0.0:
                raise InvalidStatisticsRequest(f"{name} must be non-negative")


@dataclass(frozen=True, slots=True)
class ReferenceTensilePairStatistics:
    """The scalar and curve outputs of the fixed two-sample reference method."""

    scalar: ReferenceTensilePairScalarStatistics
    curve: tuple[ReferenceTensilePairCurvePoint, ...]

    def __post_init__(self) -> None:
        if not 2 <= len(self.curve) <= MAX_REFERENCE_TENSILE_STATISTICS_POINTS:
            raise InvalidStatisticsRequest("reference curve statistics require 2..100000 points")
        if any(
            self.curve[index].engineering_strain <= self.curve[index - 1].engineering_strain
            for index in range(1, len(self.curve))
        ):
            raise InvalidStatisticsRequest("reference curve statistics strain grid must increase")


@dataclass(frozen=True, slots=True)
class ReferenceTensilePairResultContent:
    """Typed immutable output content for one completed Statistical Run."""

    statistical_run_id: UUID
    plan_id: UUID
    plan_revision_id: UUID
    first_selection_id: UUID
    first_selection_revision_id: UUID
    first_dataset_id: UUID
    first_dataset_revision_id: UUID
    second_selection_id: UUID
    second_selection_revision_id: UUID
    second_dataset_id: UUID
    second_dataset_revision_id: UUID
    curve_artifact_id: UUID
    curve_sha256: str
    curve_point_count: int
    scalar: ReferenceTensilePairScalarStatistics

    def __post_init__(self) -> None:
        for name, value in (
            ("statistical_run_id", self.statistical_run_id),
            ("plan_id", self.plan_id),
            ("plan_revision_id", self.plan_revision_id),
            ("first_selection_id", self.first_selection_id),
            ("first_selection_revision_id", self.first_selection_revision_id),
            ("first_dataset_id", self.first_dataset_id),
            ("first_dataset_revision_id", self.first_dataset_revision_id),
            ("second_selection_id", self.second_selection_id),
            ("second_selection_revision_id", self.second_selection_revision_id),
            ("second_dataset_id", self.second_dataset_id),
            ("second_dataset_revision_id", self.second_dataset_revision_id),
            ("curve_artifact_id", self.curve_artifact_id),
        ):
            _uuid(name, value)
        if self.first_selection_revision_id == self.second_selection_revision_id:
            raise InvalidStatisticsRequest("result Selection revisions must be distinct")
        if self.first_dataset_revision_id == self.second_dataset_revision_id:
            raise InvalidStatisticsRequest("result Dataset revisions must be distinct")
        if len(self.curve_sha256) != 64 or any(
            value not in "0123456789abcdef" for value in self.curve_sha256
        ):
            raise InvalidStatisticsRequest("curve_sha256 must be a lowercase SHA-256 digest")
        if not 2 <= self.curve_point_count <= MAX_REFERENCE_TENSILE_STATISTICS_POINTS:
            raise InvalidStatisticsRequest("curve_point_count must be between 2 and 100000")


@dataclass(frozen=True, slots=True)
class QcObservation:
    """A fixed-shape QC fact, not a generic key/value or annotation payload."""

    check_code: str
    outcome: QcOutcome
    detail: str
    expected_point_count: int | None = None
    observed_point_count: int | None = None
    mismatch_index: int | None = None

    def __post_init__(self) -> None:
        if self.check_code not in {
            "distinct_test_runs",
            "identical_observed_engineering_strain_grid",
            "input_artifact_readable",
        }:
            raise InvalidStatisticsRequest("QC check_code is not supported by the reference plan")
        if not self.detail or self.detail != self.detail.strip() or len(self.detail) > 500:
            raise InvalidStatisticsRequest(
                "QC detail must be trimmed and contain 1..500 characters"
            )
        for name, value in (
            ("expected_point_count", self.expected_point_count),
            ("observed_point_count", self.observed_point_count),
            ("mismatch_index", self.mismatch_index),
        ):
            if value is not None and value < 0:
                raise InvalidStatisticsRequest(f"{name} must be non-negative when supplied")


def reference_tensile_pair_plan_canonical(
    value: ReferenceTensilePairPlanContent,
) -> dict[str, object]:
    return {
        "plan_kind": REFERENCE_TENSILE_PAIR_PLAN_KIND,
        "sample_count": 2,
        "first_selection_id": str(value.first_selection_id),
        "first_selection_revision_id": str(value.first_selection_revision_id),
        "second_selection_id": str(value.second_selection_id),
        "second_selection_revision_id": str(value.second_selection_revision_id),
        "input_schema_ref": "urn:cmp:datasets:reference-tensile-normalized-parquet:1.0.0",
        "scalar_feature": REFERENCE_TENSILE_PAIR_SCALAR_FEATURE,
        "curve_grid_policy": REFERENCE_TENSILE_PAIR_GRID_POLICY,
        "assumption_profile": REFERENCE_TENSILE_PAIR_ASSUMPTION_PROFILE,
        "quantile_method": REFERENCE_TENSILE_PAIR_QUANTILE_METHOD,
        "confidence_interval_status": REFERENCE_TENSILE_PAIR_CI_STATUS,
        "curve_output_schema_ref": REFERENCE_TENSILE_PAIR_CURVE_SCHEMA,
    }


def reference_tensile_pair_result_canonical(
    value: ReferenceTensilePairResultContent,
) -> dict[str, object]:
    """Canonical typed result document used only for revision hashing."""

    return {
        "result_kind": REFERENCE_TENSILE_PAIR_PLAN_KIND,
        "statistical_run_id": str(value.statistical_run_id),
        "plan_id": str(value.plan_id),
        "plan_revision_id": str(value.plan_revision_id),
        "first_selection_id": str(value.first_selection_id),
        "first_selection_revision_id": str(value.first_selection_revision_id),
        "first_dataset_id": str(value.first_dataset_id),
        "first_dataset_revision_id": str(value.first_dataset_revision_id),
        "second_selection_id": str(value.second_selection_id),
        "second_selection_revision_id": str(value.second_selection_revision_id),
        "second_dataset_id": str(value.second_dataset_id),
        "second_dataset_revision_id": str(value.second_dataset_revision_id),
        "sample_count": 2,
        "scalar_feature": REFERENCE_TENSILE_PAIR_SCALAR_FEATURE,
        "curve_artifact_id": str(value.curve_artifact_id),
        "curve_sha256": value.curve_sha256,
        "curve_point_count": value.curve_point_count,
        "mean_engineering_stress_pa": value.scalar.mean_engineering_stress_pa,
        "sample_standard_deviation_engineering_stress_pa": (
            value.scalar.sample_standard_deviation_engineering_stress_pa
        ),
        "median_engineering_stress_pa": value.scalar.median_engineering_stress_pa,
        "median_absolute_deviation_engineering_stress_pa": (
            value.scalar.median_absolute_deviation_engineering_stress_pa
        ),
        "interquartile_range_engineering_stress_pa": (
            value.scalar.interquartile_range_engineering_stress_pa
        ),
        "minimum_engineering_stress_pa": value.scalar.minimum_engineering_stress_pa,
        "maximum_engineering_stress_pa": value.scalar.maximum_engineering_stress_pa,
        "coefficient_of_variation": value.scalar.coefficient_of_variation,
        "first_peak_engineering_stress_pa": value.scalar.first_peak_engineering_stress_pa,
        "second_peak_engineering_stress_pa": value.scalar.second_peak_engineering_stress_pa,
        "assumption_profile": REFERENCE_TENSILE_PAIR_ASSUMPTION_PROFILE,
        "curve_grid_policy": REFERENCE_TENSILE_PAIR_GRID_POLICY,
        "quantile_method": REFERENCE_TENSILE_PAIR_QUANTILE_METHOD,
        "confidence_interval_status": REFERENCE_TENSILE_PAIR_CI_STATUS,
    }


def _quantile_linear_inclusive(values: tuple[float, float], probability: float) -> float:
    """The declared Hyndman/Fan-style inclusive linear quantile for exactly two values."""

    lower, upper = sorted(values)
    return lower + probability * (upper - lower)


def _sample_statistics(first: float, second: float) -> ReferenceTensilePairScalarStatistics:
    _finite("first peak engineering stress", first)
    _finite("second peak engineering stress", second)
    if first < 0.0 or second < 0.0:
        raise InvalidStatisticsRequest("reference tensile engineering stress must be non-negative")
    values = (first, second)
    mean = (first + second) / 2.0
    sample_standard_deviation = math.sqrt((first - second) ** 2 / 2.0)
    median = _quantile_linear_inclusive(values, 0.5)
    deviations = (abs(first - median), abs(second - median))
    mad = _quantile_linear_inclusive(deviations, 0.5)
    interquartile_range = _quantile_linear_inclusive(values, 0.75) - _quantile_linear_inclusive(
        values, 0.25
    )
    return ReferenceTensilePairScalarStatistics(
        first_peak_engineering_stress_pa=first,
        second_peak_engineering_stress_pa=second,
        mean_engineering_stress_pa=mean,
        sample_standard_deviation_engineering_stress_pa=sample_standard_deviation,
        median_engineering_stress_pa=median,
        median_absolute_deviation_engineering_stress_pa=mad,
        interquartile_range_engineering_stress_pa=interquartile_range,
        minimum_engineering_stress_pa=min(values),
        maximum_engineering_stress_pa=max(values),
        coefficient_of_variation=(sample_standard_deviation / mean if mean > 0.0 else None),
    )


def observed_grid_qc(
    first: tuple[CurvePoint, ...], second: tuple[CurvePoint, ...]
) -> QcObservation:
    """Verify equality of observed normalized strain values with no tolerance or alignment."""

    if len(first) != len(second):
        return QcObservation(
            check_code="identical_observed_engineering_strain_grid",
            outcome=QcOutcome.FAILED,
            detail="Curve point counts differ; no implicit alignment or resampling was performed.",
            expected_point_count=len(first),
            observed_point_count=len(second),
        )
    for index, (left, right) in enumerate(zip(first, second, strict=True)):
        if left.engineering_strain != right.engineering_strain:
            return QcObservation(
                check_code="identical_observed_engineering_strain_grid",
                outcome=QcOutcome.FAILED,
                detail=(
                    "Observed engineering-strain values differ; no implicit alignment or "
                    "resampling was performed."
                ),
                expected_point_count=len(first),
                observed_point_count=len(second),
                mismatch_index=index,
            )
    return QcObservation(
        check_code="identical_observed_engineering_strain_grid",
        outcome=QcOutcome.PASSED,
        detail="Both normalized curves use the same observed engineering-strain grid.",
        expected_point_count=len(first),
        observed_point_count=len(second),
    )


def calculate_reference_tensile_pair_statistics(
    first: tuple[CurvePoint, ...], second: tuple[CurvePoint, ...]
) -> ReferenceTensilePairStatistics:
    """Calculate typed scalar and pointwise values only after exact-grid QC has passed."""

    grid = observed_grid_qc(first, second)
    if grid.outcome is not QcOutcome.PASSED:
        raise StatisticsConflict(grid.detail)
    if not 2 <= len(first) <= MAX_REFERENCE_TENSILE_STATISTICS_POINTS:
        raise InvalidStatisticsRequest("reference curve statistics require 2..100000 points")
    scalar = _sample_statistics(
        max(point.engineering_stress for point in first),
        max(point.engineering_stress for point in second),
    )
    curve = tuple(
        ReferenceTensilePairCurvePoint(
            engineering_strain=left.engineering_strain,
            mean_engineering_stress_pa=(left.engineering_stress + right.engineering_stress) / 2.0,
            sample_standard_deviation_engineering_stress_pa=math.sqrt(
                (left.engineering_stress - right.engineering_stress) ** 2 / 2.0
            ),
            median_engineering_stress_pa=(left.engineering_stress + right.engineering_stress) / 2.0,
            minimum_engineering_stress_pa=min(left.engineering_stress, right.engineering_stress),
            maximum_engineering_stress_pa=max(left.engineering_stress, right.engineering_stress),
        )
        for left, right in zip(first, second, strict=True)
    )
    return ReferenceTensilePairStatistics(scalar=scalar, curve=curve)


_write_parquet_table = cast(Callable[..., None], pq.write_table)
_read_parquet_table = cast(Callable[..., pa.Table], pq.read_table)


def reference_tensile_pair_curve_parquet_bytes(
    values: tuple[ReferenceTensilePairCurvePoint, ...],
) -> bytes:
    """Encode the typed pointwise output as an immutable derived Artifact."""

    if not 2 <= len(values) <= MAX_REFERENCE_TENSILE_STATISTICS_POINTS:
        raise InvalidStatisticsRequest("reference curve statistics require 2..100000 points")
    table = pa.table(
        {
            "engineering_strain": pa.array(
                [item.engineering_strain for item in values], type=pa.float64()
            ),
            "mean_engineering_stress_pa": pa.array(
                [item.mean_engineering_stress_pa for item in values], type=pa.float64()
            ),
            "sample_standard_deviation_engineering_stress_pa": pa.array(
                [item.sample_standard_deviation_engineering_stress_pa for item in values],
                type=pa.float64(),
            ),
            "median_engineering_stress_pa": pa.array(
                [item.median_engineering_stress_pa for item in values], type=pa.float64()
            ),
            "minimum_engineering_stress_pa": pa.array(
                [item.minimum_engineering_stress_pa for item in values], type=pa.float64()
            ),
            "maximum_engineering_stress_pa": pa.array(
                [item.maximum_engineering_stress_pa for item in values], type=pa.float64()
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


def reference_tensile_pair_curve_from_parquet(
    value: bytes,
) -> tuple[ReferenceTensilePairCurvePoint, ...]:
    """Read exactly the public typed curve-result columns and reject malformed artifacts."""

    columns = (
        "engineering_strain",
        "mean_engineering_stress_pa",
        "sample_standard_deviation_engineering_stress_pa",
        "median_engineering_stress_pa",
        "minimum_engineering_stress_pa",
        "maximum_engineering_stress_pa",
    )
    try:
        table = _read_parquet_table(pa.BufferReader(value), columns=list(columns))
    except Exception as error:
        raise InvalidStatisticsRequest(
            "statistics result Artifact is not the reference typed Parquet schema"
        ) from error
    if tuple(table.column_names) != columns:
        raise InvalidStatisticsRequest("statistics result Artifact channel names are invalid")
    values = tuple(
        ReferenceTensilePairCurvePoint(
            engineering_strain=float(row[0]),
            mean_engineering_stress_pa=float(row[1]),
            sample_standard_deviation_engineering_stress_pa=float(row[2]),
            median_engineering_stress_pa=float(row[3]),
            minimum_engineering_stress_pa=float(row[4]),
            maximum_engineering_stress_pa=float(row[5]),
        )
        for row in zip(*(table.column(column).to_pylist() for column in columns), strict=True)
    )
    return ReferenceTensilePairStatistics(
        scalar=_sample_statistics(0.0, 0.0),
        curve=values,
    ).curve
