"""Small, shared temperature-shift value objects and pure equations.

This module intentionally owns no fitting lifecycle.  It is used as a narrow numerical
vocabulary by the existing relaxation/DMA code and by the multi-frequency DMA kernel.
The equations use the platform's explicit log10 shift convention:

``log10(omega_reduced) = log10(omega) + log10(aT)``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K = 8.31446261815324
SHIFT_LOG10_MIN = -20.0
SHIFT_LOG10_MAX = 20.0


class ShiftLawKind(StrEnum):
    MANUAL_TABULATED = "manual_tabulated"
    WLF_FIT = "wlf_fit"
    ARRHENIUS_FIT = "arrhenius_fit"


class TemperatureShiftError(ValueError):
    """A malformed shift-law value or domain."""


def _positive_finite(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise TemperatureShiftError(f"{name} must be positive and finite")


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise TemperatureShiftError(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class ManualShiftFactor:
    temperature_k: float
    log10_a_t: float

    def __post_init__(self) -> None:
        _positive_finite("temperature_k", self.temperature_k)
        _finite("log10_a_t", self.log10_a_t)
        if not SHIFT_LOG10_MIN <= self.log10_a_t <= SHIFT_LOG10_MAX:
            raise TemperatureShiftError("log10_a_t must be within -20..20")

    def canonical(self) -> dict[str, float]:
        return {
            "temperature_k": self.temperature_k,
            "log10_a_t": self.log10_a_t,
        }


@dataclass(frozen=True, slots=True)
class WlfParameters:
    reference_temperature_k: float
    c1: float
    c2_k: float

    def __post_init__(self) -> None:
        _positive_finite("reference_temperature_k", self.reference_temperature_k)
        _positive_finite("c1", self.c1)
        _positive_finite("c2_k", self.c2_k)

    def canonical(self) -> dict[str, float | str]:
        return {
            "kind": ShiftLawKind.WLF_FIT.value,
            "reference_temperature_k": self.reference_temperature_k,
            "c1": self.c1,
            "c2_k": self.c2_k,
        }


@dataclass(frozen=True, slots=True)
class ArrheniusParameters:
    reference_temperature_k: float
    activation_energy_j_per_mol: float
    gas_constant_j_per_mol_k: float = UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K

    def __post_init__(self) -> None:
        _positive_finite("reference_temperature_k", self.reference_temperature_k)
        _positive_finite("activation_energy_j_per_mol", self.activation_energy_j_per_mol)
        if self.gas_constant_j_per_mol_k != UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K:
            raise TemperatureShiftError(
                "gas_constant_j_per_mol_k must equal the platform fixed gas constant"
            )

    def canonical(self) -> dict[str, float | str]:
        return {
            "kind": ShiftLawKind.ARRHENIUS_FIT.value,
            "reference_temperature_k": self.reference_temperature_k,
            "activation_energy_j_per_mol": self.activation_energy_j_per_mol,
            "gas_constant_j_per_mol_k": self.gas_constant_j_per_mol_k,
        }


def wlf_log10_shift(
    temperature_k: float,
    reference_temperature_k: float,
    c1: float,
    c2_k: float,
) -> float:
    """Return the WLF log10(aT) shift for one positive temperature."""

    _positive_finite("temperature_k", temperature_k)
    parameters = WlfParameters(reference_temperature_k, c1, c2_k)
    denominator = parameters.c2_k + temperature_k - parameters.reference_temperature_k
    if denominator <= 0:
        raise TemperatureShiftError("WLF denominator must be positive")
    result = -parameters.c1 * (temperature_k - parameters.reference_temperature_k) / denominator
    _finite("WLF log10_a_t", result)
    return result


def arrhenius_log10_shift(
    temperature_k: float,
    reference_temperature_k: float,
    activation_energy_j_per_mol: float,
    gas_constant_j_per_mol_k: float = UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K,
) -> float:
    """Return the Arrhenius log10(aT) shift with the fixed gas constant."""

    _positive_finite("temperature_k", temperature_k)
    parameters = ArrheniusParameters(
        reference_temperature_k,
        activation_energy_j_per_mol,
        gas_constant_j_per_mol_k,
    )
    result = (
        parameters.activation_energy_j_per_mol
        / (math.log(10.0) * parameters.gas_constant_j_per_mol_k)
        * (1.0 / temperature_k - 1.0 / parameters.reference_temperature_k)
    )
    _finite("Arrhenius log10_a_t", result)
    return result


def validate_manual_shift_table(
    factors: Sequence[ManualShiftFactor | tuple[float, float]],
    *,
    reference_temperature_k: float,
    required_temperatures: Sequence[float],
) -> tuple[ManualShiftFactor, ...]:
    """Validate an explicit table against every non-excluded representative temperature."""

    _positive_finite("reference_temperature_k", reference_temperature_k)
    normalized = tuple(
        item if isinstance(item, ManualShiftFactor) else ManualShiftFactor(*item)
        for item in factors
    )
    if not normalized:
        raise TemperatureShiftError("manual shift table cannot be empty")
    temperatures = tuple(item.temperature_k for item in normalized)
    if len(set(temperatures)) != len(temperatures):
        raise TemperatureShiftError("manual shift temperatures must be unique")
    expected = set(float(item) for item in required_temperatures)
    if set(temperatures) != expected:
        raise TemperatureShiftError(
            "manual shift factors must cover every selected temperature exactly once "
            "(every non-excluded representative temperature)"
        )
    by_temperature = dict(zip(temperatures, normalized, strict=True))
    reference = by_temperature.get(reference_temperature_k)
    if reference is None or reference.log10_a_t != 0.0:
        raise TemperatureShiftError("reference temperature must have exact log10_a_t=0")
    return normalized


def canonical_shift_law(
    *,
    kind: ShiftLawKind | str,
    reference_temperature_k: float,
    manual_factors: Sequence[ManualShiftFactor] = (),
    c1: float | None = None,
    c2_k: float | None = None,
    activation_energy_j_per_mol: float | None = None,
    gas_constant_j_per_mol_k: float = UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K,
) -> dict[str, object]:
    """Serialize one governed shift-law declaration deterministically."""

    law_kind = ShiftLawKind(str(kind))
    if law_kind is ShiftLawKind.MANUAL_TABULATED:
        if c1 is not None or c2_k is not None or activation_energy_j_per_mol is not None:
            raise TemperatureShiftError("manual shift law cannot carry fitted parameters")
        _positive_finite("reference_temperature_k", reference_temperature_k)
        return {
            "kind": law_kind.value,
            "reference_temperature_k": reference_temperature_k,
            "factors": [item.canonical() for item in manual_factors],
        }
    if law_kind is ShiftLawKind.WLF_FIT:
        if c1 is None or c2_k is None or activation_energy_j_per_mol is not None:
            raise TemperatureShiftError("WLF shift law requires c1 and c2_k only")
        return WlfParameters(reference_temperature_k, c1, c2_k).canonical()
    if c1 is not None or c2_k is not None or activation_energy_j_per_mol is None:
        raise TemperatureShiftError("Arrhenius shift law requires activation energy only")
    return ArrheniusParameters(
        reference_temperature_k,
        activation_energy_j_per_mol,
        gas_constant_j_per_mol_k,
    ).canonical()


def shift_log10_value(
    law: Mapping[str, object], temperature_k: float, *, manual: Mapping[float, float] | None = None
) -> float:
    """Evaluate a serialized shift law without fitting or interpolation."""

    kind = str(law.get("kind"))
    reference = float(law["reference_temperature_k"])
    if kind == ShiftLawKind.MANUAL_TABULATED.value:
        values = manual
        if values is None:
            values = {
                float(item["temperature_k"]): float(item["log10_a_t"])
                for item in law.get("factors", [])
                if isinstance(item, Mapping)
            }
        try:
            return float(values[temperature_k])
        except KeyError as error:
            raise TemperatureShiftError("manual shift is missing a required temperature") from error
    if kind == ShiftLawKind.WLF_FIT.value:
        return wlf_log10_shift(temperature_k, reference, float(law["c1"]), float(law["c2_k"]))
    if kind == ShiftLawKind.ARRHENIUS_FIT.value:
        return arrhenius_log10_shift(
            temperature_k,
            reference,
            float(law["activation_energy_j_per_mol"]),
            float(law.get("gas_constant_j_per_mol_k", UNIVERSAL_GAS_CONSTANT_J_PER_MOL_K)),
        )
    raise TemperatureShiftError(f"unsupported shift law kind {kind!r}")
