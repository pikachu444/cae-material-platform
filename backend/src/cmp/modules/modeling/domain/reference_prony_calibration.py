"""Bounded two-term generalized-Maxwell calibration for reference shear relaxation.

The kernel is solver neutral and non-production.  It fits a fixed instantaneous shear modulus
from an exact baseline IR and never selects or promotes a candidate automatically.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any, cast
from uuid import UUID

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray
from scipy.optimize import least_squares  # type: ignore[import-untyped]

from cmp.modules.datasets.domain.reference_shear_relaxation import ShearRelaxationPoint
from cmp.shared.domain.revisions import content_sha256

REFERENCE_PRONY_PLAN_KIND = "reference_two_term_shear_relaxation_prony"
REFERENCE_PRONY_PLAN_SCHEMA_ID = "urn:cmp:modeling:reference-prony-calibration-plan:1.0.0"
REFERENCE_PRONY_PLAN_SCHEMA_VERSION = "1.0.0"
REFERENCE_PRONY_TEST_MODE_ADAPTER_ID = (
    "urn:cmp:reference:shear-relaxation-observed-points:1.0.0"
)
REFERENCE_PRONY_EVALUATOR_ID = "urn:cmp:reference:two-term-generalized-maxwell:1.0.0"
REFERENCE_PRONY_OBJECTIVE_ID = "urn:cmp:reference:uniform-normalized-modulus-wls:1.0.0"
REFERENCE_PRONY_OPTIMIZER_ID = "urn:cmp:reference:scipy-least-squares:1.0.0"
REFERENCE_PRONY_DIAGNOSTICS_SCHEMA = (
    "urn:cmp:modeling:reference-prony-calibration-diagnostics-parquet:1.0.0"
)
REFERENCE_PRONY_ENVIRONMENT_DIGEST = content_sha256(
    {
        "numpy_version": np.__version__,
        "scipy_version": version("scipy"),
        "optimizer": "scipy.optimize.least_squares",
        "method": "trf",
        "rng": "numpy.random.PCG64",
        "non_production": True,
    }
)


class PronyCalibrationError(Exception):
    """Base error for the bounded reference calibration."""


class InvalidPronyCalibration(PronyCalibrationError, ValueError):
    """Plan or numerical input violates the fixed reference contract."""


def _positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise InvalidPronyCalibration(f"{name} must be finite and greater than zero")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidPronyCalibration(
            f"{name} must be trimmed and contain 1..{maximum} characters"
        )


@dataclass(frozen=True, slots=True)
class PronyParameterPlan:
    name: str
    unit: str
    lower: float
    initial: float
    upper: float
    transform: str

    def __post_init__(self) -> None:
        _text("parameter name", self.name, 80)
        _text("parameter unit", self.unit, 32)
        if not all(math.isfinite(value) for value in (self.lower, self.initial, self.upper)):
            raise InvalidPronyCalibration(f"{self.name} values must be finite")
        if not self.lower < self.upper or not self.lower <= self.initial <= self.upper:
            raise InvalidPronyCalibration(f"{self.name} bounds and initial value are invalid")
        if self.transform not in {"none", "log"}:
            raise InvalidPronyCalibration(f"{self.name} transform must be none or log")
        if self.transform == "log" and self.lower <= 0:
            raise InvalidPronyCalibration(f"{self.name} log transform requires positive bounds")


@dataclass(frozen=True, slots=True)
class ReferencePronyCalibrationPlanContent:
    plan_label: str
    input_dataset_id: UUID
    input_dataset_revision_id: UUID
    baseline_model_id: UUID
    baseline_model_revision_id: UUID
    total_g_ratio: PronyParameterPlan
    fast_term_fraction: PronyParameterPlan
    fast_relaxation_time_s: PronyParameterPlan
    slow_relaxation_time_s: PronyParameterPlan
    normalization_modulus_pa: float
    multistart_count: int
    random_seed: int
    maximum_function_evaluations: int = 2_000
    ftol: float = 1e-10
    xtol: float = 1e-10
    gtol: float = 1e-10
    plan_kind: str = REFERENCE_PRONY_PLAN_KIND
    test_mode_adapter_id: str = REFERENCE_PRONY_TEST_MODE_ADAPTER_ID
    evaluator_id: str = REFERENCE_PRONY_EVALUATOR_ID
    objective_engine_id: str = REFERENCE_PRONY_OBJECTIVE_ID
    optimizer_adapter_id: str = REFERENCE_PRONY_OPTIMIZER_ID
    residual_definition: str = "predicted_minus_observed_shear_modulus"
    point_weighting: str = "uniform"
    objective_aggregation: str = "mean_normalized_squared_residual"
    missing_data_policy: str = "reject"
    optimizer_method: str = "trf"
    rng_algorithm: str = "numpy.random.PCG64"
    term_count: int = 2
    non_production: bool = True

    def __post_init__(self) -> None:
        _text("plan_label", self.plan_label, 160)
        for name in (
            "input_dataset_id",
            "input_dataset_revision_id",
            "baseline_model_id",
            "baseline_model_revision_id",
        ):
            value = getattr(self, name)
            if not hasattr(value, "int") or value.int == 0:
                raise InvalidPronyCalibration(f"{name} must be a non-zero UUID")
        if (
            self.total_g_ratio.name != "total_g_ratio"
            or self.total_g_ratio.unit != "1"
            or self.total_g_ratio.transform != "none"
            or not 0 < self.total_g_ratio.lower < self.total_g_ratio.upper < 1
        ):
            raise InvalidPronyCalibration("total_g_ratio must be dimensionless within (0,1)")
        if (
            self.fast_term_fraction.name != "fast_term_fraction"
            or self.fast_term_fraction.unit != "1"
            or self.fast_term_fraction.transform != "none"
            or not 0 < self.fast_term_fraction.lower < self.fast_term_fraction.upper < 1
        ):
            raise InvalidPronyCalibration("fast_term_fraction must be within (0,1)")
        for expected, parameter in (
            ("fast_relaxation_time_s", self.fast_relaxation_time_s),
            ("slow_relaxation_time_s", self.slow_relaxation_time_s),
        ):
            if parameter.name != expected or parameter.unit != "s" or parameter.transform != "log":
                raise InvalidPronyCalibration(f"{expected} must use seconds and log transform")
        if self.fast_relaxation_time_s.upper >= self.slow_relaxation_time_s.lower:
            raise InvalidPronyCalibration(
                "fast relaxation upper bound must be below slow relaxation lower bound"
            )
        _positive("normalization_modulus_pa", self.normalization_modulus_pa)
        if not 1 <= self.multistart_count <= 16:
            raise InvalidPronyCalibration("multistart_count must be between 1 and 16")
        if not 0 <= self.random_seed < 2**63:
            raise InvalidPronyCalibration("random_seed must be a signed non-negative 64-bit value")
        if not 10 <= self.maximum_function_evaluations <= 1_000_000:
            raise InvalidPronyCalibration(
                "maximum_function_evaluations must be within 10..1000000"
            )
        if not all(
            math.isfinite(value) and 0 < value < 1 for value in (self.ftol, self.xtol, self.gtol)
        ):
            raise InvalidPronyCalibration("ftol, xtol, and gtol must be finite within (0,1)")
        fixed = (
            self.plan_kind == REFERENCE_PRONY_PLAN_KIND
            and self.test_mode_adapter_id == REFERENCE_PRONY_TEST_MODE_ADAPTER_ID
            and self.evaluator_id == REFERENCE_PRONY_EVALUATOR_ID
            and self.objective_engine_id == REFERENCE_PRONY_OBJECTIVE_ID
            and self.optimizer_adapter_id == REFERENCE_PRONY_OPTIMIZER_ID
            and self.residual_definition == "predicted_minus_observed_shear_modulus"
            and self.point_weighting == "uniform"
            and self.objective_aggregation == "mean_normalized_squared_residual"
            and self.missing_data_policy == "reject"
            and self.optimizer_method == "trf"
            and self.rng_algorithm == "numpy.random.PCG64"
            and self.term_count == 2
            and self.non_production
        )
        if not fixed:
            raise InvalidPronyCalibration("reference Prony plan fixed contract was changed")

    def canonical(self) -> dict[str, object]:
        def parameter(value: PronyParameterPlan) -> dict[str, object]:
            return {
                "name": value.name,
                "unit": value.unit,
                "lower": value.lower,
                "initial": value.initial,
                "upper": value.upper,
                "transform": value.transform,
            }

        return {
            "plan_kind": self.plan_kind,
            "plan_label": self.plan_label,
            "input_dataset_id": str(self.input_dataset_id),
            "input_dataset_revision_id": str(self.input_dataset_revision_id),
            "baseline_model_id": str(self.baseline_model_id),
            "baseline_model_revision_id": str(self.baseline_model_revision_id),
            "parameters": [
                parameter(self.total_g_ratio),
                parameter(self.fast_term_fraction),
                parameter(self.fast_relaxation_time_s),
                parameter(self.slow_relaxation_time_s),
            ],
            "normalization_modulus_pa": self.normalization_modulus_pa,
            "multistart_count": self.multistart_count,
            "random_seed": self.random_seed,
            "maximum_function_evaluations": self.maximum_function_evaluations,
            "ftol": self.ftol,
            "xtol": self.xtol,
            "gtol": self.gtol,
            "test_mode_adapter_id": self.test_mode_adapter_id,
            "evaluator_id": self.evaluator_id,
            "objective_engine_id": self.objective_engine_id,
            "optimizer_adapter_id": self.optimizer_adapter_id,
            "residual_definition": self.residual_definition,
            "point_weighting": self.point_weighting,
            "objective_aggregation": self.objective_aggregation,
            "missing_data_policy": self.missing_data_policy,
            "optimizer_method": self.optimizer_method,
            "rng_algorithm": self.rng_algorithm,
            "term_count": self.term_count,
            "non_production": self.non_production,
        }


@dataclass(frozen=True, slots=True)
class PronyCalibrationCandidate:
    attempt_ordinal: int
    initial_values: tuple[float, float, float, float]
    total_g_ratio: float
    fast_term_fraction: float
    fast_g_ratio: float
    slow_g_ratio: float
    fast_relaxation_time_s: float
    slow_relaxation_time_s: float
    objective_total: float
    residual_root_mean_square_pa: float
    residual_mean_pa: float
    status: str
    convergence_status_code: int
    convergence_reason: str
    function_evaluations: int
    jacobian_evaluations: int | None
    optimality: float
    parameter_at_bound: bool
    identifiability_status: str
    uncertainty_status: str
    predicted_modulus_pa: tuple[float, ...]
    residual_pa: tuple[float, ...]
    candidate_sha256: str


def evaluate_two_term_prony(
    *,
    instantaneous_shear_modulus_pa: float,
    times_s: NDArray[np.float64],
    total_g_ratio: float,
    fast_term_fraction: float,
    fast_relaxation_time_s: float,
    slow_relaxation_time_s: float,
) -> NDArray[np.float64]:
    fast = total_g_ratio * fast_term_fraction
    slow = total_g_ratio * (1.0 - fast_term_fraction)
    return instantaneous_shear_modulus_pa * (
        1.0
        - total_g_ratio
        + fast * np.exp(-times_s / fast_relaxation_time_s)
        + slow * np.exp(-times_s / slow_relaxation_time_s)
    )


def _transformed(value: PronyParameterPlan, raw: float) -> float:
    return math.log(raw) if value.transform == "log" else raw


def _physical(parameter: PronyParameterPlan, transformed: float) -> float:
    return math.exp(transformed) if parameter.transform == "log" else transformed


def _at_bound(value: float, lower: float, upper: float) -> bool:
    tolerance = max(1e-9, (upper - lower) * 1e-5)
    return value - lower <= tolerance or upper - value <= tolerance


def calibrate_reference_prony(
    *,
    plan: ReferencePronyCalibrationPlanContent,
    points: tuple[ShearRelaxationPoint, ...],
    instantaneous_shear_modulus_pa: float,
) -> tuple[PronyCalibrationCandidate, ...]:
    if len(points) < 5:
        raise InvalidPronyCalibration("reference Prony calibration requires at least five points")
    _positive("instantaneous_shear_modulus_pa", instantaneous_shear_modulus_pa)
    times = np.asarray([point.time_s for point in points], dtype=np.float64)
    observed = np.asarray([point.shear_modulus_pa for point in points], dtype=np.float64)
    if np.any(~np.isfinite(times)) or np.any(~np.isfinite(observed)):
        raise InvalidPronyCalibration("calibration points must be finite")
    parameters = (
        plan.total_g_ratio,
        plan.fast_term_fraction,
        plan.fast_relaxation_time_s,
        plan.slow_relaxation_time_s,
    )
    lower = np.asarray([_transformed(item, item.lower) for item in parameters])
    upper = np.asarray([_transformed(item, item.upper) for item in parameters])
    initial = np.asarray([_transformed(item, item.initial) for item in parameters])
    rng = np.random.Generator(np.random.PCG64(plan.random_seed))
    starts = [initial]
    starts.extend(rng.uniform(lower, upper) for _ in range(plan.multistart_count - 1))
    candidates: list[PronyCalibrationCandidate] = []
    for ordinal, start in enumerate(starts, 1):
        def residual(values: NDArray[np.float64]) -> NDArray[np.float64]:
            physical = tuple(
                _physical(parameter, float(value))
                for parameter, value in zip(parameters, values, strict=True)
            )
            predicted = evaluate_two_term_prony(
                instantaneous_shear_modulus_pa=instantaneous_shear_modulus_pa,
                times_s=times,
                total_g_ratio=physical[0],
                fast_term_fraction=physical[1],
                fast_relaxation_time_s=physical[2],
                slow_relaxation_time_s=physical[3],
            )
            return (predicted - observed) / plan.normalization_modulus_pa

        result = least_squares(
            residual,
            start,
            bounds=(lower, upper),
            method="trf",
            max_nfev=plan.maximum_function_evaluations,
            ftol=plan.ftol,
            xtol=plan.xtol,
            gtol=plan.gtol,
        )
        physical = tuple(
            _physical(parameter, float(value))
            for parameter, value in zip(parameters, result.x, strict=True)
        )
        predicted_array = evaluate_two_term_prony(
            instantaneous_shear_modulus_pa=instantaneous_shear_modulus_pa,
            times_s=times,
            total_g_ratio=physical[0],
            fast_term_fraction=physical[1],
            fast_relaxation_time_s=physical[2],
            slow_relaxation_time_s=physical[3],
        )
        residual_array = predicted_array - observed
        normalized = residual_array / plan.normalization_modulus_pa
        fast_g = physical[0] * physical[1]
        slow_g = physical[0] * (1.0 - physical[1])
        rank = int(np.linalg.matrix_rank(result.jac))
        values_at_bound = any(
            _at_bound(value, parameter.lower, parameter.upper)
            for value, parameter in zip(physical, parameters, strict=True)
        )
        objective_total = float(np.mean(normalized**2))
        candidate_status = "converged" if result.success else "nonconverged"
        canonical = {
            "attempt_ordinal": ordinal,
            "total_g_ratio": physical[0],
            "fast_term_fraction": physical[1],
            "fast_g_ratio": fast_g,
            "slow_g_ratio": slow_g,
            "fast_relaxation_time_s": physical[2],
            "slow_relaxation_time_s": physical[3],
            "objective_total": objective_total,
            "status": candidate_status,
        }
        candidates.append(
            PronyCalibrationCandidate(
                attempt_ordinal=ordinal,
                initial_values=(
                    _physical(parameters[0], float(start[0])),
                    _physical(parameters[1], float(start[1])),
                    _physical(parameters[2], float(start[2])),
                    _physical(parameters[3], float(start[3])),
                ),
                total_g_ratio=physical[0],
                fast_term_fraction=physical[1],
                fast_g_ratio=fast_g,
                slow_g_ratio=slow_g,
                fast_relaxation_time_s=physical[2],
                slow_relaxation_time_s=physical[3],
                objective_total=objective_total,
                residual_root_mean_square_pa=float(np.sqrt(np.mean(residual_array**2))),
                residual_mean_pa=float(np.mean(residual_array)),
                status=candidate_status,
                convergence_status_code=int(result.status),
                convergence_reason=str(result.message)[:255],
                function_evaluations=int(result.nfev),
                jacobian_evaluations=(int(result.njev) if result.njev is not None else None),
                optimality=float(result.optimality),
                parameter_at_bound=values_at_bound,
                identifiability_status=("full_rank" if rank == 4 else "rank_deficient"),
                uncertainty_status="not_assessed_reference",
                predicted_modulus_pa=tuple(float(value) for value in predicted_array),
                residual_pa=tuple(float(value) for value in residual_array),
                candidate_sha256=content_sha256(canonical),
            )
        )
    return tuple(candidates)


def prony_diagnostics_parquet_bytes(
    *,
    points: tuple[ShearRelaxationPoint, ...],
    candidate: PronyCalibrationCandidate,
) -> bytes:
    if len(points) != len(candidate.predicted_modulus_pa):
        raise InvalidPronyCalibration("candidate diagnostics point count mismatch")
    table = pa.table(
        {
            "point_ordinal": pa.array(range(len(points)), type=pa.int32()),
            "time_s": pa.array([point.time_s for point in points], type=pa.float64()),
            "observed_shear_modulus_pa": pa.array(
                [point.shear_modulus_pa for point in points], type=pa.float64()
            ),
            "predicted_shear_modulus_pa": pa.array(
                candidate.predicted_modulus_pa, type=pa.float64()
            ),
            "residual_pa": pa.array(candidate.residual_pa, type=pa.float64()),
        }
    )
    sink = pa.BufferOutputStream()
    cast(Any, pq.write_table)(
        table,
        sink,
        compression="zstd",
        version="2.6",
        use_dictionary=False,
        write_statistics=True,
    )
    return cast(bytes, sink.getvalue().to_pybytes())


def prony_diagnostics_from_parquet(value: bytes) -> tuple[dict[str, float | int], ...]:
    try:
        table = cast(Any, pq.read_table)(pa.BufferReader(value))
    except Exception as error:
        raise InvalidPronyCalibration("diagnostics Artifact is not valid Parquet") from error
    expected = (
        "point_ordinal",
        "time_s",
        "observed_shear_modulus_pa",
        "predicted_shear_modulus_pa",
        "residual_pa",
    )
    if tuple(table.column_names) != expected:
        raise InvalidPronyCalibration("diagnostics Artifact schema is invalid")
    rows = table.to_pylist()
    return tuple(
        {
            "point_ordinal": int(row["point_ordinal"]),
            "time_s": float(row["time_s"]),
            "observed_shear_modulus_pa": float(row["observed_shear_modulus_pa"]),
            "predicted_shear_modulus_pa": float(row["predicted_shear_modulus_pa"]),
            "residual_pa": float(row["residual_pa"]),
        }
        for row in rows
    )
