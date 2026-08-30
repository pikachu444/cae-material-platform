"""Independent Decimal reference for fixed-frequency DMA temperature shifts.

This module intentionally imports no production calculation code.
"""

from __future__ import annotations

from decimal import Decimal, localcontext

PI = Decimal("3.1415926535897932384626433832795028841971693993751")
LN_10 = Decimal("2.3025850929940456840179914546843642076011014886288")
R = Decimal("8.31446261815324")


def angular_frequency(frequency_hz: str) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return +(Decimal(2) * PI * Decimal(frequency_hz))


def wlf_log10_shift(
    temperature_k: str,
    reference_temperature_k: str,
    c1: str,
    c2_k: str,
) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        temperature = Decimal(temperature_k)
        reference = Decimal(reference_temperature_k)
        delta = temperature - reference
        if delta == 0:
            return Decimal(0)
        return +(-Decimal(c1) * delta / (Decimal(c2_k) + delta))


def arrhenius_log10_shift(
    temperature_k: str,
    reference_temperature_k: str,
    activation_energy_j_per_mol: str,
) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        temperature = Decimal(temperature_k)
        reference = Decimal(reference_temperature_k)
        if temperature == reference:
            return Decimal(0)
        return +(
            Decimal(activation_energy_j_per_mol)
            / (LN_10 * R)
            * (Decimal(1) / temperature - Decimal(1) / reference)
        )


def reduced_angular_frequency(frequency_hz: str, log10_a_t: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        shift_factor = (LN_10 * log10_a_t).exp()
        return +(angular_frequency(frequency_hz) * shift_factor)


def loss_modulus(storage_modulus_pa: str, tan_delta: str) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return +(Decimal(storage_modulus_pa) * Decimal(tan_delta))


def generalized_maxwell_storage(
    g_inf_pa: str,
    terms: tuple[tuple[str, str], ...],
    omega_rad_per_s: Decimal,
) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        value = Decimal(g_inf_pa)
        for modulus_pa, relaxation_time_s in terms:
            scaled = omega_rad_per_s * Decimal(relaxation_time_s)
            value += Decimal(modulus_pa) * scaled**2 / (Decimal(1) + scaled**2)
        return +value


def generalized_maxwell_loss(
    terms: tuple[tuple[str, str], ...],
    omega_rad_per_s: Decimal,
) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        value = Decimal(0)
        for modulus_pa, relaxation_time_s in terms:
            scaled = omega_rad_per_s * Decimal(relaxation_time_s)
            value += Decimal(modulus_pa) * scaled / (Decimal(1) + scaled**2)
        return +value
