"""Multi-frequency DMA time-temperature-superposition kernel.

The inputs to this module are canonical Test Data values.  The kernel owns the
typed sweep model, overlap scoring, adjacent alignment, shift-law fitting,
holdout evaluation, and application-domain derivation.  It never edits source
points, smooths curves, persists interpolation, deletes outliers, or
extrapolates outside measured frequency ranges.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from typing import cast

import scipy  # type: ignore[import-untyped]
from scipy.optimize import (  # type: ignore[import-untyped]
    least_squares as _scipy_least_squares,
)
from scipy.optimize import (
    minimize_scalar as _scipy_minimize_scalar,
)

from cmp.modules.processing.domain.dma_frequency_master_curve import (
    DMA_SWEEP_TEMPERATURE_TOLERANCE_K,
    DMA_TTS_ADJACENT_OPTIMIZER_ID,
    DMA_TTS_LAW_OPTIMIZER_ID,
    DMA_TTS_SCORER_ID,
    DmaFrequencyMasterCurveBuildResult,
    DmaFrequencyMasterCurveRow,
    DmaFrequencyMasterCurveRowValues,
    DmaInputMode,
    DmaPartition,
    DmaProcessingError,
    _fail,
)
from cmp.modules.processing.domain.temperature_shift import (
    UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K,
    TemperatureShiftError,
    arrhenius_log10_shift,
    validate_manual_shift_table,
    wlf_log10_shift,
)


@dataclass(frozen=True, slots=True)
class _ScalarOptimizationResult:
    x: float
    fun: float
    success: bool
    status: int
    nit: int
    nfev: int


@dataclass(frozen=True, slots=True)
class _LeastSquaresResult:
    x: tuple[float, ...]
    success: bool
    cost: float
    status: int
    nfev: int
    optimality: float


def _run_minimize_scalar(
    objective: Callable[[float], float], bounds: tuple[float, float]
) -> _ScalarOptimizationResult:
    """Adapt the untyped SciPy result to the fields governed by this kernel."""

    raw = _scipy_minimize_scalar(
        objective,
        bounds=bounds,
        method="bounded",
        options={"xatol": 1e-10, "maxiter": 1000},
    )
    return _ScalarOptimizationResult(
        x=float(raw.x),
        fun=float(raw.fun),
        success=bool(raw.success),
        status=int(raw.status),
        nit=int(raw.nit),
        nfev=int(raw.nfev),
    )


def _run_least_squares(
    residual: Callable[[Sequence[float]], list[float]],
    initial_parameters: tuple[float, ...],
    lower_bounds: tuple[float, ...],
    upper_bounds: tuple[float, ...],
) -> _LeastSquaresResult:
    """Adapt the untyped SciPy result to the fields governed by this kernel."""

    raw = _scipy_least_squares(
        residual,
        initial_parameters,
        bounds=(lower_bounds, upper_bounds),
        method="trf",
        ftol=1e-12,
        xtol=1e-12,
        gtol=1e-12,
        max_nfev=5000,
    )
    return _LeastSquaresResult(
        x=tuple(float(item) for item in raw.x),
        success=bool(raw.success),
        cost=float(raw.cost),
        status=int(raw.status),
        nfev=int(raw.nfev),
        optimality=float(raw.optimality),
    )


_SCIPY_VERSION = str(scipy.__version__)


@dataclass(frozen=True, slots=True)
class DmaFrequencySweepPoint:
    """One immutable measured point in a source frequency sweep."""

    source_ordinal: int
    measured_temperature_k: float
    frequency_hz: float
    storage_modulus_pa: float
    loss_modulus_pa: float

    def __post_init__(self) -> None:
        if (
            isinstance(self.source_ordinal, bool)
            or not isinstance(self.source_ordinal, int)
            or not 0 <= self.source_ordinal <= 9_223_372_036_854_775_807
        ):
            raise _fail(
                4311,
                "source point ordinal is invalid",
                "Preserve the canonical zero-based source row ordinal.",
            )
        if any(
            not math.isfinite(value) or value <= 0
            for value in (
                self.measured_temperature_k,
                self.frequency_hz,
                self.storage_modulus_pa,
                self.loss_modulus_pa,
            )
        ):
            raise _fail(
                4312,
                "a multi-frequency DMA point is not finite and positive",
                "Correct the source temperature, frequency, or modulus values.",
            )


# These names are useful to adapters that describe the source as a row or point.
DmaMultiFrequencyPoint = DmaFrequencySweepPoint
DmaFrequencySweepRow = DmaFrequencySweepPoint


@dataclass(frozen=True, slots=True)
class DmaFrequencySweep:
    """A source sweep, retaining the source row order exactly."""

    source_sweep_ordinal: int
    points: tuple[DmaFrequencySweepPoint, ...]

    def __post_init__(self) -> None:
        if (
            isinstance(self.source_sweep_ordinal, bool)
            or not isinstance(self.source_sweep_ordinal, int)
            or not 1 <= self.source_sweep_ordinal <= 9_223_372_036_854_775_807
        ):
            raise _fail(
                4311,
                "source sweep ordinal is outside positive int64",
                "Use the exact positive source sweep identity from Test Data.",
            )
        if not self.points:
            raise _fail(
                4312,
                "source sweep has no measured points",
                "Preserve every measured point for the source sweep.",
            )
        source_ordinals = tuple(point.source_ordinal for point in self.points)
        if source_ordinals != tuple(sorted(source_ordinals)) or len(set(source_ordinals)) != len(
            source_ordinals
        ):
            raise _fail(
                4311,
                "source sweep points are not in canonical source order",
                "Preserve source row order within each explicit source sweep.",
            )
        frequencies = tuple(point.frequency_hz for point in self.points)
        if any(right <= left for left, right in pairwise(frequencies)):
            raise _fail(
                4312,
                "frequency is not strictly increasing within a source sweep",
                "Provide each source isotherm in strictly increasing cyclic-frequency order.",
            )


DmaMultiFrequencySweep = DmaFrequencySweep


@dataclass(frozen=True, slots=True)
class DmaFrequencySweepDisposition:
    """The server-validated partition and representative temperature."""

    source_sweep_ordinal: int
    representative_temperature_k: float
    partition: DmaPartition
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.source_sweep_ordinal, bool)
            or not isinstance(self.source_sweep_ordinal, int)
            or not 1 <= self.source_sweep_ordinal <= 9_223_372_036_854_775_807
        ):
            raise _fail(
                4311,
                "disposition source sweep ordinal is invalid",
                "Map every imported source sweep by its positive identity exactly once.",
            )
        if not math.isfinite(self.representative_temperature_k) or (
            self.representative_temperature_k <= 0
        ):
            raise _fail(
                4316,
                "representative temperature is invalid",
                "Provide one positive finite representative temperature per source sweep.",
            )
        if self.partition is DmaPartition.EXCLUDED:
            if self.exclusion_reason is None or not self.exclusion_reason.strip():
                raise _fail(
                    4316,
                    "excluded sweep has no reason",
                    "Record why the complete source sweep is excluded.",
                )
        elif self.exclusion_reason is not None:
            raise _fail(
                4316,
                "included sweep carries an exclusion reason",
                "Remove exclusion_reason from calibration and holdout sweeps.",
            )


DmaMultiFrequencySweepDisposition = DmaFrequencySweepDisposition
DmaSweepDisposition = DmaFrequencySweepDisposition


@dataclass(frozen=True, slots=True)
class DmaTtsScoringControls:
    minimum_overlap_decades: float
    overlap_evaluation_point_count: int
    storage_weight: float
    loss_weight: float


@dataclass(frozen=True, slots=True)
class DmaTtsAdjacentOptimizerControls:
    lower: float
    upper: float
    xatol: float = 1e-10
    maxiter: int = 1000

    @property
    def relative_shift_lower_bound_log10(self) -> float:
        return self.lower

    @property
    def relative_shift_upper_bound_log10(self) -> float:
        return self.upper


@dataclass(frozen=True, slots=True)
class DmaTtsLawOptimizerControls:
    initial_parameters: tuple[float, ...]
    lower_bounds: tuple[float, ...]
    upper_bounds: tuple[float, ...]
    ftol: float = 1e-12
    xtol: float = 1e-12
    gtol: float = 1e-12
    max_nfev: int = 5000


@dataclass(frozen=True, slots=True)
class DmaShiftLawRequest:
    kind: str
    reference_temperature_k: float
    manual_table: tuple[tuple[float, float], ...] = ()
    initial_parameters: tuple[float, ...] = ()
    lower_bounds: tuple[float, ...] = ()
    upper_bounds: tuple[float, ...] = ()
    gas_constant: float = UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K

    @property
    def gas_constant_j_per_mol_k(self) -> float:
        return self.gas_constant


DmaMultiFrequencyShiftLaw = DmaShiftLawRequest


@dataclass(frozen=True, slots=True)
class DmaMultiFrequencyStartingSuggestion:
    """Read-only, deterministic controls for a multi-frequency DMA draft.

    The application layer supplies the exact source evidence and computes the
    digest.  Keeping the suggestion as a typed value makes the response and
    create-time equality check share one closed vocabulary without coupling
    the HTTP adapter to the numerical kernel.
    """

    input_mode: str
    source_evidence: Mapping[str, object]
    sweeps: tuple[Mapping[str, object], ...]
    reference_sweep_ordinal: int
    reference_temperature_k: float
    sweep_dispositions: tuple[Mapping[str, object], ...]
    shift_law: Mapping[str, object]
    scoring: Mapping[str, object]
    adjacent_optimizer: Mapping[str, object]
    law_optimizer: Mapping[str, object]
    profile_id: str
    profile_version: str
    material_specific: bool
    production_readiness: str
    requires_confirmation: bool
    recommendation_sha256: str

    def canonical_without_digest(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "input_mode": self.input_mode,
            "source_evidence": dict(self.source_evidence),
            "sweeps": [dict(item) for item in self.sweeps],
            "reference_sweep_ordinal": self.reference_sweep_ordinal,
            "reference_temperature_k": self.reference_temperature_k,
            "sweep_dispositions": [dict(item) for item in self.sweep_dispositions],
            "shift_law": dict(self.shift_law),
            "scoring": dict(self.scoring),
            "adjacent_optimizer": dict(self.adjacent_optimizer),
            "law_optimizer": dict(self.law_optimizer),
        }


@dataclass(frozen=True, slots=True)
class DmaTtsAdjacentEvidence:
    success: bool
    status: int
    iterations: int
    evaluations: int
    objective: float


@dataclass(frozen=True, slots=True)
class DmaTtsScore:
    overlap_min_log10_reduced_omega: float
    overlap_max_log10_reduced_omega: float
    scoring_point_count: int
    storage_mse: float
    loss_mse: float
    storage_rmse: float
    loss_rmse: float
    weighted_mse: float


def _finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _validate_controls(
    scoring: DmaTtsScoringControls,
    adjacent: DmaTtsAdjacentOptimizerControls,
    law: DmaTtsLawOptimizerControls | None,
) -> None:
    if (
        not _finite(scoring.minimum_overlap_decades)
        or float(scoring.minimum_overlap_decades) <= 0
        or not isinstance(scoring.overlap_evaluation_point_count, int)
        or isinstance(scoring.overlap_evaluation_point_count, bool)
        or not 2 <= scoring.overlap_evaluation_point_count <= 10_001
        or not _finite(scoring.storage_weight)
        or not _finite(scoring.loss_weight)
        or scoring.storage_weight < 0
        or scoring.loss_weight < 0
        or scoring.storage_weight + scoring.loss_weight != 1.0
    ):
        raise _fail(
            4313,
            "DMA TTS scoring controls are invalid",
            (
                "Provide explicit finite nonnegative channel weights summing to "
                "one, a positive overlap, and 2..10001 scoring points."
            ),
        )
    if (
        not _finite(adjacent.relative_shift_lower_bound_log10)
        or not _finite(adjacent.relative_shift_upper_bound_log10)
        or adjacent.relative_shift_lower_bound_log10 > adjacent.relative_shift_upper_bound_log10
        or adjacent.xatol != 1e-10
        or adjacent.maxiter != 1000
    ):
        raise _fail(
            4313,
            "DMA TTS adjacent optimizer controls are invalid",
            "Use explicit finite bounds with xatol=1e-10 and maxiter=1000.",
        )
    if law is None:
        return
    if (
        not law.initial_parameters
        or len(law.initial_parameters) != len(law.lower_bounds)
        or len(law.initial_parameters) != len(law.upper_bounds)
        or any(
            not _finite(value) or float(value) <= 0
            for value in (*law.initial_parameters, *law.lower_bounds, *law.upper_bounds)
        )
        or any(
            lower >= initial or initial >= upper
            for initial, lower, upper in zip(
                law.initial_parameters, law.lower_bounds, law.upper_bounds, strict=True
            )
        )
        or law.ftol != 1e-12
        or law.xtol != 1e-12
        or law.gtol != 1e-12
        or law.max_nfev != 5000
    ):
        raise _fail(
            4313,
            "DMA TTS shift-law optimizer controls are invalid",
            (
                "Use positive explicit start and bound vectors with the governed "
                "least-squares tolerances."
            ),
        )


def _log_curve(
    sweep: DmaFrequencySweep,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    return (
        tuple(math.log10(2.0 * math.pi * point.frequency_hz) for point in sweep.points),
        tuple(math.log10(point.storage_modulus_pa) for point in sweep.points),
        tuple(math.log10(point.loss_modulus_pa) for point in sweep.points),
    )


def _interpolate(x: tuple[float, ...], y: tuple[float, ...], point: float) -> float:
    if point <= x[0]:
        return y[0]
    if point >= x[-1]:
        return y[-1]
    for left, right, left_y, right_y in zip(x, x[1:], y, y[1:], strict=True):
        if left <= point <= right:
            fraction = (point - left) / (right - left)
            return left_y + fraction * (right_y - left_y)
    raise AssertionError("interpolation point is outside its sorted domain")


def score_sweep_pair(
    current: DmaFrequencySweep,
    anchor: DmaFrequencySweep,
    relative_shift_log10: float,
    controls: DmaTtsScoringControls,
) -> DmaTtsScore:
    """Score exact shifted overlap using a common inclusive log-frequency grid."""

    _validate_controls(
        controls,
        DmaTtsAdjacentOptimizerControls(-1.0, 1.0),
        None,
    )
    if not _finite(relative_shift_log10):
        raise _fail(
            4313,
            "relative DMA TTS shift is not finite",
            "Use a finite explicit adjacent shift bound.",
        )
    current_x, current_storage, current_loss = _log_curve(current)
    anchor_x, anchor_storage, anchor_loss = _log_curve(anchor)
    overlap_min = max(anchor_x[0], current_x[0] + relative_shift_log10)
    overlap_max = min(anchor_x[-1], current_x[-1] + relative_shift_log10)
    if overlap_max - overlap_min < controls.minimum_overlap_decades:
        raise _fail(
            4314,
            "DMA TTS pair overlap is below the explicit minimum",
            "Increase measured overlap or revise the explicit shift bounds and minimum overlap.",
        )
    grid = tuple(
        overlap_min
        + (overlap_max - overlap_min) * index / (controls.overlap_evaluation_point_count - 1)
        for index in range(controls.overlap_evaluation_point_count)
    )
    storage_residuals = tuple(
        _interpolate(anchor_x, anchor_storage, point)
        - _interpolate(current_x, current_storage, point - relative_shift_log10)
        for point in grid
    )
    loss_residuals = tuple(
        _interpolate(anchor_x, anchor_loss, point)
        - _interpolate(current_x, current_loss, point - relative_shift_log10)
        for point in grid
    )
    storage_mse = sum(value * value for value in storage_residuals) / len(storage_residuals)
    loss_mse = sum(value * value for value in loss_residuals) / len(loss_residuals)
    weighted_mse = controls.storage_weight * storage_mse + controls.loss_weight * loss_mse
    return DmaTtsScore(
        overlap_min,
        overlap_max,
        controls.overlap_evaluation_point_count,
        storage_mse,
        loss_mse,
        math.sqrt(storage_mse),
        math.sqrt(loss_mse),
        weighted_mse,
    )


def _feasible_interval(
    current: DmaFrequencySweep,
    anchor: DmaFrequencySweep,
    scoring: DmaTtsScoringControls,
    optimizer: DmaTtsAdjacentOptimizerControls,
) -> tuple[float, float]:
    current_x, _, _ = _log_curve(current)
    anchor_x, _, _ = _log_curve(anchor)
    lower = max(
        anchor_x[0] + scoring.minimum_overlap_decades - current_x[-1],
        optimizer.relative_shift_lower_bound_log10,
    )
    upper = min(
        anchor_x[-1] - scoring.minimum_overlap_decades - current_x[0],
        optimizer.relative_shift_upper_bound_log10,
    )
    if lower > upper:
        raise _fail(
            4314,
            "DMA TTS adjacent feasible overlap interval is empty",
            "Provide adjacent measured ranges and request bounds with a positive overlap.",
        )
    return lower, upper


def optimize_adjacent_shift(
    current: DmaFrequencySweep,
    anchor: DmaFrequencySweep,
    scoring: DmaTtsScoringControls,
    optimizer: DmaTtsAdjacentOptimizerControls,
) -> tuple[float, DmaTtsScore, DmaTtsAdjacentEvidence]:
    """Find one adjacent shift with the governed SciPy bounded optimizer."""

    lower, upper = _feasible_interval(current, anchor, scoring, optimizer)
    if lower == upper:
        score = score_sweep_pair(current, anchor, lower, scoring)
        return lower, score, DmaTtsAdjacentEvidence(True, 0, 0, 1, score.weighted_mse)

    def objective(value: float) -> float:
        try:
            return score_sweep_pair(current, anchor, float(value), scoring).weighted_mse
        except DmaProcessingError:
            return math.inf

    try:
        outcome = _run_minimize_scalar(objective, (lower, upper))
        candidate = float(outcome.x)
        if (
            not outcome.success
            or not math.isfinite(candidate)
            or not math.isfinite(float(outcome.fun))
        ):
            raise _fail(
                4315,
                "the adjacent DMA TTS optimizer returned an unsuccessful result",
                "Correct the explicit overlap and optimizer controls and retry.",
            )
    except (ValueError, FloatingPointError, OverflowError) as error:
        raise _fail(
            4315,
            "the adjacent DMA TTS optimizer failed",
            "Correct the explicit overlap and optimizer controls and retry.",
        ) from error
    score = score_sweep_pair(current, anchor, candidate, scoring)
    return (
        candidate,
        score,
        DmaTtsAdjacentEvidence(
            True,
            int(getattr(outcome, "status", 0)),
            int(getattr(outcome, "nit", 0)),
            int(getattr(outcome, "nfev", 0)),
            score.weighted_mse,
        ),
    )


def _validate_sweeps(
    sweeps: Sequence[DmaFrequencySweep],
    dispositions: Sequence[DmaFrequencySweepDisposition],
    reference_sweep_ordinal: int,
) -> tuple[
    dict[int, DmaFrequencySweep],
    dict[int, DmaFrequencySweepDisposition],
    tuple[int, ...],
]:
    by_sweep = {item.source_sweep_ordinal: item for item in sweeps}
    supplied_dispositions = {item.source_sweep_ordinal: item for item in dispositions}
    if (
        len(by_sweep) != len(sweeps)
        or len(supplied_dispositions) != len(dispositions)
        or set(by_sweep) != set(supplied_dispositions)
    ):
        raise _fail(
            4311,
            "sweep dispositions do not cover explicit source sweep identities exactly once",
            (
                "Provide one disposition for every positive source_sweep_ordinal "
                "and no inferred groups."
            ),
        )
    by_disposition: dict[int, DmaFrequencySweepDisposition] = {}
    for ordinal, sweep in by_sweep.items():
        disposition = supplied_dispositions[ordinal]
        expected = _representative_temperature(sweep)
        try:
            requested = Decimal(str(disposition.representative_temperature_k))
        except (InvalidOperation, ValueError) as error:
            raise _fail(
                4316,
                "representative temperature is not a normalized finite number",
                "Use the server-derived representative temperature for the exact source sweep.",
            ) from error
        if requested != expected:
            raise _fail(
                4316,
                "requested representative temperature differs from the server-derived value",
                "Use the exact normalized modal temperature from the immutable Test Data revision.",
            )
        for point in sweep.points:
            try:
                measured = Decimal(str(point.measured_temperature_k))
            except (InvalidOperation, ValueError) as error:
                raise _fail(
                    4316,
                    "source measured temperature is not a normalized finite number",
                    "Correct the source temperature and create a new immutable Test Data revision.",
                ) from error
            if (
                not measured.is_finite()
                or abs(measured - expected) > DMA_SWEEP_TEMPERATURE_TOLERANCE_K
            ):
                raise _fail(
                    4316,
                    (
                        "source measured temperature exceeds the inclusive "
                        f"{DMA_SWEEP_TEMPERATURE_TOLERANCE_K} K sweep tolerance"
                    ),
                    "Correct the source temperatures or create a new immutable Test Data revision.",
                )
        by_disposition[ordinal] = replace(
            disposition,
            representative_temperature_k=float(expected),
        )
    ordered = tuple(
        sorted(
            by_sweep,
            key=lambda ordinal: (
                by_disposition[ordinal].representative_temperature_k,
                ordinal,
            ),
        )
    )
    temperatures = {by_disposition[ordinal].representative_temperature_k for ordinal in ordered}
    if len(temperatures) != len(ordered):
        raise _fail(
            4316,
            "representative temperatures are duplicated",
            "Provide one distinct representative temperature per source sweep.",
        )
    calibration = tuple(
        ordinal
        for ordinal in ordered
        if by_disposition[ordinal].partition is DmaPartition.CALIBRATION
    )
    holdout = tuple(
        ordinal for ordinal in ordered if by_disposition[ordinal].partition is DmaPartition.HOLDOUT
    )
    if len(calibration) < 2 or len(holdout) != 1 or reference_sweep_ordinal not in calibration:
        raise _fail(
            4316,
            (
                "DMA TTS requires at least two calibration sweeps, exactly one "
                "holdout, and a calibration reference"
            ),
            "Correct every source-sweep disposition and select one calibration reference.",
        )
    if any(
        by_disposition[ordinal].partition is not DmaPartition.EXCLUDED
        and len(by_sweep[ordinal].points) < 2
        for ordinal in ordered
    ):
        raise _fail(
            4312,
            "an included DMA source sweep has fewer than two measured points",
            "Provide at least two finite positive points in every included source sweep.",
        )
    return by_sweep, by_disposition, ordered


def _representative_temperature(sweep: DmaFrequencySweep) -> Decimal:
    """Return the exact Decimal mode, breaking ties toward the lower value."""

    counts: dict[Decimal, int] = {}
    for point in sweep.points:
        try:
            value = Decimal(str(point.measured_temperature_k))
        except (InvalidOperation, ValueError) as error:
            raise _fail(
                4316,
                "source measured temperature is not finite numeric evidence",
                "Correct the source temperature and create a new immutable Test Data revision.",
            ) from error
        if not value.is_finite() or value <= 0:
            raise _fail(
                4316,
                "source measured temperature is not finite and positive",
                "Correct the source temperature and create a new immutable Test Data revision.",
            )
        counts[value] = counts.get(value, 0) + 1
    maximum = max(counts.values())
    return min(value for value, count in counts.items() if count == maximum)


def representative_temperature_for_sweep(sweep: DmaFrequencySweep) -> Decimal:
    """Expose the exact modal temperature used by recommendation and build."""

    return _representative_temperature(sweep)


def _law_value(
    law: DmaShiftLawRequest,
    parameters: tuple[float, ...],
    temperature_k: float,
) -> float:
    if temperature_k == law.reference_temperature_k:
        return 0.0
    try:
        if law.kind == "wlf_fit":
            return wlf_log10_shift(
                temperature_k,
                law.reference_temperature_k,
                parameters[0],
                parameters[1],
            )
        if law.kind == "arrhenius_fit":
            return arrhenius_log10_shift(
                temperature_k,
                law.reference_temperature_k,
                parameters[0],
                law.gas_constant_j_per_mol_k,
            )
    except (IndexError, TemperatureShiftError) as error:
        raise _fail(
            4313,
            "shift-law evaluation is outside the governed domain",
            "Use positive starts and bounds with a WLF-safe domain.",
        ) from error
    raise _fail(
        4313,
        "unsupported DMA TTS shift-law kind",
        "Use manual_tabulated, wlf_fit, or arrhenius_fit.",
    )


def _fit_shift_law(
    law: DmaShiftLawRequest,
    by_disposition: Mapping[int, DmaFrequencySweepDisposition],
    calibration: tuple[int, ...],
    nonexcluded: tuple[int, ...],
    observed: Mapping[int, float],
    controls: DmaTtsLawOptimizerControls | None,
) -> tuple[dict[int, float], dict[str, object], dict[str, object] | None]:
    required_temperatures = tuple(
        by_disposition[ordinal].representative_temperature_k for ordinal in nonexcluded
    )
    if law.kind == "manual_tabulated":
        try:
            factors = validate_manual_shift_table(
                law.manual_table,
                reference_temperature_k=law.reference_temperature_k,
                required_temperatures=required_temperatures,
            )
            applied = {
                ordinal: next(
                    item.log10_a_t
                    for item in factors
                    if item.temperature_k == by_disposition[ordinal].representative_temperature_k
                )
                for ordinal in nonexcluded
            }
            return (
                applied,
                {
                    "kind": law.kind,
                    "reference_temperature_k": law.reference_temperature_k,
                    "parameter_source": "supplied",
                    "manual_table": [
                        {
                            "temperature_k": item.temperature_k,
                            "log10_a_t": item.log10_a_t,
                        }
                        for item in factors
                    ],
                },
                None,
            )
        except TemperatureShiftError as error:
            raise _fail(
                4313,
                f"manual shift table is invalid: {error}",
                (
                    "Cover every nonexcluded representative temperature and set "
                    "the reference value to exact zero."
                ),
            ) from error

    if law.kind not in {"wlf_fit", "arrhenius_fit"} or controls is None:
        raise _fail(
            4313,
            "shift-law kind and fit controls do not agree",
            "Supply explicit positive starts and bounds for WLF or Arrhenius fitting.",
        )
    expected_count = 2 if law.kind == "wlf_fit" else 1
    if (
        len(law.initial_parameters) != expected_count
        or tuple(law.initial_parameters) != tuple(controls.initial_parameters)
        or tuple(law.lower_bounds) != tuple(controls.lower_bounds)
        or tuple(law.upper_bounds) != tuple(controls.upper_bounds)
    ):
        raise _fail(
            4313,
            "shift-law parameters and optimizer controls disagree",
            "Repeat the exact fit starts and bounds in the shift-law and optimizer objects.",
        )
    if (
        law.kind == "arrhenius_fit"
        and law.gas_constant_j_per_mol_k != UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K
    ):
        raise _fail(
            4313,
            "Arrhenius gas constant is not the governed fixed value",
            "Use the governed universal gas constant.",
        )
    if law.kind == "wlf_fit" and any(
        law.lower_bounds[1]
        + by_disposition[ordinal].representative_temperature_k
        - law.reference_temperature_k
        <= 0
        for ordinal in nonexcluded
    ):
        raise _fail(
            4313,
            "WLF fit bounds cross a singular domain",
            "Raise the lower C2 bound so every nonexcluded temperature remains WLF-safe.",
        )

    fit_ordinals = tuple(
        ordinal
        for ordinal in calibration
        if by_disposition[ordinal].representative_temperature_k != law.reference_temperature_k
    )
    fit_temperatures = tuple(
        by_disposition[ordinal].representative_temperature_k for ordinal in fit_ordinals
    )
    fit_targets = tuple(observed[ordinal] for ordinal in fit_ordinals)

    def residual(parameters: Sequence[float]) -> list[float]:
        values = tuple(float(item) for item in parameters)
        return [
            _law_value(law, values, temperature) - target
            for temperature, target in zip(fit_temperatures, fit_targets, strict=True)
        ]

    try:
        outcome = _run_least_squares(
            residual,
            law.initial_parameters,
            law.lower_bounds,
            law.upper_bounds,
        )
        fitted = tuple(float(item) for item in outcome.x)
        if (
            not outcome.success
            or any(not _finite(item) for item in fitted)
            or not _finite(outcome.cost)
        ):
            raise _fail(
                4315,
                "the DMA TTS shift-law optimizer returned an unsuccessful result",
                "Correct the explicit shift-law starts, bounds, and measured calibration overlaps.",
            )
    except (ValueError, FloatingPointError, OverflowError, DmaProcessingError) as error:
        if isinstance(error, DmaProcessingError):
            raise
        raise _fail(
            4315,
            "the DMA TTS shift-law optimizer failed",
            "Correct the explicit shift-law starts, bounds, and measured calibration overlaps.",
        ) from error

    applied = {
        ordinal: _law_value(
            law,
            fitted,
            by_disposition[ordinal].representative_temperature_k,
        )
        for ordinal in nonexcluded
    }
    if any(not _finite(value) for value in applied.values()):
        raise _fail(
            4315,
            "the fitted DMA TTS law produced a non-finite shift",
            "Correct the explicit fit bounds and representative temperatures.",
        )
    law_document: dict[str, object] = {
        "kind": law.kind,
        "reference_temperature_k": law.reference_temperature_k,
        "parameter_source": "fitted",
        "fitted_parameters": list(fitted),
        "initial_parameters": list(law.initial_parameters),
        "lower_bounds": list(law.lower_bounds),
        "upper_bounds": list(law.upper_bounds),
    }
    if law.kind == "wlf_fit":
        law_document.update(c1=fitted[0], c2_k=fitted[1])
    else:
        law_document.update(
            activation_energy_j_per_mol=fitted[0],
            gas_constant_j_per_mol_k=law.gas_constant_j_per_mol_k,
        )
    optimizer_document: dict[str, object] = {
        "optimizer_id": DMA_TTS_LAW_OPTIMIZER_ID,
        "scipy_version": _SCIPY_VERSION,
        "method": "least_squares",
        "method_variant": "trf",
        "ftol": 1e-12,
        "xtol": 1e-12,
        "gtol": 1e-12,
        "max_nfev": 5000,
        "seed": None,
        "status": int(outcome.status),
        "success": bool(outcome.success),
        "nfev": int(outcome.nfev),
        "cost": float(outcome.cost),
        "optimality": float(outcome.optimality),
        "objective_mse": sum(value * value for value in residual(fitted))
        / max(1, len(fit_targets)),
        "initial_parameters": list(law.initial_parameters),
        "lower_bounds": list(law.lower_bounds),
        "upper_bounds": list(law.upper_bounds),
    }
    return applied, law_document, optimizer_document


def _application_intervals(
    sweeps: Mapping[int, DmaFrequencySweep],
    dispositions: Mapping[int, DmaFrequencySweepDisposition],
    applied: Mapping[int, float],
) -> tuple[dict[str, object], ...]:
    ranges: list[tuple[float, float]] = []
    for ordinal, disposition in dispositions.items():
        if disposition.partition is not DmaPartition.CALIBRATION:
            continue
        x, _, _ = _log_curve(sweeps[ordinal])
        shift = applied[ordinal]
        ranges.append((x[0] + shift, x[-1] + shift))
    endpoints = sorted({endpoint for item in ranges for endpoint in item})
    covered: list[tuple[float, float]] = []
    for left, right in pairwise(endpoints):
        if right <= left:
            continue
        midpoint = (left + right) / 2.0
        if sum(start <= midpoint <= finish for start, finish in ranges) < 2:
            continue
        if covered and covered[-1][1] == left:
            covered[-1] = (covered[-1][0], right)
        else:
            covered.append((left, right))
    if not covered:
        raise _fail(
            4314,
            "calibration isotherms have no positive-width common application domain",
            "Provide at least two calibration ranges with positive-width overlap.",
        )
    return tuple(
        {
            "min_reduced_angular_frequency_rad_per_s": 10.0**left,
            "max_reduced_angular_frequency_rad_per_s": 10.0**right,
        }
        for left, right in covered
    )


def build_multi_frequency_master_curve(
    sweeps: Sequence[DmaFrequencySweep],
    dispositions: Sequence[DmaFrequencySweepDisposition],
    *,
    reference_sweep_ordinal: int,
    shift_law: DmaShiftLawRequest,
    scoring: DmaTtsScoringControls,
    adjacent_optimizer: DmaTtsAdjacentOptimizerControls,
    law_optimizer: DmaTtsLawOptimizerControls | None,
    confirmed: bool,
    confirmation_reason: str,
) -> DmaFrequencyMasterCurveBuildResult:
    """Build the sole canonical ragged result for multi-frequency DMA."""

    if not confirmed or not confirmation_reason.strip():
        raise _fail(
            4316,
            "DMA TTS settings are not explicitly confirmed",
            "Confirm the complete multi-frequency request and record the engineering reason.",
        )
    _validate_controls(scoring, adjacent_optimizer, law_optimizer)
    by_sweep, by_disposition, ordered = _validate_sweeps(
        sweeps, dispositions, reference_sweep_ordinal
    )
    reference_temperature = by_disposition[reference_sweep_ordinal].representative_temperature_k
    if shift_law.reference_temperature_k != reference_temperature:
        raise _fail(
            4316,
            "shift-law reference temperature differs from the selected reference sweep",
            "Use the selected reference sweep representative temperature exactly.",
        )
    calibration = tuple(
        ordinal
        for ordinal in ordered
        if by_disposition[ordinal].partition is DmaPartition.CALIBRATION
    )
    nonexcluded = tuple(
        ordinal
        for ordinal in ordered
        if by_disposition[ordinal].partition is not DmaPartition.EXCLUDED
    )

    observed: dict[int, float] = {reference_sweep_ordinal: 0.0}
    adjacent: dict[int, tuple[int, float, DmaTtsScore, DmaTtsAdjacentEvidence]] = {}
    reference_index = calibration.index(reference_sweep_ordinal)
    for direction in (-1, 1):
        anchor_index = reference_index
        indexes = (
            range(reference_index - 1, -1, -1)
            if direction < 0
            else range(reference_index + 1, len(calibration))
        )
        for current_index in indexes:
            anchor_ordinal = calibration[anchor_index]
            current_ordinal = calibration[current_index]
            relative, score, evidence = optimize_adjacent_shift(
                by_sweep[current_ordinal],
                by_sweep[anchor_ordinal],
                scoring,
                adjacent_optimizer,
            )
            observed[current_ordinal] = observed[anchor_ordinal] + relative
            adjacent[current_ordinal] = (
                anchor_ordinal,
                relative,
                score,
                evidence,
            )
            anchor_index = current_index

    applied, law_document, law_optimizer_document = _fit_shift_law(
        shift_law,
        by_disposition,
        calibration,
        nonexcluded,
        observed,
        law_optimizer,
    )

    rows: list[DmaFrequencyMasterCurveRow] = []
    for ordinal in ordered:
        sweep = by_sweep[ordinal]
        disposition = by_disposition[ordinal]
        source_ordinals = tuple(point.source_ordinal for point in sweep.points)
        measured = tuple(point.measured_temperature_k for point in sweep.points)
        frequencies = tuple(point.frequency_hz for point in sweep.points)
        omegas = tuple(2.0 * math.pi * value for value in frequencies)
        storage = tuple(point.storage_modulus_pa for point in sweep.points)
        loss = tuple(point.loss_modulus_pa for point in sweep.points)
        common: DmaFrequencyMasterCurveRowValues = {
            "input_mode": DmaInputMode.MULTI_FREQUENCY_ISOTHERMS.value,
            "source_sweep_ordinal": ordinal,
            "representative_temperature_k": disposition.representative_temperature_k,
            "partition": disposition.partition,
            "is_reference": False,
            "exclusion_reason": disposition.exclusion_reason,
            "holdout_evaluation_status": None,
            "source_ordinals": source_ordinals,
            "measured_temperature_k": measured,
            "source_frequency_hz": frequencies,
            "angular_frequency_rad_per_s": omegas,
            "storage_modulus_pa": storage,
            "loss_modulus_pa": loss,
            "source_tan_delta": (None,) * len(source_ordinals),
            "loss_modulus_origin": ("measured",) * len(source_ordinals),
            "reduced_angular_frequency_rad_per_s": None,
            "raw_angular_frequency_min_rad_per_s": min(omegas),
            "raw_angular_frequency_max_rad_per_s": max(omegas),
            "shifted_angular_frequency_min_rad_per_s": None,
            "shifted_angular_frequency_max_rad_per_s": None,
            "comparison_sweep_ordinal": None,
            "observed_log10_a_t": None,
            "applied_log10_a_t": None,
            "shift_factor": None,
            "shift_residual_log10_a_t": None,
            "overlap_log10_reduced_angular_frequency_min": None,
            "overlap_log10_reduced_angular_frequency_max": None,
            "scoring_point_count": None,
            "storage_mse": None,
            "loss_mse": None,
            "storage_rmse": None,
            "loss_rmse": None,
            "weighted_mse": None,
            "adjacent_success": None,
            "adjacent_status": None,
            "adjacent_iterations": None,
            "adjacent_evaluations": None,
            "adjacent_objective": None,
        }
        if disposition.partition is DmaPartition.EXCLUDED:
            rows.append(DmaFrequencyMasterCurveRow(**common))
            continue
        applied_value = 0.0 if ordinal == reference_sweep_ordinal else applied[ordinal]
        try:
            factor = 10.0**applied_value
        except OverflowError as error:
            raise _fail(
                4315,
                "applied DMA TTS shift overflows",
                "Correct the explicit shift-law bounds and representative temperatures.",
            ) from error
        reduced = tuple(omega * factor for omega in omegas)
        if any(not _finite(value) or float(value) <= 0 for value in reduced):
            raise _fail(
                4315,
                "applied DMA TTS shift is not finite and positive",
                "Correct the explicit shift-law bounds and representative temperatures.",
            )
        common["reduced_angular_frequency_rad_per_s"] = reduced
        common["shifted_angular_frequency_min_rad_per_s"] = min(reduced)
        common["shifted_angular_frequency_max_rad_per_s"] = max(reduced)
        common["applied_log10_a_t"] = applied_value
        common["shift_factor"] = factor
        if ordinal == reference_sweep_ordinal:
            common["is_reference"] = True
            common["observed_log10_a_t"] = 0.0
            common["shift_residual_log10_a_t"] = 0.0
        elif disposition.partition is DmaPartition.CALIBRATION:
            comparison, _, _, evidence = adjacent[ordinal]
            observed_value = observed[ordinal]
            common["comparison_sweep_ordinal"] = comparison
            common["observed_log10_a_t"] = observed_value
            common["shift_residual_log10_a_t"] = applied_value - observed_value
            common["adjacent_success"] = evidence.success
            common["adjacent_status"] = evidence.status
            common["adjacent_iterations"] = evidence.iterations
            common["adjacent_evaluations"] = evidence.evaluations
            common["adjacent_objective"] = evidence.objective
            score = adjacent[ordinal][2]
            common["overlap_log10_reduced_angular_frequency_min"] = (
                score.overlap_min_log10_reduced_omega
            )
            common["overlap_log10_reduced_angular_frequency_max"] = (
                score.overlap_max_log10_reduced_omega
            )
            common["scoring_point_count"] = score.scoring_point_count
            common["storage_mse"] = score.storage_mse
            common["loss_mse"] = score.loss_mse
            common["storage_rmse"] = score.storage_rmse
            common["loss_rmse"] = score.loss_rmse
            common["weighted_mse"] = score.weighted_mse
        else:
            comparison = min(
                calibration,
                key=lambda item: (
                    abs(
                        by_disposition[item].representative_temperature_k
                        - disposition.representative_temperature_k
                    ),
                    by_disposition[item].representative_temperature_k,
                    item,
                ),
            )
            common["holdout_evaluation_status"] = "evaluated"
            common["comparison_sweep_ordinal"] = comparison
            relative = applied_value - applied[comparison]
            score = score_sweep_pair(sweep, by_sweep[comparison], relative, scoring)
            common["overlap_log10_reduced_angular_frequency_min"] = (
                score.overlap_min_log10_reduced_omega
            )
            common["overlap_log10_reduced_angular_frequency_max"] = (
                score.overlap_max_log10_reduced_omega
            )
            common["scoring_point_count"] = score.scoring_point_count
            common["storage_mse"] = score.storage_mse
            common["loss_mse"] = score.loss_mse
            common["storage_rmse"] = score.storage_rmse
            common["loss_rmse"] = score.loss_rmse
            common["weighted_mse"] = score.weighted_mse
        rows.append(DmaFrequencyMasterCurveRow(**common))

    application_intervals = _application_intervals(by_sweep, by_disposition, applied)
    calibration_rows = tuple(
        row for row in rows if row.partition is DmaPartition.CALIBRATION and not row.is_reference
    )
    if not calibration_rows:
        raise _fail(
            4314,
            "no nonreference calibration comparison evidence exists",
            "Provide at least two usable calibration sweeps with a positive overlap.",
        )
    residual_summary: dict[str, object] = {
        "calibration_comparison_count": len(calibration_rows),
        "units": "log10(modulus) and log10(aT)",
        "storage_mse": sum(cast(float, row.storage_mse) for row in calibration_rows)
        / len(calibration_rows),
        "loss_mse": sum(cast(float, row.loss_mse) for row in calibration_rows)
        / len(calibration_rows),
        "storage_rmse": math.sqrt(
            sum(cast(float, row.storage_mse) for row in calibration_rows) / len(calibration_rows)
        ),
        "loss_rmse": math.sqrt(
            sum(cast(float, row.loss_mse) for row in calibration_rows) / len(calibration_rows)
        ),
        "weighted_mse": sum(cast(float, row.weighted_mse) for row in calibration_rows)
        / len(calibration_rows),
        "holdout_evaluation_separate": True,
    }
    law_document["per_temperature"] = [
        {
            "source_sweep_ordinal": row.source_sweep_ordinal,
            "representative_temperature_k": row.representative_temperature_k,
            "observed_log10_a_t": row.observed_log10_a_t,
            "applied_log10_a_t": row.applied_log10_a_t,
            "shift_residual_log10_a_t": row.shift_residual_log10_a_t,
        }
        for row in rows
        if row.partition is not DmaPartition.EXCLUDED
    ]
    law_document["adjacent_observed"] = [
        {
            "source_sweep_ordinal": ordinal,
            "comparison_sweep_ordinal": evidence[0],
            "relative_observed_log10_shift": evidence[1],
            "score": {
                "overlap_min_log10_reduced_omega": evidence[2].overlap_min_log10_reduced_omega,
                "overlap_max_log10_reduced_omega": evidence[2].overlap_max_log10_reduced_omega,
                "storage_mse": evidence[2].storage_mse,
                "loss_mse": evidence[2].loss_mse,
                "weighted_mse": evidence[2].weighted_mse,
            },
            "evidence": {
                "success": evidence[3].success,
                "status": evidence[3].status,
                "iterations": evidence[3].iterations,
                "evaluations": evidence[3].evaluations,
                "objective": evidence[3].objective,
            },
        }
        for ordinal, evidence in sorted(adjacent.items())
    ]
    scoring_document: dict[str, object] = {
        "scorer_id": DMA_TTS_SCORER_ID,
        "minimum_overlap_decades": scoring.minimum_overlap_decades,
        "scoring_point_count": scoring.overlap_evaluation_point_count,
        "storage_weight": scoring.storage_weight,
        "loss_weight": scoring.loss_weight,
        "grid_policy": "equally_spaced_log10_frequency_inside_measured_overlap",
        "interpolation": "piecewise_linear_log10_modulus",
        "persisted_scoring_points": False,
    }
    adjacent_document: dict[str, object] = {
        "optimizer_id": DMA_TTS_ADJACENT_OPTIMIZER_ID,
        "scipy_version": scipy.__version__,
        "method": "minimize_scalar",
        "method_variant": "bounded_or_direct_singleton",
        "singleton_policy": "evaluate_once_without_optimizer",
        "relative_shift_lower_bound_log10": adjacent_optimizer.relative_shift_lower_bound_log10,
        "relative_shift_upper_bound_log10": adjacent_optimizer.relative_shift_upper_bound_log10,
        "xatol": 1e-10,
        "maxiter": 1000,
        "seed": None,
        "evidence": adjacent_document_evidence(adjacent),
    }
    application_range: dict[str, object] = {
        "basis": "at_least_two_shifted_calibration_isotherms",
        "holdout_included": False,
        "reduced_angular_frequency_intervals_rad_per_s": [
            {
                "minimum": item["min_reduced_angular_frequency_rad_per_s"],
                "maximum": item["max_reduced_angular_frequency_rad_per_s"],
            }
            for item in application_intervals
        ],
        "calibration_temperature_interval_k": {
            "minimum": min(
                by_disposition[ordinal].representative_temperature_k for ordinal in calibration
            ),
            "maximum": max(
                by_disposition[ordinal].representative_temperature_k for ordinal in calibration
            ),
        },
    }
    return DmaFrequencyMasterCurveBuildResult(
        tuple(rows),
        DmaInputMode.MULTI_FREQUENCY_ISOTHERMS.value,
        reference_sweep_ordinal,
        reference_temperature,
        law_document,
        scoring_document,
        adjacent_document,
        law_optimizer_document,
        residual_summary,
        application_intervals,
        application_range,
    )


def adjacent_document_evidence(
    adjacent: Mapping[int, tuple[int, float, DmaTtsScore, DmaTtsAdjacentEvidence]],
) -> list[dict[str, object]]:
    """Serialize adjacent optimizer evidence in source-independent order."""

    return [
        {
            "source_sweep_ordinal": ordinal,
            "comparison_sweep_ordinal": value[0],
            "relative_observed_log10_shift": value[1],
            "score": {
                "overlap_min_log10_reduced_omega": value[2].overlap_min_log10_reduced_omega,
                "overlap_max_log10_reduced_omega": value[2].overlap_max_log10_reduced_omega,
                "storage_mse": value[2].storage_mse,
                "loss_mse": value[2].loss_mse,
                "weighted_mse": value[2].weighted_mse,
            },
            "evidence": {
                "success": value[3].success,
                "status": value[3].status,
                "iterations": value[3].iterations,
                "evaluations": value[3].evaluations,
                "objective": value[3].objective,
            },
        }
        for ordinal, value in sorted(adjacent.items())
    ]
