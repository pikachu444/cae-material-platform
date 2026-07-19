"""Solver-neutral polymer relaxation processing for the configurable Workbench.

The methods in this module operate on quantity-mapped curves.  They do not know about a
particular test method or solver and never extrapolate beyond the observed time domain.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares  # type: ignore[import-untyped]


class PolymerViscoelasticError(ValueError):
    """A relaxation processing request is invalid or numerically unsuccessful."""


@dataclass(frozen=True, slots=True)
class PolymerScalar:
    key: str
    quantity_semantics: str
    value: float
    unit: str


@dataclass(frozen=True, slots=True)
class PolymerProcessingResult:
    columns: dict[str, NDArray[np.float64]]
    units: dict[str, str]
    diagnostics: tuple[str, ...]
    scalars: tuple[PolymerScalar, ...]


@dataclass(frozen=True, slots=True)
class _PronyCandidate:
    term_count: int
    equilibrium_modulus_pa: float
    shear_moduli_pa: tuple[float, ...]
    relaxation_times_s: tuple[float, ...]
    predicted_modulus_pa: NDArray[np.float64]
    normalized_rmse: float
    bic: float
    function_evaluations: int


def _number(options: dict[str, Any], key: str) -> float:
    value = options.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise PolymerViscoelasticError(f"option {key} must be a finite number")
    return float(value)


def _integer(options: dict[str, Any], key: str) -> int:
    value = options.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PolymerViscoelasticError(f"option {key} must be an integer")
    return value


def _text(options: dict[str, Any], key: str) -> str:
    value = options.get(key)
    if not isinstance(value, str) or not value:
        raise PolymerViscoelasticError(f"option {key} must be a non-empty string")
    return value


def log_time_resample(
    columns: dict[str, NDArray[np.float64]],
    units: dict[str, str],
    independent_quantity: str,
    options: dict[str, Any],
) -> PolymerProcessingResult:
    """Resample every mapped quantity on an explicit log10-time grid without extrapolation."""

    if units.get(independent_quantity) != "s":
        raise PolymerViscoelasticError("log-time resampling requires normalized time unit s")
    start = _number(options, "start_time_s")
    end = _number(options, "end_time_s")
    count = _integer(options, "count")
    if options.get("extrapolation") != "reject":
        raise PolymerViscoelasticError("log-time resampling only supports reject extrapolation")
    time = columns[independent_quantity]
    if np.any(time <= 0) or np.any(np.diff(time) <= 0):
        raise PolymerViscoelasticError(
            "log-time resampling requires positive, sorted, unique time values"
        )
    if start <= 0 or start >= end or not 3 <= count <= 100_000:
        raise PolymerViscoelasticError(
            "log-time resampling requires 0 < start < end and count within 3..100000"
        )
    if start < float(time[0]) or end > float(time[-1]):
        raise PolymerViscoelasticError(
            "log-time resampling would extrapolate beyond the observed domain"
        )
    source_log_time = np.log10(time)
    grid_log_time = np.linspace(math.log10(start), math.log10(end), count)
    grid_time = np.power(10.0, grid_log_time)
    result = {
        key: np.asarray(np.interp(grid_log_time, source_log_time, values), dtype=np.float64)
        for key, values in columns.items()
    }
    result[independent_quantity] = np.asarray(grid_time, dtype=np.float64)
    return PolymerProcessingResult(
        columns=result,
        units={},
        diagnostics=(
            f"log10-time piecewise-linear interpolation on {count} points",
            "observed positive-time domain only; extrapolation rejected",
        ),
        scalars=(),
    )


def _candidate_term_counts(options: dict[str, Any]) -> tuple[int, ...]:
    value = options.get("candidate_term_counts")
    if not isinstance(value, list) or not value:
        raise PolymerViscoelasticError("candidate_term_counts must be a non-empty array")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise PolymerViscoelasticError("candidate term counts must be integers")
    counts = tuple(value)
    if any(not 1 <= item <= 10 for item in counts) or len(set(counts)) != len(counts):
        raise PolymerViscoelasticError("candidate term counts must be unique within 1..10")
    return tuple(sorted(counts))


def _fit_candidate(
    time_s: NDArray[np.float64],
    modulus_pa: NDArray[np.float64],
    *,
    term_count: int,
    normalization_modulus_pa: float,
    minimum_relaxation_time_s: float,
    maximum_relaxation_time_s: float,
    maximum_function_evaluations: int,
) -> _PronyCandidate:
    observed = modulus_pa / normalization_modulus_pa
    upper_modulus = max(float(np.max(observed)) * 2.0, 1.0)
    equilibrium_initial = max(float(np.min(observed)) * 0.95, 1e-8)
    transient_total = max(float(np.max(observed)) - equilibrium_initial, 1e-6)
    initial_times = np.geomspace(
        max(minimum_relaxation_time_s, float(time_s[0])),
        min(maximum_relaxation_time_s, float(time_s[-1])),
        term_count,
    )
    initial = np.concatenate(
        (
            np.asarray([equilibrium_initial]),
            np.full(term_count, transient_total / term_count),
            np.log(initial_times),
        )
    )
    lower = np.concatenate(
        (
            np.asarray([1e-12]),
            np.full(term_count, 1e-12),
            np.full(term_count, math.log(minimum_relaxation_time_s)),
        )
    )
    upper = np.concatenate(
        (
            np.asarray([upper_modulus]),
            np.full(term_count, upper_modulus),
            np.full(term_count, math.log(maximum_relaxation_time_s)),
        )
    )

    def prediction(parameters: NDArray[np.float64]) -> NDArray[np.float64]:
        equilibrium = parameters[0]
        amplitudes = parameters[1 : term_count + 1]
        relaxation_times = np.exp(parameters[term_count + 1 :])
        return np.asarray(
            equilibrium
            + np.sum(
                amplitudes[:, np.newaxis]
                * np.exp(-time_s[np.newaxis, :] / relaxation_times[:, np.newaxis]),
                axis=0,
            ),
            dtype=np.float64,
        )

    outcome = least_squares(
        lambda parameters: prediction(parameters) - observed,
        x0=initial,
        bounds=(lower, upper),
        method="trf",
        ftol=1e-11,
        xtol=1e-11,
        gtol=1e-11,
        max_nfev=maximum_function_evaluations,
    )
    if not outcome.success or not np.all(np.isfinite(outcome.x)):
        raise PolymerViscoelasticError(
            f"{term_count}-term Prony candidate did not converge: {outcome.message}"
        )
    equilibrium = float(outcome.x[0] * normalization_modulus_pa)
    amplitudes = outcome.x[1 : term_count + 1] * normalization_modulus_pa
    relaxation_times = np.exp(outcome.x[term_count + 1 :])
    order = np.argsort(relaxation_times)
    amplitudes = amplitudes[order]
    relaxation_times = relaxation_times[order]
    predicted = np.asarray(
        equilibrium
        + np.sum(
            amplitudes[:, np.newaxis]
            * np.exp(-time_s[np.newaxis, :] / relaxation_times[:, np.newaxis]),
            axis=0,
        ),
        dtype=np.float64,
    )
    normalized_residual = (predicted - modulus_pa) / normalization_modulus_pa
    rss = max(float(np.sum(normalized_residual**2)), np.finfo(float).tiny)
    parameter_count = 1 + 2 * term_count
    bic = len(time_s) * math.log(rss / len(time_s)) + parameter_count * math.log(len(time_s))
    return _PronyCandidate(
        term_count=term_count,
        equilibrium_modulus_pa=equilibrium,
        shear_moduli_pa=tuple(float(item) for item in amplitudes),
        relaxation_times_s=tuple(float(item) for item in relaxation_times),
        predicted_modulus_pa=predicted,
        normalized_rmse=math.sqrt(rss / len(time_s)),
        bic=bic,
        function_evaluations=int(outcome.nfev),
    )


def fit_prony_candidates(
    columns: dict[str, NDArray[np.float64]],
    units: dict[str, str],
    options: dict[str, Any],
) -> PolymerProcessingResult:
    """Fit and compare bounded generalized-Maxwell candidates on observed relaxation data."""

    time_key = _text(options, "time_quantity")
    modulus_key = _text(options, "modulus_quantity")
    if time_key not in columns or modulus_key not in columns:
        raise PolymerViscoelasticError("Prony fitting quantities are not mapped")
    if units.get(time_key) != "s" or units.get(modulus_key) != "Pa":
        raise PolymerViscoelasticError(
            "Prony fitting requires normalized time unit s and modulus unit Pa"
        )
    time_s = columns[time_key]
    modulus_pa = columns[modulus_key]
    if len(time_s) < 5 or np.any(time_s <= 0) or np.any(np.diff(time_s) <= 0):
        raise PolymerViscoelasticError(
            "Prony fitting requires at least five positive, sorted, unique time points"
        )
    if np.any(modulus_pa <= 0):
        raise PolymerViscoelasticError("Prony fitting requires positive relaxation modulus")
    counts = _candidate_term_counts(options)
    selection_mode = _text(options, "selection_mode")
    selected_term_count = _integer(options, "selected_term_count")
    normalization = _number(options, "normalization_modulus_pa")
    minimum_tau = _number(options, "minimum_relaxation_time_s")
    maximum_tau = _number(options, "maximum_relaxation_time_s")
    maximum_evaluations = _integer(options, "maximum_function_evaluations")
    selection_reason_value = options.get(
        "selection_reason",
        "Historical Recipe: candidate selection reason was not recorded.",
    )
    if not isinstance(selection_reason_value, str) or not selection_reason_value.strip():
        raise PolymerViscoelasticError("selection_reason must be non-empty when provided")
    selection_reason = selection_reason_value.strip()
    if normalization <= 0 or minimum_tau <= 0 or minimum_tau >= maximum_tau:
        raise PolymerViscoelasticError("normalization and relaxation-time bounds are invalid")
    if not 50 <= maximum_evaluations <= 100_000:
        raise PolymerViscoelasticError("maximum_function_evaluations must be within 50..100000")
    if selection_mode not in {"automatic_bic", "manual"}:
        raise PolymerViscoelasticError("selection_mode must be automatic_bic or manual")
    if selection_mode == "manual" and selected_term_count not in counts:
        raise PolymerViscoelasticError("manual selected_term_count must be a fitted candidate")
    candidates = tuple(
        _fit_candidate(
            time_s,
            modulus_pa,
            term_count=count,
            normalization_modulus_pa=normalization,
            minimum_relaxation_time_s=minimum_tau,
            maximum_relaxation_time_s=maximum_tau,
            maximum_function_evaluations=maximum_evaluations,
        )
        for count in counts
    )
    selected = (
        min(candidates, key=lambda item: (item.bic, item.term_count))
        if selection_mode == "automatic_bic"
        else next(item for item in candidates if item.term_count == selected_term_count)
    )
    result = dict(columns)
    result_units: dict[str, str] = {}
    diagnostics: list[str] = []
    scalars: list[PolymerScalar] = []
    for candidate in candidates:
        key = f"modulus.prony.candidate_{candidate.term_count}_term"
        result[key] = candidate.predicted_modulus_pa
        result_units[key] = "Pa"
        diagnostics.append(
            f"{candidate.term_count}-term candidate: normalized RMSE="
            f"{candidate.normalized_rmse:.8g}, BIC={candidate.bic:.8g}, "
            f"nfev={candidate.function_evaluations}"
        )
        scalars.extend(
            (
                PolymerScalar(
                    f"prony_{candidate.term_count}_normalized_rmse",
                    "statistics.root_mean_square.normalized",
                    candidate.normalized_rmse,
                    "1",
                ),
                PolymerScalar(
                    f"prony_{candidate.term_count}_bic",
                    "statistics.bayesian_information_criterion",
                    candidate.bic,
                    "1",
                ),
            )
        )
    result["modulus.prony.selected"] = selected.predicted_modulus_pa
    result_units["modulus.prony.selected"] = "Pa"
    instantaneous = selected.equilibrium_modulus_pa + sum(selected.shear_moduli_pa)
    scalars.extend(
        (
            PolymerScalar(
                "prony_selected_term_count",
                "model.prony.term_count",
                float(selected.term_count),
                "1",
            ),
            PolymerScalar(
                "prony_equilibrium_modulus",
                "modulus.shear.equilibrium",
                selected.equilibrium_modulus_pa,
                "Pa",
            ),
            PolymerScalar(
                "prony_instantaneous_modulus",
                "modulus.shear.instantaneous",
                instantaneous,
                "Pa",
            ),
        )
    )
    for ordinal, (amplitude, relaxation_time) in enumerate(
        zip(selected.shear_moduli_pa, selected.relaxation_times_s, strict=True), start=1
    ):
        scalars.extend(
            (
                PolymerScalar(
                    f"prony_g_ratio_{ordinal}",
                    "model.prony.shear_ratio",
                    amplitude / instantaneous,
                    "1",
                ),
                PolymerScalar(
                    f"prony_relaxation_time_{ordinal}",
                    "time.relaxation",
                    relaxation_time,
                    "s",
                ),
            )
        )
    diagnostics.extend(
        (
            f"selected {selected.term_count}-term candidate by {selection_mode}",
            f"engineering selection reason: {selection_reason}",
            "generalized Maxwell fit is reference evidence; promotion requires review",
            "fit and candidate curves remain inside the observed time domain",
        )
    )
    return PolymerProcessingResult(
        columns=result,
        units=result_units,
        diagnostics=tuple(diagnostics),
        scalars=tuple(scalars),
    )


def _fit_frequency_candidate(
    frequency_hz: NDArray[np.float64],
    storage_modulus_pa: NDArray[np.float64],
    loss_modulus_pa: NDArray[np.float64],
    *,
    term_count: int,
    normalization_modulus_pa: float,
    minimum_relaxation_time_s: float,
    maximum_relaxation_time_s: float,
    maximum_function_evaluations: int,
) -> _PronyCandidate:
    """Fit one generalized-Maxwell candidate to storage and loss modulus together."""

    angular_frequency = 2.0 * math.pi * frequency_hz
    observed_storage = storage_modulus_pa / normalization_modulus_pa
    observed_loss = loss_modulus_pa / normalization_modulus_pa
    upper_modulus = max(float(np.max(observed_storage)) * 2.0, 1.0)
    equilibrium_initial = max(float(np.min(observed_storage)) * 0.95, 1e-8)
    transient_total = max(float(np.max(observed_storage)) - equilibrium_initial, 1e-6)
    observed_tau_min = 1.0 / float(np.max(angular_frequency))
    observed_tau_max = 1.0 / float(np.min(angular_frequency))
    initial_times = np.geomspace(
        max(minimum_relaxation_time_s, observed_tau_min),
        min(maximum_relaxation_time_s, observed_tau_max),
        term_count,
    )
    initial = np.concatenate(
        (
            np.asarray([equilibrium_initial]),
            np.full(term_count, transient_total / term_count),
            np.log(initial_times),
        )
    )
    lower = np.concatenate(
        (
            np.asarray([1e-12]),
            np.full(term_count, 1e-12),
            np.full(term_count, math.log(minimum_relaxation_time_s)),
        )
    )
    upper = np.concatenate(
        (
            np.asarray([upper_modulus]),
            np.full(term_count, upper_modulus),
            np.full(term_count, math.log(maximum_relaxation_time_s)),
        )
    )

    def prediction(
        parameters: NDArray[np.float64],
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        equilibrium = parameters[0]
        amplitudes = parameters[1 : term_count + 1]
        relaxation_times = np.exp(parameters[term_count + 1 :])
        omega_tau = angular_frequency[np.newaxis, :] * relaxation_times[:, np.newaxis]
        denominator = 1.0 + omega_tau**2
        storage = equilibrium + np.sum(
            amplitudes[:, np.newaxis] * omega_tau**2 / denominator,
            axis=0,
        )
        loss = np.sum(amplitudes[:, np.newaxis] * omega_tau / denominator, axis=0)
        return np.asarray(storage, dtype=np.float64), np.asarray(loss, dtype=np.float64)

    def residual(parameters: NDArray[np.float64]) -> NDArray[np.float64]:
        storage, loss = prediction(parameters)
        return np.concatenate((storage - observed_storage, loss - observed_loss))

    outcome = least_squares(
        residual,
        x0=initial,
        bounds=(lower, upper),
        method="trf",
        ftol=1e-11,
        xtol=1e-11,
        gtol=1e-11,
        max_nfev=maximum_function_evaluations,
    )
    if not outcome.success or not np.all(np.isfinite(outcome.x)):
        raise PolymerViscoelasticError(
            f"{term_count}-term DMA Prony candidate did not converge: {outcome.message}"
        )
    equilibrium = float(outcome.x[0] * normalization_modulus_pa)
    amplitudes = outcome.x[1 : term_count + 1] * normalization_modulus_pa
    relaxation_times = np.exp(outcome.x[term_count + 1 :])
    order = np.argsort(relaxation_times)
    amplitudes = amplitudes[order]
    relaxation_times = relaxation_times[order]
    predicted_storage_normalized, predicted_loss_normalized = prediction(outcome.x)
    predicted_storage = predicted_storage_normalized * normalization_modulus_pa
    predicted_loss = predicted_loss_normalized * normalization_modulus_pa
    normalized_residual = np.concatenate(
        (
            (predicted_storage - storage_modulus_pa) / normalization_modulus_pa,
            (predicted_loss - loss_modulus_pa) / normalization_modulus_pa,
        )
    )
    rss = max(float(np.sum(normalized_residual**2)), np.finfo(float).tiny)
    observation_count = len(normalized_residual)
    parameter_count = 1 + 2 * term_count
    bic = observation_count * math.log(rss / observation_count) + parameter_count * math.log(
        observation_count
    )
    return _PronyCandidate(
        term_count=term_count,
        equilibrium_modulus_pa=equilibrium,
        shear_moduli_pa=tuple(float(item) for item in amplitudes),
        relaxation_times_s=tuple(float(item) for item in relaxation_times),
        predicted_modulus_pa=np.vstack((predicted_storage, predicted_loss)),
        normalized_rmse=math.sqrt(rss / observation_count),
        bic=bic,
        function_evaluations=int(outcome.nfev),
    )


def fit_dma_prony_candidates(
    columns: dict[str, NDArray[np.float64]],
    units: dict[str, str],
    options: dict[str, Any],
) -> PolymerProcessingResult:
    """Fit bounded generalized-Maxwell candidates to a DMA frequency sweep."""

    frequency_key = _text(options, "frequency_quantity")
    storage_key = _text(options, "storage_modulus_quantity")
    loss_key = _text(options, "loss_modulus_quantity")
    if any(key not in columns for key in (frequency_key, storage_key, loss_key)):
        raise PolymerViscoelasticError("DMA fitting quantities are not mapped")
    if units.get(frequency_key) != "Hz" or any(
        units.get(key) != "Pa" for key in (storage_key, loss_key)
    ):
        raise PolymerViscoelasticError(
            "DMA fitting requires normalized frequency unit Hz and modulus unit Pa"
        )
    frequency_hz = columns[frequency_key]
    storage_modulus_pa = columns[storage_key]
    loss_modulus_pa = columns[loss_key]
    if len(frequency_hz) < 5 or np.any(frequency_hz <= 0) or np.any(np.diff(frequency_hz) <= 0):
        raise PolymerViscoelasticError(
            "DMA fitting requires at least five positive, sorted, unique frequencies"
        )
    if np.any(storage_modulus_pa <= 0) or np.any(loss_modulus_pa < 0):
        raise PolymerViscoelasticError(
            "DMA fitting requires positive storage and non-negative loss modulus"
        )
    counts = _candidate_term_counts(options)
    selection_mode = _text(options, "selection_mode")
    selected_term_count = _integer(options, "selected_term_count")
    normalization = _number(options, "normalization_modulus_pa")
    minimum_tau = _number(options, "minimum_relaxation_time_s")
    maximum_tau = _number(options, "maximum_relaxation_time_s")
    maximum_evaluations = _integer(options, "maximum_function_evaluations")
    selection_reason = _text(options, "selection_reason")
    if normalization <= 0 or minimum_tau <= 0 or minimum_tau >= maximum_tau:
        raise PolymerViscoelasticError("normalization and relaxation-time bounds are invalid")
    if not 50 <= maximum_evaluations <= 100_000:
        raise PolymerViscoelasticError("maximum_function_evaluations must be within 50..100000")
    if selection_mode not in {"automatic_bic", "manual"}:
        raise PolymerViscoelasticError("selection_mode must be automatic_bic or manual")
    if selection_mode == "manual" and selected_term_count not in counts:
        raise PolymerViscoelasticError("manual selected_term_count must be a fitted candidate")
    candidates = tuple(
        _fit_frequency_candidate(
            frequency_hz,
            storage_modulus_pa,
            loss_modulus_pa,
            term_count=count,
            normalization_modulus_pa=normalization,
            minimum_relaxation_time_s=minimum_tau,
            maximum_relaxation_time_s=maximum_tau,
            maximum_function_evaluations=maximum_evaluations,
        )
        for count in counts
    )
    selected = (
        min(candidates, key=lambda item: (item.bic, item.term_count))
        if selection_mode == "automatic_bic"
        else next(item for item in candidates if item.term_count == selected_term_count)
    )
    result = dict(columns)
    result_units: dict[str, str] = {}
    diagnostics: list[str] = []
    scalars: list[PolymerScalar] = []
    for candidate in candidates:
        storage_prediction, loss_prediction = candidate.predicted_modulus_pa
        storage_output = f"modulus.storage.prony.candidate_{candidate.term_count}_term"
        loss_output = f"modulus.loss.prony.candidate_{candidate.term_count}_term"
        result[storage_output] = storage_prediction
        result[loss_output] = loss_prediction
        result_units[storage_output] = "Pa"
        result_units[loss_output] = "Pa"
        diagnostics.append(
            f"{candidate.term_count}-term DMA candidate: joint normalized RMSE="
            f"{candidate.normalized_rmse:.8g}, BIC={candidate.bic:.8g}, "
            f"nfev={candidate.function_evaluations}"
        )
        scalars.extend(
            (
                PolymerScalar(
                    f"prony_{candidate.term_count}_normalized_rmse",
                    "statistics.root_mean_square.normalized",
                    candidate.normalized_rmse,
                    "1",
                ),
                PolymerScalar(
                    f"prony_{candidate.term_count}_bic",
                    "statistics.bayesian_information_criterion",
                    candidate.bic,
                    "1",
                ),
            )
        )
    selected_storage, selected_loss = selected.predicted_modulus_pa
    result["modulus.storage.prony.selected"] = selected_storage
    result["modulus.loss.prony.selected"] = selected_loss
    result_units["modulus.storage.prony.selected"] = "Pa"
    result_units["modulus.loss.prony.selected"] = "Pa"
    instantaneous = selected.equilibrium_modulus_pa + sum(selected.shear_moduli_pa)
    scalars.extend(
        (
            PolymerScalar(
                "prony_selected_term_count",
                "model.prony.term_count",
                float(selected.term_count),
                "1",
            ),
            PolymerScalar(
                "prony_equilibrium_modulus",
                "modulus.shear.equilibrium",
                selected.equilibrium_modulus_pa,
                "Pa",
            ),
            PolymerScalar(
                "prony_instantaneous_modulus",
                "modulus.shear.instantaneous",
                instantaneous,
                "Pa",
            ),
        )
    )
    for ordinal, (amplitude, relaxation_time) in enumerate(
        zip(selected.shear_moduli_pa, selected.relaxation_times_s, strict=True), start=1
    ):
        scalars.extend(
            (
                PolymerScalar(
                    f"prony_g_ratio_{ordinal}",
                    "model.prony.shear_ratio",
                    amplitude / instantaneous,
                    "1",
                ),
                PolymerScalar(
                    f"prony_relaxation_time_{ordinal}",
                    "time.relaxation",
                    relaxation_time,
                    "s",
                ),
            )
        )
    diagnostics.extend(
        (
            f"selected {selected.term_count}-term DMA candidate by {selection_mode}",
            f"engineering selection reason: {selection_reason}",
            "storage and loss modulus share one generalized-Maxwell parameter set",
            "frequency-domain fit is reference evidence; promotion requires review",
        )
    )
    return PolymerProcessingResult(
        columns=result,
        units=result_units,
        diagnostics=tuple(diagnostics),
        scalars=tuple(scalars),
    )
