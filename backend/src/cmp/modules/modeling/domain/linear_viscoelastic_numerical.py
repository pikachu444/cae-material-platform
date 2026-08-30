"""Physical response equations and bounded numerical calibration for linear viscoelasticity."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

import numpy as np
from numpy.typing import NDArray

# scipy currently ships no stubs in the pinned runtime; ndarray boundaries below remain
# explicitly typed so this third-party gap cannot leak into the domain contract.
from scipy.optimize import least_squares  # type: ignore[import-untyped]

from cmp.modules.modeling.domain.linear_viscoelastic_contracts import (
    FLOAT64_EPSILON,
    LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
    DataAvailability,
    LinearViscoelasticInputError,
    PointPartition,
    RankStatus,
    RunStatus,
    _as_float,
    _uuid,
)
from cmp.modules.modeling.domain.linear_viscoelastic_input import (
    CanonicalViscoelasticInput,
    DmaObservation,
    RelaxationObservation,
)
from cmp.modules.modeling.domain.linear_viscoelastic_policy import (
    LinearViscoelasticCalibrationPlan,
)
from cmp.modules.modeling.domain.linear_viscoelastic_results import (
    CalibrationCandidate,
    CalibrationRecommendation,
    CalibrationRunResult,
    NumericalAttempt,
    ObjectiveEvaluation,
    RankDiagnostic,
)


def _normalise_points(value: CanonicalViscoelasticInput) -> None:
    calibration_counts = {
        PointPartition.CALIBRATION: 0,
        PointPartition.HOLDOUT: 0,
        PointPartition.EXCLUDED: 0,
    }
    points: Sequence[RelaxationObservation | DmaObservation] = value.relaxation or value.dma
    for point in points:
        calibration_counts[point.partition] += 1
        if point.partition is PointPartition.EXCLUDED and not point.exclusion_reason:
            raise LinearViscoelasticInputError(
                "excluded rows require a reason", code="INPUT_EXCLUSION_REASON_REQUIRED"
            )
    if value.relaxation and calibration_counts[PointPartition.CALIBRATION] < 3:
        raise LinearViscoelasticInputError(
            "at least three relaxation calibration points are required",
            code="INPUT_CALIBRATION_POINTS_REQUIRED",
        )
    if value.dma:
        if sum(point.partition is PointPartition.CALIBRATION for point in value.dma) < 3:
            raise LinearViscoelasticInputError(
                "at least three DMA calibration points per active channel are required",
                code="INPUT_CALIBRATION_POINTS_REQUIRED",
            )
        if value.availability.sweep is DataAvailability.NOT_PROVIDED:
            # The source is already a derived modulus.  This is observable evidence, not a
            # guessed pass/fail threshold.
            pass


def _input_warnings(value: CanonicalViscoelasticInput) -> tuple[str, ...]:
    """Return observable metadata warnings without guessing a missing preprocessing step."""

    statuses = value.availability
    missing = tuple(
        name
        for name in ("ramp", "sweep", "preconditioning", "linear_range")
        if getattr(statuses, name) is DataAvailability.NOT_PROVIDED
    )
    # A derived modulus source may legitimately omit upstream process metadata.  It is a
    # warning on the numerical evidence, never a threshold or an inferred status.
    return ("INPUT_PROCESS_METADATA_NOT_PROVIDED",) if missing else ()


def _parameter_arrays(
    plan: LinearViscoelasticCalibrationPlan, term_count: int
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    bounds = plan.parameter_bounds[term_count]
    lower = np.asarray([math.log(float(value.lower)) for value in bounds], dtype=np.float64)
    start = np.asarray([math.log(float(value.start)) for value in bounds], dtype=np.float64)
    upper = np.asarray([math.log(float(value.upper)) for value in bounds], dtype=np.float64)
    return lower, start, upper


def _physical_model(
    term_count: int,
    parameters: NDArray[np.float64],
    domain: NDArray[np.float64],
    mode: str,
) -> NDArray[np.float64]:
    g_inf = parameters[0]
    gi = parameters[1 : term_count + 1]
    taus = parameters[term_count + 1 :]
    if mode == "relaxation":
        return cast(
            NDArray[np.float64],
            g_inf + np.sum(gi[:, None] * np.exp(-domain[None, :] / taus[:, None]), axis=0),
        )
    omega = 2.0 * math.pi * domain
    x = omega[None, :] * taus[:, None]
    return cast(NDArray[np.float64], g_inf + np.sum(gi[:, None] * (x * x) / (1.0 + x * x), axis=0))


def evaluate_relaxation_modulus(
    term_count: int, parameters: Sequence[float], times_s: Sequence[float]
) -> np.ndarray:
    """Evaluate ``G_inf + Σ Gi exp(-t/tau_i)`` with physical parameters."""

    vector = np.asarray(parameters, dtype=np.float64)
    domain = np.asarray(times_s, dtype=np.float64)
    if vector.size != 1 + 2 * term_count:
        raise ValueError("parameter vector length does not match term_count")
    return _physical_model(term_count, vector, domain, "relaxation")


def evaluate_dma_storage_modulus(
    term_count: int, parameters: Sequence[float], frequencies_hz: Sequence[float]
) -> np.ndarray:
    vector = np.asarray(parameters, dtype=np.float64)
    domain = np.asarray(frequencies_hz, dtype=np.float64)
    if vector.size != 1 + 2 * term_count:
        raise ValueError("parameter vector length does not match term_count")
    return _physical_model(term_count, vector, domain, "dma")


def evaluate_dma_loss_modulus(
    term_count: int, parameters: Sequence[float], frequencies_hz: Sequence[float]
) -> np.ndarray:
    vector = np.asarray(parameters, dtype=np.float64)
    domain = np.asarray(frequencies_hz, dtype=np.float64)
    if vector.size != 1 + 2 * term_count:
        raise ValueError("parameter vector length does not match term_count")
    gi = vector[1 : term_count + 1]
    taus = vector[term_count + 1 :]
    x = (2.0 * math.pi * domain)[None, :] * taus[:, None]
    return np.sum(gi[:, None] * x / (1.0 + x * x), axis=0)


def evaluate_dma_moduli(
    term_count: int, parameters: Sequence[float], frequencies_hz: Sequence[float]
) -> tuple[np.ndarray, np.ndarray]:
    return (
        evaluate_dma_storage_modulus(term_count, parameters, frequencies_hz),
        evaluate_dma_loss_modulus(term_count, parameters, frequencies_hz),
    )


def _residual_builder(
    plan: LinearViscoelasticCalibrationPlan,
    value: CanonicalViscoelasticInput,
    term_count: int,
) -> tuple[Any, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return residual closure, calibration domains/observations, holdout domains/observations."""

    calibration = PointPartition.CALIBRATION
    if value.relaxation:
        cal = tuple(point for point in value.relaxation if point.partition is calibration)
        hold = tuple(
            point for point in value.relaxation if point.partition is PointPartition.HOLDOUT
        )
        domain = np.asarray([_as_float(point.time_s, "time_s") for point in cal], dtype=np.float64)
        observed = np.asarray(
            [_as_float(point.modulus_pa, "modulus_pa") for point in cal], dtype=np.float64
        )
        hold_domain = np.asarray(
            [_as_float(point.time_s, "time_s") for point in hold], dtype=np.float64
        )
        hold_observed = np.asarray(
            [_as_float(point.modulus_pa, "modulus_pa") for point in hold], dtype=np.float64
        )
        weight = math.sqrt(1.0 * 1.0 * (1.0 / len(cal)))
        scale = float(plan.weights.relaxation_scale_pa)

        def residual(parameters: np.ndarray) -> np.ndarray:
            prediction = evaluate_relaxation_modulus(
                term_count,
                cast(Sequence[float], parameters),
                cast(Sequence[float], domain),
            )
            return weight * (prediction - observed) / scale

        return residual, domain, observed, hold_domain, hold_observed

    cal_dma = tuple(point for point in value.dma if point.partition is calibration)
    hold_dma = tuple(point for point in value.dma if point.partition is PointPartition.HOLDOUT)
    domain = np.asarray(
        [_as_float(point.frequency_hz, "frequency_hz") for point in cal_dma], dtype=np.float64
    )
    storage = np.asarray(
        [_as_float(point.storage_modulus_pa, "storage_modulus_pa") for point in cal_dma],
        dtype=np.float64,
    )
    loss = np.asarray(
        [_as_float(point.loss_modulus_pa, "loss_modulus_pa") for point in cal_dma], dtype=np.float64
    )
    hold_domain = np.asarray(
        [_as_float(point.frequency_hz, "frequency_hz") for point in hold_dma], dtype=np.float64
    )
    hold_storage = np.asarray(
        [_as_float(point.storage_modulus_pa, "storage_modulus_pa") for point in hold_dma],
        dtype=np.float64,
    )
    hold_loss = np.asarray(
        [_as_float(point.loss_modulus_pa, "loss_modulus_pa") for point in hold_dma],
        dtype=np.float64,
    )
    storage_weight = math.sqrt(float(plan.weights.dma_storage_weight) / len(cal_dma))
    loss_weight = math.sqrt(float(plan.weights.dma_loss_weight) / len(cal_dma))
    storage_scale = float(plan.weights.dma_storage_scale_pa)
    loss_scale = float(plan.weights.dma_loss_scale_pa)

    def dma_residual(parameters: np.ndarray) -> np.ndarray:
        prediction_storage, prediction_loss = evaluate_dma_moduli(
            term_count,
            cast(Sequence[float], parameters),
            cast(Sequence[float], domain),
        )
        return np.concatenate(
            (
                storage_weight * (prediction_storage - storage) / storage_scale,
                loss_weight * (prediction_loss - loss) / loss_scale,
            )
        )

    # The two arrays are packed as [storage, loss] for the holdout metric; the caller knows
    # the channel order from the input mode.
    return (
        dma_residual,
        domain,
        np.concatenate((storage, loss)),
        hold_domain,
        np.concatenate((hold_storage, hold_loss)),
    )


