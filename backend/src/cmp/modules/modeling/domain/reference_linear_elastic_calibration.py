"""Typed, non-production reference calibration for one uniaxial tensile curve.

The implementation deliberately occupies a very small, explicit corner of the eventual
calibration capability: a single normalized engineering stress--strain curve and the one
parameter ``youngs_modulus_pa`` of the existing reference linear-elastic model.  It is not a
general constitutive-model library or a production material-card qualification workflow.

Every numerical convention is represented in the immutable Plan content.  In particular, the
normalization stress scale, uniform point weighting, observed x-domain, seed and multistart
count are not inferred from a moving Dataset head or hidden in an optimizer configuration.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import cast
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.modules.modeling.domain.reference_linear_elasticity import (
    REFERENCE_MODEL_FAMILY_ID,
    REFERENCE_MODEL_SCHEMA_DIGEST,
    REFERENCE_MODEL_SCHEMA_VERSION,
)
from cmp.shared.domain.revisions import content_sha256

REFERENCE_LINEAR_ELASTIC_CALIBRATION_PLAN_KIND = "reference_uniaxial_linear_elasticity"
REFERENCE_LINEAR_ELASTIC_CALIBRATION_SCHEMA_VERSION = "1.0.0"
REFERENCE_LINEAR_ELASTIC_CALIBRATION_SCHEMA_ID = (
    "urn:cmp:modeling:reference-uniaxial-linear-elastic-calibration:1.0.0"
)
REFERENCE_UNIAXIAL_TENSION_TEST_MODE = "reference_uniaxial_tension"
REFERENCE_LINEAR_ELASTIC_EVALUATOR_ID = (
    "urn:cmp:reference:linear-elastic-closed-form-curve-evaluator:1.0.0"
)
REFERENCE_LINEAR_ELASTIC_EVALUATOR_VERSION = "1.0.0"
REFERENCE_LINEAR_ELASTIC_EVALUATION_MODE = "closed_form_curve"
REFERENCE_ANALYTIC_WLS_CALIBRATOR_ID = (
    "urn:cmp:reference:analytic-bounded-weighted-least-squares:1.0.0"
)
REFERENCE_ANALYTIC_WLS_CALIBRATOR_VERSION = "1.0.0"
REFERENCE_LINEAR_ELASTIC_PARAMETER = "youngs_modulus_pa"
REFERENCE_LINEAR_ELASTIC_DIAGNOSTICS_SCHEMA = (
    "urn:cmp:modeling:reference-linear-elastic-calibration-diagnostics-parquet:1.0.0"
)
REFERENCE_CALIBRATION_ENVIRONMENT_DIGEST = content_sha256(
    {
        "evaluator_id": REFERENCE_LINEAR_ELASTIC_EVALUATOR_ID,
        "evaluator_version": REFERENCE_LINEAR_ELASTIC_EVALUATOR_VERSION,
        "calibrator_id": REFERENCE_ANALYTIC_WLS_CALIBRATOR_ID,
        "calibrator_version": REFERENCE_ANALYTIC_WLS_CALIBRATOR_VERSION,
        "algorithm": "analytic_bounded_weighted_least_squares_sigma_equals_E_times_epsilon",
        "non_production": True,
    }
)

_write_parquet_table = cast(Callable[..., None], pq.write_table)
_read_parquet_table = cast(Callable[..., pa.Table], pq.read_table)


class CalibrationError(Exception):
    """Base error for the reference calibration boundary."""


class InvalidCalibrationPlan(CalibrationError, ValueError):
    """A numerical convention or pinned input is not valid for this reference slice."""


class CalibrationConflict(CalibrationError):
    """A mutable head, scope, or append-only execution invariant conflicted."""


class CalibrationNotFound(CalibrationError):
    """A calibration resource is absent or not visible in the active tenant."""


class CalibrationRunStatus(StrEnum):
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CalibrationAttemptStatus(StrEnum):
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CalibrationCandidateStatus(StrEnum):
    CONVERGED = "converged"
    NONCONVERGED = "nonconverged"
    FAILED = "failed"


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidCalibrationPlan(f"{name} must be non-zero")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidCalibrationPlan(f"{name} must be trimmed and contain 1..{maximum} characters")


def _positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise InvalidCalibrationPlan(f"{name} must be finite and greater than zero")


@dataclass(frozen=True, slots=True)
class ReferenceLinearElasticCalibrationPlanContent:
    """One fixed reference calibration configuration and its concrete input revisions."""

    plan_label: str
    selection_id: UUID
    selection_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    youngs_modulus_lower_bound_pa: float
    youngs_modulus_initial_value_pa: float
    youngs_modulus_upper_bound_pa: float
    normalization_stress_scale_pa: float
    multistart_count: int
    random_seed: int
    plan_kind: str = REFERENCE_LINEAR_ELASTIC_CALIBRATION_PLAN_KIND
    model_family_id: str = REFERENCE_MODEL_FAMILY_ID
    model_schema_version: str = REFERENCE_MODEL_SCHEMA_VERSION
    model_schema_digest: str = REFERENCE_MODEL_SCHEMA_DIGEST
    test_mode: str = REFERENCE_UNIAXIAL_TENSION_TEST_MODE
    evaluator_id: str = REFERENCE_LINEAR_ELASTIC_EVALUATOR_ID
    evaluator_version: str = REFERENCE_LINEAR_ELASTIC_EVALUATOR_VERSION
    evaluation_mode: str = REFERENCE_LINEAR_ELASTIC_EVALUATION_MODE
    calibrator_id: str = REFERENCE_ANALYTIC_WLS_CALIBRATOR_ID
    calibrator_version: str = REFERENCE_ANALYTIC_WLS_CALIBRATOR_VERSION
    parameter_name: str = REFERENCE_LINEAR_ELASTIC_PARAMETER
    point_weighting: str = "uniform_point_weight"
    objective_aggregation: str = "mean_normalized_squared_residual"
    x_domain_policy: str = "all_observed_points"
    missing_data_policy: str = "reject"
    non_production: bool = True

    def __post_init__(self) -> None:
        _text("plan_label", self.plan_label, 160)
        for name in (
            "selection_id",
            "selection_revision_id",
            "material_model_id",
            "material_model_revision_id",
        ):
            _uuid(name, getattr(self, name))
        _positive("youngs_modulus_lower_bound_pa", self.youngs_modulus_lower_bound_pa)
        _positive("youngs_modulus_initial_value_pa", self.youngs_modulus_initial_value_pa)
        _positive("youngs_modulus_upper_bound_pa", self.youngs_modulus_upper_bound_pa)
        _positive("normalization_stress_scale_pa", self.normalization_stress_scale_pa)
        if self.youngs_modulus_lower_bound_pa >= self.youngs_modulus_upper_bound_pa:
            raise InvalidCalibrationPlan("Young's modulus bounds must be strictly ordered")
        if not (
            self.youngs_modulus_lower_bound_pa
            <= self.youngs_modulus_initial_value_pa
            <= self.youngs_modulus_upper_bound_pa
        ):
            raise InvalidCalibrationPlan("initial Young's modulus must be within explicit bounds")
        if not 1 <= self.multistart_count <= 16:
            raise InvalidCalibrationPlan("multistart_count must be between 1 and 16")
        if not -(2**63) <= self.random_seed < 2**63:
            raise InvalidCalibrationPlan("random_seed must be a signed 64-bit integer")
        if (
            self.plan_kind != REFERENCE_LINEAR_ELASTIC_CALIBRATION_PLAN_KIND
            or self.model_family_id != REFERENCE_MODEL_FAMILY_ID
            or self.model_schema_version != REFERENCE_MODEL_SCHEMA_VERSION
            or self.model_schema_digest != REFERENCE_MODEL_SCHEMA_DIGEST
            or self.test_mode != REFERENCE_UNIAXIAL_TENSION_TEST_MODE
            or self.evaluator_id != REFERENCE_LINEAR_ELASTIC_EVALUATOR_ID
            or self.evaluator_version != REFERENCE_LINEAR_ELASTIC_EVALUATOR_VERSION
            or self.evaluation_mode != REFERENCE_LINEAR_ELASTIC_EVALUATION_MODE
            or self.calibrator_id != REFERENCE_ANALYTIC_WLS_CALIBRATOR_ID
            or self.calibrator_version != REFERENCE_ANALYTIC_WLS_CALIBRATOR_VERSION
            or self.parameter_name != REFERENCE_LINEAR_ELASTIC_PARAMETER
            or self.point_weighting != "uniform_point_weight"
            or self.objective_aggregation != "mean_normalized_squared_residual"
            or self.x_domain_policy != "all_observed_points"
            or self.missing_data_policy != "reject"
            or not self.non_production
        ):
            raise InvalidCalibrationPlan(
                "reference calibration plan must retain its fixed non-production contract"
            )


@dataclass(frozen=True, slots=True)
class CalibrationCurvePoint:
    """Explicit observed, predicted, and residual channels held in a derived Artifact."""

    engineering_strain: float
    observed_engineering_stress_pa: float
    predicted_engineering_stress_pa: float
    residual_engineering_stress_pa: float
    normalized_residual: float

    def __post_init__(self) -> None:
        for name in (
            "engineering_strain",
            "observed_engineering_stress_pa",
            "predicted_engineering_stress_pa",
            "residual_engineering_stress_pa",
            "normalized_residual",
        ):
            if not math.isfinite(getattr(self, name)):
                raise InvalidCalibrationPlan(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class ReferenceCalibrationOutcome:
    """A deterministic diagnostic result for one recorded multistart attempt."""

    initial_youngs_modulus_pa: float
    calibrated_youngs_modulus_pa: float
    objective_total: float
    residual_root_mean_square_pa: float
    residual_mean_pa: float
    bound_sticking: bool
    convergence_reason: str
    curve: tuple[CalibrationCurvePoint, ...]
    identifiability_status: str = "not_assessed_reference_one_parameter"
    uncertainty_status: str = "not_estimated_reference"

    def __post_init__(self) -> None:
        _positive("initial_youngs_modulus_pa", self.initial_youngs_modulus_pa)
        _positive("calibrated_youngs_modulus_pa", self.calibrated_youngs_modulus_pa)
        for name in ("objective_total", "residual_root_mean_square_pa", "residual_mean_pa"):
            if not math.isfinite(getattr(self, name)):
                raise InvalidCalibrationPlan(f"{name} must be finite")
        if self.objective_total < 0.0 or self.residual_root_mean_square_pa < 0.0:
            raise InvalidCalibrationPlan("objective and residual RMS cannot be negative")
        _text("convergence_reason", self.convergence_reason, 255)
        if len(self.curve) < 2:
            raise InvalidCalibrationPlan("reference calibration requires at least two curve points")


def reference_linear_elastic_calibration_plan_canonical(
    value: ReferenceLinearElasticCalibrationPlanContent,
) -> dict[str, object]:
    """Canonical immutable Plan payload; no generic optimizer JSON is persisted."""

    return {
        "plan_kind": value.plan_kind,
        "plan_label": value.plan_label,
        "selection_id": str(value.selection_id),
        "selection_revision_id": str(value.selection_revision_id),
        "material_model_id": str(value.material_model_id),
        "material_model_revision_id": str(value.material_model_revision_id),
        "model_family_id": value.model_family_id,
        "model_schema_version": value.model_schema_version,
        "model_schema_digest": value.model_schema_digest,
        "test_mode": value.test_mode,
        "evaluator": {
            "id": value.evaluator_id,
            "version": value.evaluator_version,
            "evaluation_mode": value.evaluation_mode,
        },
        "calibrator": {"id": value.calibrator_id, "version": value.calibrator_version},
        "parameters": [
            {
                "name": value.parameter_name,
                "lower_bound_pa": value.youngs_modulus_lower_bound_pa,
                "initial_value_pa": value.youngs_modulus_initial_value_pa,
                "upper_bound_pa": value.youngs_modulus_upper_bound_pa,
            }
        ],
        "objective": {
            "normalization_stress_scale_pa": value.normalization_stress_scale_pa,
            "point_weighting": value.point_weighting,
            "aggregation": value.objective_aggregation,
            "x_domain_policy": value.x_domain_policy,
            "missing_data_policy": value.missing_data_policy,
        },
        "execution": {
            "multistart_count": value.multistart_count,
            "random_seed": value.random_seed,
            "determinism": "reference_r3_same_environment_tolerance",
        },
        "non_production": value.non_production,
    }


def _deterministic_start(
    plan: ReferenceLinearElasticCalibrationPlanContent, attempt_ordinal: int
) -> float:
    """Derive a recorded start without introducing hidden random state.

    The analytic reference solution is independent of its initial value.  Additional starts are
    still retained so orchestration, seed preservation and candidate comparison can be exercised
    honestly before a future approved numerical optimizer is chosen.
    """

    if attempt_ordinal == 1:
        return plan.youngs_modulus_initial_value_pa
    digest = hashlib.sha256(f"{plan.random_seed}:{attempt_ordinal}".encode("ascii")).digest()
    fraction = int.from_bytes(digest[:8], byteorder="big") / float(2**64 - 1)
    return plan.youngs_modulus_lower_bound_pa + fraction * (
        plan.youngs_modulus_upper_bound_pa - plan.youngs_modulus_lower_bound_pa
    )


def calibrate_reference_linear_elastic_curve(
    plan: ReferenceLinearElasticCalibrationPlanContent,
    points: tuple[tuple[float, float], ...],
    *,
    attempt_ordinal: int,
) -> ReferenceCalibrationOutcome:
    """Fit ``sigma = E * epsilon`` using explicit bounded normalized least squares.

    This is a closed-form, deterministic *reference* evaluator.  It intentionally does not claim
    a production optimizer, uncertainty estimate, material-point integration, or validated
    constitutive-model calibration.
    """

    if not 1 <= attempt_ordinal <= plan.multistart_count:
        raise InvalidCalibrationPlan("attempt ordinal is outside the immutable multistart range")
    if len(points) < 2:
        raise InvalidCalibrationPlan("reference calibration requires at least two observations")
    denominator = 0.0
    numerator = 0.0
    for engineering_strain, engineering_stress_pa in points:
        if (
            not math.isfinite(engineering_strain)
            or not math.isfinite(engineering_stress_pa)
            or engineering_strain < 0.0
            or engineering_stress_pa < 0.0
        ):
            raise InvalidCalibrationPlan(
                "reference calibration accepts finite non-negative normalized tensile points"
            )
        denominator += engineering_strain * engineering_strain
        numerator += engineering_strain * engineering_stress_pa
    if not math.isfinite(denominator) or denominator <= 0.0:
        raise InvalidCalibrationPlan(
            "reference calibration needs at least one observation with positive engineering strain"
        )
    unconstrained = numerator / denominator
    calibrated = min(
        max(unconstrained, plan.youngs_modulus_lower_bound_pa),
        plan.youngs_modulus_upper_bound_pa,
    )
    curve = tuple(
        CalibrationCurvePoint(
            engineering_strain=engineering_strain,
            observed_engineering_stress_pa=engineering_stress_pa,
            predicted_engineering_stress_pa=calibrated * engineering_strain,
            residual_engineering_stress_pa=(calibrated * engineering_strain)
            - engineering_stress_pa,
            normalized_residual=((calibrated * engineering_strain) - engineering_stress_pa)
            / plan.normalization_stress_scale_pa,
        )
        for engineering_strain, engineering_stress_pa in points
    )
    normalized_squared = [point.normalized_residual**2 for point in curve]
    residuals = [point.residual_engineering_stress_pa for point in curve]
    objective = sum(normalized_squared) / len(normalized_squared)
    residual_rms = math.sqrt(sum(value * value for value in residuals) / len(residuals))
    residual_mean = sum(residuals) / len(residuals)
    return ReferenceCalibrationOutcome(
        initial_youngs_modulus_pa=_deterministic_start(plan, attempt_ordinal),
        calibrated_youngs_modulus_pa=calibrated,
        objective_total=objective,
        residual_root_mean_square_pa=residual_rms,
        residual_mean_pa=residual_mean,
        bound_sticking=(
            calibrated == plan.youngs_modulus_lower_bound_pa
            or calibrated == plan.youngs_modulus_upper_bound_pa
        ),
        convergence_reason="analytic_bounded_weighted_least_squares",
        curve=curve,
    )


def reference_calibration_diagnostics_parquet_bytes(
    points: tuple[CalibrationCurvePoint, ...],
) -> bytes:
    """Encode complete curve diagnostics as a typed derived Artifact."""

    if len(points) < 2:
        raise InvalidCalibrationPlan("diagnostic curve needs at least two points")
    table = pa.table(
        {
            "engineering_strain": pa.array(
                [point.engineering_strain for point in points], type=pa.float64()
            ),
            "observed_engineering_stress_pa": pa.array(
                [point.observed_engineering_stress_pa for point in points], type=pa.float64()
            ),
            "predicted_engineering_stress_pa": pa.array(
                [point.predicted_engineering_stress_pa for point in points], type=pa.float64()
            ),
            "residual_engineering_stress_pa": pa.array(
                [point.residual_engineering_stress_pa for point in points], type=pa.float64()
            ),
            "normalized_residual": pa.array(
                [point.normalized_residual for point in points], type=pa.float64()
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


def reference_calibration_diagnostics_from_parquet(
    value: bytes,
) -> tuple[CalibrationCurvePoint, ...]:
    """Read the five declared diagnostic columns and reject any malformed Artifact."""

    columns = [
        "engineering_strain",
        "observed_engineering_stress_pa",
        "predicted_engineering_stress_pa",
        "residual_engineering_stress_pa",
        "normalized_residual",
    ]
    try:
        table = _read_parquet_table(pa.BufferReader(value), columns=columns)
    except Exception as error:
        raise InvalidCalibrationPlan(
            "calibration diagnostic Artifact is not the declared reference Parquet schema"
        ) from error
    if tuple(table.column_names) != tuple(columns):
        raise InvalidCalibrationPlan("calibration diagnostic Artifact channel names are invalid")
    values = [table.column(name).to_pylist() for name in columns]
    if len({len(column) for column in values}) != 1 or len(values[0]) < 2:
        raise InvalidCalibrationPlan("calibration diagnostic Artifact point count is invalid")
    return tuple(
        CalibrationCurvePoint(
            engineering_strain=float(row[0]),
            observed_engineering_stress_pa=float(row[1]),
            predicted_engineering_stress_pa=float(row[2]),
            residual_engineering_stress_pa=float(row[3]),
            normalized_residual=float(row[4]),
        )
        for row in zip(*values, strict=True)
    )


def calibration_candidate_content_hash(
    *,
    calibration_run_id: UUID,
    attempt_ordinal: int,
    calibrated_youngs_modulus_pa: float,
    objective_total: float,
    diagnostics_sha256: str,
) -> str:
    """Stable digest used by T-24 selection/promotion without storing opaque candidate JSON."""

    return content_sha256(
        {
            "calibration_run_id": str(calibration_run_id),
            "attempt_ordinal": attempt_ordinal,
            "parameter": {"youngs_modulus_pa": calibrated_youngs_modulus_pa},
            "objective_total": objective_total,
            "diagnostics_sha256": diagnostics_sha256,
        }
    )
