"""Deterministic replicate alignment, TTS shift evidence, and master-curve computation."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from statistics import median
from typing import cast
from uuid import UUID

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray
from scipy.optimize import least_squares, minimize_scalar  # type: ignore[import-untyped]

from cmp.modules.datasets.domain.reference_shear_relaxation import ShearRelaxationPoint
from cmp.shared.domain.revisions import content_sha256

VISCOELASTIC_MASTER_PLAN_SCHEMA_ID = "urn:cmp:processing:viscoelastic-master-plan:1.0.0"
VISCOELASTIC_MASTER_SCHEMA_VERSION = "1.0.0"
VISCOELASTIC_ALIGNED_PARQUET_SCHEMA = (
    "urn:cmp:datasets:viscoelastic-aligned-replicates-parquet:1.0.0"
)
VISCOELASTIC_STATISTICS_PARQUET_SCHEMA = (
    "urn:cmp:datasets:viscoelastic-temperature-statistics-parquet:1.0.0"
)
VISCOELASTIC_MASTER_PARQUET_SCHEMA = "urn:cmp:datasets:viscoelastic-master-curve-parquet:1.0.0"

_write_parquet = cast(Callable[..., None], pq.write_table)


class ViscoelasticMasterError(Exception):
    """Base error for the bounded T-42 processing kernel."""


class InvalidViscoelasticMasterPlan(ViscoelasticMasterError, ValueError):
    """Plan or curve evidence violates the declared TTS contract."""


class ShiftMethod(StrEnum):
    MANUAL = "manual"
    WLF_FIT = "wlf_fit"
    ARRHENIUS_FIT = "arrhenius_fit"


@dataclass(frozen=True, slots=True)
class ManualShiftFactor:
    temperature_k: float
    log10_a_t: float

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.temperature_k)
            or self.temperature_k <= 0
            or not math.isfinite(self.log10_a_t)
            or abs(self.log10_a_t) > 20
        ):
            raise InvalidViscoelasticMasterPlan("manual shift factor must be finite and bounded")


@dataclass(frozen=True, slots=True)
class ViscoelasticMasterPlanContent:
    plan_label: str
    selection_id: UUID
    selection_revision_id: UUID
    reference_temperature_k: float
    grid_point_count: int
    shift_method: ShiftMethod
    manual_shift_factors: tuple[ManualShiftFactor, ...] = ()
    interpolation: str = "piecewise_linear_log_time"
    domain_policy: str = "common_intersection_no_extrapolation"
    reduced_time_convention: str = "time_divided_by_a_t"

    def __post_init__(self) -> None:
        if (
            not self.plan_label
            or self.plan_label != self.plan_label.strip()
            or len(self.plan_label) > 160
            or "\x00" in self.plan_label
        ):
            raise InvalidViscoelasticMasterPlan("plan_label must contain 1..160 trimmed characters")
        if self.selection_id.int == 0 or self.selection_revision_id.int == 0:
            raise InvalidViscoelasticMasterPlan("selection identity and revision must be concrete")
        if not math.isfinite(self.reference_temperature_k) or self.reference_temperature_k <= 0:
            raise InvalidViscoelasticMasterPlan("reference temperature must be positive Kelvin")
        if not 3 <= self.grid_point_count <= 501:
            raise InvalidViscoelasticMasterPlan("grid_point_count must be within 3..501")
        if self.interpolation != "piecewise_linear_log_time":
            raise InvalidViscoelasticMasterPlan(
                "only piecewise-linear log-time interpolation is supported"
            )
        if self.domain_policy != "common_intersection_no_extrapolation":
            raise InvalidViscoelasticMasterPlan("extrapolation is not supported")
        if self.reduced_time_convention != "time_divided_by_a_t":
            raise InvalidViscoelasticMasterPlan("reduced time must use t/aT")
        temperatures = tuple(item.temperature_k for item in self.manual_shift_factors)
        if len(set(temperatures)) != len(temperatures):
            raise InvalidViscoelasticMasterPlan("manual shift temperatures must be unique")
        if self.shift_method is ShiftMethod.MANUAL and not self.manual_shift_factors:
            raise InvalidViscoelasticMasterPlan("manual shift method requires explicit factors")
        if self.shift_method in {ShiftMethod.WLF_FIT, ShiftMethod.ARRHENIUS_FIT} and (
            self.manual_shift_factors
        ):
            raise InvalidViscoelasticMasterPlan(
                "fitted temperature shifts cannot carry manual shift factors"
            )

    def canonical(self) -> dict[str, object]:
        return {
            "plan_label": self.plan_label,
            "selection_id": str(self.selection_id),
            "selection_revision_id": str(self.selection_revision_id),
            "reference_temperature_k": self.reference_temperature_k,
            "grid_point_count": self.grid_point_count,
            "shift_method": self.shift_method.value,
            "manual_shift_factors": [
                {"temperature_k": item.temperature_k, "log10_a_t": item.log10_a_t}
                for item in sorted(self.manual_shift_factors, key=lambda value: value.temperature_k)
            ],
            "interpolation": self.interpolation,
            "domain_policy": self.domain_policy,
            "reduced_time_convention": self.reduced_time_convention,
        }

    @property
    def digest(self) -> str:
        return content_sha256(self.canonical())


@dataclass(frozen=True, slots=True)
class ReplicateCurve:
    member_ordinal: int
    dataset_revision_id: UUID
    test_run_revision_id: UUID
    temperature_k: float
    points: tuple[ShearRelaxationPoint, ...]

    def __post_init__(self) -> None:
        if self.member_ordinal < 0:
            raise InvalidViscoelasticMasterPlan("member ordinal cannot be negative")
        if self.dataset_revision_id.int == 0 or self.test_run_revision_id.int == 0:
            raise InvalidViscoelasticMasterPlan("curve evidence requires concrete revisions")
        if not math.isfinite(self.temperature_k) or self.temperature_k <= 0:
            raise InvalidViscoelasticMasterPlan("curve temperature must be positive Kelvin")
        positive = tuple(point for point in self.points if point.time_s > 0)
        if len(positive) < 3:
            raise InvalidViscoelasticMasterPlan(
                "each curve requires at least three positive-time points"
            )
        if any(
            positive[index].time_s <= positive[index - 1].time_s
            or positive[index].shear_modulus_pa > positive[index - 1].shear_modulus_pa
            for index in range(1, len(positive))
        ):
            raise InvalidViscoelasticMasterPlan("curve time/modulus invariants are invalid")


@dataclass(frozen=True, slots=True)
class AlignedCurve:
    member_ordinal: int
    dataset_revision_id: UUID
    test_run_revision_id: UUID
    temperature_k: float
    points: tuple[ShearRelaxationPoint, ...]


@dataclass(frozen=True, slots=True)
class TemperatureStatisticsPoint:
    time_s: float
    replicate_count: int
    mean_shear_modulus_pa: float
    sample_standard_deviation_pa: float | None
    median_shear_modulus_pa: float
    minimum_shear_modulus_pa: float
    maximum_shear_modulus_pa: float


@dataclass(frozen=True, slots=True)
class TemperatureStatistics:
    temperature_k: float
    replicate_count: int
    points: tuple[TemperatureStatisticsPoint, ...]


@dataclass(frozen=True, slots=True)
class ShiftFactorEvidence:
    temperature_k: float
    log10_a_t: float
    source: str
    observed_log10_a_t: float | None
    residual_log10_a_t: float | None
    alignment_rmse_pa: float | None


@dataclass(frozen=True, slots=True)
class MasterCurvePoint:
    reduced_time_s: float
    contributing_curve_count: int
    mean_shear_modulus_pa: float
    sample_standard_deviation_pa: float | None
    minimum_shear_modulus_pa: float
    maximum_shear_modulus_pa: float


@dataclass(frozen=True, slots=True)
class ViscoelasticMasterResult:
    aligned_curves: tuple[AlignedCurve, ...]
    temperature_statistics: tuple[TemperatureStatistics, ...]
    shift_factors: tuple[ShiftFactorEvidence, ...]
    master_curve: tuple[MasterCurvePoint, ...]
    wlf_c1: float | None
    wlf_c2_k: float | None
    arrhenius_activation_energy_j_per_mol: float | None
    reference_temperature_k: float


def _positive_xy(curve: ReplicateCurve | AlignedCurve) -> tuple[np.ndarray, np.ndarray]:
    positive = tuple(point for point in curve.points if point.time_s > 0)
    return (
        np.asarray([math.log10(point.time_s) for point in positive], dtype=float),
        np.asarray([point.shear_modulus_pa for point in positive], dtype=float),
    )


def _sample_standard_deviation(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((item - mean) ** 2 for item in values) / (len(values) - 1))


def _align_temperature_group(
    curves: tuple[ReplicateCurve, ...], grid_point_count: int
) -> tuple[AlignedCurve, ...]:
    axes = tuple(_positive_xy(curve) for curve in curves)
    lower = max(float(axis[0][0]) for axis in axes)
    upper = min(float(axis[0][-1]) for axis in axes)
    if not lower < upper:
        raise InvalidViscoelasticMasterPlan(
            f"temperature {curves[0].temperature_k:g} K has no common positive log-time domain"
        )
    grid = np.linspace(lower, upper, grid_point_count)
    times = np.power(10.0, grid)
    return tuple(
        AlignedCurve(
            member_ordinal=curve.member_ordinal,
            dataset_revision_id=curve.dataset_revision_id,
            test_run_revision_id=curve.test_run_revision_id,
            temperature_k=curve.temperature_k,
            points=tuple(
                ShearRelaxationPoint(float(time), float(modulus))
                for time, modulus in zip(times, np.interp(grid, x, y), strict=True)
            ),
        )
        for curve, (x, y) in zip(curves, axes, strict=True)
    )


def _temperature_statistics(
    temperature_k: float, curves: tuple[AlignedCurve, ...]
) -> TemperatureStatistics:
    points: list[TemperatureStatisticsPoint] = []
    for index in range(len(curves[0].points)):
        values = [curve.points[index].shear_modulus_pa for curve in curves]
        points.append(
            TemperatureStatisticsPoint(
                time_s=curves[0].points[index].time_s,
                replicate_count=len(values),
                mean_shear_modulus_pa=sum(values) / len(values),
                sample_standard_deviation_pa=_sample_standard_deviation(values),
                median_shear_modulus_pa=median(values),
                minimum_shear_modulus_pa=min(values),
                maximum_shear_modulus_pa=max(values),
            )
        )
    return TemperatureStatistics(temperature_k, len(curves), tuple(points))


def _mean_xy(statistics: TemperatureStatistics) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.asarray([math.log10(item.time_s) for item in statistics.points], dtype=float),
        np.asarray([item.mean_shear_modulus_pa for item in statistics.points], dtype=float),
    )


def _observed_shift(
    reference: TemperatureStatistics, source: TemperatureStatistics
) -> tuple[float, float]:
    ref_x, ref_y = _mean_xy(reference)
    source_x, source_y = _mean_xy(source)
    scale = max(float(np.ptp(ref_y)), abs(float(np.mean(ref_y))), 1.0)

    def objective(log10_a_t: float) -> float:
        shifted_lower = float(source_x[0] - log10_a_t)
        shifted_upper = float(source_x[-1] - log10_a_t)
        lower = max(float(ref_x[0]), shifted_lower)
        upper = min(float(ref_x[-1]), shifted_upper)
        if upper - lower < 0.1 * min(float(np.ptp(ref_x)), float(np.ptp(source_x))):
            return 1e6 + abs(upper - lower)
        grid = np.linspace(lower, upper, 64)
        reference_values = np.interp(grid, ref_x, ref_y)
        source_values = np.interp(grid + log10_a_t, source_x, source_y)
        residual = (source_values - reference_values) / scale
        return float(np.mean(residual**2))

    outcome = minimize_scalar(objective, bounds=(-12.0, 12.0), method="bounded")
    if not outcome.success or not math.isfinite(float(outcome.x)):
        raise InvalidViscoelasticMasterPlan("temperature shift optimization did not converge")
    shift = float(outcome.x)
    rmse = math.sqrt(max(0.0, float(outcome.fun))) * scale
    return shift, rmse


def _fit_wlf(
    statistics: tuple[TemperatureStatistics, ...], reference_temperature_k: float
) -> tuple[tuple[ShiftFactorEvidence, ...], float, float]:
    if len(statistics) < 3:
        raise InvalidViscoelasticMasterPlan("WLF fitting requires at least three temperatures")
    reference = next(
        (item for item in statistics if item.temperature_k == reference_temperature_k), None
    )
    if reference is None:
        raise InvalidViscoelasticMasterPlan("reference temperature is absent from the Selection")
    observed: dict[float, tuple[float, float]] = {reference_temperature_k: (0.0, 0.0)}
    for item in statistics:
        if item.temperature_k != reference_temperature_k:
            observed[item.temperature_k] = _observed_shift(reference, item)

    temperatures = np.asarray(sorted(observed), dtype=float)
    deltas = temperatures - reference_temperature_k
    targets = np.asarray([observed[float(value)][0] for value in temperatures], dtype=float)
    lower_c2 = max(1e-3, -float(np.min(deltas)) + 1e-3)

    def residual(parameters: NDArray[np.float64]) -> NDArray[np.float64]:
        c1, c2 = float(parameters[0]), float(parameters[1])
        predicted = -c1 * deltas / (c2 + deltas)
        return np.asarray(predicted - targets, dtype=np.float64)

    initial_c2 = max(51.6, lower_c2 + 1.0)
    outcome = least_squares(
        residual,
        x0=np.asarray([17.44, initial_c2]),
        bounds=(np.asarray([1e-8, lower_c2]), np.asarray([1000.0, 5000.0])),
        method="trf",
        ftol=1e-12,
        xtol=1e-12,
        gtol=1e-12,
        max_nfev=5000,
    )
    if not outcome.success or not np.all(np.isfinite(outcome.x)):
        raise InvalidViscoelasticMasterPlan("WLF parameter fit did not converge")
    c1, c2 = float(outcome.x[0]), float(outcome.x[1])
    evidence = tuple(
        ShiftFactorEvidence(
            temperature_k=float(temperature),
            log10_a_t=float(-c1 * delta / (c2 + delta)),
            source="wlf_fit" if delta else "reference",
            observed_log10_a_t=observed[float(temperature)][0],
            residual_log10_a_t=(
                float(-c1 * delta / (c2 + delta)) - observed[float(temperature)][0]
            ),
            alignment_rmse_pa=observed[float(temperature)][1],
        )
        for temperature, delta in zip(temperatures, deltas, strict=True)
    )
    return evidence, c1, c2


def _fit_arrhenius(
    statistics: tuple[TemperatureStatistics, ...], reference_temperature_k: float
) -> tuple[tuple[ShiftFactorEvidence, ...], float]:
    """Fit log10(aT)=Ea/(2.303 R)*(1/T-1/Tref) through the physical origin."""

    if len(statistics) < 3:
        raise InvalidViscoelasticMasterPlan(
            "Arrhenius fitting requires at least three temperatures"
        )
    reference = next(
        (item for item in statistics if item.temperature_k == reference_temperature_k), None
    )
    if reference is None:
        raise InvalidViscoelasticMasterPlan("reference temperature is absent from the Selection")
    observed: dict[float, tuple[float, float]] = {reference_temperature_k: (0.0, 0.0)}
    for item in statistics:
        if item.temperature_k != reference_temperature_k:
            observed[item.temperature_k] = _observed_shift(reference, item)
    temperatures = np.asarray(sorted(observed), dtype=float)
    inverse_temperature_delta = 1.0 / temperatures - 1.0 / reference_temperature_k
    targets = np.asarray([observed[float(value)][0] for value in temperatures], dtype=float)
    denominator = float(np.dot(inverse_temperature_delta, inverse_temperature_delta))
    if denominator <= np.finfo(float).tiny:
        raise InvalidViscoelasticMasterPlan("Arrhenius temperatures do not span a usable range")
    slope = float(np.dot(inverse_temperature_delta, targets) / denominator)
    gas_constant_j_per_mol_k = 8.31446261815324
    activation_energy = slope * math.log(10.0) * gas_constant_j_per_mol_k
    if not math.isfinite(activation_energy) or activation_energy <= 0:
        raise InvalidViscoelasticMasterPlan(
            "Arrhenius fit produced a non-positive activation energy"
        )
    predicted = slope * inverse_temperature_delta
    evidence = tuple(
        ShiftFactorEvidence(
            temperature_k=float(temperature),
            log10_a_t=float(shift),
            source="arrhenius_fit" if temperature != reference_temperature_k else "reference",
            observed_log10_a_t=observed[float(temperature)][0],
            residual_log10_a_t=float(shift - observed[float(temperature)][0]),
            alignment_rmse_pa=observed[float(temperature)][1],
        )
        for temperature, shift in zip(temperatures, predicted, strict=True)
    )
    return evidence, activation_energy


def _manual_evidence(
    plan: ViscoelasticMasterPlanContent, temperatures: tuple[float, ...]
) -> tuple[ShiftFactorEvidence, ...]:
    factors = {item.temperature_k: item.log10_a_t for item in plan.manual_shift_factors}
    if set(factors) != set(temperatures):
        raise InvalidViscoelasticMasterPlan(
            "manual shift factors must cover every selected temperature exactly once"
        )
    if not math.isclose(factors[plan.reference_temperature_k], 0.0, abs_tol=1e-12):
        raise InvalidViscoelasticMasterPlan("reference-temperature manual shift must be zero")
    return tuple(
        ShiftFactorEvidence(
            temperature_k=temperature,
            log10_a_t=factors[temperature],
            source="reference" if temperature == plan.reference_temperature_k else "manual",
            observed_log10_a_t=None,
            residual_log10_a_t=None,
            alignment_rmse_pa=None,
        )
        for temperature in temperatures
    )


def _master_curve(
    aligned: tuple[AlignedCurve, ...], factors: tuple[ShiftFactorEvidence, ...], point_count: int
) -> tuple[MasterCurvePoint, ...]:
    by_temperature = {item.temperature_k: item.log10_a_t for item in factors}
    shifted: list[tuple[np.ndarray, np.ndarray]] = []
    for curve in aligned:
        x, y = _positive_xy(curve)
        shifted.append((x - by_temperature[curve.temperature_k], y))
    lower = min(float(x[0]) for x, _ in shifted)
    upper = max(float(x[-1]) for x, _ in shifted)
    if not lower < upper:
        raise InvalidViscoelasticMasterPlan("shifted curves have no usable master domain")
    grid = np.linspace(lower, upper, point_count)
    output: list[MasterCurvePoint] = []
    for x_value in grid:
        values = [
            float(np.interp(x_value, x, y))
            for x, y in shifted
            if float(x[0]) - 1e-12 <= x_value <= float(x[-1]) + 1e-12
        ]
        if not values:
            continue
        output.append(
            MasterCurvePoint(
                reduced_time_s=10.0**float(x_value),
                contributing_curve_count=len(values),
                mean_shear_modulus_pa=sum(values) / len(values),
                sample_standard_deviation_pa=_sample_standard_deviation(values),
                minimum_shear_modulus_pa=min(values),
                maximum_shear_modulus_pa=max(values),
            )
        )
    if len(output) < 3:
        raise InvalidViscoelasticMasterPlan("master curve requires at least three output points")
    return tuple(output)


def compute_viscoelastic_master_curve(
    curves: tuple[ReplicateCurve, ...], plan: ViscoelasticMasterPlanContent
) -> ViscoelasticMasterResult:
    if len(curves) < 2:
        raise InvalidViscoelasticMasterPlan("master-curve processing requires at least two curves")
    if len({curve.member_ordinal for curve in curves}) != len(curves):
        raise InvalidViscoelasticMasterPlan("curve member ordinals must be unique")
    if len({curve.dataset_revision_id for curve in curves}) != len(curves):
        raise InvalidViscoelasticMasterPlan("Dataset revisions cannot be repeated")
    groups: defaultdict[float, list[ReplicateCurve]] = defaultdict(list)
    for curve in curves:
        groups[curve.temperature_k].append(curve)
    temperatures = tuple(sorted(groups))
    if plan.reference_temperature_k not in groups:
        raise InvalidViscoelasticMasterPlan("reference temperature is absent from the Selection")
    aligned = tuple(
        item
        for temperature in temperatures
        for item in _align_temperature_group(
            tuple(sorted(groups[temperature], key=lambda curve: curve.member_ordinal)),
            plan.grid_point_count,
        )
    )
    statistics = tuple(
        _temperature_statistics(
            temperature,
            tuple(item for item in aligned if item.temperature_k == temperature),
        )
        for temperature in temperatures
    )
    activation_energy = None
    if plan.shift_method is ShiftMethod.MANUAL:
        factors = _manual_evidence(plan, temperatures)
        c1 = c2 = None
    elif plan.shift_method is ShiftMethod.WLF_FIT:
        factors, c1, c2 = _fit_wlf(statistics, plan.reference_temperature_k)
    else:
        factors, activation_energy = _fit_arrhenius(
            statistics, plan.reference_temperature_k
        )
        c1 = c2 = None
    return ViscoelasticMasterResult(
        aligned_curves=aligned,
        temperature_statistics=statistics,
        shift_factors=factors,
        master_curve=_master_curve(aligned, factors, plan.grid_point_count),
        wlf_c1=c1,
        wlf_c2_k=c2,
        arrhenius_activation_energy_j_per_mol=activation_energy,
        reference_temperature_k=plan.reference_temperature_k,
    )


def _parquet_bytes(columns: dict[str, pa.Array]) -> bytes:
    sink = pa.BufferOutputStream()
    _write_parquet(
        pa.table(columns),
        sink,
        compression="zstd",
        version="2.6",
        data_page_version="2.0",
        use_dictionary=False,
        write_statistics=True,
    )
    return cast(bytes, sink.getvalue().to_pybytes())


def aligned_replicates_parquet_bytes(result: ViscoelasticMasterResult) -> bytes:
    rows = [
        (curve.temperature_k, curve.member_ordinal, point.time_s, point.shear_modulus_pa)
        for curve in result.aligned_curves
        for point in curve.points
    ]
    return _parquet_bytes(
        {
            "temperature_k": pa.array((row[0] for row in rows), type=pa.float64()),
            "member_ordinal": pa.array((row[1] for row in rows), type=pa.int32()),
            "time_s": pa.array((row[2] for row in rows), type=pa.float64()),
            "shear_modulus_pa": pa.array((row[3] for row in rows), type=pa.float64()),
        }
    )


def temperature_statistics_parquet_bytes(result: ViscoelasticMasterResult) -> bytes:
    rows = [
        (statistics.temperature_k, point)
        for statistics in result.temperature_statistics
        for point in statistics.points
    ]
    return _parquet_bytes(
        {
            "temperature_k": pa.array((row[0] for row in rows), type=pa.float64()),
            "time_s": pa.array((row[1].time_s for row in rows), type=pa.float64()),
            "replicate_count": pa.array((row[1].replicate_count for row in rows), type=pa.int32()),
            "mean_shear_modulus_pa": pa.array(
                (row[1].mean_shear_modulus_pa for row in rows), type=pa.float64()
            ),
            "sample_standard_deviation_pa": pa.array(
                (row[1].sample_standard_deviation_pa for row in rows), type=pa.float64()
            ),
            "median_shear_modulus_pa": pa.array(
                (row[1].median_shear_modulus_pa for row in rows), type=pa.float64()
            ),
            "minimum_shear_modulus_pa": pa.array(
                (row[1].minimum_shear_modulus_pa for row in rows), type=pa.float64()
            ),
            "maximum_shear_modulus_pa": pa.array(
                (row[1].maximum_shear_modulus_pa for row in rows), type=pa.float64()
            ),
        }
    )


def master_curve_parquet_bytes(result: ViscoelasticMasterResult) -> bytes:
    return _parquet_bytes(
        {
            "reduced_time_s": pa.array(
                (point.reduced_time_s for point in result.master_curve), type=pa.float64()
            ),
            "contributing_curve_count": pa.array(
                (point.contributing_curve_count for point in result.master_curve), type=pa.int32()
            ),
            "mean_shear_modulus_pa": pa.array(
                (point.mean_shear_modulus_pa for point in result.master_curve), type=pa.float64()
            ),
            "sample_standard_deviation_pa": pa.array(
                (point.sample_standard_deviation_pa for point in result.master_curve),
                type=pa.float64(),
            ),
            "minimum_shear_modulus_pa": pa.array(
                (point.minimum_shear_modulus_pa for point in result.master_curve), type=pa.float64()
            ),
            "maximum_shear_modulus_pa": pa.array(
                (point.maximum_shear_modulus_pa for point in result.master_curve), type=pa.float64()
            ),
        }
    )


def _read_table(value: bytes, expected_columns: tuple[str, ...]) -> pa.Table:
    try:
        table = pq.read_table(pa.BufferReader(value))  # type: ignore[no-untyped-call]
    except (pa.ArrowInvalid, OSError) as error:
        raise InvalidViscoelasticMasterPlan("derived Parquet Artifact is invalid") from error
    if tuple(table.column_names) != expected_columns or table.num_rows < 1:
        raise InvalidViscoelasticMasterPlan("derived Parquet schema is not the declared schema")
    return table


def aligned_replicates_from_parquet(
    value: bytes,
    member_evidence: dict[int, tuple[UUID, UUID]],
) -> tuple[AlignedCurve, ...]:
    table = _read_table(
        value,
        ("temperature_k", "member_ordinal", "time_s", "shear_modulus_pa"),
    )
    groups: defaultdict[tuple[float, int], list[ShearRelaxationPoint]] = defaultdict(list)
    rows = table.to_pylist()
    for row in rows:
        temperature = float(row["temperature_k"])
        ordinal = int(row["member_ordinal"])
        groups[(temperature, ordinal)].append(
            ShearRelaxationPoint(float(row["time_s"]), float(row["shear_modulus_pa"]))
        )
    curves: list[AlignedCurve] = []
    for (temperature, ordinal), points in sorted(groups.items(), key=lambda item: item[0][1]):
        try:
            dataset_revision_id, test_run_revision_id = member_evidence[ordinal]
        except KeyError as error:
            raise InvalidViscoelasticMasterPlan(
                "aligned Artifact contains an unknown Selection member"
            ) from error
        curves.append(
            AlignedCurve(
                member_ordinal=ordinal,
                dataset_revision_id=dataset_revision_id,
                test_run_revision_id=test_run_revision_id,
                temperature_k=temperature,
                points=tuple(points),
            )
        )
    if set(member_evidence) != {curve.member_ordinal for curve in curves}:
        raise InvalidViscoelasticMasterPlan("aligned Artifact omits a Selection member")
    return tuple(curves)


def temperature_statistics_from_parquet(value: bytes) -> tuple[TemperatureStatistics, ...]:
    table = _read_table(
        value,
        (
            "temperature_k",
            "time_s",
            "replicate_count",
            "mean_shear_modulus_pa",
            "sample_standard_deviation_pa",
            "median_shear_modulus_pa",
            "minimum_shear_modulus_pa",
            "maximum_shear_modulus_pa",
        ),
    )
    groups: defaultdict[float, list[TemperatureStatisticsPoint]] = defaultdict(list)
    for row in table.to_pylist():
        standard_deviation = row["sample_standard_deviation_pa"]
        groups[float(row["temperature_k"])].append(
            TemperatureStatisticsPoint(
                time_s=float(row["time_s"]),
                replicate_count=int(row["replicate_count"]),
                mean_shear_modulus_pa=float(row["mean_shear_modulus_pa"]),
                sample_standard_deviation_pa=(
                    float(standard_deviation) if standard_deviation is not None else None
                ),
                median_shear_modulus_pa=float(row["median_shear_modulus_pa"]),
                minimum_shear_modulus_pa=float(row["minimum_shear_modulus_pa"]),
                maximum_shear_modulus_pa=float(row["maximum_shear_modulus_pa"]),
            )
        )
    return tuple(
        TemperatureStatistics(
            temperature_k=temperature,
            replicate_count=points[0].replicate_count,
            points=tuple(points),
        )
        for temperature, points in sorted(groups.items())
    )


def master_curve_from_parquet(value: bytes) -> tuple[MasterCurvePoint, ...]:
    table = _read_table(
        value,
        (
            "reduced_time_s",
            "contributing_curve_count",
            "mean_shear_modulus_pa",
            "sample_standard_deviation_pa",
            "minimum_shear_modulus_pa",
            "maximum_shear_modulus_pa",
        ),
    )
    output: list[MasterCurvePoint] = []
    for row in table.to_pylist():
        standard_deviation = row["sample_standard_deviation_pa"]
        output.append(
            MasterCurvePoint(
                reduced_time_s=float(row["reduced_time_s"]),
                contributing_curve_count=int(row["contributing_curve_count"]),
                mean_shear_modulus_pa=float(row["mean_shear_modulus_pa"]),
                sample_standard_deviation_pa=(
                    float(standard_deviation) if standard_deviation is not None else None
                ),
                minimum_shear_modulus_pa=float(row["minimum_shear_modulus_pa"]),
                maximum_shear_modulus_pa=float(row["maximum_shear_modulus_pa"]),
            )
        )
    return tuple(output)