def _holdout_residuals(
    value: CanonicalViscoelasticInput,
    term_count: int,
    parameters: np.ndarray,
    plan: LinearViscoelasticCalibrationPlan,
) -> tuple[float, ...]:
    if value.relaxation:
        points = tuple(
            point for point in value.relaxation if point.partition is PointPartition.HOLDOUT
        )
        if not points:
            return ()
        domain = np.asarray(
            [_as_float(point.time_s, "time_s") for point in points], dtype=np.float64
        )
        observed = np.asarray(
            [_as_float(point.modulus_pa, "modulus_pa") for point in points], dtype=np.float64
        )
        return tuple(
            (
                (
                    evaluate_relaxation_modulus(
                        term_count,
                        cast(Sequence[float], parameters),
                        cast(Sequence[float], domain),
                    )
                    - observed
                )
                / float(plan.weights.relaxation_scale_pa)
            ).tolist()
        )
    dma_points = tuple(point for point in value.dma if point.partition is PointPartition.HOLDOUT)
    if not dma_points:
        return ()
    domain = np.asarray(
        [_as_float(point.frequency_hz, "frequency_hz") for point in dma_points], dtype=np.float64
    )
    observed_storage = np.asarray(
        [_as_float(point.storage_modulus_pa, "storage_modulus_pa") for point in dma_points],
        dtype=np.float64,
    )
    observed_loss = np.asarray(
        [_as_float(point.loss_modulus_pa, "loss_modulus_pa") for point in dma_points],
        dtype=np.float64,
    )
    predicted_storage, predicted_loss = evaluate_dma_moduli(
        term_count,
        cast(Sequence[float], parameters),
        cast(Sequence[float], domain),
    )
    return tuple(
        np.concatenate(
            (
                (predicted_storage - observed_storage) / float(plan.weights.dma_storage_scale_pa),
                (predicted_loss - observed_loss) / float(plan.weights.dma_loss_scale_pa),
            )
        ).tolist()
    )


