"""Governed DMA frequency-master-curve domain contracts.

The fixed-frequency reduction and the canonical result vocabulary live here.  The
multi-frequency TTS numerical kernel is deliberately kept in
``dma_multi_frequency_tts`` so that this processing method remains an orchestration
boundary rather than a fitting monolith.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, TypedDict, cast

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.modules.processing.domain.temperature_shift import (
    UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K,
    TemperatureShiftError,
    arrhenius_log10_shift,
    validate_manual_shift_table,
    wlf_log10_shift,
)
from cmp.shared.domain.revisions import content_sha256

if TYPE_CHECKING:
    pass

_write_parquet = cast(Callable[..., None], pq.write_table)
_read_parquet = cast(Callable[..., pa.Table], pq.read_table)

DMA_LOSS_MODULUS_METHOD_ID = "polymer.dma_loss_modulus_from_tan_delta"
DMA_LOSS_MODULUS_METHOD_VERSION = "1.0.0"
DMA_FREQUENCY_MASTER_CURVE_METHOD_ID = "polymer.dma_frequency_master_curve"
DMA_FREQUENCY_MASTER_CURVE_METHOD_VERSION = "1.0.0"
DMA_WLF_STARTING_SUGGESTION_RULE_ID = "polymer.dma_wlf_starting_suggestion"
DMA_WLF_STARTING_SUGGESTION_RULE_VERSION = "1.0.0"

DMA_LOSS_MODULUS_PARQUET_SCHEMA_ID = "urn:cmp:processing:dma-loss-modulus-parquet:1.0.0"
DMA_FREQUENCY_MASTER_CURVE_PARQUET_SCHEMA_ID = (
    "urn:cmp:processing:dma-frequency-master-curve-parquet:1.0.0"
)
PARQUET_MEDIA_TYPE = "application/vnd.apache.parquet"

DMA_TTS_SCORER_ID = "cmp.dma_tts.common_log_frequency_grid_log_modulus_mse@1.0.0"
DMA_TTS_ADJACENT_OPTIMIZER_ID = "cmp.dma_tts.adjacent_overlap_log_mse.scipy_bounded@1.0.0"
DMA_TTS_LAW_OPTIMIZER_ID = "cmp.dma_tts.shift_law_log10_least_squares.scipy_trf@1.0.0"
# A source sweep is identified explicitly; this secondary guard only prevents a
# materially different measured temperature from being folded into that sweep.
# Temperature intervals have the same numerical magnitude in kelvin and Celsius.
DMA_SWEEP_TEMPERATURE_TOLERANCE_K = Decimal("0.5")
DMA_TTS_WARNINGS = (
    "DMA_TTS_LVR_EVIDENCE_MISSING",
    "DMA_TTS_TEMPERATURE_EQUILIBRIUM_EVIDENCE_MISSING",
    "DMA_TTS_PRECONDITIONING_EVIDENCE_MISSING",
)

DMA_LOSS_MODULUS_COLUMNS = (
    "source_ordinal",
    "temperature_k",
    "frequency_hz",
    "storage_modulus_pa",
    "tan_delta",
    "loss_modulus_pa",
)

# This is the only DMA frequency-master-curve result shape.  It is intentionally
# ragged: one result row represents one fixed point or one complete source sweep.
DMA_FREQUENCY_MASTER_CURVE_COLUMNS = (
    "input_mode",
    "source_sweep_ordinal",
    "representative_temperature_k",
    "partition",
    "is_reference",
    "exclusion_reason",
    "holdout_evaluation_status",
    "source_ordinals",
    "measured_temperature_k",
    "source_frequency_hz",
    "angular_frequency_rad_per_s",
    "storage_modulus_pa",
    "loss_modulus_pa",
    "source_tan_delta",
    "loss_modulus_origin",
    "reduced_angular_frequency_rad_per_s",
    "raw_angular_frequency_min_rad_per_s",
    "raw_angular_frequency_max_rad_per_s",
    "shifted_angular_frequency_min_rad_per_s",
    "shifted_angular_frequency_max_rad_per_s",
    "comparison_sweep_ordinal",
    "observed_log10_a_t",
    "applied_log10_a_t",
    "shift_factor",
    "shift_residual_log10_a_t",
    "overlap_log10_reduced_angular_frequency_min",
    "overlap_log10_reduced_angular_frequency_max",
    "scoring_point_count",
    "storage_mse",
    "loss_mse",
    "storage_rmse",
    "loss_rmse",
    "weighted_mse",
    "adjacent_success",
    "adjacent_status",
    "adjacent_iterations",
    "adjacent_evaluations",
    "adjacent_objective",
)


class DmaProcessingError(ValueError):
    """A stable processing failure with an actionable recovery."""

    def __init__(self, code: str, cause: str, recovery: str) -> None:
        self.code = code
        self.cause = cause
        self.recovery = recovery
        super().__init__(f"{code}: {cause} Recovery: {recovery}")


def _fail(number: int, cause: str, recovery: str) -> DmaProcessingError:
    return DmaProcessingError(f"CMP-PROCESSING-{number}", cause, recovery)


class DmaInputMode(StrEnum):
    FIXED_FREQUENCY_TEMPERATURE_SWEEP = "fixed_frequency_temperature_sweep"
    MULTI_FREQUENCY_ISOTHERMS = "multi_frequency_isotherms"


class DmaPartition(StrEnum):
    CALIBRATION = "CALIBRATION"
    HOLDOUT = "HOLDOUT"
    EXCLUDED = "EXCLUDED"


@dataclass(frozen=True, slots=True)
class DmaTemperatureSweepRow:
    source_ordinal: int
    temperature_k: float
    frequency_hz: float
    storage_modulus_pa: float
    loss_modulus_pa: float | None = None
    tan_delta: float | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.source_ordinal, bool)
            or self.source_ordinal < 0
            or self.source_ordinal > 9_223_372_036_854_775_807
        ):
            raise _fail(
                4304, "source ordinal is negative", "Preserve a nonnegative source row ordinal."
            )
        if not math.isfinite(self.temperature_k) or self.temperature_k <= 0:
            raise _fail(
                4304, "temperature is not positive Kelvin", "Correct the temperature unit mapping."
            )
        if not math.isfinite(self.frequency_hz) or self.frequency_hz <= 0:
            raise _fail(
                4304,
                "cyclic frequency is missing or nonpositive",
                "Provide one positive fixed frequency in Hz.",
            )
        if not math.isfinite(self.storage_modulus_pa) or self.storage_modulus_pa <= 0:
            raise _fail(
                4304,
                "storage modulus is not positive",
                "Correct the storage-modulus quantity and unit mapping.",
            )
        if self.loss_modulus_pa is None and self.tan_delta is None:
            raise _fail(
                4304,
                "neither loss modulus nor tan delta is available",
                "Map loss modulus, tan delta, or both.",
            )
        if self.loss_modulus_pa is not None and not math.isfinite(self.loss_modulus_pa):
            raise _fail(
                4304, "loss modulus is not finite", "Correct or exclude the affected source row."
            )
        if self.tan_delta is not None and not math.isfinite(self.tan_delta):
            raise _fail(
                4304, "tan delta is not finite", "Correct or exclude the affected source row."
            )

    @property
    def usable_loss_modulus_pa(self) -> float:
        if self.loss_modulus_pa is not None:
            return self.loss_modulus_pa
        assert self.tan_delta is not None
        return self.storage_modulus_pa * self.tan_delta

    @property
    def loss_factor(self) -> float:
        if self.tan_delta is not None:
            return self.tan_delta
        assert self.loss_modulus_pa is not None
        return self.loss_modulus_pa / self.storage_modulus_pa


@dataclass(frozen=True, slots=True)
class DmaRowDisposition:
    source_ordinal: int
    partition: DmaPartition
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.source_ordinal, bool) or self.source_ordinal < 0:
            raise _fail(
                4304,
                "disposition source ordinal is negative",
                "Use the exact nonnegative source ordinal.",
            )
        if self.partition is DmaPartition.EXCLUDED:
            if self.exclusion_reason is None or not self.exclusion_reason.strip():
                raise _fail(
                    4304, "excluded row has no reason", "Record why the source row is excluded."
                )
        elif self.exclusion_reason is not None:
            raise _fail(
                4304,
                "included row carries an exclusion reason",
                "Remove the reason or mark the row EXCLUDED.",
            )


@dataclass(frozen=True, slots=True)
class TabulatedShiftLaw:
    reference_temperature_k: float
    log10_a_t_by_temperature_k: tuple[tuple[float, float], ...]
    kind: str = "tabulated"

    def __post_init__(self) -> None:
        try:
            validate_manual_shift_table(
                self.log10_a_t_by_temperature_k,
                reference_temperature_k=self.reference_temperature_k,
                required_temperatures=tuple(item[0] for item in self.log10_a_t_by_temperature_k),
            )
        except TemperatureShiftError as error:
            raise _fail(
                4305,
                f"tabulated shift factors are invalid: {error}",
                (
                    "Provide finite unique temperatures and an exact zero at the "
                    "reference temperature."
                ),
            ) from error


@dataclass(frozen=True, slots=True)
class WlfShiftLaw:
    reference_temperature_k: float
    c1: float
    c2_k: float
    kind: str = "wlf"

    def __post_init__(self) -> None:
        try:
            wlf_log10_shift(
                self.reference_temperature_k, self.reference_temperature_k, self.c1, self.c2_k
            )
        except TemperatureShiftError as error:
            raise _fail(
                4306,
                f"WLF settings are invalid: {error}",
                "Provide positive finite Tref, C1, and C2 in Kelvin.",
            ) from error


@dataclass(frozen=True, slots=True)
class ArrheniusShiftLaw:
    reference_temperature_k: float
    activation_energy_j_per_mol: float
    gas_constant_j_per_mol_k: float = UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K
    kind: str = "arrhenius"

    def __post_init__(self) -> None:
        try:
            arrhenius_log10_shift(
                self.reference_temperature_k,
                self.reference_temperature_k,
                self.activation_energy_j_per_mol,
                self.gas_constant_j_per_mol_k,
            )
        except TemperatureShiftError as error:
            raise _fail(
                4308,
                f"Arrhenius settings are invalid: {error}",
                (
                    "Provide positive finite Tref and activation energy with the "
                    "declared gas constant."
                ),
            ) from error


DmaShiftLaw = TabulatedShiftLaw | WlfShiftLaw | ArrheniusShiftLaw


@dataclass(frozen=True, slots=True)
class DmaWlfStartingSuggestion:
    source_evidence: Mapping[str, object]
    reference_temperature_k: float
    source_ordinal: int
    c1: float
    c2_k: float
    value_origin: str
    material_specific: bool
    requires_confirmation: bool
    rule_id: str
    rule_version: str
    recommendation_sha256: str

    def canonical_without_digest(self) -> dict[str, object]:
        return {
            "source_evidence": dict(self.source_evidence),
            "reference_temperature_k": self.reference_temperature_k,
            "source_ordinal": self.source_ordinal,
            "c1": self.c1,
            "c2_k": self.c2_k,
            "value_origin": self.value_origin,
            "material_specific": self.material_specific,
            "requires_confirmation": self.requires_confirmation,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
        }


@dataclass(frozen=True, slots=True)
class DmaLossModulusRow:
    source_ordinal: int
    temperature_k: float
    frequency_hz: float
    storage_modulus_pa: float
    tan_delta: float
    loss_modulus_pa: float


@dataclass(frozen=True, slots=True)
class DmaFrequencyMasterCurveRow:
    """One row of the sole canonical ragged DMA result."""

    input_mode: str
    source_sweep_ordinal: int | None
    representative_temperature_k: float
    partition: DmaPartition
    is_reference: bool
    exclusion_reason: str | None
    holdout_evaluation_status: str | None
    source_ordinals: tuple[int, ...]
    measured_temperature_k: tuple[float, ...]
    source_frequency_hz: tuple[float, ...]
    angular_frequency_rad_per_s: tuple[float, ...]
    storage_modulus_pa: tuple[float, ...]
    loss_modulus_pa: tuple[float, ...]
    reduced_angular_frequency_rad_per_s: tuple[float, ...] | None
    raw_angular_frequency_min_rad_per_s: float
    raw_angular_frequency_max_rad_per_s: float
    shifted_angular_frequency_min_rad_per_s: float | None
    shifted_angular_frequency_max_rad_per_s: float | None
    comparison_sweep_ordinal: int | None
    observed_log10_a_t: float | None
    applied_log10_a_t: float | None
    shift_factor: float | None
    shift_residual_log10_a_t: float | None
    overlap_log10_reduced_angular_frequency_min: float | None
    overlap_log10_reduced_angular_frequency_max: float | None
    scoring_point_count: int | None
    storage_mse: float | None
    loss_mse: float | None
    storage_rmse: float | None
    loss_rmse: float | None
    weighted_mse: float | None
    adjacent_success: bool | None
    adjacent_status: int | None
    adjacent_iterations: int | None
    adjacent_evaluations: int | None
    adjacent_objective: float | None
    source_tan_delta: tuple[float | None, ...]
    loss_modulus_origin: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.input_mode not in {item.value for item in DmaInputMode}:
            raise _fail(
                4317,
                "result input_mode is unsupported",
                "Reload the exact current DMA result Artifact.",
            )
        if (
            not math.isfinite(self.representative_temperature_k)
            or self.representative_temperature_k <= 0
        ):
            raise _fail(
                4317,
                "result representative temperature is invalid",
                "Reload the exact current DMA result Artifact.",
            )
        if self.input_mode == DmaInputMode.MULTI_FREQUENCY_ISOTHERMS.value:
            if (
                self.source_sweep_ordinal is None
                or isinstance(self.source_sweep_ordinal, bool)
                or not 1 <= self.source_sweep_ordinal <= 9_223_372_036_854_775_807
            ):
                raise _fail(
                    4317,
                    "result source sweep ordinal is invalid",
                    "Reload the exact current DMA result Artifact.",
                )
        elif self.source_sweep_ordinal is not None:
            raise _fail(
                4317,
                "fixed result row carries a source sweep identity",
                "Reload the exact current DMA result Artifact.",
            )
        lengths = {
            len(self.source_ordinals),
            len(self.measured_temperature_k),
            len(self.source_frequency_hz),
            len(self.angular_frequency_rad_per_s),
            len(self.storage_modulus_pa),
            len(self.loss_modulus_pa),
        }
        if len(lengths) != 1 or not next(iter(lengths), 0):
            raise _fail(
                4317,
                "result raw lists are empty or have unequal lengths",
                "Reload the exact current DMA result Artifact.",
            )
        point_count = len(self.source_ordinals)
        tan_delta = self.source_tan_delta
        loss_origin = self.loss_modulus_origin
        if len(tan_delta) != point_count or len(loss_origin) != point_count:
            raise _fail(
                4317,
                "result loss evidence arrays have unequal lengths",
                "Reload the exact current DMA result Artifact.",
            )
        if any(origin not in {"measured", "derived_from_tan_delta"} for origin in loss_origin):
            raise _fail(
                4317,
                "result loss-modulus origin is unsupported",
                "Reload the exact current DMA result Artifact.",
            )
        for storage, loss, tan, origin in zip(
            self.storage_modulus_pa, self.loss_modulus_pa, tan_delta, loss_origin, strict=True
        ):
            if origin == "measured" and tan is not None:
                raise _fail(
                    4317,
                    "measured loss rows must not persist tan delta",
                    "Reload the exact DMA result Artifact.",
                )
            if origin == "derived_from_tan_delta" and (
                tan is None
                or not math.isfinite(tan)
                or not math.isclose(loss, storage * tan, rel_tol=1e-12, abs_tol=1e-12)
            ):
                raise _fail(
                    4317,
                    "derived loss evidence does not match storage modulus and tan delta",
                    "Reload the exact DMA result Artifact.",
                )
        if (
            self.input_mode == DmaInputMode.FIXED_FREQUENCY_TEMPERATURE_SWEEP.value
            and len(self.source_ordinals) != 1
        ):
            raise _fail(
                4317,
                "fixed result row is not a one-point ragged row",
                "Reload the exact current DMA result Artifact.",
            )
        if (
            any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
                or value > 9_223_372_036_854_775_807
                for value in self.source_ordinals
            )
            or tuple(sorted(self.source_ordinals)) != self.source_ordinals
            or len(set(self.source_ordinals)) != len(self.source_ordinals)
        ):
            raise _fail(
                4317,
                "result source ordinals are not canonical",
                "Reload the exact current DMA result Artifact.",
            )
        if any(
            not math.isfinite(value) or value <= 0
            for value in self.measured_temperature_k
            + self.source_frequency_hz
            + self.angular_frequency_rad_per_s
            + self.storage_modulus_pa
        ):
            raise _fail(
                4317,
                "result raw values are not finite and positive",
                "Reload the exact current DMA result Artifact.",
            )
        if any(not math.isfinite(value) for value in self.loss_modulus_pa):
            raise _fail(
                4317,
                "result loss-modulus values are not finite",
                "Reload the exact current DMA result Artifact.",
            )
        if self.input_mode == DmaInputMode.MULTI_FREQUENCY_ISOTHERMS.value and any(
            value <= 0 for value in self.loss_modulus_pa
        ):
            raise _fail(
                4317,
                "multi-frequency loss-modulus values are not positive",
                "Reload the exact current DMA result Artifact.",
            )
        if self.input_mode == DmaInputMode.MULTI_FREQUENCY_ISOTHERMS.value and any(
            origin != "measured" or tan is not None
            for origin, tan in zip(loss_origin, tan_delta, strict=True)
        ):
            raise _fail(
                4317,
                "multi-frequency loss evidence is not measured-only",
                "Reload the exact current DMA result Artifact.",
            )
        if (
            self.input_mode == DmaInputMode.FIXED_FREQUENCY_TEMPERATURE_SWEEP.value
            and self.partition is not DmaPartition.EXCLUDED
            and any(value <= 0 for value in self.loss_modulus_pa)
        ):
            raise _fail(
                4317,
                "included fixed loss-modulus values are not positive",
                "Reload the exact current DMA result Artifact.",
            )
        if (
            self.input_mode == DmaInputMode.FIXED_FREQUENCY_TEMPERATURE_SWEEP.value
            and self.representative_temperature_k != self.measured_temperature_k[0]
        ):
            raise _fail(
                4317,
                "fixed representative and measured temperatures differ",
                "Reload the exact current DMA result Artifact.",
            )
        if (
            not math.isfinite(self.raw_angular_frequency_min_rad_per_s)
            or not math.isfinite(self.raw_angular_frequency_max_rad_per_s)
            or self.raw_angular_frequency_min_rad_per_s <= 0
            or self.raw_angular_frequency_max_rad_per_s < self.raw_angular_frequency_min_rad_per_s
            or self.raw_angular_frequency_min_rad_per_s != min(self.angular_frequency_rad_per_s)
            or self.raw_angular_frequency_max_rad_per_s != max(self.angular_frequency_rad_per_s)
        ):
            raise _fail(
                4317,
                "result raw frequency bounds are inconsistent",
                "Reload the exact current DMA result Artifact.",
            )
        derived = (
            self.reduced_angular_frequency_rad_per_s,
            self.shifted_angular_frequency_min_rad_per_s,
            self.shifted_angular_frequency_max_rad_per_s,
            self.comparison_sweep_ordinal,
            self.observed_log10_a_t,
            self.applied_log10_a_t,
            self.shift_factor,
            self.shift_residual_log10_a_t,
            self.overlap_log10_reduced_angular_frequency_min,
            self.overlap_log10_reduced_angular_frequency_max,
            self.scoring_point_count,
            self.storage_mse,
            self.loss_mse,
            self.storage_rmse,
            self.loss_rmse,
            self.weighted_mse,
            self.adjacent_success,
            self.adjacent_status,
            self.adjacent_iterations,
            self.adjacent_evaluations,
            self.adjacent_objective,
        )
        if self.partition is DmaPartition.EXCLUDED:
            if (
                self.exclusion_reason is None
                or not self.exclusion_reason.strip()
                or self.is_reference
                or any(value is not None for value in (self.holdout_evaluation_status, *derived))
            ):
                raise _fail(
                    4317,
                    "excluded result row contains derived evidence",
                    "Reload the exact current DMA result Artifact.",
                )
            return
        if self.exclusion_reason is not None or self.reduced_angular_frequency_rad_per_s is None:
            raise _fail(
                4317,
                "included result row has an invalid null pattern",
                "Reload the exact current DMA result Artifact.",
            )
        reduced = self.reduced_angular_frequency_rad_per_s
        if len(reduced) != len(self.source_ordinals) or any(
            not math.isfinite(value) or value <= 0 for value in reduced
        ):
            raise _fail(
                4317,
                "result reduced-frequency list is invalid",
                "Reload the exact current DMA result Artifact.",
            )
        if (
            self.applied_log10_a_t is None
            or self.shift_factor is None
            or not math.isfinite(self.applied_log10_a_t)
            or not math.isfinite(self.shift_factor)
            or self.shift_factor <= 0
        ):
            raise _fail(
                4317,
                "included result shift is invalid",
                "Reload the exact current DMA result Artifact.",
            )
        try:
            expected_factor = 10.0**self.applied_log10_a_t
        except OverflowError as error:
            raise _fail(
                4317,
                "result shift factor overflows",
                "Reload the exact current DMA result Artifact.",
            ) from error
        if not math.isclose(
            self.shift_factor, expected_factor, rel_tol=1e-12, abs_tol=1e-12
        ) or any(
            not math.isclose(value, omega * self.shift_factor, rel_tol=1e-12, abs_tol=1e-12)
            for value, omega in zip(reduced, self.angular_frequency_rad_per_s, strict=True)
        ):
            raise _fail(
                4317,
                "result reduced frequencies do not match horizontal shifting",
                "Reload the exact current DMA result Artifact.",
            )
        if (
            self.shifted_angular_frequency_min_rad_per_s is None
            or self.shifted_angular_frequency_max_rad_per_s is None
            or self.shifted_angular_frequency_min_rad_per_s != min(reduced)
            or self.shifted_angular_frequency_max_rad_per_s != max(reduced)
        ):
            raise _fail(
                4317,
                "result shifted frequency bounds are inconsistent",
                "Reload the exact current DMA result Artifact.",
            )
        if self.is_reference:
            if (
                self.partition is not DmaPartition.CALIBRATION
                or self.observed_log10_a_t != 0.0
                or self.applied_log10_a_t != 0.0
                or self.shift_factor != 1.0
                or self.shift_residual_log10_a_t != 0.0
                or any(
                    value is not None
                    for value in (
                        self.comparison_sweep_ordinal,
                        self.overlap_log10_reduced_angular_frequency_min,
                        self.overlap_log10_reduced_angular_frequency_max,
                        self.scoring_point_count,
                        self.storage_mse,
                        self.loss_mse,
                        self.storage_rmse,
                        self.loss_rmse,
                        self.weighted_mse,
                        self.adjacent_success,
                        self.adjacent_status,
                        self.adjacent_iterations,
                        self.adjacent_evaluations,
                        self.adjacent_objective,
                    )
                )
            ):
                raise _fail(
                    4317,
                    "reference result row is inconsistent",
                    "Reload the exact current DMA result Artifact.",
                )
            return
        if self.input_mode == DmaInputMode.FIXED_FREQUENCY_TEMPERATURE_SWEEP.value:
            if self.holdout_evaluation_status != (
                "not_applicable_no_curve_overlap"
                if self.partition is DmaPartition.HOLDOUT
                else None
            ) or any(
                value is not None
                for value in (
                    self.comparison_sweep_ordinal,
                    self.observed_log10_a_t,
                    self.shift_residual_log10_a_t,
                    self.overlap_log10_reduced_angular_frequency_min,
                    self.overlap_log10_reduced_angular_frequency_max,
                    self.scoring_point_count,
                    self.storage_mse,
                    self.loss_mse,
                    self.storage_rmse,
                    self.loss_rmse,
                    self.weighted_mse,
                    self.adjacent_success,
                    self.adjacent_status,
                    self.adjacent_iterations,
                    self.adjacent_evaluations,
                    self.adjacent_objective,
                )
            ):
                raise _fail(
                    4317,
                    "fixed result row contains multi-frequency evidence",
                    "Reload the exact current DMA result Artifact.",
                )
            return
        if self.partition is DmaPartition.CALIBRATION:
            required: tuple[object, ...] = (
                self.comparison_sweep_ordinal,
                self.observed_log10_a_t,
                self.shift_residual_log10_a_t,
                self.overlap_log10_reduced_angular_frequency_min,
                self.overlap_log10_reduced_angular_frequency_max,
                self.scoring_point_count,
                self.storage_mse,
                self.loss_mse,
                self.storage_rmse,
                self.loss_rmse,
                self.weighted_mse,
                self.adjacent_success,
                self.adjacent_status,
                self.adjacent_iterations,
                self.adjacent_evaluations,
                self.adjacent_objective,
            )
            if (
                any(value is None for value in required)
                or self.holdout_evaluation_status is not None
            ):
                raise _fail(
                    4317,
                    "calibration result row has an incomplete evidence pattern",
                    "Reload the exact current DMA result Artifact.",
                )
        elif self.partition is DmaPartition.HOLDOUT:
            required = (
                self.holdout_evaluation_status,
                self.comparison_sweep_ordinal,
                self.overlap_log10_reduced_angular_frequency_min,
                self.overlap_log10_reduced_angular_frequency_max,
                self.scoring_point_count,
                self.storage_mse,
                self.loss_mse,
                self.storage_rmse,
                self.loss_rmse,
                self.weighted_mse,
            )
            if (
                any(value is None for value in required)
                or self.holdout_evaluation_status != "evaluated"
                or any(
                    value is not None
                    for value in (
                        self.observed_log10_a_t,
                        self.shift_residual_log10_a_t,
                        self.adjacent_success,
                        self.adjacent_status,
                        self.adjacent_iterations,
                        self.adjacent_evaluations,
                        self.adjacent_objective,
                    )
                )
            ):
                raise _fail(
                    4317,
                    "holdout result row has an incomplete evidence pattern",
                    "Reload the exact current DMA result Artifact.",
                )
        else:
            raise _fail(
                4317,
                "included result row has an unsupported partition",
                "Reload the exact current DMA result Artifact.",
            )


class DmaFrequencyMasterCurveRowValues(TypedDict):
    input_mode: str
    source_sweep_ordinal: int | None
    representative_temperature_k: float
    partition: DmaPartition
    is_reference: bool
    exclusion_reason: str | None
    holdout_evaluation_status: str | None
    source_ordinals: tuple[int, ...]
    measured_temperature_k: tuple[float, ...]
    source_frequency_hz: tuple[float, ...]
    angular_frequency_rad_per_s: tuple[float, ...]
    storage_modulus_pa: tuple[float, ...]
    loss_modulus_pa: tuple[float, ...]
    reduced_angular_frequency_rad_per_s: tuple[float, ...] | None
    raw_angular_frequency_min_rad_per_s: float
    raw_angular_frequency_max_rad_per_s: float
    shifted_angular_frequency_min_rad_per_s: float | None
    shifted_angular_frequency_max_rad_per_s: float | None
    comparison_sweep_ordinal: int | None
    observed_log10_a_t: float | None
    applied_log10_a_t: float | None
    shift_factor: float | None
    shift_residual_log10_a_t: float | None
    overlap_log10_reduced_angular_frequency_min: float | None
    overlap_log10_reduced_angular_frequency_max: float | None
    scoring_point_count: int | None
    storage_mse: float | None
    loss_mse: float | None
    storage_rmse: float | None
    loss_rmse: float | None
    weighted_mse: float | None
    adjacent_success: bool | None
    adjacent_status: int | None
    adjacent_iterations: int | None
    adjacent_evaluations: int | None
    adjacent_objective: float | None
    source_tan_delta: tuple[float | None, ...]
    loss_modulus_origin: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DmaFrequencyMasterCurveBuildResult:
    rows: tuple[DmaFrequencyMasterCurveRow, ...]
    input_mode: str
    reference_sweep_ordinal: int | None
    reference_temperature_k: float
    shift_law: dict[str, object]
    scoring: dict[str, object] | None
    adjacent_optimizer: dict[str, object] | None
    law_optimizer: dict[str, object] | None
    residual_summary: dict[str, object] | None
    application_intervals: tuple[dict[str, object], ...]
    application_range: dict[str, object] | None = None

    def __iter__(self) -> Iterator[DmaFrequencyMasterCurveRow]:
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> DmaFrequencyMasterCurveRow:
        return self.rows[index]


def _validate_fixed_rows(
    rows: Sequence[DmaTemperatureSweepRow],
) -> tuple[DmaTemperatureSweepRow, ...]:
    frozen = tuple(rows)
    if len(frozen) < 2:
        raise _fail(
            4304,
            "DMA temperature sweep has fewer than two rows",
            "Import at least two temperature observations.",
        )
    if tuple(row.source_ordinal for row in frozen) != tuple(range(len(frozen))):
        raise _fail(
            4304,
            "source row ordinals are not canonical zero-based ordinals",
            "Preserve source row order and assign ordinals from zero.",
        )
    if len({row.frequency_hz for row in frozen}) != 1:
        raise _fail(
            4304,
            "cyclic frequency is not constant",
            "Split the data by exact cyclic frequency before fixed-frequency TTS.",
        )
    return frozen


def _validate_fixed_loss_evidence(
    rows: Sequence[DmaTemperatureSweepRow],
) -> bool:
    """Validate the one complete fixed-frequency loss evidence mode.

    Returns whether the result is measured-loss authoritative.  A complete
    measured loss channel wins over a complete, agreeing tan-delta channel;
    partial channels and disagreement are source-contract failures.
    """

    frozen = tuple(rows)
    loss_present = tuple(row.loss_modulus_pa is not None for row in frozen)
    tan_present = tuple(row.tan_delta is not None for row in frozen)
    if len(set(loss_present)) != 1 or len(set(tan_present)) != 1:
        raise _fail(
            4312,
            "fixed DMA loss evidence is incomplete or mixed",
            "Provide one complete measured loss channel or one complete tan-delta channel.",
        )
    if not loss_present[0] and not tan_present[0]:
        raise _fail(
            4312,
            "fixed DMA has no complete loss evidence channel",
            "Provide measured loss modulus or tan delta for every source row.",
        )
    if loss_present[0] and tan_present[0]:
        for row in frozen:
            loss_modulus = row.loss_modulus_pa
            tan_delta = row.tan_delta
            if loss_modulus is None or tan_delta is None:
                raise _fail(
                    4312,
                    "fixed DMA loss evidence is incomplete or mixed",
                    "Provide one complete measured loss channel or one complete tan-delta channel.",
                )
            if not math.isclose(
                loss_modulus,
                row.storage_modulus_pa * tan_delta,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise _fail(
                    4312,
                    "fixed measured loss modulus conflicts with tan delta",
                    (
                        "Correct the loss/tan-delta source channels or create a corrected "
                        "immutable Test Data revision."
                    ),
                )
    return loss_present[0]


def derive_loss_modulus(rows: Sequence[DmaTemperatureSweepRow]) -> tuple[DmaLossModulusRow, ...]:
    frozen = _validate_fixed_rows(rows)
    output: list[DmaLossModulusRow] = []
    for row in frozen:
        if row.tan_delta is None:
            raise _fail(
                4304,
                "tan delta is absent from a requested loss derivation",
                "Use measured loss modulus or map tan delta for every derived row.",
            )
        output.append(
            DmaLossModulusRow(
                row.source_ordinal,
                row.temperature_k,
                row.frequency_hz,
                row.storage_modulus_pa,
                row.tan_delta,
                row.storage_modulus_pa * row.tan_delta,
            )
        )
    return tuple(output)


def recommend_wlf_starting_values(
    rows: Sequence[DmaTemperatureSweepRow], *, source_evidence: Mapping[str, object]
) -> DmaWlfStartingSuggestion:
    frozen = tuple(
        sorted(
            _validate_fixed_rows(rows), key=lambda item: (item.temperature_k, item.source_ordinal)
        )
    )
    positive = tuple(
        (row.loss_factor, index, row) for index, row in enumerate(frozen) if row.loss_factor > 0
    )
    if not positive:
        raise _fail(
            4301,
            "no positive loss-factor peak is available",
            "Provide usable loss-factor evidence or enter shift settings manually.",
        )
    maximum = max(item[0] for item in positive)
    maxima = tuple(item for item in positive if item[0] == maximum)
    if len(maxima) != 1:
        raise _fail(
            4302,
            "the positive loss-factor maximum is tied",
            "Choose the reference temperature explicitly or provide source shift factors.",
        )
    _, index, row = maxima[0]
    if index == 0 or index == len(frozen) - 1:
        raise _fail(
            4303,
            "the loss-factor maximum is at the temperature-sweep endpoint",
            "Extend the sweep or choose the reference temperature explicitly.",
        )
    canonical: dict[str, object] = {
        "source_evidence": dict(source_evidence),
        "reference_temperature_k": row.temperature_k,
        "source_ordinal": row.source_ordinal,
        "c1": 17.44,
        "c2_k": 51.6,
        "value_origin": "generic_wlf_at_tg_starting_suggestion",
        "material_specific": False,
        "requires_confirmation": True,
        "rule_id": DMA_WLF_STARTING_SUGGESTION_RULE_ID,
        "rule_version": DMA_WLF_STARTING_SUGGESTION_RULE_VERSION,
    }
    return DmaWlfStartingSuggestion(
        dict(source_evidence),
        row.temperature_k,
        row.source_ordinal,
        17.44,
        51.6,
        "generic_wlf_at_tg_starting_suggestion",
        False,
        True,
        DMA_WLF_STARTING_SUGGESTION_RULE_ID,
        DMA_WLF_STARTING_SUGGESTION_RULE_VERSION,
        content_sha256(canonical),
    )


def _fixed_dispositions(
    rows: tuple[DmaTemperatureSweepRow, ...], dispositions: Sequence[DmaRowDisposition]
) -> dict[int, DmaRowDisposition]:
    by_ordinal = {item.source_ordinal: item for item in dispositions}
    if len(by_ordinal) != len(dispositions) or set(by_ordinal) != {
        row.source_ordinal for row in rows
    }:
        raise _fail(
            4304,
            "row dispositions do not cover source rows exactly once",
            "Provide one decision for every canonical zero-based source ordinal.",
        )
    if not any(item.partition is DmaPartition.CALIBRATION for item in by_ordinal.values()):
        raise _fail(
            4304, "no CALIBRATION rows remain", "Include at least one usable calibration row."
        )
    return by_ordinal


def _fixed_shift(law: DmaShiftLaw, temperature_k: float) -> float:
    if isinstance(law, TabulatedShiftLaw):
        try:
            return dict(law.log10_a_t_by_temperature_k)[temperature_k]
        except KeyError as error:
            raise _fail(
                4305,
                "tabulated shift is missing a required temperature",
                "Provide one exact shift for every nonexcluded temperature.",
            ) from error
    if temperature_k == law.reference_temperature_k:
        return 0.0
    try:
        if isinstance(law, WlfShiftLaw):
            return wlf_log10_shift(temperature_k, law.reference_temperature_k, law.c1, law.c2_k)
        return arrhenius_log10_shift(
            temperature_k,
            law.reference_temperature_k,
            law.activation_energy_j_per_mol,
            law.gas_constant_j_per_mol_k,
        )
    except TemperatureShiftError as error:
        raise _fail(
            4307,
            f"temperature shift is outside the governed domain: {error}",
            (
                "Exclude the row or use shift settings whose domain is safe for "
                "every included temperature."
            ),
        ) from error


def _fixed_canonical_law(law: DmaShiftLaw) -> dict[str, object]:
    if isinstance(law, TabulatedShiftLaw):
        return {
            "kind": "manual_tabulated",
            "reference_temperature_k": law.reference_temperature_k,
            "parameter_source": "supplied",
            "manual_table": [
                {"temperature_k": temperature, "log10_a_t": shift}
                for temperature, shift in law.log10_a_t_by_temperature_k
            ],
        }
    if isinstance(law, WlfShiftLaw):
        return {
            "kind": "wlf",
            "reference_temperature_k": law.reference_temperature_k,
            "parameter_source": "supplied",
            "c1": law.c1,
            "c2_k": law.c2_k,
        }
    return {
        "kind": "arrhenius",
        "reference_temperature_k": law.reference_temperature_k,
        "parameter_source": "supplied",
        "activation_energy_j_per_mol": law.activation_energy_j_per_mol,
        "gas_constant_j_per_mol_k": law.gas_constant_j_per_mol_k,
    }


def build_frequency_master_curve(
    rows: Sequence[DmaTemperatureSweepRow],
    dispositions: Sequence[DmaRowDisposition],
    shift_law: DmaShiftLaw,
    *,
    confirmed: bool,
    confirmation_reason: str,
) -> tuple[DmaFrequencyMasterCurveRow, ...]:
    frozen = _validate_fixed_rows(rows)
    measured_loss = _validate_fixed_loss_evidence(frozen)
    if not confirmed or not confirmation_reason.strip():
        raise _fail(
            4306,
            "temperature-shift settings are not explicitly confirmed",
            "Confirm the settings and record the engineering reason before creating a TTS output.",
        )
    by_ordinal = _fixed_dispositions(frozen, dispositions)
    included = tuple(
        row
        for row in frozen
        if by_ordinal[row.source_ordinal].partition is not DmaPartition.EXCLUDED
    )
    reference_matches = tuple(
        row
        for row in included
        if row.temperature_k == shift_law.reference_temperature_k
        and by_ordinal[row.source_ordinal].partition is DmaPartition.CALIBRATION
    )
    duplicate_reference = tuple(
        row for row in included if row.temperature_k == shift_law.reference_temperature_k
    )
    if len(reference_matches) != 1 or len(duplicate_reference) != 1:
        raise _fail(
            4316,
            "reference temperature does not identify exactly one nonexcluded calibration row",
            (
                "Use the exact temperature of one calibration row and remove "
                "duplicate included reference temperatures."
            ),
        )
    if isinstance(shift_law, TabulatedShiftLaw) and {
        item[0] for item in shift_law.log10_a_t_by_temperature_k
    } != {row.temperature_k for row in included}:
        raise _fail(
            4305,
            "tabulated shift factors do not cover included temperatures exactly",
            "Provide one log10(aT) for every included unique temperature and no extras.",
        )
    output: list[DmaFrequencyMasterCurveRow] = []
    for row in sorted(frozen, key=lambda item: (item.temperature_k, item.source_ordinal)):
        disposition = by_ordinal[row.source_ordinal]
        loss_modulus = row.usable_loss_modulus_pa
        omega = 2.0 * math.pi * row.frequency_hz
        common: DmaFrequencyMasterCurveRowValues = {
            "input_mode": DmaInputMode.FIXED_FREQUENCY_TEMPERATURE_SWEEP.value,
            "source_sweep_ordinal": None,
            "representative_temperature_k": row.temperature_k,
            "partition": disposition.partition,
            "is_reference": False,
            "exclusion_reason": disposition.exclusion_reason,
            "holdout_evaluation_status": None,
            "source_ordinals": (row.source_ordinal,),
            "measured_temperature_k": (row.temperature_k,),
            "source_frequency_hz": (row.frequency_hz,),
            "angular_frequency_rad_per_s": (omega,),
            "storage_modulus_pa": (row.storage_modulus_pa,),
            "loss_modulus_pa": (loss_modulus,),
            "source_tan_delta": ((None,) if measured_loss else (row.tan_delta,)),
            "loss_modulus_origin": (
                ("measured",) if measured_loss else ("derived_from_tan_delta",)
            ),
            "reduced_angular_frequency_rad_per_s": None,
            "raw_angular_frequency_min_rad_per_s": omega,
            "raw_angular_frequency_max_rad_per_s": omega,
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
            output.append(DmaFrequencyMasterCurveRow(**common))
            continue
        if loss_modulus <= 0:
            raise _fail(
                4312,
                "an included row has negative usable loss modulus or another nonpositive value",
                "Mark the row EXCLUDED with a reason, or correct the source quantity mapping.",
            )
        log10_a_t = _fixed_shift(shift_law, row.temperature_k)
        try:
            shift_factor = 10.0**log10_a_t
        except OverflowError as error:
            raise _fail(
                4306,
                "temperature shift overflows the usable numerical domain",
                "Review the shift parameters or exclude the affected temperature.",
            ) from error
        reduced_omega = omega * shift_factor
        if not all(math.isfinite(value) and value > 0 for value in (shift_factor, reduced_omega)):
            raise _fail(
                4306,
                "temperature shift overflows the usable numerical domain",
                "Review the shift parameters or exclude the affected temperature.",
            )
        is_reference = row.source_ordinal == reference_matches[0].source_ordinal
        common["is_reference"] = is_reference
        common["exclusion_reason"] = None
        common["holdout_evaluation_status"] = (
            "not_applicable_no_curve_overlap"
            if disposition.partition is DmaPartition.HOLDOUT
            else None
        )
        common["reduced_angular_frequency_rad_per_s"] = (reduced_omega,)
        common["shifted_angular_frequency_min_rad_per_s"] = reduced_omega
        common["shifted_angular_frequency_max_rad_per_s"] = reduced_omega
        common["observed_log10_a_t"] = 0.0 if is_reference else None
        common["applied_log10_a_t"] = log10_a_t
        common["shift_factor"] = shift_factor
        common["shift_residual_log10_a_t"] = 0.0 if is_reference else None
        output.append(DmaFrequencyMasterCurveRow(**common))
    return tuple(output)


def _parquet_bytes(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    _write_parquet(
        table,
        sink,
        compression="zstd",
        version="2.6",
        data_page_version="2.0",
        use_dictionary=False,
        write_statistics=True,
    )
    return cast(bytes, sink.getvalue().to_pybytes())


def loss_modulus_parquet_bytes(rows: Sequence[DmaLossModulusRow]) -> bytes:
    frozen = tuple(rows)
    if not frozen:
        raise _fail(
            4304, "loss-modulus result has no rows", "Provide mapped DMA temperature-sweep rows."
        )
    return _parquet_bytes(
        pa.table(
            {
                "source_ordinal": pa.array((row.source_ordinal for row in frozen), type=pa.int64()),
                "temperature_k": pa.array((row.temperature_k for row in frozen), type=pa.float64()),
                "frequency_hz": pa.array((row.frequency_hz for row in frozen), type=pa.float64()),
                "storage_modulus_pa": pa.array(
                    (row.storage_modulus_pa for row in frozen), type=pa.float64()
                ),
                "tan_delta": pa.array((row.tan_delta for row in frozen), type=pa.float64()),
                "loss_modulus_pa": pa.array(
                    (row.loss_modulus_pa for row in frozen), type=pa.float64()
                ),
            }
        )
    )


def _read_exact_table(value: bytes, columns: tuple[str, ...]) -> pa.Table:
    try:
        table = _read_parquet(pa.BufferReader(value))
    except (pa.ArrowInvalid, OSError) as error:
        raise _fail(
            4310, "derived Parquet bytes are invalid", "Reload the exact immutable result Artifact."
        ) from error
    if tuple(table.column_names) != columns or table.num_rows < 1:
        raise _fail(
            4310,
            "derived Parquet schema or row count is invalid",
            "Use the declared result schema without column or row changes.",
        )
    return table


def loss_modulus_from_parquet(value: bytes) -> tuple[DmaLossModulusRow, ...]:
    table = _read_exact_table(value, DMA_LOSS_MODULUS_COLUMNS)
    return tuple(
        DmaLossModulusRow(
            int(row["source_ordinal"]),
            float(row["temperature_k"]),
            float(row["frequency_hz"]),
            float(row["storage_modulus_pa"]),
            float(row["tan_delta"]),
            float(row["loss_modulus_pa"]),
        )
        for row in table.to_pylist()
    )


def frequency_master_curve_parquet_bytes(rows: Sequence[DmaFrequencyMasterCurveRow]) -> bytes:
    from cmp.modules.processing.domain.dma_frequency_master_curve_result import parquet_bytes

    return parquet_bytes(rows)


def frequency_master_curve_from_parquet(value: bytes) -> tuple[DmaFrequencyMasterCurveRow, ...]:
    from cmp.modules.processing.domain.dma_frequency_master_curve_result import from_parquet

    return from_parquet(value)


def __getattr__(name: str) -> object:
    """Lazily expose the separated TTS kernel without creating an import cycle."""

    names = {
        "DmaFrequencySweep",
        "DmaFrequencySweepDisposition",
        "DmaMultiFrequencyBuildResult",
        "DmaShiftLawRequest",
        "DmaTtsAdjacentOptimizerControls",
        "DmaTtsLawOptimizerControls",
        "DmaTtsScoringControls",
        "build_multi_frequency_master_curve",
    }
    if name in names:
        from cmp.modules.processing.domain import dma_multi_frequency_tts

        if name == "DmaFrequencySweep":
            return dma_multi_frequency_tts.DmaFrequencySweep
        if name == "DmaFrequencySweepDisposition":
            return dma_multi_frequency_tts.DmaFrequencySweepDisposition
        if name == "DmaMultiFrequencyBuildResult":
            return DmaFrequencyMasterCurveBuildResult
        if name == "DmaShiftLawRequest":
            return dma_multi_frequency_tts.DmaShiftLawRequest
        if name == "DmaTtsAdjacentOptimizerControls":
            return dma_multi_frequency_tts.DmaTtsAdjacentOptimizerControls
        if name == "DmaTtsLawOptimizerControls":
            return dma_multi_frequency_tts.DmaTtsLawOptimizerControls
        if name == "DmaTtsScoringControls":
            return dma_multi_frequency_tts.DmaTtsScoringControls
        if name == "build_multi_frequency_master_curve":
            return dma_multi_frequency_tts.build_multi_frequency_master_curve
    raise AttributeError(name)
