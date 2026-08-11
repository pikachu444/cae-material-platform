"""Statistics over independent aligned tensile replicate Dataset revisions."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.modules.datasets.domain.curve_metadata import (
    CURVE_DEFINITION_PARQUET_KEY,
    CURVE_DEFINITION_SHA256_PARQUET_KEY,
    AxisRole,
    BoundDirection,
    Coverage,
    CurveChannel,
    CurveDefinition,
    CurveDeviation,
    CurveSeries,
    DeviationKind,
    DeviationScope,
    OriginalUnit,
    UnitContract,
    ValueBasis,
    curve_definition_json_bytes,
)
from cmp.modules.datasets.domain.reference_tensile import CurvePoint
from cmp.modules.statistics.domain.reference_tensile_pair import (
    InvalidStatisticsRequest,
    QcObservation,
    QcOutcome,
    StatisticsConflict,
)
from cmp.modules.units.domain.system import DimensionId

REFERENCE_TENSILE_REPLICATE_PLAN_KIND = "reference_tensile_replicate_scalar_and_curve"
REFERENCE_TENSILE_REPLICATE_PLAN_SCHEMA = (
    "urn:cmp:statistics:reference-tensile-replicate-plan:1.0.0"
)
REFERENCE_TENSILE_REPLICATE_RESULT_SCHEMA = (
    "urn:cmp:statistics:reference-tensile-replicate-result:1.0.0"
)
REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA_V1 = (
    "urn:cmp:statistics:reference-tensile-replicate-curve-parquet:1.0.0"
)
REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA = (
    "urn:cmp:statistics:reference-tensile-replicate-curve-parquet:1.1.0"
)
REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMAS = frozenset(
    {REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA_V1, REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA}
)
REFERENCE_TENSILE_REPLICATE_SCHEMA_VERSION = "1.0.0"
REFERENCE_TENSILE_REPLICATE_GRID_POLICY = "exact_processed_grid_match_no_alignment"
REFERENCE_TENSILE_REPLICATE_CI_METHOD = "student_t_95_two_sided"
REFERENCE_TENSILE_REPLICATE_QUANTILE_METHOD = "linear_inclusive"
REFERENCE_TENSILE_REPLICATE_SCALAR_FEATURE = "peak_engineering_stress_pa"
MIN_REFERENCE_TENSILE_REPLICATES = 2
MAX_REFERENCE_TENSILE_REPLICATES = 50
MAX_REFERENCE_TENSILE_REPLICATE_POINTS = 100_000

# Two-sided 95% Student-t critical values for df=1..49. The bounded reference Selection supports
# at most 50 independent Test Runs, so a finite reviewed table is clearer than a hidden dependency.
_T_975 = (
    12.7062,
    4.3027,
    3.1824,
    2.7764,
    2.5706,
    2.4469,
    2.3646,
    2.3060,
    2.2622,
    2.2281,
    2.2010,
    2.1788,
    2.1604,
    2.1448,
    2.1314,
    2.1199,
    2.1098,
    2.1009,
    2.0930,
    2.0860,
    2.0796,
    2.0739,
    2.0687,
    2.0639,
    2.0595,
    2.0555,
    2.0518,
    2.0484,
    2.0452,
    2.0423,
    2.0395,
    2.0369,
    2.0345,
    2.0322,
    2.0301,
    2.0281,
    2.0262,
    2.0244,
    2.0227,
    2.0211,
    2.0195,
    2.0181,
    2.0167,
    2.0154,
    2.0141,
    2.0129,
    2.0117,
    2.0106,
    2.0096,
)


def _finite_nonnegative(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise InvalidStatisticsRequest(f"{name} must be finite and non-negative")


def _quantile(values: tuple[float, ...], probability: float) -> float:
    ordered = tuple(sorted(values))
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidStatisticsRequest(f"{name} must be non-zero")


@dataclass(frozen=True, slots=True)
class ReferenceTensileReplicatePlanContent:
    """Immutable plan input: one concrete multi-member Selection revision."""

    plan_label: str
    selection_id: UUID
    selection_revision_id: UUID
    sample_count: int
    curve_output_schema_ref: str = REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA

    def __post_init__(self) -> None:
        if (
            not self.plan_label
            or self.plan_label != self.plan_label.strip()
            or len(self.plan_label) > 160
            or "\x00" in self.plan_label
        ):
            raise InvalidStatisticsRequest(
                "plan_label must be trimmed and contain 1..160 characters"
            )
        _uuid("selection_id", self.selection_id)
        _uuid("selection_revision_id", self.selection_revision_id)
        if (
            not MIN_REFERENCE_TENSILE_REPLICATES
            <= self.sample_count
            <= MAX_REFERENCE_TENSILE_REPLICATES
        ):
            raise InvalidStatisticsRequest("sample_count must be between 2 and 50")
        if self.curve_output_schema_ref not in REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMAS:
            raise InvalidStatisticsRequest("replicate curve output schema is not supported")


def reference_tensile_replicate_plan_canonical(
    value: ReferenceTensileReplicatePlanContent,
) -> dict[str, object]:
    """Return the complete declared method contract used for revision hashing."""

    return {
        "plan_kind": REFERENCE_TENSILE_REPLICATE_PLAN_KIND,
        "selection_id": str(value.selection_id),
        "selection_revision_id": str(value.selection_revision_id),
        "sample_count": value.sample_count,
        "required_input_representation": "processed",
        "scalar_feature": REFERENCE_TENSILE_REPLICATE_SCALAR_FEATURE,
        "curve_grid_policy": REFERENCE_TENSILE_REPLICATE_GRID_POLICY,
        "quantile_method": REFERENCE_TENSILE_REPLICATE_QUANTILE_METHOD,
        "confidence_interval_method": REFERENCE_TENSILE_REPLICATE_CI_METHOD,
        "curve_output_schema_ref": value.curve_output_schema_ref,
    }


@dataclass(frozen=True, slots=True)
class ReplicateScalarStatistics:
    sample_count: int
    mean: float
    sample_standard_deviation: float
    median: float
    median_absolute_deviation: float
    interquartile_range: float
    minimum: float
    maximum: float
    coefficient_of_variation: float | None
    mean_confidence_interval_lower_95: float
    mean_confidence_interval_upper_95: float

    def __post_init__(self) -> None:
        if (
            not MIN_REFERENCE_TENSILE_REPLICATES
            <= self.sample_count
            <= MAX_REFERENCE_TENSILE_REPLICATES
        ):
            raise InvalidStatisticsRequest("replicate sample_count must be between 2 and 50")
        for name, value in (
            ("mean", self.mean),
            ("sample_standard_deviation", self.sample_standard_deviation),
            ("median", self.median),
            ("median_absolute_deviation", self.median_absolute_deviation),
            ("interquartile_range", self.interquartile_range),
            ("minimum", self.minimum),
            ("maximum", self.maximum),
            ("mean_confidence_interval_lower_95", self.mean_confidence_interval_lower_95),
            ("mean_confidence_interval_upper_95", self.mean_confidence_interval_upper_95),
        ):
            _finite_nonnegative(name, value)
        if self.coefficient_of_variation is not None:
            _finite_nonnegative("coefficient_of_variation", self.coefficient_of_variation)


@dataclass(frozen=True, slots=True)
class ReplicateCurvePoint:
    engineering_strain: float
    stress: ReplicateScalarStatistics


@dataclass(frozen=True, slots=True)
class ReferenceTensileReplicateStatistics:
    peak_engineering_stress_pa: ReplicateScalarStatistics
    curve: tuple[ReplicateCurvePoint, ...]

    def __post_init__(self) -> None:
        if not 2 <= len(self.curve) <= MAX_REFERENCE_TENSILE_REPLICATE_POINTS:
            raise InvalidStatisticsRequest("replicate curve statistics require 2..100000 points")
        if any(
            self.curve[index].engineering_strain <= self.curve[index - 1].engineering_strain
            for index in range(1, len(self.curve))
        ):
            raise InvalidStatisticsRequest("replicate statistics grid must strictly increase")


@dataclass(frozen=True, slots=True)
class ReferenceTensileReplicateResultContent:
    """Immutable scalar summary and typed pointwise Artifact reference for one run."""

    statistical_run_id: UUID
    plan_id: UUID
    plan_revision_id: UUID
    selection_id: UUID
    selection_revision_id: UUID
    curve_artifact_id: UUID
    curve_sha256: str
    curve_point_count: int
    peak_engineering_stress_pa: ReplicateScalarStatistics

    def __post_init__(self) -> None:
        for name, value in (
            ("statistical_run_id", self.statistical_run_id),
            ("plan_id", self.plan_id),
            ("plan_revision_id", self.plan_revision_id),
            ("selection_id", self.selection_id),
            ("selection_revision_id", self.selection_revision_id),
            ("curve_artifact_id", self.curve_artifact_id),
        ):
            _uuid(name, value)
        if len(self.curve_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.curve_sha256
        ):
            raise InvalidStatisticsRequest("curve_sha256 must be a lowercase SHA-256 digest")
        if not 2 <= self.curve_point_count <= MAX_REFERENCE_TENSILE_REPLICATE_POINTS:
            raise InvalidStatisticsRequest("curve_point_count must be between 2 and 100000")


def reference_tensile_replicate_result_canonical(
    value: ReferenceTensileReplicateResultContent,
) -> dict[str, object]:
    """Return the complete typed result document used by immutable revision hashing."""

    peak = value.peak_engineering_stress_pa
    return {
        "result_kind": REFERENCE_TENSILE_REPLICATE_PLAN_KIND,
        "statistical_run_id": str(value.statistical_run_id),
        "plan_id": str(value.plan_id),
        "plan_revision_id": str(value.plan_revision_id),
        "selection_id": str(value.selection_id),
        "selection_revision_id": str(value.selection_revision_id),
        "sample_count": peak.sample_count,
        "scalar_feature": REFERENCE_TENSILE_REPLICATE_SCALAR_FEATURE,
        "curve_artifact_id": str(value.curve_artifact_id),
        "curve_sha256": value.curve_sha256,
        "curve_point_count": value.curve_point_count,
        "mean_engineering_stress_pa": peak.mean,
        "sample_standard_deviation_engineering_stress_pa": peak.sample_standard_deviation,
        "median_engineering_stress_pa": peak.median,
        "median_absolute_deviation_engineering_stress_pa": peak.median_absolute_deviation,
        "interquartile_range_engineering_stress_pa": peak.interquartile_range,
        "minimum_engineering_stress_pa": peak.minimum,
        "maximum_engineering_stress_pa": peak.maximum,
        "coefficient_of_variation": peak.coefficient_of_variation,
        "mean_confidence_interval_lower_95_pa": peak.mean_confidence_interval_lower_95,
        "mean_confidence_interval_upper_95_pa": peak.mean_confidence_interval_upper_95,
        "curve_grid_policy": REFERENCE_TENSILE_REPLICATE_GRID_POLICY,
        "quantile_method": REFERENCE_TENSILE_REPLICATE_QUANTILE_METHOD,
        "confidence_interval_method": REFERENCE_TENSILE_REPLICATE_CI_METHOD,
    }


def calculate_scalar_statistics(values: tuple[float, ...]) -> ReplicateScalarStatistics:
    if not MIN_REFERENCE_TENSILE_REPLICATES <= len(values) <= MAX_REFERENCE_TENSILE_REPLICATES:
        raise InvalidStatisticsRequest("replicate statistics require 2..50 independent values")
    for value in values:
        _finite_nonnegative("replicate value", value)
    count = len(values)
    mean = math.fsum(values) / count
    variance = math.fsum((value - mean) ** 2 for value in values) / (count - 1)
    sample_sd = math.sqrt(max(0.0, variance))
    median = _quantile(values, 0.5)
    mad = _quantile(tuple(abs(value - median) for value in values), 0.5)
    iqr = _quantile(values, 0.75) - _quantile(values, 0.25)
    half_width = _T_975[count - 2] * sample_sd / math.sqrt(count)
    return ReplicateScalarStatistics(
        sample_count=count,
        mean=mean,
        sample_standard_deviation=sample_sd,
        median=median,
        median_absolute_deviation=mad,
        interquartile_range=iqr,
        minimum=min(values),
        maximum=max(values),
        coefficient_of_variation=sample_sd / mean if mean > 0.0 else None,
        mean_confidence_interval_lower_95=max(0.0, mean - half_width),
        mean_confidence_interval_upper_95=mean + half_width,
    )


def exact_replicate_grid_qc(
    curves: tuple[tuple[CurvePoint, ...], ...],
) -> QcObservation:
    if not MIN_REFERENCE_TENSILE_REPLICATES <= len(curves) <= MAX_REFERENCE_TENSILE_REPLICATES:
        raise InvalidStatisticsRequest("grid QC requires 2..50 replicate curves")
    expected = curves[0]
    for ordinal, observed in enumerate(curves[1:], start=1):
        if len(observed) != len(expected):
            return QcObservation(
                check_code="identical_observed_engineering_strain_grid",
                outcome=QcOutcome.FAILED,
                detail=(
                    f"Replicate member {ordinal} point count differs; Statistics performed no "
                    "alignment."
                ),
                expected_point_count=len(expected),
                observed_point_count=len(observed),
            )
        for index, (left, right) in enumerate(zip(expected, observed, strict=True)):
            if left.engineering_strain != right.engineering_strain:
                return QcObservation(
                    check_code="identical_observed_engineering_strain_grid",
                    outcome=QcOutcome.FAILED,
                    detail=(
                        f"Replicate member {ordinal} grid differs; Statistics performed no "
                        "alignment."
                    ),
                    expected_point_count=len(expected),
                    observed_point_count=len(observed),
                    mismatch_index=index,
                )
    return QcObservation(
        check_code="identical_observed_engineering_strain_grid",
        outcome=QcOutcome.PASSED,
        detail="All processed replicate curves use the exact same engineering-strain grid.",
        expected_point_count=len(expected),
        observed_point_count=len(expected),
    )


def calculate_reference_tensile_replicate_statistics(
    curves: tuple[tuple[CurvePoint, ...], ...],
) -> ReferenceTensileReplicateStatistics:
    qc = exact_replicate_grid_qc(curves)
    if qc.outcome is not QcOutcome.PASSED:
        raise StatisticsConflict(qc.detail)
    if not 2 <= len(curves[0]) <= MAX_REFERENCE_TENSILE_REPLICATE_POINTS:
        raise InvalidStatisticsRequest("replicate curves require 2..100000 grid points")
    peak = calculate_scalar_statistics(
        tuple(max(point.engineering_stress for point in curve) for curve in curves)
    )
    result = tuple(
        ReplicateCurvePoint(
            engineering_strain=curves[0][index].engineering_strain,
            stress=calculate_scalar_statistics(
                tuple(curve[index].engineering_stress for curve in curves)
            ),
        )
        for index in range(len(curves[0]))
    )
    return ReferenceTensileReplicateStatistics(peak_engineering_stress_pa=peak, curve=result)


_write_parquet_table = cast(Callable[..., None], pq.write_table)
_read_parquet_table = cast(Callable[..., pa.Table], pq.read_table)


def reference_tensile_replicate_curve_definition() -> CurveDefinition:
    strain = CurveChannel(
        key="engineering_strain",
        label="Engineering strain",
        quantity_semantics="mechanics.strain.engineering",
        axis_role=AxisRole.INDEPENDENT,
        unit_contract=UnitContract.COMMON,
        dimension=DimensionId.STRAIN,
        original_units=(OriginalUnit("1", "1"),),
        normalized_unit="1",
        display_unit="1",
        display_scale="1",
        display_offset="0",
        value_basis=ValueBasis.DERIVED,
    )
    mean = CurveChannel(
        key="mean_engineering_stress_pa",
        label="Mean engineering stress",
        quantity_semantics="mechanics.stress.engineering",
        axis_role=AxisRole.DEPENDENT,
        unit_contract=UnitContract.COMMON,
        dimension=DimensionId.FORCE_PER_AREA,
        original_units=(OriginalUnit("Pa", "1"),),
        normalized_unit="Pa",
        display_unit="MPa",
        display_scale="0.000001",
        display_offset="0",
        value_basis=ValueBasis.DERIVED,
    )
    median = CurveChannel(
        key="median_engineering_stress_pa",
        label="Median engineering stress",
        quantity_semantics="mechanics.stress.engineering",
        axis_role=AxisRole.AUXILIARY,
        unit_contract=UnitContract.COMMON,
        dimension=DimensionId.FORCE_PER_AREA,
        original_units=(OriginalUnit("Pa", "1"),),
        normalized_unit="Pa",
        display_unit="MPa",
        display_scale="0.000001",
        display_offset="0",
        value_basis=ValueBasis.DERIVED,
    )
    def _deviation(
        *,
        key: str,
        kind: DeviationKind,
        method_id: str,
        unit: str,
        series_key: str,
        bound_direction: BoundDirection = BoundDirection.NONE,
        band_group: str | None = None,
        confidence_level: float | None = None,
        coverage: Coverage | None = None,
        ddof: int | None = None,
    ) -> CurveDeviation:
        return CurveDeviation(
            key=key,
            target_channel_key="mean_engineering_stress_pa",
            scope=DeviationScope.POINTWISE,
            kind=kind,
            method_id=method_id,
            method_version="1.0.0",
            unit=unit,
            bound_direction=bound_direction,
            band_group=band_group,
            series_key=series_key,
            source_count_series_key="sample_count",
            confidence_level=confidence_level,
            coverage=coverage,
            ddof=ddof,
        )
    return CurveDefinition(
        channels=(strain, mean, median),
        deviations=(
            _deviation(
                key="sample_standard_deviation_engineering_stress",
                kind=DeviationKind.STANDARD_DEVIATION,
                method_id="sample.standard_deviation",
                unit="Pa",
                series_key="sample_standard_deviation_engineering_stress_pa",
                ddof=1,
            ),
            _deviation(
                key="median_absolute_deviation_engineering_stress",
                kind=DeviationKind.MEDIAN_ABSOLUTE_DEVIATION,
                method_id="median_absolute_deviation.unscaled",
                unit="Pa",
                series_key="median_absolute_deviation_engineering_stress_pa",
            ),
            _deviation(
                key="interquartile_range_engineering_stress",
                kind=DeviationKind.INTERQUARTILE_RANGE,
                method_id="quantile.linear_inclusive.iqr",
                unit="Pa",
                series_key="interquartile_range_engineering_stress_pa",
            ),
            _deviation(
                key="coefficient_of_variation",
                kind=DeviationKind.COEFFICIENT_OF_VARIATION,
                method_id="sample.standard_deviation_over_mean",
                unit="1",
                series_key="coefficient_of_variation",
                ddof=1,
            ),
            _deviation(
                key="minimum_engineering_stress",
                kind=DeviationKind.RANGE_BOUND,
                method_id="observed.minimum_maximum",
                unit="Pa",
                bound_direction=BoundDirection.LOWER,
                band_group="observed_stress_range",
                series_key="minimum_engineering_stress_pa",
            ),
            _deviation(
                key="maximum_engineering_stress",
                kind=DeviationKind.RANGE_BOUND,
                method_id="observed.minimum_maximum",
                unit="Pa",
                bound_direction=BoundDirection.UPPER,
                band_group="observed_stress_range",
                series_key="maximum_engineering_stress_pa",
            ),
            _deviation(
                key="mean_confidence_interval_lower_95",
                kind=DeviationKind.CONFIDENCE_BOUND,
                method_id="student_t.mean_two_sided",
                unit="Pa",
                bound_direction=BoundDirection.LOWER,
                band_group="mean_confidence_interval_95",
                series_key="mean_confidence_interval_lower_95_pa",
                confidence_level=0.95,
                coverage=Coverage.POINTWISE,
                ddof=1,
            ),
            _deviation(
                key="mean_confidence_interval_upper_95",
                kind=DeviationKind.CONFIDENCE_BOUND,
                method_id="student_t.mean_two_sided",
                unit="Pa",
                bound_direction=BoundDirection.UPPER,
                band_group="mean_confidence_interval_95",
                series_key="mean_confidence_interval_upper_95_pa",
                confidence_level=0.95,
                coverage=Coverage.POINTWISE,
                ddof=1,
            ),
        ),
    )


def reference_tensile_replicate_curve_series(
    values: tuple[ReplicateCurvePoint, ...],
) -> CurveSeries:
    return CurveSeries(
        definition=reference_tensile_replicate_curve_definition(),
        channels={
            "engineering_strain": tuple(item.engineering_strain for item in values),
            "mean_engineering_stress_pa": tuple(item.stress.mean for item in values),
            "median_engineering_stress_pa": tuple(item.stress.median for item in values),
        },
        deviations={
            "sample_standard_deviation_engineering_stress_pa": tuple(
                item.stress.sample_standard_deviation for item in values
            ),
            "median_absolute_deviation_engineering_stress_pa": tuple(
                item.stress.median_absolute_deviation for item in values
            ),
            "interquartile_range_engineering_stress_pa": tuple(
                item.stress.interquartile_range for item in values
            ),
            "coefficient_of_variation": tuple(
                item.stress.coefficient_of_variation for item in values
            ),
            "minimum_engineering_stress_pa": tuple(item.stress.minimum for item in values),
            "maximum_engineering_stress_pa": tuple(item.stress.maximum for item in values),
            "mean_confidence_interval_lower_95_pa": tuple(
                item.stress.mean_confidence_interval_lower_95 for item in values
            ),
            "mean_confidence_interval_upper_95_pa": tuple(
                item.stress.mean_confidence_interval_upper_95 for item in values
            ),
        },
        source_counts={"sample_count": tuple(item.stress.sample_count for item in values)},
    )


def reference_tensile_replicate_curve_parquet_bytes(
    values: tuple[ReplicateCurvePoint, ...],
    *,
    schema_ref: str = REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA,
) -> bytes:
    """Encode the complete pointwise statistics as a typed immutable Artifact."""

    if not 2 <= len(values) <= MAX_REFERENCE_TENSILE_REPLICATE_POINTS:
        raise InvalidStatisticsRequest("replicate curve statistics require 2..100000 points")
    if schema_ref not in REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMAS:
        raise InvalidStatisticsRequest("replicate curve output schema is not supported")
    definition = reference_tensile_replicate_curve_definition()
    table = pa.table(
        {
            "engineering_strain": pa.array(
                [item.engineering_strain for item in values], type=pa.float64()
            ),
            "sample_count": pa.array(
                [item.stress.sample_count for item in values], type=pa.int16()
            ),
            "mean_engineering_stress_pa": pa.array(
                [item.stress.mean for item in values], type=pa.float64()
            ),
            "sample_standard_deviation_engineering_stress_pa": pa.array(
                [item.stress.sample_standard_deviation for item in values], type=pa.float64()
            ),
            "median_engineering_stress_pa": pa.array(
                [item.stress.median for item in values], type=pa.float64()
            ),
            "median_absolute_deviation_engineering_stress_pa": pa.array(
                [item.stress.median_absolute_deviation for item in values], type=pa.float64()
            ),
            "interquartile_range_engineering_stress_pa": pa.array(
                [item.stress.interquartile_range for item in values], type=pa.float64()
            ),
            "minimum_engineering_stress_pa": pa.array(
                [item.stress.minimum for item in values], type=pa.float64()
            ),
            "maximum_engineering_stress_pa": pa.array(
                [item.stress.maximum for item in values], type=pa.float64()
            ),
            "coefficient_of_variation": pa.array(
                [item.stress.coefficient_of_variation for item in values], type=pa.float64()
            ),
            "mean_confidence_interval_lower_95_pa": pa.array(
                [item.stress.mean_confidence_interval_lower_95 for item in values],
                type=pa.float64(),
            ),
            "mean_confidence_interval_upper_95_pa": pa.array(
                [item.stress.mean_confidence_interval_upper_95 for item in values],
                type=pa.float64(),
            ),
        }
    )
    if schema_ref == REFERENCE_TENSILE_REPLICATE_CURVE_SCHEMA:
        table = table.replace_schema_metadata(
            {
                b"cmp.schema": schema_ref.encode("ascii"),
                CURVE_DEFINITION_PARQUET_KEY: curve_definition_json_bytes(definition),
                CURVE_DEFINITION_SHA256_PARQUET_KEY: definition.sha256.encode("ascii"),
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


def reference_tensile_replicate_curve_from_parquet(
    value: bytes,
) -> tuple[ReplicateCurvePoint, ...]:
    """Read only the declared typed columns and reject malformed result Artifacts."""

    columns = (
        "engineering_strain",
        "sample_count",
        "mean_engineering_stress_pa",
        "sample_standard_deviation_engineering_stress_pa",
        "median_engineering_stress_pa",
        "median_absolute_deviation_engineering_stress_pa",
        "interquartile_range_engineering_stress_pa",
        "minimum_engineering_stress_pa",
        "maximum_engineering_stress_pa",
        "coefficient_of_variation",
        "mean_confidence_interval_lower_95_pa",
        "mean_confidence_interval_upper_95_pa",
    )
    try:
        table = _read_parquet_table(pa.BufferReader(value), columns=list(columns))
    except Exception as error:
        raise InvalidStatisticsRequest(
            "replicate statistics Artifact is not the declared typed Parquet schema"
        ) from error
    if tuple(table.column_names) != columns:
        raise InvalidStatisticsRequest("replicate statistics Artifact channel names are invalid")
    rows = zip(*(table.column(column).to_pylist() for column in columns), strict=True)
    values = tuple(
        ReplicateCurvePoint(
            engineering_strain=float(row[0]),
            stress=ReplicateScalarStatistics(
                sample_count=int(row[1]),
                mean=float(row[2]),
                sample_standard_deviation=float(row[3]),
                median=float(row[4]),
                median_absolute_deviation=float(row[5]),
                interquartile_range=float(row[6]),
                minimum=float(row[7]),
                maximum=float(row[8]),
                coefficient_of_variation=(None if row[9] is None else float(row[9])),
                mean_confidence_interval_lower_95=float(row[10]),
                mean_confidence_interval_upper_95=float(row[11]),
            ),
        )
        for row in rows
    )
    # Reuse the aggregate invariant for point count and strictly increasing strain.
    return ReferenceTensileReplicateStatistics(
        peak_engineering_stress_pa=values[0].stress,
        curve=values,
    ).curve
