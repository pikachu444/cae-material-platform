"""Governed fixed-frequency DMA temperature-sweep reduction.

The kernel is deliberately limited to loss-modulus derivation and horizontal
time-temperature superposition.  It does not interpolate, smooth, resample,
or fit Prony terms; the existing linear-viscoelastic calibration boundary owns
the latter operation.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

import pyarrow as pa
import pyarrow.parquet as pq

from cmp.shared.domain.revisions import content_sha256

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
UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K = 8.31446261815324

DMA_LOSS_MODULUS_COLUMNS = (
    "source_ordinal",
    "temperature_k",
    "frequency_hz",
    "storage_modulus_pa",
    "tan_delta",
    "loss_modulus_pa",
)
DMA_FREQUENCY_MASTER_CURVE_COLUMNS = (
    "source_ordinal",
    "temperature_k",
    "source_frequency_hz",
    "angular_frequency_rad_per_s",
    "log10_a_t",
    "shift_factor",
    "reduced_angular_frequency_rad_per_s",
    "storage_modulus_pa",
    "loss_modulus_pa",
    "partition",
    "exclusion_reason",
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
        if self.source_ordinal < 0:
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
        if self.source_ordinal < 0:
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
        if not math.isfinite(self.reference_temperature_k) or self.reference_temperature_k <= 0:
            raise _fail(
                4305,
                "tabulated shift reference temperature is invalid",
                "Provide the positive reference temperature used by the shift-factor table.",
            )
        if not self.log10_a_t_by_temperature_k:
            raise _fail(
                4305,
                "tabulated shift factors are empty",
                "Provide one log10(aT) value for every included temperature.",
            )
        temperatures = [item[0] for item in self.log10_a_t_by_temperature_k]
        if len(set(temperatures)) != len(temperatures):
            raise _fail(
                4305,
                "tabulated shift temperatures are duplicated",
                "Provide exactly one factor per included temperature.",
            )
        if any(
            not math.isfinite(t) or t <= 0 or not math.isfinite(a)
            for t, a in self.log10_a_t_by_temperature_k
        ):
            raise _fail(
                4305,
                "tabulated shift factors are invalid",
                "Correct the temperature or log10(aT) values.",
            )
        by_temperature = dict(self.log10_a_t_by_temperature_k)
        if (
            self.reference_temperature_k not in by_temperature
            or by_temperature[self.reference_temperature_k] != 0.0
        ):
            raise _fail(
                4305,
                "tabulated shift factors do not define log10(aT)=0 at the reference temperature",
                "Include the reference temperature with an exact zero log10 shift factor.",
            )


@dataclass(frozen=True, slots=True)
class WlfShiftLaw:
    reference_temperature_k: float
    c1: float
    c2_k: float
    kind: str = "wlf"

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.reference_temperature_k)
            or self.reference_temperature_k <= 0
            or not math.isfinite(self.c1)
            or self.c1 <= 0
            or not math.isfinite(self.c2_k)
            or self.c2_k <= 0
        ):
            raise _fail(
                4306,
                "WLF settings are invalid",
                "Provide positive finite Tref, C1, and C2 in Kelvin.",
            )


@dataclass(frozen=True, slots=True)
class ArrheniusShiftLaw:
    reference_temperature_k: float
    activation_energy_j_per_mol: float
    gas_constant_j_per_mol_k: float = UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K
    kind: str = "arrhenius"

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.reference_temperature_k)
            or self.reference_temperature_k <= 0
            or not math.isfinite(self.activation_energy_j_per_mol)
            or self.activation_energy_j_per_mol <= 0
            or self.gas_constant_j_per_mol_k != UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K
        ):
            raise _fail(
                4308,
                "Arrhenius settings are missing or invalid",
                "Provide positive finite Tref and activation energy with the declared "
                "gas constant.",
            )


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
    source_ordinal: int
    temperature_k: float
    source_frequency_hz: float
    angular_frequency_rad_per_s: float
    log10_a_t: float | None
    shift_factor: float | None
    reduced_angular_frequency_rad_per_s: float | None
    storage_modulus_pa: float
    loss_modulus_pa: float
    partition: DmaPartition
    exclusion_reason: str | None


def _validate_rows(rows: Sequence[DmaTemperatureSweepRow]) -> tuple[DmaTemperatureSweepRow, ...]:
    frozen = tuple(rows)
    if len(frozen) < 2:
        raise _fail(
            4304,
            "DMA temperature sweep has fewer than two rows",
            "Import at least two temperature observations.",
        )
    if len({row.source_ordinal for row in frozen}) != len(frozen):
        raise _fail(
            4304, "source ordinals are duplicated", "Preserve each source row exactly once."
        )
    frequencies = {row.frequency_hz for row in frozen}
    if len(frequencies) != 1:
        raise _fail(
            4304,
            "cyclic frequency is not constant",
            "Split the data by exact cyclic frequency before TTS.",
        )
    return frozen


def derive_loss_modulus(rows: Sequence[DmaTemperatureSweepRow]) -> tuple[DmaLossModulusRow, ...]:
    frozen = _validate_rows(rows)
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
                source_ordinal=row.source_ordinal,
                temperature_k=row.temperature_k,
                frequency_hz=row.frequency_hz,
                storage_modulus_pa=row.storage_modulus_pa,
                tan_delta=row.tan_delta,
                loss_modulus_pa=row.storage_modulus_pa * row.tan_delta,
            )
        )
    return tuple(output)


def recommend_wlf_starting_values(
    rows: Sequence[DmaTemperatureSweepRow],
    *,
    source_evidence: Mapping[str, object],
) -> DmaWlfStartingSuggestion:
    frozen = tuple(
        sorted(_validate_rows(rows), key=lambda item: (item.temperature_k, item.source_ordinal))
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
        source_evidence=dict(source_evidence),
        reference_temperature_k=row.temperature_k,
        source_ordinal=row.source_ordinal,
        c1=17.44,
        c2_k=51.6,
        value_origin="generic_wlf_at_tg_starting_suggestion",
        material_specific=False,
        requires_confirmation=True,
        rule_id=DMA_WLF_STARTING_SUGGESTION_RULE_ID,
        rule_version=DMA_WLF_STARTING_SUGGESTION_RULE_VERSION,
        recommendation_sha256=content_sha256(canonical),
    )


def _dispositions_by_ordinal(
    rows: tuple[DmaTemperatureSweepRow, ...],
    dispositions: Sequence[DmaRowDisposition],
) -> dict[int, DmaRowDisposition]:
    by_ordinal = {item.source_ordinal: item for item in dispositions}
    expected = {row.source_ordinal for row in rows}
    if len(by_ordinal) != len(dispositions) or set(by_ordinal) != expected:
        raise _fail(
            4304,
            "row dispositions do not cover source rows exactly once",
            "Provide one CALIBRATION, HOLDOUT, or EXCLUDED decision for every source ordinal.",
        )
    if not any(item.partition is DmaPartition.CALIBRATION for item in by_ordinal.values()):
        raise _fail(
            4304, "no CALIBRATION rows remain", "Include at least one usable calibration row."
        )
    return by_ordinal


def _log10_shift(law: DmaShiftLaw, temperature_k: float) -> float:
    if isinstance(law, TabulatedShiftLaw):
        return dict(law.log10_a_t_by_temperature_k)[temperature_k]
    if temperature_k == law.reference_temperature_k:
        return 0.0
    if isinstance(law, WlfShiftLaw):
        denominator = law.c2_k + temperature_k - law.reference_temperature_k
        if temperature_k <= law.reference_temperature_k - law.c2_k or denominator <= 0:
            raise _fail(
                4307,
                "a WLF row is on or below the singular-domain boundary",
                "Exclude the row or use settings whose domain satisfies T > Tref - C2.",
            )
        return -law.c1 * (temperature_k - law.reference_temperature_k) / denominator
    return (
        law.activation_energy_j_per_mol
        / (math.log(10.0) * law.gas_constant_j_per_mol_k)
        * (1.0 / temperature_k - 1.0 / law.reference_temperature_k)
    )


def build_frequency_master_curve(
    rows: Sequence[DmaTemperatureSweepRow],
    dispositions: Sequence[DmaRowDisposition],
    shift_law: DmaShiftLaw,
    *,
    confirmed: bool,
    confirmation_reason: str,
) -> tuple[DmaFrequencyMasterCurveRow, ...]:
    frozen = _validate_rows(rows)
    if not confirmed or not confirmation_reason.strip():
        raise _fail(
            4306,
            "temperature-shift settings are not explicitly confirmed",
            "Confirm the settings and record the engineering reason before creating a TTS output.",
        )
    by_ordinal = _dispositions_by_ordinal(frozen, dispositions)
    included_temperatures = {
        row.temperature_k
        for row in frozen
        if by_ordinal[row.source_ordinal].partition is not DmaPartition.EXCLUDED
    }
    if isinstance(shift_law, TabulatedShiftLaw):
        provided = {item[0] for item in shift_law.log10_a_t_by_temperature_k}
        if provided != included_temperatures:
            raise _fail(
                4305,
                "tabulated shift factors do not cover included temperatures exactly",
                "Provide one log10(aT) for every included unique temperature and no extras.",
            )

    output: list[DmaFrequencyMasterCurveRow] = []
    for row in frozen:
        disposition = by_ordinal[row.source_ordinal]
        loss_modulus = row.usable_loss_modulus_pa
        omega = 2.0 * math.pi * row.frequency_hz
        if disposition.partition is DmaPartition.EXCLUDED:
            output.append(
                DmaFrequencyMasterCurveRow(
                    source_ordinal=row.source_ordinal,
                    temperature_k=row.temperature_k,
                    source_frequency_hz=row.frequency_hz,
                    angular_frequency_rad_per_s=omega,
                    log10_a_t=None,
                    shift_factor=None,
                    reduced_angular_frequency_rad_per_s=None,
                    storage_modulus_pa=row.storage_modulus_pa,
                    loss_modulus_pa=loss_modulus,
                    partition=disposition.partition,
                    exclusion_reason=disposition.exclusion_reason,
                )
            )
            continue
        if loss_modulus < 0:
            raise _fail(
                4304,
                "an included row has negative usable loss modulus",
                "Mark the row EXCLUDED with a reason, or correct the source quantity mapping.",
            )
        log10_a_t = _log10_shift(shift_law, row.temperature_k)
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
        output.append(
            DmaFrequencyMasterCurveRow(
                source_ordinal=row.source_ordinal,
                temperature_k=row.temperature_k,
                source_frequency_hz=row.frequency_hz,
                angular_frequency_rad_per_s=omega,
                log10_a_t=log10_a_t,
                shift_factor=shift_factor,
                reduced_angular_frequency_rad_per_s=reduced_omega,
                storage_modulus_pa=row.storage_modulus_pa,
                loss_modulus_pa=loss_modulus,
                partition=disposition.partition,
                exclusion_reason=None,
            )
        )
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


def frequency_master_curve_parquet_bytes(
    rows: Sequence[DmaFrequencyMasterCurveRow],
) -> bytes:
    frozen = tuple(rows)
    if not frozen:
        raise _fail(
            4304,
            "frequency master-curve result has no rows",
            "Provide confirmed DMA temperature-sweep rows.",
        )
    return _parquet_bytes(
        pa.table(
            {
                "source_ordinal": pa.array((row.source_ordinal for row in frozen), type=pa.int64()),
                "temperature_k": pa.array((row.temperature_k for row in frozen), type=pa.float64()),
                "source_frequency_hz": pa.array(
                    (row.source_frequency_hz for row in frozen), type=pa.float64()
                ),
                "angular_frequency_rad_per_s": pa.array(
                    (row.angular_frequency_rad_per_s for row in frozen), type=pa.float64()
                ),
                "log10_a_t": pa.array((row.log10_a_t for row in frozen), type=pa.float64()),
                "shift_factor": pa.array((row.shift_factor for row in frozen), type=pa.float64()),
                "reduced_angular_frequency_rad_per_s": pa.array(
                    (row.reduced_angular_frequency_rad_per_s for row in frozen), type=pa.float64()
                ),
                "storage_modulus_pa": pa.array(
                    (row.storage_modulus_pa for row in frozen), type=pa.float64()
                ),
                "loss_modulus_pa": pa.array(
                    (row.loss_modulus_pa for row in frozen), type=pa.float64()
                ),
                "partition": pa.array((row.partition.value for row in frozen), type=pa.string()),
                "exclusion_reason": pa.array(
                    (row.exclusion_reason for row in frozen), type=pa.string()
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
            source_ordinal=int(row["source_ordinal"]),
            temperature_k=float(row["temperature_k"]),
            frequency_hz=float(row["frequency_hz"]),
            storage_modulus_pa=float(row["storage_modulus_pa"]),
            tan_delta=float(row["tan_delta"]),
            loss_modulus_pa=float(row["loss_modulus_pa"]),
        )
        for row in table.to_pylist()
    )


def frequency_master_curve_from_parquet(
    value: bytes,
) -> tuple[DmaFrequencyMasterCurveRow, ...]:
    table = _read_exact_table(value, DMA_FREQUENCY_MASTER_CURVE_COLUMNS)
    output: list[DmaFrequencyMasterCurveRow] = []
    for row in table.to_pylist():
        output.append(
            DmaFrequencyMasterCurveRow(
                source_ordinal=int(row["source_ordinal"]),
                temperature_k=float(row["temperature_k"]),
                source_frequency_hz=float(row["source_frequency_hz"]),
                angular_frequency_rad_per_s=float(row["angular_frequency_rad_per_s"]),
                log10_a_t=None if row["log10_a_t"] is None else float(row["log10_a_t"]),
                shift_factor=None if row["shift_factor"] is None else float(row["shift_factor"]),
                reduced_angular_frequency_rad_per_s=(
                    None
                    if row["reduced_angular_frequency_rad_per_s"] is None
                    else float(row["reduced_angular_frequency_rad_per_s"])
                ),
                storage_modulus_pa=float(row["storage_modulus_pa"]),
                loss_modulus_pa=float(row["loss_modulus_pa"]),
                partition=DmaPartition(str(row["partition"])),
                exclusion_reason=(
                    None if row["exclusion_reason"] is None else str(row["exclusion_reason"])
                ),
            )
        )
    return tuple(output)