def rank_diagnostic(jacobian: np.ndarray, parameter_count: int | None = None) -> RankDiagnostic:
    """Compute deterministic SVD/rank evidence from the terminal scaled Jacobian."""

    jacobian = np.asarray(jacobian, dtype=np.float64)
    if jacobian.ndim != 2:
        raise ValueError("terminal Jacobian must be a matrix")
    m, p = jacobian.shape
    parameter_count = p if parameter_count is None else parameter_count
    column_norms = np.linalg.norm(jacobian, axis=0)
    scale = np.where(column_norms > 0, column_norms, 1.0)
    scaled = jacobian / scale
    singular = np.linalg.svd(scaled, compute_uv=False)
    sigma_max = float(singular[0]) if singular.size else 0.0
    threshold = float(max(m, parameter_count) * FLOAT64_EPSILON * sigma_max)
    rank = int(np.count_nonzero(singular > threshold)) if sigma_max > 0 else 0
    status = RankStatus.FULL_RANK if rank >= parameter_count else RankStatus.RANK_DEFICIENT
    return RankDiagnostic(
        singular_values=tuple(float(value) for value in singular),
        sigma_max=sigma_max,
        threshold=threshold,
        rank=rank,
        status=status,
        warning_code="RANK_DEFICIENT" if status is RankStatus.RANK_DEFICIENT else None,
    )


