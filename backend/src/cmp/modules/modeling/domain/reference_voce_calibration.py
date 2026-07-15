"""Bounded non-production multi-curve Voce calibration kernel.

This module is intentionally solver neutral.  It separates the reference uniaxial test-mode
adapter, constitutive evaluator, objective engine, and SciPy optimizer adapter so none of those
roles becomes an implicit solver or file-format contract.  The implementation is a transparent
reference capability for monotonic tensile fixtures, not a production-qualified material model.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any, Protocol, cast
from uuid import UUID

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray
from scipy.optimize import least_squares  # type: ignore[import-untyped]

from cmp.modules.datasets.domain.reference_tensile import CurvePoint
from cmp.shared.domain.revisions import content_sha256

REFERENCE_VOCE_PLAN_KIND = "reference_multi_curve_voce_saturation"
REFERENCE_VOCE_PLAN_SCHEMA_ID = "urn:cmp:modeling:reference-voce-calibration-plan:1.0.0"
REFERENCE_VOCE_PLAN_SCHEMA_VERSION = "1.0.0"
REFERENCE_VOCE_MODEL_FAMILY_ID = "urn:cmp:reference:voce-saturation-hardening:1.0.0"
REFERENCE_VOCE_MODEL_SCHEMA_VERSION = "1.0.0"
REFERENCE_VOCE_TEST_MODE_ADAPTER_ID = "urn:cmp:reference:uniaxial-engineering-to-true-plastic:1.0.0"
REFERENCE_VOCE_EVALUATOR_ID = "urn:cmp:reference:voce-closed-form-curve-evaluator:1.0.0"
REFERENCE_VOCE_OBJECTIVE_ID = "urn:cmp:reference:equal-specimen-normalized-wls:1.0.0"
REFERENCE_SCIPY_OPTIMIZER_ID = "urn:cmp:reference:scipy-least-squares:1.0.0"
REFERENCE_VOCE_EVALUATION_MODE = "closed_form_curve"
REFERENCE_VOCE_DIAGNOSTICS_SCHEMA = (
    "urn:cmp:modeling:reference-voce-calibration-diagnostics-parquet:1.0.0"
)

REFERENCE_VOCE_ENVIRONMENT_DIGEST = content_sha256(
    {
        "numpy_version": np.__version__,
        "scipy_version": version("scipy"),
        "optimizer": "scipy.optimize.least_squares",
        "optimizer_method": "trf",
        "rng": "numpy.random.PCG64",
        "non_production": True,
    }
)


class VoceCalibrationError(Exception):
    """Base error for the bounded reference Voce capability."""


class InvalidVoceCalibration(VoceCalibrationError, ValueError):
    """A pinned convention or numerical input violates the reference contract."""


def _uuid(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidVoceCalibration(f"{name} must be non-zero")


def _positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise InvalidVoceCalibration(f"{name} must be finite and greater than zero")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidVoceCalibration(f"{name} must be trimmed and contain 1..{maximum} characters")


@dataclass(frozen=True, slots=True)
class VoceParameterPlan:
    name: str
    unit: str
    lower: float
    initial: float
    upper: float
    scale: float
    transform: str = "none"

    def __post_init__(self) -> None:
        _text("parameter name", self.name, 80)
        _text("parameter unit", self.unit, 32)
        _positive(f"{self.name} lower", self.lower)
        _positive(f"{self.name} initial", self.initial)
        _positive(f"{self.name} upper", self.upper)
        _positive(f"{self.name} scale", self.scale)
        if not self.lower < self.upper:
            raise InvalidVoceCalibration(f"{self.name} bounds must be strictly ordered")
        if not self.lower <= self.initial <= self.upper:
            raise InvalidVoceCalibration(f"{self.name} initial value must be within bounds")
        if self.transform != "none":
            raise InvalidVoceCalibration(
                "the reference Voce adapter supports transform='none' only"
            )


@dataclass(frozen=True, slots=True)
class ReferenceVoceCalibrationPlanContent:
    """Immutable numerical plan pinned to a reviewed multi-replicate input scope."""

    plan_label: str
    calibration_input_scope_id: UUID
    calibration_input_scope_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    youngs_modulus_pa: float
    sigma_0: VoceParameterPlan
    q: VoceParameterPlan
    b: VoceParameterPlan
    normalization_stress_scale_pa: float
    multistart_count: int
    random_seed: int
    maximum_function_evaluations: int = 2_000
    ftol: float = 1e-10
    xtol: float = 1e-10
    gtol: float = 1e-10
    plan_kind: str = REFERENCE_VOCE_PLAN_KIND
    model_family_id: str = REFERENCE_VOCE_MODEL_FAMILY_ID
    test_mode_adapter_id: str = REFERENCE_VOCE_TEST_MODE_ADAPTER_ID
    evaluator_id: str = REFERENCE_VOCE_EVALUATOR_ID
    objective_engine_id: str = REFERENCE_VOCE_OBJECTIVE_ID
    optimizer_adapter_id: str = REFERENCE_SCIPY_OPTIMIZER_ID
    evaluation_mode: str = REFERENCE_VOCE_EVALUATION_MODE
    residual_definition: str = "predicted_minus_observed_true_yield_stress"
    specimen_weighting: str = "equal_specimen"
    point_weighting: str = "uniform_within_specimen"
    objective_aggregation: str = "mean_of_specimen_mean_normalized_squared_residual"
    x_domain_policy: str = "observed_pre_necking_positive_true_plastic_strain"
    missing_data_policy: str = "reject"
    optimizer_method: str = "trf"
    rng_algorithm: str = "numpy.random.PCG64"
    non_production: bool = True

    def __post_init__(self) -> None:
        _text("plan_label", self.plan_label, 160)
        for name in (
            "calibration_input_scope_id",
            "calibration_input_scope_revision_id",
            "material_state_id",
            "material_state_revision_id",
            "property_set_id",
            "property_set_revision_id",
        ):
            _uuid(name, getattr(self, name))
        _positive("youngs_modulus_pa", self.youngs_modulus_pa)
        _positive("normalization_stress_scale_pa", self.normalization_stress_scale_pa)
        if self.sigma_0.name != "sigma_0_pa" or self.sigma_0.unit != "Pa":
            raise InvalidVoceCalibration("sigma_0 must use the fixed sigma_0_pa/Pa contract")
        if self.q.name != "q_pa" or self.q.unit != "Pa":
            raise InvalidVoceCalibration("Q must use the fixed q_pa/Pa contract")
        if self.b.name != "b" or self.b.unit != "1":
            raise InvalidVoceCalibration("b must use the fixed b/dimensionless contract")
        if not 1 <= self.multistart_count <= 16:
            raise InvalidVoceCalibration("multistart_count must be between 1 and 16")
        if not 0 <= self.random_seed < 2**63:
            raise InvalidVoceCalibration("random_seed must be a non-negative signed 64-bit integer")
        if not 10 <= self.maximum_function_evaluations <= 1_000_000:
            raise InvalidVoceCalibration(
                "maximum_function_evaluations must be between 10 and 1000000"
            )
        for name in ("ftol", "xtol", "gtol"):
            value = getattr(self, name)
            if not math.isfinite(value) or not 0.0 < value < 1.0:
                raise InvalidVoceCalibration(f"{name} must be finite and within (0, 1)")
        fixed = (
            self.plan_kind == REFERENCE_VOCE_PLAN_KIND
            and self.model_family_id == REFERENCE_VOCE_MODEL_FAMILY_ID
            and self.test_mode_adapter_id == REFERENCE_VOCE_TEST_MODE_ADAPTER_ID
            and self.evaluator_id == REFERENCE_VOCE_EVALUATOR_ID
            and self.objective_engine_id == REFERENCE_VOCE_OBJECTIVE_ID
            and self.optimizer_adapter_id == REFERENCE_SCIPY_OPTIMIZER_ID
            and self.evaluation_mode == REFERENCE_VOCE_EVALUATION_MODE
            and self.residual_definition == "predicted_minus_observed_true_yield_stress"
            and self.specimen_weighting == "equal_specimen"
            and self.point_weighting == "uniform_within_specimen"
            and self.objective_aggregation == "mean_of_specimen_mean_normalized_squared_residual"
            and self.x_domain_policy == "observed_pre_necking_positive_true_plastic_strain"
            and self.missing_data_policy == "reject"
            and self.optimizer_method == "trf"
            and self.rng_algorithm == "numpy.random.PCG64"
            and self.non_production
        )
        if not fixed:
            raise InvalidVoceCalibration(
                "reference Voce plan must retain its fixed non-production contract"
            )


@dataclass(frozen=True, slots=True)
class VoceEngineeringCurveInput:
    member_ordinal: int
    dataset_id: UUID
    dataset_revision_id: UUID
    test_run_id: UUID
    test_run_revision_id: UUID
    points: tuple[CurvePoint, ...]

    def __post_init__(self) -> None:
        if not 0 <= self.member_ordinal < 50:
            raise InvalidVoceCalibration("member_ordinal must be between 0 and 49")
        for name in (
            "dataset_id",
            "dataset_revision_id",
            "test_run_id",
            "test_run_revision_id",
        ):
            _uuid(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class VocePlasticObservation:
    point_ordinal: int
    true_plastic_strain: float
    observed_true_yield_stress_pa: float


@dataclass(frozen=True, slots=True)
class VoceCalibrationCurve:
    member_ordinal: int
    dataset_id: UUID
    dataset_revision_id: UUID
    test_run_id: UUID
    test_run_revision_id: UUID
    observations: tuple[VocePlasticObservation, ...]


class TestModeAdapter(Protocol):
    def adapt(
        self,
        curves: tuple[VoceEngineeringCurveInput, ...],
        *,
        youngs_modulus_pa: float,
    ) -> tuple[VoceCalibrationCurve, ...]: ...


class MaterialModelEvaluator(Protocol):
    def evaluate(
        self, parameters: NDArray[np.float64], plastic_strains: NDArray[np.float64]
    ) -> NDArray[np.float64]: ...


class ObjectiveEngine(Protocol):
    def residual_vector(
        self,
        parameters: NDArray[np.float64],
        curves: tuple[VoceCalibrationCurve, ...],
        evaluator: MaterialModelEvaluator,
        normalization_stress_scale_pa: float,
    ) -> NDArray[np.float64]: ...


class OptimizerAdapter(Protocol):
    def optimize(
        self,
        *,
        plan: ReferenceVoceCalibrationPlanContent,
        curves: tuple[VoceCalibrationCurve, ...],
        evaluator: MaterialModelEvaluator,
        objective: ObjectiveEngine,
        initial_parameters: NDArray[np.float64],
    ) -> VoceOptimizerResult: ...


class ReferenceUniaxialTensionTestModeAdapter:
    """Convert SI engineering observations to pre-necking true plastic observations."""

    def adapt(
        self,
        curves: tuple[VoceEngineeringCurveInput, ...],
        *,
        youngs_modulus_pa: float,
    ) -> tuple[VoceCalibrationCurve, ...]:
        _positive("youngs_modulus_pa", youngs_modulus_pa)
        if not 2 <= len(curves) <= 50:
            raise InvalidVoceCalibration("reference Voce calibration requires 2..50 curves")
        if tuple(item.member_ordinal for item in curves) != tuple(range(len(curves))):
            raise InvalidVoceCalibration("input curve ordinals must be contiguous")
        if len({item.dataset_revision_id for item in curves}) != len(curves):
            raise InvalidVoceCalibration("input Dataset revisions must be distinct")
        if len({item.test_run_revision_id for item in curves}) != len(curves):
            raise InvalidVoceCalibration("input Test Run revisions must be distinct")
        return tuple(self._adapt_curve(curve, youngs_modulus_pa) for curve in curves)

    @staticmethod
    def _adapt_curve(
        curve: VoceEngineeringCurveInput, youngs_modulus_pa: float
    ) -> VoceCalibrationCurve:
        if not 4 <= len(curve.points) <= 5_000:
            raise InvalidVoceCalibration("each input curve requires 4..5000 observations")
        previous_strain = -1.0
        for point in curve.points:
            if (
                not math.isfinite(point.engineering_strain)
                or not math.isfinite(point.engineering_stress)
                or point.engineering_strain < 0.0
                or point.engineering_stress < 0.0
                or point.engineering_strain <= previous_strain
            ):
                raise InvalidVoceCalibration(
                    "engineering tensile points must be finite, non-negative and strictly ordered"
                )
            previous_strain = point.engineering_strain
        peak_stress = max(point.engineering_stress for point in curve.points)
        necking_index = next(
            index
            for index, point in enumerate(curve.points)
            if point.engineering_stress == peak_stress
        )
        if necking_index < 2:
            raise InvalidVoceCalibration("engineering stress maximum occurs before a usable domain")
        observations: list[VocePlasticObservation] = []
        previous_plastic_strain = -1.0
        previous_true_stress = -1.0
        for point_ordinal, point in enumerate(curve.points[: necking_index + 1]):
            true_stress = point.engineering_stress * (1.0 + point.engineering_strain)
            true_plastic_strain = math.log1p(point.engineering_strain) - (
                true_stress / youngs_modulus_pa
            )
            if true_plastic_strain <= 0.0:
                continue
            if true_plastic_strain <= previous_plastic_strain:
                raise InvalidVoceCalibration(
                    "derived plastic strain is not strictly increasing; "
                    "explicit processing is required"
                )
            if true_stress < previous_true_stress:
                raise InvalidVoceCalibration(
                    "derived pre-necking true stress softens; explicit QC is required"
                )
            observations.append(
                VocePlasticObservation(point_ordinal, true_plastic_strain, true_stress)
            )
            previous_plastic_strain = true_plastic_strain
            previous_true_stress = true_stress
        if len(observations) < 3:
            raise InvalidVoceCalibration(
                "each curve requires at least three positive pre-necking plastic observations"
            )
        return VoceCalibrationCurve(
            member_ordinal=curve.member_ordinal,
            dataset_id=curve.dataset_id,
            dataset_revision_id=curve.dataset_revision_id,
            test_run_id=curve.test_run_id,
            test_run_revision_id=curve.test_run_revision_id,
            observations=tuple(observations),
        )


class ReferenceVoceMaterialModelEvaluator:
    """Evaluate sigma_y = sigma_0 + Q * (1 - exp(-b * epsilon_p))."""

    def evaluate(
        self, parameters: NDArray[np.float64], plastic_strains: NDArray[np.float64]
    ) -> NDArray[np.float64]:
        if parameters.shape != (3,) or not np.all(np.isfinite(parameters)):
            raise InvalidVoceCalibration("Voce evaluator requires three finite parameters")
        if plastic_strains.ndim != 1 or not np.all(np.isfinite(plastic_strains)):
            raise InvalidVoceCalibration("Voce evaluator requires finite one-dimensional strains")
        if np.any(plastic_strains < 0.0):
            raise InvalidVoceCalibration("Voce evaluator does not accept negative plastic strain")
        sigma_0, q, b = parameters
        return cast(NDArray[np.float64], sigma_0 + q * (-np.expm1(-b * plastic_strains)))


class EqualSpecimenNormalizedObjectiveEngine:
    """Give every specimen equal total weight, independent of its point count."""

    def residual_vector(
        self,
        parameters: NDArray[np.float64],
        curves: tuple[VoceCalibrationCurve, ...],
        evaluator: MaterialModelEvaluator,
        normalization_stress_scale_pa: float,
    ) -> NDArray[np.float64]:
        _positive("normalization_stress_scale_pa", normalization_stress_scale_pa)
        if len(curves) < 2:
            raise InvalidVoceCalibration("objective requires at least two specimen curves")
        weighted: list[NDArray[np.float64]] = []
        specimen_scale = math.sqrt(len(curves))
        for curve in curves:
            strains = np.asarray(
                [point.true_plastic_strain for point in curve.observations], dtype=np.float64
            )
            observed = np.asarray(
                [point.observed_true_yield_stress_pa for point in curve.observations],
                dtype=np.float64,
            )
            predicted = evaluator.evaluate(parameters, strains)
            point_scale = math.sqrt(len(curve.observations))
            weighted.append(
                (predicted - observed)
                / normalization_stress_scale_pa
                / specimen_scale
                / point_scale
            )
        return np.concatenate(weighted)


@dataclass(frozen=True, slots=True)
class VoceOptimizerResult:
    parameters: tuple[float, float, float]
    converged: bool
    status_code: int
    convergence_reason: str
    function_evaluations: int
    jacobian_evaluations: int | None
    optimality: float
    bound_sticking_parameters: tuple[str, ...]


class ScipyLeastSquaresOptimizerAdapter:
    """Narrow deterministic SciPy ``least_squares`` adapter."""

    def optimize(
        self,
        *,
        plan: ReferenceVoceCalibrationPlanContent,
        curves: tuple[VoceCalibrationCurve, ...],
        evaluator: MaterialModelEvaluator,
        objective: ObjectiveEngine,
        initial_parameters: NDArray[np.float64],
    ) -> VoceOptimizerResult:
        lower = np.asarray([plan.sigma_0.lower, plan.q.lower, plan.b.lower], dtype=np.float64)
        upper = np.asarray([plan.sigma_0.upper, plan.q.upper, plan.b.upper], dtype=np.float64)
        scale = np.asarray([plan.sigma_0.scale, plan.q.scale, plan.b.scale], dtype=np.float64)
        result = least_squares(
            lambda value: objective.residual_vector(
                value, curves, evaluator, plan.normalization_stress_scale_pa
            ),
            initial_parameters,
            bounds=(lower, upper),
            method="trf",
            x_scale=scale,
            ftol=plan.ftol,
            xtol=plan.xtol,
            gtol=plan.gtol,
            max_nfev=plan.maximum_function_evaluations,
        )
        parameters = np.asarray(result.x, dtype=np.float64)
        tolerance = np.maximum(1e-8 * (upper - lower), np.finfo(np.float64).eps)
        sticking = tuple(
            name
            for name, value, low, high, atol in zip(
                ("sigma_0_pa", "q_pa", "b"), parameters, lower, upper, tolerance, strict=True
            )
            if abs(value - low) <= atol or abs(value - high) <= atol
        )
        njev = getattr(result, "njev", None)
        return VoceOptimizerResult(
            parameters=(float(parameters[0]), float(parameters[1]), float(parameters[2])),
            converged=bool(result.success),
            status_code=int(result.status),
            convergence_reason=str(result.message).strip(),
            function_evaluations=int(result.nfev),
            jacobian_evaluations=int(njev) if njev is not None else None,
            optimality=float(result.optimality),
            bound_sticking_parameters=sticking,
        )


@dataclass(frozen=True, slots=True)
class VoceDiagnosticPoint:
    member_ordinal: int
    dataset_revision_id: UUID
    point_ordinal: int
    true_plastic_strain: float
    observed_true_yield_stress_pa: float
    predicted_true_yield_stress_pa: float
    residual_true_yield_stress_pa: float
    normalized_residual: float
    effective_weight: float

    def __post_init__(self) -> None:
        if not 0 <= self.member_ordinal < 50 or self.point_ordinal < 0:
            raise InvalidVoceCalibration("diagnostic ordinals are invalid")
        _uuid("diagnostic dataset_revision_id", self.dataset_revision_id)
        for name in (
            "true_plastic_strain",
            "observed_true_yield_stress_pa",
            "predicted_true_yield_stress_pa",
            "residual_true_yield_stress_pa",
            "normalized_residual",
            "effective_weight",
        ):
            if not math.isfinite(getattr(self, name)):
                raise InvalidVoceCalibration(f"diagnostic {name} must be finite")
        if self.true_plastic_strain < 0 or self.effective_weight <= 0:
            raise InvalidVoceCalibration("diagnostic strain and effective weight are invalid")


@dataclass(frozen=True, slots=True)
class VoceObjectiveTerm:
    member_ordinal: int
    dataset_id: UUID
    dataset_revision_id: UUID
    point_count: int
    mean_normalized_squared_residual: float


@dataclass(frozen=True, slots=True)
class ReferenceVoceCalibrationCandidate:
    attempt_ordinal: int
    initial_parameters: tuple[float, float, float]
    calibrated_parameters: tuple[float, float, float]
    objective_total: float
    objective_terms: tuple[VoceObjectiveTerm, ...]
    diagnostics: tuple[VoceDiagnosticPoint, ...]
    residual_root_mean_square_pa: float
    residual_mean_pa: float
    converged: bool
    status_code: int
    convergence_reason: str
    function_evaluations: int
    jacobian_evaluations: int | None
    optimality: float
    bound_sticking_parameters: tuple[str, ...]
    warnings: tuple[str, ...]
    identifiability_status: str = "not_assessed_reference"
    uncertainty_status: str = "not_provided_reference"


def reference_voce_multistart_parameters(
    plan: ReferenceVoceCalibrationPlanContent,
) -> tuple[tuple[float, float, float], ...]:
    initial = np.asarray([plan.sigma_0.initial, plan.q.initial, plan.b.initial], dtype=np.float64)
    starts = [initial]
    if plan.multistart_count == 1:
        return tuple((float(item[0]), float(item[1]), float(item[2])) for item in starts)
    rng = np.random.Generator(np.random.PCG64(plan.random_seed))
    lower = np.asarray([plan.sigma_0.lower, plan.q.lower, plan.b.lower], dtype=np.float64)
    upper = np.asarray([plan.sigma_0.upper, plan.q.upper, plan.b.upper], dtype=np.float64)
    for _ in range(plan.multistart_count - 1):
        starts.append(lower + rng.random(3, dtype=np.float64) * (upper - lower))
    return tuple((float(item[0]), float(item[1]), float(item[2])) for item in starts)


def calibrate_reference_voce_curves(
    plan: ReferenceVoceCalibrationPlanContent,
    inputs: tuple[VoceEngineeringCurveInput, ...],
    *,
    test_mode_adapter: TestModeAdapter | None = None,
    evaluator: MaterialModelEvaluator | None = None,
    objective_engine: ObjectiveEngine | None = None,
    optimizer_adapter: OptimizerAdapter | None = None,
) -> tuple[ReferenceVoceCalibrationCandidate, ...]:
    """Run every recorded start and retain converged and non-converged candidates."""

    test_mode = test_mode_adapter or ReferenceUniaxialTensionTestModeAdapter()
    model = evaluator or ReferenceVoceMaterialModelEvaluator()
    objective = objective_engine or EqualSpecimenNormalizedObjectiveEngine()
    optimizer = optimizer_adapter or ScipyLeastSquaresOptimizerAdapter()
    curves = test_mode.adapt(inputs, youngs_modulus_pa=plan.youngs_modulus_pa)
    candidates: list[ReferenceVoceCalibrationCandidate] = []
    for attempt_ordinal, start_values in enumerate(
        reference_voce_multistart_parameters(plan), start=1
    ):
        start = np.asarray(start_values, dtype=np.float64)
        result = optimizer.optimize(
            plan=plan,
            curves=curves,
            evaluator=model,
            objective=objective,
            initial_parameters=start,
        )
        parameters = np.asarray(result.parameters, dtype=np.float64)
        diagnostics: list[VoceDiagnosticPoint] = []
        terms: list[VoceObjectiveTerm] = []
        residuals: list[float] = []
        for curve in curves:
            strains = np.asarray(
                [point.true_plastic_strain for point in curve.observations], dtype=np.float64
            )
            predicted = model.evaluate(parameters, strains)
            curve_normalized_squared: list[float] = []
            effective_weight = 1.0 / len(curves) / len(curve.observations)
            for point, prediction in zip(curve.observations, predicted, strict=True):
                residual = float(prediction) - point.observed_true_yield_stress_pa
                normalized = residual / plan.normalization_stress_scale_pa
                residuals.append(residual)
                curve_normalized_squared.append(normalized * normalized)
                diagnostics.append(
                    VoceDiagnosticPoint(
                        member_ordinal=curve.member_ordinal,
                        dataset_revision_id=curve.dataset_revision_id,
                        point_ordinal=point.point_ordinal,
                        true_plastic_strain=point.true_plastic_strain,
                        observed_true_yield_stress_pa=point.observed_true_yield_stress_pa,
                        predicted_true_yield_stress_pa=float(prediction),
                        residual_true_yield_stress_pa=residual,
                        normalized_residual=normalized,
                        effective_weight=effective_weight,
                    )
                )
            terms.append(
                VoceObjectiveTerm(
                    member_ordinal=curve.member_ordinal,
                    dataset_id=curve.dataset_id,
                    dataset_revision_id=curve.dataset_revision_id,
                    point_count=len(curve.observations),
                    mean_normalized_squared_residual=(
                        sum(curve_normalized_squared) / len(curve_normalized_squared)
                    ),
                )
            )
        objective_total = sum(term.mean_normalized_squared_residual for term in terms) / len(terms)
        residual_rms = math.sqrt(sum(value * value for value in residuals) / len(residuals))
        warnings: tuple[str, ...] = (
            ("one_or_more_parameters_at_bound",) if result.bound_sticking_parameters else ()
        )
        if not result.converged:
            warnings += ("optimizer_did_not_converge",)
        candidates.append(
            ReferenceVoceCalibrationCandidate(
                attempt_ordinal=attempt_ordinal,
                initial_parameters=(float(start[0]), float(start[1]), float(start[2])),
                calibrated_parameters=result.parameters,
                objective_total=objective_total,
                objective_terms=tuple(terms),
                diagnostics=tuple(diagnostics),
                residual_root_mean_square_pa=residual_rms,
                residual_mean_pa=sum(residuals) / len(residuals),
                converged=result.converged,
                status_code=result.status_code,
                convergence_reason=result.convergence_reason,
                function_evaluations=result.function_evaluations,
                jacobian_evaluations=result.jacobian_evaluations,
                optimality=result.optimality,
                bound_sticking_parameters=result.bound_sticking_parameters,
                warnings=warnings,
            )
        )
    return tuple(candidates)


def reference_voce_calibration_plan_canonical(
    value: ReferenceVoceCalibrationPlanContent,
) -> dict[str, object]:
    """Canonical typed Plan payload without an ungoverned optimizer JSON blob."""

    def parameter(item: VoceParameterPlan) -> dict[str, object]:
        return {
            "name": item.name,
            "unit": item.unit,
            "lower": item.lower,
            "initial": item.initial,
            "upper": item.upper,
            "scale": item.scale,
            "transform": item.transform,
        }

    return {
        "plan_kind": value.plan_kind,
        "plan_label": value.plan_label,
        "calibration_input_scope_id": str(value.calibration_input_scope_id),
        "calibration_input_scope_revision_id": str(value.calibration_input_scope_revision_id),
        "material_state_id": str(value.material_state_id),
        "material_state_revision_id": str(value.material_state_revision_id),
        "property_set_id": str(value.property_set_id),
        "property_set_revision_id": str(value.property_set_revision_id),
        "youngs_modulus_pa": value.youngs_modulus_pa,
        "model_family_id": value.model_family_id,
        "test_mode_adapter_id": value.test_mode_adapter_id,
        "evaluator_id": value.evaluator_id,
        "evaluation_mode": value.evaluation_mode,
        "parameters": [parameter(value.sigma_0), parameter(value.q), parameter(value.b)],
        "objective": {
            "engine_id": value.objective_engine_id,
            "residual_definition": value.residual_definition,
            "normalization_stress_scale_pa": value.normalization_stress_scale_pa,
            "specimen_weighting": value.specimen_weighting,
            "point_weighting": value.point_weighting,
            "aggregation": value.objective_aggregation,
            "x_domain_policy": value.x_domain_policy,
            "missing_data_policy": value.missing_data_policy,
        },
        "optimizer": {
            "adapter_id": value.optimizer_adapter_id,
            "method": value.optimizer_method,
            "maximum_function_evaluations": value.maximum_function_evaluations,
            "ftol": value.ftol,
            "xtol": value.xtol,
            "gtol": value.gtol,
            "multistart_count": value.multistart_count,
            "random_seed": value.random_seed,
            "rng_algorithm": value.rng_algorithm,
            "environment_digest": REFERENCE_VOCE_ENVIRONMENT_DIGEST,
        },
        "non_production": value.non_production,
    }


def reference_voce_diagnostics_parquet_bytes(
    points: tuple[VoceDiagnosticPoint, ...],
) -> bytes:
    if len(points) < 6:
        raise InvalidVoceCalibration("multi-curve diagnostics require at least six points")
    table = pa.table(
        {
            "member_ordinal": pa.array([point.member_ordinal for point in points], type=pa.int16()),
            "dataset_revision_id": pa.array(
                [str(point.dataset_revision_id) for point in points], type=pa.string()
            ),
            "point_ordinal": pa.array([point.point_ordinal for point in points], type=pa.int32()),
            "true_plastic_strain": pa.array(
                [point.true_plastic_strain for point in points], type=pa.float64()
            ),
            "observed_true_yield_stress_pa": pa.array(
                [point.observed_true_yield_stress_pa for point in points], type=pa.float64()
            ),
            "predicted_true_yield_stress_pa": pa.array(
                [point.predicted_true_yield_stress_pa for point in points], type=pa.float64()
            ),
            "residual_true_yield_stress_pa": pa.array(
                [point.residual_true_yield_stress_pa for point in points], type=pa.float64()
            ),
            "normalized_residual": pa.array(
                [point.normalized_residual for point in points], type=pa.float64()
            ),
            "effective_weight": pa.array(
                [point.effective_weight for point in points], type=pa.float64()
            ),
        }
    ).replace_schema_metadata({b"cmp_schema_ref": REFERENCE_VOCE_DIAGNOSTICS_SCHEMA.encode()})
    sink = io.BytesIO()
    writer = cast(Any, pq.write_table)
    writer(table, sink, compression="zstd", use_dictionary=False)
    return sink.getvalue()


def reference_voce_diagnostics_from_parquet(
    value: bytes,
) -> tuple[VoceDiagnosticPoint, ...]:
    columns = (
        "member_ordinal",
        "dataset_revision_id",
        "point_ordinal",
        "true_plastic_strain",
        "observed_true_yield_stress_pa",
        "predicted_true_yield_stress_pa",
        "residual_true_yield_stress_pa",
        "normalized_residual",
        "effective_weight",
    )
    try:
        reader = cast(Any, pq.read_table)
        table = reader(io.BytesIO(value), columns=list(columns))
    except Exception as error:
        raise InvalidVoceCalibration("Voce diagnostics are not valid typed Parquet") from error
    if tuple(table.column_names) != columns:
        raise InvalidVoceCalibration("Voce diagnostic channels do not match the schema")
    if (table.schema.metadata or {}).get(b"cmp_schema_ref") != (
        REFERENCE_VOCE_DIAGNOSTICS_SCHEMA.encode()
    ):
        raise InvalidVoceCalibration("Voce diagnostic schema reference is invalid")
    values = [table.column(name).to_pylist() for name in columns]
    if len({len(column) for column in values}) != 1 or len(values[0]) < 6:
        raise InvalidVoceCalibration("Voce diagnostic point count is invalid")
    try:
        return tuple(
            VoceDiagnosticPoint(
                member_ordinal=int(row[0]),
                dataset_revision_id=UUID(str(row[1])),
                point_ordinal=int(row[2]),
                true_plastic_strain=float(row[3]),
                observed_true_yield_stress_pa=float(row[4]),
                predicted_true_yield_stress_pa=float(row[5]),
                residual_true_yield_stress_pa=float(row[6]),
                normalized_residual=float(row[7]),
                effective_weight=float(row[8]),
            )
            for row in zip(*values, strict=True)
        )
    except (TypeError, ValueError) as error:
        raise InvalidVoceCalibration("Voce diagnostic values are invalid") from error


def reference_voce_candidate_content_hash(
    *,
    run_id: UUID,
    candidate: ReferenceVoceCalibrationCandidate,
    diagnostics_sha256: str,
) -> str:
    return content_sha256(
        {
            "run_id": str(run_id),
            "attempt_ordinal": candidate.attempt_ordinal,
            "initial_parameters": candidate.initial_parameters,
            "calibrated_parameters": candidate.calibrated_parameters,
            "objective_total": candidate.objective_total,
            "objective_terms": [
                {
                    "member_ordinal": term.member_ordinal,
                    "dataset_id": str(term.dataset_id),
                    "dataset_revision_id": str(term.dataset_revision_id),
                    "point_count": term.point_count,
                    "mean_normalized_squared_residual": (term.mean_normalized_squared_residual),
                }
                for term in candidate.objective_terms
            ],
            "converged": candidate.converged,
            "status_code": candidate.status_code,
            "diagnostics_sha256": diagnostics_sha256,
            "environment_digest": REFERENCE_VOCE_ENVIRONMENT_DIGEST,
        }
    )
