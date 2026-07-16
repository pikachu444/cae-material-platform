"""Bounded multi-test one-term Ogden calibration with explicit diagnostics.

This reference kernel consumes normalized nominal stress/engineering-strain curves.  It does not
execute a solver and it never promotes a candidate automatically.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from importlib.metadata import version
from typing import Any, cast
from uuid import UUID

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray
from scipy.optimize import least_squares  # type: ignore[import-untyped]

from cmp.modules.modeling.domain.scientific_profile import OgdenScientificParameters
from cmp.shared.domain.revisions import content_sha256

REFERENCE_OGDEN_CALIBRATION_PLAN_SCHEMA_ID = (
    "urn:cmp:modeling:reference-multi-test-ogden-calibration-plan:1.0.0"
)
REFERENCE_OGDEN_CALIBRATION_PLAN_SCHEMA_VERSION = "1.0.0"
REFERENCE_OGDEN_CALIBRATION_DIAGNOSTICS_SCHEMA = (
    "urn:cmp:modeling:reference-ogden-calibration-diagnostics-parquet:1.0.0"
)
REFERENCE_OGDEN_CALIBRATION_ENVIRONMENT_DIGEST = "sha256:" + content_sha256(
    {
        "kernel": "reference-multi-test-one-term-ogden:1.0.0",
        "numpy": version("numpy"),
        "scipy": version("scipy"),
        "optimizer": "least_squares:trf",
    }
)


class InvalidOgdenCalibration(ValueError):
    pass


class OgdenCalibrationRole(StrEnum):
    CALIBRATION = "calibration"
    HOLDOUT = "holdout"


class OgdenTestMode(StrEnum):
    UNIAXIAL_TENSION = "uniaxial_tension"
    PLANAR_TENSION = "planar_tension"
    BIAXIAL_TENSION = "biaxial_tension"


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidOgdenCalibration(f"{name} must be non-zero")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidOgdenCalibration(f"{name} must be trimmed and contain 1..{maximum} characters")


@dataclass(frozen=True, slots=True)
class OgdenCalibrationMember:
    ordinal: int
    role: OgdenCalibrationRole
    test_mode: OgdenTestMode
    dataset_id: UUID
    dataset_revision_id: UUID
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not 0 <= self.ordinal < 24:
            raise InvalidOgdenCalibration("member ordinal must be within 0..23")
        _nonzero("dataset_id", self.dataset_id)
        _nonzero("dataset_revision_id", self.dataset_revision_id)
        if not math.isfinite(self.weight) or self.weight <= 0:
            raise InvalidOgdenCalibration("member weight must be finite and greater than zero")

    def canonical(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "role": self.role.value,
            "test_mode": self.test_mode.value,
            "dataset_id": str(self.dataset_id),
            "dataset_revision_id": str(self.dataset_revision_id),
            "weight": self.weight,
        }


@dataclass(frozen=True, slots=True)
class ReferenceOgdenCalibrationPlanContent:
    plan_label: str
    scientific_profile_id: UUID
    scientific_profile_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    baseline_model_id: UUID
    baseline_model_revision_id: UUID
    members: tuple[OgdenCalibrationMember, ...]
    evaluator: str = "one_term_incompressible_ogden_nominal"
    objective: str = "normalized_weighted_least_squares"
    aggregation_order: str = "point_then_curve_then_mode"
    holdout_policy: str = "explicit_disjoint"
    maximum_function_evaluations: int = 5000
    non_production: bool = True

    def __post_init__(self) -> None:
        _text("plan_label", self.plan_label, 160)
        for name, value in (
            ("scientific_profile_id", self.scientific_profile_id),
            ("scientific_profile_revision_id", self.scientific_profile_revision_id),
            ("material_state_id", self.material_state_id),
            ("material_state_revision_id", self.material_state_revision_id),
            ("baseline_model_id", self.baseline_model_id),
            ("baseline_model_revision_id", self.baseline_model_revision_id),
        ):
            _nonzero(name, value)
        if not 1 <= len(self.members) <= 24:
            raise InvalidOgdenCalibration("Ogden calibration requires 1..24 Dataset members")
        if tuple(item.ordinal for item in self.members) != tuple(range(len(self.members))):
            raise InvalidOgdenCalibration("member ordinals must be contiguous and ordered")
        revisions = tuple(item.dataset_revision_id for item in self.members)
        if len(revisions) != len(set(revisions)):
            raise InvalidOgdenCalibration("a Dataset revision can appear only once in a Plan")
        if not any(item.role is OgdenCalibrationRole.CALIBRATION for item in self.members):
            raise InvalidOgdenCalibration("at least one calibration member is required")
        if (
            self.evaluator != "one_term_incompressible_ogden_nominal"
            or self.objective != "normalized_weighted_least_squares"
            or self.aggregation_order != "point_then_curve_then_mode"
            or self.holdout_policy != "explicit_disjoint"
            or self.maximum_function_evaluations != 5000
            or not self.non_production
        ):
            raise InvalidOgdenCalibration("reference Ogden calibration policy was changed")

    def canonical(self) -> dict[str, object]:
        return {
            "plan_label": self.plan_label,
            "scientific_profile_id": str(self.scientific_profile_id),
            "scientific_profile_revision_id": str(self.scientific_profile_revision_id),
            "material_state_id": str(self.material_state_id),
            "material_state_revision_id": str(self.material_state_revision_id),
            "baseline_model_id": str(self.baseline_model_id),
            "baseline_model_revision_id": str(self.baseline_model_revision_id),
            "members": [item.canonical() for item in self.members],
            "evaluator": self.evaluator,
            "objective": self.objective,
            "aggregation_order": self.aggregation_order,
            "holdout_policy": self.holdout_policy,
            "maximum_function_evaluations": self.maximum_function_evaluations,
            "non_production": self.non_production,
        }


@dataclass(frozen=True, slots=True)
class OgdenCalibrationCurve:
    member: OgdenCalibrationMember
    engineering_strain: tuple[float, ...]
    nominal_stress_pa: tuple[float, ...]

    def __post_init__(self) -> None:
        if not 5 <= len(self.engineering_strain) <= 50_000:
            raise InvalidOgdenCalibration("each calibration curve requires 5..50000 points")
        if len(self.engineering_strain) != len(self.nominal_stress_pa):
            raise InvalidOgdenCalibration("strain and stress arrays must have equal length")
        previous = -math.inf
        for strain, stress in zip(
            self.engineering_strain, self.nominal_stress_pa, strict=True
        ):
            if (
                not math.isfinite(strain)
                or not math.isfinite(stress)
                or strain < 0
                or stress < 0
                or strain <= previous
            ):
                raise InvalidOgdenCalibration(
                    "Ogden reference curves require finite non-negative, increasing tension data"
                )
            previous = strain
        if max(self.nominal_stress_pa) <= 0:
            raise InvalidOgdenCalibration("calibration curve stress scale must be positive")

    @property
    def normalization_stress_pa(self) -> float:
        return max(abs(value) for value in self.nominal_stress_pa)


@dataclass(frozen=True, slots=True)
class OgdenDiagnosticPoint:
    member_ordinal: int
    role: OgdenCalibrationRole
    test_mode: OgdenTestMode
    dataset_id: UUID
    dataset_revision_id: UUID
    point_ordinal: int
    engineering_strain: float
    stretch: float
    observed_nominal_stress_pa: float
    predicted_nominal_stress_pa: float
    residual_pa: float
    normalized_residual: float
    effective_weight: float


@dataclass(frozen=True, slots=True)
class OgdenCalibrationCandidate:
    attempt_ordinal: int
    initial_mu_pa: float
    initial_alpha: float
    mu_pa: float
    alpha: float
    objective_total: float
    uniaxial_objective: float
    planar_objective: float
    biaxial_objective: float
    calibration_rmse_pa: float
    calibration_normalized_rmse: float
    holdout_rmse_pa: float | None
    holdout_normalized_rmse: float | None
    status: str
    convergence_status_code: int
    convergence_reason: str
    function_evaluations: int
    jacobian_evaluations: int | None
    optimality: float
    parameter_at_bound: bool
    jacobian_rank: int
    jacobian_condition_number: float | None
    identifiability_status: str
    uncertainty_status: str
    mu_standard_error_pa: float | None
    alpha_standard_error: float | None
    mu_confidence_lower_pa: float | None
    mu_confidence_upper_pa: float | None
    alpha_confidence_lower: float | None
    alpha_confidence_upper: float | None
    warnings: tuple[str, ...]
    candidate_sha256: str
    diagnostics: tuple[OgdenDiagnosticPoint, ...]


def ogden_nominal_stress_pa(
    mode: OgdenTestMode,
    engineering_strain: NDArray[np.float64],
    mu_pa: float,
    alpha: float,
) -> NDArray[np.float64]:
    """Return incompressible one-term Ogden nominal stress for three public test modes."""

    stretch = 1.0 + engineering_strain
    if mode is OgdenTestMode.UNIAXIAL_TENSION:
        response = stretch ** (alpha - 1.0) - stretch ** (-alpha / 2.0 - 1.0)
    elif mode is OgdenTestMode.PLANAR_TENSION:
        response = stretch ** (alpha - 1.0) - stretch ** (-alpha - 1.0)
    else:
        response = stretch ** (alpha - 1.0) - stretch ** (-2.0 * alpha - 1.0)
    return (2.0 * mu_pa / alpha) * response


def _mode_weight(parameters: OgdenScientificParameters, mode: OgdenTestMode) -> float:
    return {
        OgdenTestMode.UNIAXIAL_TENSION: parameters.uniaxial_weight,
        OgdenTestMode.PLANAR_TENSION: parameters.planar_weight,
        OgdenTestMode.BIAXIAL_TENSION: parameters.biaxial_weight,
    }[mode]


def _effective_weights(
    curves: tuple[OgdenCalibrationCurve, ...],
    parameters: OgdenScientificParameters,
) -> dict[int, float]:
    counts = Counter(curve.member.test_mode for curve in curves)
    return {
        curve.member.ordinal: (
            _mode_weight(parameters, curve.member.test_mode)
            * curve.member.weight
            / counts[curve.member.test_mode]
            / len(curve.engineering_strain)
        )
        for curve in curves
    }


def _at_bound(value: float, lower: float, upper: float) -> bool:
    span = upper - lower
    return min(value - lower, upper - value) <= max(span * 1e-6, abs(value) * 1e-9)


def _uncertainty(
    jacobian: NDArray[np.float64],
    residual: NDArray[np.float64],
    scales: NDArray[np.float64],
) -> tuple[str, tuple[float, float] | None]:
    rank = int(np.linalg.matrix_rank(jacobian))
    if rank < 2:
        return "not_estimable_rank_deficient", None
    degrees_of_freedom = residual.size - 2
    if degrees_of_freedom <= 0:
        return "not_estimable_insufficient_dof", None
    try:
        covariance = (
            np.linalg.inv(jacobian.T @ jacobian)
            * float(residual @ residual)
            / degrees_of_freedom
        )
        standard = np.sqrt(np.diag(covariance)) * scales
    except (np.linalg.LinAlgError, ValueError, FloatingPointError):
        return "not_estimable_nonfinite", None
    if standard.shape != (2,) or not np.all(np.isfinite(standard)):
        return "not_estimable_nonfinite", None
    return "estimated_jacobian_covariance", (float(standard[0]), float(standard[1]))


def calibrate_reference_ogden(
    *,
    parameters: OgdenScientificParameters,
    multistart_count: int,
    seed: int,
    maximum_function_evaluations: int,
    curves: tuple[OgdenCalibrationCurve, ...],
) -> tuple[OgdenCalibrationCandidate, ...]:
    calibration = tuple(
        curve for curve in curves if curve.member.role is OgdenCalibrationRole.CALIBRATION
    )
    holdout = tuple(curve for curve in curves if curve.member.role is OgdenCalibrationRole.HOLDOUT)
    if not calibration:
        raise InvalidOgdenCalibration("at least one calibration curve is required")
    if sum(len(curve.engineering_strain) for curve in curves) > 50_000:
        raise InvalidOgdenCalibration("reference Ogden calibration is limited to 50000 points")
    if not 1 <= multistart_count <= 32:
        raise InvalidOgdenCalibration("multistart_count must be within 1..32")

    scales = np.array([parameters.mu_scale_pa, parameters.alpha_scale], dtype=np.float64)
    lower = np.array([parameters.mu_lower_pa, parameters.alpha_lower]) / scales
    upper = np.array([parameters.mu_upper_pa, parameters.alpha_upper]) / scales
    initial = np.array([parameters.mu_initial_pa, parameters.alpha_initial]) / scales
    rng = np.random.Generator(np.random.PCG64(seed))
    starts = [initial]
    starts.extend(rng.uniform(lower, upper) for _ in range(multistart_count - 1))
    calibration_weights = _effective_weights(calibration, parameters)
    holdout_weights = _effective_weights(holdout, parameters) if holdout else {}

    def objective(scaled: NDArray[np.float64]) -> NDArray[np.float64]:
        mu_pa, alpha = scaled * scales
        values: list[NDArray[np.float64]] = []
        for curve in calibration:
            strain = np.asarray(curve.engineering_strain, dtype=np.float64)
            observed = np.asarray(curve.nominal_stress_pa, dtype=np.float64)
            normalized = (
                ogden_nominal_stress_pa(curve.member.test_mode, strain, mu_pa, alpha)
                - observed
            ) / curve.normalization_stress_pa
            values.append(
                normalized * math.sqrt(calibration_weights[curve.member.ordinal])
            )
        return np.concatenate(values)

    candidates: list[OgdenCalibrationCandidate] = []
    mode_names = {
        OgdenTestMode.UNIAXIAL_TENSION: "uniaxial",
        OgdenTestMode.PLANAR_TENSION: "planar",
        OgdenTestMode.BIAXIAL_TENSION: "biaxial",
    }
    for ordinal, start in enumerate(starts):
        result = least_squares(
            objective,
            start,
            bounds=(lower, upper),
            method="trf",
            x_scale="jac",
            max_nfev=maximum_function_evaluations,
            ftol=1e-10,
            xtol=1e-10,
            gtol=1e-10,
        )
        physical = cast(NDArray[np.float64], result.x * scales)
        mu_pa, alpha = float(physical[0]), float(physical[1])
        objective_terms = {"uniaxial": 0.0, "planar": 0.0, "biaxial": 0.0}
        diagnostics: list[OgdenDiagnosticPoint] = []
        calibration_residuals: list[float] = []
        calibration_normalized: list[float] = []
        holdout_residuals: list[float] = []
        holdout_normalized: list[float] = []
        for curve in curves:
            strain = np.asarray(curve.engineering_strain, dtype=np.float64)
            observed = np.asarray(curve.nominal_stress_pa, dtype=np.float64)
            predicted = ogden_nominal_stress_pa(
                curve.member.test_mode, strain, mu_pa, alpha
            )
            residual = predicted - observed
            normalized = residual / curve.normalization_stress_pa
            weights = (
                calibration_weights
                if curve.member.role is OgdenCalibrationRole.CALIBRATION
                else holdout_weights
            )
            effective = weights[curve.member.ordinal]
            if curve.member.role is OgdenCalibrationRole.CALIBRATION:
                calibration_residuals.extend(float(value) for value in residual)
                calibration_normalized.extend(float(value) for value in normalized)
                objective_terms[mode_names[curve.member.test_mode]] += float(
                    np.sum(normalized**2) * effective
                )
            else:
                holdout_residuals.extend(float(value) for value in residual)
                holdout_normalized.extend(float(value) for value in normalized)
            diagnostics.extend(
                OgdenDiagnosticPoint(
                    member_ordinal=curve.member.ordinal,
                    role=curve.member.role,
                    test_mode=curve.member.test_mode,
                    dataset_id=curve.member.dataset_id,
                    dataset_revision_id=curve.member.dataset_revision_id,
                    point_ordinal=point_ordinal,
                    engineering_strain=float(strain_value),
                    stretch=1.0 + float(strain_value),
                    observed_nominal_stress_pa=float(observed_value),
                    predicted_nominal_stress_pa=float(predicted_value),
                    residual_pa=float(residual_value),
                    normalized_residual=float(normalized_value),
                    effective_weight=effective,
                )
                for point_ordinal, (
                    strain_value,
                    observed_value,
                    predicted_value,
                    residual_value,
                    normalized_value,
                ) in enumerate(
                    zip(strain, observed, predicted, residual, normalized, strict=True)
                )
            )
        jacobian = cast(NDArray[np.float64], result.jac)
        rank = int(np.linalg.matrix_rank(jacobian))
        condition: float | None
        try:
            condition = float(np.linalg.cond(jacobian))
            if not math.isfinite(condition):
                condition = None
        except np.linalg.LinAlgError:
            condition = None
        uncertainty_status, standard = _uncertainty(
            jacobian,
            cast(NDArray[np.float64], result.fun),
            scales,
        )
        mu_standard = standard[0] if standard is not None else None
        alpha_standard = standard[1] if standard is not None else None
        at_bound = _at_bound(mu_pa, parameters.mu_lower_pa, parameters.mu_upper_pa) or _at_bound(
            alpha, parameters.alpha_lower, parameters.alpha_upper
        )
        warnings: list[str] = []
        if len({curve.member.test_mode for curve in calibration}) < 2:
            warnings.append("insufficient_test_modes")
        if not holdout:
            warnings.append("no_holdout_data")
        if at_bound:
            warnings.append("parameter_at_bound")
        if rank < 2:
            warnings.append("rank_deficient")
        if not uncertainty_status.startswith("estimated"):
            warnings.append(uncertainty_status)
        if not result.success:
            warnings.append("optimizer_nonconverged")
        status = "converged" if result.success else "nonconverged"
        canonical = {
            "attempt_ordinal": ordinal,
            "mu_pa": mu_pa,
            "alpha": alpha,
            "objective_total": sum(objective_terms.values()),
            "status": status,
            "warnings": warnings,
        }
        candidates.append(
            OgdenCalibrationCandidate(
                attempt_ordinal=ordinal,
                initial_mu_pa=float(start[0] * scales[0]),
                initial_alpha=float(start[1] * scales[1]),
                mu_pa=mu_pa,
                alpha=alpha,
                objective_total=sum(objective_terms.values()),
                uniaxial_objective=objective_terms["uniaxial"],
                planar_objective=objective_terms["planar"],
                biaxial_objective=objective_terms["biaxial"],
                calibration_rmse_pa=float(
                    np.sqrt(np.mean(np.square(calibration_residuals)))
                ),
                calibration_normalized_rmse=float(
                    np.sqrt(np.mean(np.square(calibration_normalized)))
                ),
                holdout_rmse_pa=(
                    float(np.sqrt(np.mean(np.square(holdout_residuals))))
                    if holdout_residuals
                    else None
                ),
                holdout_normalized_rmse=(
                    float(np.sqrt(np.mean(np.square(holdout_normalized))))
                    if holdout_normalized
                    else None
                ),
                status=status,
                convergence_status_code=int(result.status),
                convergence_reason=str(result.message)[:255],
                function_evaluations=int(result.nfev),
                jacobian_evaluations=(int(result.njev) if result.njev is not None else None),
                optimality=float(result.optimality),
                parameter_at_bound=at_bound,
                jacobian_rank=rank,
                jacobian_condition_number=condition,
                identifiability_status="full_rank" if rank == 2 else "rank_deficient",
                uncertainty_status=uncertainty_status,
                mu_standard_error_pa=mu_standard,
                alpha_standard_error=alpha_standard,
                mu_confidence_lower_pa=(
                    mu_pa - 1.96 * mu_standard if mu_standard is not None else None
                ),
                mu_confidence_upper_pa=(
                    mu_pa + 1.96 * mu_standard if mu_standard is not None else None
                ),
                alpha_confidence_lower=(
                    alpha - 1.96 * alpha_standard if alpha_standard is not None else None
                ),
                alpha_confidence_upper=(
                    alpha + 1.96 * alpha_standard if alpha_standard is not None else None
                ),
                warnings=tuple(warnings),
                candidate_sha256=content_sha256(canonical),
                diagnostics=tuple(diagnostics),
            )
        )
    return tuple(candidates)


def ogden_diagnostics_parquet_bytes(candidate: OgdenCalibrationCandidate) -> bytes:
    table = pa.table(
        {
            "member_ordinal": pa.array(
                [item.member_ordinal for item in candidate.diagnostics], type=pa.int16()
            ),
            "role": pa.array([item.role.value for item in candidate.diagnostics], type=pa.string()),
            "test_mode": pa.array(
                [item.test_mode.value for item in candidate.diagnostics], type=pa.string()
            ),
            "dataset_id": pa.array(
                [str(item.dataset_id) for item in candidate.diagnostics], type=pa.string()
            ),
            "dataset_revision_id": pa.array(
                [str(item.dataset_revision_id) for item in candidate.diagnostics],
                type=pa.string(),
            ),
            "point_ordinal": pa.array(
                [item.point_ordinal for item in candidate.diagnostics], type=pa.int32()
            ),
            "engineering_strain": pa.array(
                [item.engineering_strain for item in candidate.diagnostics], type=pa.float64()
            ),
            "stretch": pa.array(
                [item.stretch for item in candidate.diagnostics], type=pa.float64()
            ),
            "observed_nominal_stress_pa": pa.array(
                [item.observed_nominal_stress_pa for item in candidate.diagnostics],
                type=pa.float64(),
            ),
            "predicted_nominal_stress_pa": pa.array(
                [item.predicted_nominal_stress_pa for item in candidate.diagnostics],
                type=pa.float64(),
            ),
            "residual_pa": pa.array(
                [item.residual_pa for item in candidate.diagnostics], type=pa.float64()
            ),
            "normalized_residual": pa.array(
                [item.normalized_residual for item in candidate.diagnostics], type=pa.float64()
            ),
            "effective_weight": pa.array(
                [item.effective_weight for item in candidate.diagnostics], type=pa.float64()
            ),
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


def ogden_diagnostics_from_parquet(value: bytes) -> tuple[OgdenDiagnosticPoint, ...]:
    try:
        table = cast(Any, pq.read_table)(pa.BufferReader(value))
    except Exception as error:
        raise InvalidOgdenCalibration("Ogden diagnostics are not valid Parquet") from error
    expected = (
        "member_ordinal",
        "role",
        "test_mode",
        "dataset_id",
        "dataset_revision_id",
        "point_ordinal",
        "engineering_strain",
        "stretch",
        "observed_nominal_stress_pa",
        "predicted_nominal_stress_pa",
        "residual_pa",
        "normalized_residual",
        "effective_weight",
    )
    if tuple(table.column_names) != expected:
        raise InvalidOgdenCalibration("Ogden diagnostics schema is invalid")
    return tuple(
        OgdenDiagnosticPoint(
            member_ordinal=int(row["member_ordinal"]),
            role=OgdenCalibrationRole(str(row["role"])),
            test_mode=OgdenTestMode(str(row["test_mode"])),
            dataset_id=UUID(str(row["dataset_id"])),
            dataset_revision_id=UUID(str(row["dataset_revision_id"])),
            point_ordinal=int(row["point_ordinal"]),
            engineering_strain=float(row["engineering_strain"]),
            stretch=float(row["stretch"]),
            observed_nominal_stress_pa=float(row["observed_nominal_stress_pa"]),
            predicted_nominal_stress_pa=float(row["predicted_nominal_stress_pa"]),
            residual_pa=float(row["residual_pa"]),
            normalized_residual=float(row["normalized_residual"]),
            effective_weight=float(row["effective_weight"]),
        )
        for row in table.to_pylist()
    )