def calculate_bic(*, rss: float, m: int, parameter_count: int) -> float:
    """Calculate the declared unregularized BIC rule for one candidate."""

    if m < 1 or parameter_count < 1 or not math.isfinite(rss) or rss < 0:
        raise ValueError("BIC requires finite non-negative RSS and positive m/p")
    return float(
        m * math.log(max(rss / m, np.finfo(np.float64).tiny)) + parameter_count * math.log(m)
    )


def recommend_candidate(
    candidates: Sequence[CalibrationCandidate],
    *,
    recommendation_policy: str,
) -> CalibrationRecommendation | None:
    if recommendation_policy != LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY:
        raise ValueError("unsupported linear-viscoelastic recommendation policy")
    if not candidates:
        return None
    ordered = sorted(
        candidates,
        key=lambda candidate: (candidate.bic, candidate.term_count, candidate.attempt_ordinal),
    )
    selected = ordered[0]
    return CalibrationRecommendation(uuid4(), selected.candidate_id, selected.digest)


def calibrate_linear_viscoelastic(
    plan: LinearViscoelasticCalibrationPlan,
    value: CanonicalViscoelasticInput,
    *,
    run_id: UUID | None = None,
    candidate_id_factory: Any = uuid4,
    now: datetime | None = None,
) -> CalibrationRunResult:
    """Execute all explicit starts in a plan using deterministic bounded least-squares."""

    _normalise_points(value)
    input_warnings = _input_warnings(value)
    if (
        value.canonical_test_data is not None
        and plan.test_data is not None
        and value.canonical_test_data != plan.test_data
    ):
        raise LinearViscoelasticInputError(
            "Plan/test-data exact revision mismatch", code="INPUT_REVISION_MISMATCH"
        )
    if (
        value.import_profile is not None
        and plan.import_profile is not None
        and value.import_profile != plan.import_profile
    ):
        raise LinearViscoelasticInputError(
            "Plan/import-profile exact revision mismatch", code="INPUT_PROFILE_REVISION_MISMATCH"
        )
    run_id = run_id or uuid4()
    _uuid(run_id, "run_id")
    attempts: list[NumericalAttempt] = []
    candidates: list[CalibrationCandidate] = []
    attempt_ordinal = 0
    for term_count in plan.term_counts:
        lower, _, upper = _parameter_arrays(plan, term_count)
        for start_vector in plan.start_vectors[term_count]:
            attempt_ordinal += 1
            physical_start = np.asarray(
                [_as_float(item, "start_vector") for item in start_vector], dtype=np.float64
            )
            transformed_start = np.log(physical_start)
            history: list[ObjectiveEvaluation] = []

            def residual(
                transformed: np.ndarray,
                _term_count: int = term_count,
                _history: list[ObjectiveEvaluation] = history,
            ) -> np.ndarray:
                physical = np.exp(np.asarray(transformed, dtype=np.float64))
                current = _residual_builder(plan, value, _term_count)[0](physical)
                _history.append(
                    ObjectiveEvaluation(
                        ordinal=len(_history),
                        transformed_parameters=tuple(float(item) for item in transformed),
                        physical_parameters=tuple(float(item) for item in physical),
                        residuals=tuple(float(item) for item in current),
                        objective=float(np.dot(current, current)),
                    )
                )
                return cast(NDArray[np.float64], current)

            try:
                result = least_squares(
                    residual,
                    transformed_start,
                    bounds=(lower, upper),
                    method="trf",
                    x_scale="jac",
                    ftol=plan.ftol,
                    xtol=plan.xtol,
                    gtol=plan.gtol,
                    max_nfev=plan.max_nfev,
                )
                transformed_final = np.asarray(result.x, dtype=np.float64)
                physical_final = np.exp(transformed_final)
                terminal_residuals = np.asarray(result.fun, dtype=np.float64)
                rss = float(np.dot(terminal_residuals, terminal_residuals))
                rank = rank_diagnostic(
                    np.asarray(result.jac, dtype=np.float64), physical_final.size
                )
                physical_ok = bool(np.all(np.isfinite(physical_final))) and bool(
                    np.all(physical_final > 0)
                )
                converged = bool(
                    result.success and result.status > 0 and np.all(np.isfinite(terminal_residuals))
                )
                warnings = input_warnings + ((rank.warning_code,) if rank.warning_code else ())
                attempt = NumericalAttempt(
                    ordinal=attempt_ordinal,
                    term_count=term_count,
                    start_vector=tuple(float(item) for item in physical_start),
                    transformed_start_vector=tuple(float(item) for item in transformed_start),
                    status=int(result.status),
                    message=str(result.message),
                    nfev=int(result.nfev),
                    cost=float(result.cost),
                    optimality=float(result.optimality),
                    active_mask=tuple(int(item) for item in result.active_mask),
                    physical_parameters=tuple(float(item) for item in physical_final),
                    transformed_parameters=tuple(float(item) for item in transformed_final),
                    residuals=tuple(float(item) for item in terminal_residuals),
                    rss=rss,
                    rank=rank,
                    warnings=warnings,
                    objective_history=tuple(history),
                    converged=converged,
                    physical=physical_ok,
                )
            except (ValueError, FloatingPointError) as error:
                attempt = NumericalAttempt(
                    ordinal=attempt_ordinal,
                    term_count=term_count,
                    start_vector=tuple(float(item) for item in physical_start),
                    transformed_start_vector=tuple(float(item) for item in transformed_start),
                    status=0,
                    message=str(error),
                    nfev=0,
                    cost=0.0,
                    optimality=0.0,
                    active_mask=tuple(0 for _ in physical_start),
                    physical_parameters=tuple(float(item) for item in physical_start),
                    transformed_parameters=tuple(float(item) for item in transformed_start),
                    residuals=(),
                    rss=0.0,
                    rank=RankDiagnostic(
                        (), 0.0, 0.0, 0, RankStatus.RANK_DEFICIENT, "RANK_DEFICIENT"
                    ),
                    warnings=("EXECUTION_REQUEST_INVALID",),
                    objective_history=tuple(history),
                    converged=False,
                    physical=False,
                )
            attempts.append(attempt)
            if attempt.candidate_eligible:
                residual, _, _, _, _ = _residual_builder(plan, value, term_count)
                calibration_residuals = tuple(
                    float(item) for item in residual(np.asarray(attempt.physical_parameters))
                )
                holdout_residuals = _holdout_residuals(
                    value, term_count, np.asarray(attempt.physical_parameters), plan
                )
                m = len(calibration_residuals)
                bic = calculate_bic(rss=attempt.rss, m=m, parameter_count=1 + 2 * term_count)
                candidates.append(
                    CalibrationCandidate(
                        candidate_id=candidate_id_factory(),
                        attempt_ordinal=attempt.ordinal,
                        term_count=term_count,
                        physical_parameters=attempt.physical_parameters,
                        transformed_parameters=attempt.transformed_parameters,
                        rss=attempt.rss,
                        bic=bic,
                        calibration_residuals=calibration_residuals,
                        holdout_residuals=holdout_residuals,
                        rank=attempt.rank,
                        warnings=attempt.warnings,
                    )
                )
    recommendation = recommend_candidate(
        candidates, recommendation_policy=plan.recommendation_policy
    )
    status = RunStatus.SUCCEEDED if candidates else RunStatus.FAILED
    return CalibrationRunResult(
        run_id=run_id,
        plan_revision_id=plan.plan_revision_id,
        status=status,
        attempts=tuple(attempts),
        candidates=tuple(candidates),
        recommendation=recommendation,
        failure_code=None if candidates else "CALCULATION_FAILED",
        failure_detail=None
        if candidates
        else "No explicit numerical attempt converged with physical parameters.",
        recovery_hint=None
        if candidates
        else "Create a new immutable Plan with reviewed bounds or starts.",
    )
